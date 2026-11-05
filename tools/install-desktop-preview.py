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
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
HELPERS = Path.home() / '.local/libexec/monet-desktop-preview'
PRIVATE = DATA / 'monet-desktop-preview'
LOCAL = {'monet-quick', 'monet-settings', 'monet-games', 'monet-store', 'monet-store-jobs', 'monet-files-tools', 'monet-system-info', 'monet-weather', 'monet-light', 'monet-daylight'}
LOCAL |= {'monet-resume', 'monet-files-session', 'monet-browser-session', 'monet-editor-session', 'monet-pdf-session'}
LOCAL |= {'monet-session', 'monet-passwords', 'monet-passwords-browser'}


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


def plan(monitor_bundle=None, monet_prefix=None, dock_bundle=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location('connector_package', ROOT / 'browser/monet-passwords/package.py')
    connector = importlib.util.module_from_spec(spec); spec.loader.exec_module(connector)
    connector_data = connector.verify(ROOT)
    files = {}
    prefix = cli_prefix(monet_prefix)
    bindir = prefix / 'bin' if prefix else Path('/usr/bin')
    def render(source, **kwargs):
        return globals()['render'](source, bindir=bindir, **kwargs)
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
        for name in ('runtime.json', 'source.tar.xz', 'README.md'):
            add(PRIVATE / 'task-manager' / name, (monitor_bundle / name).read_bytes())
    for name in LOCAL:
        add(HELPERS / name, render(ROOT / 'linux/libexec' / name,
            private_data=name in {'monet-settings', 'monet-games', 'monet-store', 'monet-passwords', 'monet-passwords-browser'},
            local_helpers=name in {'monet-settings', 'monet-games', 'monet-store', 'monet-light', 'monet-passwords', 'monet-passwords-browser'}), 0o755)
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
    # A shell package is resolved as a unit. Copy the installed package so this
    # account can use the updated gallery without masking unrelated shell files.
    shell = Path('plasma/shells/org.kde.plasma.desktop')
    source_shell = DATA / shell if (DATA / shell / 'metadata.json').exists() else Path('/usr/share') / shell
    for source in source_shell.rglob('*'):
        if source.is_file(): add(DATA / shell / source.relative_to(source_shell), source.read_bytes())
    add(DATA / shell / 'contents/explorer/MonetWidgetExplorer.qml',
        (ROOT / 'linux/share/monet/explorer/MonetWidgetExplorer.qml').read_bytes())
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
    for name in ('monet-folder-tools.desktop', 'monet-local-app.desktop', 'monet-archive-apps.desktop'):
        add(DATA / 'kio/servicemenus' / name, render(ROOT / 'linux/share/kio/servicemenus' / name, local_helpers=True))
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
    for name in ('monet-password-offers.service', 'monet-frames.path', 'monet-frames.service', 'monet-light.timer', 'monet-light.service', 'monet-light-sync.service', 'monet-listening.service'):
        text = render(ROOT / 'linux/systemd/user' / name).decode()
        for helper in ('monet-quick', 'monet-light', 'monet-passwords'):
            text = text.replace('/usr/libexec/' + helper, str(HELPERS / helper))
        add(CONFIG / 'systemd/user' / name, text.encode())
    nvidia = Path(r'app-nvidia\x2dsettings\x2dload@autostart.service.d/monet-saved-settings.conf')
    add(CONFIG / 'systemd/user' / nvidia, (ROOT / 'linux/systemd/user/monet-nvidia-settings.conf').read_bytes())
    return files


def restore(receipt):
    info = json.loads(receipt.read_text()); kept = []
    for row in reversed(info['files']):
        target = Path(row['path'])
        if digest(target) != row['after']:
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
    for receipt in sorted((STATE / 'monet/desktop-preview').glob('*/receipt.json')):
        for row in json.loads(receipt.read_text())['files']:
            target = Path(row['path'])
            # Receipts are account-local data, never authority for arbitrary paths.
            if not any(target.is_relative_to(root) for root in (DATA, CONFIG, HELPERS, STATE / 'monet/desktop-preview')):
                raise ValueError(f'Preview receipt is outside the managed account paths: {target}')
            rows.setdefault(target, []).append((receipt, row))
    return rows


def retirement_plan():
    """Replay receipts backwards in memory; never discard an unrecorded edit."""
    rows = recorded_previews()
    changes, kept = {}, []
    for target, history in rows.items():
        current = value = digest(target)
        source = None
        for receipt, row in reversed(history):
            if value != row['after']:
                continue
            source = receipt.parent / row['backup'] if row['before'] is not None else None
            if source is not None and digest(source) != row['before']:
                raise ValueError(f'Preview backup is missing or changed: {source}')
            value = row['before']
        if current == value:
            if current is not None: kept.append(str(target))
        else:
            changes[target] = (current, source)
    return changes, kept


def is_preview_launcher(path):
    return (any(path.is_relative_to(root) for root in
                (DATA / 'applications', CONFIG / 'autostart', CONFIG / 'systemd/user'))
            or path == STATE / 'monet/desktop-preview/cli-prefix')


def prune_preview_directories(launchers_only=False):
    # KPackage treats even an empty user package folder as an override. Leaving
    # one behind hides /usr/share's valid shell and can crash Plasma at sign-in.
    roots = (DATA, CONFIG, HELPERS, STATE / 'monet/desktop-preview')
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
            row = dict(path=str(target), before=before, after=after, backup=str(len(info['files'])))
            if before is not None: shutil.copy2(target, backup / row['backup'], follow_symlinks=False)
            info['files'].append(row)
            receipt.write_text(json.dumps(info, indent=2)); receipt.chmod(0o600)
            if target.exists() or target.is_symlink(): target.unlink()
            if source is not None: shutil.copy2(source, target, follow_symlinks=False)
        result.update(receipt=str(receipt), retired_files=len(info['files']))
    if apply_changes:
        result['removed_empty_directories'] = prune_preview_directories(launchers_only)
    print(json.dumps(result, indent=2))


def apply(files):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup = STATE / 'monet/desktop-preview' / stamp
    backup.mkdir(parents=True); receipt = backup / 'receipt.json'
    info = {'source': str(ROOT), 'files': []}
    for target, (data, mode) in files.items():
        after = 'link:' + str(data) if isinstance(data, Path) else hashlib.sha256(data).hexdigest()
        before = digest(target)
        if before == after: continue
        row = {'path': str(target), 'before': before, 'after': after, 'backup': str(len(info['files']))}
        if before is not None: shutil.copy2(target, backup / row['backup'], follow_symlinks=False)
        info['files'].append(row); receipt.write_text(json.dumps(info, indent=2))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.monet-preview-tmp')
        if temporary.exists() or temporary.is_symlink(): raise FileExistsError(temporary)
        if isinstance(data, Path): temporary.symlink_to(data)
        else:
            temporary.write_bytes(data); temporary.chmod(mode)
        temporary.replace(target)
    receipt.write_text(json.dumps(info, indent=2))
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
    parser.add_argument('--monet-prefix', type=Path, help='Root-owned tested CLI preview; remembered for future previews')
    args = parser.parse_args()
    if args.retire and args.restore: parser.error('--retire cannot be combined with --restore')
    if args.launchers_only and not args.retire: parser.error('--launchers-only requires --retire')
    if args.after_version and not args.retire: parser.error('--after-version requires --retire')
    if args.after_version and not running_monet_version(args.after_version):
        print(json.dumps({'deferred': True, 'version': args.after_version}))
    elif args.retire: retire(args.apply, args.launchers_only)
    elif args.restore: restore(args.restore)
    elif args.apply: apply(plan(args.task_manager_bundle, args.monet_prefix, args.dock_bundle))
    else: print(json.dumps({'files': len(plan(args.task_manager_bundle, args.monet_prefix, args.dock_bundle)), 'data': str(DATA), 'helpers': str(HELPERS)}, indent=2))
