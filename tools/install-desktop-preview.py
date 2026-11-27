#!/usr/bin/env python3
"""Install the tested desktop UI for this account, without changing the OS image.

Default: show the plan. --apply: back up and install. --restore RECEIPT: undo
unchanged installed files, preserving files edited since installation.
--retire: plan removal of all recorded previews before an OS upgrade;
--retire --apply: back up and retire them, preserving later personal edits.
"""
import argparse
import datetime
import hashlib
import json
import os
import stat
from pathlib import Path
import shutil
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
HELPERS = Path.home() / '.local/libexec/monet-desktop-preview'
PRIVATE = DATA / 'monet-desktop-preview'
BIN = Path.home() / '.local/bin'
LOCAL = {'monet-game-keys', 'monet-quick', 'monet-settings', 'monet-games', 'monet-store', 'monet-store-jobs', 'monet-files-tools', 'monet-system-info', 'monet-graphics-use', 'monet-weather', 'monet-light', 'monet-daylight'}
LOCAL |= {'monet-resume', 'monet-files-session', 'monet-browser-session', 'monet-editor-session', 'monet-pdf-session'}
LOCAL |= {'monet-session', 'monet-passwords', 'monet-passwords-browser', 'monet-keep-awake', 'monet-brightness'}
LOCAL |= {'monet-look', 'monet-fresh', 'monet-region', 'monet-files', 'monet-file-jobs'}


def digest(path):
    if path.is_symlink():
        return 'link:' + os.readlink(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def render(source, *, private_data=False, local_helpers=False, bindir='/usr/bin'):
    text = source.read_text()
    # Keep privileged and image-bound helpers at their installed system paths.
    # Route only these user-facing helpers to the preview, including self calls.
    if not local_helpers:
        for name in LOCAL:
            text = text.replace('{LIBEXECDIR}/' + name, str(HELPERS / name))
            text = text.replace('"$LIBEXECDIR/' + name + '"', '"' + str(HELPERS / name) + '"')
    preview_files = str(BIN / 'monet-files')
    text = text.replace('/usr/bin/monet-files', preview_files)
    text = text.replace('"$BINDIR/monet-files"', '"' + preview_files + '"')
    if source.name == 'monet-files':
        text = text.replace('@DATADIR@', str(DATA))
    return (text.replace('@BINDIR@', str(bindir))
            .replace('@DATADIR@', str(PRIVATE) if private_data else '/usr/share')
            .replace('@LIBEXECDIR@', str(HELPERS) if local_helpers else '/usr/libexec')).encode()


def cli_prefix(requested=None):
    """Keep a tested CLI preview attached to every desktop entry point."""
    marker = STATE / 'monet/desktop-preview/cli-prefix'
    prefix = requested or (Path(marker.read_text().strip()) if marker.exists() else None)
    if prefix is None:
        return None
    prefix = Path(prefix).resolve(strict=True)
    required = [prefix / 'bin/monet', prefix / 'libexec/monet-leave', prefix / 'libexec/monet-quick',
                prefix / 'libexec/monet-prepare-windows']
    siblings = (prefix / 'libexec/monet-quick').resolve(strict=True).parent
    required += [siblings / name for name in ('monet-resume', 'monet-files-session', 'monet-browser-session',
                                             'monet-editor-session', 'monet-pdf-session')]
    for path in required:
        path = path.resolve(strict=True)
        for part in (path, *path.parents):
            info = part.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError(f'CLI preview must be root-owned and not writable by other users: {part}')
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f'CLI preview helper is not executable: {path}')
    return prefix


