#!/usr/bin/env python3
"""Install the laptop monitoring, battery details and conditional boot wait locally."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def put(path, data, backup, records, mode=0o644):
    if path.is_symlink():
        raise RuntimeError('Refusing to replace a symlink: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    record = next((r for r in records if r['path'] == str(path)), None)
    if record is None:
        previous = backup / str(len(records))
        if path.exists(): previous.write_bytes(path.read_bytes())
        record = dict(path=str(path), before=str(previous) if previous.exists() else None)
        records.append(record)
    record['sha256'] = hashlib.sha256(data).hexdigest()
    temp = path.with_name(path.name + '.installing')
    temp.write_bytes(data); temp.chmod(mode); temp.replace(path)
    # Image bytecode is ahead-of-time compiled and can override changed QML.
    if path.suffix in ('.qml', '.js'):
        cache = path.with_suffix('.qmlc' if path.suffix == '.qml' else '.jsc')
        if cache.exists() and not cache.is_symlink():
            previous = backup / str(len(records))
            previous.write_bytes(cache.read_bytes())
            records.append(dict(path=str(cache), before=str(previous), sha256=None))
            cache.unlink()


def system_install(stage):
    if os.geteuid() != 0: raise RuntimeError('System installation requires administrator authentication.')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('prepare_boot', stage / 'prepare.py')
    boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
    # Validate against a staged copy before touching the real unit override.
    vendor = Path('/usr/lib/systemd/system/greenboot-healthcheck.service.d/10-network-online.conf')
    target = Path('/etc/systemd/system/greenboot-healthcheck.service.d/10-network-online.conf')
    with tempfile.TemporaryDirectory(prefix='monet-boot-validate-') as folder:
        root = Path(folder)
        copy = root / vendor.relative_to('/'); copy.parent.mkdir(parents=True); copy.write_bytes(vendor.read_bytes())
        if target.exists() or target.is_symlink():
            if target.is_symlink(): raise RuntimeError('Existing boot override is a symlink.')
            copy = root / target.relative_to('/'); copy.parent.mkdir(parents=True); copy.write_bytes(target.read_bytes())
        boot.prepare_healthcheck(root, '/usr/local/libexec', local=True)
        override = (root / target.relative_to('/')).read_bytes()
    backup = Path('/var/lib/monet/local-power') / datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    backup.mkdir(parents=True, mode=0o700); records = []
    put(Path('/usr/local/libexec/monet-boot-network'), (stage/'monet-boot-network').read_bytes(), backup, records, 0o755)
    put(target, override, backup, records)
    (backup/'receipt.json').write_text(json.dumps(records, indent=2) + '\n')
    subprocess.run(['restorecon', '/usr/local/libexec/monet-boot-network', str(target)], check=False)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)


def apply():
    home = Path.home()
    backup = home / '.local/state/monet/power-install' / datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    backup.mkdir(parents=True); records = []
    data = home / '.local/share'
    helper = home / '.local/libexec/monet-power-preview'
    with tempfile.TemporaryDirectory(prefix='monet-power-install-') as folder:
        stage = Path(folder)
        shutil.copy2(ROOT/'image/boot/prepare.py', stage/'prepare.py')
        shutil.copy2(ROOT/'linux/libexec/monet-boot-network', stage/'monet-boot-network')
        subprocess.run(['pkexec', sys.executable, '-B', str(Path(__file__).resolve()), '--system', str(stage)], check=True)
    put(helper / 'monet-graphics-use', (ROOT/'linux/libexec/monet-graphics-use').read_bytes(), backup, records, 0o755)
    policy = (ROOT/'linux/share/monet/widgets/GraphicsPolicy.qml').read_text().replace('@LIBEXECDIR@', str(helper)).encode()
    package = data/'plasma/plasmoids/org.monet.system'
    if not package.exists():
        # Keep the installed widget's shared modules and artwork intact.
        source = Path('/usr/share/plasma/plasmoids/org.monet.system')
        for p in source.rglob('*'):
            if p.is_file() and p.suffix not in ('.qmlc', '.jsc'):
                put(package/p.relative_to(source), p.read_bytes(), backup, records)
    for name in ('main.qml', 'ReadingCell.qml', 'ReadingStrip.qml', 'ConfigReadings.qml'):
        source = ROOT/'linux/share/plasma/plasmoids/org.monet.system/contents/ui'/name
        put(package/'contents/ui'/name, source.read_bytes(), backup, records)
    source = ROOT/'linux/share/plasma/plasmoids/org.monet.system/contents/config/main.xml'
    put(package/'contents/config/main.xml', source.read_bytes(), backup, records)
    put(package/'contents/ui/GraphicsPolicy.qml', policy, backup, records)
    notch = data/'plasma/plasmoids/org.monet.notch/contents/ui'
    if notch.is_dir():
        put(notch/'GraphicsPolicy.qml', policy, backup, records)
        put(notch/'IslandSystem.qml', (ROOT/'linux/share/plasma/plasmoids/org.monet.notch/contents/ui/IslandSystem.qml').read_bytes(), backup, records)
    settings = data/'monet-desktop-preview/editor/monet/settings-app'
    preview = home / '.local/libexec/monet-desktop-preview/layout-editor'
    if settings.is_dir() and (preview/'monet-quick').exists():
        for name in ('SettingsPower.qml', 'MonetSettings.qml'):
            put(settings/name, (ROOT/'linux/share/monet/settings-app'/name).read_bytes(), backup, records)
        code = (ROOT/'linux/libexec/monet-quick').read_text().replace('@LIBEXECDIR@', '/usr/libexec').replace('@DATADIR@', '/usr/share').replace('@BINDIR@', '/usr/bin')
        put(preview/'monet-quick', code.encode(), backup, records, 0o755)
    (backup/'receipt.json').write_text(json.dumps(records, indent=2) + '\n')
    print('Installed. Backups and receipt: ' + str(backup), flush=True)
    # Disconnect old sensor subscriptions, including any left in KDE's daemon.
    subprocess.run(['systemctl', '--user', 'restart', 'plasma-plasmashell.service'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'plasma-ksystemstats.service'], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--system', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.system: system_install(args.system)
    elif args.apply: apply()
    else: print('Run with --apply. Updates this account’s desktop widget and Settings, adds a boot-wait override, and reloads Plasma. Backups are kept.')
