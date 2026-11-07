#!/usr/bin/env python3
"""Fail early when the native desktop test job has lost a required runtime."""
import importlib
import ctypes.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    problems = []
    electron = os.environ.get('MONET_ELECTRON_BINARY', '')
    if not electron or not os.access(electron, os.X_OK):
        problems.append('Missing pinned Electron accessibility test runtime')
    client = os.environ.get('MONET_TEST_ELECTRON_DBUS', '')
    if not client or not (Path(client)/'package.json').is_file():
        problems.append('Missing pinned Electron native-login test transport')
    for module in ("PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtQml", "PySide6.QtQuick",
                   "PySide6.QtTest", "PySide6.QtDBus", "gi", "nacl", "numpy", "PIL", "dbus"):
        try:
            importlib.import_module(module)
        except ImportError as error:
            problems.append(str(error))
    for name in ("node", "dbus-run-session", "kreadconfig6", "kwriteconfig6", "kbuildsycoca6", "plasma-systemmonitor",
                 "plasmawindowed", "pipewire", "pipewire-pulse", "pw-metadata", "pactl", "openssl",
                 "sfdisk", "blkid", "mkfs.ntfs", "mkfs.vfat", "ntfscp", "wimlib-imagex", "dolphin", "ark", "7z", "Xvfb", "xdotool", "pgrep", "fc-cache", "fc-match"):
        if not shutil.which(name):
            problems.append("Missing command: " + name)
    if not os.access('/usr/libexec/kscreenlocker_greet', os.X_OK):
        problems.append('Missing native KDE lock-screen greeter')
    if not ctypes.util.find_library('Xtst'):
        problems.append('Missing native XTest input library')
    for path in ("lib*/qt6/plugins/styles/libkvantum.so",
                 "lib*/qt6/plugins/platformthemes/KDEPlasmaPlatformTheme6.so",
                 "lib*/libKF6BalooWidgets.so.6"):
        if not any(Path("/usr").glob(path)):
            problems.append("Missing native plugin: /usr/" + path)
    if not problems:
        import gi
        for version in ("3.0", "4.0"):
            result = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('Gtk', '" + version + "'); from gi.repository import Gtk"],
                                    capture_output=True, timeout=10)
            if result.returncode:
                problems.append("Missing native GTK " + version + " accessibility fixture runtime")
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        app = QGuiApplication([])
        engine = QQmlEngine()
        for name in ("QtQuick.Controls", "QtQuick.Dialogs", "QtQuick.Effects", "QtQuick.Shapes",
                     "org.kde.kirigami", "org.kde.notificationmanager", "org.kde.ksysguard.sensors",
                     "org.kde.plasma.core", "org.kde.plasma.plasma5support", "org.kde.taskmanager",
                     "org.kde.plasma.private.volume", "org.kde.plasma.workspace.keyboardlayout"):
            component = QQmlComponent(engine)
            component.setData(f"import QtQml\nimport {name}\nQtObject {{}}".encode(), QUrl())
            if component.isError():
                problems.extend(e.toString() for e in component.errors())
    if problems:
        print("Desktop test dependencies are incomplete:\n" + "\n".join(problems), file=sys.stderr)
        return 1
    print("Desktop test runtimes are available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
