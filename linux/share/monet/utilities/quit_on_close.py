"""Choose which applications should leave when their last window closes."""
import json
import subprocess

import dbus

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget
from actions import tr
from close_rules import application_aliases, applications, settings
from quit_protection import AppPicker, installed_apps


class QuitOnClose(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings()
        self.names = installed_apps()
        layout = QVBoxLayout(self)
        intro = QLabel(tr("Choose apps that should quit when you close their last window. Minimized windows and windows on other desktops still count as open."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.setAccessibleName(tr("Selected applications"))
        layout.addWidget(self.list)
        choose = QPushButton(tr("Choose applications…"))
        choose.clicked.connect(self.choose)
        layout.addWidget(choose, 0, Qt.AlignLeft)
        self.fallback = QCheckBox(tr("Send a termination request if the app has no Quit action"))
        self.fallback.setChecked(self.config.value("terminate", False, type=bool))
        self.fallback.toggled.connect(self.save_fallback)
        layout.addWidget(self.fallback)
        hint = QLabel(tr("This can end background work in a selected app. Leave it off to use only the app’s own Quit action."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        self.config.sync()
        rules = applications(self.config)
        self.list.clear()
        self.list.addItems(sorted((self.names.get(k, (k.removesuffix(".desktop"), ""))[0] for k in rules), key=str.casefold))
        self.fallback.setEnabled(bool(rules))
        self.status.setText("" if rules else tr("Apps currently keep their usual close behavior."))

    def choose(self):
        dialog = AppPicker(applications(self.config), self)
        if dialog.exec() == QDialog.Accepted:
            self.set_apps(dialog.selection())

    def set_apps(self, selected):
        rules = application_aliases(selected)
        self.config.setValue("applications", json.dumps(rules, ensure_ascii=False))
        self.config.sync()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save window closing preferences."))
            return
        # KWin reloads the enabled script list without restarting the compositor.
        try:
            subprocess.run(["kwriteconfig6", "--file", "kwinrc", "--group", "Plugins", "--key",
                            "monet-quit-on-closeEnabled", "--type", "bool", "true" if rules else "false"],
                           timeout=2, check=True)
            scripting = dbus.Interface(dbus.SessionBus().get_object("org.kde.KWin", "/Scripting", introspect=False),
                                       "org.kde.kwin.Scripting")
            scripting.start(timeout=2)
            if bool(scripting.isScriptLoaded("monet-quit-on-close", timeout=2)) != bool(rules):
                raise RuntimeError("Script did not load")
        except (OSError, RuntimeError, subprocess.SubprocessError, dbus.DBusException):
            self.refresh()
            self.status.setText(tr("The desktop could not apply this change. Open Choose applications to try again."))
            return
        self.refresh()

    def save_fallback(self, enabled):
        self.config.setValue("terminate", enabled)
        self.config.sync()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save window closing preferences."))
