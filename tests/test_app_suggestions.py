"""Notification consent, stale destinations, and secret lifetime boundaries."""
from types import SimpleNamespace as NS
import unittest

from tests.test_app_logins import IDENTITY, VALUES
from app_suggestions import Suggestions


class NotificationFlow(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.enabled = self.live = self.active = True
        self.calls, self.notifications, self.timers, self.writes = [], [], [], []
        self.offers = NS(busy=False, fill=lambda *a, **kw: self.calls.append((a, kw)))
        self.bus = NS(add_signal_receiver=lambda *a, **kw: None,
                      get_object=lambda *a: NS(CloseNotification=lambda *a, **kw: None))
        self.glib = NS(timeout_add=lambda _, callback: self.timers.append(callback))
        self.suggestions = Suggestions(self.bus, self.glib, self.offers, lambda _: self.enabled,
                                       known=lambda _: True, clock=lambda: self.now)
        self.suggestions.notify = lambda *args: self.notifications.append(args) or len(self.notifications)
        self.target = NS(identity=IDENTITY, window=object(), context={'username': '', 'service': ''},
                         valid=lambda active=True: self.live and self.enabled and (self.active or not active),
                         apply=lambda login: self.writes.append(dict(login)) or True)

    def test_focus_only_shows_a_quiet_hint_and_never_opens_the_vault(self):
        self.suggestions.show(self.target)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.calls, [])
        self.suggestions.show(self.target)
        self.assertEqual(len(self.notifications), 1)
        self.suggestions.action(999, 'fill')
        self.assertEqual(self.calls, [])
        self.suggestions.activated(1, 'fixture-activation-token')
        self.active = False  # Clicking the desktop notification can move focus.
        self.suggestions.action(1, 'fill')
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.calls[0][1]['user_requested'])
        self.assertEqual(self.calls[0][1]['activation_token'], 'fixture-activation-token')
        self.assertEqual(self.suggestions.activation_token, '')

    def test_unknown_app_and_stale_or_disabled_form_do_not_offer(self):
        self.suggestions.known = lambda _: False
        self.suggestions.show(self.target)
        self.assertEqual(self.notifications, [])
        self.suggestions.known = lambda _: True
        self.suggestions.show(self.target)
        self.live = False
        self.suggestions.action(1, 'fill')
        self.assertEqual(self.calls, [])

    def test_fill_waits_for_original_window_then_discards_its_secret(self):
        login = dict(VALUES)
        self.active = False
        self.suggestions.chosen(self.target, {'status': 'filled', 'login': login})
        self.assertTrue(self.timers[0]())
        self.assertEqual(self.writes, [])
        self.active = True
        self.assertFalse(self.timers[0]())
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(login, {})

    def test_lock_change_or_timeout_discards_secret_without_filling(self):
        for reason in ('lock', 'change', 'timeout'):
            with self.subTest(reason=reason):
                self.setUp()
                login = dict(VALUES)
                self.suggestions.chosen(self.target, {'status': 'filled', 'login': login})
                if reason == 'lock': self.enabled = False
                elif reason == 'change': self.live = False
                else: self.active = False; self.now = 3
                self.assertFalse(self.timers[0]())
                self.assertEqual(login, {})
                self.assertEqual(self.writes, [])


if __name__ == '__main__': unittest.main()
