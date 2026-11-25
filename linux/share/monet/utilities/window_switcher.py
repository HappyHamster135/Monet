"""Configure the native Alt+Tab window list."""
from pathlib import Path
import subprocess

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from actions import tr


def setting(key, default):
    return subprocess.check_output(["kreadconfig6", "--file", "kwinrc", "--group", "TabBox", "--key", key,
                                    "--default", default], text=True, timeout=2).strip()


def write(key, value):
    subprocess.run(["kwriteconfig6", "--file", "kwinrc", "--group", "TabBox", "--key", key, value],
                   check=True, timeout=2)
    if setting(key, "") != value:
        raise ValueError(key)


class WindowSwitcher(QWidget):
    def __init__(self):
        super().__init__()
        config = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation))
        self.view = QSettings(str(config / "monet/window-switcher.ini"), QSettings.IniFormat)
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addLayout(self.form)
        self.style = self.choice(tr("Appearance"), [(tr("Live window previews"), "grid"), (tr("Icons and titles"), "list")])
        self.apps = self.choice(tr("Show"), [(tr("All windows"), "0"), (tr("One window per app"), "1"),
                                              (tr("Only the active app"), "2")])
        self.screens = self.choice(tr("Include windows from"), [(tr("All displays"), "0"), (tr("Current display"), "1"),
                                                                  (tr("Other displays"), "2")])
        self.hint = QLabel(tr("Hold Alt and press Tab. Type a window title or app name to narrow the list. Release Alt to switch, or press Esc to cancel."))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.style.activated.connect(lambda: self.change("LayoutName", self.style))
        self.apps.activated.connect(lambda: self.change("ApplicationsMode", self.apps))
        self.screens.activated.connect(lambda: self.change("MultiScreenMode", self.screens))

    def choice(self, title, items):
        box = QComboBox()
        box.setAccessibleName(title)
        for text, value in items:
            box.addItem(text, value)
        self.form.addRow(title, box)
        return box

    def refresh(self):
        try:
            layout = setting("LayoutName", "monet-switcher")
            shown = setting("ShowTabBox", "true").lower() in ("true", "yes", "on", "1")
            self.view.sync()
            appearance = "list" if self.view.value("View/compact", False, type=bool) else "grid"
            custom = tr("Switcher hidden") if not shown else tr("Current layout: %1").replace("%1", layout)
            for box, value, label in ((self.style, appearance if layout == "monet-switcher" and shown else "", custom),
                                      (self.apps, setting("ApplicationsMode", "0"), tr("Custom")),
                                      (self.screens, setting("MultiScreenMode", "0"), tr("Custom"))):
                index = box.findData(None)
                if index >= 0: box.removeItem(index)
                index = box.findData(value)
                if index < 0:
                    box.addItem(label, None)
                    index = box.count() - 1
                box.setCurrentIndex(index)
            self.hint.setVisible(shown and layout == "monet-switcher")
        except (OSError, subprocess.SubprocessError):
            self.status.setText(tr("Could not read window switcher settings."))

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def change(self, key, box):
        value = box.currentData()
        if value is None: return
        try:
            if key == "LayoutName":
                self.view.setValue("View/compact", value == "list")
                self.view.sync()
                if self.view.status() != QSettings.NoError: raise ValueError(key)
                write(key, "monet-switcher")
                if setting("ShowTabBox", "true").lower() not in ("true", "yes", "on", "1"):
                    write("ShowTabBox", "true")
            else:
                write(key, value)
        except (OSError, ValueError, subprocess.SubprocessError):
            self.refresh()
            self.status.setText(tr("Could not save window switcher settings."))
            return
        self.refresh()
        self.status.clear()
        msg = QDBusMessage.createMethodCall("org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure")
        msg.setAutoStartService(False)
        watcher = QDBusPendingCallWatcher(QDBusConnection.sessionBus().asyncCall(msg, 2000), self)
        watcher.finished.connect(self.reloaded)

    def reloaded(self, watcher):
        if watcher.isError():
            self.status.setText(tr("Settings saved. The switcher will use them at your next sign-in."))
        watcher.deleteLater()
