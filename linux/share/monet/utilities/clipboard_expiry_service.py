"""Event-driven clipboard expiry. Observe ownership changes without requesting data."""
import ctypes as C
import os
from pathlib import Path
import signal
import socket
import sys
import time

from gi.repository import Gio, GLib, GLibUnix

from clipboard_expiry import Policy, read_policy

SCREEN = "org.freedesktop.ScreenSaver"
LOGIN = "org.freedesktop.login1"
MANAGER = LOGIN + ".Manager"
LOGIN_PATH = "/org/freedesktop/login1"
CHANGE = C.CFUNCTYPE(None, C.c_int)


def notify(message):
    address = os.getenv("NOTIFY_SOCKET")
    if address:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(message.encode(), "\0" + address[1:] if address.startswith("@") else address)


class Watcher:
    def __init__(self):
        self.loop = GLib.MainLoop()
        self.lib = C.CDLL(str(Path(__file__).with_name("libmonetclipboard.so")))
        self.lib.clip_open_observer.argtypes = [CHANGE]
        self.callback = CHANGE(self.changed)
        self.timer = os.timerfd_create(time.CLOCK_BOOTTIME, flags=os.TFD_NONBLOCK | os.TFD_CLOEXEC)
        GLibUnix.fd_add_full(GLib.PRIORITY_DEFAULT, self.timer, GLib.IO_IN, self.timeout)
        self.copied_at = 0
        self.policy = Policy()
        self.has_item = False
        self.inhibitor = None
        self.subscriptions = []
        self.system = None
        self.failed = False
        fd = self.lib.clip_open_observer(self.callback)
        if fd < 0:
            raise RuntimeError("Wayland clipboard management is unavailable.")
        GLibUnix.fd_add_full(GLib.PRIORITY_DEFAULT, fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.dispatch)

    def dispatch(self, fd, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR) or self.lib.clip_dispatch() < 0:
            self.failed = True
            self.loop.quit()
            return False
        self.finish_if_disabled()
        return True

    def finish_if_disabled(self):
        # Keep an expired selection empty until the next copy replaces our marker.
        if not self.policy.enabled() and not self.lib.clip_retaining():
            self.loop.quit()

    def changed(self, present):
        self.has_item = bool(present)
        self.copied_at = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.arm_timer()

    def arm_timer(self):
        # Boot time includes suspend. This one-shot timer never wakes the laptop.
        deadline = 0
        if self.has_item and self.policy.seconds:
            deadline = self.copied_at + self.policy.seconds * 1_000_000_000
        os.timerfd_settime_ns(self.timer, flags=os.TFD_TIMER_ABSTIME, initial=deadline)

    def timeout(self, fd, condition):
        try:
            os.read(fd, 8)
        except BlockingIOError:
            return True  # A selection change already replaced this deadline.
        self.expire()
        return True

    def expire(self):
        if self.has_item and self.lib.clip_expire() < 0:
            self.failed = True
            self.loop.quit()

    def screen_changed(self, bus, sender, path, iface, name, values):
        if self.policy.lock and values.unpack() == (True,):
            self.expire()

    def release_inhibitor(self):
        if self.inhibitor is not None:
            os.close(self.inhibitor)
            self.inhibitor = None

    def inhibit(self):
        reply, files = self.system.call_with_unix_fd_list_sync(LOGIN, LOGIN_PATH, MANAGER, "Inhibit",
            GLib.Variant("(ssss)", ("sleep", "Monet Utilities", "Clear the current clipboard", "delay")),
            GLib.VariantType.new("(h)"), Gio.DBusCallFlags.NO_AUTO_START, 1200, None, None)
        self.inhibitor = files.get(reply.unpack()[0])

    def sleep_changed(self, bus, sender, path, iface, name, values):
        if not self.policy.sleep:
            return
        if values.unpack() == (True,):
            try:
                self.expire()
            finally:
                self.release_inhibitor()
        elif self.inhibitor is None:
            try:
                self.inhibit()
            except GLib.Error as error:
                self.fail(error)

    def login_changed(self, bus, sender, path, iface, name, values):
        if self.policy.sleep and values.unpack()[1]:
            self.fail("Login manager restarted.")

    def reset_subscriptions(self):
        for bus, sub in self.subscriptions:
            bus.signal_unsubscribe(sub)
        self.subscriptions.clear()
        self.release_inhibitor()

    def subscribe(self, bus, service, interface, path, name, handler, arg=None):
        sub = bus.signal_subscribe(service, interface, name, path, arg, Gio.DBusSignalFlags.NONE, handler)
        self.subscriptions.append((bus, sub))

    def apply(self):
        self.reset_subscriptions()
        previous = self.policy
        self.policy = read_policy()
        if self.policy.seconds and not previous.seconds:
            self.copied_at = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.arm_timer()
        if self.policy.lock:
            session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.subscribe(session, SCREEN, SCREEN, "/ScreenSaver", "ActiveChanged", self.screen_changed)
            try:
                state = session.call_sync(SCREEN, "/ScreenSaver", SCREEN, "GetActive", None,
                    GLib.VariantType.new("(b)"), Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
            except GLib.Error:
                # Plasma can start the locker after graphical-session.target.
                pass
            else:
                if state.unpack()[0]:
                    self.expire()
        if self.policy.sleep:
            self.system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.subscribe(self.system, LOGIN, MANAGER, LOGIN_PATH, "PrepareForSleep", self.sleep_changed)
            self.subscribe(self.system, "org.freedesktop.DBus", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                           "NameOwnerChanged", self.login_changed, LOGIN)
            self.inhibit()
            state = self.system.call_sync(LOGIN, LOGIN_PATH, "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", (MANAGER, "PreparingForSleep")), GLib.VariantType.new("(v)"),
                Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
            if state.unpack()[0]:
                self.expire()
                self.release_inhibitor()

    def fail(self, error):
        print(str(error), file=sys.stderr, flush=True)
        self.failed = True
        self.loop.quit()

    def reload(self):
        notify(f"RELOADING=1\nMONOTONIC_USEC={time.monotonic_ns() // 1000}")
        try:
            self.apply()
            notify("READY=1")
            self.finish_if_disabled()
        except (OSError, TypeError, ValueError, GLib.Error) as error:
            self.fail(error)
        return True

    def run(self):
        try:
            self.apply()
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, self.reload)
            notify("READY=1")
            if self.policy.enabled():
                self.loop.run()
        finally:
            self.reset_subscriptions()
            os.close(self.timer)
        return int(self.failed)


if __name__ == "__main__":
    try:
        sys.exit(Watcher().run())
    except (OSError, RuntimeError, TypeError, ValueError, GLib.Error) as exc:
        sys.exit(str(exc))
