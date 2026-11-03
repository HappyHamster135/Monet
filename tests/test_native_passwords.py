"""Synthetic secrets only; never connect to a user's real vault or copy its entries."""
import importlib.util
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / 'linux/share/monet/passwords'
sys.path.insert(0, str(MODULES))
from vault import Vault, VaultError, pack_map, unpack_map, decode_stream, friendly_title, APP_ID, PERSONAL_FOLDER


class FakeWallet:
    def __init__(self):
        self.opened = True
        self.calls = []
        self.fail_write = False
        self.entries = {
            ('Network Management', 'Test Wi-Fi'): (3, pack_map({'psk': 'synthetic-wifi-only'})),
            ('Example App', 'Account'): (2, 'synthetic-login-only'),
            ('Example App', 'Encryption key'): (1, b'\x00\xff\x91\x12'),
            ('Network Management', 'Old Wi-Fi'): (1, b'{"802-11-wireless-security":{"psk":"synthetic-old"}}'),
        }
        self.connected = ['Fixture App', APP_ID]
    def close_connection(self): pass
    def lock_wallet(self, wallet): self.opened = False
    def call(self, method, *args):
        self.calls.append(method)  # No secret arguments retained in test logs.
        if method == 'wallets': return ['fixture']
        if method == 'localWallet': return 'fixture'
        if method == 'open':
            self.opened = True
            if APP_ID not in self.connected: self.connected.append(APP_ID)
            return 42
        if method == 'isOpen': return self.opened
        if method == 'folderList': return sorted({f for f, _ in self.entries})
        if method == 'entryList': return [k for f, k in self.entries if f == args[1]]
        if method == 'hasEntry': return (args[1], args[2]) in self.entries
        if method == 'hasFolder': return args[1] in {f for f, _ in self.entries}
        if method == 'createFolder': return True
        if method == 'entryType': return self.entries[(args[1], args[2])][0]
        if method in ('readPassword', 'readMap', 'readEntry'): return self.entries[(args[1], args[2])][1]
        if method in ('writeMap', 'writePassword'):
            if self.fail_write: return -1
            self.entries[(args[1], args[2])] = (3 if method == 'writeMap' else 2, args[3]); return 0
        if method == 'removeEntry': self.entries.pop((args[1], args[2])); return 0
        if method == 'users': return self.connected[:]
        if method == 'disconnectApplication': self.connected.remove(args[1]); return True
        if method == 'close': self.opened = False; return 0
        raise AssertionError(method)


