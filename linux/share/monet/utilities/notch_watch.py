"""Expose a user-pinned preview to this Plasma shell, for the requesting notch."""
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusServiceWatcher, QDBusVirtualObject

SHELL = "org.kde.plasmashell"
INTERFACE = "org.monet.WindowWatch"


class NotchWatch(QDBusVirtualObject):
    def __init__(self, preview, widget_id):
        super().__init__(preview)
        self.preview = preview
        self.bus = QDBusConnection.sessionBus()
        self.service = INTERFACE + ".n" + widget_id
        self.path = "/WindowWatch/n" + widget_id
        self.owner = ""
        self.active = False
        self.encoded = ""
        self.shell = QDBusServiceWatcher(SHELL, self.bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.shell.serviceOwnerChanged.connect(self.shell_changed)

    def start(self):
        if self.active:
            return True
        owner = self.bus.interface().serviceOwner(SHELL)
        if not owner.isValid() or not owner.value():
            return False
        if not self.bus.registerVirtualObject(self.path, self):
            return False
        if not self.bus.registerService(self.service):
            self.bus.unregisterObject(self.path)
            return False
        self.owner = owner.value()
        self.active = True
        return True

    def shell_changed(self, name, old_owner, new_owner):
        if self.active and self.owner != new_owner:
            self.preview.close()

    def stop(self):
        if self.active:
            self.active = False
            self.bus.unregisterService(self.service)
            self.bus.unregisterObject(self.path)
        self.encoded = ""
        self.owner = ""

    def changed(self):
        self.encoded = ""
        if self.active:
            self.bus.send(QDBusMessage.createTargetedSignal(self.owner, self.path, INTERFACE, "Changed"))

    def frame(self):
        image = self.preview.picture
        if image.isNull():
            return ""
        if not self.encoded:
            if image.width() > 480 or image.height() > 360:
                image = image.scaled(480, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            data = QByteArray()
            stream = QBuffer(data)
            if not stream.open(QIODevice.WriteOnly) or not image.save(stream, "JPEG", 87):
                return ""
            self.encoded = "data:image/jpeg;base64," + bytes(data.toBase64()).decode("ascii")
        return self.encoded

    def introspect(self, path):
        return ('<interface name="org.monet.WindowWatch"><method name="Frame"><arg type="s" direction="out"/>'
                '</method><method name="Edit"/><method name="Stop"/><signal name="Changed"/></interface>')

    def handleMessage(self, message, connection):
        if message.interface() != INTERFACE:
            return False
        if not self.active or message.service() != self.owner:
            reply = message.createErrorReply("org.freedesktop.DBus.Error.AccessDenied", "The preview belongs to the desktop shell.")
        elif message.arguments():
            reply = message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", "Expected no arguments.")
        elif message.member() == "Frame":
            reply = message.createReply(self.frame())
        elif message.member() in ("Edit", "Stop"):
            reply = message.createReply()
            QTimer.singleShot(0, self.preview.edit if message.member() == "Edit" else self.preview.close)
        else:
            return False
        connection.send(reply)
        return True
