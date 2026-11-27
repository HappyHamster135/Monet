"""Exercise the actual widget host and the settings entrance with disposable preferences."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
from actions import ACTIONS, DESKTOP_TOOLS, FULL_APPLICATIONS, notch_catalog
try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from notch_tools import NotchTools
    from window import Receiver, Window
except ImportError:
    NotchTools = None


class Catalog(unittest.TestCase):
    def test_every_action_has_a_known_group_and_dispatch(self):
        catalog = notch_catalog()
        self.assertEqual({row["key"] for row in catalog["rows"]}, set(ACTIONS) - FULL_APPLICATIONS)
        groups = {group["key"] for group in catalog["groups"]}
        for row in catalog["rows"]:
            self.assertIn(row["group"], groups)
            self.assertEqual(row["immediate"], row["key"] in DESKTOP_TOOLS)


@unittest.skipUnless(NotchTools, "requires Qt Widgets")
class NativeTool(unittest.TestCase):
    def test_reuse_and_stale_close(self):
        self.app = QApplication.instance() or QApplication([])
        self.app.setQuitOnLastWindowClosed(False)
        window = Window("/usr/libexec", defer_catalog=True)
        owner = Receiver(window)
        tools = NotchTools(owner)
        with tempfile.TemporaryDirectory() as folder:
            window.settings = QSettings(folder + "/tools.ini", QSettings.IniFormat)
            area = self.app.primaryScreen().geometry()
            args = dict(action="show", id="17.1", key="snippets", screen="", x=area.x()+5, y=area.y()+5, w=270, h=200)
            def call(**changes):
                return json.loads(tools.handle(json.dumps(dict(args, **changes))))["ok"]
            self.assertFalse(call(key="empty-trash"))
            self.assertTrue(call())
            self.assertFalse(window.isVisible())
            self.assertTrue(tools.scroll.widget().isVisible())
            tools.scroll.widget().edit.setPlainText("unsaved draft")
            self.assertTrue(call(action="close", id="17.0"))
            self.assertTrue(tools.area.isVisible())
            self.assertTrue(call(action="close"))
            self.assertFalse(tools.area.isVisible())
            self.assertTrue(call(id="17.2"))
            self.assertEqual(tools.scroll.widget().edit.toPlainText(), "unsaved draft")
            tools.hide()
            window.settings.setValue("hidden", '["snippets"]')
            self.assertFalse(call())
            self.assertFalse(tools.area.isVisible())