def notch_plan(system_share=Path('/usr/share')):
    """Update just the island, keeping installed native helpers and preferences."""
    files = {}
    package = Path('plasma/plasmoids/org.monet.notch')
    installed = system_share / package
    if not (installed / 'metadata.json').is_file():
        raise ValueError('Install Monet before applying a notch-only preview')
    destination = DATA / package
    override = PRIVATE / 'notch/utilities'
    # A package is resolved as a unit. Preserve its installed shared components,
    # but never import image-built bytecode: Qt may prefer it to edited source.
    for folder in (installed, ROOT / 'linux/share' / package):
        for source in folder.rglob('*'):
            if not source.is_file() or source.suffix in {'.qmlc', '.jsc'} or '__pycache__' in source.parts:
                continue
            data = source.read_bytes()
            if source.suffix in {'.qml', '.js'}:
                data = data.replace(b'@DATADIR@/monet/utilities/agent_history.py', str(override / 'agent_history.py').encode())
                data = data.replace(b'@DATADIR@/monet/utilities/actions.py', str(override / 'actions.py').encode())
                data = (data.replace(b'@LIBEXECDIR@', b'/usr/libexec')
                        .replace(b'@DATADIR@', str(system_share).encode()).replace(b'@BINDIR@', b'/usr/bin'))
            files[destination / source.relative_to(folder)] = (data, 0o644)
    # This shared calendar suppresses its hover previews only in island mode.
    files[destination / 'contents/ui/Month.qml'] = (
        (ROOT / 'linux/share/monet/widgets/Month.qml').read_bytes(), 0o644)
    for name in ('scratchpads.py', 'notch_tools.py', 'notch_pages.py', 'notch_style.py', 'monitor_page.py', 'command_search.py', 'NotchPlacement.qml', 'actions.py', 'links.py', 'agent_history.py', 'agent_pricing.py', 'notch_preferences.py', 'quick_text_colors.py', 'NotchSettingsLayout.qml', 'tool_pages.py', 'compact_system.py', 'compact_capture.py', 'notch_settings_style.py', 'screen_selection.py', 'inline_dialogs.py', 'script_page.py', 'calendars.py', 'quit_protection.py', 'quit_on_close.py', 'compress_page.py', 'link_settings.py', 'network_page.py', 'mouse_exceptions.py', 'ports.py', 'wallpaper_page.py', 'fan_page.py', 'capture.py', 'window_interaction.py', 'notch_overview.py', 'radial_preview.py', 'radial_art.py', 'wheel_emoji.py', 'settings_sections.py', 'settings_controls.py', 'settings-chevron.svg', 'radial_actions.py', 'radial_editor.py', 'favorites_wheel.py', 'wheel_profiles.py'):
        files[override / name] = ((ROOT / 'linux/share/monet/utilities' / name).read_bytes(), 0o644)
    window = (ROOT / 'linux/share/monet/utilities/window.py').read_text().replace('MODULES = Path(__file__).resolve().parent', 'MODULES = Path(' + repr(str(system_share / 'monet/utilities')) + ')')
    files[override / 'window.py'] = (window.encode(),0o644)
    settings = (ROOT / 'linux/share/monet/utilities/notch_settings.py').read_text().replace('BACKEND = None', 'BACKEND = ' + repr(str(HELPERS / 'monet-notch-layout')))
    files[override / 'notch_settings.py'] = (settings.encode(),0o644)
    for name in ('NotchEditor.qml','ResizeGrip.qml','IslandGlyph.qml','IslandSymbols.js'):
        files[override.parent / 'panel' / name] = ((ROOT/'linux/share/monet/panel'/name).read_bytes(),0o644)
    layout_js = override.parent / 'panel-notch.js'
    files[layout_js] = ((ROOT/'linux/share/monet/panel-notch.js').read_bytes(),0o644)
    quick = (ROOT/'linux/libexec/monet-quick').read_text().replace('@DATADIR@',str(system_share)).replace('@LIBEXECDIR@','/usr/libexec').replace('@BINDIR@','/usr/bin')
    quick = quick.replace('(Path(DATADIR) / "monet/panel-notch.js")', 'Path('+repr(str(layout_js))+')')
    quick = quick.replace('package = notch_package() if choice in ("add", "compact", "wide") else "org.monet.notch"', 'package = '+repr(str(destination)))
    files[HELPERS / 'monet-notch-layout'] = (quick.encode(),0o755)
    launcher = HELPERS / 'monet-notch-utilities'
    shortcuts = (ROOT / 'linux/share/monet/utilities/notch_shortcuts.py').read_text().replace('LAUNCHER = None', 'LAUNCHER = ' + repr(str(launcher)))
    files[override / 'notch_shortcuts.py'] = (shortcuts.encode(), 0o644)
    text = (ROOT / 'linux/libexec/monet-utilities').read_text().replace('@DATADIR@', str(system_share)).replace('@LIBEXECDIR@', '/usr/libexec')
    needle = 'sys.path.insert(0, str(modules))'
    if text.count(needle) != 1:
        raise ValueError('Utilities launcher has changed; review the notch override')
    text = text.replace(needle, needle + '\n# Account-local notch modules; other resources retain their installed paths.\nsys.path.insert(0, ' + repr(str(override)) + ')')
    files[launcher] = (text.encode(), 0o755)
    desktop = (ROOT/'linux/share/applications/monet-notch-settings.desktop').read_text().replace('@LIBEXECDIR@/monet-utilities',str(launcher))
    files[DATA/'applications/monet-notch-settings.desktop'] = (desktop.encode(),0o644)
    radial = (ROOT/'linux/share/applications/org.monet.NotchRadial.desktop').read_text().replace('@LIBEXECDIR@/monet-utilities',str(launcher))
    files[DATA/'applications/org.monet.NotchRadial.desktop'] = (radial.encode(),0o644)
    files[DATA / 'dbus-1/services/org.monet.Utilities.service'] = (
        ('[D-BUS Service]\nName=org.monet.Utilities\nExec=' + str(launcher) + ' --pad-service\n').encode(), 0o644)
    return files


