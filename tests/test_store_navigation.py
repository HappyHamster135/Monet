"""Rendered Store keys, image-viewer focus and restored-window bounds."""
import gettext
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_settings_navigation as navigation
from tests import test_settings_feedback as feedback

ROOT = Path(__file__).resolve().parents[1]
QT = navigation.QT
if QT:
    from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, Qt, Q_ARG, Signal, Slot
    from PySide6.QtGui import QFontDatabase, QImage
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest

    class Shop(QObject):
        loaded = Signal(); changed = Signal(str, bool, str); progress = Signal(str, float)
        facts = Signal(str, "QVariant"); wanted = Signal(str)
        jobsChanged = Signal("QVariant"); queueProblem = Signal(str)

        def __init__(self, image):
            super().__init__(); self.actions = []; self.queries = []
            self.featured = None
            self.apps = [dict(id="org.example.Fixture" + str(i), name="Fixture " + str(i),
                              summary="A controlled app for native Store navigation.", developer="Fixture",
                              section="tools", state="get", icon=image, picture=image, released=0,
                              screenshots=[dict(image=image, thumb=image, caption="Controlled screenshot")])
                         for i in range(12)]

        @Slot(result="QVariant")
        def home(self): return dict(rows=[dict(id="everyday", apps=self.apps[:3])], today=self.featured, top=self.apps[:3], fresh=[])
        @Slot(result="QVariant")
        def counts(self): return dict(tools=12, games=12, installed=0)
        @Slot(result="QVariant")
        def windows(self): return []
        @Slot(str, str, str, bool, result="QVariant")
        def section(self, section, order, kind, checked):
            self.queries.append((section, order, kind, checked))
            return dict(apps=self.apps, kinds=[])
        @Slot(str, result="QVariant")
        def app(self, ident): return next((app for app in self.apps if app["id"] == ident), None)
        @Slot(str, result="QVariant")
        def find(self, query): return dict(apps=self.apps, windows=[], instead=None)
        @Slot(str)
        def learn(self, ident): pass
        @Slot(str)
        def install(self, ident): self.actions.append((ident, "install"))
        @Slot(str)
        def open(self, ident): self.actions.append((ident, "open"))
        @Slot(str)
        def remove(self, ident): self.actions.append((ident, "remove"))
        @Slot(str, str)
        def downloadAction(self, ident, action): self.actions.append((ident, action))
        @Slot()
        def poll(self): pass


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class StoreNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        navigation.SettingsNavigation.setUpClass.__func__(cls)
        cls.app.setApplicationName("store-navigation")

    @classmethod
    def tearDownClass(cls):
        navigation.SettingsNavigation.tearDownClass.__func__(cls)

    item = navigation.SettingsNavigation.item
    wait_for = navigation.SettingsNavigation.wait_for
    capture = navigation.SettingsNavigation.capture
    assert_visible_in = navigation.SettingsNavigation.assert_visible_in

    def setUp(self):
        language = os.environ.get("MONET_SETTINGS_TEST_LANGUAGE", "en")
        words = gettext.translation("monet", localedir=str(ROOT / "linux/share/locale"),
                                    languages=[language], fallback=language == "en")
        translation = patch.object(self.games, "WORDS", words)
        translation.start(); self.addCleanup(translation.stop)
        settings = QSettings(); settings.clear()
        if "restored_geometry" in self._testMethodName:
            settings.setValue("Store/windowWidth", 3000)
            settings.setValue("Store/windowHeight", 2000)
        settings.sync()
        self.temporary = tempfile.TemporaryDirectory(prefix="monet-store-navigation-")
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "screenshot.png"
        image = QImage(320, 180, QImage.Format_RGB32); image.fill(0xff376f68); self.assertTrue(image.save(str(path)))
        self.image = path.as_uri(); self.shop = Shop(self.image)
        self.engine = QQmlApplicationEngine(); self.words = self.games.Words(); self.helper = feedback.FakeHelper()
        self.area = self.games.WindowArea()
        self.errors = []; self.engine.warnings.connect(lambda errors: self.errors.extend(e.toString() for e in errors))
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in dict(shop=self.shop, helper=self.helper, windowArea=self.area, firstPage="tools", blurBehind=False,
                                banners=(ROOT / "linux/share/monet/store").as_uri() + "/",
                                art=(ROOT / "linux/share/monet/settings").as_uri() + "/",
                                brush=(ROOT / "linux/share/monet/textures/brush.png").as_uri()).items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/store-app/Store.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.area.watch(self.window)
        self.shop.loaded.emit(); QTest.qWait(100)
        if os.environ.get("QT_SCALE_FACTOR"):
            self.assertAlmostEqual(self.window.devicePixelRatio(), float(os.environ["QT_SCALE_FACTOR"]), places=2)
        if os.environ.get("MONET_TEST_REQUIRE_FONTS"):
            self.assertIn("Inter", QFontDatabase.families())
            self.assertIn("Fraunces 72pt SuperSoft", QFontDatabase.families())
        if os.environ.get("MONET_TEST_REDUCED_MOTION"):
            self.assertGreaterEqual(self.window.property("speed"), 0)
            self.assertLessEqual(self.window.property("speed"), 1 / 200)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(10)
        self.assertFalse(self.errors, "\n".join(self.errors))

    def open_app(self):
        ident = self.shop.apps[0]["id"]
        self.assertTrue(QMetaObject.invokeMethod(self.window, "openApp", Q_ARG("QVariant", ident)))
        QTest.qWait(80)
        self.assertEqual(self.window.property("pageId"), ident)
        return ident

    def test_restored_geometry_fits_the_available_screen(self):
        area = self.window.screen().availableGeometry()
        self.assertLessEqual(self.window.width(), area.width())
        self.assertLessEqual(self.window.height(), area.height())
        self.assertLessEqual(self.window.minimumWidth(), area.width())
        self.assertLessEqual(self.window.minimumHeight(), area.height())
        QTest.qWait(350)
        self.capture("store-fit")

    def test_keypad_enter_selects_sections_sort_and_checked_filter(self):
        section = self.item("storeSection-games"); section.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(30)
        self.assertEqual(self.window.property("section"), "games")
        order = self.item("storeOrder-name"); order.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(30)
        self.assertEqual(self.window.property("order"), "name")
        checked = self.item("storeCheckedFilter"); checked.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(30)
        self.assertTrue(self.window.property("checkedOnly"))
        self.assertTrue(checked.hasActiveFocus())

    def test_image_escape_closes_only_the_image_and_restores_gallery_focus(self):
        ident = self.open_app(); gallery = self.item("storeScreenshotGallery")
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(gallery.hasActiveFocus())
        self.assertTrue(self.item("storeScreenshotFocus").isVisible())
        self.assert_visible_in(gallery, self.item("storeAppPage"))
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: self.window.property("picture") == self.image)
        QTest.qWait(50); QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(50)
        self.assertEqual(self.window.property("picture"), "")
        self.assertEqual(self.window.property("pageId"), ident)
        self.wait_for(gallery.hasActiveFocus)
        self.assert_visible_in(gallery, self.item("storeAppPage"))
        self.capture("store-gallery-focus")

    def test_image_keypad_enter_tab_find_and_close_stay_in_the_viewer(self):
        ident = self.open_app(); gallery = self.item("storeScreenshotGallery")
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(gallery.hasActiveFocus())
        self.assert_visible_in(gallery, self.item("storeAppPage"))
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.wait_for(lambda: self.window.property("picture") == self.image)
        close = self.item("storePictureClose")
        self.wait_for(close.hasActiveFocus)
        for key in (Qt.Key_Tab, Qt.Key_Backtab):
            QTest.keyClick(self.window, key); QTest.qWait(20)
            self.assertTrue(close.hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_F, Qt.ControlModifier); QTest.qWait(20)
        self.assertTrue(close.hasActiveFocus())
        self.capture("store-image-viewer")
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(50)
        self.assertEqual(self.window.property("picture"), "")
        self.assertEqual(self.window.property("pageId"), ident)
        self.wait_for(gallery.hasActiveFocus)
        self.assert_visible_in(gallery, self.item("storeAppPage"))
        self.assertEqual(self.shop.actions, [])

    def test_back_returns_keyboard_focus_to_the_original_app_card(self):
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "home")); QTest.qWait(50)
        card = self.item("storeRanked-" + self.shop.apps[0]["id"])
        card.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(80)
        self.assertEqual(self.window.property("pageId"), self.shop.apps[0]["id"])
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(50)
        self.assertEqual(self.window.property("pageId"), "")
        self.wait_for(card.hasActiveFocus)
        view = card.parentItem()
        while view and not view.inherits("QQuickFlickable"): view = view.parentItem()
        self.assertIsNotNone(view)
        self.assert_visible_in(card, view)

    def test_late_back_focus_does_not_override_a_new_section(self):
        self.open_app()
        QMetaObject.invokeMethod(self.window, "closePage")
        section = self.item("storeSection-games"); section.forceActiveFocus(Qt.TabFocusReason)
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "games"))
        QTest.qWait(50)
        self.assertEqual(self.window.property("section"), "games")
        self.assertTrue(section.hasActiveFocus())

    def test_back_after_the_original_card_is_removed_uses_the_search(self):
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "home")); QTest.qWait(50)
        card = self.item("storeRanked-" + self.shop.apps[0]["id"])
        card.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(50)
        self.assertNotEqual(self.window.property("pageId"), "")
        self.shop.apps = []; self.shop.loaded.emit(); QTest.qWait(50)
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(50)
        self.assertEqual(self.window.property("pageId"), "")
        self.assertTrue(self.item("storeSearch").hasActiveFocus())

    def test_featured_card_opens_details_by_keyboard_and_receives_back_focus(self):
        self.shop.featured = self.shop.apps[0]; self.shop.loaded.emit()
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "home")); QTest.qWait(50)
        card = self.item("storeFeaturedCard"); card.forceActiveFocus(Qt.TabFocusReason)
        self.assertTrue(card.isVisible())
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(50)
        self.assertEqual(self.window.property("pageId"), self.shop.apps[0]["id"])
        self.assertEqual(self.shop.actions, [])
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(50)
        self.wait_for(card.hasActiveFocus)
        view = card.parentItem()
        while view and not view.inherits("QQuickFlickable"): view = view.parentItem()
        self.assertIsNotNone(view)
        self.assert_visible_in(card, view)
