#!/usr/bin/env python3
"""One-boot P16s EFI-kernel test, preserving shim for the existing PCR 7 policy.

--install RECEIPT uses the physically tested startup-image receipt. It copies
that kernel/initrd to a new ESP directory, creates an entry outside BootOrder,
and sets BootNext only after verification. GRUB, BLS and original EFI files
remain untouched. --cancel RECEIPT disarms only this trial; files stay for audit.
This is a local experiment, not an update-aware replacement for OSTree boot.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

GLOBAL = '8be4df61-93ca-11d2-aa0d-00e098032b8c'
VARS = Path('/sys/firmware/efi/efivars')
STATE = Path('/var/lib/monet/efi-boot-trial')
LABEL = 'Monet EFI kernel test'


def run(*args):
    return subprocess.check_output(args, text=True, timeout=60).strip()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.receipt-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)


def variable(name):
    path = VARS / (name + '-' + GLOBAL)
    return path.read_bytes() if path.exists() else None


def number(name):
    value = variable(name)
    if value is None:
        return None
    if len(value) != 6:
        raise ValueError('Invalid EFI number: ' + name)
    return struct.unpack_from('<H', value, 4)[0]


def load_option(raw):
    """Decode efivarfs header, EFI_LOAD_OPTION, and GPT/file device path nodes."""
    if len(raw) < 16:
        raise ValueError('Truncated EFI entry')
    attributes, path_size = struct.unpack_from('<IH', raw, 4)
    end = 10
    while end + 2 <= len(raw) and raw[end:end + 2] != b'\0\0':
        end += 2
    if end + 2 + path_size > len(raw) or path_size < 4:
        raise ValueError('Invalid EFI entry lengths')
    label = raw[10:end].decode('utf-16-le')
    pos, limit = end + 2, end + 2 + path_size
    result = dict(active=bool(attributes & 1), label=label)
    while pos + 4 <= limit:
        kind, subtype, size = struct.unpack_from('<BBH', raw, pos)
        if size < 4 or pos + size > limit:
            raise ValueError('Invalid EFI path node')
        node = raw[pos:pos + size]
        if (kind, subtype) == (4, 1):
            if size != 42 or node[40:] != b'\2\2' or 'partuuid' in result:
                raise ValueError('Expected one GPT partition path')
            result.update(partition=struct.unpack_from('<I', node, 4)[0],
                          partuuid=str(uuid.UUID(bytes_le=node[24:40])))
        elif (kind, subtype) == (4, 4):
            if 'loader' in result or node[-2:] != b'\0\0':
                raise ValueError('Expected one terminated EFI file path')
            result['loader'] = node[4:-2].decode('utf-16-le')
        elif (kind, subtype) == (127, 255):
            if size != 4 or pos + size != limit:
                raise ValueError('Invalid EFI path end')
            break
        pos += size
    else:
        raise ValueError('Missing EFI path end')
    if not {'loader', 'partuuid'} <= result.keys():
        raise ValueError('Expected a GPT file boot entry')
    result['options'] = raw[limit:]
    return result


def kernel_options(cmdline, baseline_options, trial):
    if not re.fullmatch(r'\d{8}T\d{6}Z', trial):
        raise ValueError('Invalid trial identifier')
    tokens = cmdline.split()
    cleaned = [v for v in tokens if not v.startswith('BOOT_IMAGE=')
               and not re.fullmatch(r'monet\.startup_trial=\d{8}T\d{6}Z', v)]
    if cleaned != baseline_options.split():
        raise ValueError('Running kernel options differ from the current BLS entry')
    if any(v.startswith(('initrd=', 'rd.luks.key=', 'monet.uefi_trial=')) for v in cleaned):
        raise ValueError('Unsupported existing startup options')
    path = '\\EFI\\MonetDirect\\' + trial
    # Shim 16.1 consumes the first UTF-16 argument as its second-stage path.
    # All remaining arguments are passed to the kernel EFI stub unchanged.
    options = (path + '\\vmlinuz.efi initrd=' + path + '\\initramfs.img '
               + ' '.join(cleaned) + ' monet.uefi_trial=' + trial)
    if len(options.encode('ascii')) >= 2048:
        raise ValueError('Kernel command line is too long')
    return options


def validate_pe(path):
    data = Path(path).read_bytes()[:4096]
    if data[:2] != b'MZ' or len(data) < 64:
        raise ValueError('Kernel is not an EFI executable')
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset + 94 > len(data) or data[offset:offset + 4] != b'PE\0\0':
        raise ValueError('Invalid kernel PE header')
    if (struct.unpack_from('<H', data, offset + 4)[0] != 0x8664
            or struct.unpack_from('<H', data, offset + 24)[0] != 0x20b
            or struct.unpack_from('<H', data, offset + 24 + 68)[0] != 10):
        raise ValueError('Expected an x86-64 EFI application')


def snapshot():
    names = ('BootOrder', 'BootCurrent', 'Timeout', 'SecureBoot', 'SetupMode')
    result = {name: variable(name) for name in names}
    for path in VARS.glob('Boot????-' + GLOBAL):
        name = path.name.split('-')[0]
        if re.fullmatch(r'Boot[0-9A-F]{4}', name):
            result[name] = path.read_bytes()
    return result


def unchanged(before):
    for name, expected in before.items():
        if variable(name) != expected:
            raise RuntimeError('Existing EFI state changed: ' + name)


def deployment():
    deployments = json.loads(run('rpm-ostree', 'status', '--json'))['deployments']
    if any(d.get('staged') for d in deployments):
        raise ValueError('Finish the staged OS update before this experiment')
    booted = [d['checksum'] for d in deployments if d.get('booted')]
    if len(booted) != 1:
        raise ValueError('Cannot identify current deployment')
    return booted[0]


def rollback_entry(bootnum, options):
    """Undo only the exact entry created by this transaction, never another boot."""
    raw = variable(f'Boot{bootnum:04X}')
    if raw is None:
        return
    candidate = load_option(raw)
    if candidate['label'] != LABEL or candidate['options'] not in (
            options.encode('utf-16-le'), (options + '\0').encode('utf-16-le')):
        return
    if number('BootNext') == bootnum:
        run('efibootmgr', '--delete-bootnext')
    run('efibootmgr', '--bootnum', f'{bootnum:04X}', '--delete-bootnum')


def register_once(before, original, bootnum, disk, options, save_entry, verify):
    """Validate the complete EFI load option before arming; roll back failed writes."""
    unchanged(before)
    if number('BootNext') is not None or variable(f'Boot{bootnum:04X}') is not None:
        raise ValueError('Boot selection changed during preparation')
    try:
        # efibootmgr 18's --unicode omits the final UTF-16 NUL. Supply an exact
        # binary payload so shim and the kernel see a terminated command line.
        with tempfile.NamedTemporaryFile(prefix='monet-efi-options-') as payload:
            payload.write((options + '\0').encode('utf-16-le')); payload.flush()
            run('efibootmgr', '--create-only', '--bootnum', f'{bootnum:04X}', '--disk', disk,
                '--part', str(original['partition']), '--label', LABEL, '--loader', original['loader'],
                '--append-binary-args', payload.name)
        new = variable(f'Boot{bootnum:04X}')
        decoded = load_option(new)
        if decoded != {**original, 'label': LABEL, 'options': (options + '\0').encode('utf-16-le')}:
            raise RuntimeError('New EFI boot entry did not round-trip correctly')
        save_entry(hashlib.sha256(new).hexdigest())
        unchanged(before)
        verify()
        if number('BootNext') is not None:
            raise ValueError('Another one-time boot was scheduled during installation')
        run('efibootmgr', '--bootnext', f'{bootnum:04X}')
        if number('BootNext') != bootnum:
            raise RuntimeError('BootNext was not saved correctly')
        unchanged(before)
    except BaseException:
        rollback_entry(bootnum, options)
        raise


def install(source):
    source = source.resolve()
    if (source.name != 'receipt.json' or source.parent.parent != Path('/var/lib/monet/startup-image')
            or source.stat().st_uid != 0):
        raise ValueError('Expected a root-owned startup-image receipt')
    prior = json.loads(source.read_text())
    if (prior.get('status') != 'tested-once'
            or not prior.get('physical_boot_result', {}).get('boot_success')
            or not prior['physical_boot_result'].get('trial_cmdline_marker_present')):
        raise ValueError('The smaller initramfs must have passed a physical boot')
    if prior['kernel'] != os.uname().release:
        raise ValueError('Kernel changed since the image test')
    if Path('/sys/class/dmi/id/product_version').read_text().strip() != 'ThinkPad P16s Gen 2':
        raise ValueError('This experiment is specific to the measured P16s')
    if Path('/sys/firmware/efi/fw_platform_size').read_text().strip() != '64':
        raise ValueError('Expected 64-bit UEFI')
    if number('BootNext') is not None:
        raise ValueError('Another one-time boot is already scheduled')
    before = snapshot()
    if before['SecureBoot'] is None or before['SecureBoot'][4:] != b'\0':
        raise ValueError('This local trial requires the existing Secure Boot-disabled state')
    current = number('BootCurrent')
    original = load_option(before[f'Boot{current:04X}'])
    if (original['label'] != 'Monet' or not original['active']
            or original['loader'] != '\\EFI\\fedora\\shimx64.efi'
            or before['BootOrder'][4:6] != struct.pack('<H', current)):
        raise ValueError('Expected Monet shim as the current and default firmware entry')
    for name, raw in before.items():
        if re.fullmatch(r'Boot[0-9A-F]{4}', name) and LABEL.encode('utf-16-le') in raw:
            raise ValueError('An EFI kernel trial already exists; inspect its receipt')
    deployed = deployment()
    grub = dict(line.split('=', 1) for line in run('grub2-editenv', '-', 'list').splitlines() if '=' in line)
    if grub.get('boot_success') != '1' or any(grub.get(k) for k in ('boot_counter', 'monet_initrd_trial', 'next_entry')):
        raise ValueError('A healthy boot with no other trial is required')
    for name, expected in prior['boot_files'].items():
        if digest(name) != expected:
            raise ValueError('Original boot files changed: ' + name)
    cmdline = Path('/proc/cmdline').read_text().strip()
    ostree = [v for v in cmdline.split() if v.startswith('ostree=')]
    matches = []
    for path in Path('/boot/loader/entries').glob('*.conf'):
        values = dict(line.split(' ', 1) for line in path.read_text().splitlines() if ' ' in line)
        if ostree and ostree[0] in values.get('options', '').split():
            matches.append(values)
    if len(matches) != 1:
        raise ValueError('Cannot identify the running BLS entry')
    entry = matches[0]
    kernel, initrd = Path(entry['linux']).resolve(), Path(prior['installed_image']).resolve()
    if digest(initrd) != prior['sha256'] or str(kernel) not in prior['boot_files']:
        raise ValueError('Unverified kernel or startup image')
    validate_pe(kernel)
    trial = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    options = kernel_options(cmdline, entry['options'], trial)
    partition = (Path('/dev/disk/by-partuuid') / original['partuuid']).resolve(strict=True)
    parent = run('lsblk', '-dnro', 'PKNAME', str(partition))
    if not re.fullmatch(r'nvme\d+n\d+', parent):
        raise ValueError('Expected the local NVMe boot disk')
    if int(Path('/sys/class/block', partition.name, 'partition').read_text()) != original['partition']:
        raise ValueError('EFI partition number does not match the local disk')
    if run('blkid', '-s', 'TYPE', '-o', 'value', str(partition)) != 'vfat':
        raise ValueError('EFI partition is not FAT')
    bootnum = next(n for n in range(65536) if f'Boot{n:04X}' not in before)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = STATE / trial
    folder.mkdir(mode=0o700)
    receipt_path = folder / 'receipt.json'
    receipt = dict(schema=1, status='preparing', trial=trial, boot_number=f'{bootnum:04X}',
                   label=LABEL, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                   deployment=deployed, baseline_systemd_time=run('systemd-analyze', 'time'),
                   source_receipt=str(source), esp_partuuid=original['partuuid'],
                   original_boot_number=f'{current:04X}', options=options,
                   route='UEFI -> existing shim -> Linux EFI stub; GRUB bypassed',
                   reason_for_shim='Existing PCR 7 includes shim SbatLevel measurement',
                   original_boot_files=prior['boot_files'], physical_boot_result=None)
    (folder / 'efi-before.json').write_text(json.dumps({k:v.hex() if v is not None else None for k,v in before.items()}, indent=2))
    shutil.copyfile(__file__, folder / 'installer.py')
    write_json(receipt_path, receipt)
    mnt = Path(tempfile.mkdtemp(prefix='monet-efi-trial-', dir='/run'))
    mounted = False
    try:
        run('mount', '-t', 'vfat', '-o', 'rw,nosuid,nodev,noexec,umask=0077', str(partition), str(mnt))
        mounted = True
        original_files = {str(p.relative_to(mnt)): digest(p) for p in mnt.rglob('*') if p.is_file()}
        if 'EFI/fedora/shimx64.efi' not in original_files:
            raise ValueError('Current EFI launcher is missing')
        if shutil.disk_usage(mnt).free < kernel.stat().st_size + initrd.stat().st_size + 64 * 1024**2:
            raise ValueError('Insufficient free space on the EFI partition')
        relative = Path('EFI/MonetDirect') / trial
        destination = mnt / relative
        destination.mkdir(parents=True, exist_ok=False)
        copies = {'vmlinuz.efi': kernel, 'initramfs.img': initrd}
        expected_files = {str(relative / name): digest(path) for name, path in copies.items()}
        receipt.update(esp_files=expected_files, preserved_esp_files=original_files)
        write_json(receipt_path, receipt)
        for name, src in copies.items():
            with src.open('rb') as inp, (destination / name).open('xb') as out:
                shutil.copyfileobj(inp, out); out.flush(); os.fsync(out.fileno())
        run('sync', '-f', str(mnt))
        for name, expected in {**original_files, **expected_files}.items():
            if digest(mnt / name) != expected:
                raise RuntimeError('EFI file verification failed: ' + name)
        # Unmount and read again to verify durable data before selecting it.
        run('umount', str(mnt)); mounted = False
        run('mount', '-t', 'vfat', '-o', 'ro,nosuid,nodev,noexec', str(partition), str(mnt)); mounted = True
        for name, expected in {**original_files, **expected_files}.items():
            if digest(mnt / name) != expected:
                raise RuntimeError('Remounted EFI file verification failed: ' + name)
        unchanged(before)
        if number('BootNext') is not None or deployment() != deployed:
            raise ValueError('Boot selection or deployment changed during preparation')
        def save_entry(entry_hash):
            receipt.update(status='installed-unarmed', entry_sha256=entry_hash)
            write_json(receipt_path, receipt)

        def verify():
            if deployment() != deployed:
                raise ValueError('Deployment changed before arming')
            for name, expected in prior['boot_files'].items():
                if digest(name) != expected:
                    raise RuntimeError('Original boot files changed: ' + name)

        register_once(before, original, bootnum, '/dev/' + parent, options, save_entry, verify)
        for name, expected in prior['boot_files'].items():
            if digest(name) != expected:
                raise RuntimeError('Original boot files changed during installation: ' + name)
        receipt.update(status='armed-once', existing_boot_order_preserved=True,
                       existing_efi_files_preserved=True, original_boot_files_preserved=True)
        write_json(receipt_path, receipt)
    except BaseException:
        rollback_entry(bootnum, options)
        receipt['status'] = 'failed-disarmed'
        write_json(receipt_path, receipt)
        raise
    finally:
        if mounted:
            run('umount', str(mnt))
        mnt.rmdir()
    print(json.dumps({'status': receipt['status'], 'entry': f'Boot{bootnum:04X}',
                      'receipt': str(receipt_path), 'backup': f'Boot{current:04X} Monet'}, indent=2))


def cancel(path):
    path = path.resolve()
    if path.name != 'receipt.json' or path.parent.parent != STATE or path.stat().st_uid != 0:
        raise ValueError('Expected a root-owned EFI trial receipt')
    receipt = json.loads(path.read_text())
    number_text = receipt['boot_number']
    if not re.fullmatch('[0-9A-F]{4}', number_text):
        raise ValueError('Invalid recorded boot number')
    next_boot = number('BootNext')
    if next_boot not in (None, int(number_text, 16)):
        raise ValueError('A different one-time boot is scheduled; left unchanged')
    raw = variable('Boot' + number_text)
    if raw is None or hashlib.sha256(raw).hexdigest() != receipt.get('entry_sha256'):
        raise ValueError('Trial entry changed; inspect it before cancellation')
    if next_boot is not None:
        run('efibootmgr', '--delete-bootnext')
        if number('BootNext') is not None:
            raise RuntimeError('Could not disarm the trial')
    receipt['status'] = 'disarmed'
    write_json(path, receipt)
    print('EFI trial disarmed. The original boot order is unchanged; test files retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--install', type=Path)
    action.add_argument('--cancel', type=Path)
    parser.add_argument('--private-mounts', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() != 0:
        if args.private_mounts:
            parser.error('Internal flag requires root')
        return subprocess.call(['pkexec', sys.executable, '-B', str(Path(__file__).resolve()), *sys.argv[1:]])
    if args.install and not args.private_mounts:
        return subprocess.call(['unshare', '--mount', '--propagation', 'private', sys.executable,
                                '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--private-mounts'])
    install(args.install) if args.install else cancel(args.cancel)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
