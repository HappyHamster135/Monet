"""On-demand native messaging host. Passwords stay off argv, disk and logs."""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import threading

from browser_protocol import Protocol, BrowserError, read_message, write_message
from browser_store import BrowserStore
from vault import NativeWallet, Vault

EXTENSION = 'keepassxc-browser@keepassxc.org'


class LockWatcher:
    def __init__(self, notify):
        self.collection_path = None
        self.vault_blocked = threading.Event()
        self.blocked = threading.Event()
        self.blocked.set()  # Fail closed until both service and screen state were checked.
        self.notify = notify
        self.loop = None
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def watch(self):
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            bus = dbus.SessionBus(private=True, mainloop=DBusGMainLoop())
            def owner_changed(name, old, new):
                if str(name) in ('org.freedesktop.ScreenSaver', 'org.freedesktop.secrets', 'org.kde.kwalletd6') and old and old != new:
                    self.blocked.set()
                    self.notify({'action': 'database-locked'})
            bus.add_signal_receiver(owner_changed, signal_name='NameOwnerChanged',
                dbus_interface='org.freedesktop.DBus', bus_name='org.freedesktop.DBus')
            def active(value):
                if value: self.blocked.set()
                else: self.blocked.clear()
                self.notify({'action': 'database-locked' if value else 'database-unlocked'})
            bus.add_signal_receiver(active, signal_name='ActiveChanged',
                dbus_interface='org.freedesktop.ScreenSaver', bus_name='org.freedesktop.ScreenSaver')
            def changed(interface, properties, _, path=None):
                if self.collection_path is not None and str(path) != self.collection_path:
                    return
                if str(interface) == 'org.freedesktop.Secret.Collection' and 'Locked' in properties:
                    if properties['Locked']: self.vault_blocked.set()
                    else: self.vault_blocked.clear()
                    self.notify({'action': 'database-locked' if properties['Locked'] else 'database-unlocked'})
            bus.add_signal_receiver(changed, signal_name='PropertiesChanged',
                dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.freedesktop.secrets', path_keyword='path')
            def contents(wallet, folder):
                if str(folder) in ('Monet Browser Connections', 'Monet Logins'):
                    # Clear the connector's cached credentials when editing or revoking.
                    self.notify({'action': 'database-locked'})
                    self.notify({'action': 'database-unlocked'})
            bus.add_signal_receiver(contents, signal_name='folderUpdated', dbus_interface='org.kde.KWallet', bus_name='org.kde.kwalletd6')
            obj = bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver', introspect=False)
            screen = dbus.Interface(obj, 'org.freedesktop.ScreenSaver')
            if not screen.GetActive(timeout=5): self.blocked.clear()
            self.loop = GLib.MainLoop(); self.loop.run(); bus.close()
        except Exception:
            self.blocked.set()  # No logging of exceptions from credential services.

    def close(self):
        if self.loop: self.loop.quit()


def confirmation(launcher, proposal):
    # Only metadata is sent to the separate consent window; never the password.
    try:
        result = subprocess.run([launcher, '--browser-prompt'], input=json.dumps(proposal).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90, check=True)
        answer = json.loads(result.stdout[:4096])
        return answer if isinstance(answer, dict) else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def main(launcher, factory=NativeWallet):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Firefox supplies manifest path and initiating add-on ID. A shell invocation
    # without the expected ID is not a browser connection.
    if len(sys.argv) < 3 or sys.argv[-1] != EXTENSION:
        return 1
    write_lock = threading.Lock()
    transport = None
    vault = None
    def notify(message):
        try:
            with write_lock: write_message(sys.stdout.buffer, message)
        except (BrokenPipeError, OSError): pass
    watcher = LockWatcher(notify)
    try:
        transport = factory()
        vault = Vault(transport, app_id='Monet Passwords for Zen')
        default_wallet = str(transport.call('localWallet'))
        watcher.collection_path = transport.collection(default_wallet)
        if transport.wallet_locked(default_wallet) is False: watcher.vault_blocked.clear()
        else: watcher.vault_blocked.set()
        # Local database identity only, not an authentication key.
        machine = Path('/etc/machine-id').read_text().strip()
        def screen_locked():
            if watcher.blocked.is_set(): return True
            try:
                obj = transport.bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver', introspect=False)
                return bool(transport.dbus.Interface(obj, 'org.freedesktop.ScreenSaver').GetActive(timeout=3))
            except Exception: return True
        store = BrowserStore(vault, lambda p: confirmation(launcher, p), screen_locked,
                             identity=machine + ':' + str(os.getuid()))
        protocol = Protocol(store)
        while True:
            request = read_message(sys.stdin.buffer)
            if request is None: break
            try: reply = protocol.handle(request)
            except Exception: reply = protocol.error(request.get('action', ''), 'Monet Passwords could not complete this request.', 8)
            with write_lock:
                if (watcher.blocked.is_set() or watcher.vault_blocked.is_set()) and request.get('action') != 'change-public-keys':
                    reply = protocol.error(request.get('action', ''), 'The screen is locked.', 1)
                write_message(sys.stdout.buffer, reply)
    except Exception:
        # Startup/provider/framing failures must not dump exception arguments.
        return 1
    finally:
        watcher.close()
        if transport:
            try:
                if vault: vault.release()
            except Exception: pass
            try: transport.close_connection()
            except Exception: pass
    return 0
