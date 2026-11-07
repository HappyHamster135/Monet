"""Actual Store pixels: screenshots, fallback paintings/icons and section banners."""
import unittest
import os
import json
from pathlib import Path

from tests import test_store_navigation as navigation

QT = navigation.QT
if QT:
    from PySide6.QtCore import QPointF, QMetaObject, Qt, Q_ARG
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtTest import QTest


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class StoreArtwork(unittest.TestCase):
    setUpClass = classmethod(navigation.StoreNavigation.setUpClass.__func__)
    tearDownClass = classmethod(navigation.StoreNavigation.tearDownClass.__func__)
    tearDown = navigation.StoreNavigation.tearDown
    item = navigation.StoreNavigation.item
    wait_for = navigation.StoreNavigation.wait_for
    capture = navigation.StoreNavigation.capture

    def setUp(self):
        navigation.StoreNavigation.setUp(self)
        if os.environ.get("MONET_TEST_GRAPHICS_API"):
            self.wait_for(self.window.isExposed)
            api = self.window.rendererInterface().graphicsApi().name
            self.assertEqual(api, os.environ["MONET_TEST_GRAPHICS_API"])
            details = dict(api=api, render_loop=os.environ.get("QSG_RENDER_LOOP", "default"))
            if api!="Software" and os.environ.get("MONET_TEST_COLLECT_DRIVER")=="1":
                # Python callbacks on the threaded loop can block on the GIL
                # during GUI/render synchronization. Collect driver data only
                # in the explicit basic-loop run; test threaded pixels separately.
                self.assertEqual(os.environ.get("QSG_RENDER_LOOP"), "basic")
                frames = []
                def collect():
                    # Query QRhi on the render thread, after an actual frame.
                    try:
                        info = self.window.rhi().driverInfo()
                        name = info.deviceName if isinstance(info.deviceName, str) else bytes(info.deviceName).decode("utf-8", "replace")
                        frames.append(dict(device_name=name, device_type=info.deviceType.name,
                                           vendor_id=info.vendorId, device_id=info.deviceId))
                    except Exception as error: frames.append(dict(error=str(error)))
                self.window.afterFrameEnd.connect(collect, Qt.DirectConnection)
                try:
                    self.window.update(); self.wait_for(lambda: bool(frames))
                finally: self.window.afterFrameEnd.disconnect(collect)
                self.assertNotIn("error", frames[0]); details.update(frames[0])
                self.assertNotEqual(details["device_type"], "CpuDevice")
                for software in ("llvmpipe", "softpipe", "swrast", "swiftshader"):
                    self.assertNotIn(software, details["device_name"].lower())
            if os.environ.get("MONET_NAV_CAPTURE"):
                (Path(os.environ["MONET_NAV_CAPTURE"])/("renderer-"+self._testMethodName+".json")).write_text(json.dumps(details, indent=2)+"\n")
        if os.environ.get("MONET_TEST_EXPECT_DPR"):
            self.assertAlmostEqual(self.window.devicePixelRatio(), float(os.environ["MONET_TEST_EXPECT_DPR"]), places=2)
        self.painting = self.make_image("painting.png", 0xff395ba0)
        self.logo = self.make_image("logo.png", 0xffe99f39)
        screens = QGuiApplication.screens()
        if len(screens)>1:
            self.window.setScreen(min(screens, key=lambda screen: screen.geometry().width()))
            self.window.show(); QTest.qWait(100)
        self.window.resize(self.window.minimumWidth(), 620)
        for app in self.shop.apps:
            app.update(shot=self.image, icon=self.logo)
        self.shop.loaded.emit(); QTest.qWait(80)

    def make_image(self, name, color):
        path = Path(self.temporary.name) / name
        image = QImage(320, 180, QImage.Format_RGB32); image.fill(color)
        self.assertTrue(image.save(str(path)))
        return path.as_uri()

    def card(self, screenshot=True):
        for app in self.shop.apps: app["shot"] = self.image if screenshot else ""
        self.shop.loaded.emit()
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "tools")); QTest.qWait(80)
        card = self.item("storePodium-"+self.shop.apps[0]["id"])
        card.setProperty("painting", self.painting)
        card.forceActiveFocus(Qt.TabFocusReason)
        QTest.qWait(max(80, int(self.window.property("speed") * 350) + 50))
        return card

    def assert_color(self, item, point, expected, name):
        def matches():
            location = item.mapToScene(point); scale = self.window.devicePixelRatio()
            if not (0 <= location.x() < self.window.width() and 0 <= location.y() < self.window.height()): return False
            color = self.window.grabWindow().pixelColor(int(location.x()*scale), int(location.y()*scale))
            return max(abs(actual-target) for actual, target in zip((color.red(),color.green(),color.blue()), expected)) <= 6
        try: self.wait_for(matches)
        finally: self.capture(name)

    @staticmethod
    def descendants(item):
        for child in item.childItems():
            yield child
            yield from StoreArtwork.descendants(child)

    def test_podium_screenshot_is_painted(self):
        card = self.card()
        self.assert_color(card, QPointF(card.width()/2, card.width()*0.3), (55,111,104), "artwork-screenshot")
        self.assertEqual(self.shop.actions, [])

    def test_no_screenshot_shows_the_painting_and_app_icon(self):
        card = self.card(False)
        self.assert_color(card, QPointF(card.width()*0.15, card.width()*0.15), (57,91,160), "artwork-fallback-painting")
        self.assert_color(card, QPointF(card.width()/2, card.width()*0.3), (233,159,57), "artwork-fallback-icon")

    def test_failed_screenshot_returns_to_the_painting_and_icon(self):
        card = self.card()
        missing = Path(self.temporary.name) / "unavailable-controlled-image.png"
        app = dict(self.shop.apps[0], shot=missing.as_uri()); card.setProperty("app", app)
        shot = next(item for item in self.descendants(card) if item.objectName()=="storeFramedShot")
        self.wait_for(lambda: self.engine.newQObject(shot).property("status").toInt()==3)
        # This deliberately missing image may warn; all other QML warnings still fail.
        self.errors[:] = [message for message in self.errors if str(missing) not in message]
        self.assert_color(card, QPointF(card.width()*0.15, card.width()*0.15), (57,91,160), "artwork-error-painting")
        self.assert_color(card, QPointF(card.width()/2, card.width()*0.3), (233,159,57), "artwork-error-icon")

    def test_section_banner_is_painted(self):
        banner = self.item("storeShelfBanner"); banner.setProperty("picture", self.painting)
        self.window.contentItem().forceActiveFocus()
        shelf = self.item("storeShelf"); shelf.setProperty("contentY", shelf.property("originY"))
        QTest.qWait(max(80, int(self.window.property("speed") * 350) + 50))
        self.assert_color(banner, QPointF(banner.width()/2, banner.property("paintingHeight")*0.2), (57,91,160), "artwork-banner")
