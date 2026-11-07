"""The actual Store process paints before its catalog worker starts."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import ast
import select
import time

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and importlib.util.find_spec('PySide6')
                     and shutil.which('dbus-daemon'), 'requires Linux Qt and private D-Bus')
class NativeStartup(unittest.TestCase):
    def test_new_windows_and_store_worker_start_in_order(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'timing.json'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/bench-desktop.py'),
                '--samples', '1', '--verify-store-start', '--output', str(report)],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr
                             + (report.read_text() if report.exists() else ''))
            data = json.loads(report.read_text())
            for app in ('settings', 'store'):
                sample = data['apps'][app]['samples'][0]
                self.assertGreater(sample['external_first_frame_ms'], 0)
                phases = [event['phase'] for event in sample['events']]
                self.assertLess(phases.index('qml-load-start'), phases.index('first-frame'))
                if app == 'store':
                    self.assertEqual(phases.count('catalog-load-start'), 1)
                    self.assertLess(phases.index('first-frame'), phases.index('catalog-load-start'))

    def test_real_store_defers_cache_serialization_until_after_its_catalog_frame(self):
        from tests.test_look import STORE_CATALOG
        spec = importlib.util.spec_from_file_location('readiness_bench', ROOT / 'tools/bench-app-readiness.py')
        bench = importlib.util.module_from_spec(spec); spec.loader.exec_module(bench)
        with tempfile.TemporaryDirectory() as tmp, bench.private_session() as env:
            root = Path(tmp); catalog = root / 'catalog'; catalog.mkdir()
            (catalog / 'appstream.xml').write_text(STORE_CATALOG)
            helpers = bench.stage(root / 'candidate')
            source = helpers / 'monet-store'; text = source.read_text(); lines = text.splitlines(keepends=True)
            assignment = next(node for node in ast.parse(text).body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'CATALOGS' for target in node.targets))
            lines[assignment.lineno-1:assignment.end_lineno] = ['CATALOGS = (Path('+repr(str(catalog))+'),)\n']
            text = ''.join(lines).replace('def save_catalog_cache(path, identity, apps):\n',
                'def save_catalog_cache(path, identity, apps):\n    time.sleep(.5)\n')
            source.write_text(text)
            cold = bench.sample('store', helpers, env, 15)
            self.assertNotIn('error', cold, cold)
            phases = {event['phase']: event for event in cold['events'] if event.get('channel') == 'app'}
            self.assertGreaterEqual(phases['catalog-cache-write-start']['external_ms'], cold['ready-frame'])
            self.assertGreater(phases['catalog-cache-settled']['external_ms'] - cold['ready-frame'], 400)
            self.assertEqual(len(list((Path(env['XDG_CACHE_HOME'])/'monet/store/catalog').glob('*.json'))), 1)
            warm = bench.sample('store', helpers, env, 15)
            self.assertNotIn('error', warm, warm)
            phases = [event['phase'] for event in warm['events']]
            self.assertIn('catalog-cache-hit', phases)
            self.assertNotIn('catalog-cache-write-start', phases)
            # Also exercise the uninstrumented production entry point: the
            # common probe imports extra Qt bindings and must not hide a
            # missing native-window method in the real application.
            for path in (Path(env['XDG_CACHE_HOME'])/'monet/store/catalog').glob('*.json'): path.unlink()
            process = subprocess.Popen([sys.executable, str(source)],
                env=dict(env, MONET_STARTUP_TIMING='1', TMPDIR=env['XDG_RUNTIME_DIR']),
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
            output = ''; events = []
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and 'catalog-cache-settled' not in events:
                    if select.select([process.stderr], [], [], .1)[0]:
                        raw = os.read(process.stderr.fileno(), 65536)
                        if not raw: break
                        output += raw.decode('utf-8','replace')
                        events = [json.loads(line[len('MONET_STARTUP '):])['phase'] for line in output.splitlines()
                            if line.startswith('MONET_STARTUP ') and line.endswith('}')]
                self.assertIn('catalog-data-frame', events, output)
                self.assertLess(events.index('catalog-data-frame'), events.index('catalog-cache-write-start'))
                self.assertIn('catalog-cache-settled', events, output)
                self.assertNotIn('Traceback', output)
            finally:
                bench.stop(process); process.stderr.close()
