"""A Files executable and private library must match each other and the image."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('files_bundle',Path(__file__).resolve().parents[1]/'image/files-recovery/bundle.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


class FilesBundle(unittest.TestCase):
    def setUp(self):
        self.manifest={'schema':1,'targets':[
            {'path':'/usr/bin/dolphin','original_sha256':'exe'},
            {'path':'/usr/lib64/libdolphinprivate.so.26.08.1','original_sha256':'lib'}],
            'package_names':['dolphin.x86_64','dolphin-libs.x86_64'],
            'packages':['dolphin-26.08.1-2.fc44.x86_64','dolphin-libs-26.08.1-2.fc44.x86_64']}

    def test_both_originals_and_transitive_runtime_must_match(self):
        with patch.object(b,'packages',return_value=self.manifest['packages']) as packages, \
                patch.object(b,'digest',side_effect=['exe','lib']) as digest:
            b.verify(self.manifest)
            for hashes in (['changed','lib'],['exe','changed']):
                digest.side_effect=hashes
                with self.assertRaisesRegex(ValueError,'binary changed'): b.verify(self.manifest)
            packages.return_value=['upgraded-runtime']
            with self.assertRaisesRegex(ValueError,'runtime changed'): b.verify(self.manifest)

    def test_invalid_destination_or_package_never_reaches_files(self):
        for target in (None,[],[None,{}],[{'path':'/etc/passwd'},{}],
                       [{'path':'/usr/bin/dolphin'},{'path':'/usr/lib64/../etc/secret'}]):
            with self.subTest(target=target),patch.object(b,'digest') as digest:
                with self.assertRaises(ValueError): b.verify(dict(self.manifest,targets=target))
                digest.assert_not_called()
        for names in ([],['--config=/tmp/malicious'],['a\nb'],['valid']*513):
            with self.subTest(names=str(names)[:80]),patch.object(b,'packages') as packages:
                with self.assertRaises(ValueError): b.verify(dict(self.manifest,package_names=names))
                packages.assert_not_called()

    def test_features_loader_paths_and_native_exports_are_preserved(self):
        dynamic='(NEEDED) Shared library: [libQt6Core.so.6]\n(SONAME) [libdolphinprivate.so.26.08.1]'
        symbols='view_api T 100 10\nview_vtable V 200 10\nview_staticMetaObject D 300 10'
        with patch.object(b,'run',side_effect=[dynamic,dynamic,symbols,symbols.replace('vtable V','vtable D')+'\nnew_api T 400 10']):
            b.compatible('old.so','new.so')
        for output in ([dynamic,'(NEEDED) [libOther.so]'],[dynamic,dynamic+'\n(RUNPATH) [/work]'],
                       [dynamic,dynamic,symbols,symbols.replace('view_staticMetaObject D 300 10','')],
                       [dynamic,dynamic,symbols,'view_api T 100 10'],[dynamic,dynamic,'','']):
            with self.subTest(output=output),patch.object(b,'run',side_effect=output):
                with self.assertRaises(ValueError): b.compatible('old.so','new.so')
        with patch.object(b,'run',side_effect=[dynamic,dynamic]): b.compatible('/usr/bin/dolphin','new')
        wayland = dynamic+'\n(NEEDED) [libwayland-client.so.0]'
        with patch.object(b,'run',side_effect=[dynamic,wayland]): b.compatible('/usr/bin/dolphin','new')
        with patch.object(b,'run',side_effect=[dynamic,wayland]):
            with self.assertRaises(ValueError): b.compatible('old.so','new.so')

    def test_all_bundle_guards_precede_either_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            names=['dolphin','libdolphinprivate.so.26.08.1','source.tar.xz']
            for name in names: (folder/name).write_bytes(b'original bundle')
            manifest=copy.deepcopy(self.manifest)
            manifest['files']={name:b.digest(folder/name) for name in names}
            (folder/'runtime.json').write_text(json.dumps(manifest))
            for name in names:
                (folder/name).write_bytes(b'corrupt')
                with patch.object(b,'verify'),patch.object(b,'atomic_copy') as write:
                    with self.assertRaisesRegex(ValueError,'Damaged Files'): b.install(folder)
                    write.assert_not_called()
                (folder/name).write_bytes(b'original bundle')
            for missing in (False,True):
                with patch.object(b,'verify'),patch.object(b,'atomic_copy') as write, \
                        patch.object(b,'compatible',side_effect=None if missing else [None,ValueError('ABI differs')]), \
                        patch.object(b,'run',return_value='library => not found' if missing else 'complete'):
                    with self.assertRaises(ValueError): b.install(folder)
                    write.assert_not_called()

    def test_failed_copy_preserves_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp:
            source,target=Path(temp)/'source',Path(temp)/'target'
            source.write_bytes(b'new'); target.write_bytes(b'original')
            with patch.object(b.shutil,'copyfileobj',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): b.atomic_copy(source,target,0o755)
            self.assertEqual(target.read_bytes(),b'original')
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()),['source','target'])
