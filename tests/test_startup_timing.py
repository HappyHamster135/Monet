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


@unittest.skipUnless(sys.platform == "linux" and shutil.which("dbus-daemon"), "requires private Linux session")
class SessionStartup(unittest.TestCase):
    def stage_revision_session(self, root, env):
        helpers = root / 'helpers'; helpers.mkdir()
        events = root / 'events'
        share = root / 'share'; (share / 'monet').mkdir(parents=True)
        (share / 'monet/desktop-revision').write_text('unchanged-qml\n')
        revision = share / 'monet/session-revision'; revision.write_text('build-a\n')
        stub = helpers / 'stub'
        stub.write_text('''#!/usr/bin/python3
import os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
command=sys.argv[1] if len(sys.argv)>1 else ''
def record(event):
    with open(os.environ['MONET_SESSION_EVENTS'],'a') as out: out.write(event+'\\n')
if name=='monet-quick' and command=='zen':
    record('zen-login' if '--login' in sys.argv else 'zen-later')
    if Path(os.environ['MONET_ZEN_FAIL']).exists(): sys.exit(1)
elif name=='monet-quick' and command=='trip-apps-again': record('restore')
elif name=='monet-quick' and command=='older-pc': print('no')
elif name=='monet' and command in ('version','--version'): print('monet 0.9.8-8')
elif name=='monet-files' and command=='stacks-reconcile': record('stacks')
''')
        stub.chmod(0o755)
        for name in ('monet','monet-quick','monet-files','monet-look','monet-light','monet-profile',
                     'monet-widgets','notify-send','systemd-run'):
            (helpers / name).symlink_to(stub)
        session = root / 'monet-session'
        session.write_text((ROOT / 'linux/libexec/monet-session').read_text().replace('@BINDIR@', str(helpers))
                           .replace('@LIBEXECDIR@', str(helpers)).replace('@DATADIR@', str(share)))
        env.update(PATH=str(helpers)+os.pathsep+env['PATH'], MONET_SESSION_EVENTS=str(events), MONET_ZEN_FAIL=str(root/'fail'))
        return session, events, revision

    def test_same_version_rebuild_prepares_zen_before_restore_and_failed_preparation_retries(self):
        from tools.test import private_session, stop
        with tempfile.TemporaryDirectory() as folder, private_session() as env:
            root = Path(folder)
            session, events, revision = self.stage_revision_session(root, env)
            receipt = Path(env['XDG_CACHE_HOME']) / 'monet/zen-login-revision'
            (root / 'fail').touch()
            for build, prepare, fail in [('build-a',True,True), ('build-a',True,False),
                                         ('build-a',False,False), ('build-b',True,False)]:
                if not fail: (root / 'fail').unlink(missing_ok=True)
                revision.write_text(build+'\n'); events.unlink(missing_ok=True)
                process = subprocess.Popen(['bash',str(session)],env=env,start_new_session=True,
                                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        lines=events.read_text().splitlines() if events.exists() else []
                        if 'restore' in lines: break
                        time.sleep(.02)
                    self.assertIn('restore',lines)
                    self.assertEqual('zen-login' in lines,prepare)
                    if prepare: self.assertLess(lines.index('zen-login'),lines.index('restore'))
                    if fail: self.assertFalse(receipt.exists())
                    else: self.assertEqual(receipt.read_text(),build+'\n')
                finally: stop(process)

    def test_later_maintenance_does_not_restore_apps_and_uses_the_build_revision(self):
        from tools.test import private_session, stop
        with tempfile.TemporaryDirectory() as folder, private_session() as env:
            root=Path(folder)
            session,events,revision=self.stage_revision_session(root,env)
            seen=Path(env['XDG_CACHE_HOME'])/'monet/apps-seen'
            signatures=[]
            for build in ['build-a','build-b']:
                revision.write_text(build+'\n'); events.unlink(missing_ok=True)
                process=subprocess.Popen(['bash',str(session),'--later'],env=env,start_new_session=True,
                                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    self.assertEqual(process.wait(timeout=5),0)
                    signatures.append(seen.read_text())
                    self.assertEqual(events.read_text().splitlines(),['zen-later'])
                finally: stop(process)
            self.assertNotEqual(*signatures)

    def test_guest_login_does_not_prepare_personal_profiles_or_restore_apps(self):
        from tools.test import private_session, stop
        with tempfile.TemporaryDirectory() as folder, private_session() as env:
            root = Path(folder)
            session, events, revision = self.stage_revision_session(root, env)
            identity = root / 'helpers/id'
            identity.write_text('#!/bin/sh\nprintf "guest\\n"\n'); identity.chmod(0o755)
            process = subprocess.Popen(['bash',str(session)],env=env,start_new_session=True,
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                self.assertEqual(process.wait(timeout=5),0)
                lines = events.read_text().splitlines() if events.exists() else []
                self.assertNotIn('restore',lines)
                self.assertNotIn('zen-login',lines)
                self.assertFalse((Path(env['XDG_CACHE_HOME'])/'monet/zen-login-revision').exists())
            finally: stop(process)

    def test_restore_starts_before_unrelated_sign_in_work_finishes(self):
        from tools.test import private_session, stop
        with tempfile.TemporaryDirectory() as folder, private_session() as env:
            root = Path(folder); helpers = root / "helpers"; helpers.mkdir()
            events = root / "events"
            stub = helpers / "stub"
            stub.write_text('''#!/usr/bin/python3
import os,sys,time
from pathlib import Path
name=Path(sys.argv[0]).name
command=sys.argv[1] if len(sys.argv)>1 else ""
def record(event):
    with open(os.environ["MONET_SESSION_EVENTS"],"a") as stream: stream.write(event+"\\n")
if name=="monet-quick" and command=="trip-apps-again": record("restore")
elif name=="monet-quick" and command=="files-place":
    record("maintenance-start"); time.sleep(.8); record("maintenance-finish")
elif name=="monet-quick" and command=="older-pc": print("no")
elif name=="monet" and command in ("version","--version"): print("monet 0.9.8-7")
''')
            stub.chmod(0o755)
            for name in ("monet", "monet-quick", "monet-files", "monet-look", "monet-light", "monet-profile", "notify-send", "systemd-run"):
                (helpers / name).symlink_to(stub)
            session = root / "monet-session"
            source = (ROOT / "linux/libexec/monet-session").read_text()
            session.write_text(source.replace("@LIBEXECDIR@", str(helpers)).replace("@BINDIR@", str(helpers)))
            env.update(PATH=str(helpers) + os.pathsep + env["PATH"], MONET_SESSION_EVENTS=str(events))
            process = subprocess.Popen(["bash", str(session)], env=env, start_new_session=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                end = time.monotonic() + 5
                while time.monotonic() < end:
                    lines = events.read_text().splitlines() if events.exists() else []
                    if "maintenance-finish" in lines and "restore" in lines: break
                    time.sleep(.02)
                self.assertIn("restore", lines)
                self.assertIn("maintenance-finish", lines)
                self.assertLess(lines.index("restore"), lines.index("maintenance-finish"))
            finally:
                stop(process)


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
                if app == 'settings':
                    self.assertEqual(phases.count('initial-data-start'), 1)
                    self.assertLess(phases.index('first-frame'), phases.index('initial-data-start'))
                    self.assertLess(phases.index('initial-page-ready'), phases.index('initial-data-start'))
                    self.assertGreater(sample['external_initial_page_ms'], 0)
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
