#!/usr/bin/env python3
"""Install the tested desktop UI for this account, without changing the OS image.

Default: show the plan. --apply: back up and install. --restore RECEIPT: undo
unchanged installed files, preserving files edited since installation.
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
LOCAL = {'monet-quick', 'monet-settings', 'monet-games', 'monet-files-tools', 'monet-system-info', 'monet-weather', 'monet-light', 'monet-daylight'}


def digest(path):
    if path.is_symlink():
        return 'link:' + os.readlink(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def render(source, *, private_data=False, local_helpers=False):
    text = source.read_text()
    # Keep privileged and image-bound helpers at their installed system paths.
    # Route only these user-facing helpers to the preview, including self calls.
    if not local_helpers:
        for name in LOCAL:
            text = text.replace('{LIBEXECDIR}/' + name, str(HELPERS / name))
    return (text.replace('@BINDIR@', '/usr/bin')
            .replace('@DATADIR@', str(PRIVATE) if private_data else '/usr/share')
            .replace('@LIBEXECDIR@', str(HELPERS) if local_helpers else '/usr/libexec')).encode()


def plan(monitor_bundle=None):
    files = {}
    monitor_binary = None
    if monitor_bundle:
        import importlib.util
        spec = importlib.util.spec_from_file_location('monitor_bundle', ROOT / 'image/task-manager/bundle.py')
        bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)
        monitor_binary = bundle.verified_binary(monitor_bundle)

    def add(target, data, mode=0o644):
        files[target] = (data, mode)
    if monitor_binary:
        add(HELPERS / 'plasma-systemmonitor', monitor_binary.read_bytes(), 0o755)
        for name in ('runtime.json', 'source.tar.xz', 'README.md'):
            add(PRIVATE / 'task-manager' / name, (monitor_bundle / name).read_bytes())
    for name in LOCAL:
        add(HELPERS / name, render(ROOT / 'linux/libexec' / name,
            private_data=name == 'monet-settings', local_helpers=name in {'monet-settings', 'monet-games', 'monet-light'}), 0o755)
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
    for source in (ROOT / 'linux/share/monet/settings-app').rglob('*'):
        if source.is_file():
            add(PRIVATE / 'monet/settings-app' / source.relative_to(ROOT / 'linux/share/monet/settings-app'), source.read_bytes())
    # Settings artwork stays shared with the installed OS, without duplicating it.
    for name in ('settings', 'textures', 'window-buttons'):
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
    for name in ('monet-folder-tools.desktop', 'monet-local-app.desktop'):
        add(DATA / 'kio/servicemenus' / name, render(ROOT / 'linux/share/kio/servicemenus' / name, local_helpers=True))
    add(DATA / 'applications/monet-settings.desktop', render(ROOT / 'linux/share/applications/monet-settings.desktop', local_helpers=True))
    for name in ('monet-frames.path', 'monet-frames.service', 'monet-light.timer', 'monet-light.service', 'monet-light-sync.service'):
        text = render(ROOT / 'linux/systemd/user' / name).decode()
        for helper in ('monet-quick', 'monet-light'):
            text = text.replace('/usr/libexec/' + helper, str(HELPERS / helper))
        add(CONFIG / 'systemd/user' / name, text.encode())
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
            shutil.copy2(saved, target, follow_symlinks=False)
    print(json.dumps({'restored': str(receipt), 'preserved_edits': kept}, indent=2))


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
    parser.add_argument('--task-manager-bundle', type=Path)
    args = parser.parse_args()
    if args.restore: restore(args.restore)
    elif args.apply: apply(plan(args.task_manager_bundle))
    else: print(json.dumps({'files': len(plan(args.task_manager_bundle)), 'data': str(DATA), 'helpers': str(HELPERS)}, indent=2))
