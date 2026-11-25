"""Exercise the notch's actual QML input surface using Qt pointer and wheel events."""
from pathlib import Path
import tempfile
import unittest

try:
    from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False

UI = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"


@unittest.skipUnless(QT, "requires Qt Quick")
class NotchGestures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "Scene.qml"
        path.write_text('''import QtQuick
import QtQuick.Controls as C
import "''' + UI.as_uri() + '''" as Monet
Item {
    id: scene
    width: 300; height: 160
    property bool open: false
    property bool gesturesEnabled: true
    property int tracks: 0
    property int clicks: 0
    Monet.NotchGestures {
        id: controls
        expanded: scene.open; enabled: scene.gesturesEnabled
        onExpansionRequested: open => scene.open = open
        onTrackRequested: next => scene.tracks += next ? 1 : -1
    }
    C.Button {
        width: 140; height: 100
        onClicked: scene.clicks++
        Monet.NotchGestureSurface { gestures: controls }
    }
    C.SpinBox { x: 150; width: 140; height: 100; wheelEnabled: true; objectName: "spin" }
}''')
        self.view = QQuickView()
        self.view.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(self.view.status(), QQuickView.Ready, [e.toString() for e in self.view.errors()])
        self.root = self.view.rootObject()
        self.view.show()
        QTest.qWait(15)
        self.touchpad = QPointingDevice("Notch test pad", 46, QInputDevice.TouchPad, QPointingDevice.Finger,
                                        QInputDevice.Position | QInputDevice.PixelScroll | QInputDevice.Scroll, 2, 0)
        self.addCleanup(self.view.close)

    def send(self, pixel=(0, 0), phase=None, *, angle=(0, 0), inverted=False, at=(70, 40), modifiers=None):
        phase = Qt.NoScrollPhase if phase is None else phase
        precise = phase != Qt.NoScrollPhase or any(pixel)
        point = QPointF(*at)
        event = QWheelEvent(point, QPointF(self.view.mapToGlobal(point.toPoint())), QPoint(*pixel), QPoint(*angle),
                            Qt.NoButton, modifiers or Qt.NoModifier, phase, inverted,
                            Qt.MouseEventSynthesizedBySystem if precise else Qt.MouseEventNotSynthesized,
                            self.touchpad if precise else QPointingDevice.primaryPointingDevice())
        QGuiApplication.sendEvent(self.view, event)

    def test_one_skip_per_swipe_including_long_hold_and_momentum(self):
        self.send(phase=Qt.ScrollBegin)
        for _ in range(3):
            self.send((-18, 3), Qt.ScrollUpdate)
        self.assertEqual(self.root.property("tracks"), 1)
        QTest.qWait(500)
        self.send((-60, 1), Qt.ScrollUpdate)
        self.send((-80, 0), Qt.ScrollMomentum)
        self.send(phase=Qt.ScrollEnd)
        self.assertEqual(self.root.property("tracks"), 1)
        self.send(phase=Qt.ScrollBegin)
        self.send((65, 2), Qt.ScrollUpdate)
        self.assertEqual(self.root.property("tracks"), 0)

    def test_diagonal_jitter_and_standalone_momentum_do_nothing(self):
        self.send((0, -40), Qt.ScrollMomentum)
        self.send(phase=Qt.ScrollBegin)
        self.send((3, -3), Qt.ScrollUpdate)
        self.send((30, -30), Qt.ScrollUpdate)
        self.send((80, 0), Qt.ScrollMomentum)
        self.assertFalse(self.root.property("open"))
        self.assertEqual(self.root.property("tracks"), 0)

    def test_vertical_flick_and_inverted_direction(self):
        self.send(phase=Qt.ScrollBegin)
        self.send((1, 9), Qt.ScrollUpdate, inverted=True)
        self.assertFalse(self.root.property("open"))
        self.send((0, 12), Qt.ScrollMomentum, inverted=True)
        self.assertTrue(self.root.property("open"))
        self.send(phase=Qt.ScrollEnd)
        self.send(phase=Qt.ScrollBegin)
        self.send((0, -25), Qt.ScrollUpdate, inverted=True)
        self.assertFalse(self.root.property("open"))

    def test_mouse_can_tilt_or_reverse_immediately_after_one_detent(self):
        self.send(angle=(0, -120))
        self.assertTrue(self.root.property("open"))
        self.send(angle=(-120, 0))
        self.assertEqual(self.root.property("tracks"), 1)
        self.send(angle=(120, 0))
        self.assertEqual(self.root.property("tracks"), 0)
        self.send(angle=(0, 120))
        self.assertFalse(self.root.property("open"))

    def test_gesture_starting_over_a_control_stays_with_that_control(self):
        self.send(phase=Qt.ScrollBegin, at=(200, 40))
        self.send((-80, 0), Qt.ScrollUpdate)
        self.send((0, -80), Qt.ScrollMomentum)
        self.assertEqual(self.root.property("tracks"), 0)
        self.assertFalse(self.root.property("open"))

    def test_disabling_mid_gesture_requires_a_fresh_swipe(self):
        self.send(phase=Qt.ScrollBegin)
        self.send((-21, 0), Qt.ScrollUpdate)
        self.root.setProperty("gesturesEnabled", False)
        self.root.setProperty("gesturesEnabled", True)
        self.send((-35, 0), Qt.ScrollUpdate)
        self.send((-50, 0), Qt.ScrollMomentum)
        self.assertEqual(self.root.property("tracks"), 0)
        self.send(phase=Qt.ScrollBegin)
        self.send((-45, 0), Qt.ScrollUpdate)
        self.assertEqual(self.root.property("tracks"), 1)

    def test_wheel_bursts_modifiers_clicks_and_opt_out(self):
        self.send(angle=(-120, 0))
        self.send(angle=(-120, 0))
        self.assertEqual(self.root.property("tracks"), 1)
        QTest.qWait(360)
        self.send(angle=(0, -120), modifiers=Qt.ControlModifier)
        self.assertFalse(self.root.property("open"))
        self.send(angle=(0, -120))
        self.assertTrue(self.root.property("open"))
        self.root.setProperty("gesturesEnabled", False)
        self.send(angle=(0, 120))
        self.assertTrue(self.root.property("open"))
        for enabled in (False, True):
            self.root.setProperty("gesturesEnabled", enabled)
            QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, QPoint(70, 40))
        self.assertEqual(self.root.property("clicks"), 2)
        self.send(angle=(0, 120), at=(200, 40))
        self.assertTrue(self.root.property("open"))
        spin = next(item for item in self.root.childItems() if item.objectName() == "spin")
        self.assertEqual(spin.property("value"), 1)