def editor_plan(system_share=Path('/usr/share')):
    """Install the visual editor and Settings entry point for this account."""
    files = {}
    private = PRIVATE / 'editor'
    helpers = HELPERS / 'layout-editor'
    def put(target, data, mode=0o644):
        files[target] = (data, mode)
    def qml(source):
        return (source.read_text().replace('@DATADIR@', str(private))
                .replace('@LIBEXECDIR@', str(helpers)).replace('@BINDIR@', '/usr/bin')).encode()
    # Keep native edit-mode guides from surrounding the live bar. Theme lookup
    # resolves a package at a time, so preserve all other installed theme assets.
    for name in ('monet', 'monet-matte', 'monet-solid'):
        package = Path('plasma/desktoptheme') / name
        existing = DATA / package if (DATA / package / 'metadata.json').is_file() else system_share / package
        if not (existing / 'metadata.json').is_file():
            continue
        for source in existing.rglob('*'):
            if source.is_file():
                put(DATA / package / source.relative_to(existing), source.read_bytes())
        put(DATA / package / 'widgets/margins-highlight.svg',
            (ROOT / 'linux/share' / package / 'widgets/margins-highlight.svg').read_bytes())
    toolbox = Path('plasma/packages/org.kde.paneltoolbox')
    for source in (ROOT / 'linux/share' / toolbox).rglob('*'):
        if source.is_file():
            put(DATA / toolbox / source.relative_to(ROOT / 'linux/share' / toolbox), source.read_bytes())
    # Preserve the complete installed shell: Plasma resolves this as a package.
    package = Path('plasma/shells/org.kde.plasma.desktop')
    existing = DATA / package if (DATA / package / 'metadata.json').is_file() else system_share / package
    for source in existing.rglob('*'):
        if source.is_file() and source.suffix not in {'.qmlc', '.jsc'}:
            put(DATA / package / source.relative_to(existing), source.read_bytes())
    configuration = DATA / package / 'contents/configuration'
    views = DATA / package / 'contents/views'
    if not (existing / 'contents/views/KdeDesktopEditMode.qml').is_file():
        original = existing / 'contents/views/DesktopEditMode.qml'
        if original.is_file():
            put(views / 'KdeDesktopEditMode.qml', original.read_bytes())
    for name in ('DesktopEditMode.qml', 'MonetDesktopEditMode.qml'):
        put(views / name, qml(ROOT / 'linux/share/monet/editmode' / name))
    explorer = DATA / package / 'contents/explorer'
    if not (existing / 'contents/explorer/KdeWidgetExplorer.qml').is_file():
        original = existing / 'contents/explorer/WidgetExplorer.qml'
        if original.is_file():
            put(explorer / 'KdeWidgetExplorer.qml', original.read_bytes())
    for name in ('WidgetExplorer.qml', 'MonetWidgetExplorer.qml'):
        put(explorer / name, qml(ROOT / 'linux/share/monet/explorer' / name))
    if not (existing / 'contents/configuration/KdePanelConfiguration.qml').is_file():
        put(configuration / 'KdePanelConfiguration.qml', (existing / 'contents/configuration/PanelConfiguration.qml').read_bytes())
    page = qml(ROOT / 'linux/share/monet/panel/MonetPanelConfiguration.qml')
    shared = qml(ROOT / 'linux/share/monet/panel/NotchEditor.qml')
    grip = qml(ROOT / 'linux/share/monet/panel/ResizeGrip.qml')
    placement = qml(ROOT / 'linux/share/monet/panel/EditorWindowPlacement.qml')
    glyph = qml(ROOT / 'linux/share/monet/panel/IslandGlyph.qml')
    symbols = qml(ROOT / 'linux/share/monet/panel/IslandSymbols.js')
    revision = hashlib.sha256(page + shared + grip + placement + glyph + symbols).hexdigest()
    entry = 'monet-editor/' + revision + '/MonetPanelConfiguration.qml'
    put(configuration / entry, page)
    put(configuration / 'MonetPanelConfiguration.qml', page)
    wrapper = qml(ROOT / 'linux/share/monet/panel/PanelConfiguration.qml').replace(b'@PANEL_EDITOR@', entry.encode())
    put(configuration / 'PanelConfiguration.qml', wrapper)
    put(configuration / 'monet-editor-entry/PanelConfiguration.qml', wrapper)
    put(configuration / 'MonetPanelEditor.ini', ('[Editor]\nPage=' + entry + '\n').encode())
    for name in ('EditorWindows.js', 'EditorHost.qml', 'EditorAppWindow.qml', 'PanelEditorWindow.qml', 'WidgetEditorWindow.qml', 'WindowControls.qml'):
        put(private / 'monet/panel' / name, qml(ROOT / 'linux/share/monet/panel' / name))
    put(private / 'monet/panel/NotchEditor.qml', shared)
    put(private / 'monet/panel/ResizeGrip.qml', grip)
    put(private / 'monet/panel/EditorWindowPlacement.qml', placement)
    put(private / 'monet/panel/IslandGlyph.qml', glyph)
    put(private / 'monet/panel/IslandSymbols.js', symbols)
    put(private / 'monet/panel-notch.js', (ROOT / 'linux/share/monet/panel-notch.js').read_bytes())
    quick = (ROOT / 'linux/libexec/monet-quick').read_text().replace('@DATADIR@', str(system_share)).replace('@LIBEXECDIR@', '/usr/libexec').replace('@BINDIR@', '/usr/bin')
    quick = quick.replace('(Path(DATADIR) / "monet/panel-notch.js")', 'Path(' + repr(str(private / 'monet/panel-notch.js')) + ')')
    quick = quick.replace('package = notch_package() if choice in ("add", "compact", "wide") else "org.monet.notch"',
                          'package = ' + repr(str(DATA / 'plasma/plasmoids/org.monet.notch')))
    put(helpers / 'monet-quick', quick.encode(), 0o755)
    put(helpers / 'monet-game-keys', (ROOT / 'linux/libexec/monet-game-keys').read_bytes(), 0o755)
    put(helpers / 'monet-editor-window', (ROOT/'linux/libexec/monet-editor-window').read_bytes().replace(b'@LIBEXECDIR@', b'/usr/libexec'), 0o755)
    # Other settings pages retain their installed code and resources.
    for source in (system_share / 'monet/settings-app').rglob('*'):
        if source.is_file() and source.suffix not in {'.qmlc', '.jsc'}:
            put(private / 'monet/settings-app' / source.relative_to(system_share / 'monet/settings-app'), source.read_bytes())
    # These pages share newly added controller methods and backend fields. Keep
    # them from the same source revision when refreshing an existing preview.
    for name in ('MonetSettings.qml', 'NotchPreferences.qml', 'SettingsControls.qml',
                 'SettingsGames.qml', 'SettingsPower.qml', 'SettingsUpdates.qml', 'SettingsAbout.qml'):
        put(private / 'monet/settings-app' / name, (ROOT / 'linux/share/monet/settings-app' / name).read_bytes())
    for name in ('widgets', 'games', 'window-buttons', 'monet_runtime', 'settings', 'textures'):
        put(private / 'monet' / name, system_share / 'monet' / name)
    launcher = (ROOT / 'linux/libexec/monet-settings').read_text().replace('@DATADIR@', str(private)).replace('@LIBEXECDIR@', '/usr/libexec')
    launcher = launcher.replace('_loader.exec_module(games)', '_loader.exec_module(games)\ngames.PROGRAMS["helper"] = ' + repr(str(helpers / 'monet-quick')))
    put(helpers / 'monet-settings', launcher.encode(), 0o755)
    desktop = (system_share / 'applications/monet-settings.desktop').read_text().replace('/usr/libexec/monet-settings', str(helpers / 'monet-settings'))
    put(DATA / 'applications/monet-settings.desktop', desktop.encode())
    return files


