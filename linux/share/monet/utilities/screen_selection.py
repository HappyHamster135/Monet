"""Lifecycle and clipboard delivery for a user-selected screen region or pixel."""
import time

from PySide6.QtCore import QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusVariant
from PySide6.QtWidgets import QWidget

from actions import ACTIONS, tr


class ScreenSelection(QWidget):
    def __init__(self, owner, key):
        super().__init__()
        self.owner = owner
        self.key = key
        self.busy = False
        self.return_to_page = False
        self.closing = False

    def pick(self, from_catalog):
        if any(isinstance(page, ScreenSelection) and page.busy for page in self.owner.pages.values()):
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
        self.capture()

    def copy_text(self, text, confirmation, failure):
        from clipboard_text import copy_text
        copy_text(self.owner, text, lambda ok: self.finish(confirmation if ok else failure),
                  cancelled=lambda: self.closing)

    def finish(self, message):
        self.busy = False
        self.setEnabled(True)
        if self.closing:
            return
        restored = self.return_to_page and not self.owner.isVisible()
        self.return_to_page = False
        if restored:
            self.owner.page(self.key, lambda: self)
            self.owner.show()
        if message and (restored or self.owner.isActiveWindow()):
            self.owner.issue(message)
        elif message:
            notice = QDBusMessage.createMethodCall("org.kde.plasmashell", "/org/kde/osdService",
                                                   "org.kde.osdService", "showText")
            notice.setArguments([ACTIONS[self.key].icon, message])
            QDBusConnection.sessionBus().send(notice)
        self.owner.panelDismissed.emit()
