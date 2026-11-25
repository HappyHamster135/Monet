"""Resolve and deliver an opted-in application's Quit action after KWin confirms the last window is gone."""
import configparser
import gettext
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import signal
import time
from xml.etree import ElementTree

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from close_rules import applications, settings
from local_ports import desktop_entry, process

NAME = "org.monet.QuitOnClose"
PATH = "/org/monet/QuitOnClose"
PROPS = "org.freedesktop.DBus.Properties"
MPRIS = "org.mpris.MediaPlayer2"
MENU = "com.canonical.dbusmenu"
GTK = "org.gtk.Actions"


def interface(bus, owner, path, name):
    return dbus.Interface(bus.get_object(owner, path, introspect=False), name)


def property_of(bus, owner, path, name, key):
    return interface(bus, owner, path, PROPS).Get(name, key, timeout=.4)


def app_scope(pid):
    """Only a per-launch app scope may link a sandbox proxy to a window."""
    try:
        cg = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
        return next(p[3:] for p in cg if p.startswith("0::") and
                    re.fullmatch(r"app-.+[-@][a-fA-F0-9]{8,64}\.(?:scope|service)", p.rsplit("/", 1)[-1]))
    except (StopIteration, OSError, UnicodeError):
        return ""


def menu_quit_id(layout):
    labels = {"quit", "exit"}
    for domain in ("gtk40", "gtk30", "kxmlgui6"):
        for msg in ("_Quit", "&Quit", "Quit", "Exit"):
            labels.add(gettext.dgettext(domain, msg).replace("_", "").replace("&", "").strip().casefold())
    found = []
    def visit(node):
        number, props, children = node
        if not props.get("visible", True) or not props.get("enabled", True):
            return
        label = str(props.get("label", "")).replace("_", "").replace("&", "").strip().casefold()
        if number > 0 and not children and (label in labels or props.get("icon-name") in ("application-exit", "gtk-quit")):
            found.append(int(number))
        for child in children:
            visit(child)
    visit(layout)
    return found[0] if len(found) == 1 else None


def absent(error):
    # A hung application or a denied request does not establish that it
    # lacks a Quit action. Never escalate those failures to a Unix signal.
    return error.get_dbus_name().rsplit(".", 1)[-1] in {
        "UnknownMethod", "UnknownInterface", "UnknownObject", "UnknownProperty",
        "InvalidArgs", "NameHasNoOwner", "ServiceUnknown",
    }


def native_quit(bus, owner, name):
    # Desktop applications commonly publish a GApplication action or a Qt
    # /MainApplication quit method. Address the unique owner in both cases.
    path = "/" + name.replace(".", "/").replace("-", "_")
    try:
        obj = interface(bus, owner, path, GTK)
        enabled, parameter, _ = obj.Describe("quit", timeout=.4)
        if enabled and not parameter:
            return lambda: obj.Activate("quit", dbus.Array([], signature="v"), dbus.Dictionary({}, signature="sv"), timeout=.5)
    except dbus.DBusException as error:
        if not absent(error):
            raise
    path = "/MainApplication"
    try:
        xml = interface(bus, owner, path, "org.freedesktop.DBus.Introspectable").Introspect(timeout=.4)
        for iface in ElementTree.fromstring(xml).findall("interface"):
            for method in iface.findall("method"):
                if method.get("name") == "quit" and not method.findall("arg[@direction='in']") and not any(
                        arg.get("direction") is None for arg in method.findall("arg")):
                    obj = interface(bus, owner, path, iface.get("name"))
                    return lambda: obj.quit(timeout=.5)
    except dbus.DBusException as error:
        if not absent(error):
            raise
    return None


