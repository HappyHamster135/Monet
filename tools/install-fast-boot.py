#!/usr/bin/env python3
"""Reversible, opt-in boot profile for the locally measured ThinkPad P16s Gen 2.

Use --apply to install, --restore RECEIPT to undo, or --show-menu to request
GRUB's menu at the next boot. Firmware changes take effect after restarting.
This does not flash firmware, regenerate the initrd or modify boot entries.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

BIOS = Path('/sys/class/firmware-attributes/thinklmi/attributes')
USER = Path('/boot/grub2/user.cfg')
CONFIG = Path('/boot/grub2/grub.cfg')
STATE = Path('/var/lib/monet/fast-boot')
NETWORK = ('IPv4NetworkStack', 'IPv6NetworkStack')
BEGIN = '# BEGIN Monet local fast boot'
END = '# END Monet local fast boot'
PROFILE = '''# BEGIN Monet local fast boot
# A completed boot can start directly; failures and trial deployments get a menu.
# A one-time menu request is applied later by bootupd's 14_menu_show_once.cfg.
set timeout_style=menu
set timeout=10
if [ "${boot_success}" = "1" -a -z "${boot_counter}" -a -z "${menu_show_once_timeout}" ]; then
  set timeout=0
fi
# Persist the incomplete-boot marker explicitly. Some installed bootupd configs
# concatenate save_env and an END comment without a separating newline.
# Trial counters and the upstream fallback selection remain under greenboot.
if [ -z "${boot_counter}" ]; then
  set boot_success=0
  save_env boot_success
fi
# END Monet local fast boot
'''


def run(*args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def render(existing):
    """Preserve unrelated settings; never silently override another boot policy."""
    if BEGIN in existing or END in existing:
        if existing.count(BEGIN) != 1 or existing.count(END) != 1:
            raise ValueError('Ambiguous existing fast-boot block')
        start, end = existing.index(BEGIN), existing.index(END)
        if start > end:
            raise ValueError('Invalid fast-boot block')
        remaining = existing[:start] + existing[end + len(END):].lstrip('\n')
    else:
        remaining = existing
    if re.search(r'^\s*(?:set\s+)?(?:timeout(?:_style)?|boot_success|boot_counter|default|saved_entry)\s*=', remaining, re.M):
        raise ValueError('Existing user.cfg contains a custom boot policy; review it first')
    return remaining.rstrip('\n') + ('\n\n' if remaining.strip() else '') + PROFILE


def validate_config(config):
    required = ('source ${prefix}/user.cfg', '### BEGIN 08_greenboot.cfg ###',
                'set boot_success=0', 'save_env boot_counter', 'blscfg',
                '### BEGIN 14_menu_show_once.cfg ###')
    if any(s not in config for s in required):
        raise ValueError('Unrecognized bootupd configuration')
    positions = [config.index(s) for s in (required[0], required[1], required[2], required[4], required[5])]
    if positions != sorted(positions):
        raise ValueError('Unexpected ordering of boot policy and recovery hooks')


def efi_state(text):
    timeout = re.search(r'^Timeout: (\d+) seconds$', text, re.M)
    current = re.search(r'^BootCurrent: ([0-9A-Fa-f]{4})$', text, re.M)
    order = re.search(r'^BootOrder: ([0-9A-Fa-f,]+)$', text, re.M)
    if not timeout or not current or not order:
        raise ValueError('Cannot establish firmware timeout or boot order')
    entry = re.search(r'^Boot' + current[1] + r'\*?\s+(.+)$', text, re.M)
    if not entry or not entry[1].startswith('Monet\t'):
        raise ValueError('The current firmware entry is not Monet')
    if order[1].split(',')[0].upper() != current[1].upper():
        raise ValueError('Monet is not first in the firmware boot order')
    return {'timeout': int(timeout[1]), 'order': order[1], 'current': current[1]}


def bios_value(name):
    return (BIOS / name / 'current_value').read_text().strip()


def snapshot():
    names = (*NETWORK, 'BootMode', 'BootTimeExtension', 'BootOrder',
             'StartupOptionKeys', 'BootDeviceListF12Option', 'SecureBoot')
    files = [CONFIG, *Path('/boot/loader/entries').glob('*.conf')]
    return {'bios': {n: bios_value(n) for n in names},
            'pending_reboot': (BIOS/'pending_reboot').read_text().strip(),
            'efi': efi_state(run('efibootmgr')),
            'grubenv': run('grub2-editenv', '-', 'list'),
            'boot_files': {str(p): digest(p.read_bytes()) for p in files},
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'timing': run('systemd-analyze', 'time')}


def atomic_write(path, data, mode=0o600):
    if path.is_symlink():
        raise ValueError('Refusing to replace a symlink: ' + str(path))
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def validate_firmware(before):
    model = Path('/sys/class/dmi/id/product_version').read_text().strip()
    if model != 'ThinkPad P16s Gen 2':
        raise ValueError('This local profile is qualified only for the measured P16s Gen 2')
    if before['pending_reboot'] != '0':
        raise ValueError('Other firmware changes are pending; restart before installing this profile')
    save_mode = BIOS/'save_settings'
    if save_mode.exists() and save_mode.read_text().strip() != 'single':
        raise ValueError('Another program has selected bulk firmware changes')
    for n in NETWORK:
        if before['bios'][n] not in ('Enable', 'Disable'):
            raise ValueError('Unknown firmware network setting: ' + n)
        if 'Disable' not in (BIOS/n/'possible_values').read_text().split(';'):
            raise ValueError('Firmware does not support disabling ' + n)
    for n, value in {'BootMode': 'Quick', 'BootTimeExtension': 'Disable',
                     'StartupOptionKeys': 'Enable', 'BootDeviceListF12Option': 'Enable'}.items():
        if before['bios'][n] != value:
            raise ValueError('Unexpected firmware configuration: ' + n)


def revert(receipt, *, check_current=True):
    """Undo only recorded changes, without overwriting later user changes."""
    conflicts = []
    if receipt.get('user_written'):
        current = digest(USER.read_bytes()) if USER.exists() else None
        if check_current and current != receipt['user_sha256']:
            conflicts.append(str(USER))
        else:
            backup = receipt.get('user_backup')
            if backup:
                atomic_write(USER, Path(backup).read_bytes(), receipt['user_mode'])
            else:
                USER.unlink(missing_ok=True)
    if receipt.get('efi_written'):
        now = efi_state(run('efibootmgr'))['timeout']
        if check_current and now != 0:
            conflicts.append('firmware timeout')
        else:
            run('efibootmgr', '--timeout', str(receipt['before']['efi']['timeout']))
    for n in reversed(receipt.get('bios_written', [])):
        if check_current and bios_value(n) != 'Disable':
            conflicts.append(n)
        else:
            (BIOS/n/'current_value').write_text(receipt['before']['bios'][n] + '\n')
    if conflicts:
        raise ValueError('Settings changed since installation; not overwritten: ' + ', '.join(conflicts))


def install():
    if USER.is_symlink():
        raise ValueError('user.cfg must not be a symlink')
    before = snapshot()
    validate_firmware(before)
    validate_config(CONFIG.read_text())
    old = USER.read_bytes() if USER.exists() else None
    new = render(old.decode() if old else '').encode()
    with tempfile.NamedTemporaryFile(suffix='.cfg') as check:
        check.write(new); check.flush()
        run('grub2-script-check', check.name)
    run('grub2-script-check', str(CONFIG))
    folder = STATE/datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    folder.mkdir(parents=True, mode=0o700)
    if old is not None: atomic_write(folder/'user.cfg.before', old)
    shutil.copy2(Path(__file__).resolve(), folder/'installer.py')
    receipt_path = folder/'receipt.json'
    receipt = {'schema': 1, 'before': before, 'bios_written': [], 'efi_written': False,
               'user_written': False, 'user_sha256': digest(new),
               'user_backup': str(folder/'user.cfg.before') if old is not None else None,
               'user_mode': USER.stat().st_mode & 0o777 if old is not None else 0o600}
    def save(): atomic_write(receipt_path, (json.dumps(receipt, indent=2)+'\n').encode())
    save()
    try:
        # Journal each intended change before writing, allowing recovery if interrupted.
        for n in NETWORK:
            if before['bios'][n] == 'Enable':
                receipt['bios_written'].append(n); save()
                (BIOS/n/'current_value').write_text('Disable\n')
                if bios_value(n) != 'Disable': raise RuntimeError('Firmware did not accept ' + n)
        if before['efi']['timeout'] != 0:
            receipt['efi_written'] = True; save()
            run('efibootmgr', '--timeout', '0')
        receipt['user_written'] = True; save()
        atomic_write(USER, new, receipt['user_mode'])
        run('restorecon', str(USER))
        run('grub2-script-check', str(USER))
        after = snapshot()
        for field in ('boot_files', 'grubenv'):
            if after[field] != before[field]: raise RuntimeError('Unexpected change to ' + field)
        for field in ('order', 'current'):
            if after['efi'][field] != before['efi'][field]: raise RuntimeError('Firmware boot order changed')
        if after['efi']['timeout'] != 0: raise RuntimeError('Firmware timeout was not saved')
        for n, value in before['bios'].items():
            if n not in NETWORK and after['bios'][n] != value:
                raise RuntimeError('Unexpected firmware change: ' + n)
        receipt.update(status='installed', after=after); save()
    except BaseException as error:
        receipt.update(status='failed', error=str(error)); save()
        try:
            revert(receipt, check_current=False)
            receipt['status'] = 'reverted-after-failure'
        except Exception as undo:
            receipt['restore_error'] = str(undo)
        save()
        raise
    print(json.dumps({'status': 'installed', 'receipt': str(receipt_path),
                      'firmware_changes': receipt['bios_written'],
                      'firmware_timeout': after['efi']['timeout'],
                      'grub_healthy_timeout': 0, 'grub_recovery_timeout': 10,
                      'reboot_required': after['pending_reboot'] == '1'}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--apply', action='store_true')
    action.add_argument('--restore', type=Path, metavar='RECEIPT')
    action.add_argument('--show-menu', action='store_true')
    parser.add_argument('--private-boot', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() != 0:
        if args.private_boot: parser.error('Internal option requires root')
        result = subprocess.run(['pkexec', sys.executable, '-B', str(Path(__file__).resolve()), *sys.argv[1:]])
        return result.returncode
    # /boot is read-only on bootc. Make only this process's mount view writable.
    if not args.private_boot:
        return subprocess.call(['unshare', '--mount', '--propagation', 'private',
                                sys.executable, '-B', str(Path(__file__).resolve()),
                                *sys.argv[1:], '--private-boot'])
    if not Path('/boot').is_mount(): raise RuntimeError('/boot is not a mount point')
    run('mount', '-o', 'remount,bind,rw', '/boot')
    if args.apply:
        install()
    elif args.show_menu:
        run('grub2-editenv', '-', 'set', 'menu_show_once_timeout=30')
        print('The next boot will show the recovery menu for 30 seconds. No restart was requested.')
    else:
        path = args.restore.resolve()
        if path.parent.parent != STATE or path.name != 'receipt.json':
            raise ValueError('Use a receipt from /var/lib/monet/fast-boot')
        receipt = json.loads(path.read_text())
        if receipt.get('status') == 'restored':
            print('Already restored.'); return 0
        revert(receipt)
        receipt['status'] = 'restored'
        atomic_write(path, (json.dumps(receipt, indent=2)+'\n').encode())
        print('Previous boot settings restored. Firmware changes take effect after restarting.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
