"""KRunner's D-Bus search provider. The first selection opens the actual tool."""
import json
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtCore import QSettings

from actions import ACTIONS, SEARCH_HINTS, find_tools, preferences, tr, words

INTERFACE = "org.kde.krunner1"
SERVICE = "org.monet.ToolSearch"


class ToolSearch(dbus.service.Object):
    def __init__(self, bus, loop):
        super().__init__(bus, "/runner")
        self.bus = bus
        self.loop = loop
        self.settings = QSettings("Monet", "Utilities")
        self.tokens = {}
        self.menu_search = None
        self.script_searches = {}
        self.clip_search = None
        self.prefixes = {"tools", words(tr("tools")), "monet tools", words(tr("Monet Utilities"))}
        self.timeout = 0
        self.touch()

    def touch(self):
        if self.timeout:
            GLib.source_remove(self.timeout)
        self.timeout = GLib.timeout_add_seconds(45, self.idle)

    def idle(self):
        if any(search.running for search in self.script_searches.values()):
            return True
        self.loop.quit()
        return False

    def close_clip_search(self):
        if self.clip_search:
            self.clip_search.close()
            self.clip_search = None

    @dbus.service.method(INTERFACE, sender_keyword="sender")
    def Teardown(self, sender=None):
        self.tokens.pop(sender, None)
        if sender in self.script_searches:
            self.script_searches[sender].leave()
        self.menu_search = None
        self.close_clip_search()

    def desktop_search(self, sender):
        for name in ("org.kde.krunner", "org.kde.plasmashell"):
            try:
                if self.bus.get_name_owner(name) == sender:
                    return True
            except dbus.DBusException:
                continue
        return False

    @dbus.service.method(INTERFACE, out_signature="a(sss)")
    def Actions(self):
        self.touch()
        return []

    @dbus.service.method(INTERFACE, in_signature="s", out_signature="a(sssida{sv})", sender_keyword="sender",
                         async_callbacks=("reply", "error"))
    def Match(self, query, reply, error, sender=None):
        self.touch()
        if ":" in query:
            from command_search import command_query
            direct = command_query(str(query), self.prefixes)
            if direct and direct[0] == "script":
                self.close_clip_search()
                self.menu_search = None
                self.settings.sync()
                if len(query) > 8192 or "scripts" in preferences(self.settings)[1] or not self.desktop_search(sender):
                    if sender in self.script_searches:
                        self.script_searches[sender].leave()
                    reply([])
                    return
                if sender not in self.script_searches:
                    from script_search import ScriptSearch
                    self.script_searches[sender] = ScriptSearch(self.bus, self.settings)
                self.script_searches[sender].search(direct[1], reply)
                return
        if sender in self.script_searches:
            self.script_searches[sender].leave()
        reply(self.tool_matches(query, sender))

    def tool_matches(self, query, sender):
        raw = str(query[:256]).strip()
        query = words(raw)
        scoped = False
        for prefix in sorted(self.prefixes, key=len, reverse=True):
            if query == prefix or query.startswith(prefix + " "):
                scoped, query = True, query[len(prefix):].strip()
                break
        if not scoped and len(query) < 3:
            self.menu_search = None
            self.close_clip_search()
            return []
        self.settings.sync()
        favorites, hidden = preferences(self.settings)
        # Preserve punctuation in personal searches, including from the tools shortcut.
        if ":" in raw:
            from command_search import command_query, matches as command_matches
            direct = command_query(raw, self.prefixes)
            if direct and direct[0] == "menu":
                self.close_clip_search()
                if "command-bar" in hidden or not self.desktop_search(sender):
                    self.menu_search = None
                    return []
                if self.menu_search is None:
                    from menu_commands import MenuSearch
                    self.menu_search = MenuSearch(self.bus)
                return self.menu_search.matches(direct[1])
            self.menu_search = None
            if direct:
                if direct[0] == "clip" and "clipboard" not in hidden:
                    if self.clip_search is None:
                        from command_search import ClipboardSearch
                        self.clip_search = ClipboardSearch(self.bus)
                else:
                    self.close_clip_search()
                return command_matches(*direct, hidden, self.settings, self.clip_search)
        self.close_clip_search()
        self.menu_search = None
        matches = find_tools(query, favorites, hidden)
        if scoped and not query:
            matches = [(key, score) for key, score in matches if key in favorites]
            if not matches:
                return [("customize", tr("Choose favorite tools"), "configure", 70, 1.0,
                         {"category": tr("Monet Utilities")})]
        return [(key, ACTIONS[key].name, ACTIONS[key].icon, 70 if scoped or score >= 0.95 else 30,
                 score, {"category": tr("Monet Utilities"), "subtext": tr(SEARCH_HINTS[key]) if key in SEARCH_HINTS else ""})
                for key, score in matches[:8]]

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
        self.close_clip_search()
        token, expiry = self.tokens.pop(sender, ("", 0))
        self.settings.sync()
        _, hidden = preferences(self.settings)
        if not action and str(key).startswith("script/"):
            if "scripts" not in hidden and self.desktop_search(sender) and sender in self.script_searches:
                self.script_searches[sender].run(str(key))
            return
        if not action and str(key).startswith("menu/"):
            if "command-bar" not in hidden and self.desktop_search(sender):
                from menu_commands import MenuSearch
                from command_search import notify
                if not MenuSearch(self.bus).run(key):
                    notify(self.bus, tr("This menu command is no longer available."))
            self.menu_search = None
            return
        if not action and str(key).startswith(("snippet/", "clip/", "emoji/")):
            from command_search import copy_result
            copy_result(str(key), hidden, self.settings, self.bus)
            return
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
