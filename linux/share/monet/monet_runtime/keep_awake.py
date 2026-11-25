"""Temporary, connection-owned desktop inhibition without editing saved policy."""
import json
import math
import os
import signal
import time

from .awake_apps import SYSTEMD
from .awake_rules import KWIN, RuleMonitor
from . import awake_session

NAME = 'org.monet.KeepAwake'
PATH = '/org/monet/KeepAwake'
INTERFACE = NAME
POWER = ('org.kde.Solid.PowerManagement', '/org/kde/Solid/PowerManagement/PolicyAgent',
         'org.kde.Solid.PowerManagement.PolicyAgent')
SCREEN = ('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver')
XML = '''<node><interface name="org.monet.KeepAwake">
<signal name="StatusChanged"><arg type="s"/></signal>
<method name="GetStatus"><arg type="s" direction="out"/></method>
<method name="SetDuration"><arg type="i" direction="in"/><arg type="s" direction="out"/></method>
<method name="ReloadRules"><arg type="s" direction="out"/></method>
<method name="WindowsChanged"><arg type="s" direction="in"/></method>
</interface></node>'''


def boottime():
    # Includes explicit suspend, and is independent of wall-clock/time-zone changes.
    return time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time, 'CLOCK_BOOTTIME') else time.monotonic()


class Controller:
    def __init__(self, backend, clock=boottime, remember=None):
        self.backend, self.clock = backend, clock
        self.remember = remember
        self.duration, self.end, self.cookies, self.error = 0, 0., None, ''
        self.changed = lambda: None
        self.reasons = []
        self.watching = False
        self.rule_display = self.holding_display = False

    def status(self):
        remaining = max(0, math.ceil(self.end-self.clock())) if self.end else 0
        return dict(active=self.cookies is not None, duration=self.duration, end=self.end,
                    remaining=remaining, indefinite=self.duration == -1,
                    pending=bool((self.duration or self.reasons) and self.cookies is None), error=self.error,
                    reasons=self.reasons, display=self.holding_display, watching=self.watching)

    def set_duration(self, seconds):
        if type(seconds) is not int or seconds not in (-1, 0) and not 1 <= seconds <= 86400:
            return dict(ok=False, state=self.status(), error='request')
        end = self.clock() + seconds if seconds > 0 else 0.
        if self.remember:
            try:
                self.remember(seconds, end)
            except OSError:
                return dict(ok=False, state=self.status(), error='timer-storage')
        self.apply_manual(seconds, end)
        return dict(ok=not self.error, state=self.status(), error=self.error)

    def apply_manual(self, duration, end):
        self.duration, self.end = duration, end
        self.acquire()
        self.changed()

    def set_rules(self, reasons, display):
        if reasons == self.reasons and display == self.rule_display and not self.error:
            return
        self.reasons, self.rule_display = reasons, display
        self.acquire()
        self.changed()

    def acquire(self):
        if not (self.duration or self.reasons):
            self.release()
            self.error = ''
            return
        display = bool(self.duration or self.rule_display)
        if self.cookies is not None and self.holding_display == display:
            self.error = ''
            return
        try:
            cookies = self.backend.acquire() if display else self.backend.acquire(keep_display=False)
            self.release()
            self.cookies, self.holding_display = cookies, display
            self.error = ''
        except (OSError, RuntimeError):
            self.release()
            self.error = 'backend-unavailable'

    def backend_changed(self):
        # Release the surviving old cookie before reacquiring the pair. The backend
        # addresses unique owners, so an old number cannot release a new owner's cookie.
        self.release()
        if not self.expired():
            self.acquire()
            self.changed()

    def expired(self):
        if self.duration > 0 and self.clock() >= self.end:
            # Release on time even when the expired record cannot be deleted.
            if self.remember:
                try:
                    self.remember(0, 0.)
                except OSError:
                    pass
            self.apply_manual(0, 0.)
            return True
        return False

    def release(self):
        if self.cookies is not None:
            self.backend.release(self.cookies)
            self.cookies, self.holding_display = None, False

    def stop(self):
        self.release()
        self.duration, self.end, self.error = 0, 0., ''
        self.reasons = []


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

    def acquire(self, keep_display=True):
        cookies = []
        try:
            # ChangeScreenSettings (4) implies InterruptSession (1) in PowerDevil.
            requests = [(POWER, 'AddInhibition', '(uss)', (5 if keep_display else 1, 'Monet', 'Keep awake'))]
            if keep_display:
                requests.append((SCREEN, 'Inhibit', '(ss)', ('Monet', 'Keep awake')))
            for endpoint, method, signature, args in requests:
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


def timer_session(backend):
    # The unit removes its private directory on sign-out or an explicit stop.
    # A fallback worker on a lingering per-user bus needs a desktop identity.
    if str(awake_session.timer_path().parent) in os.environ.get('RUNTIME_DIRECTORY', '').split(':'):
        scope = 'managed'
    elif os.environ.get('XDG_SESSION_ID'):
        scope = 'login:' + os.environ['XDG_SESSION_ID']
    else:
        try:
            scope = 'compositor:' + backend.owner(KWIN)
        except RuntimeError:
            # Without a desktop identity, a later worker cannot prove this is
            # the same login. A manual timer still works for this process.
            scope = 'worker:' + backend.connection.get_unique_name()
    return [backend.connection.get_guid(), scope]


