"""Exercise Monet's shared QML frame without changing the desktop or user settings.

Requires PySide6 and Kirigami (available in the Monet VM); other hosts skip it.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QPoint, QMetaObject, QUrl, Qt
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # Register the wrapper used by grabWindow/contentItem.
    from PySide6.QtTest import QTest, QSignalSpy
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requires PySide6")
class WindowFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        loader = importlib.machinery.SourceFileLoader("frame_games", str(ROOT / "linux/libexec/monet-games"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.games = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.games)

    def setUp(self):
        self.engine = QQmlApplicationEngine()
        self.qml_errors = []
        self.engine.warnings.connect(lambda warnings: self.qml_errors.extend(w.toString() for w in warnings))
        self.words = self.games.Words()
        self.engine.rootContext().setContextObject(self.words)
        self.engine.rootContext().setContextProperty("blurBehind", False)
        folder = QUrl.fromLocalFile(str(ROOT / "linux/share/monet/games")).toString()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        scene = Path(self.temp.name) / "FrameTest.qml"
        scene.write_text('import QtQuick\nimport QtQuick.Templates as T\n'
                         'import org.kde.kirigami as Kirigami\nimport "' + folder + '"\n'
                         'MonetWindow { width: 640; height: 480; visible: true; title: "Frame test"; '
                         'property int clicks: 0; '
                         'Item { objectName: "appBody"; anchors.fill: parent; '
                         'Flickable { id: scroll; objectName: "scroll"; width: 300; height: 360; '
                         'contentHeight: 900; contentWidth: width; clip: true; '
                         'MouseScroll { view: scroll } '
                         'Kirigami.WheelHandler { target: scroll; keyNavigationEnabled: true; '
                         'filterMouseEvents: !("acceptedButtons" in scroll) } '
                         'Item { width: 300; height: 900; '
                         'T.Button { x: 150; y: 60; width: 120; height: 40; onClicked: clicks += 1 } '
                         'TextInput { objectName: "scrollEditor"; x: 150; y: 130; width: 140; height: 40; '
                         'text: "Inside scrolling page"; selectByMouse: true } '
                         'T.Slider { objectName: "scrollSlider"; x: 150; y: 200; width: 140; height: 40 } } } '
                         'T.Button { x: 360; y: 30; width: 180; height: 40; onClicked: clicks += 1 } '
                         'T.Slider { objectName: "slider"; x: 360; y: 100; width: 180; height: 40 } '
                         'TextInput { objectName: "editor"; x: 360; y: 180; width: 220; height: 40; '
                         'text: "Select these words"; selectByMouse: true } '
                         'MouseArea { x: 360; y: 260; width: 180; height: 40; onClicked: clicks += 1 } '
                         '} }', encoding="utf-8")
        self.engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(self.engine.rootObjects(), "The shared frame must load: " + "\n".join(self.qml_errors))
        self.window = self.engine.rootObjects()[0]
        QTest.qWait(100)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        QTest.qWait(1)

    def item(self, name):
        item = self.window.findChild(QObject, name)
        if item is None:
            # Repeater delegates are parented visually to the window, not as QObject children.
            pending = [self.window.contentItem()]
            while pending:
                candidate = pending.pop()
                if candidate.objectName() == name:
                    item = candidate
                    break
                pending.extend(candidate.childItems())
        self.assertIsNotNone(item, name)
        return item

    def test_body_starts_below_title_and_keeps_available_height_on_resize(self):
        self.assertTrue(self.window.flags() & Qt.FramelessWindowHint)
        self.assertEqual(self.item("windowContents").property("y"), 40)
        self.assertEqual(self.item("appBody").property("height"), 440)
        self.window.resize(800, 600)
        QTest.qWait(10)
        self.assertEqual(self.item("appBody").property("width"), 800)
        self.assertEqual(self.item("appBody").property("height"), 560)
        self.assertEqual(self.item("windowGlass").property("height"), 600)

    def move_spy(self):
        meta = self.window.metaObject()
        return QSignalSpy(self.window, meta.method(meta.indexOfSignal("backgroundMoveRequested()")))

    def drag(self, start, end, modifiers=None):
        modifiers = Qt.NoModifier if modifiers is None else modifiers
        QTest.mousePress(self.window, Qt.LeftButton, modifiers, QPoint(*start))
        QTest.mouseMove(self.window, QPoint(*end), 25)
        QTest.mouseRelease(self.window, Qt.LeftButton, modifiers, QPoint(*end))
        QTest.qWait(20)

    def test_empty_body_and_scroll_background_request_a_move(self):
        spy = self.move_spy()
        self.drag((320, 420), (350, 420))
        self.assertEqual(spy.count(), 1)
        self.drag((100, 170), (140, 170))
        self.assertEqual(spy.count(), 2)
        self.assertEqual(self.item("scroll").property("contentY"), 0)

    def test_buttons_sliders_text_and_clickable_cards_keep_their_gestures(self):
        spy = self.move_spy()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(450, 90))
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(450, 320))
        self.assertEqual(self.window.property("clicks"), 2)
        self.drag((380, 160), (510, 160))
        self.assertGreater(self.item("slider").property("value"), 0.6)
        self.drag((365, 235), (450, 235))
        self.assertTrue(self.item("editor").property("selectedText"))
        self.assertEqual(spy.count(), 0)

    def test_controls_inside_a_scrolling_page_keep_their_gestures(self):
        spy = self.move_spy()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(210, 120))
        self.assertEqual(self.window.property("clicks"), 1)
        self.drag((155, 185), (275, 185))
        self.assertTrue(self.item("scrollEditor").property("selectedText"))
        self.drag((165, 260), (275, 260))
        self.assertGreater(self.item("scrollSlider").property("value"), 0.6)
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self.item("scroll").property("contentY"), 0)

    def test_click_and_modified_drag_do_not_move_the_window(self):
        spy = self.move_spy()
        self.drag((320, 420), (321, 420))
        self.drag((320, 420), (350, 420), Qt.ShiftModifier)
        self.assertEqual(spy.count(), 0)

    def test_wheel_still_scrolls_over_the_draggable_background(self):
        from PySide6.QtCore import QPointF
        spy = self.move_spy()
        wheel = QWheelEvent(QPointF(100, 170), QPointF(100, 170), QPoint(), QPoint(0, -120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(self.window, wheel)
        QTest.qWait(100)
        self.assertGreater(self.item("scroll").property("contentY"), 0)
        self.assertEqual(spy.count(), 0)

    def test_touch_still_scrolls_without_requesting_a_window_move(self):
        spy = self.move_spy()
        device = QTest.createTouchDevice()
        gesture = QTest.touchEvent(self.window, device, False)
        gesture.press(0, QPoint(100, 320), self.window).commit()
        QTest.qWait(30)
        for y in (290, 250, 210, 170):
            gesture.move(0, QPoint(100, y), self.window).commit()
            QTest.qWait(30)
        gesture.release(0, QPoint(100, 170), self.window).commit()
        QTest.qWait(100)
        self.assertGreater(self.item("scroll").property("contentY"), 0)
        self.assertEqual(spy.count(), 0)

    def test_painted_controls_decode_in_every_state(self):
        from PySide6.QtGui import QImageReader
        for asset in (ROOT / "linux/share/monet/window-buttons").glob("*.svg"):
            reader = QImageReader(str(asset))
            self.assertFalse(reader.read().isNull(), f"{asset.name}: {reader.errorString()}")
        self.assertFalse(self.qml_errors, "\n".join(self.qml_errors))

    def test_every_edge_has_a_reachable_resize_grip(self):
        # QML instances exist, are above the body, and cover all eight edge combinations.
        for edges in (Qt.TopEdge, Qt.BottomEdge, Qt.LeftEdge, Qt.RightEdge,
                      Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge | Qt.RightEdge,
                      Qt.BottomEdge | Qt.LeftEdge, Qt.BottomEdge | Qt.RightEdge):
            edge = edges.value
            grip = self.item("windowResize" + str(edge))
            self.assertTrue(grip.property("visible"))
            self.assertGreater(grip.property("z"), 0)
            x, y = grip.property("x"), grip.property("y")
            w, h = grip.property("width"), grip.property("height")
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, 640)
            self.assertLessEqual(y + h, 480)
        self.assertEqual(self.item("windowResize" + str(Qt.LeftEdge.value)).property("x"), 0)
        self.assertEqual(self.item("windowResize" + str(Qt.TopEdge.value)).property("y"), 0)

    def test_visible_controls_and_missing_artwork_fallback(self):
        from PySide6.QtCore import QPointF
        artwork = self.item("windowButtonArtwork-close")
        self.assertFalse(any("Cannot open" in warning for warning in self.qml_errors))
        fallback = self.item("windowButtonFallback-close")
        self.assertFalse(fallback.property("visible"))
        artwork.setProperty("source", QUrl.fromLocalFile("/nonexistent/monet-close.svg"))
        QTest.qWait(20)
        self.assertTrue(fallback.property("visible"))
        button = self.item("windowClose")
        self.assertGreaterEqual(button.width(), 40)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier,
                         button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint())
        self.assertFalse(self.window.isVisible())

    def test_maximize_restore_buttons_change_outline_and_grips(self):
        button = self.item("windowMaximize")
        self.assertTrue(QMetaObject.invokeMethod(button, "clicked"))
        QTest.qWait(10)
        self.assertTrue(self.window.property("frameMaximized"))
        self.assertEqual(self.window.property("frameRadius"), 0)
        self.assertFalse(self.item("windowResize" + str(Qt.TopEdge.value)).property("visible"))
        self.assertEqual(button.property("text"), "Restore")
        QMetaObject.invokeMethod(button, "clicked")
        QTest.qWait(10)
        self.assertFalse(self.window.property("frameMaximized"))
        self.assertEqual(self.window.property("frameRadius"), 14)
        self.assertTrue(self.item("windowResize" + str(Qt.TopEdge.value)).property("visible"))

    def test_minimize_and_close_buttons_operate_the_window(self):
        QMetaObject.invokeMethod(self.item("windowMinimize"), "clicked")
        self.assertEqual(self.window.windowState(), Qt.WindowMinimized)
        self.window.showNormal()
        QMetaObject.invokeMethod(self.item("windowClose"), "clicked")
        self.assertFalse(self.window.isVisible())

    def test_software_fallback_has_paper_and_transparent_outer_corners(self):
        self.assertEqual(self.item("windowGlass").property("wash"), 1)
        pixels = self.window.grabWindow()
        self.assertFalse(pixels.isNull())
        for x, y in ((0, 0), (639, 0), (0, 479), (639, 479)):
            self.assertEqual(pixels.pixelColor(x, y).alpha(), 0, (x, y))
        self.assertEqual(pixels.pixelColor(320, 240).alpha(), 255)

    def test_blur_region_matches_rounded_and_maximized_outline(self):
        rounded = self.games.window_region(640, 480, 14)
        self.assertFalse(rounded.contains(QPoint(0, 0)))
        self.assertFalse(rounded.contains(QPoint(639, 479)))
        self.assertTrue(rounded.contains(QPoint(320, 0)))
        self.assertTrue(rounded.contains(QPoint(320, 479)))
        square = self.games.window_region(640, 480, 0)
        self.assertTrue(square.contains(QPoint(0, 0)))
        self.assertTrue(square.contains(QPoint(639, 479)))
        self.assertFalse(square.contains(QPoint(640, 480)))


if __name__ == "__main__":
    unittest.main()
