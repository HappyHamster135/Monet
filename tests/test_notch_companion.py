"""Exercise the actual Qt Quick companion, including its idle and reduced-motion paths."""
from pathlib import Path
import unittest

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None


@unittest.skipUnless(QQuickView, "requires Qt Quick")
class Companion(unittest.TestCase):
    def setUp(self):
        self.app = QGuiApplication.instance() or QGuiApplication([])
        self.view = QQuickView()
        self.view.setResizeMode(QQuickView.SizeRootObjectToView)
        path = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui/NotchCompanion.qml"
        self.view.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(self.view.status(), QQuickView.Ready, [e.toString() for e in self.view.errors()])
        self.view.resize(66, 66)
        self.view.show()
        self.addCleanup(self.view.close)
        self.buddy = self.view.rootObject()
        QTest.qWait(30)

    def test_idle_reactions_repeat_gate_and_inactive_display(self):
        b = self.buddy
        b.setProperty("hideIdle", True)
        b.setProperty("visits", False)
        self.assertFalse(b.property("showing"))
        self.assertFalse(b.property("waitingForVisit"))
        b.react("music")
        self.assertTrue(b.property("showing"))
        stamp = b.property("lastAt")
        b.react("music")
        b.react("timer")
        self.assertEqual((b.property("moment"), b.property("lastAt")), ("music", stamp))
        b.react("finish")
        self.assertEqual(b.property("moment"), "finish")
        b.setProperty("presented", False)
        b.setProperty("visits", True)
        self.assertFalse(b.property("moving"))
        self.assertFalse(b.property("waitingForVisit"))
        b.react("shelf")
        self.assertEqual(b.property("moment"), "")
        b.setProperty("presented", True)
        self.assertTrue(b.property("waitingForVisit"))
        b.setProperty("frequency", "frequent")
        self.assertTrue(90000 <= b.nextVisit() <= 180000)
        b.setProperty("frequency", "rare")
        self.assertTrue(600000 <= b.nextVisit() <= 1200000)
        b.setProperty("reactions", False)
        b.react("finish")
        self.assertEqual(b.property("moment"), "")

    def test_greeting_ends_and_reduced_motion_keeps_a_still_expression(self):
        b = self.buddy
        b.setProperty("motionAllowed", True)
        b.setProperty("hideIdle", True)
        b.greet()
        self.assertTrue(b.property("moving"))
        QTest.qWait(80)
        b.setProperty("motionAllowed", False)
        self.assertFalse(b.property("moving"))
        self.assertEqual((b.property("lift"), b.property("lean")), (0, 0))
        self.assertEqual(b.property("moment"), "greeting")
        b.setProperty("visits", False)
        self.assertFalse(b.property("showing"))
        b.react("finish")
        self.assertTrue(b.property("wideEyes"))
        self.assertFalse(b.property("moving"))
        QTest.qWait(2800)
        self.assertFalse(b.property("showing"))
        self.assertFalse(b.property("waitingForVisit"))

    def test_appearance_changes_render(self):
        b = self.buddy
        b.setProperty("visits", False)
        b.setProperty("motionAllowed", False)
        def capture():
            QTest.qWait(60)
            image = self.view.grabWindow()
            self.assertFalse(image.isNull())
            return bytes(image.constBits())
        original = capture()
        b.setProperty("styleName", "robot")
        robot = capture()
        self.assertNotEqual(robot, original)
        b.setProperty("shapeName", "pill")
        pill = capture()
        self.assertNotEqual(pill, robot)
        b.setProperty("paletteName", "lilac")
        self.assertNotEqual(capture(), pill)
