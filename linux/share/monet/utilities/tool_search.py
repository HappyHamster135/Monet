"""KRunner's D-Bus search provider. The first selection opens the actual tool."""
import json
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtCore import QSettings

from actions import ACTIONS, find_tools, preferences, tr, words

INTERFACE = "org.kde.krunner1"
SERVICE = "org.monet.ToolSearch"


class ToolSearch(dbus.service.Object):
    def __init__(self, bus, loop):
        super().__init__(bus, "/runner")
        self.bus = bus
        self.loop = loop
        self.settings = QSettings("Monet", "Utilities")
        self.tokens = {}
        self.prefixes = {"tools", words(tr("tools")), "monet tools", words(tr("Monet Utilities"))}
        self.timeout = 0
        self.touch()

    def touch(self):
        if self.timeout:
            GLib.source_remove(self.timeout)
        self.timeout = GLib.timeout_add_seconds(45, self.loop.quit)

    @dbus.service.method(INTERFACE, sender_keyword="sender")
    def Teardown(self, sender=None):
        self.tokens.pop(sender, None)

    @dbus.service.method(INTERFACE, out_signature="a(sss)")
    def Actions(self):
        self.touch()
        return []

    @dbus.service.method(INTERFACE, in_signature="s", out_signature="a(sssida{sv})")
    def Match(self, query):
        self.touch()
        query = words(query[:256])
        scoped = False
        for prefix in sorted(self.prefixes, key=len, reverse=True):
            if query == prefix or query.startswith(prefix + " "):
                scoped, query = True, query[len(prefix):].strip()
                break
        if not scoped and len(query) < 3:
            return []
        self.settings.sync()
        favorites, hidden = preferences(self.settings)
        matches = find_tools(query, favorites, hidden)
        if scoped and not query:
            matches = [(key, score) for key, score in matches if key in favorites]
            if not matches:
                return [("customize", tr("Choose favorite tools"), "configure", 70, 1.0,
                         {"category": tr("Monet Utilities")})]
        return [(key, ACTIONS[key].name, ACTIONS[key].icon, 70 if scoped or score >= 0.95 else 30,
                 score, {"category": tr("Monet Utilities")}) for key, score in matches[:8]]

    @dbus.service.method(INTERFACE, in_signature="s", sender_keyword="sender")
    def SetActivationToken(self, token, sender=None):
        self.touch()
        now = time.monotonic()
        self.tokens = {owner: item for owner, item in self.tokens.items() if item[1] > now}
        if token and len(token) <= 4096:
            self.tokens[sender] = (str(token), now + 5)

    @dbus.service.method(INTERFACE, in_signature="ss", sender_keyword="sender")
    def Run(self, key, action, sender=None):
        self.touch()
        token, expiry = self.tokens.pop(sender, ("", 0))
        self.settings.sync()
        _, hidden = preferences(self.settings)
        if action or (key != "customize" and (key not in ACTIONS or key in hidden)):
            return
        target = self.bus.get_object("org.monet.Utilities", "/Utilities", introspect=False)
        try:
            target.OpenTool(key, token if expiry > time.monotonic() else "",
                            dbus_interface="org.monet.Utilities", signature="ss")
        except dbus.DBusException as error:
            if error.get_dbus_name() != "org.freedesktop.DBus.Error.UnknownMethod":
                raise
            # An already-open Utilities window may predate this live update.
            target.Present(json.dumps(["tools" if key == "customize" else key]),
                           dbus_interface="org.monet.Utilities", signature="s")


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()
    runner = ToolSearch(bus, loop)
    name = dbus.service.BusName(SERVICE, bus=bus, do_not_queue=True)
    loop.run()
    runner.remove_from_connection()


if __name__ == "__main__":
    main()