def resolve(bus, entry, pid):
    scope = app_scope(pid)
    daemon = interface(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus")
    def owned(service):
        try:
            owner = service if service.startswith(":") else str(bus.get_name_owner(service))
            peer = int(daemon.GetConnectionUnixProcessID(owner, timeout=.4))
            if peer == pid or (scope and app_scope(peer) == scope):
                return owner
        except dbus.DBusException as error:
            if not absent(error):
                raise
        return None

    names = bus.list_names()
    app_id = entry.get_id().removesuffix(".desktop")
    prefixes = {n for n in (app_id, entry.get_string("X-DBUS-ServiceName")) if n}
    for name in names:
        if not any(name == base or name.startswith(base + "-") for base in prefixes):
            continue
        owner = owned(name)
        if owner and (quit_action := native_quit(bus, owner, str(name))):
            return quit_action
    for name in names:
        if not name.startswith(MPRIS + ".") or not (owner := owned(name)):
            continue
        try:
            path = "/org/mpris/MediaPlayer2"
            if property_of(bus, owner, path, MPRIS, "CanQuit"):
                player = interface(bus, owner, path, MPRIS)
                return lambda: player.Quit(timeout=.5)
        except dbus.DBusException as error:
            if not absent(error):
                raise
    watcher = "org.kde.StatusNotifierWatcher"
    if watcher not in names:
        return None
    items = property_of(bus, bus.get_name_owner(watcher), "/StatusNotifierWatcher", watcher, "RegisteredStatusNotifierItems")
    for item in items:
        service, _, tail = str(item).partition("/")
        if not (owner := owned(service)):
            continue
        try:
            path = property_of(bus, owner, "/" + (tail or "StatusNotifierItem"), "org.kde.StatusNotifierItem", "Menu")
            menu = interface(bus, owner, path, MENU)
            # Dynamic menus may populate their actions only when opened.
            try:
                menu.AboutToShow(0, timeout=.4)
            except dbus.DBusException as error:
                if not absent(error):
                    raise
            _, tree = menu.GetLayout(0, 2, ["label", "icon-name", "enabled", "visible"], timeout=.4)
            number = menu_quit_id(tree)
            if number is not None:
                return lambda: menu.Event(number, "clicked", dbus.Int32(0, variant_level=1), dbus.UInt32(0), timeout=.5)
        except dbus.DBusException as error:
            if not absent(error):
                raise
    return None


def matches_executable(entry, pid):
    # Generic launchers can run many unrelated apps. A Flatpak sandbox or a
    # dedicated native executable provides a stronger identity for SIGTERM.
    try:
        info = Path(f"/proc/{pid}/root/.flatpak-info")
        if info.exists():
            config = configparser.ConfigParser(interpolation=None)
            config.read(info)
            return config.get("Application", "name", fallback="") + ".desktop" == entry.get_id()
        exe = shutil.which(entry.get_executable() or "")
        generic = r"(?:.*sh|env|python[\d.]*|perl|ruby|node|electron[\d.-]*|java|wine.*|flatpak|snap|gtk-launch|xdg-open|gio|mono|dotnet|busybox|systemd-run)"
        if not exe or any(re.fullmatch(generic, name, re.I) for name in (Path(exe).name, Path(exe).resolve().name)):
            return False
        return Path(exe).samefile(f"/proc/{pid}/exe")
    except (OSError, ValueError, configparser.Error):
        return False


class Service(dbus.service.Object):
    def __init__(self, bus, loop):
        self.bus = bus
        self.loop = loop
        self.pending = {}
        self.timer = None
        super().__init__(bus, PATH)
        self.touch()

    def touch(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add_seconds(8, self.idle)
        now = time.monotonic()
        for key, (deadline, fd, *_) in list(self.pending.items()):
            if now > deadline:
                self.pending.pop(key)
                os.close(fd)

    def idle(self):
        self.loop.quit()
        return False

    def authorized(self, sender):
        return (self.bus.name_has_owner("org.kde.KWin") and sender == self.bus.get_name_owner("org.kde.KWin")
                and not self.bus.name_has_owner("org.kde.Shutdown"))

    @dbus.service.method(NAME, in_signature="sss", out_signature="s", sender_keyword="sender")
    def Prepare(self, desktop, pid, closed_at, sender=None):
        self.touch()
        try:
            pid, closed_at = int(pid), int(closed_at)
        except ValueError:
            return ""
        config = settings()
        if not self.authorized(sender) or pid <= 1 or desktop not in applications(config):
            return ""
        entry = desktop_entry(str(desktop))
        if entry is None:
            return ""
        fd = None
        try:
            fd = os.pidfd_open(pid)
            proc = process(pid)
            # A PID allocated after this window closed cannot own it.
            age = time.clock_gettime(time.CLOCK_BOOTTIME) - proc.start / os.sysconf("SC_CLK_TCK") if proc else -1
            if not proc or proc.uid != os.getuid() or age < max(0, time.time() - closed_at / 1000):
                return ""
            action = resolve(self.bus, entry, pid)
            if not action and not (config.value("terminate", False, type=bool) and matches_executable(entry, pid)):
                return ""
            key = secrets.token_hex(16)
            self.pending[key] = (time.monotonic() + 3, fd, str(desktop), action, pid)
            fd = None
            return key
        except (OSError, dbus.DBusException, ValueError, ElementTree.ParseError):
            return ""
        finally:
            if fd is not None:
                os.close(fd)

    @dbus.service.method(NAME, in_signature="s", out_signature="", sender_keyword="sender")
    def Confirm(self, key, sender=None):
        if not self.authorized(sender):
            return
        self.touch()
        match = self.pending.pop(str(key), None)
        if match is None:
            return
        _, fd, desktop, action, pid = match
        try:
            system = dbus.SystemBus()
            if system.name_has_owner("org.freedesktop.login1") and property_of(
                    system, "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "PreparingForShutdown"):
                return
            config = settings()
            if desktop not in applications(config) or select.select([fd], [], [], 0)[0]:
                return
            if action:
                action()
            elif config.value("terminate", False, type=bool):
                entry = desktop_entry(desktop)
                if entry and matches_executable(entry, pid):
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
        except (OSError, dbus.DBusException, ValueError):
            pass
        finally:
            os.close(fd)


if __name__ == "__main__":
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()
    name = dbus.service.BusName(NAME, bus, do_not_queue=True)
    service = Service(bus, loop)
    loop.run()
