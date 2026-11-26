"""Direct desktop actions and their confirmation dialog, using disposable settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_look import quick_helper

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from window import Window
except ImportError:
    Window = None


class DesktopAction(unittest.TestCase):
    def setUp(self):
        self.helper = quick_helper()

    def test_switches_from_effective_appearance_and_can_restore_schedule(self):
        with patch.object(self.helper, "run") as read, patch.object(self.helper, "set_light") as write:
            for value, target in (("hours smoke", "mist"), ("mist mist", "smoke"), ("hours mist", "smoke")):
                read.return_value = value
                self.assertTrue(self.helper.desktop_action("switch-appearance")["ok"])
                write.assert_called_with(target)
            read.reset_mock()
            self.assertTrue(self.helper.desktop_action("automatic-appearance")["ok"])
            read.assert_not_called()
            write.assert_called_with("hours")
            write.reset_mock()
            read.return_value = "bad mist"
            self.assertFalse(self.helper.desktop_action("switch-appearance")["ok"])
            write.assert_not_called()
            write.side_effect = OSError()
            self.assertFalse(self.helper.desktop_action("automatic-appearance")["ok"])

    @unittest.skipUnless(Window, "requires Qt settings")
    def test_keyboard_remembers_actual_brightness_and_adapts_to_new_hardware(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(folder + "/settings", QSettings.IniFormat)
            with patch("PySide6.QtCore.QSettings", return_value=settings), patch.object(self.helper, "keyboard_light") as state, patch.object(self.helper, "busctl") as call:
                key = "QuickActions/keyboardLevel"
                state.return_value = {"level": 4, "levels": 6}
                call.return_value = None
                self.assertFalse(self.helper.desktop_action("keyboard-light")["ok"])
                self.assertFalse(settings.contains(key))
                call.return_value = ""
                for current, maximum, target in ((4, 6, 0), (0, 6, 4), (0, 2, 2)):
                    state.return_value = {"level": current, "levels": maximum}
                    self.assertTrue(self.helper.desktop_action("keyboard-light")["ok"])
                    call.assert_called_with("call", *self.helper.KEYBOARD_LIGHT, "setKeyboardBrightness", "i", str(target))
                settings.setValue(key, "invalid")
                self.assertTrue(self.helper.desktop_action("keyboard-light")["ok"])
                self.assertEqual(call.call_args.args[-1], "2")
                state.return_value = None
                call.reset_mock()
                self.assertFalse(self.helper.desktop_action("keyboard-light")["ok"])
                call.assert_not_called()

    def test_lock_uses_screen_locker_and_reports_an_unavailable_service(self):
        with patch.object(self.helper, "busctl") as call:
            for reply, expected in (("", True), (None, False)):
                call.return_value = reply
                self.assertEqual(self.helper.desktop_action("lock-screen")["ok"], expected)
                call.assert_called_with("call", "org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "Lock")

    def test_display_power_uses_session_backend_and_reports_unsupported(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), patch.object(subprocess, "run") as invoke, patch.object(self.helper, "ok") as x11:
            for code, error, expected in ((0, b"", True), (0, b"DPMS not supported in this system", False), (1, b"", False)):
                invoke.return_value = subprocess.CompletedProcess([], code, stderr=error)
                self.assertEqual(self.helper.desktop_action("display-off")["ok"], expected)
                self.assertEqual(invoke.call_args.args[0], ["kscreen-doctor", "--dpms", "off"])
            invoke.side_effect = subprocess.TimeoutExpired([], 5)
            self.assertFalse(self.helper.desktop_action("display-off")["ok"])
            x11.assert_not_called()
            os.environ["XDG_SESSION_TYPE"] = "x11"
            x11.return_value = True
            self.assertTrue(self.helper.desktop_action("display-off")["ok"])
            x11.assert_called_once_with("xset", "dpms", "force", "off")
            os.environ["XDG_SESSION_TYPE"] = "tty"
            self.assertFalse(self.helper.desktop_action("display-off")["ok"])


@unittest.skipUnless(Window, "requires Qt widgets")
class ActionDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        settings = QSettings(folder + "/utilities", QSettings.IniFormat)
        with patch("window.QSettings", return_value=settings):
            self.window = Window(folder)
        self.jobs = Mock()
        self.window.worker = self.jobs
        self.addCleanup(self.window.deleteLater)

    def test_category_filters_keep_all_tools_reachable(self):
        from actions import ACTIONS
        from tool_catalog import CATEGORIES, category_for
        from PySide6.QtWidgets import QToolButton
        expected = set(ACTIONS) - set(self.window.hidden)
        grouped = set()
        for category, _, _ in CATEGORIES[2:]:
            self.window.findChild(QToolButton, "toolCategory-" + category).click()
            keys = {self.window.catalog.item(i).data(Qt.UserRole) for i in range(self.window.catalog.count())}
            self.assertTrue(keys)
            self.assertTrue(all(category_for(key, ACTIONS[key]) == category for key in keys))
            grouped.update(keys)
        self.assertEqual(grouped, expected)
        self.window.findChild(QToolButton, "toolCategory-favorites").click()
        self.assertEqual({self.window.catalog.item(i).data(Qt.UserRole) for i in range(self.window.catalog.count())},
                         set(self.window.favorites) & expected)

    def test_recent_captures_show_latest_local_files_once(self):
        from recent_captures import recent_files
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for n in range(16):
                file = path / f"Shot #{n}.png"
                file.touch()
                os.utime(file, (100 + n, 100 + n))
            (path / "not a capture.txt").touch()
            (path / "private.png").symlink_to(path / "Shot #3.png")
            (path / ".draft.png").touch()
            captures = recent_files({path: {".png"}, path / "missing": {".mp4"}})
            self.assertEqual([row["name"] for row in captures], [f"Shot #{n}.png" for n in range(15, 3, -1)])
            self.assertIn("%23", captures[0]["url"])
            self.assertFalse(captures[0]["video"])

    def test_empty_trash_is_singleton_and_cancel_is_safe(self):
        for key in (Qt.Key_Return, Qt.Key_Escape):
            self.window.Open(["empty-trash"])
            prompt = self.window.direct_actions.prompt
            self.window.Open(["empty-trash"])
            self.assertIs(prompt, self.window.direct_actions.prompt)
            self.assertFalse(self.window.isVisible())
            self.assertTrue(prompt.testOption(QMessageBox.Option.DontUseNativeDialog))
            self.assertEqual(prompt.defaultButton(), prompt.button(QMessageBox.Cancel))
            QTest.keyClick(prompt, key)
            self.app.processEvents()
            self.assertIsNone(self.window.direct_actions.prompt)
            self.jobs.assert_not_called()

    def test_approved_trash_can_finish_after_closing_and_independent_actions_run(self):
        self.window.Open(["empty-trash"])
        direct = self.window.direct_actions
        prompt = direct.prompt
        empty = next(b for b in prompt.buttons() if prompt.buttonRole(b) == QMessageBox.DestructiveRole)
        QTest.mouseClick(empty, Qt.LeftButton)
        self.assertEqual(self.jobs.call_count, 1)
        self.assertEqual(self.jobs.call_args.args[0][-1], "empty-trash")
        done = self.jobs.call_args.args[1]
        self.window.Open(["empty-trash"])
        self.assertIsNone(direct.prompt)
        self.window.Open(["lock-screen"])
        self.assertEqual(self.jobs.call_args.args[0][-2:], ["desktop-action", "lock-screen"])
        self.jobs.call_args.args[1]('{"ok":true}')
        self.window.show()
        self.window.close()
        self.assertFalse(self.window.isVisible())
        self.assertEqual(direct.busy, {"empty-trash"})
        done('{"ok":false}')
        self.assertFalse(direct.busy)
        self.assertTrue(direct.error.isVisible())
        self.assertIn("Trash", direct.error.text())
        direct.error.accept()
        self.assertIsNone(direct.error)

    def test_quick_panel_serializes_appearance_and_respects_hidden_tools(self):
        for key in ("switch-appearance", "automatic-appearance"):
            self.window.open_favorite(key)
        self.assertEqual(self.jobs.call_count, 1)
        self.jobs.call_args.args[1]('{"ok":true}')
        self.assertEqual(self.jobs.call_args.args[0][-1], "automatic-appearance")
        self.jobs.call_args.args[1]('{"ok":true}')
        self.assertFalse(self.window.direct_actions.busy)
        self.assertFalse(self.window.isVisible())
        self.window.settings.setValue("hidden", json.dumps(["lock-screen"]))
        self.window.Open(["lock-screen"])
        self.window.Open(["display-off", "extra"])
        self.assertEqual(self.jobs.call_count, 2)
