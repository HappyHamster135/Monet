"""Keyboard shortcuts that can open a named wheel while Utilities is closed."""
from pathlib import Path
import re

import dbus
from gi.repository import GLib
from PySide6.QtCore import QIODevice, QSaveFile, QStandardPaths, Qt
from PySide6.QtGui import QKeySequence

from actions import tr


def launcher(ident):
    if not re.fullmatch("[0-9a-f]{32}", ident):
        raise ValueError("Invalid wheel ID")
    data = Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))
    return data / "kglobalaccel" / f"org.monet.Wheel.{ident}.desktop"


def registry():
    obj = dbus.SessionBus().get_object("org.kde.kglobalaccel", "/kglobalaccel")
    return dbus.Interface(obj, "org.kde.KGlobalAccel")


def action(path, name):
    return [path.name, "_launch", tr("Open wheel “%1”").replace("%1", name), tr("Open wheel")]


def write_launcher(path, ident, name, helpers):
    # Desktop Entry Exec and string values have separate escaping rules.
    program = str(helpers / "monet-utilities").replace("%", "%%")
    quoted = re.sub(r'(["`$\\])', lambda match: "\\" + match[0], program)
    entry = GLib.KeyFile()
    for key, value in (("Type", "Application"), ("Name", action(path, name)[2]),
                       ("Icon", "view-more"), ("Exec", f'"{quoted}" wheel {ident}'), ("StartupNotify", "true")):
        entry.set_string("Desktop Entry", key, value)
    data = entry.to_data()[0].encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    output = QSaveFile(str(path))
    if not output.open(QIODevice.WriteOnly) or output.write(data) != len(data) or not output.commit():
        raise OSError(output.errorString())


def current(ident, name):
    path = launcher(ident)
    if path.is_file():
        keys = registry().shortcutKeys(action(path, name), timeout=2)
        if keys and keys[0][0]:
            return QKeySequence(*(int(key) for key in keys[0][0]))
    return QKeySequence()


def remove(ident):
    path = launcher(ident)
    if path.exists():
        registry().unregister(path.name, "_launch", timeout=2)
        path.unlink(missing_ok=True)


def rename(ident, name, helpers):
    path = launcher(ident)
    if path.exists():
        write_launcher(path, ident, name, helpers)
        registry().doRegister(action(path, name), timeout=2)


def assign(ident, name, helpers, sequence):
    if sequence.isEmpty():
        remove(ident)
        return
    chord = sequence[0]
    if chord.key() < Qt.Key_Escape and not chord.keyboardModifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
        raise ValueError(tr("Include Ctrl, Alt or Super with a typing key."))
    path = launcher(ident)
    api = registry()
    details = action(path, name)
    # KGlobalAccel returns each sequence as four key codes padded with zero.
    codes = [sequence[i].toCombined() for i in range(sequence.count())]
    keys = dbus.Array(codes + [0] * (4 - len(codes)), signature="i")
    wanted = dbus.Struct((keys,), signature="ai")
    previous = api.shortcutKeys(details, timeout=2)
    existed = path.is_file()
    if existed and wanted in previous and api.actionList(wanted, timeout=2)[:2] == details[:2]:
        return
    if wanted not in previous and not api.globalShortcutAvailable(wanted, path.name, timeout=2):
        raise ValueError(tr("That shortcut is already in use. Choose another."))
    write_launcher(path, ident, name, helpers)
    api.doRegister(details, timeout=2)
    # NoAutoloading | SetPresent. The daemon owns the binding across sessions.
    actual = api.setShortcutKeys(details, dbus.Array([wanted], signature="(ai)"), dbus.UInt32(6), timeout=2)
    if not actual or api.actionList(wanted, timeout=2)[:2] != details[:2]:
        if existed:
            api.setShortcutKeys(details, previous, dbus.UInt32(6), timeout=2)
        else:
            remove(ident)
        raise ValueError(tr("The desktop couldn’t assign that shortcut. Choose another."))
