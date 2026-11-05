"""Opt-in app login policy and encrypted storage. No secret files or global typing hooks."""
import configparser
import fcntl
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import tempfile

from vault import VaultError, pack_map, readable

APP_FOLDER = 'Monet App Logins'
MAX_VALUE = 4096


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'monet/app-logins.json'


def policy(path=None):
    path = path or config_path()
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError()
        data = json.loads(path.read_text())
        if (data.get('version') != 1 or type(data.get('enabled')) is not bool
                or not isinstance(data.get('ignored'), dict) or len(data['ignored']) > 256
                or not isinstance(data.get('saved_apps', []), list) or len(data.get('saved_apps', [])) > 512
                or any(not isinstance(k, str) or not re.fullmatch(r'[a-f0-9]{64}', k) for k in data.get('saved_apps', []))
                or any(not re.fullmatch(r'[a-f0-9]{64}', k) or not valid_text(v, 200)
                       for k, v in data['ignored'].items())):
            raise ValueError()
        return data
    except FileNotFoundError:
        return {'version': 1, 'enabled': False, 'ignored': {}}
    except (OSError, ValueError, TypeError, AttributeError):
        return {'version': 1, 'enabled': False, 'ignored': {}, 'error': True}


def change_policy(*, enabled=None, ignore=None, reset=False, saved=None, path=None):
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Save completion and the Settings switch must not overwrite each other's
    # preferences. In particular, recording an app must never re-enable capture.
    fd = os.open(path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _change_policy(enabled=enabled, ignore=ignore, reset=reset, saved=saved, path=path)
    finally:
        os.close(fd)


def _change_policy(*, enabled, ignore, reset, saved, path):
    data = policy(path)
    if data.get('error'):
        raise VaultError('App login settings could not be read. No settings were changed.')
    if enabled is not None:
        if type(enabled) is not bool:
            raise ValueError('Invalid preference')
        data['enabled'] = enabled
    if reset:
        data['ignored'] = {}
    if ignore:
        if len(data['ignored']) >= 256 and ignore.key not in data['ignored']:
            raise VaultError('The skipped-app list is full. Reset it in Password settings first.')
        data['ignored'][ignore.key] = ignore.name
    if saved:
        known = data.get('saved_apps', [])
        if saved.key not in known:
            data['saved_apps'] = (known + [saved.key])[-512:]
    encoded = json.dumps(data, ensure_ascii=True)
    if len(encoded) > 65536:
        raise VaultError('App login settings are full. Reset skipped apps before trying again.')
    fd, name = tempfile.mkstemp(prefix='.app-logins-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(encoded)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)
    return data


def valid_text(value, limit=MAX_VALUE, empty=True):
    return (isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= limit
            and readable(value) and not any(ord(c) < 32 or 0x7f <= ord(c) < 0xa0
                                           or c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'
                                           for c in value))


@dataclass(frozen=True)
class AppIdentity:
    scope: str
    name: str
    executable: str

    @property
    def key(self):
        return hashlib.sha256(self.scope.encode()).hexdigest()

    @property
    def document(self):
        return self.scope.partition('|document:')[2]


def identify(pid, proc=Path('/proc')):
    """PID must come from D-Bus peer credentials, never a request's app name/PID."""
    folder = proc / str(int(pid))
    if folder.stat().st_uid != os.getuid():
        raise ValueError('Different user')
    executable = str((folder / 'exe').readlink())
    name = Path(executable).name
    if not executable.startswith('/') or executable.endswith(' (deleted)'):
        raise ValueError('Unknown executable')
    # Never offer to save the vault/master password, desktop unlock, admin auth,
    # terminals, or browser forms whose web origin cannot be established here.
    excluded = ('monet-password', 'kwallet', 'ksecretd', 'keepass', 'bitwarden', '1password',
                'pinentry', 'polkit', 'kscreenlocker', 'plasmalogin', 'kcheckpass',
                'systemsettings', 'konsole', 'terminal', 'firefox', 'zen', 'chrom', 'brave',
                'vivaldi', 'opera', 'microsoft-edge', 'ssh', 'sudo', 'su', 'bash', 'sh', 'zsh')
    scope = 'executable:' + executable
    info = folder / 'root/.flatpak-info'
    if info.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        with info.open() as stream:
            contents = stream.read(65537)
        if len(contents) > 65536: raise ValueError('Unknown sandbox')
        parser.read_string(contents)
        app_id = parser.get('Application', 'name')
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}', app_id):
            raise ValueError('Unknown sandbox')
        if any(x in app_id.casefold() for x in ('browser', 'firefox', 'chrom', 'brave', 'keepass',
                'bitwarden', '1password', 'kwallet', 'terminal', 'konsole', 'zen', 'vivaldi',
                'opera', 'microsoft.edge')):
            raise ValueError('Excluded application')
        scope, name = 'flatpak:' + app_id, app_id
    elif any(name == x or name.startswith(x + '-') for x in excluded) or any(
            x in name.casefold() for x in excluded[:14]):
        raise ValueError('Excluded application')
    elif re.fullmatch(r'electron(?:-?\d+)?', name.casefold()):
        # A shared Electron executable is not an app identity. Resolve the
        # launched package from peer process arguments; never use its claimed
        # product name or a renderer-supplied PID. Packaged apps have unique exes.
        with (folder / 'cmdline').open('rb') as stream:
            arguments = stream.read(8193)
        if len(arguments) > 8192: raise ValueError('Unknown Electron application')
        vector = [os.fsdecode(arg) for arg in arguments.split(b'\0') if arg]
        if len(vector) == 1:
            # Recent Electron rewrites argv to a single process-title string.
            # Accept only an unambiguous executable + flags + one package path.
            vector = shlex.split(vector[0])
            if not vector or vector[0] != executable: raise ValueError('Unknown Electron launch')
        args = vector[1:]
        if any(arg.startswith('--type=') for arg in args):
            raise ValueError('Electron child process')
        packages = [arg for arg in args if not arg.startswith('-')]
        if len(packages) != 1: raise ValueError('Unknown Electron package')
        package = packages[0]
        path = Path(package)
        if not path.is_absolute(): path = (folder / 'cwd').resolve() / path
        path = path.resolve(strict=True)
        if not path.is_file() and not (path / 'package.json').is_file():
            raise ValueError('Unknown Electron package')
        scope += '|package:' + str(path)
        name = path.stem
    elif name.startswith(('python', 'ruby', 'perl', 'node')):
        # Distinguish installed script apps from other programs using the interpreter.
        with (folder / 'cmdline').open('rb') as stream:
            args = stream.read(8192).split(b'\0')
        script = Path(os.fsdecode(args[1])) if len(args) > 1 else Path()
        if (not script.is_absolute() or not script.is_file() or 'monet-password' in str(script)
                or script.name == 'monet-settings'):
            raise ValueError('Unknown script application')
        scope += '|script:' + str(script.resolve())
        name, executable = script.stem, str(script.resolve())
    if '|document:' in scope or not valid_text(scope, 4096, False) or not valid_text(name, 200, False):
        raise ValueError('Invalid application identity')
    return AppIdentity(scope, name, executable)


def allowed(identity, path=None):
    settings = policy(path)
    return settings['enabled'] and identity.key not in settings['ignored']


def known_app(identity):
    return identity.key in policy().get('saved_apps', [])


def candidate(data):
    """An offer contains one account, never bulk records or an arbitrary website."""
    if not isinstance(data, dict) or set(data) - {'username', 'password', 'service', 'kind'}:
        raise ValueError('Invalid offer')
    result = dict(username=data.get('username', ''), password=data.get('password', ''),
                  service=data.get('service', ''), kind=data.get('kind', 'login'))
    if (result['kind'] not in ('login', 'register', 'change')
            or not valid_text(result['username'], 320)
            or not valid_text(result['service'], 200)
            or not isinstance(result['password'], str) or len(result['password']) > MAX_VALUE
            or not readable(result['password'])):
        raise ValueError('Invalid offer')
    return result


class AppLoginStore:
    """Only an approved prompt uses this. App credentials never enter browser matching."""
    def __init__(self, vault, identity, guard=lambda: True):
        self.vault, self.identity, self.guard = vault, identity, guard

    def check(self):
        if not self.guard():
            raise VaultError('Saving was cancelled. App login offers are off or the screen is locked.')
        self.vault.check()

    def prepare(self, values):
        values = candidate(values)
        if not values['password']:
            raise VaultError('Enter the password you want to save.')
        self.check()
        title = self.identity.name + ' — ' + (values['username'] or 'Account')
        digest = hashlib.sha256(json.dumps([self.identity.scope, values['service'], values['username']],
                                          ensure_ascii=True).encode()).hexdigest()
        legacy = title[:130] + ' [' + digest + ']'
        key = title[:60] + ' [' + self.identity.key + ':' + digest + ']'
        if self.vault.call('hasEntry', self.vault.handle, APP_FOLDER, legacy, self.vault.app_id):
            key = legacy  # Preserve already saved preview records and their names.
        before = None
        if self.vault.call('hasEntry', self.vault.handle, APP_FOLDER, key, self.vault.app_id):
            before = self.vault.read(APP_FOLDER, key)
            if (before['fields'].get('Application ID') != self.identity.scope
                    or before['fields'].get('Username') != values['username']
                    or before['fields'].get('Service') != values['service']):
                raise VaultError('This saved account has changed. Review it in Monet Passwords.')
        fields = {'Username': values['username'], 'Password': values['password'],
                  'Application': self.identity.name, 'Application ID': self.identity.scope,
                  'Service': values['service']}
        return {'key': key, 'fields': fields, 'before': before,
                'unchanged': bool(before and before['fields'] == fields)}

    def commit(self, prepared):
        self.check()
        vault = self.vault
        before = prepared['before']
        if before:
            vault.selected = before
            vault.unchanged()
        elif vault.call('hasEntry', vault.handle, APP_FOLDER, prepared['key'], vault.app_id):
            raise VaultError('This account was saved elsewhere. Reopen it in Monet Passwords.')
        if prepared['unchanged']:
            return 'unchanged'
        self.check()
        if before:
            vault.save(prepared['fields'])
        else:
            if not vault.call('hasFolder', vault.handle, APP_FOLDER, vault.app_id):
                if not vault.call('createFolder', vault.handle, APP_FOLDER, vault.app_id):
                    raise VaultError('The vault could not create a place for app logins.')
            self.check()
            if int(vault.call('writeMap', vault.handle, APP_FOLDER, prepared['key'],
                              pack_map(prepared['fields']), vault.app_id)) != 0:
                raise VaultError('The vault could not save this login.')
            self.check()
            if vault.read(APP_FOLDER, prepared['key'])['fields'] != prepared['fields']:
                raise VaultError('The saved login could not be verified. Reopen Monet Passwords.')
        return 'updated' if before else 'saved'

    def accounts(self, service, username=''):
        if not valid_text(service, 200) or not valid_text(username, 320):
            raise VaultError('Check the app account and service.')
        self.check()
        keys = self.vault.call('entryList', self.vault.handle, APP_FOLDER, self.vault.app_id)
        if len(keys) > 2000:
            raise VaultError('Too many app logins. Open Monet Passwords to choose an account.')
        rows = []
        for key in keys:
            key = str(key)
            scope = re.search(r' \[([a-f0-9]{64}):[a-f0-9]{64}\]$', key)
            if scope and scope[1] != self.identity.key:
                continue  # New records can be filtered without reading other apps' secrets.
            self.check()
            entry = self.vault.read(APP_FOLDER, key)
            fields = entry['fields']
            if (fields.get('Application ID') != self.identity.scope or fields.get('Service', '') != service
                    or username and fields.get('Username', '') != username):
                continue
            if not fields.get('Password') or not valid_text(fields.get('Username', ''), 320):
                continue
            rows.append({'key': key, 'username': fields.get('Username', ''), 'service': service,
                         'signature': entry['signature']})
            if len(rows) > 128:
                raise VaultError('Too many matching accounts. Enter a username in the app first.')
        return sorted(rows, key=lambda row: row['username'].casefold())

    def retrieve(self, row):
        self.check()
        entry = self.vault.read(APP_FOLDER, row['key'])
        fields = entry['fields']
        if (entry['signature'] != row['signature'] or fields.get('Application ID') != self.identity.scope
                or fields.get('Service', '') != row['service'] or fields.get('Username', '') != row['username']):
            raise VaultError('This account changed. Choose it again before filling.')
        result = candidate({'username': fields.get('Username', ''), 'password': fields.get('Password', ''),
                            'service': fields.get('Service', '')})
        if not result['password']:
            raise VaultError('This account has no saved password.')
        self.check()
        return {k: result[k] for k in ('username', 'password', 'service')}
