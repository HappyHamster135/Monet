"""Reject incompatible or damaged native launcher modules before installing them."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launcher_bundle', Path(__file__).resolve().parents[1] / 'image/launcher/bundle.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


class LauncherBundle(unittest.TestCase):
    def setUp(self):
        self.originals = {str((Path('/usr/lib64') / name).resolve()): 'a' * 64 for name in b.LIBRARIES}
        self.manifest = dict(schema=1, path='/usr/lib64/qt6/qml/org/monet/launcher', originals=self.originals,
                             package_names=['qt6-qtbase.x86_64'], packages=['qt6-qtbase-6.11.2-3.fc45.x86_64'])
        self.directory = patch.object(b, 'libdir', return_value=Path('/usr/lib64')); self.directory.start()
        self.addCleanup(self.directory.stop)

    def test_runtime_identity_and_library_content_must_match(self):
        with patch.object(b, 'packages', return_value=self.manifest['packages']) as packages, \
                patch.object(b, 'digest', return_value='a'*64) as digest:
            b.verify(self.manifest)
            packages.return_value = ['changed']
            with self.assertRaisesRegex(ValueError, 'runtime changed'): b.verify(self.manifest)
            packages.return_value = self.manifest['packages']; digest.return_value = 'b'*64
            with self.assertRaisesRegex(ValueError, 'runtime changed'): b.verify(self.manifest)

    def test_paths_and_package_arguments_are_checked_before_access(self):
        with patch.object(b, 'digest') as digest, patch.object(b, 'packages') as packages:
            for path in ('/tmp/module', '/usr/lib64/qt6/qml/../launcher', None):
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, path=path))
            for originals in (None, {}, dict(self.originals, **{'/etc/passwd': 'a'*64})):
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, originals=originals))
            for names in ([], ['--config=/tmp/injected'], ['a\nb']):
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, package_names=names))
            packages.assert_not_called(); digest.assert_not_called()

    def test_build_paths_unresolved_symbols_and_uncaptured_dependencies_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); (folder / 'qmldir').write_text('module org.monet.launcher\nplugin monetlauncherplugin\n')
            dynamic = '\n'.join('(NEEDED) [' + name + ']' for name in b.LIBRARIES)
            with patch.object(b, 'linked_paths', return_value={'/usr/lib64/a.so'}), \
                    patch.object(b, 'owners', return_value={'qt6-qtbase.x86_64'}), \
                    patch.object(b, 'run', side_effect=[dynamic, 'complete']):
                b.compatible(folder, self.manifest)
            for changed in (dynamic + '\n(RUNPATH) [/tmp/build]', '(NEEDED) [libQt6Core.so.6]'):
                with patch.object(b, 'run', return_value=changed):
                    with self.assertRaises(ValueError): b.compatible(folder, self.manifest)
            with patch.object(b, 'run', side_effect=[dynamic, 'undefined symbol: required']):
                with self.assertRaisesRegex(ValueError, 'unresolved'): b.compatible(folder, self.manifest)
            with patch.object(b, 'run', side_effect=[dynamic, 'complete']), \
                    patch.object(b, 'linked_paths', return_value={'/usr/lib64/a.so'}), \
                    patch.object(b, 'owners', return_value={'unexpected-devel-runtime.x86_64'}):
                with self.assertRaisesRegex(ValueError, 'uncaptured'): b.compatible(folder, self.manifest)

    def test_corrupt_source_or_metadata_prevents_all_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in b.FILES: (folder / name).write_bytes(b'fixture')
            manifest = dict(self.manifest, files={n: b.digest(folder/n) for n in b.FILES})
            (folder / 'runtime.json').write_text(json.dumps(manifest))
            for name in ('qmldir', 'source.tar.xz', 'monet-launcher.notifyrc'):
                (folder / name).write_bytes(b'broken')
                with patch.object(b, 'verify'), patch.object(b, 'atomic_copy') as copy:
                    with self.assertRaisesRegex(ValueError, 'Damaged'): b.install(folder)
                    copy.assert_not_called()
                (folder / name).write_bytes(b'fixture')
            with patch.object(b, 'verify'), patch.object(b, 'compatible'), patch.object(b.Path, 'mkdir'), \
                    patch.object(b, 'atomic_copy') as copy:
                b.install(folder)
                self.assertEqual([c.args[1].name for c in copy.call_args_list],
                                 ['runtime.json', 'source.tar.xz', 'README.md', 'monet-launcher.notifyrc', b.PLUGIN, 'qmldir'])

    def test_failed_write_keeps_installed_file_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp)/'source', Path(temp)/'target'
            source.write_bytes(b'new'); target.write_bytes(b'old')
            with patch.object(b.shutil, 'copyfileobj', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): b.atomic_copy(source, target, 0o755)
            self.assertEqual(target.read_bytes(), b'old')
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ['source', 'target'])
