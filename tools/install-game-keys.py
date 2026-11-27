#!/usr/bin/env python3
"""Install the game-only laptop keys and their Games settings locally.

--apply stages a fixed system helper, authenticates once through Polkit, then
updates this account's priority service and existing Settings preview. It does
not restart the desktop or change BIOS settings. --system is internal.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'linux/libexec/monet-game-keys'
UNIT = ROOT / 'linux/systemd/monet-game-keys.service'


def system_install(stage):
    if os.geteuid() != 0:
        raise SystemExit('Administrator authentication is required for the keyboard helper.')
    import evdev, pyudev, dbus  # Verify dependencies before any mutation.
    staged = Path(stage)
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = Path('/var/lib/monet/local-game-keys') / stamp
    backup.mkdir(parents=True, mode=0o700)
    for source, dest, mode in (
        (staged / 'monet-game-keys', Path('/usr/local/libexec/monet-game-keys'), 0o755),
        (staged / 'monet-game-keys.service', Path('/etc/systemd/system/monet-game-keys.service'), 0o644)):
        if not source.is_file() or source.is_symlink():
            raise SystemExit('The staged payload is not a regular file.')
        if dest.exists():
            shutil.copy2(dest, backup / dest.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_suffix('.installing')
        temporary.write_bytes(source.read_bytes())
        temporary.chmod(mode)
        temporary.replace(dest)
    subprocess.run(['restorecon', '/usr/local/libexec/monet-game-keys', '/etc/systemd/system/monet-game-keys.service'], check=False)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'monet-game-keys.service'], check=True)
    subprocess.run(['systemctl', 'restart', 'monet-game-keys.service'], check=True)


def apply():
    import evdev, pyudev, dbus
    home = Path.home()
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = home / '.local/state/monet/game-keys-install' / stamp
    backup.mkdir(parents=True)
    files = []
    def put(dest, data, mode=0o644):
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = backup / str(len(files))
        if dest.exists():
            before.write_bytes(dest.read_bytes())
        files.append(dict(path=str(dest), before=str(before) if before.exists() else None,
                          sha256=hashlib.sha256(data).hexdigest()))
        temporary = dest.with_suffix('.installing')
        temporary.write_bytes(data)
        temporary.chmod(mode)
        temporary.replace(dest)

    # Complete and review the fixed payload before requesting system authentication.
    with tempfile.TemporaryDirectory(prefix='monet-game-keys-install-') as folder:
        stage = Path(folder)
        (stage / 'monet-game-keys').write_bytes(HELPER.read_bytes())
        (stage / 'monet-game-keys.service').write_text(UNIT.read_text().replace('@LIBEXECDIR@', '/usr/local/libexec'))
        subprocess.run(['pkexec', sys.executable, str(Path(__file__).resolve()), '--system', str(stage)], check=True)

    local = home / '.local/libexec/monet-game-keys'
    for name in ('monet-game-keys', 'monet-priority', 'monet-rest'):
        put(local / name, (ROOT / 'linux/libexec' / name).read_bytes(), 0o755)
    override = home / '.config/systemd/user/monet-priority.service.d/20-game-keys.conf'
    put(override, f'[Service]\nExecStart=\nExecStart="{local}/monet-priority"\n'.encode())
    # Update the existing editor Settings window without replacing its other pages.
    editor = home / '.local/share/monet-desktop-preview/editor/monet/settings-app'
    preview = home / '.local/libexec/monet-desktop-preview/layout-editor'
    if editor.is_dir() and (preview / 'monet-quick').is_file():
        put(editor / 'SettingsGames.qml', (ROOT / 'linux/share/monet/settings-app/SettingsGames.qml').read_bytes())
        quick = (ROOT / 'linux/libexec/monet-quick').read_text()
        quick = quick.replace('@DATADIR@', '/usr/share').replace('@LIBEXECDIR@', '/usr/libexec').replace('@BINDIR@', '/usr/bin')
        put(preview / 'monet-quick', quick.encode(), 0o755)
        put(preview / 'monet-game-keys', HELPER.read_bytes(), 0o755)
    (backup / 'receipt.json').write_text(json.dumps(files, indent=2) + '\n')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'monet-priority.service'], check=True)
    print('Installed. Backups and receipt: ' + str(backup))
    subprocess.run([str(local / 'monet-game-keys'), 'status'], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--system', metavar='STAGED_PAYLOAD', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.system:
        system_install(args.system)
    elif args.apply:
        apply()
    else:
        print('Adds a system keyboard helper and updates this account’s Games settings and game-focus service.\n'
              'Run with --apply to install; Polkit asks for the administrator password once.')
