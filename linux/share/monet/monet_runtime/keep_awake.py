"""Temporary, connection-owned desktop inhibition without editing saved policy."""
import json
import math
import os
from pathlib import Path
import signal
import tempfile
import time

NAME = 'org.monet.KeepAwake'
PATH = '/org/monet/KeepAwake'
INTERFACE = NAME
POWER = ('org.kde.Solid.PowerManagement', '/org/kde/Solid/PowerManagement/PolicyAgent',
         'org.kde.Solid.PowerManagement.PolicyAgent')
SCREEN = ('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver')
XML = '''<node><interface name="org.monet.KeepAwake">
<method name="GetStatus"><arg type="s" direction="out"/></method>
<method name="SetDuration"><arg type="i" direction="in"/><arg type="s" direction="out"/></method>
</interface></node>'''


def boottime():
    # Includes explicit suspend, and is independent of wall-clock/time-zone changes.
    return time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time, 'CLOCK_BOOTTIME') else time.monotonic()


def marker_path():
    return Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'monet/keep-awake.json'


class Controller:
    def __init__(self, backend, clock=boottime):
        self.backend, self.clock = backend, clock
        self.duration, self.end, self.cookies, self.error = 0, 0., None, ''

    def status(self):
        remaining = max(0, math.ceil(self.end-self.clock())) if self.end else 0
        return dict(active=self.cookies is not None, duration=self.duration, end=self.end,
                    remaining=remaining, indefinite=self.duration == -1,
                    pending=bool(self.duration and self.cookies is None), error=self.error)

    def set_duration(self, seconds):
        if type(seconds) is not int or seconds not in (-1, 0) and not 1 <= seconds <= 86400:
            return dict(ok=False, state=self.status(), error='request')
        if seconds == 0:
            self.stop()
            return dict(ok=True, state=self.status())
        self.duration, self.end = seconds, self.clock()+seconds if seconds > 0 else 0.
        self.acquire()
        return dict(ok=self.cookies is not None, state=self.status(), error=self.error)

    def acquire(self):
        if self.cookies is not None:
            self.error = ''
            return
        try:
            self.cookies = self.backend.acquire()
            self.error = ''
        except (OSError, RuntimeError):
            self.cookies = None
            self.error = 'backend-unavailable'

    def backend_changed(self):
        # Release the surviving old cookie before reacquiring the pair. The backend
        # addresses unique owners, so an old number cannot release a new owner's cookie.
        self.release()
        if self.duration and not self.expired():
            self.acquire()

    def expired(self):
        if self.duration > 0 and self.clock() >= self.end:
            self.stop()
            return True
        return False

    def release(self):
        if self.cookies is not None:
            self.backend.release(self.cookies)
            self.cookies = None

    def stop(self):
        self.release()
        self.duration, self.end, self.error = 0, 0., ''


class DesktopBackend:
    def __init__(self, connection, Gio, GLib):
        self.connection, self.Gio, self.GLib = connection, Gio, GLib

    def call(self, endpoint, method, signature, values):
        try:
            result = self.connection.call_sync(*endpoint, method, self.GLib.Variant(signature, values),
                None, self.Gio.DBusCallFlags.NONE, 2500, None)
            return result.unpack()
        except self.GLib.Error as error:
            raise RuntimeError('Desktop inhibition service unavailable') from error

    def owner(self, service):
        return self.call(('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus'),
                         'GetNameOwner', '(s)', (service,))[0]

    def acquire(self):
        cookies = []
        try:
            # ChangeScreenSettings (4) implies InterruptSession (1) in PowerDevil.
            for endpoint, method, signature, args in [
                (POWER, 'AddInhibition', '(uss)', (5, 'Monet', 'Keep awake')),
                (SCREEN, 'Inhibit', '(ss)', ('Monet', 'Keep awake'))]:
                owner = self.owner(endpoint[0])
                cookie = self.call((owner, *endpoint[1:]), method, signature, args)[0]
                cookies.append((endpoint, owner, cookie))
                if self.owner(endpoint[0]) != owner:
                    raise RuntimeError('Inhibition owner changed')
        except (OSError, RuntimeError):
            self.release(cookies)
            raise
        return cookies

    def release(self, cookies):
        for endpoint, owner, cookie in reversed(cookies):
            try:
                method = 'ReleaseInhibition' if endpoint == POWER else 'UnInhibit'
                self.call((owner, *endpoint[1:]), method, '(u)', (cookie,))
            except (OSError, RuntimeError):
                pass  # Owner death itself releases the connection-owned inhibition.


def main():
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    backend = DesktopBackend(connection, Gio, GLib)
    owned = backend.call(('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus'),
                         'RequestName', '(su)', (NAME, 4))[0]
    if owned not in (1, 4):
        return 1
    loop = GLib.MainLoop()
    controller = Controller(backend)
    marker = marker_path()
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='awake-', dir=marker.parent)
    with os.fdopen(fd, 'w') as output:
        json.dump(dict(owner=connection.get_unique_name()), output)
    os.replace(temporary, marker)

    def quit_later():
        loop.quit()
        return False

    def method_call(bus, sender, path, interface, method, args, invocation):
        if method == 'GetStatus':
            if controller.expired():
                GLib.idle_add(quit_later)
            result = controller.status()
        elif method == 'SetDuration':
            result = controller.set_duration(args.unpack()[0])
            arm_expiry()
            if not controller.duration:
                GLib.idle_add(quit_later)
        else:
            invocation.return_dbus_error(INTERFACE+'.UnknownMethod', 'Unknown method')
            return
        invocation.return_value(GLib.Variant('(s)', (json.dumps(result),)))

    def owner_changed(bus, sender, path, interface, signal_name, parameters):
        service, old, new = parameters.unpack()
        if service in (POWER[0], SCREEN[0]) and controller.duration:
            controller.backend_changed()
            arm_expiry()
            if not controller.duration:
                GLib.idle_add(quit_later)

    timer = [None]
    def tick():
        if controller.expired():
            timer[0] = None
            loop.quit()
            return False
        return True

    def arm_expiry():
        if timer[0] is not None:
            GLib.source_remove(timer[0])
            timer[0] = None
        if controller.duration > 0:
            timer[0] = GLib.timeout_add_seconds(1, tick)

    info = Gio.DBusNodeInfo.new_for_xml(XML)
    registration = connection.register_object(PATH, info.interfaces[0], method_call, None, None)
    subscription = connection.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
        'NameOwnerChanged', '/org/freedesktop/DBus', None, Gio.DBusSignalFlags.NONE, owner_changed)
    for signum in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, quit_later)
    try:
        loop.run()
    finally:
        controller.stop()
        marker.unlink(missing_ok=True)
        connection.signal_unsubscribe(subscription)
        connection.unregister_object(registration)
        connection.flush_sync(None)
    return 0
