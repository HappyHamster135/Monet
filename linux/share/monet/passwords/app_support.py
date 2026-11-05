"""Reversible per-app accessibility preference; never grants sandbox permissions."""
import base64
import configparser
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

KEY = 'ACCESSIBILITY_ENABLED'
LIMIT = 262144


def app_id(value):
    return isinstance(value, str) and len(value) <= 255 and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}', value)


def excluded(value):
    return any(part in value.casefold() for part in ('browser', 'firefox', 'chrom', 'zen', 'brave',
        'vivaldi', 'opera', 'microsoft.edge', 'keepass', 'kwallet', 'bitwarden', '1password', 'konsole', 'terminal'))


def read(path, limit=LIMIT):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    import stat
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('App settings could not be verified.')
        data = stream.read(limit + 1)
        if len(data) > limit: raise ValueError('App settings are too large.')
        return data


def parse(data):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string((data or b'').decode('utf-8'))
    if parser.defaults(): raise ValueError('App settings could not be verified.')
    return parser


def atomic(path, data, expected):
    if read(path) != expected: raise ValueError('App settings changed. Refresh and try again.')
    if data is None:
        if expected is not None: path.unlink()
        return
    fd, name = tempfile.mkstemp(prefix='.monet-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if read(path) != expected: raise ValueError('App settings changed. Refresh and try again.')
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


class AppSupport:
    def __init__(self, data=None, config=None, runner=subprocess.run):
        self.overrides = (data or Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share')))/'flatpak/overrides'
        self.receipts = (config or Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config')))/'monet/app-support'
        self.runner = runner

    def record(self, ident):
        # A receipt contains a base64 backup of a bounded override file.
        data = read(self.receipts/(ident+'.json'), (LIMIT + 2)//3*4 + 4096)
        if data is None: return None
        value = json.loads(data)
        if (value.get('version') != 1 or value.get('app') != ident or
                not re.fullmatch('[a-f0-9]{64}', value.get('after', '')) or
                not isinstance(value.get('existed'), bool) or not isinstance(value.get('before'), str)):
            raise ValueError('Saved app settings could not be verified.')
        old = base64.b64decode(value['before'], validate=True)
        if len(old) > LIMIT: raise ValueError('Saved app settings are too large.')
        parse(old)
        return value

    def listed(self):
        result = self.runner(['flatpak', 'list', '--app', '--columns=application,name'], capture_output=True,
                             text=True, timeout=8)
        if result.returncode or len(result.stdout) > LIMIT: raise ValueError('Apps could not be listed. Try again.')
        found = {}
        for line in result.stdout.splitlines():
            ident, _, name = line.partition('\t')
            if app_id(ident) and not excluded(ident): found[ident] = name.strip()[:200] or ident
        # Keep an uninstall's receipt available for Undo without reinstalling.
        if self.receipts.exists():
            for path in self.receipts.glob('*.json'):
                if app_id(path.stem) and not excluded(path.stem): found.setdefault(path.stem, path.stem)
        if len(found) > 512: raise ValueError('Too many apps to review at once.')
        rows = []
        for ident, name in sorted(found.items(), key=lambda item: item[1].casefold()):
            current = parse(read(self.overrides/ident))
            rows.append(dict(id=ident, name=name, enabled=current.get('Environment', KEY, fallback=None) == '1',
                             managed=self.record(ident) is not None))
        return rows

    def change(self, ident, enabled):
        if not app_id(ident) or excluded(ident) or type(enabled) is not bool: raise ValueError('Unknown app.')
        if ident not in {r['id'] for r in self.listed()}: raise ValueError('This app is no longer installed.')
        for folder in (self.overrides, self.receipts):
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            if folder.is_symlink() or folder.stat().st_uid != os.getuid(): raise ValueError('App settings folder changed.')
        lock = os.open(self.receipts/'.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path, receipt = self.overrides/ident, self.receipts/(ident+'.json')
            current = read(path); parser = parse(current); record = self.record(ident)
            value = parser.get('Environment', KEY, fallback=None)
            if enabled:
                if value == '1': return {'changed': False}
                if record: raise ValueError('Undo the earlier support change first.')
                if not parser.has_section('Environment'): parser.add_section('Environment')
                parser.set('Environment', KEY, '1')
                buffer = io.StringIO(); parser.write(buffer, space_around_delimiters=False); after = buffer.getvalue().encode()
                if len(after) > LIMIT: raise ValueError('App settings are too large.')
                record = dict(version=1, app=ident, existed=current is not None,
                              before=base64.b64encode(current or b'').decode(), after=hashlib.sha256(after).hexdigest())
                atomic(receipt, json.dumps(record).encode(), None)
                atomic(path, after, current)
                return {'changed': True}
            if not record: return {'changed': False}
            if value != '1':
                receipt.unlink(); return {'changed': False, 'preserved': True}
            before = base64.b64decode(record['before'])
            if hashlib.sha256(current).hexdigest() == record['after']:
                after = before if record['existed'] else None
            else:
                old = parse(before).get('Environment', KEY, fallback=None)
                if old is None: parser.remove_option('Environment', KEY)
                else: parser.set('Environment', KEY, old)
                if not parser.items('Environment'): parser.remove_section('Environment')
                buffer = io.StringIO(); parser.write(buffer, space_around_delimiters=False); after = buffer.getvalue().encode()
                if len(after) > LIMIT: raise ValueError('App settings are too large.')
            atomic(path, after, current); receipt.unlink()
            return {'changed': True}
        finally:
            os.close(lock)
