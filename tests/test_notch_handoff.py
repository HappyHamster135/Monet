"""Navigation waits for the native surface to unmap, on a private test bus."""
import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

UI = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"


class DelayedSurface(QDBusVirtualObject):
    def __init__(self):
        super().__init__()
        self.shows = self.closes = 0
        self.mapped = False

    def introspect(self, path):
        return '<interface name="org.monet.Utilities"><method name="Tool"><arg type="s" direction="in"/><arg type="s" direction="out"/></method></interface>'

    def handleMessage(self, message, connection):
        if message.member() != "Tool":
            return False
        data = json.loads(message.arguments()[0])
        if data["action"] == "show":
            self.shows += 1
            self.mapped = True
            connection.send(message.createReply('{"ok":true}'))
        elif data["action"] == "close":
            self.closes += 1
            message.setDelayedReply(True)
            def unmap():
                self.mapped = False
                connection.send(message.createReply('{"ok":true}'))
            QTimer.singleShot(120, self, unmap)
        return True


class NativeHandoff(unittest.TestCase):
    def test_latest_navigation_waits_for_close_reply_and_never_reopens_the_surface(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        # A separate connection prevents Qt's same-connection direct-call
        # optimization, which does not support asynchronous local replies.
        bus = QDBusConnection.connectToBus(QDBusConnection.SessionBus, "notch-surface-fixture")
        self.addCleanup(lambda: QDBusConnection.disconnectFromBus("notch-surface-fixture"))
        surface = DelayedSurface()
        self.assertTrue(bus.registerService("org.monet.Utilities"))
        self.addCleanup(lambda: bus.unregisterService("org.monet.Utilities"))
        self.assertTrue(bus.registerVirtualObject("/NotchTools", surface))
        self.addCleanup(lambda: bus.unregisterObject("/NotchTools"))
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Handoff.qml"
            scene.write_text('''import QtQuick
import "@UI@" as Monet
Item {
    id: scene; width: 350; height: 300
    property bool activated: true
    property string committed: ""
    property bool ownsSurface: tool.ownsSurface
    property bool waiting: !!tool.pending
    function i18n(text) { return text }
    function navigate() {
        tool.releaseForNavigation(() => { committed = "first"; activated = false })
        tool.releaseForNavigation(() => { committed = "last"; activated = false })
        width = 320
        tool.reposition()
    }
    Monet.NotchTool {
        id: tool; anchors.fill: parent; ownerId: "101"; screenName: ""
        tool: "record"; active: scene.activated
    }
}'''.replace("@UI@", UI.as_uri()))
            view = QQuickView()
            self.addCleanup(view.close)
            view.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(view.status(), QQuickView.Ready, [error.toString() for error in view.errors()])
            view.show()
            root = view.rootObject()
            for _ in range(100):
                QTest.qWait(10)
                if surface.mapped and not root.property("waiting"):
                    break
            self.assertTrue(surface.mapped)
            shows = surface.shows
            root.navigate()
            self.assertTrue(root.property("ownsSurface"))
            QTest.qWait(30)
            self.assertEqual(root.property("committed"), "")
            self.assertTrue(surface.mapped)
            self.assertEqual(surface.closes, 1)
            for _ in range(100):
                QTest.qWait(10)
                if root.property("committed"):
                    break
            self.assertEqual(root.property("committed"), "last")
            self.assertFalse(surface.mapped)
            self.assertFalse(root.property("ownsSurface"))
            QTest.qWait(80)
            self.assertEqual(surface.shows, shows)