def window_frames_plan():
    """Override the active Monet shadow theme without changing window preferences."""
    folder = Path('aurorae/themes/MonetBare')
    return {DATA / folder / source.name: (source.read_bytes(), 0o644)
            for source in (ROOT / 'linux/share' / folder).iterdir() if source.is_file()}


def plan(monitor_bundle=None, monet_prefix=None, dock_bundle=None, native_bundles=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location('connector_package', ROOT / 'browser/monet-passwords/package.py')
    connector = importlib.util.module_from_spec(spec); spec.loader.exec_module(connector)
    connector_data = connector.verify(ROOT)
    files = {}
    prefix = cli_prefix(monet_prefix)
    bindir = prefix / 'bin' if prefix else Path('/usr/bin')
    def render(source, **kwargs):
        kwargs.setdefault('bindir', bindir)
        return globals()['render'](source, **kwargs)
    monitor_binary = None
    if monitor_bundle:
        import importlib.util
        spec = importlib.util.spec_from_file_location('monitor_bundle', ROOT / 'image/task-manager/bundle.py')
        bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)
        monitor_binary = bundle.verified_binary(monitor_bundle)

    def add(target, data, mode=0o644):
        files[target] = (data, mode)
    if dock_bundle:
        import importlib.util
        spec = importlib.util.spec_from_file_location('dock_bundle', ROOT / 'image/dock/bundle.py')
        bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)
        plugins = bundle.verified_binaries(Path(dock_bundle))
        dock = PRIVATE / 'dock'
        for plugin in plugins:
            add(dock / 'plugins/plasma/applets' / plugin.name, plugin.read_bytes(), 0o755)
        add(dock / 'runtime.json', (Path(dock_bundle) / 'runtime.json').read_bytes())
        for name in ('preview.py', 'bundle.py'):
            add(dock / name, (ROOT / 'image/dock' / name).read_bytes())
        add(CONFIG / 'systemd/user/plasma-plasmashell.service.d/monet-dock.conf',
            ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 "' + str(dock / 'preview.py') + '"\n').encode())
    if prefix:
        add(STATE / 'monet/desktop-preview/cli-prefix', (str(prefix) + '\n').encode(), 0o600)
        shortcut = Path('applications/monet-windows.desktop')
        source = DATA / shortcut if (DATA / shortcut).exists() else Path('/usr/share') / shortcut
        if source.exists():
            lines = source.read_text().splitlines(keepends=True)
            for i, line in enumerate(lines):
                if line.startswith('Exec=') and ' windows' in line:
                    command, args = line.split(' windows', 1)
                    if command.endswith('/monet') or command == 'Exec=monet':
                        lines[i] = f'Exec={bindir}/monet windows{args}'
            add(DATA / shortcut, ''.join(lines).encode())
    if monitor_binary:
        add(HELPERS / 'plasma-systemmonitor', monitor_binary.read_bytes(), 0o755)
        add(HELPERS / 'libPlasmaSystemMonitorPage.so', (monitor_bundle / 'libPlasmaSystemMonitorPage.so').read_bytes(), 0o755)
        for name in ('runtime.json', 'source.tar.xz', 'README.md'):
            add(PRIVATE / 'task-manager' / name, (monitor_bundle / name).read_bytes())
    for name in LOCAL:
        add(HELPERS / name, render(ROOT / 'linux/libexec' / name,
            private_data=name in {'monet-settings', 'monet-games', 'monet-store', 'monet-passwords', 'monet-passwords-browser', 'monet-keep-awake', 'monet-brightness'},
            local_helpers=name in {'monet-settings', 'monet-games', 'monet-store', 'monet-light', 'monet-passwords', 'monet-passwords-browser'}), 0o755)
    # Status probes use the new reader. Privileged actions still use the system helper.
    add(HELPERS / 'monet-secure', (ROOT / 'linux/libexec/monet-secure').read_bytes())
    for source in (ROOT / 'linux/share/monet/monet_runtime').glob('*.py'):
        add(PRIVATE / 'monet/monet_runtime' / source.name, source.read_bytes())
    add(HELPERS / 'monet_region.py', (ROOT / 'setup/monet_setup/region.py').read_bytes())
    add(BIN / 'monet-files', HELPERS / 'monet-files')
    for source in (ROOT / 'linux/share/monet/monet_files').glob('*.py'):
        add(DATA / 'monet/monet_files' / source.name, source.read_bytes())
    for name in ('stacks.js', 'transfers.js', 'bar-defaults.js'):
        add(DATA / 'monet' / name, render(ROOT / 'linux/share/monet' / name, local_helpers=True))
    add(DATA / 'applications/monet-archive.desktop', render(ROOT / 'linux/share/applications/monet-archive.desktop', local_helpers=True))
    add(CONFIG / 'systemd/user/monet-fresh.service', render(ROOT / 'linux/systemd/user/monet-fresh.service', local_helpers=True))
    # Layout packages are resolved as a unit. Keep installed logout and other
    # unrelated files while replacing only Monet's current layout instructions.
    for name in ('org.monet.desktop', 'org.monet.smoke.desktop'):
        folder = Path('plasma/look-and-feel') / name
        installed = DATA / folder if (DATA / folder / 'metadata.json').exists() else Path('/usr/share') / folder
        for source in installed.rglob('*'):
            if source.is_file(): add(DATA / folder / source.relative_to(installed), source.read_bytes())
        layout = Path('contents/layouts/org.kde.plasma.desktop-layout.js')
        add(DATA / folder / layout, render(ROOT / 'linux/share' / folder / layout, local_helpers=True))
        for source in (ROOT / 'linux/share/monet/logout').iterdir():
            if source.is_file(): add(DATA / folder / 'contents/logout' / source.name, source.read_bytes())
    for source in (ROOT / 'linux/share/locale').glob('*/LC_MESSAGES/monet.mo'):
        add(DATA / source.relative_to(ROOT / 'linux/share'), source.read_bytes())
        add(PRIVATE / source.relative_to(ROOT / 'linux/share'), source.read_bytes())
    add(DATA / 'dbus-1/services/org.monet.KeepAwake.service',
        render(ROOT / 'linux/share/dbus-1/services/org.monet.KeepAwake.service', local_helpers=True))
    add(CONFIG / 'systemd/user/monet-keep-awake.service',
        render(ROOT / 'linux/systemd/user/monet-keep-awake.service', local_helpers=True))
    add(CONFIG / 'systemd/user/monet-brightness.service',
        render(ROOT / 'linux/systemd/user/monet-brightness.service', local_helpers=True))
    add(CONFIG / 'systemd/user/graphical-session.target.wants/monet-brightness.service',
        CONFIG / 'systemd/user/monet-brightness.service')
    # Preserve the installed launch command and all existing desktop metadata.
    # KWin's supported per-application declaration enables minimized-window
    # notifications; it does not disable compositor permission checks.
    monitor = Path('applications/org.kde.plasma-systemmonitor.desktop')
    source = DATA / monitor if (DATA / monitor).exists() else Path('/usr/share') / monitor
    if source.exists():
        text = source.read_text()
        lines = text.splitlines(keepends=True)
        start = lines.index('[Desktop Entry]\n') + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith('[')), len(lines))
        # KWin matches this capability to the canonical executable path, not a
        # PATH-relative Exec name. Preserve arguments and custom commands.
        executable = shutil.which('plasma-systemmonitor')
        if executable:
            for i in range(start, end):
                if lines[i].rstrip() == 'Exec=plasma-systemmonitor' or lines[i].startswith('Exec=plasma-systemmonitor '):
                    lines[i] = lines[i].replace('Exec=plasma-systemmonitor', 'Exec=' + str(Path(executable).resolve()), 1)
        if monitor_binary:
            for i in range(start, end):
                if lines[i].startswith('Exec='):
                    lines[i] = 'Exec=' + str(HELPERS / 'plasma-systemmonitor') + '\n'
        key = 'X-KDE-Wayland-Interfaces='
        entry = next((i for i in range(start, end) if lines[i].startswith(key)), None)
        interfaces = lines[entry].strip()[len(key):].split(',') if entry is not None else []
        if 'org_kde_plasma_window_management' not in interfaces:
            interfaces.append('org_kde_plasma_window_management')
        value = key + ','.join(interfaces) + '\n'
        if entry is None: lines.insert(start, value)
        else: lines[entry] = value
        add(DATA / monitor, ''.join(lines).encode())
    for source in (ROOT / 'linux/share/monet/passwords').glob('*.py'):
        add(PRIVATE / 'monet/passwords' / source.name, source.read_bytes())
    add(PRIVATE / 'monet/passwords/connector.xpi', connector_data)
    for source in (ROOT / 'linux/share/monet/settings-app').rglob('*'):
        if source.is_file():
            add(PRIVATE / 'monet/settings-app' / source.relative_to(ROOT / 'linux/share/monet/settings-app'), source.read_bytes())
    for source in (ROOT / 'linux/share/monet/store-app').rglob('*'):
        if source.is_file():
            add(PRIVATE / 'monet/store-app' / source.relative_to(ROOT / 'linux/share/monet/store-app'), source.read_bytes())
    # Settings artwork stays shared with the installed OS, without duplicating it.
    for name in ('settings', 'store', 'textures', 'window-buttons'):
        add(PRIVATE / 'monet' / name, Path('/usr/share/monet') / name)
    # Copy the shared frame as well as its callers. Keep the old private games
    # symlink replaceable without ever writing through it into /usr/share.
    add(DATA / 'monet/widgets/ScrollInput.qml', (ROOT / 'linux/share/monet/widgets/ScrollInput.qml').read_bytes())
    # QML resolves ../widgets from the private games URL, before following its
    # symlink into the shared account data directory.
    add(PRIVATE / 'monet/widgets', DATA / 'monet/widgets')
    for source in (ROOT / 'linux/share/monet/games').rglob('*'):
        if source.is_file():
            add(DATA / 'monet/games' / source.relative_to(ROOT / 'linux/share/monet/games'),
                render(source, local_helpers=True) if source.suffix in {'.qml', '.js'} else source.read_bytes())
    add(PRIVATE / 'monet/games', DATA / 'monet/games')
    add(DATA / 'monet/window-buttons', Path('/usr/share/monet/window-buttons'))
    add(DATA / 'monet/textures', Path('/usr/share/monet/textures'))
    wallpaper = ROOT / 'linux/share/plasma/wallpapers/org.monet.hours'
    for source in wallpaper.rglob('*'):
        if source.is_file():
            add(DATA / source.relative_to(ROOT / 'linux/share'), render(source, local_helpers=True)
                if source.suffix in {'.qml', '.js'} else source.read_bytes())
    add(DATA / 'plasma/wallpapers/org.monet.hours/contents/ui/TaskManagerAction.qml',
        render(ROOT / 'linux/share/monet/widgets/TaskManagerAction.qml', local_helpers=True))
    add(DATA / 'plasma/wallpapers/org.monet.hours/contents/ui/SessionActivity.qml',
        render(ROOT / 'linux/share/monet/widgets/SessionActivity.qml', local_helpers=True))
    # Shared fixes must reach desktop widgets too: the lowest-ID desktop
    # widget coordinates layout persistence for the whole containment.
    for source_dir in sorted((ROOT / 'linux/share/plasma/plasmoids').glob('org.monet.*')):
        dest = DATA / 'plasma/plasmoids' / source_dir.name
        for source in source_dir.rglob('*'):
            if source.is_file():
                add(dest / source.relative_to(source_dir), render(source, local_helpers=True)
                    if source.suffix in {'.qml', '.js'} else source.read_bytes())
        for source in (ROOT / 'linux/share/monet/widgets').iterdir():
            if source.is_file(): add(dest / 'contents/ui' / source.name, render(source, local_helpers=True))
    sensor_catalog = Path('ksysguard/sensorfaces/org.monet.performance/contents/ui/SensorCatalog.qml')
    add(DATA / 'plasma/plasmoids/org.monet.system/contents/ui/SensorCatalog.qml',
        (ROOT / 'linux/share' / sensor_catalog).read_bytes())
    # A shell package is resolved as a unit. Copy the installed package so this
    # account can use the updated gallery without masking unrelated shell files.
    shell = Path('plasma/shells/org.kde.plasma.desktop')
    source_shell = DATA / shell if (DATA / shell / 'metadata.json').exists() else Path('/usr/share') / shell
    for source in source_shell.rglob('*'):
        if source.is_file(): add(DATA / shell / source.relative_to(source_shell), source.read_bytes())
    logout = shell / 'contents/logout'
    fallback = source_shell / 'contents/logout/KdeLogout.qml'
    if not fallback.exists(): fallback = source_shell / 'contents/logout/Logout.qml'
    if fallback.exists():
        add(DATA / logout / 'KdeLogout.qml', fallback.read_bytes())
        for source, target in (('ShellLogout.qml', 'Logout.qml'), ('Logout.qml', 'MonetLogout.qml'),
                               ('PowerMark.qml', 'PowerMark.qml'), ('timer.js', 'timer.js'), ('monet.svg', 'monet.svg')):
            add(DATA / logout / target, (ROOT / 'linux/share/monet/logout' / source).read_bytes())
    add(DATA / 'monet/panel/WindowControls.qml',
        (ROOT / 'linux/share/monet/panel/WindowControls.qml').read_bytes())
    gallery = render(ROOT / 'linux/share/monet/explorer/MonetWidgetExplorer.qml', bindir=BIN)
    gallery = gallery.replace(b'file:///usr/share/monet/panel', ('file://' + str(DATA / 'monet/panel')).encode())
    add(DATA / shell / 'contents/explorer/MonetWidgetExplorer.qml', gallery)
    for name in ('MonetLockScreen.qml', 'LockScreen.qml'):
        add(DATA / shell / 'contents/lockscreen' / name,
            (ROOT / 'linux/share/monet/lockscreen' / name).read_bytes())
    add(DATA / shell / 'contents/lockscreen/ClockFormat.qml',
        (ROOT / 'linux/share/monet/widgets/ClockFormat.qml').read_bytes())
    for name in ('chatgpt', 'org.inkscape.Inkscape', 'org.keepassxc.KeePassXC'):
        path = Path('icons/Monet/apps/scalable') / (name + '.svg')
        add(DATA / path, (ROOT / 'linux/share' / path).read_bytes())
    wanted = {'ChatGPT', 'inkscape', 'keepassxc', 'google-chrome-stable', 'google-chrome-beta', 'google-chrome-unstable'}
    for line in (ROOT / 'linux/share/icons/Monet/aliases').read_text().splitlines():
        alias, target = line.split()
        if Path(alias).stem in wanted:
            # An absolute target also works when only the new paintings are user-local.
            candidate = DATA / 'icons/Monet' / Path(alias).parent / target
            target_path = candidate if candidate in files else Path('/usr/share/icons/Monet') / Path(alias).parent / target
            add(DATA / 'icons/Monet' / alias, target_path)
    for folder in ('ksysguard/sensorfaces', 'plasma-systemmonitor'):
        for source in (ROOT / 'linux/share' / folder).rglob('*'):
            if source.is_file(): add(DATA / source.relative_to(ROOT / 'linux/share'),
                render(source, local_helpers=True) if source.suffix == '.qml' else source.read_bytes())
    for source in (ROOT / 'linux/share/locale').glob('*/LC_MESSAGES/plasma-systemmonitor.mo'):
        add(DATA / source.relative_to(ROOT / 'linux/share'), source.read_bytes())
    for name in ('monet-folder-tools.desktop', 'monet-local-app.desktop', 'monet-archive-apps.desktop', 'monet-archive-open.desktop'):
        # KIO trusts user-owned service menus only when marked executable.
        add(DATA / 'kio/servicemenus' / name, render(ROOT / 'linux/share/kio/servicemenus' / name, local_helpers=True), 0o755)
    add(DATA / 'applications/monet-settings.desktop', render(ROOT / 'linux/share/applications/monet-settings.desktop', local_helpers=True))
    add(DATA / 'applications/monet-passwords.desktop', render(ROOT / 'linux/share/applications/monet-passwords.desktop', local_helpers=True))
    # Session restore/return notifications must use the same Settings runtime
    # as search. Otherwise the old system instance captures all later opens.
    add(CONFIG / 'autostart/monet-session.desktop', render(ROOT / 'linux/autostart/monet-session.desktop', local_helpers=True))
    for name in ('monet-store.desktop', 'org.kde.discover.desktop', 'io.github.kolunmi.Bazaar.desktop'):
        target = DATA / 'applications' / name
        if not target.exists() and name != 'monet-store.desktop':
            continue
        source = target if target.exists() else ROOT / 'linux/share/applications/monet-store.desktop'
        lines = source.read_text().splitlines(keepends=True)
        in_entry = False
        for i, line in enumerate(lines):
            if line.startswith('['):
                in_entry = line.strip() == '[Desktop Entry]'
            if in_entry:
                for command in ('/usr/libexec/monet-store', '@LIBEXECDIR@/monet-store'):
                    if line.rstrip() == 'Exec=' + command or line.startswith('Exec=' + command + ' '):
                        lines[i] = line.replace('Exec=' + command, 'Exec=' + str(HELPERS / 'monet-store'), 1)
        # Keep names, icons, arguments, actions and custom launch commands.
        add(target, ''.join(lines).encode())
    for name in ('monet-password-offers.service', 'monet-frames.path', 'monet-frames.service', 'monet-light.timer', 'monet-light.service', 'monet-light-sync.service', 'monet-listening.service',
                 'monet-game-names.path', 'monet-game-names.service'):
        text = render(ROOT / 'linux/systemd/user' / name).decode()
        for helper in ('monet-quick', 'monet-light', 'monet-passwords'):
            text = text.replace('/usr/libexec/' + helper, str(HELPERS / helper))
        add(CONFIG / 'systemd/user' / name, text.encode())
    nvidia = Path(r'app-nvidia\x2dsettings\x2dload@autostart.service.d/monet-saved-settings.conf')
    add(CONFIG / 'systemd/user' / nvidia, (ROOT / 'linux/systemd/user/monet-nvidia-settings.conf').read_bytes())
    if native_bundles:
        spec = importlib.util.spec_from_file_location('desktop_preview_native', ROOT / 'tools/desktop-preview-native.py')
        native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
        # Validate the complete native set before returning any installation plan.
        native.extend(SimpleNamespace(ROOT=ROOT, DATA=DATA, CONFIG=CONFIG, HELPERS=HELPERS, PRIVATE=PRIVATE), files, Path(native_bundles))
    return files


