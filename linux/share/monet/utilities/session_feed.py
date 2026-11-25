"""One event-driven session reader shared by open Utilities and notch views."""
import json
from pathlib import Path
import re
import sys

from PySide6.QtCore import QObject, QProcess, Signal, Slot
from PySide6.QtDBus import QDBusMessage, QDBusServiceWatcher, QDBusVirtualObject
from PySide6.QtWidgets import QApplication

from actions import stored, tr


class SessionFeed(QObject):
    changed = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.settings = parent.settings
        self.views = set()
        self.process = None
        self.path = ""
        self.text = ""
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def view(self, name, visible):
        if visible:
            self.views.add(name)
        else:
            self.views.discard(name)
        self.refresh()

    def publish(self, text):
        if self.text != text:
            self.text = text
            self.changed.emit(text)

    def refresh(self, force=False):
        path = self.settings.value("agentFile", "") if self.views else ""
        if not isinstance(path, str) or not path or not Path(path).is_absolute() or "agents" in stored(self.settings, "hidden", []):
            path = ""
        if path == self.path and not force:
            return
        self.path = path
        old, self.process = self.process, None
        if old is not None:
            old.kill()
        self.publish("")
        if not path:
            return
        job = QProcess(self)
        self.process = job
        job.readyReadStandardOutput.connect(self.receive)
        job.finished.connect(self.finished)
        job.finished.connect(job.deleteLater)
        job.errorOccurred.connect(self.failed)
        job.start(sys.executable, ["-u", str(Path(__file__).with_name("session_watch.py"))])
        # Keeping the pipe open also lets the reader notice an unexpected parent exit.
        job.write((json.dumps(path) + "\n").encode())

    @Slot()
    def receive(self):
        job = self.sender()
        if job is not self.process:
            return
        while job.canReadLine():
            try:
                value = json.loads(bytes(job.readLine()))
            except (UnicodeError, ValueError):
                continue
            if isinstance(value, str):
                self.publish(value)

    @Slot()
    def finished(self):
        if self.sender() is self.process:
            self.process = None
            self.path = ""
            self.publish(tr("Could not read the selected session file."))

    @Slot(QProcess.ProcessError)
    def failed(self, error):
        if error == QProcess.FailedToStart:
            self.finished()
            self.sender().deleteLater()

    @Slot()
    def shutdown(self):
        self.process = None
        for job in self.findChildren(QProcess):
            if job.state() != QProcess.NotRunning:
                job.kill()
                job.waitForFinished(1000)


class NotchSession(QDBusVirtualObject):
    path = "/AgentSession"
    service = "org.monet.Utilities"
    shell = "org.kde.plasmashell"

    def __init__(self, bus, receiver):
        super().__init__(receiver)
        self.bus = bus
        self.receiver = receiver
        self.owner = ""
        self.clients = set()
        self.owner_watch = QDBusServiceWatcher(self.shell, bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.owner_watch.serviceOwnerChanged.connect(self.owner_changed)
        receiver.window.session_feed().changed.connect(self.changed)

    def owner_changed(self, _, previous, current):
        if self.owner == current:
            return
        self.owner = current
        for client in list(self.clients):
            self.watch(client, False)

    def changed(self, value):
        if self.clients and self.owner:
            signal = QDBusMessage.createTargetedSignal(self.owner, self.path, self.service, "SessionChanged")
            signal.setArguments([value])
            self.bus.send(signal)

    def watch(self, client, enabled):
        feed = self.receiver.window.session_feed()
        if enabled:
            self.clients.add(client)
        else:
            self.clients.discard(client)
        QApplication.setQuitOnLastWindowClosed(not self.clients)
        feed.view("notch-" + client, enabled)
        if enabled:
            self.changed(feed.text)
        self.receiver.idle.start()

    def introspect(self, _):
        return ('<interface name="org.monet.Utilities"><method name="Watch">'
                '<arg type="s" direction="in"/><arg type="b" direction="in"/></method>'
                '<signal name="SessionChanged"><arg type="s"/></signal></interface>')

    def handleMessage(self, message, connection):
        if message.interface() != self.service or message.member() != "Watch":
            return False
        if not self.owner:
            self.owner = self.bus.interface().serviceOwner(self.shell).value() or ""
        if not self.owner or self.owner != message.service():
            reply = message.createErrorReply("org.freedesktop.DBus.Error.AccessDenied", "Desktop shell only")
        elif message.signature() != "sb" or not re.fullmatch(r"[0-9]{1,10}", message.arguments()[0]):
            reply = message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", "Expected a widget ID and visibility")
        else:
            self.receiver.window.settings.sync()
            self.watch(*message.arguments())
            reply = message.createReply()
        connection.send(reply)
        return True
