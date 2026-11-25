"""Saved wheels and their typed targets. The built-in wheel follows Quick Panel favorites."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from uuid import uuid4

from actions import ACTIONS, tr

SLOTS = 8
ICONS = {"app": "application-x-executable", "file": "text-x-generic", "url": "internet-web-browser",
         "shortcut": "preferences-desktop-keyboard-shortcuts", "menu": "folder"}


@dataclass(frozen=True)
class Entry:
    kind: str
    value: str = ""
    name: str = ""
    icon: str = ""
    component: str = ""
    children: tuple = ()

    @property
    def title(self):
        if self.name:
            return self.name
        if self.kind == "tool":
            return ACTIONS[self.value].name if self.value in ACTIONS else self.value
        return self.value

    @property
    def icon_name(self):
        if self.kind == "tool" and self.value in ACTIONS:
            return ACTIONS[self.value].icon
        return self.icon or ICONS.get(self.kind, "")

    def record(self):
        data = {"kind": self.kind}
        for attr in ("value", "name", "icon", "component"):
            if value := getattr(self, attr):
                data[attr] = value
        if self.kind == "menu":
            data["children"] = [e.record() for e in self.children]
        return data


def entries(raw):
    result = []
    if not isinstance(raw, list):
        return ()
    for data in raw[:SLOTS]:
        if not isinstance(data, dict):
            continue
        kind = data.get("kind")
        if not isinstance(kind, str) or kind not in (*ICONS, "tool"):
            continue
        fields = [data.get(k, "") for k in ("value", "name", "icon", "component")]
        if not all(isinstance(v, str) for v in fields):
            continue
        value, name, _, component = fields
        if (not (name if kind == "menu" else value) or (kind == "shortcut" and not component)
                or (kind == "file" and not Path(value).is_absolute())):
            continue
        children = entries(data.get("children")) if kind == "menu" else ()
        result.append(Entry(kind, *fields, children))
    return tuple(result)


@dataclass(frozen=True)
class Profile:
    name: str
    items: tuple


def profiles(settings):
    result = {}
    settings.beginGroup("wheelProfiles")
    try:
        for ident in settings.childKeys():
            if not re.fullmatch("[0-9a-f]{32}", ident):
                continue
            try:
                data = json.loads(settings.value(ident))
                if isinstance(data, dict) and isinstance(data.get("name"), str) and data["name"].strip():
                    result[ident] = Profile(data["name"], entries(data.get("items")))
            except (ValueError, TypeError, RecursionError):
                continue
    finally:
        settings.endGroup()
    return result


def save_profile(settings, ident, profile):
    ident = ident or uuid4().hex
    settings.setValue("wheelProfiles/" + ident, json.dumps({"name": profile.name,
                      "items": [item.record() for item in profile.items]}, ensure_ascii=False))
    settings.sync()
    return ident


def favorites_profile(keys):
    return Profile(tr("Quick Panel favorites"), tuple(Entry("tool", k) for k in keys if k in ACTIONS and k != "wheel")[:SLOTS])


def visible(items, hidden):
    result = []
    for item in items:
        if item.kind == "tool" and (item.value not in ACTIONS or item.value in hidden or item.value == "wheel"):
            continue
        if item.kind == "menu":
            children = visible(item.children, hidden)
            if not children:
                continue
            item = replace(item, children=children)
        result.append(item)
    return tuple(result)


def web_address(text):
    from PySide6.QtCore import QUrl
    url = QUrl(text.strip(), QUrl.StrictMode)
    return url.toString(QUrl.FullyEncoded) if url.isValid() and url.host() and url.scheme() in ("https", "http") else ""


def shortcut_components():
    import dbus
    bus = dbus.SessionBus()
    api = dbus.Interface(bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"), "org.kde.KGlobalAccel")
    return api, sorted(api.allMainComponents(timeout=2), key=lambda c: str(c[1] or c[0]).casefold())


def open_target(entry):
    """Launch exactly the configured desktop object using its native handler."""
    if entry.kind == "app":
        from gi.repository import GLib
        from local_ports import desktop_entry
        try:
            app = desktop_entry(entry.value)
            return bool(app and not app.get_is_hidden() and app.launch([], None))
        except GLib.Error:
            return False
    if entry.kind == "shortcut":
        import dbus
        try:
            bus = dbus.SessionBus()
            api = dbus.Interface(bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"), "org.kde.KGlobalAccel")
            path = api.getComponent(entry.component, timeout=2)
            component = dbus.Interface(bus.get_object("org.kde.kglobalaccel", path), "org.kde.kglobalaccel.Component")
            if entry.value not in component.shortcutNames(timeout=2):
                return False
            component.invokeShortcut(entry.value, timeout=2)
            return True
        except dbus.DBusException:
            return False
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    if entry.kind == "file" and Path(entry.value).exists():
        return QDesktopServices.openUrl(QUrl.fromLocalFile(entry.value))
    if entry.kind == "url" and web_address(entry.value):
        return QDesktopServices.openUrl(QUrl(entry.value))
    return False
