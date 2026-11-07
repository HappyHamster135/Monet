"""Native laptop previews reject changed runtimes and remain reversible."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class NativePreview(unittest.TestCase):
    def setUp(self):
        self.runtime = load('native_preview_runtime_test', 'native-preview-runtime.py')
        self.plan = load('native_preview_plan_test', 'desktop-preview-native.py')

    def fixture(self, root):
        library, payload = root / 'library', root / 'plugin'
        library.write_bytes(b'original runtime'); payload.write_bytes(b'native plugin')
        return {'runtime': {str(library): self.runtime.identity(library)},
                'files': {str(payload): hashlib.sha256(payload.read_bytes()).hexdigest()},
                'qml': str(root / 'qml'), 'executable': str(payload)}, library, payload

    def test_changed_library_and_plugin_both_disable_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            component, library, payload = self.fixture(Path(tmp))
            self.assertTrue(self.runtime.valid(component))
            original = library.stat()
            library.write_bytes(b'altered! runtime')
            os.utime(library, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertFalse(self.runtime.valid(component))
            component['runtime'][str(library)] = self.runtime.identity(library)
            self.assertTrue(self.runtime.valid(component))
            payload.write_bytes(b'broken plugin')
            self.assertFalse(self.runtime.valid(component))
            self.assertFalse(self.runtime.valid({'runtime': {}, 'files': {}}))

    def test_invalid_inherited_module_paths_are_removed_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); good, _, _ = self.fixture(root)
            bad = dict(good, files={str(root / 'missing'): 'a' * 64}, qml=str(root / 'bad-qml'), plugins=str(root / 'bad-plugins'))
            manifest = {'schema': 1, 'components': {'good': good, 'bad': bad}}
            inherited = {key: bad['qml'] + ':/custom' for key in ('QML_IMPORT_PATH', 'QML2_IMPORT_PATH')}
            inherited['QT_PLUGIN_PATH'] = bad['plugins'] + ':/custom-plugins'
            with patch.object(self.runtime, 'read', return_value=manifest), patch.dict(os.environ, inherited, clear=True):
                self.runtime.prepare()
                for name in ('QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
                    self.assertEqual(os.environ[name], good['qml'] + ':/custom')
                self.assertEqual(os.environ['QT_PLUGIN_PATH'], '/custom-plugins')
            self.runtime._prepared = False
            with patch.object(self.runtime, 'read', return_value={'schema': 1, 'components': {'bad': bad}}), \
                    patch.dict(os.environ, {'QML_IMPORT_PATH': bad['qml'], 'QT_PLUGIN_PATH': bad['plugins']}, clear=True):
                self.runtime.prepare()
                self.assertNotIn('QML_IMPORT_PATH', os.environ)
                self.assertNotIn('QT_PLUGIN_PATH', os.environ)

    def test_changed_runtime_launches_system_app_with_original_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            component, library, _ = self.fixture(Path(tmp)); library.unlink()
            component['libraries'] = str(Path(tmp) / 'private-libraries')
            data = {'schema': 1, 'components': {'dolphin': component}}
            with patch.object(self.runtime, 'read', return_value=data), \
                    patch.dict(os.environ, LD_LIBRARY_PATH=component['libraries'] + ':/custom-libraries'), \
                    patch.object(self.runtime.os, 'execv', side_effect=SystemExit) as execute:
                with self.assertRaises(SystemExit): self.runtime.launch('dolphin', '/usr/bin/dolphin', ['--new-window', '/tmp/a b'])
                execute.assert_called_once_with('/usr/bin/dolphin', ['dolphin', '--new-window', '/tmp/a b'])
                self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/custom-libraries')

    def test_corrupt_manifest_has_no_preview_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native.json'
            with patch.object(self.runtime, 'MANIFEST', path):
                for text in ('not json', '[]', '{}', '{"schema":1,"components":[]}'):
                    path.write_text(text)
                    self.assertEqual(self.runtime.read()['components'], {})

    def test_archive_plugin_is_scoped_to_guarded_archives_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); component, _, payload = self.fixture(root)
            component.pop('qml')
            component.update(plugins=str(root/'ark-plugins'), executable=str(payload))
            data = {'schema':1, 'components':{'ark':component}}
            with patch.object(self.runtime, 'read', return_value=data), patch.dict(os.environ, {}, clear=True):
                self.runtime.prepare(include_dock=True)
                self.assertNotIn('QT_PLUGIN_PATH', os.environ)
                with patch.object(self.runtime.os, 'execv', side_effect=SystemExit):
                    with self.assertRaises(SystemExit): self.runtime.launch('ark', '/usr/bin/ark', [])
                self.assertEqual(os.environ['QT_PLUGIN_PATH'], component['plugins'])

    def test_app_preparation_checks_only_modules_it_can_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            component, _, _ = self.fixture(Path(tmp))
            dock = dict(component, qml='', plugins='/private/dock')
            executable = dict(component, qml='', executable='/private/dolphin')
            data = {'schema': 1, 'components': {'qml': component, 'dock': dock, 'dolphin': executable}}
            with patch.object(self.runtime, 'read', return_value=data), patch.object(self.runtime, 'valid', return_value=True) as verify, \
                    patch.dict(os.environ, {}, clear=True):
                self.runtime.prepare()
                self.assertEqual(verify.call_args_list, [unittest.mock.call(component)])
                self.assertNotIn('QT_PLUGIN_PATH', os.environ)
                verify.reset_mock(); self.runtime.prepare(include_dock=True)
                self.assertEqual(verify.call_args_list, [unittest.mock.call(component), unittest.mock.call(dock)])
                self.assertEqual(os.environ['QT_PLUGIN_PATH'], '/private/dock')

    def test_bundle_validation_does_not_accept_mutated_corresponding_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); payload = root / 'source.tar.xz'; payload.write_bytes(b'source')
            manifest = {'files': {'source.tar.xz': self.plan.digest(payload)}}
            (root / 'runtime.json').write_text(json.dumps(manifest))
            class Bundle:
                def verify(self, value): self.manifest = value
            bundle = Bundle()
            self.plan.checked(root, bundle, ['source.tar.xz'])
            payload.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Damaged'): self.plan.checked(root, bundle, ['source.tar.xz'])
            with self.assertRaisesRegex(ValueError, 'Incomplete'): self.plan.checked(root, bundle, ['source.tar.xz', 'plugin'])

    def test_bootstrap_preserves_future_imports_and_runs_once_without_helpers(self):
        source = b'#!/usr/bin/python3\n"""Description."""\nfrom __future__ import annotations\nvalue = 3\n'
        result = self.plan.bootstrap(source)
        compile(result, '<preview>', 'exec')
        self.assertLess(result.index(b'from __future__'), result.index(b'import monet_native_preview'))
        self.assertLess(result.index(b'monet_native_preview.prepare()'), result.index(b'value = 3'))

    def test_installation_restore_preserves_new_personal_edits(self):
        p = load('native_preview_install_test', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); p.STATE = root / 'state'
            p.DATA = root
            executable, config = root / 'executable', root / 'config'
            executable.write_text('old app'); config.write_text('personal choice')
            p.apply({executable: (b'new app', 0o755), config: (b'preview config', 0o600)})
            receipt = next((p.STATE / 'monet/desktop-preview').glob('*/receipt.json'))
            config.write_text('later personal choice')
            p.restore(receipt)
            self.assertEqual(executable.read_text(), 'old app')
            self.assertEqual(config.read_text(), 'later personal choice')

    def test_service_menu_mode_only_update_is_installed_and_reversible(self):
        p = load('native_preview_mode_test', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); p.STATE = root / 'state'; p.DATA = root
            target = root / 'menu.desktop'; target.write_bytes(b'unchanged entry'); target.chmod(0o644)
            p.apply({target: (target.read_bytes(), 0o755)})
            receipt = next((p.STATE / 'monet/desktop-preview').glob('*/receipt.json'))
            self.assertEqual(len(json.loads(receipt.read_text())['files']), 1)
            self.assertEqual(target.stat().st_mode & 0o777, 0o755)
            changes, kept = p.retirement_plan()
            self.assertIn(target, changes)
            self.assertEqual(changes[target][1].stat().st_mode & 0o777, 0o644)
            p.restore(receipt)
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertEqual(target.read_bytes(), b'unchanged entry')

    def test_restore_keeps_later_personal_permission_edits(self):
        p = load('native_preview_mode_conflict_test', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); p.STATE = root / 'state'; p.DATA = root
            target = root / 'menu.desktop'; target.write_bytes(b'unchanged entry'); target.chmod(0o644)
            p.apply({target: (target.read_bytes(), 0o755)})
            receipt = next((p.STATE / 'monet/desktop-preview').glob('*/receipt.json'))
            target.chmod(0o700)
            changes, kept = p.retirement_plan()
            self.assertNotIn(target, changes); self.assertIn(str(target), map(str, kept))
            p.restore(receipt)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_retirement_unwinds_legacy_binary_but_preserves_seeded_preferences(self):
        p = load('native_preview_legacy_test', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p.STATE = root / 'state'; p.BIN = root / 'bin'; p.CONFIG = root / 'config'
            p.DATA = root / 'data'; p.HELPERS = root / 'helpers'
            binary = p.BIN / 'dolphin'; binary.parent.mkdir(); binary.write_text('latest preview')
            choice = p.CONFIG / 'user-dirs.dirs'; choice.parent.mkdir(); choice.write_text('chosen Desktop')
            legacy = p.STATE / 'monet/local-test-install/20261105/receipt.json'; legacy.parent.mkdir(parents=True)
            (legacy.parent / '0').write_text('system wrapper')
            legacy.write_text(json.dumps({'files': [
                {'path': str(binary), 'before': p.digest(legacy.parent / '0'), 'after': hashlib.sha256(b'first preview').hexdigest(), 'backup': '0'},
                {'path': str(choice), 'before': None, 'after': p.digest(choice), 'backup': 'config-0'}]}))
            latest = p.STATE / 'monet/desktop-preview/20261106/receipt.json'; latest.parent.mkdir(parents=True)
            (latest.parent / '0').write_text('first preview')
            latest.write_text(json.dumps({'files': [{'path': str(binary), 'before': p.digest(latest.parent / '0'), 'after': p.digest(binary), 'backup': '0'}]}))
            changes, kept = p.retirement_plan()
            self.assertEqual(set(changes), {binary})
            self.assertEqual(changes[binary][1].read_text(), 'system wrapper')
            self.assertEqual(choice.read_text(), 'chosen Desktop')
            self.assertNotIn(choice, p.recorded_previews())

    def test_private_games_relative_import_has_its_shared_widgets_directory(self):
        p = load('native_preview_shared_import', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p.DATA=root/'data'; p.PRIVATE=root/'private'; p.CONFIG=root/'config'
            p.STATE=root/'state'; p.HELPERS=root/'helpers'; p.BIN=root/'bin'
            files=p.plan()
            self.assertEqual(files[p.PRIVATE/'monet/widgets'][0],p.DATA/'monet/widgets')
            self.assertIn(p.DATA/'monet/widgets/ScrollInput.qml',files)
