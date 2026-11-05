"""Monet's view of the system vault. No secret files, shell commands or logging.

The desktop's existing KWallet/Secret Service owns encryption and unlock prompts.
Only the selected entry is read; lists contain metadata, never bulk secret dumps.
"""
import hashlib
import json
import re
import secrets
import struct
from threading import Event

APP_ID = 'Monet Passwords'
PERSONAL_FOLDER = 'Monet Logins'
MAX_BYTES = 1024 * 1024
MAX_FIELDS = 128
MAX_TEXT = 65536
N_ = lambda text: text  # Extract UI explanations; translate them in the view.


class VaultError(Exception):
    """A message safe to show; never include a provider exception or a secret."""


def readable(value):
    return isinstance(value, str) and len(value) <= MAX_TEXT and all(
        ord(c) >= 32 or c in '\n\r\t' for c in value)


def unpack_map(raw):
    """Bounded QDataStream QMap<QString,QString>, used by KWallet readMap."""
    raw = bytes(raw)
    if len(raw) > MAX_BYTES or len(raw) < 4:
        raise ValueError('Invalid map')
    offset = 4
    count = struct.unpack_from('>I', raw)[0]
    if count > MAX_FIELDS:
        raise ValueError('Too many fields')
    result = {}
    def string():
        nonlocal offset
        if offset + 4 > len(raw):
            raise ValueError('Incomplete map')
        size = struct.unpack_from('>I', raw, offset)[0]; offset += 4
        if size == 0xffffffff:
            return ''
        if size > MAX_TEXT * 2 or size % 2 or offset + size > len(raw):
            raise ValueError('Invalid string')
        value = raw[offset:offset + size].decode('utf-16-be'); offset += size
        if not readable(value):
            raise ValueError('Non-text field')
        return value
    for _ in range(count):
        key, value = string(), string()
        if key in result or not key:
            raise ValueError('Invalid field name')
        result[key] = value
    if offset != len(raw):
        raise ValueError('Trailing data')
    return result


def pack_map(values):
    if not isinstance(values, dict) or len(values) > MAX_FIELDS:
        raise VaultError('Too many fields to save.')
    parts = [struct.pack('>I', len(values))]
    for key, value in sorted(values.items()):
        if not key or not readable(key) or not readable(value):
            raise VaultError('This entry contains an unsupported field.')
        for text in (key, value):
            encoded = text.encode('utf-16-be')
            parts += [struct.pack('>I', len(encoded)), encoded]
    raw = b''.join(parts)
    if len(raw) > MAX_BYTES:
        raise VaultError('This entry is too large to save.')
    return raw


def decode_stream(raw):
    """Known text encodings only. Binary keys are never guessed or shown as hex."""
    raw = bytes(raw)
    if len(raw) > MAX_BYTES:
        return {}, N_('This app entry is too large to display.')
    try:
        return unpack_map(raw), N_('Saved fields from this app. Edit them in the app that created them.')
    except (ValueError, UnicodeError, struct.error):
        pass
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        text = None
    if text is not None and readable(text):
        try:
            value = json.loads(text)
        except (ValueError, RecursionError):
            value = None
        if isinstance(value, dict):
            fields = {}
            def flatten(node, prefix='', depth=0):
                if depth > 3:
                    raise ValueError('Too deeply nested')
                for key, item in node.items():
                    label = f'{prefix} / {key}' if prefix else key
                    if not readable(label) or not label or len(fields) >= MAX_FIELDS:
                        raise ValueError('Invalid fields')
                    if isinstance(item, dict):
                        flatten(item, label, depth + 1)
                    elif readable(item):
                        fields[label] = item
                    else:
                        raise ValueError('Not text')
            try:
                flatten(value)
                return fields, N_('Saved app fields. Edit them in the app that created them.')
            except ValueError:
                return {}, N_('This entry contains structured app data, not a readable login.')
        # Do not mislabel structured arrays/objects with non-text fields as passwords.
        if value is None or isinstance(value, str):
            return {'Secret': text if value is None else value}, N_('Saved text used by this app.')
    return {}, N_('App-managed binary data. This may be an encryption key, not a password. Manage it in the app that created it.')


