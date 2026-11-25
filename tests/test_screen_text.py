"""Exercise capture ownership, empty results and clipboard delivery without touching the desktop."""
import json
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
    from actions import tr
    from window import Receiver, Window
except ImportError:
    Window = None


@unittest.skipUnless(Window, "requires Qt widgets and D-Bus")
class ScreenTextActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.window = Window("/usr/libexec", defer_catalog=True)
        self.window.settings = QSettings(str(Path(self.folder.name) / "tools.ini"), QSettings.IniFormat)
        self.jobs = []
        self.window.worker = lambda command, done, fail, **kw: self.jobs.append((command, done, fail, kw))
        wayland = patch.object(QApplication, "platformName", return_value="wayland")
        wayland.start()
        self.addCleanup(wayland.stop)
        clipboard = patch("clipboard_text.shutil.which", return_value="/usr/bin/wl-copy")
        clipboard.start()
        self.addCleanup(clipboard.stop)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def next_job(self):
        for _ in range(100):
            if self.jobs:
                return self.jobs.pop(0)
            QTest.qWait(10)
        self.fail("Screen selection did not start a worker")

    def read_selection(self, text):
        command, selected, _, _kw = self.next_job()
        path = command[-1]
        self.assertIn("--region", command)
        self.assertIn("--new-instance", command)
        path.touch()
        selected("")
        cmd, read, _, _kw = self.next_job()
        self.assertEqual(cmd[-2:], ["read", path])
        read(json.dumps(text))
        self.assertFalse(path.parent.exists())

    def test_repeated_shortcuts_select_once_and_copy_whitespace_without_arguments(self):
        receiver = Receiver(self.window)
        receiver.OpenTool("ocr", "")
        self.window.open_favorite("ocr")
        self.window.Open(["color"])
        with patch.object(QApplication, "quit") as quit_app:
            receiver.release_if_unused()
            quit_app.assert_not_called()
        value = "  αβ\n" + "0123" * 40000 + "  "
        self.read_selection(value)
        cmd, copied, _, kw = self.next_job()
        self.assertEqual(cmd, ["wl-copy", "--type", "text/plain;charset=utf-8"])
        self.assertEqual(kw["input_data"], value.encode())
        copied("")
        self.assertFalse(self.jobs)
        self.assertFalse(self.window.isVisible())

    def test_empty_selection_and_failure_preserve_edits_and_allow_retry(self):
        self.window.Open(["tools"])
        self.window.run_tool("ocr")
        page = self.window.pages["ocr"]
        page.editor.setPlainText("Uncopied changes")
        self.read_selection("")
        self.assertTrue(self.window.isVisible())
        self.assertEqual(page.editor.toPlainText(), "Uncopied changes")
        self.assertEqual(self.window.status.currentMessage(), tr("No text or QR code was found."))
        page.pick(True)
        cmd, _, fail, _kw = self.next_job()
        fail("unavailable")
        self.assertFalse(cmd[-1].parent.exists())
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.status.currentMessage(), tr("Couldn’t read the selected area."))
        page.pick(True)
        cmd, selected, _, _kw = self.next_job()
        selected("")  # Esc in Spectacle leaves no file.
        self.assertFalse(cmd[-1].parent.exists())
        self.assertFalse(page.busy)
        self.assertFalse(self.jobs)

    def test_close_or_hide_discards_pending_text(self):
        self.window.Open(["ocr"])
        cmd, selected, _, _kw = self.next_job()
        cmd[-1].touch()
        selected("")
        _, read, _, _kw = self.next_job()
        self.window.close()
        read(json.dumps("late text"))
        self.assertFalse(cmd[-1].parent.exists())
        self.assertFalse(self.jobs)
        self.assertFalse(self.window.isVisible())
        self.window.settings.setValue("hidden", '["ocr"]')
        self.window.Open(["ocr"])
        self.window.open_favorite("ocr")
        self.assertFalse(self.jobs)
