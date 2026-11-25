"""The launcher and its editor share ordered favorites with the wheel and search."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
from actions import ACTIONS, find_tools, preferences

try:
    from PySide6.QtCore import QSettings, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QTreeWidget
    from quick_panel import QuickPanel
except ImportError:
    QuickPanel = None


@unittest.skipUnless(QuickPanel, "requires Qt widgets")
class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = QuickPanel()
        self.addCleanup(self.panel.close)

    def test_single_click_keyboard_and_hidden_tools(self):
        keys = ["ports", "notes", "shelf", "quick-panel"]
        chosen = []
        self.panel.chosen.connect(chosen.append)
        self.panel.present(keys, ["notes"])
        self.assertEqual(self.panel.keys, ["ports", "shelf"])
        self.app.processEvents()
        rect = self.panel.grid.visualItemRect(self.panel.grid.item(1))
        QTest.mouseClick(self.panel.grid.viewport(), Qt.LeftButton, pos=rect.center())
        self.assertEqual(chosen, ["shelf"])
        self.assertFalse(self.panel.isVisible())
        self.panel.present(keys, ["notes"])
        self.panel.grid.setCurrentRow(0)
        QTest.keyClick(self.panel.grid, Qt.Key_Right)
        QTest.keyClick(self.panel.grid, Qt.Key_Return)
        self.assertEqual(chosen, ["shelf", "shelf"])

    def test_edit_preserves_order_and_empty_panel_is_recoverable(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "utilities.ini"), QSettings.IniFormat)
            settings.setValue("hidden", '["mic"]')
            self.panel.reordered.connect(lambda keys: settings.setValue("favorites", json.dumps(keys)))
            self.panel.present(["notes", "shelf", "ports"], ["mic"])
            self.panel.edit()
            self.assertEqual(self.panel.available.findData("mic"), -1)
            self.assertEqual(self.panel.available.findData("quick-panel"), -1)
            self.panel.order.setCurrentRow(2)
            self.panel.up.click()
            self.assertEqual(preferences(settings)[0], ["notes", "ports", "shelf"])
            self.panel.down.click()
            self.assertEqual(self.panel.keys, ["notes", "shelf", "ports"])
            for _ in range(3):
                self.panel.remove.click()
            self.assertEqual(self.panel.keys, [])
            self.panel.reject()
            self.assertTrue(self.panel.isVisible() and self.panel.empty.isVisible())
            self.panel.edit()
            self.panel.available.setCurrentIndex(self.panel.available.findData("color"))
            self.panel.add.click()
            self.panel.available.setCurrentIndex(self.panel.available.findData("notes"))
            self.panel.add.click()
            self.panel.reject()
            self.assertEqual([k for k, _ in find_tools("", *preferences(settings))][:2], ["color", "notes"])
            self.panel.reject()
            self.assertFalse(self.panel.isVisible())
            self.panel.present(*preferences(settings))
            self.assertEqual(self.panel.keys, ["color", "notes"])

    def test_catalog_changes_preserve_custom_order_and_hidden_panel_stays_closed(self):
        from window import Window
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "utilities.ini"), QSettings.IniFormat)
            settings.setValue("favorites", '["color","ports","notes"]')
            with patch("window.QSettings", return_value=settings):
                window = Window(folder)
            def customize():
                dialog = QApplication.activeModalWidget()
                tree = dialog.findChild(QTreeWidget)
                for row in range(tree.topLevelItemCount()):
                    tool = tree.topLevelItem(row)
                    if tool.data(0, Qt.UserRole) in ("ports", "quick-panel"):
                        tool.setCheckState(1, Qt.Unchecked)
                    if tool.data(0, Qt.UserRole) == "shelf":
                        tool.setCheckState(2, Qt.Checked)
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
            QTimer.singleShot(0, customize)
            window.customize()
            self.assertEqual(preferences(settings)[0], ["color", "notes", "shelf"])
            window.Open(["quick-panel"])
            self.assertIsNone(window.quick_panel)
            self.assertFalse(window.isVisible())
            window.close()

    def test_narrow_panel_keeps_last_tile_reachable_by_keyboard(self):
        tools = [key for key in ACTIONS if key != "quick-panel"]
        self.panel.present(tools, [])
        self.panel.resize(310, 260)
        self.app.processEvents()
        self.assertGreater(self.panel.grid.verticalScrollBar().maximum(), 0)
        first = self.panel.grid.visualItemRect(self.panel.grid.item(0))
        third = self.panel.grid.visualItemRect(self.panel.grid.item(2))
        self.assertGreater(third.top(), first.top())
        QTest.keyClick(self.panel.grid, Qt.Key_End)
        self.app.processEvents()
        last = self.panel.grid.currentItem()
        self.assertEqual(last.data(Qt.UserRole), tools[-1])
        self.assertTrue(self.panel.grid.viewport().rect().contains(self.panel.grid.visualItemRect(last).center()))

    def test_panel_can_hold_more_than_one_wheel(self):
        self.panel.present(["shelf", "notes", "color", "screenshot", "awake", "sound", "ports"], [])
        self.panel.edit()
        self.panel.add.click()
        self.panel.add.click()
        self.assertEqual(len(self.panel.keys), 9)
        self.panel.finish_editing()
        self.assertEqual(self.panel.grid.count(), 9)
