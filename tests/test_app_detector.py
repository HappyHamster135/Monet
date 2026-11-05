"""Real native accessibility and conservative event/state boundaries."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest

from tests.test_app_logins import IDENTITY
from app_detector import Detector

ROOT = Path(__file__).resolve().parents[1]
ROLES = NS(PASSWORD_TEXT=1, TEXT=2, ENTRY=3, DOCUMENT_WEB=4, DOCUMENT_FRAME=5, PUSH_BUTTON=6, APPLICATION=7)
API = NS(Role=ROLES, StateType=NS(SHOWING='showing', EDITABLE='editable', ACTIVE='active'),
         Text=NS(get_text=lambda node, *_: node.value))


class Node:
    def __init__(self, role=0, name='', value='', parent=None):
        self.role, self.name, self.value, self.parent = role, name, value, parent
        self.children = []; self.states = {'showing', 'editable', 'active'}
        if parent: parent.children.append(self)
    def get_parent(self): return self.parent
    def get_role(self): return self.role
    def get_name(self): return self.name
    def get_state_set(self): return NS(contains=lambda name: name in self.states)
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, i): return self.children[i]
    def get_character_count(self): return len(self.value)
    def get_text_iface(self): return self
    def get_process_id(self): return 1
    def clear_cache_single(self): pass


class DetectorBoundaries(unittest.TestCase):
    def setUp(self):
        self.now, self.enabled = 0, True
        self.offers = []
        timers = NS(source_remove=lambda *_: None, timeout_add=lambda *_: 1, timeout_add_seconds=lambda *_: 2)
        self.detector = Detector(API, timers, lambda *args: self.offers.append(args), lambda _: self.enabled,
                                 resolver=lambda _: IDENTITY, clock=lambda: self.now)
        self.root = Node(parent=Node(role=ROLES.APPLICATION))
        self.user = Node(ROLES.TEXT, 'Username', 'demo', self.root)
        self.password = Node(ROLES.PASSWORD_TEXT, 'Password', 'synthetic', self.root)
        self.button = Node(ROLES.PUSH_BUTTON, 'Sign in', parent=self.root)

    def event(self, kind, source, value=1):
        self.detector.event(NS(type=kind, source=source, detail1=value))

    def focus(self, source): self.event('object:state-changed:focused', source)
    def hide(self):
        self.event('object:state-changed:showing', self.password, 0)
        self.detector.confirm_offer()

    def test_focus_or_button_focus_alone_never_prompts(self):
        self.focus(self.password); self.focus(self.button)
        self.assertEqual(self.offers, [])
        self.hide(); self.hide()
        self.assertEqual(len(self.offers), 1)
        self.assertEqual(self.offers[0][1]['password'], 'synthetic')

    def test_recent_edit_cannot_save_a_stale_partial_password(self):
        self.focus(self.password)
        self.password.value = 'synthetic-full'
        self.event('object:text-changed:insert', self.password)
        self.hide()
        self.assertEqual(self.offers[0][1]['password'], '')

    def test_other_window_cancel_and_expiry_discard_candidates(self):
        self.focus(self.password)
        self.focus(Node(parent=Node(parent=Node(role=ROLES.APPLICATION))))
        self.hide(); self.assertEqual(self.offers, [])
        self.focus(self.password); self.focus(Node(ROLES.PUSH_BUTTON, 'Cancel', parent=self.root))
        self.hide(); self.assertEqual(self.offers, [])
        self.focus(self.password); self.now = 91; self.hide()
        self.assertEqual(self.offers, [])

    def test_disable_unknown_username_and_embedded_browser_are_ignored(self):
        self.enabled = False; self.focus(self.password); self.hide()
        self.assertEqual(self.offers, [])
        self.enabled = True; self.user.name = 'Search'; self.focus(self.password); self.hide()
        self.assertEqual(self.offers, [])
        self.user.name = 'Username'; self.root.role = ROLES.DOCUMENT_WEB
        self.focus(self.password); self.hide(); self.assertEqual(self.offers, [])

    def test_only_removing_the_password_subtree_can_offer_a_login(self):
        self.focus(self.password)
        self.detector.event(NS(type='object:children-changed:remove', source=self.root, detail1=0, any_data=self.user))
        self.assertEqual(self.detector.submission_timer, 0)
        self.detector.event(NS(type='object:children-changed:remove', source=self.root, detail1=0, any_data=self.password))
        self.assertNotEqual(self.detector.submission_timer, 0)
        self.detector.confirm_offer()
        self.assertEqual(len(self.offers), 1)

    def test_closed_window_and_scan_limits_fail_closed(self):
        self.focus(self.password); self.root.states.remove('showing'); self.hide()
        self.assertEqual(self.offers, [])
        self.root.states.add('showing'); self.password.value = 'x' * 4097
        self.focus(self.password); self.hide(); self.assertEqual(self.offers, [])


@unittest.skipUnless(shutil.which('Xvfb') and os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1', 'isolated Xvfb accessibility fixture')
class NativeDetector(unittest.TestCase):
    def test_actual_qt_gtk_controls_and_changed_destinations(self):
        self.run_cases('app-login-widgets.py', [(toolkit, mode) for toolkit in ('qt', 'gtk3', 'gtk4')
                       for mode in ('fill', 'save', 'readonly', 'changed-server', 'changed-action')] + [('qt', 'steps')])

    def test_actual_qt_login_register_cancel_and_close(self):
        self.run_cases('app-login-form.py', [(mode,) for mode in ('login', 'register', 'change', 'cancel', 'close')])

    def run_cases(self, fixture, cases):
        reader, writer = os.pipe()
        display = subprocess.Popen(['Xvfb', '-displayfd', str(writer), '-screen', '0', '1280x800x24', '-nolisten', 'tcp'],
                                   pass_fds=(writer,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(writer)
        try:
            self.assertTrue(select.select([reader], [], [], 5)[0])
            number = os.read(reader, 100).decode().strip(); self.assertTrue(number.isdigit())
            env = dict(os.environ, DISPLAY=':' + number, QT_QPA_PLATFORM='xcb', QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1', GSK_RENDERER='cairo')
            for args in cases:
                with self.subTest(args=args):
                    result = subprocess.run(['dbus-run-session', '--', sys.executable,
                                             str(ROOT / 'tests/fixtures'/fixture), 'observe', *args],
                                            env=env, capture_output=True, text=True, timeout=12)
                    self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                    self.assertIn('PASS: ' + ' '.join(args), result.stdout)
        finally:
            os.close(reader); display.terminate(); display.wait(timeout=3)