def restore(receipt):
    info = json.loads(receipt.read_text()); kept = []
    for row in reversed(info['files']):
        target = Path(row['path'])
        if digest(target) != row['after']:
            kept.append(str(target)); continue
        if (row.get('after_mode') is not None and target.exists() and not target.is_symlink()
                and stat.S_IMODE(target.stat().st_mode) != row['after_mode']):
            kept.append(str(target)); continue
        if target.exists() or target.is_symlink(): target.unlink()
        if row['before'] is not None:
            saved = receipt.parent / row['backup']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, target, follow_symlinks=False)
    print(json.dumps({'restored': str(receipt), 'preserved_edits': kept}, indent=2))


def recorded_previews():
    """Validated receipt history, including already-retired package paths."""
    rows = {}
    receipts = [*(STATE / 'monet/desktop-preview').glob('*/receipt.json'),
                *(STATE / 'monet/local-test-install').glob('*/receipt.json')]
    for receipt in sorted(receipts, key=lambda path: path.parent.name):
        for row in json.loads(receipt.read_text())['files']:
            # The first laptop installer separately recorded newly seeded user
            # preferences. Those are now their choices, not preview payloads to
            # unwind when the full OS update replaces the account overrides.
            if receipt.parent.parent.name == 'local-test-install' and row.get('backup', '').startswith('config-'):
                continue
            target = Path(row['path'])
            # Receipts are account-local data, never authority for arbitrary paths.
            if not any(target.is_relative_to(root) for root in (DATA, CONFIG, HELPERS, BIN, STATE / 'monet/desktop-preview')):
                raise ValueError(f'Preview receipt is outside the managed account paths: {target}')
            rows.setdefault(target, []).append((receipt, row))
    return rows


