#!/usr/bin/python3
"""Pinned acceptance-test runtime; never included in Monet's OS image."""
import hashlib
from pathlib import Path
import sys
import urllib.request
import zipfile
import io

VERSION = '43.8.7'
SHA256 = '2f8e1a625c4f84bd7a6cbf1c0cb8d37a6ddb45050aab89be1adcbc818a5c1689'
root = Path(sys.argv[1]).resolve()
assert not root.exists(), 'Use a new test-runtime directory'
url = f'https://github.com/electron/electron/releases/download/v{VERSION}/electron-v{VERSION}-linux-x64.zip'
with urllib.request.urlopen(url, timeout=120) as response:
    data = response.read(200_000_001)
assert len(data) <= 200_000_000 and hashlib.sha256(data).hexdigest() == SHA256
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for item in archive.infolist():
        destination = root/item.filename
        assert destination.resolve().is_relative_to(root)
        archive.extract(item, root)
        if item.external_attr >> 16: destination.chmod((item.external_attr >> 16) & 0o777)
print('Verified Electron ' + VERSION)
