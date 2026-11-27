"""Preferences for Monet's native quit and close shortcut protection."""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from actions import tr


def installed_apps():
    from gi.repository import Gio
    apps = {}
    for app in Gio.AppInfo.get_all():
        ident = app.get_id()
        if ident and app.should_show():
            icon = app.get_icon()
            apps[ident] = (app.get_display_name(), icon.to_string() if icon else "")
    return apps


class AppPicker(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Choose applications"))
        self.resize(400, 390)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Find an application…"))
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        self.items = QListWidget()
        layout.addWidget(self.items)
        apps = installed_apps()
        for ident in selected:
            apps.setdefault(ident, (ident.removesuffix(".desktop"), ""))
        for ident, (name, icon) in sorted(apps.items(), key=lambda pair: pair[1][0].casefold()):
            item = QListWidgetItem(QIcon.fromTheme(icon), name)
            item.setToolTip(ident)
            item.setData(Qt.UserRole, ident)
            item.setCheckState(Qt.Checked if ident in selected else Qt.Unchecked)
            self.items.addItem(item)
        self.search.textChanged.connect(self.filter)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.setFocus()

    def filter(self, query):
        for i in range(self.items.count()):
            item = self.items.item(i)
            item.setHidden(query.casefold() not in (item.text() + " " + item.data(Qt.UserRole)).casefold())

    def selection(self):
        return sorted(item.data(Qt.UserRole) for i in range(self.items.count())
                      if (item := self.items.item(i)).checkState() == Qt.Checked)


def choice(options, current):
    box = QComboBox()
    for title, value in options:
        box.addItem(title, value)
    box.setCurrentIndex(max(0, box.findData(current)))
    return box


class ShortcutRule(QWidget):
    def __init__(self, config, group):
        super().__init__()
        self.config = config
        self.group = group
        def saved(key, default, kind):
            return config.value(group + "/" + key, default, type=kind)

        layout = QVBoxLayout(self)
        self.enable = QCheckBox(tr("Protect Ctrl+Q") if group == "quit" else tr("Protect Ctrl+W"))
        self.enable.setChecked(saved("enabled", False, bool))
        layout.addWidget(self.enable)
        self.options = QWidget()
        self.form = QFormLayout(self.options)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addWidget(self.options)
        self.mode = choice([(tr("Hold the shortcut"), "hold"), (tr("Press it twice"), "twice"),
                            (tr("Add a modifier key"), "modifier")], saved("mode", "hold", str))
        self.form.addRow(tr("Confirm by"), self.mode)
        self.hold = self.duration("holdMs", 800, 250, 2000)
        self.form.addRow(tr("Hold for"), self.hold)
        self.interval = self.duration("doubleMs", 600, 200, 1500)
        self.form.addRow(tr("Second press within"), self.interval)
        self.modifier = choice([("Shift", "shift"), ("Alt", "alt"), (tr("Super"), "meta")],
                               saved("modifier", "shift", str))
        self.form.addRow(tr("Extra key"), self.modifier)
        self.extra_hint = QLabel(tr("This combination takes over the app’s usual action for those keys."))
        self.extra_hint.setWordWrap(True)
        self.form.addRow(self.extra_hint)
        self.scope = choice([(tr("All applications"), "all"), (tr("Only selected applications"), "selected"),
                             (tr("All except selected applications"), "except")], saved("scope", "all", str))
        self.form.addRow(tr("Apply to"), self.scope)
        self.apps = [s for s in saved("apps", [], list) if isinstance(s, str) and s]
        self.pick = QPushButton()
        self.pick.clicked.connect(self.choose_apps)
        self.form.addRow(tr("Applications"), self.pick)
        self.feedback = QCheckBox(tr("Show a reminder when a shortcut is caught"))
        self.feedback.setChecked(saved("feedback", True, bool))
        self.form.addRow(self.feedback)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        for widget in (self.enable, self.feedback):
            widget.toggled.connect(self.save)
        for widget in (self.mode, self.modifier, self.scope):
            widget.currentIndexChanged.connect(self.save)
        for widget in (self.hold, self.interval):
            widget.valueChanged.connect(self.save)
        self.refresh()

    def duration(self, key, default, minimum, maximum):
        widget = QDoubleSpinBox()
        widget.setRange(minimum / 1000, maximum / 1000)
        widget.setSingleStep(.05)
        widget.setSuffix(tr(" s"))
        widget.setKeyboardTracking(False)
        widget.setValue(self.config.value(self.group + "/" + key, default, type=int) / 1000)
        return widget

    def refresh(self):
        mode = self.mode.currentData()
        self.options.setEnabled(self.enable.isChecked())
        self.form.setRowVisible(self.hold, mode == "hold")
        self.form.setRowVisible(self.interval, mode == "twice")
        self.form.setRowVisible(self.modifier, mode == "modifier")
        self.form.setRowVisible(self.extra_hint, mode == "modifier")
        self.form.setRowVisible(self.pick, self.scope.currentData() != "all")
        self.pick.setText(tr("Choose applications…") if not self.apps else tr("Choose applications… (%1)").replace("%1", str(len(self.apps))))
        empty = self.enable.isChecked() and self.scope.currentData() == "selected" and not self.apps
        self.status.setText(tr("Choose an application to start protecting this shortcut.") if empty else "")
        self.status.setVisible(empty)

    def choose_apps(self):
        dialog = AppPicker(self.apps, self)
        def selected():
            self.apps = dialog.selection()
            self.save()
        from inline_dialogs import present_dialog
        present_dialog(dialog,self,selected)

    def save(self):
        values = {"enabled": self.enable.isChecked(), "mode": self.mode.currentData(),
                  "scope": self.scope.currentData(), "modifier": self.modifier.currentData(),
                  "holdMs": round(self.hold.value() * 1000), "doubleMs": round(self.interval.value() * 1000),
                  "apps": self.apps, "feedback": self.feedback.isChecked()}
        for key, value in values.items():
            self.config.setValue(self.group + "/" + key, value)
        self.config.sync()
        self.refresh()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save shortcut protection settings."))
            self.status.show()
            return
        signal = QDBusMessage.createSignal("/org/monet/QuitProtection", "org.monet.QuitProtection", "Changed")
        QDBusConnection.sessionBus().send(signal)


class QuitProtection(QWidget):
    def __init__(self, config=None):
        super().__init__()
        config = config if config is not None else QSettings("Monet", "QuitProtection")
        layout = QVBoxLayout(self)
        intro = QLabel(tr("Choose how to confirm keyboard shortcuts that quit an app or close its current tab or window."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        self.tabs.addTab(ShortcutRule(config, "quit"), tr("Quit application"))
        self.tabs.addTab(ShortcutRule(config, "close"), tr("Close tab or window"))
        layout.addWidget(self.tabs)
