"""Native Store scroll input, viewport clipping and small-output card readability."""
import time
import unittest

from tests import test_store_navigation as navigation

QT = navigation.QT
if QT:
    from PySide6.QtCore import QPoint, QPointF, QRect, QMetaObject, QUrl, Qt, Q_ARG
    from PySide6.QtGui import QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QSignalSpy, QTest


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class StoreScrolling(unittest.TestCase):
    setUpClass = classmethod(navigation.StoreNavigation.setUpClass.__func__)
    tearDownClass = classmethod(navigation.StoreNavigation.tearDownClass.__func__)
    setUp = navigation.StoreNavigation.setUp
    tearDown = navigation.StoreNavigation.tearDown
    item = navigation.StoreNavigation.item
    wait_for = navigation.StoreNavigation.wait_for
    capture = navigation.StoreNavigation.capture
    open_app = navigation.StoreNavigation.open_app
    assert_visible_in = navigation.StoreNavigation.assert_visible_in

    def choose(self, section):
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", section))
        QTest.qWait(80)

    def views(self):
        self.window.resize(self.window.minimumWidth(), 520); QTest.qWait(80)
        self.choose("home"); yield self.item("storeHome")
        self.choose("tools"); yield self.item("storeShelf")
        self.window.setProperty("query", "fixture"); QTest.qWait(250)
        yield self.item("storeResults")
        self.window.setProperty("query", ""); self.open_app()
        yield self.item("storeAppPage")
        jobs = [dict(id="org.example.Job"+str(i), name="Controlled download "+str(i), action="install",
                     state="failed", progress=0.2, error="offline") for i in range(12)]
        self.shop.jobsChanged.emit(jobs); self.choose("downloads")
        yield self.item("storeDownloads")

    @staticmethod
    def bounds(view):
        first = view.property("originY") - view.property("topMargin")
        last = max(first, view.property("originY") + view.property("contentHeight") - view.height() + view.property("bottomMargin"))
        return first, last

    def wheel(self, view, pixel=False, modifiers=None, amount=-80):
        if modifiers is None: modifiers = Qt.NoModifier
        point = view.mapToScene(QPointF(view.width() - 16, view.height() / 2))
        screen = QPointF(self.window.mapToGlobal(point.toPoint()))
        QTest.mouseMove(self.window, point.toPoint()); QTest.qWait(20)
        if pixel:
            device = QPointingDevice("Store fixture touchpad", 43, QInputDevice.TouchPad, QPointingDevice.Finger,
                                     QInputDevice.Position | QInputDevice.PixelScroll | QInputDevice.Scroll, 2, 0)
            samples = [(Qt.ScrollBegin, 0), (Qt.ScrollUpdate, amount), (Qt.ScrollEnd, 0)]
        else:
            device = QPointingDevice.primaryPointingDevice(); samples = [(Qt.NoScrollPhase, -120)]
        observed = []
        for phase, delta in samples:
            event = QWheelEvent(point, screen, QPoint(0, delta) if pixel else QPoint(),
                                QPoint() if pixel else QPoint(0, delta), Qt.NoButton, modifiers, phase,
                                False, Qt.MouseEventSynthesizedBySystem if pixel else Qt.MouseEventNotSynthesized, device)
            event.setTimestamp(int(time.monotonic() * 1000))
            QGuiApplication.sendEvent(self.window, event); QTest.qWait(20)
            observed.append((str(phase), event.isAccepted(), view.property("contentY")))
        QTest.qWait(350)
        return observed

    def test_wheel_and_precise_touchpad_input_stay_in_each_store_panel(self):
        nav = self.item("storeNavigation")
        for view in self.views():
            self.window.contentItem().forceActiveFocus()
            first, last = self.bounds(view); self.assertGreater(last, first)
            for pixel in (False, True):
                for target, other in ((view, nav), (nav, view)):
                    with self.subTest(view=view.objectName(), target=target.objectName(), pixel=pixel):
                        start = self.bounds(target)[0]; target.setProperty("contentY", start)
                        other.setProperty("contentY", self.bounds(other)[0]); QTest.qWait(30)
                        other_before = other.property("contentY")
                        samples = self.wheel(target, pixel)
                        self.assertGreater(target.property("contentY"), start, samples)
                        if pixel: self.assertAlmostEqual(target.property("contentY") - start, min(80, self.bounds(target)[1] - start), delta=1)
                        self.assertAlmostEqual(other.property("contentY"), other_before, delta=1)
                        if pixel:
                            previous = target.property("contentY")
                            self.wheel(target, pixel=True, amount=40)
                            self.assertAlmostEqual(target.property("contentY"), max(start, previous - 40), delta=1)
        self.assertEqual(self.shop.actions, [])

    def test_page_keys_and_modified_wheel_use_viewport_steps_and_keep_bounds(self):
        for view in self.views():
            with self.subTest(view=view.objectName()):
                first, last = self.bounds(view); view.forceActiveFocus(Qt.TabFocusReason)
                history = []
                def moved(): history.append((view.property("originY"), view.property("contentY")))
                view.contentYChanged.connect(moved)
                QTest.keyClick(self.window, Qt.Key_Home); QTest.qWait(30)
                view.contentYChanged.disconnect(moved)
                self.assertAlmostEqual(view.property("contentY"), first, delta=1,
                    msg=str(dict(history=history, focus=self.window.activeFocusItem().objectName(),
                        focus_type=self.window.activeFocusItem().metaObject().className(),
                        tab_focus=self.window.activeFocusItem().activeFocusOnTab(), current=view.property("currentIndex"))))
                QTest.keyClick(self.window, Qt.Key_PageDown); QTest.qWait(200)
                self.assertAlmostEqual(view.property("contentY"), min(last, first + view.height()), delta=1)
                QTest.keyClick(self.window, Qt.Key_End); QTest.qWait(200)
                self.assertAlmostEqual(view.property("contentY"), last, delta=1)
                QTest.keyClick(self.window, Qt.Key_Home); QTest.qWait(100)
                self.wheel(view, modifiers=Qt.ControlModifier)
                self.assertAlmostEqual(view.property("contentY"), min(last, first + view.height()), delta=1)
                view.setProperty("contentY", last)
                self.wheel(view, pixel=True)
                self.assertAlmostEqual(view.property("contentY"), last, delta=1)

    @staticmethod
    def descendants(item):
        for child in item.childItems():
            yield child
            yield from StoreScrolling.descendants(child)

    def test_podium_names_and_sort_choices_fit_a_small_output_without_recreating_focus(self):
        screens = QGuiApplication.screens()
        if len(screens) > 1:
            self.window.setScreen(min(screens, key=lambda screen: screen.geometry().width())); self.window.show()
        self.choose("tools"); QTest.qWait(120)
        card = self.item("storePodium-"+self.shop.apps[0]["id"])
        card.forceActiveFocus(Qt.TabFocusReason)
        for width in (self.window.minimumWidth(), min(1000, self.area.width - 32), self.window.minimumWidth()):
            self.window.resize(width, self.window.minimumHeight()); QTest.qWait(100)
            self.assertIs(self.item(card.objectName()), card); self.assertTrue(card.hasActiveFocus())
            cards = [self.item("storePodium-"+app["id"]) for app in self.shop.apps[:3]]
            for item, app in zip(cards, self.shop.apps):
                label = next(text for text in self.descendants(item)
                             if text.inherits("QQuickText") and text.property("text") == app["name"])
                with self.subTest(width=width, name=app["name"]):
                    self.assertGreater(label.width(), 50)
                    self.assertFalse(label.property("truncated"))
                    point = label.mapToItem(item, QPointF())
                    self.assertGreaterEqual(point.x(), 0); self.assertLessEqual(point.x()+label.width(), item.width()+1)
                    self.assertLessEqual(point.y()+label.height(), item.height()+1)
            shelf = self.item("storeShelf")
            for control in ("storeOrder-popular", "storeOrder-updated", "storeOrder-name", "storeCheckedFilter"):
                item = self.item(control); point = item.mapToItem(shelf, QPointF())
                self.assertGreaterEqual(point.x(), 0, control)
                self.assertLessEqual(point.x()+item.width(), shelf.width()+1, control)
                for text in (child for child in self.descendants(item)
                             if child.inherits("QQuickText") and child.isVisible() and child.property("text")):
                    point = text.mapToItem(item, QPointF())
                    self.assertFalse(text.property("truncated"), text.property("text"))
                    self.assertLessEqual(point.x()+text.width(), item.width()+1, text.property("text"))
                    self.assertLessEqual(point.y()+text.height(), item.height()+1, text.property("text"))
            image = self.window.grabWindow(); scale = self.window.devicePixelRatio()
            # The centered title has neutral ink/paper. An offscreen teal
            # verification mark must not paint over it after focus scrolling.
            green = sum(1 for x in range(int((self.window.width()/2-70)*scale), int((self.window.width()/2+70)*scale))
                        for y in range(int(8*scale), int(32*scale))
                        if image.pixelColor(x,y).green() > image.pixelColor(x,y).red()+12
                        and image.pixelColor(x,y).green() > image.pixelColor(x,y).blue()+6)
            self.assertEqual(green, 0, (width, scale, green))
        self.assertEqual(self.shop.actions, []); self.capture("store-narrow-podium")

    def test_grid_arrow_navigation_opens_the_selected_app_with_enter(self):
        self.window.resize(self.window.minimumWidth(), 520); self.choose("tools")
        shelf = self.item("storeShelf"); shelf.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(60)
        index = shelf.property("currentIndex"); self.assertGreater(index, 0)
        QTest.keyClick(self.window, Qt.Key_Up); QTest.qWait(60)
        self.assertLess(shelf.property("currentIndex"), index)
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(60)
        index = shelf.property("currentIndex")
        first = self.item("storeShelfCard-"+self.shop.apps[3]["id"])
        first.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(60)
        self.assertEqual(shelf.property("currentIndex"), 0)
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(60)
        index = shelf.property("currentIndex"); self.assertGreater(index, 0)
        app = self.shop.apps[3 + index]
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(60)
        self.assertEqual(self.window.property("pageId"), app["id"])
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(80)
        focus = self.window.activeFocusItem()
        self.assertEqual(focus.property("app")["id"], app["id"])
        self.assert_visible_in(focus, shelf)
        self.assertEqual(self.shop.actions, [])

    def test_sidebar_glyphs_stay_inside_their_viewport_when_scrolled(self):
        self.window.resize(self.window.minimumWidth(), 520); self.choose("tools")
        nav = self.item("storeNavigation"); first, last = self.bounds(nav)
        positions = [last, (first+last)/2] + [(first+last)/2 + offset for offset in range(-20, 21, 2)]
        for position in positions:
            nav.setProperty("contentY", max(first, min(last, position))); QTest.qWait(30)
            image = self.window.grabWindow(); scale = self.window.devicePixelRatio()
            top = nav.mapToScene(QPointF()).y()
            for edge, start, end in (("above", 42, top-3),
                                     ("below", top+nav.height()+3, self.window.height()-3)):
                white = sum(1 for x in range(int(24*scale), int(36*scale))
                            for y in range(int(start*scale), int(end*scale))
                            if min(image.pixelColor(x,y).red(), image.pixelColor(x,y).green(), image.pixelColor(x,y).blue()) > 253)
                self.assertLessEqual(white, 4, (position, scale, edge, white))
        self.capture("store-sidebar-clipping")

    def test_scroll_background_drag_and_app_clicks_keep_working(self):
        method = self.window.metaObject().indexOfSignal("backgroundMoveRequested()")
        spy = QSignalSpy(self.window, self.window.metaObject().method(method))
        for view in self.views():
            with self.subTest(view=view.objectName()):
                self.window.contentItem().forceActiveFocus()
                point = view.mapToScene(QPointF(view.width()-4, view.height()/2)).toPoint()
                before = spy.count(); position = view.property("contentY")
                QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, point)
                QTest.mouseMove(self.window, point-QPoint(40,0), 25)
                QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, point-QPoint(40,0)); QTest.qWait(20)
                self.assertEqual(spy.count(), before+1)
                self.assertEqual(view.property("contentY"), position)
        self.choose("tools")
        card = self.item("storePodium-"+self.shop.apps[0]["id"])
        card.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(80)
        point = card.mapToScene(QPointF(card.width()/2, min(card.height()/2, 40))).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point); QTest.qWait(60)
        self.assertEqual(self.window.property("pageId"), self.shop.apps[0]["id"])
        self.assertEqual(self.shop.actions, [])

    def test_fully_clipped_filter_does_not_paint_outside_its_viewport(self):
        self.window.resize(self.window.minimumWidth(), 520); self.choose("tools")
        self.window.contentItem().forceActiveFocus()
        shelf = self.item("storeShelf"); checked = self.item("storeCheckedFilter")
        shelf.setProperty("contentY", shelf.property("contentY") + checked.mapToItem(shelf, QPointF()).y()+checked.height()+20)
        QTest.qWait(300)
        self.assertLess(checked.mapToItem(shelf, QPointF()).y()+checked.height(), 0)
        before = self.window.grabWindow(); self.capture("store-header-before")
        position = shelf.property("contentY")
        shapes = [item for item in self.descendants(checked) if item.inherits("QQuickShape")]
        self.assertTrue(shapes)
        for shape in shapes: shape.setVisible(False)
        QTest.qWait(80)
        after = self.window.grabWindow(); self.capture("store-header-hidden")
        self.assertAlmostEqual(shelf.property("contentY"), position)
        scale = self.window.devicePixelRatio(); top = shelf.mapToScene(QPointF()).y()
        area = QRect(0, 0, before.width(), max(0, int(top * scale)-2))
        self.assertEqual(before.copy(area), after.copy(area), "An offscreen header changed pixels above its viewport")

    def test_shared_glyph_clip_tracks_geometry_and_nested_intersections(self):
        self.engine.loadData(b'''import QtQuick
import "../games"
Window {
    width: 160; height: 160; visible: true; color: "#FFFFFF"
    Item {
        objectName: "clipOuter"; x: 20; y: 20; width: 100; height: 100; clip: true
        Item {
            objectName: "clipInner"; width: 100; height: 100; clip: true
            Item {
                objectName: "clipMoving"; x: 10; y: 10; width: 20; height: 20; transformOrigin: Item.TopLeft
                Glyph { objectName: "clipGlyph"; width: 20; height: 20; path: "M2 2h20v20H2z"; color: "#378273" }
            }
        }
    }
}''', QUrl.fromLocalFile(str(navigation.ROOT / "linux/share/monet/store-app/clip-fixture.qml")))
        self.assertEqual(len(self.engine.rootObjects()), 2, self.errors)
        scene = self.engine.rootObjects()[1]; QTest.qWait(80)
        items = {item.objectName(): item for item in self.descendants(scene.contentItem()) if item.objectName()}
        mark, moving, outer, inner = (items[name] for name in ("clipGlyph", "clipMoving", "clipOuter", "clipInner"))
        def check(expected):
            QTest.qWait(30)
            self.assertEqual(not scene.grabWindow().allGray(), expected, "Unexpected colored pixels from the clipped glyph")
            self.assertTrue(mark.isVisible(), "Culling the paint must keep the glyph's layout slot")
        try:
            check(True)
            moving.setX(120); check(False)
            moving.setX(10); check(True)
            outer.setWidth(5); check(False)
            outer.setWidth(100); check(True)
            moving.setScale(2); moving.setX(-50); check(False)
            moving.setScale(3); check(True)
            moving.setX(20); moving.setY(20); moving.setRotation(180); check(True)
            moving.setX(-5); check(False)
            moving.setTransformOrigin(QQuickItem.BottomRight); check(True)
            moving.setTransformOrigin(QQuickItem.TopLeft); check(False)
            moving.setRotation(0); check(True)
            moving.setScale(1); moving.setX(20); moving.setY(10)
            inner.setX(90); check(False)
            inner.setX(50); check(True)
            outer.setClip(False); inner.setX(90); check(True)
        finally:
            scene.close()