def retirement_plan():
    """Replay receipts backwards in memory; never discard an unrecorded edit."""
    rows = recorded_previews()
    changes, kept = {}, []
    for target, history in rows.items():
        current = value = digest(target)
        current_mode = value_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() and not target.is_symlink() else None
        source = None
        for receipt, row in reversed(history):
            if value != row['after']:
                continue
            if row.get('after_mode') is not None and value_mode != row['after_mode']:
                # A later permission edit is personal, even with identical bytes.
                break
            source = receipt.parent / row['backup'] if row['before'] is not None else None
            if source is not None and digest(source) != row['before']:
                raise ValueError(f'Preview backup is missing or changed: {source}')
            value = row['before']
            value_mode = stat.S_IMODE(source.stat().st_mode) if source is not None and not source.is_symlink() else None
        if current == value and current_mode == value_mode:
            if current is not None: kept.append(str(target))
        else:
            changes[target] = (current, source)
    return changes, kept


def is_preview_launcher(path):
    return (any(path.is_relative_to(root) for root in
                (DATA / 'applications', CONFIG / 'autostart', CONFIG / 'systemd/user'))
            or path.is_relative_to(BIN)
            or path == STATE / 'monet/desktop-preview/cli-prefix')


def prune_preview_directories(launchers_only=False):
    # KPackage treats even an empty user package folder as an override. Leaving
    # one behind hides /usr/share's valid shell and can crash Plasma at sign-in.
    roots = (DATA, CONFIG, HELPERS, BIN, STATE / 'monet/desktop-preview')
    parents = set()
    for target in recorded_previews():
        if launchers_only and not is_preview_launcher(target):
            continue
        parent = target.parent
        while parent not in roots and any(parent.is_relative_to(root) for root in roots):
            parents.add(parent)
            parent = parent.parent
    removed = 0
    for parent in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        if parent.is_symlink():
            continue
        if not any(parent.resolve().is_relative_to(root.resolve()) for root in roots):
            continue
        try:
            parent.rmdir()  # Only empty directories; personal contents always win.
            removed += 1
        except OSError:
            pass
    return removed


