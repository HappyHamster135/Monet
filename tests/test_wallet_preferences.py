"""Vault settings never read secrets and preserve existing encrypted storage."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


class WalletPreferences(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()

    @unittest.skipUnless(shutil.which('kwriteconfig6'), 'native KConfig tools')
    def test_native_policy_round_trip_preserves_unrelated_preferences(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
            path = Path(tmp) / 'kwalletrc'
            path.write_text('[Wallet]\nDefault Wallet=personal\nEnabled=true\n[Other]\nKeep=unchanged\n')
            original = self.q.run
            def command(*args, **kwargs):
                if args[0] == 'busctl': return 'b true\n' if 'isOpen' in args else ''
                if args[0] == 'loginctl': return 'plasmalogin-autologin\n'
                return original(*args, **kwargs)
            with patch.object(self.q, 'run', side_effect=command) as calls:
                for mode in ('10', '30', 'session'):
                    result = self.q.wallet_policy(mode)
                    self.assertTrue(result['ok'], result)
                    self.assertEqual(result['state']['policy'], mode)
                    self.assertTrue(result['state']['unlocked'])
                    self.assertEqual(self.q.kread('kwalletrc', 'Wallet', 'Default Wallet'), 'personal')
                    self.assertEqual(self.q.kread('kwalletrc', 'Other', 'Keep'), 'unchanged')
                # No password/entry reads, vault deletion or password changes.
                allowed = {'isOpen', 'reconfigure'}
                for call in calls.call_args_list:
                    if call.args[0] == 'busctl':
                        self.assertIn(call.args[call.args.index('org.kde.KWallet') + 1], allowed)

    def test_invalid_policy_writes_nothing(self):
        with patch.object(self.q, 'kwrite') as write, patch.object(self.q, 'run') as run:
            for value in ('', 'never-encrypt', 'session;anything', '0', '../other'):
                self.assertFalse(self.q.wallet_policy(value)['ok'])
            write.assert_not_called(); run.assert_not_called()

    def test_failed_write_or_readback_cannot_report_success(self):
        with patch.object(self.q, 'kwrite', return_value=False), patch.object(self.q, 'kread', return_value='false'), \
                patch.object(self.q, 'run', return_value=None), patch.object(self.q, 'wallet_status', return_value={}):
            self.assertFalse(self.q.wallet_policy('session')['ok'])
        with patch.object(self.q, 'kwrite', return_value=True), patch.object(self.q, 'kread', return_value='wrong'), \
                patch.object(self.q, 'run', return_value=None), patch.object(self.q, 'wallet_status', return_value={}):
            self.assertFalse(self.q.wallet_policy('session')['ok'])

    def test_unavailable_status_does_not_claim_vault_is_unlocked(self):
        with patch.object(self.q, 'run', return_value=None):
            self.assertIsNone(self.q.wallet_status()['unlocked'])

    def test_lock_uses_native_lock_only_and_reports_failure(self):
        with patch.object(self.q, 'wallet_status', return_value={}), patch.object(self.q, 'run', return_value=None) as run:
            self.assertFalse(self.q.wallet_lock()['ok'])
            self.assertEqual(run.call_args.args[-1], 'closeAllWallets')
            self.assertIn('--auto-start=no', run.call_args.args)
            run.return_value = ''
            self.assertTrue(self.q.wallet_lock()['ok'])

    def test_access_opens_native_preferences_without_reading_passwords(self):
        with patch.object(self.q.subprocess, 'Popen') as launch, patch.object(self.q, 'run') as run:
            self.assertTrue(self.q.wallet_access()['ok'])
            self.assertEqual(launch.call_args.args[0], ['kcmshell6', 'kcm_kwallet5'])
            run.assert_not_called()

    def test_browser_link_uses_only_known_local_application_and_fixed_page(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            browser=folder/'app.zen_browser.zen.desktop'
            browser.write_text('[Desktop Entry]\nType=Application\nExec=fixture %u\n')
            with patch.object(self.q, 'run', return_value=browser.name), patch.object(self.q, 'app_dirs', return_value=(folder,)), \
                    patch.object(self.q.shutil, 'which', return_value='/usr/bin/gio'), patch.object(self.q.subprocess, 'Popen') as launch:
                self.assertTrue(self.q.wallet_browser()['ok'])
                self.assertEqual(launch.call_args.args[0], ['gio','launch',str(browser),'about:logins'])
                browser.write_text(browser.read_text()+'Hidden=true\n')
                self.assertFalse(self.q.wallet_browser()['ok'])
                self.q.run.return_value='../../unsafe.desktop'
                self.assertFalse(self.q.wallet_browser()['ok'])
                self.assertEqual(launch.call_count,1)
