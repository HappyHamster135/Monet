"""Exercise the routes used by both notch Back buttons."""
from pathlib import Path
import tempfile
import unittest

try:
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"


@unittest.skipUnless(QQuickView, "requires Qt Quick")
class NotchNavigation(unittest.TestCase):
    def test_back_returns_from_sections_to_the_last_tab_and_preserves_detail_parents(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Navigation.qml"
            scene.write_text('''import QtQuick
import "@MONET_UI@" as Monet
Item {
    id: scene
    property string page: "sections"
    property var tabs: ["music", "controls", "tools"]
    property var details: ["lyrics", "timer-tool"]
    Monet.NotchNavigation {
        objectName: "navigation"
        route: scene.page
        sections: scene.tabs.map(key => ({key}))
        available: key => scene.tabs.includes(key) || scene.details.includes(key)
        onRequested: (key, backwards) => scene.page = key
    }
}'''.replace("@MONET_UI@", UI.as_uri()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            root = window.rootObject()
            nav = root.findChild(QObject, "navigation")

            def back_to(page):
                nav.back()
                self.assertEqual(root.property("page"), page)

            self.assertFalse(nav.property("canGoBack"))
            nav.openTab("controls")
            nav.openTab("music")
            for _ in range(3):
                back_to("sections")
                self.assertEqual(nav.property("lastSection"), "music")
                back_to("music")

            nav.openDetail("lyrics")
            nav.showSections()
            back_to("lyrics")
            back_to("music")
            nav.showSections()
            nav.openTab("tools")
            nav.openDetail("timer-tool")
            nav.showSections()
            root.setProperty("details", [])
            back_to("tools")
            back_to("sections")
            root.setProperty("tabs", ["music", "controls"])
            self.assertFalse(nav.property("canGoBack"))
            back_to("sections")

            nav.openTab("controls")
            nav.dismiss()
            root.setProperty("page", "sections")
            back_to("controls")
