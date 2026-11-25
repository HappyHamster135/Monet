"""Exercise real wheel hit targets, keyboard selection, and the catalog entry points."""
from configparser import ConfigParser
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
from actions import ACTIONS, find_tools

try:
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from favorites_wheel import FavoritesWheel
    from window import Receiver, Window
except ImportError:
    FavoritesWheel = None


class WheelShortcut(unittest.TestCase):
    def test_global_shortcut_and_launcher_action_open_the_same_wheel(self):
        directory = MODULES.parents[1] / "applications"
        desktop = ConfigParser(interpolation=None)
        desktop.read(directory / "monet-utilities.desktop")
        shortcut = ConfigParser(interpolation=None)
        shortcut.read(directory / "org.monet.FavoritesWheel.desktop")
        entry = shortcut["Desktop Entry"]
        self.assertEqual(entry["Exec"], desktop["Desktop Action Wheel"]["Exec"])
        self.assertTrue(entry.getboolean("NoDisplay"))
        self.assertEqual(entry["X-KDE-Shortcuts"], "Meta+Alt+W")


@unittest.skipUnless(FavoritesWheel, "requires Qt widgets")
class Wheel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = QSettings(folder + "/utilities.ini", QSettings.IniFormat)
        with patch("window.QSettings", return_value=self.settings):
            self.window = Window(folder)
        self.receiver = Receiver(self.window)
        self.addCleanup(self.cleanup_widgets)

    def cleanup_widgets(self):
        for widget in (self.window.favorites_wheel, self.window.quick_panel, self.window):
            if widget:
                widget.hide()
                widget.deleteLater()
        self.app.processEvents()

    def favorites(self, keys, hidden=()):
        self.settings.setValue("favorites", json.dumps(keys))
        self.settings.setValue("hidden", json.dumps(list(hidden)))
        self.settings.sync()

    def test_mouse_sectors_are_disjoint_from_center_and_activate_once(self):
        keys = ["shelf", "ports", "notes", "apps", "calendars", "downloads", "display", "files"]
        self.favorites(keys)
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertFalse(self.window.isVisible())
        calls = []
        wheel.chosen.disconnect(self.window.open_favorite)
        wheel.chosen.connect(calls.append)
        for i, key in enumerate(keys):
            if i:
                self.window.Open(["wheel"])
            center = wheel.rect().center()
            self.assertFalse(any(button.hitButton(center) for button in wheel.buttons))
            angle = math.tau*i/len(keys) - math.pi/2
            x = round(center.x() + .36*wheel.width()*math.cos(angle))
            y = round(center.y() + .36*wheel.height()*math.sin(angle))
            point = QPoint(x, y)
            button = wheel.childAt(point)
            self.assertIs(button, wheel.buttons[i])
            self.assertEqual(button.accessibleName(), ACTIONS[key].name)
            self.assertEqual([b.key for b in wheel.buttons if b.hitButton(point)], [key])
            QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, point)
            self.assertFalse(wheel.isVisible())
        self.assertEqual(calls, keys)

    def test_arrows_follow_hover_wrap_and_escape_dismisses(self):
        self.favorites(["shelf", "notes", "ports"])
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        chosen = []
        wheel.chosen.disconnect(self.window.open_favorite)
        wheel.chosen.connect(chosen.append)
        wheel.highlight(wheel.buttons[1])
        self.assertEqual(wheel.label.text(), ACTIONS["notes"].name)
        QTest.keyClick(wheel.buttons[0], Qt.Key_Right)
        self.assertIs(wheel.current, wheel.buttons[2])
        QTest.keyClick(wheel.current, Qt.Key_Down)
        self.assertIs(wheel.current, wheel.buttons[0])
        QTest.keyClick(wheel.current, Qt.Key_Left)
        QTest.keyClick(wheel.current, Qt.Key_Return)
        self.assertEqual(chosen, ["ports"])
        self.window.Open(["wheel"])
        QTest.keyClick(wheel.current, Qt.Key_Escape)
        self.assertFalse(wheel.isVisible())
        self.assertEqual(chosen, ["ports"])
        self.assertFalse(self.window.isVisible())

    def test_reopens_with_current_favorites_and_rejects_stale_requests(self):
        self.favorites(["wheel", "notes", "shelf", "ports"], ["shelf"])
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertEqual([b.key for b in wheel.buttons], ["notes", "ports"])
        self.window.Open(["wheel"])
        self.assertFalse(wheel.isVisible())
        self.favorites(["files"])
        self.window.Open(["wheel"])
        self.assertEqual([b.key for b in wheel.buttons], ["files"])
        self.assertTrue(wheel.buttons[0].hitButton(QPoint(wheel.width()//2, 10)))
        self.assertTrue(wheel.buttons[0].hitButton(QPoint(wheel.width()//2, wheel.height()-10)))
        self.window.Open(["wheel"])
        self.assertFalse(self.receiver.ShowWheel("old-request", "640"))
        self.assertFalse(self.receiver.ShowWheel("1", "-4"))
        self.favorites(["shelf"], ["wheel"])
        self.window.Open(["wheel"])
        self.assertFalse(wheel.isVisible())
        self.assertFalse(self.window.isVisible())

    def test_shortcut_defers_catalog_work_until_a_window_needs_it(self):
        self.favorites(["shelf", "notes"])
        with patch("window.QSettings", return_value=self.settings), patch("window.find_tools", wraps=find_tools) as search:
            window = Window(self.window.helpers, defer_catalog=True)
            self.addCleanup(window.deleteLater)
            window.Open(["wheel"])
            self.addCleanup(window.favorites_wheel.deleteLater)
            search.assert_not_called()
            self.assertFalse(window.isVisible())
            window.favorites_wheel.hide()
            window.Open(["shelf"])
            self.assertTrue(window.isVisible())
            window.home()
            self.assertGreater(window.catalog.count(), 1)
            window.close()

    def test_empty_favorites_open_the_existing_editor(self):
        self.favorites(["wheel"])
        self.window.Open(["wheel"])
        self.assertIsNone(self.window.favorites_wheel)
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.quick_panel.isVisible())
        self.assertEqual(self.window.quick_panel.stack.currentIndex(), 1)
