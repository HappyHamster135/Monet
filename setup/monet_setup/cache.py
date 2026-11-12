"""Verify the saved OCI download against the manifest on the installer media."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .checkpoint import atomic, read_file

MARKER = 'download-complete.json'
JSON_LIMIT = 2 * 1024 * 1024
OCI_MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
MANIFESTS = {OCI_MANIFEST, 'application/vnd.docker.distribution.manifest.v2+json'}
INDEXES = {'application/vnd.oci.image.index.v1+json',
           'application/vnd.docker.distribution.manifest.list.v2+json'}


def complete(folder, image):
    index = read_file(folder / 'oci/index.json', JSON_LIMIT)
    atomic(folder / MARKER, json.dumps(dict(image=image, index=hashlib.sha256(index).hexdigest())).encode())


def writable_layout_is_safe(folder):
    root = folder / 'oci'
    digests = root / 'blobs/sha256'
    if any(path.is_symlink() for path in (root, root / 'blobs', digests, root / 'index.json', root / 'oci-layout')):
        return False
    try:
        with os.scandir(digests) as entries:
            return all(entry.is_file(follow_symlinks=False) for entry in entries)
    except FileNotFoundError:
        return True
    except OSError:
        return False


def valid(folder, image, expected=None):
    try:
        receipt = json.loads(read_file(folder / MARKER, 4096))
        root = folder / 'oci'
        if any(p.is_symlink() for p in (root, root / 'blobs', root / 'blobs/sha256')):
            return False
        index_data = read_file(root / 'index.json', JSON_LIMIT)
        if receipt.get('image') != image or hashlib.sha256(index_data).hexdigest() != receipt.get('index'):
            return False
        index = json.loads(index_data)
        if index.get('schemaVersion') != 2:
            return False
        roots = [d for d in index['manifests'] if d.get('annotations', {}).get('org.opencontainers.image.ref.name') == 'latest']
        if len(roots) != 1: return False
        if expected is not None and (roots[0].get('digest') != expected or roots[0].get('mediaType') != OCI_MANIFEST):
            return False
        pending, checked, total = [(roots[0], 0)], set(), 0
        while pending:
            descriptor, depth = pending.pop()
            digest, size, media = descriptor['digest'], descriptor['size'], descriptor['mediaType']
            if (not re.fullmatch(r'sha256:[0-9a-f]{64}', digest) or type(size) is not int
                    or size < 0 or depth > 4 or len(checked) >= 2048): return False
            if digest in checked: continue
            checked.add(digest); total += size
            if total > 128 * 1024**3: return False
            path = root / 'blobs/sha256' / digest[7:]
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size: return False
                value = hashlib.sha256()
                while block := stream.read(1024 * 1024): value.update(block)
            if value.hexdigest() != digest[7:]: return False
            if media in MANIFESTS | INDEXES:
                document = json.loads(read_file(path, JSON_LIMIT))
                if document.get('schemaVersion') != 2: return False
                children = document['manifests'] if media in INDEXES else [document['config'], *document['layers']]
                pending.extend((child, depth + 1) for child in children)
        return bool(checked)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
