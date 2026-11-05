"""Zen setup uses only installation metadata; never browser passwords or storage."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.test_native_passwords import MODULES
from browser_setup import inspect, plan, browser_command, MONET_EXTENSION


class BrowserSetup(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.host = self.home / 'host'; self.host.write_text('fixture'); self.host.chmod(0o700)
        self.root = self.home / '.var/app/app.zen_browser.zen/.zen'
        self.profile = self.root / 'default'; self.profile.mkdir(parents=True)
        (self.root / 'profiles.ini').write_text('[Profile0]\nDefault=1\nIsRelative=1\nPath=default\n')
        self.connector = self.home / 'connector.xpi'
        self.connector.write_bytes((MODULES / 'connector.xpi').read_bytes())
        self.uuid = '01234567-89ab-cdef-0123-456789abcdef'

    def snapshot(self):
        return inspect(self.host, self.home, self.connector)

    def install(self, **overrides):
        row = dict(id=MONET_EXTENSION, version='0.1.1', active=True, userDisabled=False, appDisabled=False, signedState=2)
        row.update(overrides)
        (self.profile / 'extensions.json').write_text(json.dumps({'addons': [row]}))
        pref = json.dumps(json.dumps({MONET_EXTENSION: self.uuid}))
        (self.profile / 'prefs.js').write_text(f'user_pref("extensions.webextensions.uuids", {pref});\n')

    def configure(self):
        for path, text in plan(self.host, self.home).items():
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
        override = self.home / '.local/share/flatpak/overrides/app.zen_browser.zen'
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text('[Session Bus Policy]\norg.freedesktop.NativeMessagingProxy=talk\n')

    def test_missing_disabled_active_and_configured_are_distinct(self):
        state = self.snapshot(); self.assertEqual(state['addon'], 'missing'); self.assertFalse(state['configured'])
        self.install(userDisabled=True); state = self.snapshot()
        self.assertEqual(state['addon'], 'disabled'); self.assertEqual(state['popup'], '')
        self.install(); state = self.snapshot(); self.assertEqual(state['addon'], 'active')
        self.assertIn(self.uuid, state['popup']); self.assertFalse(state['configured'])
        self.configure(); self.assertTrue(self.snapshot()['configured'])

    def test_metadata_check_is_read_only_and_never_reads_browser_credentials(self):
        self.install(); self.configure()
        for name in ('logins.json', 'key4.db', 'storage.sqlite'):
            (self.profile / name).write_text('DO NOT READ')
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        original = Path.open
        def guarded(path, *args, **kwargs):
            self.assertNotIn(path.name, ('logins.json', 'key4.db', 'storage.sqlite'))
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            state = self.snapshot(); self.assertTrue(state['configured'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_missing_profile_and_other_manager_are_recoverable_without_overwrites(self):
        (self.root / 'profiles.ini').unlink()
        self.assertFalse(self.snapshot()['profile'])
        (self.root / 'profiles.ini').write_text('[Profile0]\nDefault=1\nIsRelative=1\nPath=default\n')
        self.configure()
        manifest = self.home / '.mozilla/native-messaging-hosts/org.keepassxc.keepassxc_browser.json'
        manifest.write_text('{"path":"/another/manager"}')
        state = self.snapshot(); self.assertIn('Another password manager', state['problem'])
        self.assertFalse(state['configured']); self.assertEqual(json.loads(manifest.read_text())['path'], '/another/manager')

    def test_bad_profiles_registry_and_uuid_fail_closed(self):
        self.install(signedState=0)
        self.assertEqual(self.snapshot()['addon'], 'disabled')
        self.install()
        (self.profile / 'prefs.js').write_text('user_pref("extensions.webextensions.uuids", "not-json");\n')
        state = self.snapshot(); self.assertTrue(state['problem']); self.assertEqual(state['popup'], '')
        (self.profile / 'extensions.json').write_text('{broken')
        self.assertTrue(self.snapshot()['problem'])
        (self.root / 'profiles.ini').write_text('[Profile0]\nDefault=1\nIsRelative=1\nPath=../../../../..\n')
        self.assertFalse(self.snapshot()['profile'])

    def test_browser_launch_cannot_open_untrusted_urls_or_bypass_file_portal(self):
        self.install(); state = self.snapshot()
        self.assertEqual(browser_command(state, 'popup')[-1], state['popup'])
        self.assertIn('--new-window', browser_command(state, 'popup'))
        self.assertEqual(browser_command({'popup': 'https://untrusted.invalid'}, 'popup')[-1], 'about:addons')
        command = browser_command(state, 'install', self.connector)
        self.assertIn('--file-forwarding', command); self.assertEqual(command[-3:], ['@@u', self.connector.as_uri(), '@@'])
        self.connector.write_bytes(b'unsigned or corrupted archive')
        with self.assertRaises(ValueError): browser_command(state, 'install', self.connector)
        self.assertFalse(self.snapshot()['bundled'])
        self.connector.unlink()
        with self.assertRaises(ValueError): browser_command(state, 'install', self.connector)
        with self.assertRaises(ValueError): browser_command(state, 'arbitrary')

    def test_only_older_known_versions_offer_a_verified_bundle_update(self):
        for version, expected in [('0.1.0', True), ('0.1.1', False), ('0.1.1.0', False),
                                  ('0.2.0', False), ('1.0', False), ('0.1.0beta', False),
                                  ('', False), (None, False), ([], False)]:
            with self.subTest(version=version):
                self.install(version=version)
                self.assertEqual(self.snapshot()['update_available'], expected)
        self.install(version='0.1.0')
        self.connector.unlink()
        state = self.snapshot()
        self.assertFalse(state['update_available'])
        self.assertEqual(state['addon'], 'active')
        self.assertTrue(state['popup'])


@unittest.skipUnless(os.environ.get('MONET_PASSWORDS_QT_TESTS') == '1', 'native Qt setup fixture')
class BrowserPageUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_installed_connector_opens_without_reinstallation_or_automatic_pairing(self):
        from browser_ui import BrowserPage
        page = BrowserPage(lambda text: text)
        try:
            events = []; page.requested.connect(events.append)
            state = dict(profile=True, configured=True, addon='active', bundled=True, problem='', options='fixture')
            page.show_state(state); page.primary.click()
            self.assertEqual(events, ['popup'])
            self.assertNotIn('connected', page.title.text().lower())
            page.set_busy(True); page.primary.click(); self.assertEqual(events, ['popup'])
            self.assertFalse(page.options.isEnabled())
            page.show_state(dict(state, addon='disabled')); page.primary.click(); self.assertEqual(events[-1], 'manage')
            page.show_state(dict(state, update_available=True))
            self.assertIn('update', page.title.text())
            page.primary.click(); self.assertEqual(events[-1], 'install')
            page.show_state(dict(state, update_available=True, addon='disabled'))
            page.primary.click(); self.assertEqual(events[-1], 'manage')
            page.show_state(dict(state, addon='missing', bundled=False)); self.assertFalse(page.primary.isEnabled())
        finally: page.close()


if __name__ == '__main__': unittest.main()
