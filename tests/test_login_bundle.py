"""An incompatible or damaged greeter must never replace the working sign-in."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('login_bundle', ROOT/'image/login/bundle.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class LoginBundle(unittest.TestCase):
    def test_runtime_changes_stop_installation(self):
        manifest = dict(original='original', package_names=['plasma-login-manager.x86_64'], packages=['matching'])
        with patch.object(b, 'packages', return_value=['matching']) as packages, \
                patch.object(b, 'digest', return_value='original') as digest:
            b.verify(manifest)
            digest.return_value = 'changed'
            with self.assertRaisesRegex(ValueError, 'runtime changed'): b.verify(manifest)
            digest.return_value = 'original'; packages.return_value = ['different']
            with self.assertRaisesRegex(ValueError, 'runtime changed'): b.verify(manifest)
        for names in ([], None, ['--config=/tmp/injected'], ['pkg\nother']):
            with patch.object(b, 'packages') as packages:
                with self.assertRaises(ValueError): b.verify(dict(manifest, package_names=names))
                packages.assert_not_called()

    def test_link_changes_and_unresolved_symbols_are_rejected(self):
        native = '(NEEDED) Shared library: [libQt6Core.so.6]'
        with patch.object(b, 'run', side_effect=[native, native, 'resolved']): b.compatible('new')
        for changed in ('', native+'\n(NEEDED) [libUnexpected.so]', native+'\n(RUNPATH) [/work]'):
            with patch.object(b, 'run', side_effect=[changed, native]), self.assertRaises(ValueError):
                b.compatible('new')
        for linked in ('library => not found', 'undefined symbol: missing_api'):
            with patch.object(b, 'run', side_effect=[native, native, linked]), self.assertRaises(ValueError):
                b.compatible('new')

    def test_corrupt_binary_or_source_cannot_reach_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('plasma-login-greeter','source.tar.xz'): (root/name).write_bytes(b'bundle')
            (root/'runtime.json').write_text(json.dumps(dict(
                binary=b.digest(root/'plasma-login-greeter'),source=b.digest(root/'source.tar.xz'))))
            for name in ('plasma-login-greeter','source.tar.xz'):
                (root/name).write_bytes(b'broken')
                with patch.object(b,'verify'), patch.object(b,'atomic_copy') as write:
                    with self.assertRaisesRegex(ValueError,'checksum mismatch'): b.install(root)
                    write.assert_not_called()
                (root/name).write_bytes(b'bundle')

    def test_disk_full_during_copy_preserves_working_greeter(self):
        with tempfile.TemporaryDirectory() as folder:
            source,target=Path(folder)/'source',Path(folder)/'target'
            source.write_bytes(b'new');target.write_bytes(b'working')
            with patch.object(b.shutil,'copyfileobj',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): b.atomic_copy(source,target)
            self.assertEqual(target.read_bytes(),b'working')
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()),['source','target'])


if __name__=='__main__': unittest.main()
