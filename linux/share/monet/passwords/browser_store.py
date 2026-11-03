"""Origin-scoped browser access to Monet-owned logins. No browser profile scraping."""
import base64
import hashlib
import json
import secrets
from urllib.parse import urlsplit

from vault import PERSONAL_FOLDER, VaultError, pack_map, unpack_map, readable

CONNECTIONS = 'Monet Browser Connections'
MAX_MATCHES = 100


class BrowserError(Exception):
    def __init__(self, message, code=8):
        super().__init__(message)
        self.code = code


def origin(url):
    """Exact scheme/IDNA host/effective port. Never suffix-match or trust userinfo."""
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 33 for c in url) or '\\' in url:
        raise BrowserError('This website address is not supported.')
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
        if not host or parsed.username is not None or parsed.password is not None or '%' in host:
            raise ValueError()
        if parsed.scheme not in ('https', 'http'):
            raise ValueError()
        # HTTP is restricted to local development. Never silently downgrade TLS.
        if parsed.scheme == 'http' and host not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError()
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
        if not 1 <= port <= 65535: raise ValueError()
        shown = '[' + host + ']' if ':' in host else host
        suffix = '' if port == (443 if parsed.scheme == 'https' else 80) else ':' + str(port)
        return parsed.scheme + '://' + shown + suffix
    except (ValueError, UnicodeError):
        raise BrowserError('Autofill requires an exact HTTPS website match. Local development addresses are also supported.') from None


def request_origin(data):
    site = origin(data.get('url'))
    if data.get('submitUrl') and origin(data['submitUrl']) != site:
        raise BrowserError('The form submits to a different website. Autofill was blocked.')
    return site


def entry_id(key):
    return hashlib.sha256((PERSONAL_FOLDER + '\0' + key).encode()).hexdigest()[:32]