class VaultBehavior(unittest.TestCase):
    def setUp(self):
        self.transport = FakeWallet(); self.vault = Vault(self.transport)
        self.vault.unlock('fixture')

    def test_listing_never_bulk_reads_secrets(self):
        self.assertEqual(len(self.vault.list_entries()), 4)
        self.assertFalse(any(c.startswith('read') for c in self.transport.calls))

    def test_network_names_replace_opaque_ids_without_reading_passwords(self):
        uuid = '01234567-89ab-cdef-0123-456789abcdef'
        self.assertEqual(friendly_title('Network Management', '{'+uuid+'};802-11-wireless-security', {uuid:'Test Wi-Fi'}), 'Test Wi-Fi')
        self.assertEqual(friendly_title('Example App', uuid, {uuid:'Test Wi-Fi'}), uuid)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt serialization fixture')
    def test_qt_map_round_trip_matches_native_serialization(self):
        from PySide6.QtCore import QByteArray, QDataStream, QIODevice
        fields = {'Password': 'synthetic🔑', 'Username': 'test'}
        raw = QByteArray(); stream = QDataStream(raw, QIODevice.WriteOnly)
        stream.writeUInt32(2)
        for k, v in fields.items(): stream.writeQString(k); stream.writeQString(v)
        self.assertEqual(bytes(raw), pack_map(fields))
        self.assertEqual(unpack_map(raw), fields)

    def test_map_decoder_rejects_truncation_duplicate_and_unbounded_lengths(self):
        raw = pack_map({'Password': 'synthetic'})
        for bad in (raw[:-1], raw+b'bad', b'\xff'*4, struct.pack('>II', 1, 0xfffffffe),
                    struct.pack('>I', 2)+raw[4:]+raw[4:]):
            with self.assertRaises((ValueError, UnicodeError)): unpack_map(bad)

    def test_binary_and_structured_fields_are_distinguished(self):
        self.assertEqual(decode_stream(b'\x00\xff\x90')[0], {})
        self.assertEqual(decode_stream(b'{"wifi":{"psk":"synthetic"}}')[0], {'wifi / psk': 'synthetic'})
        self.assertEqual(decode_stream(b'{"nested":[1,2,3]}')[0], {})
        self.assertEqual(decode_stream(b'plain-synthetic')[0], {'Secret': 'plain-synthetic'})

    def test_stream_is_viewable_but_never_reencoded_on_edit(self):
        entry = self.vault.select('Network Management', 'Old Wi-Fi')
        self.assertFalse(entry['editable']); self.assertTrue(entry['fields'])
        with self.assertRaises(VaultError): self.vault.save(entry['fields'])
        with self.assertRaises(VaultError): self.vault.delete()
        self.assertNotIn('writeMap', self.transport.calls)

    def test_create_edit_delete_and_duplicate_protection(self):
        added = self.vault.add('Fixture login', 'tester', 'synthetic', 'https://example.invalid', '')
        self.assertEqual(added['fields']['Password'], 'synthetic')
        with self.assertRaises(VaultError): self.vault.add('Fixture login', '', 'other', '', '')
        fields = dict(added['fields'], Password='changed-synthetic')
        self.assertEqual(self.vault.save(fields)['fields'], fields)
        self.vault.delete(); self.assertNotIn((PERSONAL_FOLDER, 'Fixture login'), self.transport.entries)

    def test_other_app_change_prevents_stale_save_and_delete(self):
        self.vault.select('Example App', 'Account')
        self.transport.entries[('Example App', 'Account')] = (2, 'changed-elsewhere')
        with self.assertRaises(VaultError): self.vault.save({'Password': 'overwrite'})
        with self.assertRaises(VaultError): self.vault.delete()
        self.assertNotIn('writePassword', self.transport.calls); self.assertNotIn('removeEntry', self.transport.calls)

    def test_write_failure_does_not_claim_success(self):
        self.vault.select('Example App', 'Account'); self.transport.fail_write = True
        with self.assertRaises(VaultError): self.vault.save({'Password': 'changed'})
        self.assertEqual(self.transport.entries[('Example App', 'Account')][1], 'synthetic-login-only')

    def test_lock_clears_state_and_refuses_read_write(self):
        self.vault.select('Example App', 'Account'); self.vault.lock()
        self.assertIsNone(self.vault.selected)
        with self.assertRaises(VaultError): self.vault.select('Example App', 'Account')
        with self.assertRaises(VaultError): self.vault.add('test', '', 'test', '', '')

    def test_only_existing_apps_can_be_disconnected(self):
        self.assertEqual(self.vault.apps(), ['Fixture App'])
        with self.assertRaises(VaultError): self.vault.disconnect(APP_ID)
        self.assertEqual(self.vault.disconnect('Fixture App'), [])


