"""A private-bus KWallet protocol fixture. Never run on a desktop session bus."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
sys.path.insert(0, str(ROOT))
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from tests.test_native_passwords import FakeWallet
assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'
DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
assert not bus.name_has_owner('org.kde.kwalletd6') and not bus.name_has_owner('org.freedesktop.secrets'), 'Refuse a real desktop vault bus'
name = dbus.service.BusName('org.kde.kwalletd6', bus)
secret_name = dbus.service.BusName('org.freedesktop.secrets', bus)
screen_name = dbus.service.BusName('org.freedesktop.ScreenSaver', bus)
class Screen(dbus.service.Object):
    def __init__(self): super().__init__(bus, '/ScreenSaver'); self.active = False
    @dbus.service.method('org.freedesktop.ScreenSaver', out_signature='b')
    def GetActive(self): return self.active
    @dbus.service.signal('org.freedesktop.ScreenSaver', signature='b')
    def ActiveChanged(self, active): pass
    @dbus.service.method('org.monet.Test', in_signature='b')
    def SetActive(self, active): self.active = bool(active); self.ActiveChanged(active)
screen = Screen()
collection_path = '/org/freedesktop/secrets/collection/fixture'
class Collection(dbus.service.Object):
    def __init__(self, path=collection_path):
        super().__init__(bus, path); self.locked = False
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        return dbus.String('fixture') if prop == 'Label' else dbus.Boolean(self.locked)
    @dbus.service.signal('org.freedesktop.DBus.Properties', signature='sa{sv}as')
    def PropertiesChanged(self, interface, changes, invalidated): pass
class SecretService(dbus.service.Object):
    def __init__(self): super().__init__(bus, '/org/freedesktop/secrets')
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
    def Get(self, interface, prop): return dbus.Array([dbus.ObjectPath(collection_path)], signature='o')
    @dbus.service.method('org.freedesktop.Secret.Service', in_signature='ao', out_signature='aoo')
    def Lock(self, paths):
        assert list(paths) == [collection_path]
        collection.locked = True
        collection.PropertiesChanged('org.freedesktop.Secret.Collection', {'Locked': dbus.Boolean(True)}, [])
        return paths, dbus.ObjectPath('/')
collection = Collection(); secret_service = SecretService()
other_collection = Collection('/org/freedesktop/secrets/collection/other')
api = 'org.kde.KWallet'
class Service(dbus.service.Object):
    def __init__(self):
        super().__init__(bus, '/modules/kwalletd6'); self.data = FakeWallet()
    @dbus.service.method(api, out_signature='as')
    def wallets(self): return ['fixture']
    @dbus.service.method(api, out_signature='s')
    def localWallet(self): return 'fixture'
    @dbus.service.method(api)
    def emitOtherLock(self):
        other_collection.PropertiesChanged('org.freedesktop.Secret.Collection', {'Locked': dbus.Boolean(True)}, [])
    @dbus.service.method(api, in_signature='sxs', out_signature='i')
    def open(self, wallet, window, app):
        assert int(window) == 0 and app in ('Monet Passwords', 'Monet Passwords for Zen')
        collection.locked = False
        collection.PropertiesChanged('org.freedesktop.Secret.Collection', {'Locked': dbus.Boolean(False)}, [])
        return self.data.call('open', wallet, window, app)
    @dbus.service.method(api, in_signature='i', out_signature='b')
    def isOpen(self, handle): return self.data.call('isOpen', handle)
    @dbus.service.method(api, in_signature='is', out_signature='as')
    def folderList(self, handle, app): return self.data.call('folderList', handle, app)
    @dbus.service.method(api, in_signature='iss', out_signature='as')
    def entryList(self, handle, folder, app): return self.data.call('entryList', handle, folder, app)
    @dbus.service.method(api, in_signature='isss', out_signature='b')
    def hasEntry(self, handle, folder, key, app): return self.data.call('hasEntry', handle, folder, key, app)
    @dbus.service.method(api, in_signature='iss', out_signature='b')
    def hasFolder(self, handle, folder, app): return self.data.call('hasFolder', handle, folder, app)
    @dbus.service.method(api, in_signature='iss', out_signature='b')
    def createFolder(self, handle, folder, app): return True
    @dbus.service.method(api, in_signature='isss', out_signature='i')
    def entryType(self, handle, folder, key, app): return self.data.call('entryType', handle, folder, key, app)
    @dbus.service.method(api, in_signature='isss', out_signature='s')
    def readPassword(self, handle, folder, key, app): return self.data.call('readPassword', handle, folder, key, app)
    @dbus.service.method(api, in_signature='isss', out_signature='ay')
    def readMap(self, handle, folder, key, app): return dbus.ByteArray(self.data.call('readMap', handle, folder, key, app))
    @dbus.service.method(api, in_signature='isss', out_signature='ay')
    def readEntry(self, handle, folder, key, app): return dbus.ByteArray(self.data.call('readEntry', handle, folder, key, app))
    @dbus.service.method(api, in_signature='issss', out_signature='i')
    def writePassword(self, handle, folder, key, value, app): return self.data.call('writePassword', handle, folder, key, value, app)
    @dbus.service.method(api, in_signature='issays', out_signature='i')
    def writeMap(self, handle, folder, key, value, app):
        result = self.data.call('writeMap', handle, folder, key, bytes(value), app)
        self.folderUpdated('fixture', folder)
        return result
    @dbus.service.signal(api, signature='ss')
    def folderUpdated(self, wallet, folder): pass
    @dbus.service.method(api, in_signature='isss', out_signature='i')
    def removeEntry(self, handle, folder, key, app):
        result = self.data.call('removeEntry', handle, folder, key, app)
        self.folderUpdated('fixture', folder)
        return result
    @dbus.service.method(api, in_signature='sb', out_signature='i')
    def close(self, wallet, force): return self.data.call('close', wallet, force)
    @dbus.service.method(api, in_signature='s', out_signature='as')
    def users(self, wallet): return self.data.call('users', wallet)
    @dbus.service.method(api, in_signature='ss', out_signature='b')
    def disconnectApplication(self, wallet, app):
        self.data.call('disconnectApplication', wallet, app)
        self.walletClosed(wallet)
        return False  # Installed KDE 6.31 returns false after a successful disconnect.
    @dbus.service.signal(api, signature='s')
    def walletClosed(self, name): pass
    @dbus.service.method(api, in_signature='s')
    def emitClose(self, name):
        self.data.opened = False
        self.walletClosed(name)
service = Service()
print('ready', flush=True)
GLib.MainLoop().run()
