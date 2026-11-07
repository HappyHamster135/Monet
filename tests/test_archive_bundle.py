"""Native archive errors must not introduce an unguarded executable replacement."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('archive_bundle', Path(__file__).resolve().parents[1] / 'image/archive-recovery/bundle.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


class ArchiveBundle(unittest.TestCase):
    def setUp(self):
        self.originals = {'/usr/bin/ark': 'a'*64, '/usr/lib64/libkerfuffle.so.26.08.2': 'b'*64,
                          '/usr/lib64/qt6/plugins/kerfuffle/kerfuffle_libzip.so': 'c'*64}
        self.manifest = dict(schema=1, originals=self.originals, package_names=['ark.x86_64'], packages=['ark-26.08.2-1.fc45.x86_64'])

    def test_original_plugins_and_runtime_packages_must_match(self):
        with patch.object(b, 'packages', return_value=self.manifest['packages']) as packages, \
                patch.object(b, 'digest', side_effect=self.originals.get) as digest:
            b.verify(self.manifest)
            digest.side_effect = lambda path: 'd'*64 if path.endswith('libzip.so') else self.originals[path]
            with self.assertRaisesRegex(ValueError, 'binaries changed'): b.verify(self.manifest)
            packages.return_value = ['changed-runtime']
            with self.assertRaisesRegex(ValueError, 'runtime changed'): b.verify(self.manifest)

    def test_manifest_paths_and_package_arguments_are_validated_before_access(self):
        with patch.object(b, 'digest') as digest, patch.object(b, 'packages') as packages:
            for originals in (None, {}, dict(self.originals, **{'/etc/passwd': 'a'*64}),
                              dict(self.originals, **{'/usr/lib64/../etc/passwd': 'a'*64})):
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, originals=originals))
            for names in ([], ['--config=/tmp/injected'], ['a\nb']):
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, package_names=names))
            digest.assert_not_called(); packages.assert_not_called()

    def test_replacement_keeps_native_features_and_cannot_load_build_libraries(self):
        original = '(NEEDED) Shared library: [libQt6Core.so.6]\n(NEEDED) Shared library: [libkerfuffle.so.26]'
        with patch.object(b, 'run', side_effect=[original, original, 'complete']): b.compatible('replacement')
        for changed in ('(NEEDED) [libQt6Core.so.6]', original + '\n(RUNPATH) [/work]'):
            with patch.object(b, 'run', side_effect=[original, changed]):
                with self.assertRaises(ValueError): b.compatible('replacement')
        with patch.object(b, 'run', side_effect=[original, original, 'library => not found']):
            with self.assertRaises(ValueError): b.compatible('replacement')

    def test_corrupt_bundle_is_rejected_before_any_install_and_source_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ('ark', 'source.tar.xz', 'README.md'): (folder / name).write_bytes(b'fixture')
            manifest = dict(self.manifest, files={n: b.digest(folder/n) for n in ('ark', 'source.tar.xz')})
            (folder / 'runtime.json').write_text(json.dumps(manifest))
            (folder / 'source.tar.xz').write_bytes(b'damaged')
            with patch.object(b, 'verify'), patch.object(b, 'atomic_copy') as copy:
                with self.assertRaisesRegex(ValueError, 'Damaged'): b.install(folder)
                copy.assert_not_called()
            (folder / 'source.tar.xz').write_bytes(b'fixture')
            with patch.object(b, 'verify'), patch.object(b, 'compatible'), patch.object(b.Path, 'mkdir'), patch.object(b, 'atomic_copy') as copy:
                b.install(folder)
                self.assertEqual([c.args[1].name for c in copy.call_args_list], ['runtime.json', 'source.tar.xz', 'README.md', 'ark'])
                self.assertEqual(copy.call_args.args[1], Path('/usr/bin/ark'))

    def test_failed_copy_keeps_original_and_cleans_temporary_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp)/'source', Path(temp)/'target'
            source.write_bytes(b'new'); target.write_bytes(b'original')
            with patch.object(b.shutil, 'copyfileobj', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): b.atomic_copy(source, target, 0o755)
            self.assertEqual(target.read_bytes(), b'original')
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ['source', 'target'])

    def test_rpm_plugin_and_query_runtime_are_required_in_new_bundles(self):
        originals = dict(self.originals, **{'/usr/bin/rpm': 'd'*64,
            '/usr/lib64/qt6/plugins/kerfuffle/'+b.RPM_PLUGIN: 'e'*64})
        manifest = dict(self.manifest, schema=2, originals=originals)
        with patch.object(b, 'packages', return_value=manifest['packages']), patch.object(b, 'digest', side_effect=originals.get):
            b.verify(manifest)
            self.assertEqual(set(b.payload_names(manifest)), {'ark', b.RPM_PLUGIN, 'source.tar.xz'})
            for missing in ('/usr/bin/rpm', '/usr/lib64/qt6/plugins/kerfuffle/'+b.RPM_PLUGIN):
                incomplete = dict(originals); incomplete.pop(missing)
                with self.assertRaises(ValueError): b.verify(dict(manifest, originals=incomplete))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'runtime.json').write_text(json.dumps(dict(manifest, files={'ark':'a'*64,'source.tar.xz':'b'*64})))
            with patch.object(b, 'verify'), patch.object(b, 'atomic_copy') as copy:
                with self.assertRaisesRegex(ValueError, 'Damaged'): b.install(folder)
                copy.assert_not_called()