class BrowserStore:
    def __init__(self, vault, prompt, screen_locked=lambda: True, identity=''):
        self.vault = vault
        self.prompt = prompt
        self.screen_locked = screen_locked
        self.identity = identity
        self.associated = None

    def guard(self):
        if self.screen_locked():
            raise BrowserError('The screen is locked. Unlock Monet to use saved passwords.', 1)
        self.vault.check()

    def open(self, trigger_unlock=False):
        if self.screen_locked():
            raise BrowserError('The screen is locked.', 1)
        transport = self.vault.transport
        wallet = str(self.vault.call('localWallet'))
        if hasattr(transport, 'wallet_locked'):
            locked = transport.wallet_locked(wallet)
            if locked is not False and not trigger_unlock:
                raise BrowserError('Open Monet Passwords and unlock your vault.', 1)
        try:
            self.guard()
        except VaultError:
            self.vault.unlock(wallet, listing=False)
        self.guard()
        return hashlib.sha256((self.identity + '\0' + wallet).encode()).hexdigest()

    def connection(self, identifier):
        self.guard()
        if not isinstance(identifier, str) or len(identifier) > 100:
            raise BrowserError('This browser is not connected.', 10)
        if not self.vault.call('hasEntry', self.vault.handle, CONNECTIONS, identifier, self.vault.app_id):
            raise BrowserError('This browser connection has been revoked. Connect it again in Monet Passwords.', 10)
        try:
            return unpack_map(self.vault.call('readMap', self.vault.handle, CONNECTIONS, identifier, self.vault.app_id))
        except (ValueError, UnicodeError):
            raise BrowserError('This browser connection could not be read.', 10) from None

    def put_connection(self, identifier, fields):
        self.guard()
        if not self.vault.call('hasFolder', self.vault.handle, CONNECTIONS, self.vault.app_id):
            if not self.vault.call('createFolder', self.vault.handle, CONNECTIONS, self.vault.app_id):
                raise BrowserError('The browser connection could not be saved.')
        if int(self.vault.call('writeMap', self.vault.handle, CONNECTIONS, identifier, pack_map(fields), self.vault.app_id)) != 0:
            raise BrowserError('The browser connection could not be saved.')
        if self.connection(identifier) != fields:
            raise BrowserError('The browser connection could not be verified.')

    def associate(self, data, client_key):
        self.guard()
        if data.get('key') != client_key:
            raise BrowserError('The browser key changed. Connect again.', 10)
        key = data.get('idKey', '')
        try:
            if len(base64.b64decode(key, validate=True)) != 32: raise ValueError()
        except (ValueError, TypeError):
            raise BrowserError('Invalid browser identification key.', 10) from None
        answer = self.prompt({'kind': 'connect'})
        self.guard()
        if not answer.get('approved'):
            raise BrowserError('Browser connection cancelled.', 6)
        label = answer.get('name', 'Zen')
        if not readable(label) or not 1 <= len(label.strip()) <= 60:
            label = 'Zen'
        identifier = 'Monet-' + secrets.token_hex(12)
        self.put_connection(identifier, {'Name': label.strip(), 'Key': key, 'Sites': '[]'})
        self.associated = (identifier, key)
        return identifier

    def authenticate(self, identifier, key):
        fields = self.connection(identifier)
        try:
            expected = base64.b64decode(fields.get('Key', ''), validate=True)
            provided = base64.b64decode(key, validate=True) if isinstance(key, str) else b''
        except (ValueError, TypeError):
            expected, provided = b'', b''
        if len(expected) != 32 or len(provided) != 32 or not secrets.compare_digest(expected, provided):
            raise BrowserError('This browser is not authorized.', 10)
        self.associated = (identifier, key)
        return fields

    def authorized(self, data):
        if not self.associated or data.get('id') != self.associated[0]:
            raise BrowserError('Connect this browser before using passwords.', 10)
        return self.authenticate(*self.associated)

    def accounts(self, site):
        self.guard()
        entries = []
        keys = dict.fromkeys(self.vault.call('entryList', self.vault.handle, PERSONAL_FOLDER, self.vault.app_id))
        # Only Monet-owned account records are eligible, never app keys/network data.
        for key in keys:
            entry = self.vault.read(PERSONAL_FOLDER, str(key))
            try:
                if origin(entry['fields'].get('Website', '')) != site: continue
            except BrowserError:
                continue
            if entry['fields'].get('Password'):
                entries.append(entry)
            if len(entries) > MAX_MATCHES:
                raise BrowserError('Too many matching logins. Open Monet Passwords to choose an account.')
        self.guard()
        return entries

    def logins(self, data):
        fields = self.authorized(data)
        site = request_origin(data)
        entries = self.accounts(site)
        if not entries: return []
        try: sites = json.loads(fields.get('Sites', '[]'))
        except ValueError: sites = []
        if not isinstance(sites, list) or any(not isinstance(s, str) for s in sites): sites = []
        if site not in sites:
            answer = self.prompt({'kind': 'fill', 'site': site, 'count': len(entries)})
            self.guard()
            # Revocation while the prompt was open must win.
            current = self.authorized(data)
            if current != fields:
                raise BrowserError('Browser permissions changed. Try again.')
            if not answer.get('approved'):
                return []
            if answer.get('remember') and len(sites) < 1000:
                self.put_connection(self.associated[0], dict(fields, Sites=json.dumps(sites + [site])))
            # Refresh after approval; stale credentials must not be sent.
            entries = self.accounts(site)
        self.guard()
        return [{'login': e['fields'].get('Username', ''), 'password': e['fields']['Password'],
                 'name': e['key'], 'uuid': entry_id(e['key']), 'group': 'Monet Logins',
                 'expired': 'false'} for e in entries]

    def save(self, data):
        fields = self.authorized(data)
        site = request_origin(data)
        username, password = data.get('login', ''), data.get('password', '')
        if not readable(username) or not readable(password) or not password:
            raise BrowserError('Enter a valid username and password.')
        entries = self.accounts(site)
        requested = data.get('uuid')
        matches = [e for e in entries if entry_id(e['key']) == requested] if requested else [e for e in entries if e['fields'].get('Username', '') == username]
        if requested and not matches:
            raise BrowserError('The selected login does not belong to this website.')
        if len(matches) > 1:
            raise BrowserError('More than one login matches. Choose the account to update in the browser.')
        before = matches[0] if matches else None
        if before and before['fields'].get('Username', '') == username and before['fields']['Password'] == password:
            return {'error': 'success', 'unchanged': True}
        answer = self.prompt({'kind': 'update' if before else 'save', 'site': site, 'username': username})
        self.guard(); self.authorized(data)
        if not answer.get('approved'):
            raise BrowserError('Saving cancelled. Your saved login was not changed.', 6)
        if before:
            # Optimistic concurrency check covers changes made while consent is open.
            self.vault.selected = before
            values = dict(before['fields'], Username=username, Password=password)
            self.vault.save(values)
        else:
            # Do not create a duplicate if another window saved while this prompt was open.
            if any(e['fields'].get('Username', '') == username for e in self.accounts(site)):
                raise BrowserError('This login was saved elsewhere. Refresh before trying again.')
            title = site.split('://', 1)[1][:100] + (' — ' + ' '.join(username.split())[:70] if username else '')
            original, suffix = title, 1
            while self.vault.call('hasEntry', self.vault.handle, PERSONAL_FOLDER, title, self.vault.app_id):
                suffix += 1
                if suffix > 10000: raise BrowserError('Too many logins with the same title.')
                title = original + ' (' + str(suffix) + ')'
            self.vault.add(title, username, password, site, '')
        # The user explicitly approved saving this site for this connection.
        current = self.authorized(data)
        try: sites = json.loads(current.get('Sites', '[]'))
        except ValueError: sites = []
        if isinstance(sites, list) and site not in sites and len(sites) < 1000:
            self.put_connection(self.associated[0], dict(current, Sites=json.dumps(sites + [site])))
        self.vault.selected = None
        return {'error': 'success'}
