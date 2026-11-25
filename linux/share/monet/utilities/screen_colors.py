"""Pick a composited screen pixel and copy it in the user's preferred format."""
import colorsys
import re
import shutil
import time

from PySide6.QtCore import QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusVariant
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout, QWidget)

from actions import tr


def color_text(rgb, form):
    red, green, blue = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    if form == "rgb":
        return f"rgb({red}, {green}, {blue})"
    def decimal(value):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if form == "swiftui":
        return f"Color(red: {decimal(red / 255)}, green: {decimal(green / 255)}, blue: {decimal(blue / 255)})"
    if form == "hsl":
        hue, light, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
        return f"hsl({decimal(hue * 360)}, {decimal(saturation * 100)}%, {decimal(light * 100)}%)"
    return ("" if form == "bare" else "#") + f"{rgb:06X}"


class ScreenColors(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.rgb = None
        self.busy = False
        self.return_to_page = False
        self.closing = False
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

    def pick(self, from_catalog):
        if self.busy:
            return
        self.busy = True
        self.setEnabled(False)
        self.closing = False
        self.return_to_page = from_catalog and self.owner.isVisible()
        if self.return_to_page:
            self.owner.hide()
        # KWin can still be painting the window or launcher after Qt hides it.
        # Check only during a pick so a fast click samples the uncovered pixel.
        self.settle_until = time.monotonic() + 3
        QTimer.singleShot(32, self, self.wait_for_scene)

    def wait_for_scene(self):
        if self.closing:
            self.finish("")
            return
        message = QDBusMessage.createMethodCall("org.kde.KWin", "/Effects", "org.freedesktop.DBus.Properties", "Get")
        message.setArguments(["org.kde.kwin.Effects", "activeEffects"])
        call = QDBusConnection.sessionBus().asyncCall(message, 250)
        watcher = QDBusPendingCallWatcher(call, self)
        watcher.finished.connect(self.scene_ready)

    def scene_ready(self, watcher):
        args = watcher.reply().arguments()
        watcher.deleteLater()
        if self.closing:
            self.finish("")
            return
        effects = args[0].variant() if args and isinstance(args[0], QDBusVariant) else []
        transitions = {"scale", "fade", "fadingpopups", "glide", "squash", "magiclamp"}
        if isinstance(effects, list) and transitions.intersection(effects) and time.monotonic() < self.settle_until:
            QTimer.singleShot(40, self, self.wait_for_scene)
            return
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
        # A global shortcut on Wayland has no focused application surface. Give
        # the compositor a clipboard source that survives Utilities closing.
        def copied(_):
            self.finish(tr("Copied %1").replace("%1", text))
        def local_copy(_):
            if self.closing:
                self.finish("")
                return
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            if clipboard.ownsClipboard():
                copied(None)
            else:
                self.finish(tr("Couldn’t copy the color."))
        if QApplication.platformName().startswith("wayland") and shutil.which("wl-copy"):
            self.owner.worker(["wl-copy", "--type", "text/plain;charset=utf-8", "--", text], copied,
                              lambda _: self.copy_with_klipper(text, copied, local_copy))
        else:
            self.copy_with_klipper(text, copied, local_copy)

    def copy_with_klipper(self, text, copied, fallback):
        if self.closing:
            self.finish("")
            return
        self.owner.worker(["gdbus", "call", "--session", "--timeout", "3", "--dest", "org.kde.klipper",
                           "--object-path", "/klipper", "--method", "org.kde.klipper.klipper.setClipboardContents",
                           text], copied, fallback)

    def finish(self, message):
        self.busy = False
        self.setEnabled(True)
        if self.closing:
            return
        restored = self.return_to_page and not self.owner.isVisible()
        self.return_to_page = False
        if restored:
            self.owner.page("color", lambda: self)
            self.owner.show()
        if message and (restored or self.owner.isActiveWindow()):
            self.owner.issue(message)
        elif message:
            notice = QDBusMessage.createMethodCall("org.kde.plasmashell", "/org/kde/osdService",
                                                   "org.kde.osdService", "showText")
            notice.setArguments(["color-picker", message])
            QDBusConnection.sessionBus().send(notice)
        self.owner.panelDismissed.emit()
