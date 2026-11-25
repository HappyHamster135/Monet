"""Exercise the picker through window, favorite and search entry points."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
try:
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from screen_colors import color_text
    from window import Receiver, Window
except ImportError:
    Window = None


@unittest.skipUnless(Window, "requires Qt widgets and D-Bus")
class ScreenColorActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.window = Window("/usr/libexec", defer_catalog=True)
        self.window.settings = QSettings(str(Path(self.folder.name) / "colors.ini"), QSettings.IniFormat)
        self.jobs = []
        self.input_data = []
        def worker(argv, done, failed, *, input_data=None):
            self.jobs.append((argv, done, failed))
            if input_data is not None:
                self.input_data.append(input_data)
        self.window.worker = worker
        wayland = patch.object(QApplication, "platformName", return_value="wayland")
        wayland.start()
        self.addCleanup(wayland.stop)
        wl_copy = patch("clipboard_text.shutil.which", return_value="/usr/bin/wl-copy")
        wl_copy.start()
        self.addCleanup(wl_copy.stop)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.folder.cleanup()

    def until(self, predicate):
        for _ in range(100):
            if predicate():
                return
            QTest.qWait(10)
        self.fail("Timed out waiting for the picker")

    def get_job(self):
        self.until(lambda: bool(self.jobs))
        return self.jobs.pop(0)

    def test_global_pick_keeps_catalog_hidden_and_coalesces_repeat_launches(self):
        self.window.Open(["color"])
        receiver = Receiver(self.window)
        receiver.OpenTool("color", "")
        self.window.open_favorite("color")
        command, done, fail = self.get_job()
        self.assertEqual(command[-1], "org.kde.kwin.ColorPicker.pick")
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.catalog_pending)
        self.assertTrue(self.window.pages["color"].busy)
        with patch.object(QApplication, "quit") as quit_app:
            receiver.release_if_unused()
            quit_app.assert_not_called()
        fail("GDBus.Error:org.kde.kwin.ColorPicker.Error.Cancelled: cancelled")
        QTest.qWait(60)
        self.assertFalse(self.window.pages["color"].busy)
        self.assertFalse(self.jobs)
        self.assertFalse(self.window.isVisible())

    def test_catalog_restores_result_and_formats_next_copy(self):
        self.window.Open(["tools"])
        self.window.run_tool("color")
        self.assertFalse(self.window.isVisible())
        command, done, fail = self.get_job()
        done("((uint32 4278256131,),)")  # #010203
        command, copied, failed = self.get_job()
        self.assertEqual(command[0], "wl-copy")
        self.assertEqual(self.input_data.pop(), b"#010203")
        copied("")
        page = self.window.pages["color"]
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(page.value.text(), "#010203")
        page.format.setCurrentIndex(page.format.findData("rgb"))
        self.assertFalse(self.jobs)
        page.copy_button.click()
        command, copied, failed = self.get_job()
        self.assertEqual(self.input_data.pop(), b"rgb(1, 2, 3)")
        copied("")
        self.assertEqual(self.window.settings.value("colorFormat"), "rgb")
        self.window.run_tool("color")
        self.get_job()[1]("((uint32 4294967296,),)")
        self.assertFalse(self.jobs)
        self.assertEqual(page.value.text(), "rgb(1, 2, 3)")
        self.assertTrue(self.window.isVisible())

    def test_formats_and_invalid_preference(self):
        examples = [("hex", 0x010203, "#010203"), ("unrecognized", 0, "#000000"),
                    ("bare", 0xFF00, "00FF00"), ("rgb", 0xFF00FF, "rgb(255, 0, 255)"),
                    ("hsl", 0x333333, "hsl(0, 0%, 20%)"), ("hsl", 0xFF0000, "hsl(0, 100%, 50%)"),
                    ("swiftui", 0x336699, "Color(red: 0.2, green: 0.4, blue: 0.6)")]
        for form, rgb, expected in examples:
            self.assertEqual(color_text(rgb, form), expected)
        self.window.settings.setValue("colorFormat", "unknown")
        self.window.Open(["color"])
        self.assertEqual(self.window.pages["color"].format.currentData(), "hex")
        self.window.close()
        QTest.qWait(100)
        self.assertFalse(self.jobs)

    def test_hidden_tool_is_not_started(self):
        self.window.settings.setValue("hidden", '["color"]')
        self.window.Open(["color"])
        self.window.open_favorite("color")
        self.assertNotIn("color", self.window.pages)
        self.assertFalse(self.jobs)