def category(folder):
    if folder in (PERSONAL_FOLDER, 'Monet App Logins'):
        return 'Logins'
    if any(word in folder.casefold() for word in ('network', 'wifi', 'wireless', '802-11', 'vpn')):
        return 'Network'
    return 'Apps'


def internal_entry(folder, key):
    """Identify infrastructure by metadata, never by inspecting its secret."""
    if folder == 'Monet Browser Connections':
        return N_('Browser authorization data. Manage or revoke this connection in Connected apps; this is not a website password.')
    if folder.casefold() == 'xdg-desktop-portal':
        return N_('An app encryption key supplied by the desktop portal. This is not a website login. The app manages this key automatically.')
    if key.casefold().endswith(' safe storage') or folder.casefold().endswith(' keys'):
        return N_('A browser encryption key, not a saved login. Your website passwords are managed inside the browser. Leave this key in place so the browser can read its data.')
    return ''


def entry_title(folder, key):
    if folder == 'Monet App Logins':
        return re.sub(r' \[(?:[a-f0-9]{64}:)?[a-f0-9]{64}\]$', '', key)
    if folder.casefold() == 'xdg-desktop-portal' and key == 'app.zen_browser.zen':
        return 'Zen Browser'
    if key.endswith(' Safe Storage'):
        return key.removesuffix(' Safe Storage')
    return key


def display_label(key):
    labels = {'psk': 'Wi-Fi password', 'password': 'Password', 'passwd': 'Password',
              'username': 'Username', 'user': 'Username', 'url': 'Website', 'notes': 'Notes',
              'private-key-password': 'Private key password', 'pin': 'PIN'}
    return labels.get(key.casefold(), key)