def main():
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    backend = DesktopBackend(connection, Gio, GLib)
    loop = GLib.MainLoop()
    session = timer_session(backend)
    controller = Controller(backend, remember=lambda duration, end: awake_session.save_timer(session, duration, end))

    def publish():
        connection.emit_signal(None, PATH, NAME, 'StatusChanged',
                               GLib.Variant('(s)', (json.dumps(controller.status()),)))
    controller.changed = publish
    monitor = RuleMonitor(backend, controller, Gio, GLib)

    def quit_later():
        loop.quit()
        return False

    def quit_if_idle():
        if not (controller.duration or monitor.rules):
            loop.quit()
        return False

    def method_call(bus, sender, path, interface, method, args, invocation):
        if method == 'GetStatus':
            if monitor.power_deadline and controller.clock() >= monitor.power_deadline:
                monitor.update()
            if controller.expired():
                arm_expiry()
                GLib.idle_add(quit_if_idle)
            result = controller.status()
        elif method == 'WindowsChanged':
            if not monitor.windows_changed(sender, args.unpack()[0]):
                invocation.return_dbus_error(INTERFACE+'.Denied', 'Unknown window observer')
                return
            invocation.return_value(GLib.Variant('()', ()))
            return
        elif method == 'ReloadRules':
            monitor.reload()
            result = controller.status()
            GLib.idle_add(quit_if_idle)
        elif method == 'SetDuration':
            result = controller.set_duration(args.unpack()[0])
            arm_expiry()
            if not controller.duration:
                GLib.idle_add(quit_if_idle)
        else:
            invocation.return_dbus_error(INTERFACE+'.UnknownMethod', 'Unknown method')
            return
        invocation.return_value(GLib.Variant('(s)', (json.dumps(result),)))

    def owner_changed(bus, sender, path, interface, signal_name, parameters):
        service, old, new = parameters.unpack()
        if service == SYSTEMD and monitor.rules.get('apps'):
            monitor.units.configure(monitor.rules['apps'])
            monitor.update()
        if service == KWIN and monitor.rules.get('apps'):
            monitor.watch_windows()
            monitor.update()
        if service in (POWER[0], SCREEN[0]) and (controller.duration or controller.reasons):
            controller.backend_changed()
            arm_expiry()
            if not controller.duration:
                GLib.idle_add(quit_if_idle)

    # A boottime deadline includes explicit suspend and needs no periodic wakeups.
    # Older portable Python builds use the existing clock check.
    deadline_fd = None
    if hasattr(os, 'timerfd_create') and hasattr(time, 'CLOCK_BOOTTIME'):
        deadline_fd = os.timerfd_create(time.CLOCK_BOOTTIME, flags=os.TFD_NONBLOCK | os.TFD_CLOEXEC)
    timer = None

    def tick(*_):
        nonlocal timer
        if deadline_fd is not None:
            os.read(deadline_fd, 8)
        timer = None
        if monitor.power_deadline and controller.clock() >= monitor.power_deadline:
            monitor.update()
        controller.expired()
        arm_expiry()
        return quit_if_idle()

    def arm_expiry():
        nonlocal timer
        if timer is not None:
            GLib.source_remove(timer)
            timer = None
        deadline = min((end for end in (controller.end, monitor.power_deadline) if end), default=0.)
        if deadline_fd is not None:
            os.timerfd_settime(deadline_fd, flags=os.TFD_TIMER_ABSTIME, initial=deadline)
        if deadline:
            if deadline_fd is None:
                # A whole-second GLib timer may coalesce two nearby deadlines.
                # Still recheck boottime after a resume on older Python versions.
                remaining_ms = math.ceil((deadline - controller.clock()) * 1000)
                timer = GLib.timeout_add(max(1, min(1000, remaining_ms)), tick)
            else:
                timer = GLib.io_add_watch(deadline_fd, GLib.PRIORITY_DEFAULT, GLib.IO_IN, tick)

    monitor.deadline_changed = arm_expiry
    info = Gio.DBusNodeInfo.new_for_xml(XML)
    registration = connection.register_object(PATH, info.interfaces[0], method_call, None, None)
    subscriptions = [connection.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
        'NameOwnerChanged', '/org/freedesktop/DBus', name, Gio.DBusSignalFlags.NONE, owner_changed)
        for name in (POWER[0], SCREEN[0], KWIN, SYSTEMD)]
    for signum in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, quit_later)

    # D-Bus can forward a waiting SetDuration request as soon as the name is owned.
    marker = awake_session.marker_path()
    with awake_session.startup_lock():
        owned = backend.call(('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus'),
                             'RequestName', '(su)', (NAME, 4))[0]
        if owned not in (1, 4):
            return 1
        previous = awake_session.saved_timer(session, controller.clock())
        awake_session.write_record(marker, dict(owner=connection.get_unique_name()))
    try:
        if previous:
            controller.apply_manual(*previous)
        monitor.reload()
        controller.expired()
        arm_expiry()
        # Activation can precede its requesting D-Bus method. An empty service
        # left after a crash or an abandoned request should exit on its own.
        GLib.timeout_add_seconds(5, quit_if_idle)
        loop.run()
    finally:
        monitor.deadline_changed = lambda: None
        if timer is not None:
            GLib.source_remove(timer)
        if deadline_fd is not None:
            os.close(deadline_fd)
        controller.stop()
        monitor.close()
        marker.unlink(missing_ok=True)
        for subscription in subscriptions:
            connection.signal_unsubscribe(subscription)
        connection.unregister_object(registration)
        connection.flush_sync(None)
    return 0
