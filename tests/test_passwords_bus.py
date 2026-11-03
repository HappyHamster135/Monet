"""Actual typed D-Bus calls, isolated from the desktop vault in dbus-run-session."""
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
from vault import NativeWallet, Vault

@unittest.skipUnless(os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1', 'requires isolated dbus-run-session')
class PasswordsBus(unittest.TestCase):
    def test_protocol_round_trip_and_signals(self):
        names = patch.object(NativeWallet, 'connection_names', return_value={})
        names.start(); self.addCleanup(names.stop)
        process = subprocess.Popen([sys.executable, str(ROOT/'tests/passwords_bus_fixture.py')],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(lambda: (process.terminate(), process.wait(timeout=5), process.stdout.close()))
        self.assertEqual(process.stdout.readline().strip(), 'ready')
        transport = NativeWallet(); self.addCleanup(transport.close_connection)
        vault = Vault(transport)
        self.assertEqual(vault.available()['default'], 'fixture')
        self.assertEqual(len(vault.unlock('fixture')), 4)
        entry = vault.select('Network Management', 'Test Wi-Fi')
        self.assertEqual(entry['fields'], {'psk': 'synthetic-wifi-only'})
        saved = vault.add('Bus test', 'tester', 'test-only', 'https://example.invalid', '')
        values = dict(saved['fields'], Password='changed-test-only')
        self.assertEqual(vault.save(values)['fields'], values)
        vault.delete()
        self.assertEqual(vault.disconnect('Fixture App'), [])
        # Verify the real Qt signal hookup, rather than only calling its slot.
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from app import PasswordsWindow
        app = QApplication.instance() or QApplication([])
        window = PasswordsWindow('/missing-test-helper')
        self.addCleanup(lambda: (window.close(), window.thread.wait(2000)))
        def wait():
            for _ in range(200):
                QTest.qWait(10)
                if not window.busy: return
            self.fail('UI timed out')
        wait(); window.dispatch('unlock', ['fixture']); wait()
        self.assertTrue(window.unlocked)
        # Closing an unrelated compatibility connection must not lock this view.
        window.wallet_closed('fixture'); wait()
        self.assertTrue(window.unlocked)
        transport.call('emitClose', 'fixture')
        for _ in range(200):
            QTest.qWait(10)
            if not window.unlocked: break
        self.assertFalse(window.unlocked)
        window.dispatch('unlock', ['fixture']); wait()
        watcher = None
        if importlib.util.find_spec('nacl'):
            from browser_host import LockWatcher
            notifications = []
            watcher = LockWatcher(notifications.append)
            watcher.collection_path = '/org/freedesktop/secrets/collection/fixture'
            self.addCleanup(watcher.close)
            for _ in range(100):
                time.sleep(.01)  # Let the GLib watcher thread run alongside Qt.
                QTest.qWait(10)
                if not watcher.blocked.is_set(): break
            self.assertFalse(watcher.blocked.is_set())
            transport.call('emitOtherLock'); time.sleep(.1); QTest.qWait(20)
            self.assertFalse(watcher.vault_blocked.is_set())
        transport.lock_wallet('fixture')
        for _ in range(200):
            QTest.qWait(10)
            if not window.unlocked: break
        self.assertFalse(window.unlocked)
        self.assertTrue(transport.wallet_locked('fixture'))
        if watcher:
            for _ in range(100):
                time.sleep(.01)
                QTest.qWait(10)
                if watcher.vault_blocked.is_set(): break
            self.assertTrue(watcher.vault_blocked.is_set())
            self.assertIn({'action': 'database-locked'}, notifications)
        window.close(); window.thread.wait(2000)
        vault.lock()

if __name__ == '__main__': unittest.main()
