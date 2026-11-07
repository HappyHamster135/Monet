"""Native menu keys/layout/input, with real delegates and inert external models."""
import gettext
import os
import unittest
from unittest.mock import patch

from tests import test_everyday_search as search
from tests import test_settings_navigation as settings
from tests import test_store_scrolling as scrolling

QT = search.QT
if QT:
    from PySide6.QtCore import QAbstractListModel, QModelIndex, QPointF, QMetaObject, Qt
    from PySide6.QtTest import QTest

    class Apps(QAbstractListModel):
        roles = {int(Qt.DisplayRole): b"display", int(Qt.DecorationRole): b"decoration",
                 int(Qt.UserRole)+1: b"description", int(Qt.UserRole)+2: b"favoriteId", int(Qt.UserRole)+3: b"group"}
        def __init__(self, name, count): super().__init__(); self.name = name; self.size = count
        def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else self.size
        def roleNames(self): return self.roles
        def data(self, index, role):
            if not index.isValid(): return None
            values = {"display": self.name+" "+str(index.row()), "decoration": "application-x-executable",
                      "description": "Controlled menu item", "favoriteId": "fixture-"+str(index.row())+".desktop", "group": "F"}
            name = self.roles.get(role)
            return values.get(name.decode()) if name else None


@unittest.skipUnless(QT, "requires Qt and Plasma")
class MenuNavigation(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    tearDown = search.MenuSearchUI.tearDown
    item = search.MenuSearchUI.item
    query = search.MenuSearchUI.query
    deliver = search.MenuSearchUI.deliver
    wait_for = settings.SettingsNavigation.wait_for
    capture = settings.SettingsNavigation.capture
    assert_visible_in = settings.SettingsNavigation.assert_visible_in
    wheel = scrolling.StoreScrolling.wheel
    bounds = staticmethod(scrolling.StoreScrolling.bounds)

    def setUp(self):
        language = os.environ.get("MONET_SETTINGS_TEST_LANGUAGE", "en")
        words = gettext.translation("monet", localedir=str(settings.ROOT/"linux/share/locale"), languages=[language], fallback=language=="en")
        change = patch.object(self.games, "WORDS", words); change.start(); self.addCleanup(change.stop)
        self.words = self.games.Words()
        search.MenuSearchUI.setUp(self)
        self.pins = Apps("Pinned", 14); self.recent = Apps("Recent", 20); self.all = Apps("All app", 40)
        self.root.setProperty("everyApp", self.all); self.root.setProperty("recent", self.recent)
        apps = self.root.property("apps")
        if hasattr(apps, "toQObject"): apps = apps.toQObject()
        apps.setProperty("favoritesModel", self.pins)
        area = self.window.screen().availableGeometry()
        self.window.resize(min(560, area.width()-32), min(520, area.height()-48)); QTest.qWait(80)

    def reset(self):
        self.root.setProperty("expanded", True)
        QMetaObject.invokeMethod(self.page, "reset"); QTest.qWait(30)

    def test_tab_reaches_pinned_recent_and_all_apps_with_a_visible_current_item(self):
        self.search.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item("menuOtherList").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        pinned = self.item("menuPinned"); self.assertTrue(pinned.hasActiveFocus())
        self.assertGreaterEqual(pinned.property("currentIndex"), 0)
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item("menuRecentFiles").hasActiveFocus())
        self.page.setProperty("everything", True); self.item("menuOtherList").forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item("menuAllApps").hasActiveFocus())

    def test_arrows_cross_pinned_and_recent_and_both_enter_keys_activate_once(self):
        pinned = self.item("menuPinned"); recent = self.item("menuRecentFiles")
        self.search.forceActiveFocus(); QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(30)
        self.assertTrue(pinned.hasActiveFocus()); self.assertEqual(pinned.property("currentIndex"), 0)
        pinned.setProperty("currentIndex", 13)
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(30)
        self.assertTrue(recent.hasActiveFocus()); self.assertEqual(recent.property("currentIndex"), 0)
        QTest.keyClick(self.window, Qt.Key_Up); QTest.qWait(30)
        self.assertTrue(pinned.hasActiveFocus())
        self.page.setProperty("everything", True)
        view = self.item("menuAllApps"); view.forceActiveFocus(); view.setProperty("currentIndex", 0)
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(30)
        self.assertEqual(view.property("currentIndex"), 1)
        for key in (Qt.Key_Return, Qt.Key_Enter):
            self.root.setProperty("launched", "")
            QTest.keyClick(self.window, key); self.assertEqual(self.root.property("launched"), "native-1")

    def test_escape_returns_through_search_and_all_apps_before_closing(self):
        self.reset(); self.page.setProperty("everything", True)
        self.search.setProperty("text", "fixture"); self.search.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(30)
        self.assertEqual(self.search.property("text"), ""); self.assertTrue(self.root.property("expanded"))
        self.assertTrue(self.page.property("everything"))
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(30)
        self.assertFalse(self.page.property("everything")); self.assertTrue(self.root.property("expanded"))
        QTest.keyClick(self.window, Qt.Key_Escape); self.assertFalse(self.root.property("expanded"))

    def test_keyboard_context_menu_is_available_for_selected_apps(self):
        self.page.setProperty("everything", True)
        view = self.item("menuAllApps"); view.forceActiveFocus(); view.setProperty("currentIndex", 2)
        for key, modifiers in ((Qt.Key_Menu, Qt.NoModifier), (Qt.Key_F10, Qt.ShiftModifier)):
            self.root.setProperty("requestedMenu", "")
            QTest.keyClick(self.window, key, modifiers); QTest.qWait(30)
            self.assertEqual(self.root.property("requestedMenu"), "fixture-2.desktop")

    def test_mouse_wheel_and_touchpad_pixels_scroll_every_list(self):
        pinned = self.item("menuPinned"); recent = self.item("menuRecentFiles")
        for view in (pinned, recent):
            for pixel in (False, True):
                with self.subTest(view=view.objectName(), pixel=pixel):
                    self.window.contentItem().forceActiveFocus()
                    first, last = self.bounds(view); self.assertGreater(last, first)
                    view.setProperty("contentY", first); QTest.qWait(20)
                    self.wheel(view, pixel=pixel)
                    self.assertGreater(view.property("contentY"), first)
        self.page.setProperty("everything", True); QTest.qWait(30)
        all_apps = self.item("menuAllApps")
        source = self.query("fixture"); self.deliver(source, [])
        for view in (self.results, all_apps):
            if view is all_apps: self.search.setProperty("text", ""); QTest.qWait(30)
            for pixel in (False, True):
                with self.subTest(view=view.objectName(), pixel=pixel):
                    self.window.contentItem().forceActiveFocus()
                    first, last = self.bounds(view); self.assertGreater(last, first)
                    view.setProperty("contentY", first); QTest.qWait(20)
                    self.wheel(view, pixel=pixel)
                    self.assertGreater(view.property("contentY"), first)

    def test_sections_stay_inside_the_window_on_a_short_screen(self):
        for height in (420, 360, 520):
            self.window.resize(480, min(height, self.window.screen().availableGeometry().height()-48)); QTest.qWait(80)
            for name in ("menuSearch", "menuOtherList", "menuPinned", "menuRecentFiles"):
                item = self.item(name); point = item.mapToScene(QPointF())
                self.assertGreaterEqual(item.height(), 30, name)
                self.assertGreaterEqual(point.y(), 0, name)
                self.assertLessEqual(point.y()+item.height(), self.window.height()+1, name)
        self.capture("menu-short")
