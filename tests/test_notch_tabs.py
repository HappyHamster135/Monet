"""Native tab selection stays on the displayed page when its position changes."""
from pathlib import Path
import tempfile
import time
import unittest

try:
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import (QAccessible, QAccessibleActionInterface, QGuiApplication,
                               QInputDevice, QPointingDevice, QWheelEvent)
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

SHARE = Path(__file__).resolve().parents[1] / "linux/share"
UI = SHARE / "plasma/plasmoids/org.monet.notch/contents/ui"


@unittest.skipUnless(QQuickView, "requires Qt Quick")
class NotchTabs(unittest.TestCase):
    def test_section_grid_follows_keyboard_activation_after_reorder(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Sections.qml"
            scene.write_text('''import QtQuick
import "@MONET_UI@" as Monet
Monet.IslandSections {
    id: grid; width: 420; height: 130
    function i18n(text) { return text }
    property string chosen: ""
    function reorder() { entries = entries.slice().reverse() }
    entries: ["music","time","notes","files","activity"].map(k => ({key:k, label:k, icon:"folder", color:"white"}))
    onSelected: key => chosen = key
}'''.replace("@MONET_UI@", UI.as_uri()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            QTest.qWait(50)
            grid = window.rootObject()
            grid.focusFirst()
            QTest.keyClick(window, Qt.Key_Right)
            QTest.keyClick(window, Qt.Key_Return)
            self.assertEqual(grid.property("chosen"), "time")
            # Four columns fit the expanded panel; narrow panels keep every row keyboard-accessible.
            grid.setWidth(432)
            app.processEvents()
            self.assertEqual(grid.property("columns"), 4)
            grid.setWidth(282)
            app.processEvents()
            self.assertEqual(grid.property("columns"), 3)
            grid.focusFirst()
            QTest.keyClick(window, Qt.Key_Down)
            QTest.keyClick(window, Qt.Key_Return)
            self.assertEqual(grid.property("chosen"), "files")
            grid.reorder()
            app.processEvents()
            grid.focusFirst()
            QTest.keyClick(window, Qt.Key_Space)
            self.assertEqual(grid.property("chosen"), "activity")

    def test_section_grid_snaps_to_pages_by_wheel_gesture_dot_and_keyboard(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Sections.qml"
            scene.write_text('''import QtQuick
import "@MONET_UI@" as Monet
Monet.IslandSections {
    width: 432; height: 269
    function i18n(text, a, b) { return text.replace("%1", a).replace("%2", b) }
    entries: Array.from({length: 15}, (_, i) => ({key: String(i), label: String(i), icon: "folder", color: "white"}))
    onSelected: key => lastSection = key
}'''.replace("@MONET_UI@", UI.as_uri()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            QTest.qWait(50)
            grid = window.rootObject()
            pending = [grid]
            tiles = {}
            dots = {}
            while pending:
                item = pending.pop()
                if item.objectName().startswith("island-section-"):
                    tiles[int(item.objectName().removeprefix("island-section-"))] = item
                if item.objectName().startswith("island-dot-"):
                    dots[int(item.objectName().removeprefix("island-dot-"))] = item
                pending.extend(item.childItems())

            def in_view(item):
                y = item.mapToScene(QPointF()).y()
                return y >= -0.5 and y + item.height() <= grid.height() + 0.5

            self.assertEqual(len(tiles), 15)
            self.assertEqual([i for i in sorted(tiles) if in_view(tiles[i])], list(range(12)))
            point = tiles[5].mapToScene(QPointF(20, 20))
            screen = QPointF(window.mapToGlobal(point.toPoint()))
            QTest.mouseMove(window, point.toPoint())
            touchpad = QPointingDevice("Fixture touchpad", 42, QInputDevice.TouchPad, QPointingDevice.Finger,
                                       QInputDevice.Position | QInputDevice.PixelScroll | QInputDevice.Scroll, 2, 0)

            def wheel(angle, pixel=QPoint(), phase=Qt.NoScrollPhase):
                device = QPointingDevice.primaryPointingDevice() if phase == Qt.NoScrollPhase else touchpad
                event = QWheelEvent(point, screen, pixel, angle, Qt.NoButton, Qt.NoModifier, phase, False,
                                    Qt.MouseEventNotSynthesized if phase == Qt.NoScrollPhase else Qt.MouseEventSynthesizedBySystem,
                                    device)
                event.setTimestamp(int(time.monotonic() * 1000))
                app.sendEvent(window, event)
                QTest.qWait(20)

            def click(item):
                point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)

            def on_page(page):
                QTest.qWait(210)
                self.assertEqual(grid.property("currentPage"), page)
                self.assertEqual([i for i in sorted(tiles) if in_view(tiles[i])],
                                 list(range(12)) if page == 0 else [12, 13, 14])
                # The first row of each settled page aligns with the top of the grid.
                self.assertAlmostEqual(tiles[page * 12].mapToScene(QPointF()).y(), 0, delta=1)

            self.assertEqual(list(sorted(dots)), [0, 1])
            self.assertTrue(all(dot.isVisible() for dot in dots.values()))
            wheel(QPoint(-120, 0))
            on_page(0)
            wheel(QPoint(0, -120))
            on_page(1)
            wheel(QPoint(0, -120))
            on_page(1)
            wheel(QPoint(0, 120))
            on_page(0)
            # Small pixel deltas accumulate, and rebound or momentum from the same swipe cannot undo the turn.
            wheel(QPoint(), phase=Qt.ScrollBegin)
            wheel(QPoint(), QPoint(0, -8), Qt.ScrollUpdate)
            self.assertEqual(grid.property("currentPage"), 0)
            wheel(QPoint(), QPoint(0, -20), Qt.ScrollUpdate)
            self.assertEqual(grid.property("currentPage"), 1)
            wheel(QPoint(), QPoint(0, 42), Qt.ScrollUpdate)
            wheel(QPoint(), QPoint(0, 80), Qt.ScrollMomentum)
            wheel(QPoint(), phase=Qt.ScrollEnd)
            on_page(1)

            click(tiles[14])
            self.assertEqual(grid.property("lastSection"), "14")
            click(dots[0])
            on_page(0)
            grid.focusFirst()
            on_page(1)
            self.assertTrue(tiles[14].hasActiveFocus())
            QTest.keyClick(window, Qt.Key_Up)
            on_page(0)
            self.assertTrue(tiles[10].hasActiveFocus())
            QTest.keyClick(window, Qt.Key_PageDown)
            on_page(1)
            device = QTest.createTouchDevice()
            gesture = QTest.touchEvent(window, device, False)
            gesture.press(0, QPoint(70, 35), window).commit()
            for y in (60, 95, 140):
                gesture.move(0, QPoint(70, y), window).commit()
                QTest.qWait(20)
            gesture.release(0, QPoint(70, 140), window).commit()
            on_page(0)
            self.assertEqual(grid.property("lastSection"), "14")
            click(dots[1])
            on_page(1)

            grid.setWidth(250)
            QTest.qWait(40)
            self.assertEqual(grid.property("pageCount"), 2)
            grid.focusFirst()
            self.assertTrue(tiles[14].hasActiveFocus() and in_view(tiles[14]))
            dot_row = dots[0].parentItem()
            grid.setProperty("entries", [{"key": "only", "label": "Only", "icon": "folder", "color": "white"}])
            QTest.qWait(40)
            self.assertEqual((grid.property("pageCount"), grid.property("currentPage")), (1, 0))
            self.assertFalse(dot_row.isVisible())

    def test_navigation_reuses_visited_pages_and_releases_private_content(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Deck.qml"
            scene.write_text('''import QtQuick
import "@MONET_UI@" as Monet
Item {
    id: root; width: 350; height: 190
    function i18n(text) { return text }
    property int tab: 0
    property bool opened: true
    property int clocks: 0
    property int cameras: 0
    property string shown: deck.item?.objectName ?? ""
    Component { id: grid; Item { objectName: "grid" } }
    Component { id: clock; Item { objectName: "time"; Component.onCompleted: ++root.clocks } }
    Component { id: camera; Item { objectName: "camera"; Component.onCompleted: ++root.cameras; Component.onDestruction: --root.cameras } }
    Monet.IslandPages {
        id: deck; anchors.fill: parent; components: [grid, clock, camera]
        reusable: [clock]; privatePages: [camera]; prewarm: grid
        presented: root.opened; duration: 90; requested: components[root.tab]
    }
}'''.replace("@MONET_UI@", UI.as_uri()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            root = window.rootObject()

            def shown(name):
                for _ in range(100):
                    QTest.qWait(10)
                    if root.property("shown") == name:
                        return
                self.fail(f"Expected to see {name!r}, got {root.property('shown')!r}")

            shown("grid")
            root.setProperty("tab", 1)
            shown("time")
            root.setProperty("tab", 0)
            shown("grid")
            root.setProperty("tab", 1)
            shown("time")
            self.assertEqual(root.property("clocks"), 1)
            root.setProperty("tab", 2)
            shown("camera")
            root.setProperty("tab", 0)
            shown("grid")
            self.assertEqual(root.property("cameras"), 0)
            root.setProperty("opened", False)
            shown("")
            root.setProperty("tab", 1)
            root.setProperty("opened", True)
            shown("time")
            self.assertEqual(root.property("clocks"), 2)

    def test_interrupted_slides_share_one_edge_and_finish_on_the_last_request(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Slide.qml"
            scene.write_text('''import QtQuick
import "@MONET_UI@" as Monet
Item {
    id: root; width: 301; height: 120
    property int tab: 0
    property string shown: deck.item?.objectName ?? ""
    property bool settled: !deck.outgoing
    property int motion: 400
    function i18n(text) { return text }
    function reverseInPlace() {
        if (!deck.outgoing || deck.progress < 0.15 || deck.progress > 0.9) return false
        const old = deck.outgoing, next = deck.current
        const a = old.x, b = next.x
        tab = 0
        deck.resolve()
        return deck.current === old && deck.outgoing === next &&
               Math.abs(a - old.x) <= 1 && Math.abs(b - next.x) <= 1 &&
               Math.abs(old.x - next.x) === deck.width && old.clip && next.clip
    }
    Component { id: home; Item { objectName: "home" } }
    Component { id: player; Item { objectName: "player" } }
    Component { id: mixer; Item { objectName: "mixer" } }
    Monet.IslandPages {
        id: deck; anchors.fill: parent; components: [home, player, mixer]
        reusable: [player, mixer]; privatePages: []; prewarm: home
        presented: true; duration: root.motion; requested: components[root.tab]
    }
}'''.replace("@MONET_UI@", UI.as_uri()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            root = window.rootObject()

            def until(predicate):
                for _ in range(150):
                    if predicate():
                        return
                    QTest.qWait(8)
                self.fail(f"Slide stalled at {root.property('shown')!r}")

            until(lambda: root.property("shown") == "home")
            root.setProperty("tab", 1)
            until(root.reverseInPlace)
            root.setProperty("tab", 2)
            until(lambda: root.property("shown") == "mixer" and root.property("settled"))
            root.setProperty("motion", 0)
            root.setProperty("tab", 1)
            until(lambda: root.property("shown") == "player")
            self.assertTrue(root.property("settled"))

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
            strip = root.findChild(QObject, "notchTabStrip")
            root.setWidth(95)
            QTest.qWait(40)
            self.assertGreater(strip.property("naturalWidth"), strip.width())
            self.assertGreaterEqual(item.width(), item.implicitWidth())
            root.setProperty("order", [2, 1])
            strip.step(1)
            self.assertEqual((root.property("page"), root.property("highlighted")), (2, "Time"))
            strip.step(-1)
            self.assertEqual((root.property("page"), root.property("highlighted")), (1, "Activity"))
            root.setProperty("order", [1])
            strip.step(-1)
            self.assertEqual(root.property("page"), 1)
            root.setProperty("order", [])
            strip.step(1)
            self.assertEqual(root.property("highlighted"), "")