if os.environ.get('MONET_PASSWORDS_QT_TESTS') == '1':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QEvent, Qt, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QPushButton
    from PySide6.QtTest import QTest
    from app import PasswordsWindow, SecretClipboard, SecretField, Editor

    class PasswordsUI(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.app = QApplication.instance() or QApplication([])

        def setUp(self):
            self.backend = FakeWallet()
            self.window = PasswordsWindow('/missing-test-helper', lambda: self.backend, listen=False)
            self.window.show(); self.wait()

        def wait(self):
            for _ in range(300):
                QTest.qWait(10)
                if not self.window.busy: return
            self.fail('UI operation timed out')

        def tearDown(self):
            self.window.close(); self.window.thread.wait(2000); QTest.qWait(20)

        def unlock(self):
            QTest.mouseClick(self.window.unlock_button, Qt.LeftButton); self.wait()

        def select(self, key='Account'):
            self.unlock()
            item = next(self.window.list.item(i) for i in range(self.window.list.count())
                        if self.window.list.item(i).data(Qt.UserRole)['key'] == key)
            self.window.list.setCurrentItem(item); self.wait()

        def test_open_search_and_selection_are_readable_and_concealed(self):
            self.assertFalse(any(c.startswith('read') for c in self.backend.calls))
            self.select()
            field = self.window.fields[0]
            self.assertNotIn('synthetic', field.display.text())
            QTest.mouseClick(field.reveal, Qt.LeftButton)
            self.assertEqual(field.display.text(), 'synthetic-login-only')
            QApplication.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
            self.assertNotIn('synthetic', field.display.text())
            self.window.search.setText('Wi-Fi')
            self.assertEqual(self.window.list.count(), 2)
            self.assertIsNone(self.window.entry)

        def test_copy_uses_private_mime_and_preserves_newer_clipboard(self):
            self.select(); self.window.fields[0].clipboard.copy('synthetic-copy')
            clip = QApplication.clipboard()
            self.assertEqual(bytes(clip.mimeData().data('x-kde-passwordManagerHint')), b'secret')
            self.window.clipboard.clear(); self.assertEqual(clip.text(), '')
            self.window.clipboard.copy('synthetic-copy'); clip.setText('something else')
            self.window.clipboard.clear(); self.assertEqual(clip.text(), 'something else')
            clip.clear()

        def test_editor_cancel_wipes_values_and_does_not_write(self):
            self.select(); self.window.edit_login()
            editor = self.window.editor
            editor.fields['Password'].setText('synthetic-unsaved')
            editor.reject()
            self.assertEqual(editor.fields['Password'].text(), '')
            self.assertNotIn('writePassword', self.backend.calls)

        def test_multiline_app_fields_survive_editing_another_field(self):
            entry = {'key': 'Fixture', 'fields': {'Password': 'synthetic', 'private-key': 'line1\nline2'}}
            editor = Editor(entry, self.window)
            editor.fields['Password'].setText('changed')
            self.assertEqual(editor.values()['private-key'], 'line1\nline2')
            editor.reject(); self.assertEqual(editor.preserved, {})

        def test_clipboard_and_reveal_expiry_timers_clear_values(self):
            self.select(); field = self.window.fields[0]
            field.toggle(); self.assertEqual(field.timer.interval(), 15000)
            field.timer.timeout.emit(); self.assertFalse(field.shown)
            self.window.clipboard.copy('synthetic-timer')
            self.assertEqual(self.window.clipboard.timer.interval(), 30000)
            self.window.clipboard.timer.timeout.emit()
            self.assertEqual(QApplication.clipboard().text(), '')

        def test_slow_provider_keeps_ui_event_loop_responsive(self):
            import time
            original = self.backend.call
            def slow(method, *args):
                if method == 'open': time.sleep(0.15)
                return original(method, *args)
            self.backend.call = slow
            ticks = []
            QTimer.singleShot(20, lambda: ticks.append(self.window.busy))
            self.unlock()
            self.assertEqual(ticks, [True])

        def test_add_form_saves_and_clears_after_success(self):
            self.unlock(); self.window.add_login(); editor = self.window.editor
            editor.title.setText('Synthetic login'); editor.fields['Password'].setText('synthetic-new')
            self.window.save_editor(True); self.wait()
            self.assertEqual(editor.fields['Password'].text(), '')
            self.assertIsNone(self.window.editor)
            self.assertIn((PERSONAL_FOLDER, 'Synthetic login'), self.backend.entries)

        def test_lock_discards_late_results_and_clears_fields(self):
            self.select(); token = self.window.token; late = self.window.entry.copy()
            self.window.screen_locked(True)
            self.window.finished(token, 'select', late, '')
            self.assertIsNone(self.window.entry); self.assertEqual(self.window.fields, [])
            self.assertFalse(self.window.unlocked)

        def test_cleanup_reply_does_not_finish_a_new_unlock(self):
            self.window.clear_session()
            self.window.busy = True
            self.window.finished(self.window.token, 'forget', None, '')
            self.assertTrue(self.window.busy)
            self.window.busy = False

        def test_unknown_binary_is_explained_and_not_editable(self):
            self.select('Encryption key')
            self.assertEqual(self.window.fields, [])
            self.assertIn('binary', self.window.entry['note'])
            self.assertFalse(self.window.entry['editable'])

        def test_palette_change_keeps_list_text_readable(self):
            from PySide6.QtGui import QPalette, QColor
            old = self.app.palette()
            try:
                palette = QPalette(old); palette.setColor(QPalette.Window, QColor('#202424'))
                self.app.setPalette(palette); QTest.qWait(30)
                self.assertIn('color: #eeeae2; font-size: 14px;', self.window.styleSheet())
            finally:
                self.app.setPalette(old)

        def test_actual_dbus_signal_connections_can_be_registered(self):
            # No credential method is called; this only connects signals on the current bus.
            other = PasswordsWindow('/missing-test-helper', FakeWallet, listen=True)
            QTest.qWait(50); other.close(); other.thread.wait(2000)


if __name__ == '__main__': unittest.main()
