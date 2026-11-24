"""Settings for the physical mouse wheel on Monet's Wayland desktop."""
from PySide6.QtCore import QSettings
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from actions import tr


class WheelScrolling(QWidget):
    def __init__(self, config=None):
        super().__init__()
        self.config = config if config is not None else QSettings("Monet", "WheelScrolling")
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addLayout(self.form)
        self.profile = self.choice("profile", tr("Scrolling style"), [
            ("system", tr("System default")), ("linear", tr("Fixed distance")), ("smooth", tr("Smooth"))])
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.form.addRow(self.hint)
        self.step = self.number("distance", tr("Distance per wheel step"), 100, 50, 250, "%")
        self.duration = self.number("duration", tr("Glide duration"), 160, 60, 400, tr(" ms"))
        self.sideways = self.choice("sideways", tr("Hold to scroll sideways"), [
            ("off", tr("Off")), ("shift", "Shift"), ("ctrl", "Ctrl"), ("alt", "Alt"), ("meta", tr("Super"))])
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.available = True
        self.refresh()
        query = QDBusMessage.createMethodCall("org.kde.KWin", "/Plugins", "org.freedesktop.DBus.Properties", "Get")
        query.setAutoStartService(False)
        query.setArguments(["org.kde.KWin.Plugins", "LoadedPlugins"])
        self.check = QDBusPendingCallWatcher(QDBusConnection.sessionBus().asyncCall(query, 1000), self)
        self.check.finished.connect(self.check_session)
        for combo in (self.profile, self.sideways):
            combo.currentIndexChanged.connect(self.save)
        for spin in (self.step, self.duration):
            spin.valueChanged.connect(self.save)

    def choice(self, key, label, choices):
        box = QComboBox()
        for value, title in choices:
            box.addItem(title, value)
        box.setCurrentIndex(max(0, box.findData(self.config.value(key, choices[0][0]))))
        self.form.addRow(label, box)
        return box

    def number(self, key, label, default, minimum, maximum, suffix):
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setSuffix(suffix)
        box.setKeyboardTracking(False)
        try:
            value = int(self.config.value(key, default))
        except (ValueError, TypeError, OverflowError):
            value = default
        box.setValue(max(minimum, min(value, maximum)))
        self.form.addRow(label, box)
        return box

    def check_session(self, pending):
        arguments = pending.reply().arguments()
        self.available = (not pending.isError() and bool(arguments)
                          and "monet_wheel_scroll" in arguments[0].variant())
        self.refresh()

    def refresh(self):
        profile = self.profile.currentData()
        hints = {"system": tr("Each app handles the mouse wheel using its usual settings."),
                 "linear": tr("Each wheel step scrolls a fixed distance, however fast you turn it."),
                 "smooth": tr("Each wheel step glides to a stop. Turn the wheel the other way to reverse.")}
        self.hint.setText(hints[profile])
        self.form.setRowVisible(self.step, profile != "system")
        self.form.setRowVisible(self.duration, profile == "smooth")
        self.status.setText(tr("These settings apply to mouse wheels. Touchpad gestures keep their usual behavior.")
                            if self.available else tr("Mouse wheel profiles are unavailable in this desktop session."))

    def save(self):
        self.refresh()
        for key, value in (("profile", self.profile.currentData()), ("sideways", self.sideways.currentData()),
                           ("distance", self.step.value()), ("duration", self.duration.value())):
            self.config.setValue(key, value)
        self.config.sync()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save mouse wheel settings."))
            return
        signal = QDBusMessage.createSignal("/org/monet/WheelScrolling", "org.monet.WheelScrolling", "Changed")
        QDBusConnection.sessionBus().send(signal)
