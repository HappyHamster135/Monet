"""Search the menus published by the window behind the desktop launcher."""
from dataclasses import dataclass
import hashlib
import json
import time

import dbus
from gi.repository import GLib

from actions import tr, words
from command_search import result


@dataclass
class Command:
    path: tuple
    origin: tuple
    invoke: object
    shortcut: str = ""
    checked: bool = False
    route: tuple = ()
    resolve: object = None

    def key(self, window_id):
        # Keep window titles, menu labels and document names out of runner history IDs.
        payload = json.dumps([window_id, self.origin, self.path], ensure_ascii=False).encode()
        key = "menu/" + hashlib.sha256(payload).hexdigest()
        if self.route:
            key += "/" + ".".join(map(str, self.route))
        return key


def target_window(bus):
    try:
        kwin = bus.get_object("org.kde.KWin", "/MonetAppMenu", introspect=False)
        target = kwin.target(dbus_interface="org.monet.AppMenuTarget", timeout=.4)
        return dict(target) if target.get("id") and target.get("pid", 0) > 0 else {}
    except dbus.DBusException:
        return {}


def exported_menu(bus, window):
    service, path = window["service"], window["path"]
    if not service or not path:
        return None
    try:
        owner = bus.get_name_owner(service)
        owner_pid = bus.call_blocking("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                      "GetConnectionUnixProcessID", "s", (owner,), timeout=.4)
        if owner_pid != window["pid"]:
            from last_window import app_scope
            scope = app_scope(owner_pid)
            if not scope or scope != app_scope(window["pid"]):
                return None
        menu = dbus.Interface(bus.get_object(owner, path, introspect=False), "com.canonical.dbusmenu")
        properties = ["label", "type", "enabled", "visible", "children-display", "shortcut", "toggle-state"]
        def layout(number):
            return menu.GetLayout(number, -1, properties, signature="iias", timeout=.45)[1]

        entries = []
        deadline = time.monotonic() + .65
        def visit(node, parents):
            number, props, children = node
            if not props.get("enabled", True) or not props.get("visible", True) or props.get("type") == "separator":
                return
            label = str(props.get("label", "")).replace("__", "\x00").replace("_", "").replace("\x00", "_").strip()
            names = (*parents, label) if label else parents
            if not children and props.get("children-display") == "submenu" and time.monotonic() < deadline:
                try:
                    if menu.AboutToShow(number, timeout=.25):
                        children = layout(number)[2]
                except dbus.DBusException:
                    pass
            if children:
                for child in children:
                    visit(child, names)
            elif label and number > 0 and props.get("children-display") != "submenu":
                keys = props.get("shortcut") or []
                shortcut = "+".join(keys[0]) if keys else ""
                def activate():
                    menu.Event(number, "clicked", dbus.Int32(0, variant_level=1), dbus.UInt32(0), timeout=.5)
                entries.append(Command(names, (owner, path, int(number)), activate, shortcut, props.get("toggle-state") == 1))
        visit(layout(0), ())
        return entries
    except (dbus.DBusException, ValueError):
        return None


def accessible_menu(window, route=()):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi

    Atspi.set_timeout(300, 500)
    role, state = Atspi.Role, Atspi.StateType
    containers = {role.ROOT_PANE, role.LAYERED_PANE, role.PANEL, role.FILLER, role.GROUPING, role.SPLIT_PANE,
                  role.TOOL_BAR, role.REDUNDANT_OBJECT, role.GLASS_PANE}
    wrappers = {role.MENU_BAR, role.POPUP_MENU}
    leaves = {role.MENU_ITEM, role.CHECK_MENU_ITEM, role.RADIO_MENU_ITEM}
    menus = wrappers | leaves | {role.MENU}
    deadline = time.monotonic() + 2

    def children(node, indices=()):
        count = node.get_child_count()
        for i in indices or range(count):
            if time.monotonic() > deadline:
                raise TimeoutError
            if i < count:
                child = node.get_child_at_index(i)
                if child:
                    yield i, child

    def frames():
        desktop = Atspi.get_desktop(0)
        if not desktop:
            return []
        title = window["title"].split()  # KWin simplifies whitespace in captions.
        for _, app in children(desktop):
            try:
                pid = app.get_process_id()
            except GLib.Error:
                continue
            if pid != window["pid"]:
                continue
            if route:
                app.clear_cache_single()
            found = []
            for _, node in children(app):
                if route:
                    node.clear_cache_single()
                if node.get_role() in (role.WINDOW, role.FRAME, role.DIALOG) and node.get_name().split() == title:
                    found.append(node)
            return found
        return []

    def available(node):
        flags = node.get_state_set()
        return flags.contains(state.ENABLED) or flags.contains(state.SENSITIVE)

    def resolve(node, names, indices):
        if not node.get_action_iface():
            return None
        for i in range(node.get_n_actions()):
            action = Atspi.Action.get_action_name(node, i).casefold()
            if action in ("click", "press", "activate", "toggle"):
                keys = Atspi.Action.get_key_binding(node, i) or ""
                return Command(names, (node.app.bus_name, node.path, action),
                               lambda: Atspi.Action.do_action(node, i), keys.split(";")[-1],
                               node.get_state_set().contains(state.CHECKED), indices)
        return None

    entries = []

    def visit(node, names, indices, in_menu=False):
        if route:
            node.clear_cache_single()
        kind = node.get_role()
        if not in_menu and kind != role.MENU_BAR:
            if kind not in containers:
                return
        elif kind in menus:
            in_menu = True
            if not available(node):
                return
            if kind not in wrappers:
                label = node.get_name()
                if label:
                    names = (*names, label)
                if kind in leaves and not node.get_child_count():
                    if not label or (route and route != indices):
                        return
                    # Looking up action names and shortcuts costs IPC. Resolve only the visible results.
                    entries.append(Command(names, (), None, resolve=lambda: resolve(node, names, indices)))
                    return
        else:
            return
        if not route or len(indices) < len(route):
            for i, child in children(node, route[len(indices):len(indices) + 1]):
                visit(child, names, (*indices, i), in_menu)

    try:
        matched = frames()
        # Refuse ambiguous same-process windows instead of guessing from focus flags in the launcher.
        if len(matched) == 1:
            for i, child in children(matched[0], route[:1]):
                visit(child, (), (i,))
    except (GLib.Error, TimeoutError):
        pass
    return entries


def resolved(entry):
    if entry.resolve:
        try:
            return entry.resolve()
        except GLib.Error:
            return None
    return entry


class MenuSearch:
    def __init__(self, bus):
        self.bus = bus
        self.window = {}
        self.entries = []
        self.expires = 0

    def read(self, window):
        self.entries = []
        if window:
            entries = exported_menu(self.bus, window)
            self.entries = accessible_menu(window) if entries is None else entries
        self.window = window
        self.expires = time.monotonic() + (5.0 if self.entries else .4)

    def matches(self, query):
        window = target_window(self.bus)
        if window != self.window or time.monotonic() >= self.expires:
            self.read(window)
        needle = words(query)
        tokens = needle.split()
        ranked = []
        for entry in self.entries:
            label = words(entry.path[-1])
            full = words(" ".join(entry.path))
            if all(token in full for token in tokens):
                if label == needle:
                    rank = 0
                elif label.startswith(needle):
                    rank = 1
                elif all(term in label for term in tokens):
                    rank = 2
                else:
                    rank = 3
                ranked.append((rank, entry))
        rows = []
        for _, candidate in sorted(ranked, key=lambda pair: pair[0]):
            entry = resolved(candidate)
            if not entry:
                continue
            detail = [window["title"], " › ".join(entry.path[:-1]), entry.shortcut]
            rows.append(result(entry.key(window["id"]), entry.path[-1], "dialog-ok-apply" if entry.checked else "application-menu",
                               tr("App menu"), " · ".join(filter(None, detail)), 1.0 - .01 * len(rows)))
            if len(rows) == 10:
                break
        return rows

    def run(self, key):
        window = target_window(self.bus)
        if not window:
            return False
        parts = key.split("/")
        if len(parts) == 2:
            entries = exported_menu(self.bus, window) or []
        elif len(parts) == 3 and len(parts[2]) <= 128:
            indices = parts[2].split(".")
            if len(indices) > 32 or not all(i.isascii() and i.isdecimal() for i in indices):
                return False
            entries = accessible_menu(window, tuple(map(int, indices)))
        else:
            return False
        for candidate in entries:
            entry = resolved(candidate)
            if entry and entry.key(window["id"]) == key and target_window(self.bus) == window:
                try:
                    return entry.invoke() is not False
                except (dbus.DBusException, GLib.Error):
                    return False
        return False
