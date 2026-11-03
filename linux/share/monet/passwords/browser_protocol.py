"""KeePassXC-Browser's documented NaCl protocol, backed by the PyNaCl library.

No custom cipher or key derivation. Native framing is bounded; errors never
include provider exceptions, credentials, ciphertext or keys.
"""
import base64
import json
import secrets
import struct
from nacl.public import Box, PrivateKey, PublicKey
from nacl.exceptions import CryptoError
from browser_store import BrowserError
from vault import VaultError

VERSION = '2.7.0'  # Supported connector protocol capabilities, not Monet's version.
MAX_MESSAGE = 256 * 1024


def decode(value, size=None):
    if not isinstance(value, str) or len(value) > MAX_MESSAGE:
        raise BrowserError('Invalid browser message.', 4)
    try: raw = base64.b64decode(value, validate=True)
    except ValueError: raise BrowserError('Invalid browser message.', 4) from None
    if size is not None and len(raw) != size:
        raise BrowserError('Invalid browser message size.', 4)
    return raw


def b64(value): return base64.b64encode(value).decode('ascii')


def increment(nonce):
    return ((int.from_bytes(nonce, 'little') + 1) % (1 << 192)).to_bytes(24, 'little')


def read_message(stream):
    prefix = stream.read(4)
    if not prefix: return None
    if len(prefix) != 4: raise BrowserError('Incomplete native message.', 4)
    size = struct.unpack('@I', prefix)[0]
    if not 1 <= size <= MAX_MESSAGE: raise BrowserError('Native message exceeds the limit.', 4)
    raw = bytearray()
    while len(raw) < size:
        chunk = stream.read(size - len(raw))
        if not chunk: raise BrowserError('Incomplete native message.', 4)
        raw.extend(chunk)
    try: message = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError): raise BrowserError('Invalid native message.', 4) from None
    if not isinstance(message, dict): raise BrowserError('Invalid native message.', 4)
    return message


def write_message(stream, message):
    data = json.dumps(message, separators=(',', ':'), ensure_ascii=True).encode()
    if len(data) > MAX_MESSAGE: raise BrowserError('Too many matching accounts.', 4)
    stream.write(struct.pack('@I', len(data)) + data); stream.flush()


class Protocol:
    def __init__(self, store):
        self.store = store
        self.box = None
        self.client_id = None
        self.client_key = None
        self.seen = set()

    def error(self, action, text, code):
        return {'action': action, 'error': text, 'errorCode': code}

    def handle(self, request):
        action = request.get('action', '')
        if not isinstance(action, str) or len(action) > 64:
            return self.error('', 'Invalid action.', 12)
        try:
            nonce = decode(request.get('nonce'), 24)
            reply_nonce = increment(nonce)
            if action == 'change-public-keys':
                client_key = decode(request.get('publicKey'), 32)
                client_id = request.get('clientID')
                decode(client_id, 24)
                private = PrivateKey.generate()
                self.box = Box(private, PublicKey(client_key))
                self.client_key, self.client_id = b64(client_key), client_id
                self.seen = {nonce, reply_nonce}
                self.store.associated = None
                return {'action': action, 'version': VERSION, 'success': 'true',
                        'publicKey': b64(bytes(private.public_key)), 'nonce': b64(reply_nonce)}
            if self.box is None or request.get('clientID') != self.client_id:
                raise BrowserError('Connect this browser again.', 10)
            if nonce in self.seen or reply_nonce in self.seen or len(self.seen) > 32768:
                raise BrowserError('Browser nonce was reused. Reconnect the browser.', 4)
            self.seen.update((nonce, reply_nonce))
            if action == 'generate-password' and 'message' not in request:
                data = {'action': action}
            else:
                data = json.loads(self.box.decrypt(decode(request.get('message')), nonce))
                if not isinstance(data, dict) or data.get('action') != action:
                    raise BrowserError('Browser action mismatch.', 4)
            db_hash = self.store.open(request.get('triggerUnlock') is True)
            result = {'hash': db_hash, 'monet': {'nativeConsent': True}}
            if action == 'get-databasehash':
                pass
            elif action == 'associate':
                result['id'] = self.store.associate(data, self.client_key)
            elif action == 'test-associate':
                self.store.authenticate(data.get('id'), data.get('key'))
                result['id'] = data['id']
            elif action == 'get-logins':
                self.store.authorized(data)
                # The identity token must also accompany this site's lookup.
                if not any(isinstance(k, dict) and k.get('id') == self.store.associated[0]
                           and isinstance(k.get('key'), str)
                           and secrets.compare_digest(k['key'].encode(), self.store.associated[1].encode())
                           for k in data.get('keys', [])[:100]):
                    raise BrowserError('Browser identity was not provided.', 10)
                result['entries'] = self.store.logins(data)
                result['count'] = str(len(result['entries']))
            elif action == 'set-login':
                result.update(self.store.save(data))
            elif action in ('get-database-groups', 'generate-password', 'lock-database'):
                self.store.authorized({'id': self.store.associated[0] if self.store.associated else None})
                if action == 'generate-password': result['password'] = secrets.token_urlsafe(24)
                elif action == 'get-database-groups':
                    result.update(defaultGroup='Monet Logins', defaultGroupAlwaysAllow=True,
                                  groups=[{'name': 'Monet Logins', 'uuid': '0' * 32, 'children': []}])
                else:
                    self.store.vault.lock()
                    return self.error(action, 'Vault locked.', 1)
            else:
                raise BrowserError('This browser feature is not supported by Monet Passwords.', 12)
            self.store.guard()
            result.update(success='true', nonce=b64(reply_nonce), version=VERSION)
            encrypted = self.box.encrypt(json.dumps(result, separators=(',', ':')).encode(), reply_nonce).ciphertext
            return {'action': action, 'message': b64(encrypted), 'nonce': b64(reply_nonce)}
        except BrowserError as error:
            return self.error(action, str(error), error.code)
        except VaultError:
            return self.error(action, 'The vault is locked or the entry changed. Open Monet Passwords and try again.', 1)
        except (CryptoError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return self.error(action, 'Invalid or unauthenticated browser message.', 4)