def running_monet_version(version, release=Path('/usr/lib/os-release')):
    """VERSION identifies Monet; VERSION_ID deliberately identifies Fedora."""
    values = dict(line.split('=', 1) for line in release.read_text().splitlines() if '=' in line)
    return values.get('NAME', '').strip('"') == 'Monet' and values.get('VERSION', '').strip('"') == version


def retire(apply_changes=False, launchers_only=False):
    changes, kept = retirement_plan()
    if launchers_only:
        # Keep payloads used by the currently running desktop until its next
        # start. Retiring entry points first lets systemd load the OS's units.
        changes = {path: value for path, value in changes.items() if is_preview_launcher(path)}
    result = {'retired_files': len(changes), 'preserved_edits': kept, 'applied': apply_changes}
    if apply_changes and changes:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        backup = STATE / 'monet/preview-retirement' / stamp
        backup.mkdir(parents=True, mode=0o700)
        receipt = backup / 'receipt.json'
        info = {'source': str(ROOT), 'files': []}
        # Children before a preview-owned symlink; restoration reverses this.
        for target in sorted(changes, key=lambda path: len(path.parts), reverse=True):
            before, source = changes[target]
            # A personal edit between review and application always wins.
            if digest(target) != before:
                kept.append(str(target)); continue
            after = digest(source) if source is not None else None
            row = dict(path=str(target), before=before, after=after, backup=str(len(info['files'])),
                       before_mode=stat.S_IMODE(target.stat().st_mode) if target.exists() and not target.is_symlink() else None,
                       after_mode=stat.S_IMODE(source.stat().st_mode) if source is not None and not source.is_symlink() else None)
            if before is not None: shutil.copy2(target, backup / row['backup'], follow_symlinks=False)
            info['files'].append(row)
            receipt.write_text(json.dumps(info, indent=2)); receipt.chmod(0o600)
            if target.exists() or target.is_symlink(): target.unlink()
            if source is not None: shutil.copy2(source, target, follow_symlinks=False)
        result.update(receipt=str(receipt), retired_files=len(info['files']))
    if apply_changes:
        result['removed_empty_directories'] = prune_preview_directories(launchers_only)
    print(json.dumps(result, indent=2))


