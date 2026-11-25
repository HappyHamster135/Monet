"""Exercise shipped QML bytecode with the actual Qt loader and isolated caches."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_settings_feedback import QT

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qml_precompile', ROOT / 'image/precompile-qml.py')
precompile = importlib.util.module_from_spec(spec); spec.loader.exec_module(precompile)


@unittest.skipUnless(QT, 'requires native Qt QML')
class QmlPrecompile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='monet-qml-precompile-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.share = self.root / 'share'
        self.source = self.share / 'monet/Probe.qml'
        self.source.parent.mkdir(parents=True)
        self.compiler = Path(os.environ.get('MONET_TEST_QMLCACHEGEN') or
                             shutil.which('monet-test-qmlcachegen') or
                             '/usr/lib64/qt6/libexec/qmlcachegen')
        self.assertTrue(self.compiler.is_file(), 'matching native QML compiler is required')

    def write(self, value):
        self.source.write_text('import QtQml\nQtObject { property string value: ' + json.dumps(value) + ' }\n')
        os.utime(self.source, ns=(0, 0))

    def read(self):
        # A fresh process prevents the in-memory component cache hiding a failure.
        code = '''import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
app=QGuiApplication([])
app.setApplicationName("monet-bytecode-test")
engine=QQmlApplicationEngine()
engine.load(QUrl.fromLocalFile(sys.argv[1]))
assert engine.rootObjects(), "QML failed to load"
print(engine.rootObjects()[0].property("value"))
'''
        env = dict(os.environ, XDG_CACHE_HOME=str(self.root / 'cache'),
                   QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        result = subprocess.run([sys.executable, '-c', code, str(self.source)], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_retained_panel_url_reads_the_updated_editor(self):
        panel = self.share / precompile.PANEL_CONFIG
        alias = panel / 'monet-editor/previous/MonetPanelConfiguration.qml'
        alias.parent.mkdir(parents=True)
        alias.symlink_to('../../MonetPanelConfiguration.qml')
        self.source = panel / 'MonetPanelConfiguration.qml'
        self.write('old editor')
        precompile.compile_sources(self.share, self.compiler)
        cache = alias.with_suffix('.qmlc')
        cache.unlink()
        shutil.copy(self.source.with_suffix('.qmlc'), cache)
        self.write('new editor')
        precompile.compile_sources(self.share, self.compiler)
        self.assertEqual(cache.readlink(), Path('../../MonetPanelConfiguration.qmlc'))
        self.source = alias
        self.assertEqual(self.read(), 'new editor')

    def test_new_image_cache_overrides_a_previous_profile_cache(self):
        self.write('old image')
        os.utime(self.source, ns=(1_000_000_000, 1_000_000_000))
        self.assertEqual(self.read(), 'old image')
        self.assertTrue(list((self.root / 'cache').rglob('*.qmlc')))
        self.write('new image')
        self.assertEqual(precompile.compile_sources(self.share, self.compiler), 1)
        self.assertEqual(self.read(), 'new image')
        self.assertEqual(self.source.stat().st_mtime_ns, 0)

    def test_extra_source_outside_the_share_tree_is_cached(self):
        self.write('main')
        extra = self.root / 'qml' / 'MonetResultsView.qml'
        extra.parent.mkdir()
        extra.write_text('import QtQml\nQtObject {}\n')
        self.assertEqual(precompile.compile_sources(self.share, self.compiler, [extra]), 2)
        self.assertTrue(Path(str(extra) + 'c').is_file())

    def test_damaged_bytecode_falls_back_to_source(self):
        self.write('cached')
        precompile.compile_sources(self.share, self.compiler)
        self.assertEqual(self.read(), 'cached')
        self.write('changed source')
        Path(str(self.source) + 'c').write_bytes(b'bad cache')
        self.assertEqual(self.read(), 'changed source')

    def test_imported_qt_scripts_are_cached_without_compiling_node_dependencies(self):
        script = self.source.parent / 'logic/Value.js'
        script.parent.mkdir()
        script.write_text('.pragma library\nvar current = "Qt script"\n')
        self.source.write_text('import QtQml\nimport "logic/Value.js" as Logic\n'
                               'QtObject { property string value: Logic.current }\n')
        node = self.source.parent / 'app-integration/electron/node_modules/Node.js'
        node.parent.mkdir(parents=True)
        node.write_text('await import("node:fs"); // Not a Qt script\n')
        self.assertEqual(precompile.compile_sources(self.share, self.compiler), 2)
        self.assertTrue(Path(str(script) + 'c').is_file())
        self.assertFalse(Path(str(node) + 'c').exists())
        self.assertEqual(self.read(), 'Qt script')
        self.assertFalse(list(self.share.rglob('*.aotstats')))

    def test_compile_failure_stops_the_build_and_cleans_temporary_output(self):
        self.source.write_text('invalid QML !!!')
        with self.assertRaises(subprocess.CalledProcessError):
            precompile.compile_sources(self.share, self.compiler)
        self.assertFalse(list(self.source.parent.glob('*.tmp.qmlc')))
        self.assertFalse(Path(str(self.source) + 'c').exists())
