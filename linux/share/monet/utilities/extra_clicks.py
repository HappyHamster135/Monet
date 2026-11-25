"""Choose which mouse buttons need a short switch-bounce interval."""
import json

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QTimer, Slot, SLOT
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusServiceWatcher
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)
from actions import tr
from mouse_exceptions import MouseExceptions

SERVICE = "org.kde.KWin"
PATH = "/org/monet/ExtraClicks"
INTERFACE = "org.monet.ExtraClicks1"
BUTTONS = (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton)


def request(method):
    message = QDBusMessage.createMethodCall(SERVICE, PATH, INTERFACE, method)
    message.setAutoStartService(False)
    return message


class ClickTest(QLabel):
    def __init__(self):
        super().__init__()
        self.setAccessibleName(tr("Test mouse buttons"))
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(64)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.reset()

    def reset(self):
        self.counts = [0, 0, 0]
        self.held = set()
        self.refresh()

    def refresh(self):
        text = tr("Primary %1 · Secondary %2 · Middle %3")
        for i, count in enumerate(self.counts, 1):
            text = text.replace("%" + str(i), str(count))
        self.setText(text)

    def mousePressEvent(self, event):
        if event.button() in BUTTONS:
            self.held.add(event.button())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in self.held:
            self.held.discard(event.button())
            if self.rect().contains(event.position().toPoint()):
                self.counts[BUTTONS.index(event.button())] += 1
                self.refresh()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ExtraClicks(QWidget):
    def __init__(self):
        super().__init__()
        self.config = QSettings("Monet", "ExtraClicks")
        self.bus = QDBusConnection.sessionBus()
        self.pending = None
        self.dirty = False
        self.available = None
        layout = QVBoxLayout(self)
        self.enable = QCheckBox(tr("Filter accidental extra clicks"))
        self.enable.setChecked(self.config.value("enabled", False, type=bool))
        layout.addWidget(self.enable)
        hint = QLabel(tr("Use this if one mouse click sometimes registers twice. The first click is delivered immediately."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.options = QWidget()
        form = QFormLayout(self.options)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.model = QComboBox()
        form.addRow(tr("Mouse model"), self.model)
        self.interval = QSpinBox()
        self.interval.setRange(5, 100)
        self.interval.setSuffix(tr(" ms"))
        self.interval.setKeyboardTracking(False)
        self.interval.setValue(self.config.value("interval", 25, type=int))
        form.addRow(tr("Ignore repeats within"), self.interval)
        self.buttons = {}
        row = QHBoxLayout()
        for key, label in (("primary", tr("Primary")), ("secondary", tr("Secondary")), ("middle", tr("Middle"))):
            button = QCheckBox(label)
            button.setChecked(self.config.value(key, key == "primary", type=bool))
            self.buttons[key] = button
            row.addWidget(button)
        row.addStretch()
        form.addRow(tr("Buttons"), row)
        layout.addWidget(self.options)
        label = QLabel(tr("Click in the box to test each button."))
        layout.addWidget(label)
        self.test_area = ClickTest()
        layout.addWidget(self.test_area)
        reset = QPushButton(tr("Reset count"))
        reset.clicked.connect(self.test_area.reset)
        layout.addWidget(reset, 0, Qt.AlignLeft)
        self.exceptions = MouseExceptions()
        layout.addWidget(self.exceptions)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.devices)
        self.bus.connect(SERVICE, PATH, INTERFACE, "ModelsChanged", self, SLOT("refreshSoon()"))
        self.watcher = QDBusServiceWatcher(SERVICE, self.bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.watcher.serviceOwnerChanged.connect(self.refreshSoon)
        self.fill_models({})
        self.enable.toggled.connect(self.save)
        self.model.currentIndexChanged.connect(self.save)
        self.interval.valueChanged.connect(self.save)
        for button in self.buttons.values():
            button.toggled.connect(self.save)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.devices()

    @Slot()
    def refreshSoon(self):
        if self.isVisible():
            self.timer.start()

    def devices(self):
        if self.pending is not None:
            self.dirty = True
            return
        self.pending = QDBusPendingCallWatcher(self.bus.asyncCall(request("Models"), 1200), self)
        self.pending.finished.connect(self.received)

    def received(self, watcher):
        try:
            models = json.loads(watcher.reply().arguments()[0]) if not watcher.isError() else None
        except (ValueError, TypeError, IndexError):
            models = None
        self.available = isinstance(models, dict)
        self.fill_models(models or {})
        self.pending = None
        watcher.deleteLater()
        self.refresh()
        if self.dirty:
            self.dirty = False
            self.refreshSoon()

    def fill_models(self, models):
        selected = self.config.value("model", "")
        with QSignalBlocker(self.model):
            self.model.clear()
            self.model.addItem(tr("All mice"), "")
            for key, label in sorted(models.items(), key=lambda item: (item[1].casefold(), item[0])):
                self.model.addItem(label, key)
            if selected and selected not in models:
                self.model.addItem(tr("%1 (disconnected)").replace("%1", selected.split(":", 2)[-1]), selected)
            self.model.setCurrentIndex(max(0, self.model.findData(selected)))

    def refresh(self):
        enabled = self.enable.isChecked()
        self.enable.setEnabled(bool(self.available))
        self.options.setEnabled(bool(self.available) and enabled)
        if self.available is False:
            self.status.setText(tr("The mouse click filter is unavailable in this session."))
        elif self.available and enabled and not any(b.isChecked() for b in self.buttons.values()):
            self.status.setText(tr("Select a mouse button to start filtering."))
        else:
            self.status.clear()

    def save(self):
        self.config.setValue("enabled", self.enable.isChecked())
        self.config.setValue("interval", self.interval.value())
        self.config.setValue("model", self.model.currentData() or "")
        for key, button in self.buttons.items():
            self.config.setValue(key, button.isChecked())
        self.config.sync()
        self.refresh()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save mouse click settings."))
            return
        self.bus.asyncCall(request("Reload"), 1000)
