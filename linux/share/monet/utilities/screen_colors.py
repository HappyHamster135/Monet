"""Pick a composited screen pixel and copy it in the user's preferred format."""
import re

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from actions import tr
from color_values import color_text
from screen_selection import ScreenSelection


class ScreenColors(ScreenSelection):
    def __init__(self, owner):
        super().__init__(owner, "color")
        self.rgb = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.format = QComboBox()
        for key, label in (("hex", "HEX"), ("bare", tr("HEX without #")), ("rgb", "RGB"),
                           ("hsl", "HSL"), ("swiftui", "SwiftUI")):
            self.format.addItem(label, key)
        self.format.setCurrentIndex(max(0, self.format.findData(owner.settings.value("colorFormat", "hex"))))
        self.format.setAccessibleName(tr("Copy colors as"))
        form.addRow(tr("Copy colors as"), self.format)
        layout.addLayout(form)
        self.swatch = QFrame()
        self.swatch.setFrameShape(QFrame.StyledPanel)
        self.swatch.setAutoFillBackground(True)
        self.swatch.setMinimumHeight(70)
        layout.addWidget(self.swatch, 1)
        self.value = QLineEdit()
        self.value.setReadOnly(True)
        self.value.setAccessibleName(tr("Sampled color"))
        self.copy_button = QPushButton(tr("Copy"))
        pick = QPushButton(tr("Pick a screen color"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.value, 1)
        buttons.addWidget(self.copy_button)
        layout.addLayout(buttons)
        layout.addWidget(pick)
        pick.clicked.connect(lambda: self.pick(True))
        self.copy_button.clicked.connect(self.copy_current)
        self.format.currentIndexChanged.connect(self.change_format)
        self.refresh()

    def change_format(self):
        self.owner.settings.setValue("colorFormat", self.format.currentData())
        self.owner.settings.sync()
        self.refresh()

    def refresh(self):
        available = self.rgb is not None
        self.copy_button.setVisible(available)
        self.swatch.setVisible(available)
        self.value.setVisible(available)
        if available:
            palette = self.swatch.palette()
            palette.setColor(QPalette.Window, QColor.fromRgb(self.rgb))
            self.swatch.setPalette(palette)
            self.swatch.setAccessibleName(color_text(self.rgb, "hex"))
            self.value.setText(color_text(self.rgb, self.format.currentData()))

    def capture(self):
        self.owner.worker(["gdbus", "call", "--session", "--timeout", "120", "--dest", "org.kde.KWin",
                           "--object-path", "/ColorPicker", "--method", "org.kde.kwin.ColorPicker.pick"],
                          self.sampled, self.pick_failed)

    def sampled(self, reply):
        if self.closing or "color" in self.owner.hidden:
            self.finish("")
            return
        value = re.fullmatch(r"\s*\(\(uint32 ([0-9]{1,10}),\),\)\s*", reply)
        if not value or int(value[1]) > 0xffffffff:
            self.finish(tr("Couldn’t read that screen color."))
            return
        self.rgb = int(value[1]) & 0xffffff
        self.refresh()
        self.copy_value(self.value.text())

    def pick_failed(self, error):
        cancelled = "org.kde.kwin.ColorPicker.Error.Cancelled" in error
        self.finish("" if cancelled else tr("Screen color picking is unavailable."))

    def copy_current(self):
        if self.busy or self.rgb is None:
            return
        self.busy = True
        self.setEnabled(False)
        self.closing = False
        self.copy_value(self.value.text())

    def copy_value(self, text):
        self.copy_text(text, tr("Copied %1").replace("%1", text), tr("Couldn’t copy the color."))
