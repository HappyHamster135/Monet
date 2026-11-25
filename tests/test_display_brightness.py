"""Regression coverage for named monitor controls in Settings."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]


class DisplayBrightness(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux" and all(importlib.util.find_spec(name) for name in
                         ("gi", "dbus", "PySide6")), "Linux Qt and D-Bus")
    def test_two_screens_external_write_keys_and_hotplug(self):
        from PySide6.QtCore import QLibraryInfo
        qml = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
        if not (qml / "org/kde/plasma/private/brightnesscontrolplugin/qmldir").is_file():
            self.skipTest("PowerDevil brightness controls unavailable")
        with private_session() as env:
            result = subprocess.run([sys.executable, str(ROOT / "tests/fixtures/display-brightness-ui.py")],
                                    env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DISPLAY_BRIGHTNESS_UI_OK", result.stdout)