def source_only(files):
    """Remove adjacent bytecode whenever a source preview owns that URL."""
    files = dict(files)
    for target in tuple(files):
        if target.suffix in {'.qml', '.js', '.mjs'}:
            cache = Path(str(target) + 'c')
            files.pop(cache, None)
            if cache.exists() or cache.is_symlink():
                files[cache] = (None, None)
    return files


def apply(files):
    files = source_only(files)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup = STATE / 'monet/desktop-preview' / stamp
    backup.mkdir(parents=True, mode=0o700); receipt = backup / 'receipt.json'
    info = {'source': str(ROOT), 'files': []}
    for target, (data, mode) in files.items():
        after = None if data is None else 'link:' + str(data) if isinstance(data, Path) else hashlib.sha256(data).hexdigest()
        before = digest(target)
        before_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() and not target.is_symlink() else None
        after_mode = None if data is None or isinstance(data, Path) else mode
        if before == after and (isinstance(data, Path) or before_mode == after_mode): continue
        row = {'path': str(target), 'before': before, 'after': after, 'backup': str(len(info['files'])),
               'before_mode': before_mode, 'after_mode': after_mode}
        if before is not None: shutil.copy2(target, backup / row['backup'], follow_symlinks=False)
        info['files'].append(row); receipt.write_text(json.dumps(info, indent=2)); receipt.chmod(0o600)
        if data is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.monet-preview-tmp')
        if temporary.exists() or temporary.is_symlink(): raise FileExistsError(temporary)
        if isinstance(data, Path): temporary.symlink_to(data)
        else:
            temporary.write_bytes(data); temporary.chmod(mode)
        temporary.replace(target)
    receipt.write_text(json.dumps(info, indent=2))
    receipt.chmod(0o600)
    print(json.dumps({'installed_files': len(info['files']), 'receipt': str(receipt)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--restore', type=Path)
    parser.add_argument('--retire', action='store_true', help='Retire recorded account previews; combine with --apply to make changes')
    parser.add_argument('--launchers-only', action='store_true', help='With --retire: keep live desktop payloads until the next sign-in')
    parser.add_argument('--after-version', help='With --retire: defer until this Monet VERSION is running')
    parser.add_argument('--task-manager-bundle', type=Path)
    parser.add_argument('--dock-bundle', type=Path)
    parser.add_argument('--native-bundles', type=Path, help='Matching activity, launcher, dock, Files and Archives bundles')
    parser.add_argument('--notch', action='store_true', help='Update only the notch and its pad service, preserving desktop preferences')
    parser.add_argument('--editor', action='store_true', help='Update the taskbar and notch editor and its Settings entry point')
    parser.add_argument('--window-frames', action='store_true', help='Update Monet window shadows without changing the selected theme; may be combined with --notch')
    parser.add_argument('--monet-prefix', type=Path, help='Root-owned tested CLI preview; remembered for future previews')
    args = parser.parse_args()
    if args.retire and args.restore: parser.error('--retire cannot be combined with --restore')
    if args.launchers_only and not args.retire: parser.error('--launchers-only requires --retire')
    if args.after_version and not args.retire: parser.error('--after-version requires --retire')
    if (args.notch or args.window_frames or args.editor) and (args.retire or args.restore or args.task_manager_bundle or args.dock_bundle or args.native_bundles or args.monet_prefix):
        parser.error('--notch, --editor and --window-frames cannot be combined with other preview targets or restoration')
    if args.after_version and not running_monet_version(args.after_version):
        print(json.dumps({'deferred': True, 'version': args.after_version}))
    elif args.retire: retire(args.apply, args.launchers_only)
    elif args.restore: restore(args.restore)
    elif args.notch or args.window_frames or args.editor:
        files = notch_plan() if args.notch else {}
        if args.window_frames: files.update(window_frames_plan())
        if args.editor: files.update(editor_plan())
        if args.apply: apply(files)
        else: print(json.dumps({'files': len(files), 'data': str(DATA), 'targets': [name for name, active in [('notch', args.notch), ('editor', args.editor), ('window-frames', args.window_frames)] if active]}, indent=2))
    elif args.apply: apply(plan(args.task_manager_bundle, args.monet_prefix, args.dock_bundle, args.native_bundles))
    else: print(json.dumps({'files': len(plan(args.task_manager_bundle, args.monet_prefix, args.dock_bundle, args.native_bundles)), 'data': str(DATA), 'helpers': str(HELPERS)}, indent=2))
