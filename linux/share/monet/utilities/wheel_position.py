"""Place a single wheel with KWin, then unload the placement script."""
import json
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
from PySide6.QtWidgets import QApplication


class WheelPlacement(QObject):
    def __init__(self, window, token, caption):
        super().__init__(window)
        self.window = window
        self.token = token
        self.name = f"monet-favorites-wheel-{os.getpid()}-{token}"
        self.bus = QDBusConnection.sessionBus()
        self.folder = tempfile.TemporaryDirectory(prefix="monet-wheel-")
        script = Path(self.folder.name) / "position.js"
        args = json.dumps([os.getpid(), token, caption])
        script.write_text("const [pid, token, title] = " + args + ";\n" + POSITION, encoding="utf-8")
        self.finished = False
        self.timeout = QTimer(self, singleShot=True)
        self.timeout.timeout.connect(self.finish)
        self.timeout.start(650)
        self.pending = QDBusPendingCallWatcher(
            self.call("/Scripting", "loadScript", str(script), self.name), self)
        self.pending.finished.connect(self.loaded)
        QApplication.instance().aboutToQuit.connect(self.stop)

    def call(self, path, method, *args):
        interface = "org.kde.kwin.Scripting" if path == "/Scripting" else "org.kde.kwin.Script"
        message = QDBusMessage.createMethodCall("org.kde.KWin", path, interface, method)
        message.setArguments(list(args))
        return self.bus.asyncCall(message, 1200)

    def loaded(self, watcher):
        reply = watcher.reply()
        watcher.deleteLater()
        self.pending = None
        if self.finished:
            self.release()
            return
        result = reply.arguments()
        if reply.type() == QDBusMessage.ErrorMessage or not result or int(result[0]) < 0:
            self.finish()
            return
        self.call(f"/Scripting/Script{int(result[0])}", "run")

    def finish(self):
        # If KWin is unavailable the chooser can still open at the compositor's default.
        if not self.finished:
            self.window.show_wheel(self.token)
            self.stop()

    def stop(self):
        if self.finished:
            return
        self.finished = True
        self.timeout.stop()
        if self.window.wheel_placement is self:
            self.window.wheel_placement = None
        if self.pending:
            # Queue cleanup even when the desktop session exits before load replies.
            self.call("/Scripting", "unloadScript", self.name)
        else:
            self.release()

    def release(self):
        self.call("/Scripting", "unloadScript", self.name)
        self.folder.cleanup()
        self.deleteLater()


POSITION = """
const service = 'org.monet.Utilities';
const p = workspace.cursorPos;
const output = workspace.screens.find(s => {
    const g = s.geometry;
    return p.x >= g.x && p.y >= g.y && p.x < g.x+g.width && p.y < g.y+g.height;
}) || workspace.activeScreen;
const a = workspace.clientArea(KWin.MaximizeArea, output, workspace.currentDesktop);
let approved = false;
function place(w) {
    if (!approved || w.pid !== pid || w.captionNormal !== title) return;
    approved = false;
    const g = w.frameGeometry;
    const x = Math.max(a.x, Math.min(Math.round(p.x-g.width/2), a.x+a.width-g.width));
    const y = Math.max(a.y, Math.min(Math.round(p.y-g.height/2), a.y+a.height-g.height));
    w.frameGeometry = {x:x, y:y, width:g.width, height:g.height};
    workspace.activeWindow = w;
    callDBus(service, '/Utilities', service, 'WheelPlaced', token);
}
workspace.windowAdded.connect(place);
callDBus(service, '/Utilities', service, 'ShowWheel', token,
         String(Math.floor(Math.min(a.width, a.height))), function(accepted) {
    if (!accepted) return;
    approved = true;
    workspace.windowList().forEach(place);
});
"""
