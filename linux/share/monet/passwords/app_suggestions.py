"""Quiet, transient autofill suggestions. A notification never contains a credential."""
import html
import time

from app_logins import known_app, valid_text


class Suggestions:
    def __init__(self, bus, glib, offers, permitted, known=known_app, clock=time.monotonic):
        self.bus, self.glib, self.offers, self.permitted, self.known, self.clock = bus, glib, offers, permitted, known, clock
        self.target = None
        self.identifier = 0
        self.recent = {}
        self.activation_token = ''
        bus.add_signal_receiver(self.action, signal_name='ActionInvoked', dbus_interface='org.freedesktop.Notifications', bus_name='org.freedesktop.Notifications')
        bus.add_signal_receiver(self.activated, signal_name='ActivationToken', dbus_interface='org.freedesktop.Notifications', bus_name='org.freedesktop.Notifications')
        bus.add_signal_receiver(self.closed, signal_name='NotificationClosed', dbus_interface='org.freedesktop.Notifications', bus_name='org.freedesktop.Notifications')

    def notify(self, title, detail, actions, timeout=8000):
        import dbus
        return int(self.bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications').Notify(
            'Monet Passwords', 0, 'monet-passwords', title, detail, dbus.Array(actions, signature='s'),
            dbus.Dictionary({'transient': True, 'suppress-sound': True, 'desktop-entry': 'monet-passwords'}, signature='sv'),
            timeout, dbus_interface='org.freedesktop.Notifications', timeout=2))

    def show(self, target):
        if self.offers.busy or not self.known(target.identity) or not target.valid(): return
        now = self.clock()
        self.recent = {k: t for k, t in self.recent.items() if t > now}
        key = (target.identity.key, hash(target.window))
        if key in self.recent: return
        self.dismiss()
        try:
            from gettext import translation
            tr = translation('monet', fallback=True).gettext
            self.identifier = self.notify(tr('Use a saved app login?'), html.escape(target.identity.name),
                                          ['fill', tr('Choose account')])
            self.target = target
            self.recent[key] = now + 30
            if len(self.recent) > 64: self.recent.pop(next(iter(self.recent)))
        except Exception:
            self.target = None

    def dismiss(self):
        identifier, self.identifier, self.target = self.identifier, 0, None
        self.activation_token = ''
        if identifier:
            try:
                self.bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications').CloseNotification(
                    identifier, dbus_interface='org.freedesktop.Notifications', timeout=2)
            except Exception: pass

    def activated(self, identifier, token):
        if int(identifier) == self.identifier and valid_text(str(token), 4096, False):
            self.activation_token = str(token)

    def closed(self, identifier, reason):
        if int(identifier) == self.identifier:
            self.identifier, self.target, self.activation_token = 0, None, ''

    def action(self, identifier, action):
        if int(identifier) != self.identifier or action != 'fill': return
        target, token = self.target, self.activation_token
        self.dismiss()
        if not target or not target.valid(active=False): return
        self.offers.fill(target.identity, target.context, lambda result: self.chosen(target, result),
                         validate=lambda: target.valid(active=False), user_requested=True, activation_token=token)

    def chosen(self, target, result):
        if result.get('status') != 'filled': return
        login = result['login']
        deadline = self.clock() + 2
        def failed():
            if not self.permitted(target.identity): return
            try:
                from gettext import translation
                tr = translation('monet', fallback=True).gettext
                self.notify(tr('The app login could not be filled'),
                            tr('Return to the login form and choose your account again.'), [], 5000)
            except Exception: pass
        def apply():
            if not self.permitted(target.identity) or not target.valid(active=False):
                login.clear(); failed(); return False
            if target.valid():
                success = target.apply(login); login.clear()
                if not success: failed()
                return False
            if self.clock() >= deadline:
                login.clear(); failed(); return False
            return True
        # Closing the native picker returns focus to the original app. Never
        # force another window forward or send credentials into a different form.
        self.glib.timeout_add(50, apply)
