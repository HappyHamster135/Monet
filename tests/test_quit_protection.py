"""Shortcut-specific settings, application selection, and persisted defaults."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication
    from quit_protection import AppPicker, QuitProtection
except ImportError:
    QuitProtection = None


@unittest.skipIf(QuitProtection is None, "requires Qt")
class ProtectionSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "protection.ini")
        self.panel = self.open()
        self.quit = self.panel.tabs.widget(0)
        self.close = self.panel.tabs.widget(1)

    def open(self):
        return QuitProtection(QSettings(self.path, QSettings.IniFormat))

    def test_opening_settings_enables_neither_shortcut(self):
        self.assertFalse(self.quit.enable.isChecked())
        self.assertFalse(self.close.enable.isChecked())
        self.assertFalse(self.quit.options.isEnabled())
        self.assertFalse(Path(self.path).exists())

    def test_modes_are_independent_and_keep_the_users_timing_and_scope(self):
        self.quit.enable.setChecked(True)
        self.quit.mode.setCurrentIndex(self.quit.mode.findData("twice"))
        self.quit.interval.setValue(1.15)
        self.quit.scope.setCurrentIndex(self.quit.scope.findData("selected"))
        self.assertFalse(self.quit.status.isHidden())
        self.quit.apps = ["org.kde.kwrite.desktop"]
        self.quit.save()
        self.close.mode.setCurrentIndex(self.close.mode.findData("modifier"))
        self.close.modifier.setCurrentIndex(self.close.modifier.findData("alt"))
        reopened = self.open()
        quit, close = (reopened.tabs.widget(i) for i in (0, 1))
        self.assertEqual(quit.interval.value(), 1.15)
        self.assertTrue(quit.form.isRowVisible(quit.interval))
        self.assertFalse(quit.form.isRowVisible(quit.hold))
        self.assertEqual(quit.apps, ["org.kde.kwrite.desktop"])
        self.assertTrue(quit.status.isHidden())
        self.assertFalse(close.enable.isChecked())
        self.assertEqual(close.modifier.currentData(), "alt")
        self.assertEqual(close.scope.currentData(), "all")

    def test_picker_search_keeps_checked_and_uninstalled_applications(self):
        apps = {"org.monet.Editor.desktop": ("Editor", ""), "org.monet.Other.desktop": ("Other", "")}
        with patch("quit_protection.installed_apps", return_value=dict(apps)):
            picker = AppPicker(["old.desktop", "org.monet.Other.desktop"])
        picker.search.setText("editor")
        item = picker.items.item(0)
        self.assertEqual(item.data(Qt.UserRole), "org.monet.Editor.desktop")
        item.setCheckState(Qt.Checked)
        self.assertTrue(picker.items.item(1).isHidden())
        self.assertEqual(picker.selection(), sorted([*apps, "old.desktop"]))