def friendly_title(folder, key, networks):
    if category(folder) != 'Network':
        return key
    match = re.search(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', key)
    if match and match[0].lower() in networks:
        return networks[match[0].lower()]
    return key


class NativeWallet:
    """Used only on the worker thread. dbus-python keeps Int64/byte arrays exact."""
    def __init__(self):
        import dbus
        self.dbus = dbus
        self.bus = dbus.SessionBus(private=True)
        self.object = self.bus.get_object('org.kde.kwalletd6', '/modules/kwalletd6', introspect=False)
        self.interface = dbus.Interface(self.object, 'org.kde.KWallet')
        self.collections = {}

    def call(self, method, *args):
        if method in ('open', 'changePassword'):
            args = (args[0], self.dbus.Int64(args[1]), *args[2:])
        if method == 'writeMap':
            args = (*args[:3], self.dbus.ByteArray(args[3]), *args[4:])
        try:
            return getattr(self.interface, method)(*args, timeout=120 if method == 'open' else 10)
        except self.dbus.DBusException:
            raise VaultError('The vault did not respond or access was denied. Unlock it and try again.') from None

    def close_connection(self):
        self.bus.close()

    def collection(self, wallet):
        if not self.bus.name_has_owner('org.freedesktop.secrets'):
            return None
        if wallet not in self.collections:
            service = self.bus.get_object('org.freedesktop.secrets', '/org/freedesktop/secrets', introspect=False)
            paths = self.dbus.Interface(service, 'org.freedesktop.DBus.Properties').Get(
                'org.freedesktop.Secret.Service', 'Collections', timeout=5)
            matches = []
            for path in paths:
                obj = self.bus.get_object('org.freedesktop.secrets', path, introspect=False)
                props = self.dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
                if str(props.Get('org.freedesktop.Secret.Collection', 'Label', timeout=5)) == wallet:
                    matches.append(str(path))
            if len(matches) != 1:
                raise VaultError('The encrypted vault could not be identified safely.')
            self.collections[wallet] = matches[0]
        return self.collections[wallet]

    def wallet_locked(self, wallet):
        path = self.collection(wallet)
        if path is None:
            return None
        obj = self.bus.get_object('org.freedesktop.secrets', path, introspect=False)
        return bool(self.dbus.Interface(obj, 'org.freedesktop.DBus.Properties').Get(
            'org.freedesktop.Secret.Collection', 'Locked', timeout=5))

    def lock_wallet(self, wallet):
        # KWallet 6.31 close() drops compatibility handles without locking the
        # encrypted Secret Service collection. Lock and verify the real provider.
        path = self.collection(wallet)
        if path is None:
            raise VaultError('The encrypted storage service is unavailable. Locking was not confirmed.')
        obj = self.bus.get_object('org.freedesktop.secrets', '/org/freedesktop/secrets', introspect=False)
        service = self.dbus.Interface(obj, 'org.freedesktop.Secret.Service')
        _locked, prompt = service.Lock(self.dbus.Array([self.dbus.ObjectPath(path)], signature='o'), timeout=10)
        if str(prompt) != '/' or self.wallet_locked(wallet) is not True:
            raise VaultError('The encrypted vault did not confirm locking. The password view has been cleared.')
        self.call('close', wallet, True)

    def connection_names(self):
        """Profile names only. Never request NetworkManager GetSecrets."""
        system = None
        try:
            system = self.dbus.SystemBus(private=True)
            settings = self.dbus.Interface(system.get_object('org.freedesktop.NetworkManager',
                '/org/freedesktop/NetworkManager/Settings', introspect=False),
                'org.freedesktop.NetworkManager.Settings')
            names = {}
            for path in settings.ListConnections(timeout=3)[:256]:
                connection = self.dbus.Interface(system.get_object('org.freedesktop.NetworkManager', path, introspect=False),
                                                'org.freedesktop.NetworkManager.Settings.Connection')
                profile = connection.GetSettings(timeout=3).get('connection', {})
                if profile.get('uuid') and profile.get('id'):
                    names[str(profile['uuid']).lower()] = str(profile['id'])
            return names
        except self.dbus.DBusException:
            return {}
        finally:
            if system:
                system.close()


class Vault:
    def __init__(self, transport, app_id=APP_ID):
        self.transport = transport
        self.app_id = app_id
        self.handle = -1
        self.wallet = ''
        self.selected = None
        self.pending_import = []
        self.import_cancelled = Event()

    def call(self, method, *args):
        return self.transport.call(method, *args)

    def available(self):
        return {'wallets': [str(x) for x in self.call('wallets')], 'default': str(self.call('localWallet'))}

    def unlock(self, wallet, listing=True):
        if wallet not in [str(x) for x in self.call('wallets')]:
            raise VaultError('Choose an existing vault. Create a vault in desktop vault settings first.')
        handle = int(self.call('open', wallet, 0, self.app_id))
        if handle < 0:
            raise VaultError('The vault was not unlocked. You can try again.')
        self.handle, self.wallet, self.selected = handle, wallet, None
        return self.list_entries() if listing else None

    def check(self):
        if (self.handle < 0 or not self.call('isOpen', self.handle)
                or (hasattr(self.transport, 'wallet_locked') and self.transport.wallet_locked(self.wallet) is True)):
            self.forget()
            raise VaultError('The vault is locked. Unlock it to continue.')

    def forget(self):
        self.handle, self.wallet, self.selected = -1, '', None
        self.pending_import.clear()
        self.import_cancelled.set()

    def release(self):
        wallet = self.wallet
        self.forget()
        if wallet:
            try:
                self.call('disconnectApplication', wallet, self.app_id)
            except VaultError:
                pass  # Local values are cleared even if the provider disappeared.

    def list_entries(self):
        self.check()
        rows = []
        for folder in dict.fromkeys(self.call('folderList', self.handle, self.app_id)):
            folder = str(folder)
            if folder == 'Monet Browser Connections':
                continue  # Authorization material belongs only in connection management.
            for key in dict.fromkeys(self.call('entryList', self.handle, folder, self.app_id)):
                key = str(key)
                rows.append({'folder': folder, 'key': key, 'title': entry_title(folder, key),
                             'category': category(folder), 'internal': bool(internal_entry(folder, key))})
        if any(row['category'] == 'Network' for row in rows) and hasattr(self.transport, 'connection_names'):
            names = self.transport.connection_names()
            for row in rows:
                row['title'] = friendly_title(row['folder'], row['key'], names)
        return sorted(rows, key=lambda r: (r['title'].casefold(), r['folder'].casefold()))

    def read(self, folder, key):
        self.check()
        if not self.call('hasEntry', self.handle, folder, key, self.app_id):
            raise VaultError('This entry no longer exists. Refresh the list.')
        note = internal_entry(folder, key)
        if note:
            return {'folder': folder, 'key': key, 'kind': 0, 'fields': {}, 'note': note,
                    'editable': False, 'signature': b'', 'internal': True}
        kind = int(self.call('entryType', self.handle, folder, key, self.app_id))
        if kind == 2:
            value = str(self.call('readPassword', self.handle, folder, key, self.app_id))
            if not readable(value):
                raise VaultError('This password is too large or is not readable text.')
            raw, fields, note = value.encode('utf-8'), {'Password': value}, ''
        elif kind == 3:
            raw = bytes(self.call('readMap', self.handle, folder, key, self.app_id))
            try:
                fields = unpack_map(raw)
            except (ValueError, UnicodeError, struct.error):
                raise VaultError('This app uses an unsupported field format. Its saved data has been left untouched.') from None
            note = ''
        elif kind == 1:
            raw = bytes(self.call('readEntry', self.handle, folder, key, self.app_id))
            fields, note = decode_stream(raw)
        else:
            raise VaultError('This entry has an unsupported type. Its saved data has been left untouched.')
        # A close during the read must not turn an empty/failed response into a valid password.
        self.check()
        signature = hashlib.sha256(bytes([kind]) + raw).digest()
        return {'folder': folder, 'key': key, 'kind': kind, 'fields': fields, 'note': note,
                'editable': kind in (2, 3), 'signature': signature}

    def select(self, folder, key):
        self.selected = self.read(folder, key)
        return self.selected.copy()

    def unchanged(self):
        if self.selected is None:
            raise VaultError('Select an entry first.')
        before = self.selected
        now = self.read(before['folder'], before['key'])
        if not secrets.compare_digest(now['signature'], before['signature']):
            raise VaultError('Another app changed this entry. Reopen it before editing or deleting.')
        return before

    def save(self, fields):
        before = self.unchanged()
        if not before['editable'] or set(fields) != set(before['fields']):
            raise VaultError('This entry cannot be changed here.')
        if before['kind'] == 2:
            value = fields['Password']
            if not readable(value):
                raise VaultError('This password is too large.')
            result = self.call('writePassword', self.handle, before['folder'], before['key'], value, self.app_id)
        else:
            result = self.call('writeMap', self.handle, before['folder'], before['key'], pack_map(fields), self.app_id)
        if int(result) != 0:
            raise VaultError('The vault could not save this entry. Your change was not confirmed.')
        saved = self.select(before['folder'], before['key'])
        if saved['fields'] != fields:
            raise VaultError('The saved values could not be verified. Reopen the entry before retrying.')
        return saved

    def prepare_import(self, path):
        from login_import import read_csv
        self.check()
        self.pending_import.clear()
        self.import_cancelled.clear()
        records, skipped = read_csv(path)
        self.check()
        self.pending_import = records
        return {'count': len(records), 'skipped': skipped}

    def cancel_import(self):
        self.pending_import.clear()
        return None

    def import_logins(self):
        """Explicit CSV import reads only Monet's own logins to avoid duplicates.

        Never overwrite existing records. Interrupted imports can be retried;
        verified entries already saved are skipped on the next attempt.
        """
        self.check()
        records, self.pending_import = self.pending_import, []
        existing = set()
        for key in dict.fromkeys(self.call('entryList', self.handle, PERSONAL_FOLDER, self.app_id)):
            if self.import_cancelled.is_set():
                return {'added': 0, 'skipped': 0, 'incomplete': True, 'rows': []}
            fields = self.read(PERSONAL_FOLDER, str(key))['fields']
            existing.add(tuple(fields.get(k, '') for k in ('Username', 'Password', 'Website', 'Notes')))
        added = skipped = 0
        incomplete = False
        try:
            for record in records:
                if self.import_cancelled.is_set():
                    incomplete = True
                    break
                identity = tuple(record[k] for k in ('username', 'password', 'website', 'notes'))
                if identity in existing:
                    skipped += 1
                    continue
                title = record['title']
                suffix = 1
                while self.call('hasEntry', self.handle, PERSONAL_FOLDER, title, self.app_id):
                    suffix += 1
                    if suffix > 10000:
                        raise VaultError('Too many logins have the same title.')
                    title = record['title'][:185] + ' (' + str(suffix) + ')'
                self.add(title, *identity)
                added += 1
                existing.add(identity)
        except VaultError:
            incomplete = True
        finally:
            records.clear(); existing.clear(); self.selected = None
        return {'added': added, 'skipped': skipped, 'incomplete': incomplete,
                'rows': self.list_entries() if not incomplete else []}

    def add(self, title, username, password, website, notes):
        self.check()
        title = title.strip()
        if not title or len(title) > 200 or not readable(title) or '\n' in title:
            raise VaultError('Enter a title between 1 and 200 characters.')
        if not password:
            raise VaultError('Enter or generate a password.')
        fields = {'Username': username, 'Password': password, 'Website': website, 'Notes': notes}
        raw = pack_map(fields)
        if not self.call('hasFolder', self.handle, PERSONAL_FOLDER, self.app_id):
            if not self.call('createFolder', self.handle, PERSONAL_FOLDER, self.app_id):
                raise VaultError('The vault could not create a place for your logins.')
        if self.call('hasEntry', self.handle, PERSONAL_FOLDER, title, self.app_id):
            raise VaultError('A login already has that title. Choose another title or edit the existing login.')
        if int(self.call('writeMap', self.handle, PERSONAL_FOLDER, title, raw, self.app_id)) != 0:
            raise VaultError('The vault could not save this login.')
        saved = self.select(PERSONAL_FOLDER, title)
        if saved['fields'] != fields:
            raise VaultError('The saved login could not be verified. Refresh before retrying.')
        return saved

    def delete(self):
        before = self.unchanged()
        if not before['editable']:
            raise VaultError('App-managed binary data cannot be deleted here. Manage it in the original app.')
        if int(self.call('removeEntry', self.handle, before['folder'], before['key'], self.app_id)) != 0:
            raise VaultError('The vault could not remove this entry.')
        if self.call('hasEntry', self.handle, before['folder'], before['key'], self.app_id):
            raise VaultError('The entry is still present. Refresh before retrying.')
        self.selected = None
        return self.list_entries()

    def apps(self):
        self.check()
        return sorted(str(x) for x in self.call('users', self.wallet) if str(x) != self.app_id)

    def browser_connections(self):
        self.check()
        folder = 'Monet Browser Connections'
        result = []
        for key in dict.fromkeys(self.call('entryList', self.handle, folder, self.app_id)):
            fields = unpack_map(self.call('readMap', self.handle, folder, str(key), self.app_id))
            try: sites = json.loads(fields.get('Sites', '[]'))
            except ValueError: sites = []
            result.append({'id': str(key), 'name': fields.get('Name', 'Zen'),
                           'sites': [s for s in sites if isinstance(s, str)] if isinstance(sites, list) else []})
        return result

    def connections(self):
        return {'apps': self.apps(), 'browsers': self.browser_connections()}

    def revoke_browser(self, identifier):
        self.check()
        if identifier not in [row['id'] for row in self.browser_connections()]:
            raise VaultError('This browser connection no longer exists.')
        folder = 'Monet Browser Connections'
        if int(self.call('removeEntry', self.handle, folder, identifier, self.app_id)) != 0 or self.call('hasEntry', self.handle, folder, identifier, self.app_id):
            raise VaultError('The browser connection could not be revoked.')
        return self.connections()

    def disconnect(self, app):
        if app not in self.apps():
            raise VaultError('This app is no longer connected.')
        self.call('disconnectApplication', self.wallet, app)
        remaining = self.apps()
        # The installed compatibility service returns false even after success.
        if app in remaining:
            raise VaultError('This connection could not be closed.')
        return remaining

    def lock(self):
        wallet = self.wallet
        self.forget()
        if wallet:
            self.transport.lock_wallet(wallet)
        return None
