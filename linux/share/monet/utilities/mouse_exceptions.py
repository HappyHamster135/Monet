"""Applications that should receive the mouse's original clicks and wheel events."""
import json

from PySide6.QtCore import QSettings, Slot, SLOT
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QWidget

from actions import tr
from close_rules import application_aliases, applications

PATH = "/org/monet/MouseEnhancements"
INTERFACE = "org.monet.MouseEnhancements"


class MouseExceptions(QWidget):
    def __init__(self):
        super().__init__()
        self.config = QSettings("Monet", "MouseEnhancements")
        self.bus = QDBusConnection.sessionBus()
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.choose = QPushButton()
        self.choose.clicked.connect(self.edit)
        form.addRow(tr("Use standard mouse controls in"), self.choose)
        self.hint = QLabel(tr("Selected apps receive clicks and wheel scrolling directly."))
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.bus.connect("", PATH, INTERFACE, "Changed", self, SLOT("refresh()"))
        self.refresh()

    @Slot()
    def refresh(self):
        self.config.sync()
        count = len(applications(self.config))
        self.choose.setText(tr("Choose applications") if count == 0 else
                            tr("1 app selected") if count == 1 else tr("%1 apps selected").replace("%1", str(count)))

    def edit(self):
        from quit_protection import AppPicker
        self.config.sync()
        picker = AppPicker(applications(self.config), self)
        from inline_dialogs import present_dialog
        present_dialog(picker,self,lambda:self.save(picker.selection()))

    def save(self, selected):
        self.config.setValue("applications", json.dumps(application_aliases(selected), ensure_ascii=False))
        self.refresh()
        if self.config.status() != QSettings.NoError:
            self.hint.setText(tr("Could not save mouse settings."))
            return
        self.hint.setText(tr("Selected apps receive clicks and wheel scrolling directly."))
        self.bus.send(QDBusMessage.createSignal(PATH, INTERFACE, "Changed"))
