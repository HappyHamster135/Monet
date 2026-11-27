"""Native laptop previews reject changed runtimes and remain reversible."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
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
    def test_window_shadow_preview_does_not_change_window_preferences(self):
        p = load('native_preview_window_frames', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            p.DATA = Path(tmp) / 'data'
            files = p.window_frames_plan()
            self.assertEqual({f.name for f in files}, {'decoration.svg', 'MonetBarerc', 'metadata.desktop'})
            self.assertTrue(all(f.parent == p.DATA / 'aurorae/themes/MonetBare' for f in files))
            for target, (data, mode) in files.items():
                self.assertEqual(mode, 0o644)
                self.assertEqual(data, (ROOT / 'linux/share/aurorae/themes/MonetBare' / target.name).read_bytes())

    def test_editor_preview_delivers_shared_editor_and_preserves_other_shell_files(self):
        p = load('native_preview_editor', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); p.DATA=root/'data'; p.PRIVATE=root/'private'; p.HELPERS=root/'helpers'
            system=root/'system'
            shell=system/'plasma/shells/org.kde.plasma.desktop'
            (shell/'contents/configuration').mkdir(parents=True)
            (shell/'metadata.json').write_text('{}')
            (shell/'contents/configuration/PanelConfiguration.qml').write_text('native fallback')
            (shell/'contents/configuration/Unrelated.qml').write_text('preserved')
            (system/'monet/settings-app').mkdir(parents=True)
            (system/'monet/settings-app/MonetSettings.qml').write_text('installed settings')
            (system/'applications').mkdir()
            (system/'applications/monet-settings.desktop').write_text('[Desktop Entry]\nExec=/usr/libexec/monet-settings\n')
            for name in ('monet', 'monet-matte', 'monet-solid'):
                theme=system/'plasma/desktoptheme'/name
                (theme/'widgets').mkdir(parents=True)
                (theme/'metadata.json').write_text('{}')
                (theme/'widgets/panel-background.svg').write_text('installed panel')
            # A locally adjusted theme must survive an editor-only update.
            personal=p.DATA/'plasma/desktoptheme/monet'
            (personal/'widgets').mkdir(parents=True)
            (personal/'metadata.json').write_text('{"personal":true}')
            (personal/'widgets/panel-background.svg').write_text('personal panel')
            files=p.editor_plan(system)
            config=p.DATA/'plasma/shells/org.kde.plasma.desktop/contents/configuration'
            self.assertEqual(files[config/'Unrelated.qml'][0],b'preserved')
            self.assertEqual(files[config/'KdePanelConfiguration.qml'][0],b'native fallback')
            self.assertIn(p.PRIVATE/'editor/monet/panel/NotchEditor.qml',files)
            self.assertIn(p.PRIVATE/'editor/monet/panel/ResizeGrip.qml',files)
            self.assertIn(p.PRIVATE/'editor/monet/panel/EditorWindowPlacement.qml',files)
            for name in ('EditorWindows.js','EditorHost.qml','EditorAppWindow.qml','PanelEditorWindow.qml','WidgetEditorWindow.qml','WindowControls.qml'):
                self.assertIn(p.PRIVATE/'editor/monet/panel'/name,files)
            self.assertIn(p.HELPERS/'layout-editor/monet-editor-window',files)
            self.assertEqual(files[p.PRIVATE/'editor/monet/window-buttons'][0], system/'monet/window-buttons')
            self.assertEqual(files[config.parent/'views/MonetDesktopEditMode.qml'][0],
                (ROOT/'linux/share/monet/editmode/MonetDesktopEditMode.qml').read_bytes())
            self.assertEqual(files[config.parent/'explorer/WidgetExplorer.qml'][0],
                (ROOT/'linux/share/monet/explorer/WidgetExplorer.qml').read_bytes().replace(b'@DATADIR@', str(p.PRIVATE/'editor').encode()))
            self.assertIn(b'widgetGalleryTitleDrag',files[config.parent/'explorer/MonetWidgetExplorer.qml'][0])
            self.assertEqual(files[personal/'widgets/panel-background.svg'][0], b'personal panel')
            for name in ('monet', 'monet-matte', 'monet-solid'):
                theme=Path('plasma/desktoptheme')/name
                self.assertEqual(files[p.DATA/theme/'widgets/margins-highlight.svg'][0],
                    (ROOT/'linux/share'/theme/'widgets/margins-highlight.svg').read_bytes())
            self.assertIn(p.DATA/'plasma/packages/org.kde.paneltoolbox/contents/ui/main.qml',files)
            helper=files[p.HELPERS/'layout-editor/monet-quick'][0].decode()
            self.assertIn(str(p.PRIVATE/'editor/monet/panel-notch.js'),helper)
            for name in ('MonetSettings.qml', 'SettingsUpdates.qml', 'SettingsAbout.qml',
                         'SettingsControls.qml', 'SettingsGames.qml', 'SettingsPower.qml'):
                self.assertEqual(files[p.PRIVATE/'editor/monet/settings-app'/name][0],
                                 (ROOT/'linux/share/monet/settings-app'/name).read_bytes())
            self.assertNotIn('package = notch_package()',helper)
            self.assertFalse(any(f.is_relative_to(system) for f in files))
            self.assertFalse(any(f.suffix in {'.qmlc','.jsc'} for f in files))

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

    def test_source_update_removes_stale_adjacent_bytecode_and_restores_both(self):
        p = load('native_preview_qml_cache', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp); p.STATE = root / 'state'
            source, cache = root / 'Scratchpad.qml', root / 'Scratchpad.qmlc'
            source.write_bytes(b'old editor'); cache.write_bytes(b'compiled old editor')
            # A copied package can contain stale bytecode even alongside new source.
            p.apply({source: (b'new editor', 0o644), cache: (b'compiled old editor', 0o644)})
            self.assertEqual(source.read_bytes(), b'new editor')
            self.assertFalse(cache.exists())
            receipt = next((p.STATE / 'monet/desktop-preview').glob('*/receipt.json'))
            p.restore(receipt)
            self.assertEqual(source.read_bytes(), b'old editor')
            self.assertEqual(cache.read_bytes(), b'compiled old editor')

    def test_notch_preview_uses_source_and_preserves_installed_shared_components(self):
        p = load('native_preview_notch_plan', 'install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p.DATA = root / 'data'; p.PRIVATE = root / 'private'; p.HELPERS = root / 'helpers'
            package = Path('plasma/plasmoids/org.monet.notch')
            installed = root / 'system' / package
            (installed / 'contents/ui').mkdir(parents=True)
            (installed / 'metadata.json').write_text('{}')
            (installed / 'contents/ui/Scratchpad.qmlc').write_bytes(b'old bytecode')
            (installed / 'contents/ui/VolumeMixer.qml').write_text('shared mixer')
            files = p.notch_plan(root / 'system')
            self.assertFalse(any(path.suffix in {'.qmlc', '.jsc'} for path in files))
            self.assertEqual(files[p.DATA / package / 'contents/ui/VolumeMixer.qml'][0], b'shared mixer')
            self.assertIn(b'scratchpadTabs', files[p.DATA / package / 'contents/ui/Scratchpad.qml'][0])
            self.assertIn(str(p.PRIVATE / 'notch/utilities/agent_history.py').encode(), files[p.DATA / package / 'contents/ui/AgentHistory.qml'][0])
            self.assertIn(str(p.PRIVATE / 'notch/utilities/actions.py').encode(), files[p.DATA / package / 'contents/ui/ToolDirectory.qml'][0])
            for name in ('actions.py', 'links.py'):
                target = p.PRIVATE / 'notch/utilities' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(files[target][0])
            catalog = json.loads(subprocess.check_output([sys.executable, str(p.PRIVATE / 'notch/utilities/actions.py')], text=True))
            inline = {row['key'] for row in catalog['rows'] if not row['immediate']}
            self.assertTrue({'emoji', 'record', 'plain', 'clean', 'snippets'} <= inline)
            self.assertIn(p.PRIVATE / 'notch/utilities/agent_pricing.py', files)
            self.assertIn(p.DATA / 'applications/monet-notch-settings.desktop', files)
            self.assertIn(p.PRIVATE / 'notch/utilities/favorites_wheel.py', files)
            radial = files[p.DATA / 'applications/org.monet.NotchRadial.desktop'][0]
            self.assertIn((str(p.HELPERS / 'monet-notch-utilities') + ' radial').encode(), radial)
            self.assertIn(b'X-KDE-Shortcuts=Ctrl+Shift+Space', radial)
            self.assertIn(str(p.HELPERS / 'monet-notch-utilities').encode(), files[p.DATA / 'applications/monet-notch-settings.desktop'][0])
            self.assertIn(str(root / 'system/monet/utilities').encode(), files[p.PRIVATE / 'notch/utilities/window.py'][0])
            self.assertIn(str(p.HELPERS / 'monet-notch-layout').encode(), files[p.PRIVATE / 'notch/utilities/notch_settings.py'][0])
            self.assertIn(str(p.PRIVATE / 'notch/panel-notch.js').encode(), files[p.HELPERS / 'monet-notch-layout'][0])
            self.assertIn(p.PRIVATE / 'notch/panel/NotchEditor.qml', files)
            self.assertTrue({'text-tools', 'color-tools', 'display', 'sound', 'screenshot', 'color', 'ocr', 'watch'} <= inline)
            self.assertFalse({'files','homebrew','store'} & {row['key'] for row in catalog['rows']})
            for module in ('tool_pages.py','compact_capture.py','compact_system.py','inline_dialogs.py','notch_settings_style.py'):
                self.assertIn(p.PRIVATE / 'notch/utilities' / module,files)
            self.assertFalse(any(path.is_relative_to(root / 'system') for path in files))

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
            gallery = p.DATA / 'plasma/shells/org.kde.plasma.desktop/contents/explorer/MonetWidgetExplorer.qml'
            self.assertIn(str(p.BIN / 'monet-files').encode(), files[gallery][0])
            self.assertNotIn(b'@BINDIR@', files[gallery][0])
