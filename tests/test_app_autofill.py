"""Native autofill is scoped to an app/service and an unchanged explicit account choice."""
import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tests.test_app_logins import IDENTITY, VALUES, FakeWallet, Vault, VaultError, pack_map
from tests import test_app_detector as detector_fixture
from tests.test_app_detector import Node, ROLES, API
from app_detector import FillTarget, form_values
from app_logins import AppIdentity, AppLoginStore, APP_FOLDER, change_policy, policy


class FillStorage(unittest.TestCase):
    def setUp(self):
        self.wallet = FakeWallet(); self.vault = Vault(self.wallet); self.vault.unlock('fixture', listing=False)
        self.enabled = True; self.store = AppLoginStore(self.vault, IDENTITY, lambda: self.enabled)
        for user, server in (('first', 'server-a'), ('second', 'server-a'), ('first', 'server-b')):
            self.store.commit(self.store.prepare(dict(VALUES, username=user, service=server)))

    def test_account_selection_requires_exact_service_and_optional_username(self):
        self.assertEqual([r['username'] for r in self.store.accounts('server-a')], ['first', 'second'])
        self.assertEqual(len(self.store.accounts('server-a', 'second')), 1)
        self.assertEqual(self.store.accounts('other-server'), [])
        self.assertEqual(self.store.accounts('server-a', 'Second'), [])
        row = self.store.accounts('server-b', 'first')[0]
        self.assertEqual(self.store.retrieve(row)['password'], VALUES['password'])

    def test_other_apps_are_not_read_and_never_returned(self):
        other = AppLoginStore(self.vault, AppIdentity('executable:/other', IDENTITY.name, '/other'))
        record = other.prepare(dict(VALUES, username='different-app', service='server-a')); other.commit(record)
        with patch.object(self.vault, 'read', wraps=self.vault.read) as read:
            rows = self.store.accounts('server-a')
            self.assertEqual(len(rows), 2)
            self.assertFalse(any(call.args[1] == record['key'] for call in read.call_args_list))
        with self.assertRaises(VaultError): self.store.retrieve(other.accounts('server-a')[0])

    def test_a_changed_or_locked_record_cannot_be_filled(self):
        row = self.store.accounts('server-a', 'first')[0]
        entry = self.vault.read(APP_FOLDER, row['key'])
        self.wallet.entries[(APP_FOLDER, row['key'])] = (3, pack_map(dict(entry['fields'], Password='intervening-change')))
        with self.assertRaises(VaultError): self.store.retrieve(row)
        row = self.store.accounts('server-a', 'first')[0]
        self.enabled = False
        with self.assertRaises(VaultError): self.store.retrieve(row)
        self.enabled = True; self.wallet.opened = False
        with self.assertRaises(VaultError): self.store.retrieve(row)

    def test_legacy_app_records_are_preserved_and_can_be_selected(self):
        row = self.store.accounts('server-a', 'first')[0]
        legacy = 'Fixture — first [' + row['key'].split(':')[-1]
        self.wallet.entries[(APP_FOLDER, legacy)] = self.wallet.entries.pop((APP_FOLDER, row['key']))
        selected = self.store.accounts('server-a', 'first')[0]
        self.assertEqual(selected['key'], legacy)
        self.assertEqual(self.store.retrieve(selected)['username'], 'first')

    def test_recording_saved_apps_cannot_race_the_off_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.json'
            change_policy(enabled=True, path=path)
            with ThreadPoolExecutor(2) as pool:
                a = pool.submit(change_policy, saved=IDENTITY, path=path)
                b = pool.submit(change_policy, enabled=False, path=path)
                a.result(); b.result()
            self.assertFalse(policy(path)['enabled'])
            self.assertIn(IDENTITY.key, policy(path)['saved_apps'])


