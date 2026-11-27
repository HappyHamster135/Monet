#!/usr/bin/env python3
"""Arm one validated, locally built P16s initramfs trial; keep normal boots intact.

--arm takes its root-owned /var/lib/monet/startup-image/.../receipt.json.
--cancel removes that trial and restores custom.cfg, refusing later edits.
This does not build an image, rewrite BLS entries, or reboot the computer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

STATE = Path('/var/lib/monet/startup-image')
CUSTOM = Path('/boot/grub2/custom.cfg')
FLAG = 'monet_initrd_trial'
BEGIN = '# BEGIN Monet startup image trial'
END = '# END Monet startup image trial'


def run(*args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, data, mode=0o600):
    if path.is_symlink():
        raise ValueError('Refusing symlinked destination: ' + str(path))
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), mode)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)


def boot_entry(text):
    fields = {}
    for line in text.splitlines():
        key, _, value = line.partition(' ')
        if key in ('linux', 'initrd', 'options'):
            if key in fields:
                raise ValueError('Ambiguous boot entry: ' + key)
            fields[key] = value
    if set(fields) != {'linux', 'initrd', 'options'}:
        raise ValueError('Incomplete boot entry')
    for key, value in fields.items():
        if not re.fullmatch(r'[A-Za-z0-9_./:=,+@% -]+', value) or '..' in value.split('/'):
            raise ValueError('Unsupported boot entry syntax: ' + key)
        if key != 'options' and (not value.startswith('/boot/ostree/') or ' ' in value):
            raise ValueError('Unexpected kernel or initramfs path')
    if not any(x.startswith('ostree=/ostree/boot.') for x in fields['options'].split()):
        raise ValueError('Expected a standard OSTree boot link')
    return fields


def render(existing, entry, trial):
    if BEGIN in existing or END in existing or FLAG in existing:
        raise ValueError('A startup trial already exists')
    if not re.fullmatch(r'\d{8}T\d{6}Z', trial):
        raise ValueError('Invalid trial identifier')
    # custom.cfg is sourced after blscfg: append a menu entry without changing
    # OSTree's indices. Consume the selector BEFORE attempting the trial kernel.
    # If saving fails, keep the ordinary selection. A later power-on is normal.
    return existing.rstrip() + '\n\n' + f'''{BEGIN}
menuentry 'Monet: smaller startup image test' --id monet-initrd-trial {{
    linux {entry['linux']} {entry['options']} monet.startup_trial={trial}
    initrd /boot/monet-startup/{trial}/initramfs.img
}}
if [ "${{{FLAG}}}" = "{trial}" ]; then
    unset {FLAG}
    if save_env {FLAG}; then
        if [ -z "${{boot_counter}}" ]; then
            set default=monet-initrd-trial
            set fallback=0
        fi
    fi
fi
{END}
'''


def env():
    return dict(line.split('=', 1) for line in run('grub2-editenv', '-', 'list').splitlines() if '=' in line)


def arm(path, receipt):
    if receipt['status'] != 'validated-uninstalled' or not all(receipt['validation'].values()):
        raise ValueError('The image must pass validation first')
    if Path('/sys/class/dmi/id/product_version').read_text().strip() != 'ThinkPad P16s Gen 2':
        raise ValueError('This trial is specific to the measured P16s')
    if receipt['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Boot changed since the build; revalidate the image')
    if receipt['kernel'] != os.uname().release:
        raise ValueError('Kernel changed since the build')
    state = env()
    if state.get('boot_success') != '1' or any(state.get(k) for k in (FLAG, 'boot_counter', 'next_entry', 'menu_show_once_timeout')):
        raise ValueError('A healthy boot with no other trial or menu request is required')
    deployments = json.loads(run('rpm-ostree', 'status', '--json'))
    if any(d.get('staged') for d in deployments['deployments']):
        raise ValueError('An OS update is staged; finish it before this test')
    cmdline = Path('/proc/cmdline').read_text().strip().split(' ', 1)[1]
    entries = list(Path('/boot/loader/entries').glob('*.conf'))
    matches = [boot_entry(p.read_text()) for p in entries if '\noptions ' + cmdline + '\n' in '\n' + p.read_text()]
    if len(matches) != 1:
        raise ValueError('Cannot identify the running deployment boot entry')
    entry = matches[0]
    original = Path(entry['initrd']).resolve()
    candidate = path.parent / 'initramfs.img'
    if (original != Path(receipt['original_image']).resolve()
            or digest(original) != receipt['original_sha256'] or digest(candidate) != receipt['sha256']):
        raise ValueError('Startup image changed since validation')
    if candidate.stat().st_size >= original.stat().st_size * .95:
        raise ValueError('Insufficient size reduction to justify a boot trial')
    if CUSTOM.is_symlink():
        raise ValueError('Custom GRUB configuration is symlinked')
    existing = CUSTOM.read_text() if CUSTOM.exists() else ''
    config = Path('/boot/grub2/grub.cfg')
    if 'source $prefix/custom.cfg' not in config.read_text():
        raise ValueError('GRUB does not load custom entries')
    new = render(existing, entry, path.parent.name)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg') as f:
        f.write(new); f.flush()
        run('grub2-script-check', f.name)
    boot_files = {str(p): digest(p) for p in [config, *entries, original, Path(entry['linux']).resolve()]}
    destination = Path('/boot/monet-startup') / path.parent.name / 'initramfs.img'
    if destination.exists():
        raise ValueError('Trial destination already exists')
    receipt.update(status='installing', custom_existed=CUSTOM.exists(),
                   custom_mode=CUSTOM.stat().st_mode & 0o777 if CUSTOM.exists() else 0o600,
                   custom_after_sha256=hashlib.sha256(new.encode()).hexdigest(),
                   boot_files=boot_files, installed_image=str(destination))
    atomic_write(path.parent / 'custom.cfg.before', existing.encode())
    atomic_write(path, (json.dumps(receipt, indent=2) + '\n').encode())
    try:
        destination.parent.mkdir(parents=True, exist_ok=False)
        atomic_write(destination, candidate.read_bytes())
        atomic_write(CUSTOM, new.encode(), receipt['custom_mode'])
        run('restorecon', str(CUSTOM), str(destination))
        if digest(destination) != receipt['sha256'] or any(digest(Path(p)) != h for p, h in boot_files.items()):
            raise RuntimeError('Installed image or preserved boot files failed verification')
        run('grub2-editenv', '-', 'set', FLAG + '=' + path.parent.name)
        if env() != {**state, FLAG: path.parent.name}:
            raise RuntimeError('Unexpected boot-environment change')
        receipt['status'] = 'armed-once'
        atomic_write(path, (json.dumps(receipt, indent=2) + '\n').encode())
    except BaseException:
        cancel(path, receipt)
        raise
    print(json.dumps({'status': receipt['status'], 'receipt': str(path),
                      'original_bytes': original.stat().st_size, 'trial_bytes': candidate.stat().st_size}, indent=2))


def cancel(path, receipt):
    if 'custom_after_sha256' not in receipt:
        raise ValueError('This image was never installed as a trial')
    selector = env().get(FLAG)
    if selector not in (None, path.parent.name):
        raise ValueError('A different trial is armed')
    run('grub2-editenv', '-', 'unset', FLAG)
    if CUSTOM.exists() and digest(CUSTOM) == receipt.get('custom_after_sha256'):
        if receipt['custom_existed']:
            atomic_write(CUSTOM, (path.parent / 'custom.cfg.before').read_bytes(), receipt.get('custom_mode', 0o600))
            run('restorecon', str(CUSTOM))
        else:
            CUSTOM.unlink()
    elif CUSTOM.exists() and CUSTOM.read_bytes() != (path.parent / 'custom.cfg.before').read_bytes():
        raise ValueError('Custom GRUB config changed later; trial disarmed but later edits preserved')
    destination = Path('/boot/monet-startup') / path.parent.name / 'initramfs.img'
    if destination.exists():
        if digest(destination) != receipt['sha256']:
            raise ValueError('Trial file changed; left in place')
        destination.unlink()
        destination.parent.rmdir()
    receipt['status'] = 'cancelled'
    atomic_write(path, (json.dumps(receipt, indent=2) + '\n').encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--arm', type=Path)
    action.add_argument('--cancel', type=Path)
    parser.add_argument('--private-boot', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() != 0:
        if args.private_boot:
            parser.error('Internal flag requires root')
        return subprocess.call(['pkexec', sys.executable, '-B', str(Path(__file__).resolve()), *sys.argv[1:]])
    if not args.private_boot:
        return subprocess.call(['unshare', '--mount', '--propagation', 'private', sys.executable,
                                '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--private-boot'])
    path = (args.arm or args.cancel).resolve()
    if path.parent.parent != STATE or path.name != 'receipt.json' or path.stat().st_uid != 0:
        raise ValueError('Expected a root-owned local build receipt')
    if not Path('/boot').is_mount():
        raise ValueError('/boot must be mounted')
    run('mount', '-o', 'remount,bind,rw', '/boot')
    receipt = json.loads(path.read_text())
    if args.arm:
        arm(path, receipt)
    else:
        cancel(path, receipt)
        print('Trial cancelled; original startup retained.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
