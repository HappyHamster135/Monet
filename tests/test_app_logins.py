"""App login capture is opt-in, bounded, separated from websites, and consent driven."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_native_passwords import FakeWallet, Vault, VaultError, pack_map, MODULES
from app_logins import (AppIdentity, APP_FOLDER, AppLoginStore, candidate, policy, change_policy,
                        allowed, identify)
from app_detector import form_values
from vault import category, entry_title

IDENTITY = AppIdentity('executable:/usr/bin/fixture', 'Fixture', '/usr/bin/fixture')
VALUES = dict(username='demo@example.invalid', password='synthetic-only', service='', kind='login')


class AppPolicy(unittest.TestCase):
    def test_default_off_enable_ignore_disable_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'monet/app-logins.json'
            self.assertFalse(policy(path)['enabled'])
            change_policy(enabled=True, path=path)
            self.assertTrue(allowed(IDENTITY, path))
            change_policy(ignore=IDENTITY, path=path)
            self.assertFalse(allowed(IDENTITY, path))
            change_policy(enabled=False, path=path)
            self.assertIn(IDENTITY.key, policy(path)['ignored'])
            change_policy(reset=True, path=path)
            self.assertFalse(policy(path)['enabled'])
            self.assertEqual(policy(path)['ignored'], {})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(VALUES['password'], path.read_text())

    def test_corrupt_or_symlinked_policy_fails_closed_without_erasing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prefs'
            for text in ('[', '{}', '{"version":1,"enabled":"true","ignored":{}}'):
                path.write_text(text)
                self.assertFalse(policy(path)['enabled'])
                with self.assertRaises(VaultError): change_policy(enabled=True, path=path)
                self.assertEqual(path.read_text(), text)
            link = Path(directory) / 'link'; link.symlink_to(path)
            self.assertTrue(policy(link)['error'])

    def test_bounded_request_and_metadata(self):
        for extra in ({'pid': 2}, {'website': 'https://example.invalid'}, {'kind': 'fill'},
                      {'username': 'a\nmisleading'}, {'username': '\u202espoof'},
                      {'service': 'x' * 201}, {'password': 'x' * 4097}, {'password': None}):
            with self.assertRaises(ValueError): candidate(dict(VALUES, **extra))
        self.assertEqual(candidate(VALUES), VALUES)

    def test_failed_service_start_rolls_opt_in_back(self):
        import app_offers
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), \
                patch.object(app_offers.subprocess, 'run') as run:
            run.return_value.returncode = 1
            self.assertFalse(app_offers.configure('on')['ok'])
            self.assertFalse(policy()['enabled'])
            self.assertFalse(app_offers.configure('anything')['ok'])

    def test_identity_comes_from_process_not_claimed_app_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); process = root / '45'; process.mkdir()
            (process / 'exe').symlink_to('/usr/bin/example-app')
            identity = identify(45, root)
            self.assertEqual(identity.scope, 'executable:/usr/bin/example-app')
            for name in ('firefox', 'kwalletd6', 'ksecretd', 'keepassxc', 'monet-passwords', 'polkit-kde-authentication-agent-1'):
                (process / 'exe').unlink(); (process / 'exe').symlink_to('/usr/bin/' + name)
                with self.assertRaises(ValueError, msg=name): identify(45, root)


class AppStorage(unittest.TestCase):
    def setUp(self):
        self.transport = FakeWallet(); self.vault = Vault(self.transport)
        self.vault.unlock('fixture', listing=False)
        self.enabled = True
        self.store = AppLoginStore(self.vault, IDENTITY, lambda: self.enabled)

    def test_save_readback_display_and_browser_separation(self):
        before = dict(self.transport.entries)
        prepared = self.store.prepare(VALUES)
        self.assertEqual(self.transport.entries, before)
        self.assertEqual(self.store.commit(prepared), 'saved')
        self.assertEqual(self.vault.read(APP_FOLDER, prepared['key'])['fields']['Password'], VALUES['password'])
        self.assertEqual(category(APP_FOLDER), 'Logins')
        self.assertEqual(entry_title(APP_FOLDER, prepared['key']), 'Fixture — demo@example.invalid')
        self.assertNotIn('Website', prepared['fields'])
        for key in before: self.assertEqual(self.transport.entries[key], before[key])
        from browser_store import BrowserStore
        browser = BrowserStore(self.vault, lambda *args: {}, lambda: False)
        self.assertEqual(browser.accounts('https://example.invalid'), [])

    def test_duplicate_and_explicit_update(self):
        first = self.store.prepare(VALUES); self.store.commit(first)
        duplicate = self.store.prepare(VALUES)
        self.assertTrue(duplicate['unchanged'])
        self.assertEqual(self.store.commit(duplicate), 'unchanged')
        update = self.store.prepare(dict(VALUES, password='new-synthetic'))
        self.assertIsNotNone(update['before'])
        self.assertEqual(self.vault.read(APP_FOLDER, first['key'])['fields']['Password'], VALUES['password'])
        self.assertEqual(self.store.commit(update), 'updated')

    def test_other_apps_and_services_have_distinct_entries(self):
        keys = {self.store.prepare(VALUES)['key'], self.store.prepare(dict(VALUES, service='second server'))['key']}
        other = AppLoginStore(self.vault, AppIdentity('executable:/other', 'Fixture', '/other'))
        keys.add(other.prepare(VALUES)['key'])
        self.assertEqual(len(keys), 3)

    def test_disable_lock_conflict_and_failed_write_never_claim_success(self):
        prepared = self.store.prepare(VALUES)
        self.enabled = False
        with self.assertRaises(VaultError): self.store.commit(prepared)
        self.enabled = True; self.transport.opened = False
        with self.assertRaises(VaultError): self.store.commit(prepared)
        self.vault.unlock('fixture', listing=False)
        self.transport.fail_write = True
        with self.assertRaises(VaultError): self.store.commit(prepared)
        self.transport.fail_write = False; self.store.commit(prepared)
        update = self.store.prepare(dict(VALUES, password='new-synthetic'))
        self.transport.entries[(APP_FOLDER, prepared['key'])] = (3, pack_map(dict(prepared['fields'], Password='other-change')))
        with self.assertRaises(VaultError): self.store.commit(update)

    def test_only_one_matching_app_record_is_read(self):
        self.transport.calls.clear()
        prepared = self.store.prepare(VALUES); self.store.commit(prepared)
        self.assertNotIn('entryList', self.transport.calls)
        self.assertNotIn('folderList', self.transport.calls)
        self.assertNotIn('readPassword', self.transport.calls)


class FormRecognition(unittest.TestCase):
    def field(self, name, value, role='password'):
        return dict(name=name, value=value, role=role)

    def values(self, *passwords):
        return form_values([self.field('Email', 'demo@example.invalid', 'text'), *passwords])

    def test_plaintext_and_masked_forms(self):
        self.assertEqual(self.values(self.field('Password', 'synthetic'))['password'], 'synthetic')
        for value in ('*****', '•••••', '●●●●'):
            self.assertEqual(self.values(self.field('Password', value))['password'], '')
        self.assertIsNone(self.values(self.field('Password', '')))

    def test_registration_confirmation_and_password_changes(self):
        self.assertEqual(self.values(self.field('Password', 'new'), self.field('Confirm password', 'new'))['kind'], 'register')
        self.assertIsNone(self.values(self.field('Password', 'new'), self.field('Confirm password', 'typo')))
        changed = self.values(self.field('Current password', 'old'), self.field('New password', 'new'), self.field('Confirm password', 'new'))
        self.assertEqual((changed['kind'], changed['password']), ('change', 'new'))
        self.assertIsNone(self.values(self.field('Password one', 'one'), self.field('Password two', 'two')))

    def test_ambiguous_username_or_missing_username_is_ignored(self):
        self.assertIsNone(form_values([self.field('Password', 'secret')]))
        self.assertIsNone(form_values([self.field('Username', 'one', 'text'), self.field('Email', 'two', 'text'), self.field('Password', 'secret')]))


if os.environ.get('MONET_PASSWORDS_QT_TESTS') == '1':
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app_prompt import OfferDialog

    class AppOfferUI(unittest.TestCase):
        @classmethod
        def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

        def setUp(self):
            self.wallet = FakeWallet()
            self.ignored = []
            self.dialog = OfferDialog(IDENTITY, VALUES, lambda: self.wallet, lambda _: True, self.ignored.append)
            self.dialog.show(); QTest.qWait(10)

        def tearDown(self):
            self.dialog.reject(); self.dialog.finish(); self.dialog.deleteLater(); self.app.processEvents()

        def wait(self, predicate):
            for _ in range(100):
                if predicate(): return
                QTest.qWait(10)
            self.fail('Native prompt did not finish')

        def test_enter_declines_without_opening_vault(self):
            self.assertTrue(self.dialog.cancel.isDefault())
            QTest.keyClick(self.dialog, Qt.Key_Return)
            self.assertEqual(self.dialog.result_name, 'declined')
            self.assertNotIn('open', self.wallet.calls)
            self.assertEqual(self.dialog.password.text(), '')

        def test_explicit_save_and_update_confirmation(self):
            vault = Vault(self.wallet); vault.unlock('fixture', listing=False)
            store = AppLoginStore(vault, IDENTITY)
            prepared = store.prepare(dict(VALUES, password='old-synthetic')); store.commit(prepared)
            QTest.mouseClick(self.dialog.save, Qt.LeftButton)
            self.wait(lambda: self.dialog.updating)
            self.assertEqual(vault.read(APP_FOLDER, prepared['key'])['fields']['Password'], 'old-synthetic')
            self.assertTrue(self.dialog.cancel.isDefault())
            QTest.mouseClick(self.dialog.save, Qt.LeftButton)
            self.wait(lambda: self.dialog.result_name == 'updated')
            self.assertEqual(vault.read(APP_FOLDER, prepared['key'])['fields']['Password'], VALUES['password'])

        def test_save_and_never_choices(self):
            QTest.mouseClick(self.dialog.never, Qt.LeftButton)
            self.assertEqual(self.ignored, [IDENTITY]); self.assertNotIn('open', self.wallet.calls)

        def test_masked_fallback_requires_password_and_lock_clears_it(self):
            self.dialog.password.clear()
            self.assertFalse(self.dialog.save.isEnabled())
            self.dialog.password.setText('synthetic')
            self.assertTrue(self.dialog.save.isEnabled())
            self.dialog.screen_changed(True)
            self.assertEqual(self.dialog.password.text(), '')
            self.assertNotIn('open', self.wallet.calls)
