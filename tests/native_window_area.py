"""Actual QScreen switches in a required private two-screen Xvfb session."""
import json
import unittest

from PySide6.QtCore import QMetaObject, QSettings, Qt
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtTest import QTest

from tests import test_settings_navigation as settings
from tests import test_store_navigation as store


def exercise(case):
    screens = QGuiApplication.screens()
    case.assertEqual(len(screens), 2, "This fixture requires two actual private QScreens")
    primary, small = sorted(screens, key=lambda screen: screen.geometry().width(), reverse=True)
    window = case.window
    case.assertIs(window.screen(), primary)
    evidence = []

    def check(label, screen):
        expected = screen.availableGeometry()
        case.wait_for(lambda: case.area.geometry == expected and window.width() <= expected.width() - 32
                      and window.height() <= expected.height() - 48)
        case.assertEqual(window.property("availableWidth"), expected.width())
        case.assertEqual(window.property("availableHeight"), expected.height())
        case.assertLessEqual(window.minimumWidth(), expected.width() - 32)
        case.assertLessEqual(window.minimumHeight(), expected.height() - 48)
        evidence.append(dict(label=label, screen=screen.name(), available=[expected.x(), expected.y(), expected.width(), expected.height()],
                             size=[window.width(), window.height()], minimum=[window.minimumWidth(), window.minimumHeight()]))

    check("restored", primary)
    page = window.property("page") or window.property("section")
    search_name = "settingsSearch" if window.property("page") else "storeSearch"
    search = case.item(search_name)
    window.setScreen(small); window.show(); QTest.qWait(100)
    check("smaller screen", small)
    window.resize(small.availableGeometry().width() + 100, small.availableGeometry().height() + 100)
    check("late oversized configure", small)
    case.assertIs(case.item(search_name), search)
    case.assertEqual(window.property("page") or window.property("section"), page)
    case.capture(("settings" if window.property("page") else "store") + "-small-screen")

    # Merely returning to a larger display must not replace the user's smaller
    # width with the app's default width.
    chosen_width = min(window.minimumWidth() + 24, small.availableGeometry().width() - 32)
    window.resize(chosen_width, window.minimumHeight())
    # X11 migration recreates the platform window on another X screen. Let
    # the previous resize reach that window before starting the migration.
    QGuiApplication.sync(); QTest.qWait(50)
    case.assertEqual(window.width(), chosen_width)
    window.setScreen(primary); window.show(); QTest.qWait(100)
    check("larger screen", primary)
    case.assertEqual(window.width(), max(chosen_width, window.minimumWidth()))

    window.showMinimized(); QTest.qWait(30)
    QMetaObject.invokeMethod(window, "fitAvailableScreen")
    case.assertEqual(window.visibility(), QWindow.Minimized)
    window.showNormal(); QTest.qWait(100)
    check("restore from minimized", primary)
    window.setScreen(small); window.show(); QTest.qWait(100)
    check("move after restore", small)

    window.showMaximized(); QTest.qWait(30)
    QMetaObject.invokeMethod(window, "fitAvailableScreen")
    case.assertEqual(window.visibility(), QWindow.Maximized)
    window.showFullScreen(); QTest.qWait(30)
    QMetaObject.invokeMethod(window, "fitAvailableScreen")
    case.assertEqual(window.visibility(), QWindow.FullScreen)
    window.showNormal(); QTest.qWait(100)
    check("return to normal", small)
    print("WINDOW_AREA " + json.dumps(evidence), flush=True)


class SettingsScreens(unittest.TestCase):
    keep_window_size = True
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    tearDown = settings.SettingsNavigation.tearDown
    item = settings.SettingsNavigation.item
    wait_for = settings.SettingsNavigation.wait_for
    capture = settings.SettingsNavigation.capture

    def setUp(self):
        saved = QSettings(); saved.setValue("Window/windowWidth", 3000); saved.setValue("Window/windowHeight", 2000); saved.sync()
        settings.SettingsNavigation.setUp(self)

    def test_restored_geometry_and_screen_switch(self): exercise(self)


class StoreScreens(unittest.TestCase):
    setUpClass = classmethod(store.StoreNavigation.setUpClass.__func__)
    tearDownClass = classmethod(store.StoreNavigation.tearDownClass.__func__)
    setUp = store.StoreNavigation.setUp
    tearDown = store.StoreNavigation.tearDown
    item = store.StoreNavigation.item
    wait_for = store.StoreNavigation.wait_for
    capture = store.StoreNavigation.capture

    def test_restored_geometry_and_screen_switch(self): exercise(self)
