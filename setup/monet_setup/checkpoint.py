"""A bounded installation receipt on the newly created boot filesystem.

No account password, Wi-Fi password or recovery phrase is stored. An encrypted
target retains only its existing bootstrap key, just as /boot does before TPM
enrollment. That slot is retired by monet-seal after the first successful boot.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from . import disks

DIRECTORY = 'monet-setup-pending'
RECEIPT = 'checkpoint.json'
KEYFILE = 'bootstrap.key'


def read_file(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        import stat
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Invalid installation checkpoint file')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Installation checkpoint is too large')
    return data


def atomic(path, data):
    fd, name = tempfile.mkstemp(prefix='.checkpoint-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def boot_mount(partition, writable=False):
    parent = Path('/run/monet-setup/probes'); parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = Path(tempfile.mkdtemp(prefix='boot-', dir=parent))
    mounted = False
    try:
        options = 'rw,nodev,nosuid,noexec' if writable else 'ro,noload,nodev,nosuid,noexec'
        subprocess.run(['mount', '-t', 'ext4', '-o', options, partition, str(folder)],
                       check=True, capture_output=True, timeout=30)
        mounted = True
        yield folder
    finally:
        if mounted:
            subprocess.run(['umount', str(folder)], check=True, capture_output=True, timeout=30)
        folder.rmdir()


def current_disk(path):
    return next((d for d in disks.lsblk() if d.get('path') == path and d.get('type') == 'disk'), None)


def validate(receipt, disk):
    if (not isinstance(receipt, dict) or receipt.get('schema') != 1
            or not re.fullmatch(r'[0-9a-f]{32}', str(receipt.get('id', '')))
            or receipt.get('identity') != disks.identity(disk)
            or receipt.get('layout') != disks.layout(disk)
            or receipt.get('mode') not in ('erase', 'keep')
            or not isinstance(receipt.get('encrypted'), bool)
            or not isinstance(receipt.get('image'), str)
            or not isinstance(receipt.get('sizes'), dict)):
        raise ValueError('The installation checkpoint does not match this drive')
    sizes = receipt['sizes']
    if (not all(isinstance(sizes.get(key), int) and 0 < sizes[key] < 10**10 for key in ('boot', 'monet'))
            or receipt['mode'] == 'erase' and not isinstance(sizes.get('windows'), int)):
        raise ValueError('Invalid checkpoint sizes')
    parts = {}
    records = receipt.get('partitions', {})
    if not isinstance(records, dict) or set(records) != {'efi', 'boot', 'monet'}:
        raise ValueError('Incomplete checkpoint partitions')
    for role, expected in records.items():
        if not isinstance(expected, dict) or not expected.get('partuuid') or not expected.get('uuid'):
            raise ValueError('Missing partition identity')
        matches = [p for p in disk.get('children', []) if p.get('partuuid') == expected['partuuid']]
        if len(matches) != 1:
            raise ValueError('Checkpoint partition is missing or ambiguous')
        part = matches[0]
        if any(part.get(key) != expected.get(key) for key in ('uuid', 'fstype', 'size', 'start')):
            raise ValueError('Checkpoint filesystem changed')
        expected_type = {'efi': 'vfat', 'boot': 'ext4', 'monet': 'crypto_LUKS' if receipt['encrypted'] else 'btrfs'}[role]
        if part.get('fstype') != expected_type or part.get('type') != 'part':
            raise ValueError('Unexpected checkpoint filesystem')
        parts[role] = part['path']
    if len(set(parts.values())) != 3:
        raise ValueError('Checkpoint partitions overlap')
    return parts


def read(root, disk):
    folder = root / DIRECTORY
    if folder.is_symlink():
        raise ValueError('Invalid checkpoint folder')
    receipt = json.loads(read_file(folder / RECEIPT, 16384))
    parts = validate(receipt, disk)
    if receipt['encrypted']:
        key = read_file(folder / KEYFILE, 64)
        if len(key) != 64 or hashlib.sha256(key).hexdigest() != receipt.get('key_sha256'):
            raise ValueError('Invalid installation bootstrap key')
    return receipt, parts


def probe(disk):
    """Only inspect candidate boot partitions on the explicitly selected drive."""
    if disk is None or disks.in_use(disk):
        return None
    candidates = [p for p in disk.get('children', []) if p.get('fstype') == 'ext4'
                  and p.get('label') == 'boot' and 0 < int(p.get('size') or 0) <= 4 * disks.GIB]
    found = []
    for part in candidates[:4]:
        try:
            with boot_mount(part['path']) as root:
                receipt, parts = read(root, disk)
                if parts['boot'] == part['path']:
                    try:
                        receipt['health'] = json.loads(read_file(root / DIRECTORY / 'health.json', 4096))
                    except (OSError, ValueError):
                        pass
                    found.append(receipt)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            continue
    return found[0] if len(found) == 1 else None


def save(plan, parts, key):
    disk = current_disk(plan['disk'])
    if disk is None or disks.identity(disk) != plan['identity']:
        raise ValueError('The installation drive changed')
    records = {}
    for role in ('efi', 'boot', 'monet'):
        part = next(p for p in disk['children'] if p['path'] == parts[role])
        records[role] = {k: part.get(k) for k in ('partuuid', 'uuid', 'fstype', 'size', 'start')}
    receipt = dict(schema=1, id=uuid.uuid4().hex, identity=disks.identity(disk), layout=disks.layout(disk),
                   mode=plan['mode'], image=plan['image'], sizes=plan['sizes'],
                   encrypted=bool(parts.get('fs')), partitions=records)
    validate(receipt, disk)
    with boot_mount(parts['boot'], writable=True) as root:
        folder = root / DIRECTORY
        folder.mkdir(mode=0o700)  # Never overwrite an unrelated installation's receipt.
        if receipt['encrypted']:
            data = read_file(key, 64)
            if len(data) != 64:
                raise ValueError('Invalid installation bootstrap key')
            receipt['key_sha256'] = hashlib.sha256(data).hexdigest()
            atomic(folder / KEYFILE, data)
        atomic(folder / RECEIPT, (json.dumps(receipt, sort_keys=True) + '\n').encode())
    return receipt


def resume(plan, key):
    disk = current_disk(plan['disk'])
    if disk is None or disks.in_use(disk):
        raise ValueError('The installation drive is missing or in use')
    receipt = probe(disk)
    if receipt is None or receipt['id'] != plan.get('resume') or receipt['image'] != plan['image']:
        raise ValueError('The interrupted installation could not be verified')
    parts = validate(receipt, disk)
    if receipt['encrypted']:
        with boot_mount(parts['boot']) as root:
            read(root, disk)  # Recheck before copying the bounded bootstrap key.
            key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic(key, read_file(root / DIRECTORY / KEYFILE, 64))
    plan.update(mode=receipt['mode'], sizes=receipt['sizes'], encrypt=receipt['encrypted'])
    return parts, receipt


def clear(parts):
    with boot_mount(parts['boot'], writable=True) as root:
        folder = root / DIRECTORY
        if folder.is_symlink():
            raise ValueError('Invalid checkpoint folder')
        (folder / KEYFILE).unlink(missing_ok=True)
        (folder / RECEIPT).unlink(missing_ok=True)
        (folder / 'health.json').unlink(missing_ok=True)
        for temporary in folder.glob('.checkpoint-*'):
            if temporary.is_file() or temporary.is_symlink(): temporary.unlink()
        if folder.exists():
            try: folder.rmdir()
            except OSError: pass  # Preserve unrelated files; our key/receipt are gone.
