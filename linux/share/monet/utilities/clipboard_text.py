"""Deliver explicitly copied text even when a Wayland tool has yielded focus."""
import shutil

from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
from PySide6.QtWidgets import QApplication


def copy_text(owner, text, finished, *, cancelled=lambda: False):
    def local_copy():
        if cancelled():
            finished(False)
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        finished(clipboard.ownsClipboard())

    def klipper(_):
        if cancelled():
            finished(False)
            return
        message = QDBusMessage.createMethodCall("org.kde.klipper", "/klipper",
                                                "org.kde.klipper.klipper", "setClipboardContents")
        message.setArguments([text])
        watcher = QDBusPendingCallWatcher(QDBusConnection.sessionBus().asyncCall(message, 3000), owner)
        def replied(call):
            reply = call.reply()
            call.deleteLater()
            if reply.type() == QDBusMessage.ErrorMessage:
                local_copy()
            else:
                finished(True)
        watcher.finished.connect(replied)

    if QApplication.platformName().startswith("wayland") and shutil.which("wl-copy"):
        owner.worker(["wl-copy", "--type", "text/plain;charset=utf-8"], lambda _: finished(True), klipper,
                     input_data=text.encode("utf-8"))
    else:
        klipper(None)
