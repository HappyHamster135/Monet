"""Embedded forms are scoped to app and document; sandbox peers cannot claim IDs."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from tests.test_app_detector import API, ROLES, Node
from tests import test_app_detector as detector_fixtures
from tests.test_app_logins import IDENTITY, VALUES
from app_detector import Detector, FillTarget
from app_documents import document_scope
from app_logins import identify


class DocumentNode(Node):
    uri = 'https://accounts.example.invalid/signin'
    def get_document_iface(self): return self


class DocumentBoundaries(unittest.TestCase):
    def setUp(self):
        roles = NS(**vars(ROLES), FORM=8)
        api = NS(**vars(API)); api.Role = roles
        api.Document = NS(get_document_attribute_value=lambda node, name: node.uri)
        self.writes = []
        def write(node, value):
            self.writes.append(node); node.value = value; return True
        api.EditableText = NS(set_text_contents=write)
        DocumentNode.get_editable_text_iface = lambda node: node
        self.offers = []
        self.detector = Detector(api, NS(source_remove=lambda *_: None, timeout_add=lambda *_: 1, timeout_add_seconds=lambda *_: 1),
                                 lambda *args: self.offers.append(args), lambda _: True, resolver=lambda _: IDENTITY)
        self.window = DocumentNode(parent=DocumentNode(role=ROLES.APPLICATION))
        self.page = DocumentNode(ROLES.DOCUMENT_WEB, parent=self.window)
        self.form = DocumentNode(roles.FORM, parent=self.page)
        self.user = DocumentNode(ROLES.TEXT, 'Email', '', self.form)
        self.password = DocumentNode(ROLES.PASSWORD_TEXT, 'Password', '', self.form)
        self.button = DocumentNode(ROLES.PUSH_BUTTON, 'Sign in', parent=self.form)

    def target(self):
        self.detector.event(NS(source=self.password, type='object:state-changed:focused', detail1=1))
        return FillTarget.capture(self.detector, self.detector.pending) if self.detector.pending else None

    def test_app_and_document_are_both_bound_and_only_chosen_form_is_filled(self):
        other = DocumentNode(self.detector.api.Role.FORM, parent=self.page)
        DocumentNode(ROLES.PASSWORD_TEXT, 'Password', '', other)
        target = self.target(); self.assertIsNotNone(target)
        self.assertEqual(target.identity.scope, IDENTITY.scope + '|document:https://accounts.example.invalid')
        self.assertEqual(target.identity.document, 'https://accounts.example.invalid')
        self.assertTrue(target.apply(VALUES)); self.assertEqual(self.writes, [self.user, self.password])

    def test_changed_path_query_fragment_origin_or_controls_cannot_receive_password(self):
        for uri in ('https://accounts.example.invalid/other', 'https://accounts.example.invalid/signin?new',
                    'https://accounts.example.invalid/signin#new', 'https://other.example.invalid/signin'):
            with self.subTest(uri=uri):
                self.setUp(); target=self.target(); self.page.uri=uri
                self.assertFalse(target.apply(VALUES)); self.assertFalse(self.writes)

    def test_nested_cross_origin_missing_and_opaque_pages_fail_closed(self):
        for uri in ('https://other.example.invalid/login', 'about:blank', '', 'data:text/html,login'):
            with self.subTest(uri=uri):
                self.setUp()
                parent = DocumentNode(ROLES.DOCUMENT_WEB, parent=self.window); parent.uri=uri
                self.page.parent = parent; parent.children.append(self.page)
                self.assertIsNone(self.target()); self.assertFalse(self.writes)

    def test_same_origin_frame_remains_bound_to_its_parent_document(self):
        parent=DocumentNode(ROLES.DOCUMENT_WEB, parent=self.window)
        self.page.parent=parent; parent.children.append(self.page)
        target=self.target(); self.assertIsNotNone(target)
        parent.uri='https://other.example.invalid/'
        self.assertFalse(target.apply(VALUES)); self.assertFalse(self.writes)

    def test_editable_state_without_a_setter_does_not_offer_a_fill(self):
        self.password.get_editable_text_iface=lambda: None
        self.assertIsNone(self.target()); self.assertFalse(self.writes)

    def test_save_after_hiding_form_rechecks_document_and_never_records_url_tokens(self):
        self.user.value='demo'; self.password.value='synthetic'
        self.page.uri += '?token=private#fragment'
        self.target()
        self.detector.event(NS(source=self.password, type='object:state-changed:showing', detail1=0))
        self.detector.confirm_offer()
        self.assertEqual(len(self.offers),1)
        self.assertNotIn('token',self.offers[0][0].scope)
        self.setUp(); self.user.value='demo'; self.password.value='synthetic'; self.target()
        self.page.uri='https://other.example.invalid/'
        self.detector.event(NS(source=self.password, type='object:state-changed:showing', detail1=0))
        self.detector.confirm_offer(); self.assertEqual(self.offers,[])

    def test_document_scope_rejects_remote_http_credentials_and_unknown_schemes(self):
        for value in ('http://example.invalid/login', 'https://user:secret@example.invalid/',
                      'https://example.invalid:bad/', 'file://remote/login', 'about:blank',
                      'javascript:alert(1)', 'https://example.invalid\\@evil.invalid', 'https://example.invalid/\n'):
            with self.subTest(value=value), self.assertRaises(ValueError): document_scope(value)
        self.assertEqual(document_scope('https://EXAMPLE.invalid:443/login?a=b#c'), 'https://example.invalid')
        self.assertEqual(document_scope('file:///app/login.html?token=secret'), 'file:///app/login.html')
        self.assertNotEqual(document_scope('file:///app/login.html'), document_scope('file:///app/other.html'))
        self.assertEqual(document_scope('app://desktop/login'), 'app://desktop')
        self.assertEqual(document_scope('https://example.invalid:0/login'), 'https://example.invalid:0')


class SandboxedIdentity(unittest.TestCase):
    def test_flatpak_proxy_uses_its_namespace_identity_and_excludes_browsers_and_vaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); process=root/'45'; (process/'root').mkdir(parents=True)
            (process/'exe').symlink_to('/usr/bin/xdg-dbus-proxy')
            info=process/'root/.flatpak-info'
            info.write_text('[Application]\nname=org.example.Native\n')
            self.assertEqual(identify(45,root).scope,'flatpak:org.example.Native')
            for app in ('org.mozilla.firefox','app.zen_browser.zen','com.bitwarden.desktop','org.kde.konsole','bad'):
                info.write_text('[Application]\nname='+app+'\n')
                with self.assertRaises(ValueError): identify(45,root)
            info.write_text('[Application]\nname=org.example.Native\n#'+'x'*65536)
            with self.assertRaises(ValueError): identify(45,root)

    def test_shared_electron_executable_cannot_share_accounts_between_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); process=root/'45'; process.mkdir()
            (process/'exe').symlink_to('/opt/electron/electron')
            identities=[]
            for name in ('first.cjs','second.cjs'):
                path=root/name; path.touch()
                (process/'cmdline').write_bytes(b'electron\0--disable-gpu\0'+os.fsencode(path)+b'\0')
                identities.append(identify(45,root))
            self.assertNotEqual(identities[0].key,identities[1].key)
            (process/'cmdline').write_bytes(os.fsencode('/opt/electron/electron --disable-gpu '+str(root/'first.cjs'))+b'\0')
            self.assertEqual(identify(45,root),identities[0])
            (process/'cmdline').write_bytes(os.fsencode('/opt/electron/electron ambiguous '+str(root/'first.cjs'))+b'\0')
            with self.assertRaises(ValueError): identify(45,root)
            (process/'cmdline').write_bytes(b'electron\0--type=renderer\0')
            with self.assertRaises(ValueError): identify(45,root)


@unittest.skipUnless(os.environ.get('MONET_ELECTRON_BINARY'), 'explicit isolated Electron runtime')
class ElectronAccessibility(unittest.TestCase):
    run_cases = detector_fixtures.NativeDetector.run_cases
    def test_actual_electron_saving_and_unsupported_fill_is_not_offered(self):
        self.run_cases('app-login-electron.py', [('electron',mode) for mode in
                       ('unsupported-fill','save','changed-page','changed-action')])


@unittest.skipUnless(os.environ.get('MONET_SANDBOX_WIDGET_BINARY'), 'explicit isolated Flatpak runtime')
class FlatpakAccessibility(unittest.TestCase):
    run_cases = detector_fixtures.NativeDetector.run_cases
    def test_actual_sandboxed_gtk_fill_save_and_readonly_username(self):
        self.run_cases('app-login-widgets.py',[('flatpak',mode) for mode in ('fill','save','readonly')])


@unittest.skipUnless(os.environ.get('MONET_FLATPAK_INTEGRATION')=='1','explicit isolated Flatpak runtime')
class FlatpakElectronAccessibility(unittest.TestCase):
    run_cases = detector_fixtures.NativeDetector.run_cases
    def test_reversible_app_preference_exposes_electron_without_more_permissions(self):
        from unittest.mock import patch
        with patch.dict(os.environ,MONET_FLATPAK_FIXTURE='1',MONET_FLATPAK_SUPPORT_FIXTURE='1'):
            self.run_cases('app-login-electron.py',[('electron',mode) for mode in ('unsupported-fill','save','changed-page','changed-action')])
