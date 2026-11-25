"""Native tab selection stays on the displayed page when its position changes."""
from pathlib import Path
import tempfile
import unittest

try:
    from PySide6.QtCore import QPoint, Qt, QUrl
    from PySide6.QtGui import QAccessible, QAccessibleActionInterface, QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"


@unittest.skipUnless(QQuickView, "requires Qt Quick")
class NotchTabs(unittest.TestCase):
    def test_keys_and_live_reordering_keep_page_and_selection_together(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        was_active = QAccessible.isActive()
        QAccessible.setActive(True)
        self.addCleanup(QAccessible.setActive, was_active)
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Tabs.qml"
            scene.write_text('''import QtQuick
import "''' + UI.as_uri() + '''" as Monet
Item {
    id: root; width: 360; height: 60
    property int page: 2
    property var order: [0, 2, 1]
    property string highlighted: strip.currentItem?.text ?? ""
    Monet.NotchTabs {
        id: strip; anchors.fill: parent
        tabs: root.order; page: root.page; labels: ["Music", "Activity", "Time"]
        onChosen: tab => root.page = tab
    }
}''')
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            QTest.qWait(40)
            root = window.rootObject()
            self.assertEqual(root.property("highlighted"), "Time")
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(180, 26))
            QTest.keyClick(window, Qt.Key_Right)
            self.assertEqual((root.property("page"), root.property("highlighted")), (1, "Activity"))
            root.setProperty("order", [1, 0, 2])
            app.processEvents()
            self.assertEqual((root.property("page"), root.property("highlighted")), (1, "Activity"))
            root.setProperty("page", 2)
            self.assertEqual(root.property("highlighted"), "Time")
            app.processEvents()
            items = list(root.childItems())
            while items:
                item = items.pop()
                if item.inherits("QQuickTabButton") and item.property("text") == "Activity":
                    break
                items.extend(item.childItems())
            else:
                self.fail("The Activity tab was missing after reordering")
            face = QAccessible.queryAccessibleInterface(item)
            self.assertIsNotNone(face)
            action = face.actionInterface()
            self.assertIn(QAccessibleActionInterface.pressAction(), action.actionNames())
            action.doAction(QAccessibleActionInterface.pressAction())
            self.assertEqual((root.property("page"), root.property("highlighted")), (1, "Activity"))
            root.setProperty("order", [])
            self.assertEqual(root.property("highlighted"), "")
