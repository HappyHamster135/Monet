"""Open Files' own shortcut editor at the Rename action."""
import os
import re
import subprocess
import time
from xml.etree import ElementTree

import dbus

WINDOW = "org.kde.dolphin.MainWindow"
ACTIONS = "org.kde.KMainWindow"
SHORTCUTS = "options_configure_keybinding"


def file_windows(bus):
    windows = []
    for name in bus.list_names():
        match = re.fullmatch(r"org\.kde\.dolphin-([0-9]+)", name)
        if not match:
            continue
        try:
            owner = bus.get_name_owner(name)
            parent = bus.get_object(owner, "/dolphin", introspect=False)
            xml = parent.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable", timeout=.4)
            if len(xml) > 65536:
                continue
            pid = int(match[1])
            for child in ElementTree.fromstring(xml).findall("node"):
                ident = child.get("name", "")
                if re.fullmatch(r"Dolphin_[0-9]+", ident):
                    window = bus.get_object(owner, "/dolphin/" + ident, introspect=False)
                    windows.append((pid, window))
        except (dbus.DBusException, ElementTree.ParseError):
            continue  # A Files window may close during discovery.
    return windows


def choose_window(bus, windows):
    for pid, window in windows:
        try:
            if window.isActiveWindow(dbus_interface=WINDOW, timeout=.3):
                return pid, window
        except dbus.DBusException:
            continue
    if windows:
        return windows[0]
    child = subprocess.Popen(["dolphin", "--new-window"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    until = time.monotonic() + 8
    while time.monotonic() < until:
        windows = file_windows(bus)
        if windows:
            return windows[0]
        if child.poll() not in (None, 0):
            break
        time.sleep(.1)
    return None, None


def shortcut_dialog(atspi, pids):
    desktop = atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app.get_process_id() in pids:
            for j in range(app.get_child_count()):
                frame = app.get_child_at_index(j)
                if frame.get_role() == atspi.Role.DIALOG and frame.get_accessible_id().endswith(".KShortcutsDialog"):
                    return frame
    return None


def raise_editor(bus, dialog):
    # The native shortcut editor is a separate Wayland surface. Activating
    # its parent can leave the editor behind the Utilities catalog.
    title = dialog.get_name()
    pid = dialog.get_process_id()
    runner = dbus.Interface(bus.get_object("org.kde.KWin", "/WindowsRunner", introspect=False), "org.kde.krunner1")
    kwin = dbus.Interface(bus.get_object("org.kde.KWin", "/KWin", introspect=False), "org.kde.KWin")
    for key, caption, *_ in runner.Match(title, timeout=.5):
        action, _, ident = key.partition("_")
        if action == "0" and caption == title:
            info = kwin.getWindowInfo(ident, timeout=.5)
            if info.get("pid") == pid and info.get("hasTransientParent") and info.get("caption") == title:
                runner.Run(key, "", timeout=.5)
                return True
    return False


def filter_rename(atspi, dialog, label):
    # KDE exposes this editor by ID regardless of language. Leave any search
    # the user has already typed alone, and never send keys to the desktop.
    def search(node, depth):
        if node.get_accessible_id().endswith(".searchFilter.KTreeWidgetSearchLine"):
            return node
        if depth < 4 and node.get_role() not in (atspi.Role.TREE, atspi.Role.TABLE, atspi.Role.TREE_TABLE):
            for i in range(min(24, node.get_child_count())):
                result = search(node.get_child_at_index(i), depth + 1)
                if result:
                    return result
        return None
    field = search(dialog, 0)
    if field and field.get_text_iface().get_character_count() == 0:
        field.get_editable_text_iface().set_text_contents(label)


def open_editor():
    bus = dbus.SessionBus()
    if bus.request_name("org.monet.FilesRenameShortcut", dbus.bus.NAME_FLAG_DO_NOT_QUEUE) != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
        return True
    windows = file_windows(bus)
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi, GLib
        Atspi.set_timeout(200, 400)
    except (ImportError, ValueError):
        Atspi = None
    if windows and Atspi:
        try:
            existing = shortcut_dialog(Atspi, {pid for pid, _ in windows})
            if existing:
                if not existing.get_state_set().contains(Atspi.StateType.ACTIVE):
                    try:
                        raised = raise_editor(bus, existing)
                    except dbus.DBusException:
                        raised = False
                    if not raised:
                        existing.get_component_iface().grab_focus()
                return True
        except (GLib.Error, AttributeError):
            pass

    pid, window = choose_window(bus, windows)
    if window is None or not window.actionIsEnabled(SHORTCUTS, dbus_interface=ACTIONS, timeout=1):
        return False
    window.activateWindow(os.environ.get("XDG_ACTIVATION_TOKEN", ""), dbus_interface=WINDOW, timeout=1)
    # KDE returns from this action when the dialog closes. Opening it must
    # return immediately to the caller while the user chooses their keys.
    bus.call_async(window.bus_name, window.object_path, ACTIONS, "activateAction", "s", (SHORTCUTS,), None, None)
    if Atspi:
        until = time.monotonic() + 2
        try:
            rename = bus.get_object(window.bus_name, window.object_path + "/actions/renamefile", introspect=False)
            label = str(rename.Get("org.qtproject.Qt.QAction", "iconText", dbus_interface="org.freedesktop.DBus.Properties", timeout=1))
            while label and time.monotonic() < until:
                dialog = shortcut_dialog(Atspi, {pid})
                if dialog:
                    filter_rename(Atspi, dialog, label)
                    break
                time.sleep(.09)
        except (GLib.Error, dbus.DBusException, AttributeError):
            pass  # The native editor also provides its own search.
    return True


def main():
    try:
        return 0 if open_editor() else 1
    except (OSError, dbus.DBusException):
        return 1
