"""Optional session service: native app offers and conservative accessibility detection."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from app_logins import allowed, candidate, change_policy, config_path, identify, policy, valid_text

BUS_NAME = 'org.monet.PasswordOffers1'
BUS_PATH = '/org/monet/PasswordOffers1'
UNIT = 'monet-password-offers.service'


def status():
    prefs = policy()
    try:
        result = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', UNIT],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=3)
        running = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        running = False
    return {'enabled': prefs['enabled'], 'running': running,
            'ignored': len(prefs['ignored']), 'error': bool(prefs.get('error'))}


def configure(value):
    if value not in ('on', 'off', 'reset'): return {'ok': False}
    try:
        change_policy(enabled=None if value == 'reset' else value == 'on', reset=value == 'reset')
        if value != 'reset':
            command = ['systemctl', '--user', 'enable' if value == 'on' else 'disable', '--now', UNIT]
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=10)
            if result.returncode:
                # A failed start cannot leave a latent opt-in for next sign-in.
                if value == 'on': change_policy(enabled=False)
                return {'ok': False, 'state': status()}
        state = status()
        ok = not state['error'] and (value == 'reset' or state['running'] == (value == 'on'))
        if value == 'on' and not ok: change_policy(enabled=False); state = status()
        return {'ok': ok, 'state': state}
    except Exception:
        return {'ok': False, 'state': status()}


class Offers:
    def __init__(self, glib, prompt_command, screen_locked, permitted=allowed, clock=time.monotonic):
        self.glib, self.command, self.screen_locked, self.permitted = glib, prompt_command, screen_locked, permitted
        self.clock = clock
        self.child = None
        self.active = None
        self.busy = False
        self.generation = 0
        self.recent = {}
        self.salt = os.urandom(32)

    def cancel(self):
        self.generation += 1
        if self.child and self.child.poll() is None:
            try: self.child.terminate()
            except ProcessLookupError: pass
        self.active = None

    def offer(self, identity, values, reply=lambda status: None):
        if self.screen_locked() or not self.permitted(identity): reply('disabled'); return
        if self.busy: reply('busy'); return
        values = candidate(values)
        now = self.clock()
        self.recent = {k: deadline for k, deadline in self.recent.items() if deadline > now}
        digest = hashlib.sha256(self.salt + identity.key.encode() + json.dumps(values).encode()).digest()
        if digest in self.recent: reply('recent'); return
        self.recent[digest] = now + 30
        if len(self.recent) > 64: self.recent.pop(next(iter(self.recent)))
        self.run_prompt(identity, values, lambda result: reply(result['status']))

    def fill(self, identity, context, reply, validate=lambda: True, user_requested=False, activation_token=''):
        if self.screen_locked() or not self.permitted(identity) or not validate(): reply({'status': 'disabled'}); return
        if self.busy: reply({'status': 'busy'}); return
        context = candidate(context)
        if context['password'] or context['kind'] != 'login': reply({'status': 'invalid'}); return
        self.run_prompt(identity, context, reply, fill=True, validate=validate, user_requested=user_requested, activation_token=activation_token)

    def run_prompt(self, identity, values, reply, fill=False, validate=lambda: True, user_requested=False, activation_token=''):
        payload = json.dumps({'identity': asdict(identity), 'values': values, 'user_requested': user_requested}).encode()
        self.active, self.busy = identity, True
        generation = self.generation
        command = [*self.command[:-1], '--app-login-fill'] if fill else self.command
        environment = dict(os.environ)
        environment.pop('XDG_ACTIVATION_TOKEN', None)
        if valid_text(activation_token, 4096, False): environment['XDG_ACTIVATION_TOKEN'] = activation_token
        try:
            self.child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, close_fds=True, env=environment)
        except OSError:
            self.active, self.busy = None, False; reply({'status': 'unavailable'}); return
        child = self.child

        def wait():
            result = {'status': 'cancelled'}
            try:
                stdout, _ = child.communicate(payload, timeout=100)
                if child.returncode == 0 and len(stdout) <= 131072:
                    result = json.loads(stdout)
            except Exception:
                child.kill(); child.communicate()
            if not isinstance(result, dict) or result.get('status') not in ('saved', 'updated', 'unchanged', 'declined', 'ignored', 'filled'):
                result = {'status': 'cancelled'}
            if result['status'] == 'filled':
                try:
                    login = candidate(result['login'])
                    if not fill or not login['password'] or login['service'] != values['service'] or (
                            values['username'] and login['username'] != values['username']): raise ValueError()
                    result = {'status': 'filled', 'login': {k: login[k] for k in ('username', 'password', 'service')}}
                except Exception:
                    result = {'status': 'cancelled'}
            self.glib.idle_add(finished, result)

        def finished(result):
            self.child, self.active, self.busy = None, None, False
            # Recheck after the consent window closes; stale peers, locked screens,
            # revoked permission and changed forms must never receive credentials.
            if (generation != self.generation or self.screen_locked() or not self.permitted(identity) or not validate()):
                result = {'status': 'cancelled'}
            reply(result)
            return False

        threading.Thread(target=wait, name='app-login-consent', daemon=True).start()


def main(command):
    if not policy()['enabled']: return 0
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, Gio, GLib
    from app_detector import Detector

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()
    locked = [True]
    request_sender = [None]
    offers = Offers(GLib, [command, '--app-login-prompt'], lambda: locked[0])
    permitted = lambda app: not locked[0] and allowed(app)
    detector = Detector(Atspi, GLib, offers.offer, permitted, suspended=lambda: offers.busy)
    from app_suggestions import Suggestions
    suggestions = Suggestions(bus, GLib, offers, permitted)
    detector.suggest, detector.dismiss = suggestions.show, suggestions.dismiss

    def screen(active):
        locked[0] = bool(active)
        if active: detector.clear(); offers.cancel()

    def properties(interface, changes, invalidated):
        if interface == 'org.freedesktop.Secret.Collection' and (changes.get('Locked') or 'Locked' in invalidated):
            detector.clear(); offers.cancel()

    def owners(name, old, new):
        if name == request_sender[0] and old and not new:
            detector.clear(); offers.cancel()
        if name in ('org.freedesktop.ScreenSaver', 'org.freedesktop.secrets') and old:
            detector.clear(); offers.cancel()
            if name == 'org.freedesktop.ScreenSaver': locked[0] = True

    bus.add_signal_receiver(screen, signal_name='ActiveChanged', dbus_interface='org.freedesktop.ScreenSaver',
                            bus_name='org.freedesktop.ScreenSaver', path='/ScreenSaver')
    bus.add_signal_receiver(properties, signal_name='PropertiesChanged', dbus_interface='org.freedesktop.DBus.Properties',
                            bus_name='org.freedesktop.secrets')
    bus.add_signal_receiver(owners, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus',
                            bus_name='org.freedesktop.DBus')
    try:
        screen(bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver').GetActive(
            dbus_interface='org.freedesktop.ScreenSaver', timeout=2))
    except dbus.DBusException:
        return 1  # Unknown screen state must not expose a prompt on the lock screen.

    class Interface(dbus.service.Object):
        def caller(self, sender, document=None):
            pid = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus').GetConnectionUnixProcessID(
                sender, dbus_interface='org.freedesktop.DBus', timeout=2)
            identity = identify(pid)
            if document is not None:
                from app_documents import document_identity
                identity = document_identity(identity, str(document))
            return identity

        def request(self, username, service, sender, reply, document=None):
            try:
                if offers.busy:
                    reply({'status': 'busy'}); return
                identity = self.caller(sender, document)
                def same_caller():
                    try: return self.caller(sender, document) == identity
                    except Exception: return False
                def done(result):
                    if request_sender[0] == sender: request_sender[0] = None
                    response = {'status': result['status']}
                    if result['status'] == 'filled':
                        if same_caller(): response.update(result['login'])
                        else: response['status'] = 'cancelled'
                    reply(response)
                request_sender[0] = sender
                offers.fill(identity, {'username': str(username), 'service': str(service)}, done, validate=same_caller)
            except Exception:
                if request_sender[0] == sender: request_sender[0] = None
                reply({'status': 'unavailable'})

        @dbus.service.method(BUS_NAME, out_signature='a{sv}')
        def GetStatus(self):
            return {'enabled': policy()['enabled'], 'busy': offers.busy, 'screenLocked': locked[0]}

        @dbus.service.method(BUS_NAME, in_signature='ssss', out_signature='s',
                             sender_keyword='sender', async_callbacks=('reply', 'error'))
        def OfferLogin(self, username, password, service, kind, sender, reply, error):
            try:
                pid = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus').GetConnectionUnixProcessID(
                    sender, dbus_interface='org.freedesktop.DBus', timeout=2)
                identity = identify(pid)
                values = candidate(dict(username=str(username), password=str(password), service=str(service), kind=str(kind)))
                if not values['password']: reply('invalid'); return
                offers.offer(identity, values, reply)
            except Exception:
                reply('unavailable')  # Never put caller values or exceptions in replies/logs.

        @dbus.service.method(BUS_NAME, in_signature='ss', out_signature='a{ss}',
                             sender_keyword='sender', async_callbacks=('reply', 'error'))
        def RequestLogin(self, username, service, sender, reply, error):
            self.request(username, service, sender, reply)

        @dbus.service.method(BUS_NAME, in_signature='sss', out_signature='a{ss}',
                             sender_keyword='sender', async_callbacks=('reply', 'error'))
        def RequestDocumentLogin(self, document, username, service, sender, reply, error):
            # A cooperating app's trusted main process supplies its own document.
            # No renderer-provided app ID, PID or record key is accepted.
            self.request(username, service, sender, reply, document)

        @dbus.service.method(BUS_NAME, in_signature='sssss', out_signature='s',
                             sender_keyword='sender', async_callbacks=('reply', 'error'))
        def OfferDocumentLogin(self, document, username, password, service, kind, sender, reply, error):
            try:
                identity = self.caller(sender, document)
                values = candidate(dict(username=str(username), password=str(password), service=str(service), kind=str(kind)))
                if not values['password']: reply('invalid'); return
                offers.offer(identity, values, reply)
            except Exception:
                reply('unavailable')

    detector.start()
    name = dbus.service.BusName(BUS_NAME, bus, do_not_queue=True)
    interface = Interface(name, BUS_PATH)

    def config_changed(monitor, file, other, event):
        if file.get_basename() != 'app-logins.json' and (not other or other.get_basename() != 'app-logins.json'):
            return
        if offers.active and not allowed(offers.active): offers.cancel()
        detector.clear()
        if not policy()['enabled']:
            offers.cancel(); loop.quit()

    monitor = Gio.File.new_for_path(str(config_path().parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
    monitor.connect('changed', config_changed)
    import signal
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (offers.cancel(), loop.quit(), False)[-1])
    try:
        loop.run()
    finally:
        detector.clear(); offers.cancel(); monitor.cancel(); interface.remove_from_connection()
    return 0
