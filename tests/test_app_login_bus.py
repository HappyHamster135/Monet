"""Actual authenticated app -> session service -> Qt prompt -> dummy encrypted provider API."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
from app_logins import change_policy, policy, APP_FOLDER
from app_offers import BUS_NAME, BUS_PATH
from vault import unpack_map


@unittest.skipUnless(os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1', 'private native D-Bus fixture')
class AppLoginBus(unittest.TestCase):
    def setUp(self):
        import dbus
        self.bus = dbus.SessionBus(); self.processes = []
        self.assertFalse(self.bus.name_has_owner('org.kde.kwalletd6'))
        change_policy(enabled=True, reset=True)
        self.launch([sys.executable, str(ROOT / 'tests/passwords_bus_fixture.py')])
        self.wait(lambda: self.bus.name_has_owner('org.kde.kwalletd6'))
        self.launch(['/usr/libexec/at-spi-bus-launcher'])
        self.wait(lambda: self.bus.name_has_owner('org.a11y.Bus'))
        self.wallet = dbus.Interface(self.bus.get_object('org.kde.kwalletd6', '/modules/kwalletd6'), 'org.kde.KWallet')
        self.screen = dbus.Interface(self.bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver'), 'org.monet.Test')

    def launch(self, command, **kwargs):
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        self.processes.append(process); return process

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.02)
        self.fail('Private service did not reach expected state')

    def service(self, mode):
        process = self.launch([sys.executable, str(ROOT / 'tests/fixtures/app-login-native.py'), 'service'],
                             env=dict(os.environ, APP_LOGIN_FIXTURE_ACTION=mode))
        self.wait(lambda: self.bus.name_has_owner(BUS_NAME) or process.poll() is not None)
        self.assertIsNone(process.poll(), 'Offer service failed to start')
        return process

    def client(self):
        return subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/app-login-native.py'), 'client'],
                              capture_output=True, text=True, timeout=20)

    def busy(self):
        return bool(self.bus.get_object(BUS_NAME, BUS_PATH).GetStatus(dbus_interface=BUS_NAME)['busy'])

    def tearDown(self):
        for process in reversed(self.processes):
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        self.wait(lambda: not self.bus.name_has_owner('org.kde.kwalletd6'))
        change_policy(enabled=False, reset=True)

    def test_explicit_save_reaches_provider_and_repeat_is_suppressed(self):
        self.service('save')
        response = self.client()
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(response.stdout.strip(), 'saved')
        keys = self.wallet.entryList(42, APP_FOLDER, 'Monet App Logins')
        self.assertEqual(len(keys), 1)
        fields = unpack_map(bytes(self.wallet.readMap(42, APP_FOLDER, keys[0], 'Monet App Logins')))
        self.assertEqual(fields['Password'], 'synthetic-app-only')
        self.assertIn('app-login-native.py', fields['Application ID'])
        self.assertEqual(self.client().stdout.strip(), 'recent')

    def test_decline_keeps_vault_unchanged(self):
        self.service('decline')
        self.assertEqual(self.client().stdout.strip(), 'declined')
        self.assertEqual(list(self.wallet.entryList(42, APP_FOLDER, 'Monet App Logins')), [])

    def test_native_autofill_returns_only_an_approved_exact_service_account(self):
        import json
        self.service('save'); self.assertEqual(self.client().stdout.strip(), 'saved')
        def request(service):
            result = subprocess.run([sys.executable, str(ROOT/'tests/fixtures/app-login-native.py'), 'get', service],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(request('Test service'), dict(status='filled', matches=True, has_secret=True))
        self.assertEqual(request('Other service'), dict(status='declined', matches=False, has_secret=False))
        self.screen.SetActive(True)
        self.assertEqual(request('Test service'), dict(status='disabled', matches=False, has_secret=False))

    def test_document_integration_shares_only_exact_app_origin_and_never_url_tokens(self):
        import json
        self.service('save')
        def client(verb, url):
            result=subprocess.run([sys.executable,str(ROOT/'tests/fixtures/app-login-native.py'),verb,url],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
        self.assertEqual(client('doc-save','https://accounts.example.invalid/login?private=token#fragment'),'saved')
        rows=self.wallet.entryList(42,APP_FOLDER,'Monet App Logins');self.assertEqual(len(rows),1)
        fields=unpack_map(bytes(self.wallet.readMap(42,APP_FOLDER,rows[0],'Monet App Logins')))
        self.assertTrue(fields['Application ID'].endswith('|document:https://accounts.example.invalid'))
        self.assertNotIn('private',str(fields));self.assertNotIn('fragment',str(fields))
        self.assertTrue(json.loads(client('doc-get','https://accounts.example.invalid/another'))['matches'])
        self.assertFalse(json.loads(client('doc-get','https://other.example.invalid/'))['has_secret'])
        self.assertEqual(client('doc-save','http://remote.example.invalid/'),'unavailable')
        self.assertFalse(json.loads(client('doc-get','about:blank'))['has_secret'])

    def test_disconnected_fill_caller_closes_pending_consent(self):
        self.service('hold')
        process=self.launch([sys.executable,str(ROOT/'tests/fixtures/app-login-native.py'),'get'])
        self.wait(self.busy);process.terminate();process.wait(timeout=3)
        self.wait(lambda: not self.busy())

    def test_never_is_persisted_without_a_secret(self):
        self.service('never')
        response = self.client()
        self.assertIn(response.stdout.strip(), ('ignored', 'cancelled'))
        self.assertEqual(len(policy()['ignored']), 1)
        self.assertEqual(self.client().stdout.strip(), 'disabled')
        self.assertEqual(list(self.wallet.entryList(42, APP_FOLDER, 'Monet App Logins')), [])

    def test_screen_lock_cancels_pending_and_blocks_new_offers(self):
        self.service('hold')
        client = self.launch([sys.executable, str(ROOT / 'tests/fixtures/app-login-native.py'), 'client'])
        # Verify one prompt is pending through the bounded busy response, not a sleep.
        self.wait(self.busy)
        self.screen.SetActive(True)
        client.wait(timeout=5)
        self.assertEqual(self.client().stdout.strip(), 'disabled')
        self.assertEqual(list(self.wallet.entryList(42, APP_FOLDER, 'Monet App Logins')), [])

    def test_turning_off_stops_service_and_cancels_pending(self):
        service = self.service('hold')
        client = self.launch([sys.executable, str(ROOT / 'tests/fixtures/app-login-native.py'), 'client'])
        self.wait(self.busy)
        change_policy(enabled=False)
        service.wait(timeout=5); client.wait(timeout=5)
        self.assertEqual(list(self.wallet.entryList(42, APP_FOLDER, 'Monet App Logins')), [])