class FillDestination(detector_fixture.DetectorBoundaries):
    def setUp(self):
        super().setUp()
        self.password.value = ''; self.user.value = ''
        from types import SimpleNamespace
        API.EditableText = SimpleNamespace(set_text_contents=self.write)
        Node.get_editable_text_iface = lambda node: node
        self.writes = []

    def write(self, node, value):
        self.writes.append(node); node.value = value
        return True

    def target(self):
        self.focus(self.password)
        return FillTarget.capture(self.detector, self.detector.pending)

    def test_fill_changes_only_the_selected_fields_and_never_submits(self):
        target = self.target(); self.assertTrue(target.apply(dict(VALUES, username='chosen')))
        self.assertEqual((self.user.value, self.password.value), ('chosen', VALUES['password']))
        self.assertEqual(self.writes, [self.user, self.password])
        self.assertEqual(self.offers, [])

    def test_destination_change_lock_new_password_and_timeout_prevent_writes(self):
        for change in ('server', 'username', 'password', 'lock', 'timeout', 'replaced-field', 'operation'):
            with self.subTest(change=change):
                self.setUp()
                server = Node(ROLES.TEXT, 'Server', 'one', self.root)
                target = self.target()
                if change == 'server': server.value = 'two'
                elif change == 'username': self.user.value = 'someone-else'
                elif change == 'password': self.password.value = 'already-typed'
                elif change == 'lock': self.enabled = False
                elif change == 'timeout': self.now = 91
                elif change == 'operation': self.button.name = 'Create account'
                else:
                    self.root.children.remove(self.password); Node(ROLES.PASSWORD_TEXT, 'Password', '', self.root)
                self.assertFalse(target.apply(dict(VALUES, username='chosen', service='one')))
                self.assertEqual(self.writes, [])

    def test_signup_and_password_change_forms_are_never_autofilled(self):
        self.button.name = 'Create account'
        self.assertIsNone(self.target())
        self.detector.clear(); self.button.name = 'Sign in'
        Node(ROLES.PASSWORD_TEXT, 'Confirm password', '', self.root)
        self.assertIsNone(self.target())

    def test_fixed_username_is_not_replaced_by_another_account(self):
        self.user.value = 'first'
        self.assertFalse(self.target().apply(dict(VALUES, username='second')))
        self.assertEqual(self.writes, [])

    def test_readonly_username_is_supported_and_not_written(self):
        self.user.value = VALUES['username']; self.user.states.remove('editable')
        self.assertTrue(self.target().apply(VALUES))
        self.assertEqual(self.writes, [self.password])

    def test_username_first_context_is_limited_to_the_same_window(self):
        self.password.states.remove('showing'); self.button.name = 'Continue'
        self.user.value = 'first'; self.focus(self.user)
        self.assertEqual(self.detector.previous_user(IDENTITY, self.root), 'first')
        self.user.states.remove('showing'); self.password.states.add('showing')
        self.button.name = 'Sign in'
        target = self.target()
        self.assertEqual(target.context['username'], 'first')
        self.assertTrue(target.apply(dict(VALUES, username='first')))

    # This class uses an empty form for autofill. The inherited capture tests use
    # a nonempty password and run in their original suite, not twice here.
    test_focus_or_button_focus_alone_never_prompts = None
    test_recent_edit_cannot_save_a_stale_partial_password = None
    test_other_window_cancel_and_expiry_discard_candidates = None
    test_disable_unknown_username_and_embedded_browser_are_ignored = None
    test_closed_window_and_scan_limits_fail_closed = None
    test_only_removing_the_password_subtree_can_offer_a_login = None


if os.environ.get('MONET_PASSWORDS_QT_TESTS') == '1':
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app_fill import FillDialog

    class AccountChooser(unittest.TestCase):
        @classmethod
        def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

        def setUp(self):
            self.wallet = FakeWallet(); vault = Vault(self.wallet); vault.unlock('fixture', listing=False)
            store = AppLoginStore(vault, IDENTITY)
            for username in ('first', 'second'): store.commit(store.prepare(dict(VALUES, username=username)))
            self.wallet.calls.clear()
            self.dialog = FillDialog(IDENTITY, dict(username='', service=''), factory=lambda: self.wallet, permitted=lambda _: True)
            self.dialog.show(); QTest.qWait(10)

        def tearDown(self):
            self.dialog.reject(); self.dialog.finish(); self.dialog.deleteLater(); self.app.processEvents()

        def wait(self, condition):
            for _ in range(100):
                if condition(): return
                QTest.qWait(10)
            self.fail('Account chooser did not finish')

        def test_initial_prompt_does_not_open_the_vault_and_enter_declines(self):
            self.assertNotIn('open', self.wallet.calls)
            QTest.keyClick(self.dialog, Qt.Key_Return)
            self.assertEqual(self.dialog.result_login, {})

        def test_multiple_accounts_require_selection_and_explicit_fill(self):
            QTest.mouseClick(self.dialog.refresh, Qt.LeftButton)
            self.wait(lambda: self.dialog.loaded)
            self.assertEqual(self.dialog.accounts.count(), 2)
            self.assertEqual(self.dialog.result_login, {})
            self.dialog.accounts.setCurrentRow(1)
            QTest.mouseClick(self.dialog.fill, Qt.LeftButton)
            self.wait(lambda: bool(self.dialog.result_login))
            self.assertEqual(self.dialog.result_login['username'], 'second')
            self.assertEqual(self.dialog.result_login['password'], VALUES['password'])

        def test_lock_discards_selection_and_returns_no_password(self):
            self.dialog.load(); self.wait(lambda: self.dialog.loaded)
            self.dialog.accounts.setCurrentRow(0); self.dialog.screen_changed(True)
            self.assertEqual(self.dialog.result_login, {})
            self.assertEqual(self.dialog.accounts.count(), 0)
