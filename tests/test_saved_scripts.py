"""Saved script editing and bounded execution on disposable files."""
from importlib.util import find_spec
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))


@unittest.skipUnless(find_spec("PySide6") and find_spec("dbus") and find_spec("gi"), "requires the Linux desktop runtime")
class SavedScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder/"My local script"
        self.settings = QSettings(str(self.folder/"settings.ini"), QSettings.IniFormat)

    def file(self, body):
        self.path.write_text(f"#!{sys.executable}\n" + body)
        self.path.chmod(0o700)

    def test_editor_validation_persistence_and_removal(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from script_page import ScriptEditor, ScriptPage
        from saved_scripts import library
        self.file("print('ok')")
        page = ScriptPage(self.settings)
        page.refresh()
        self.assertFalse(page.try_button.isEnabled())
        edit = ScriptEditor(self.settings, None, page)
        edit.name.setText("Echo")
        edit.path.setText(str(self.folder))
        button = edit.findChild(QDialogButtonBox).button(QDialogButtonBox.Save)
        button.click()
        self.assertFalse(edit.problem.isHidden())
        self.assertFalse(library(self.settings))
        edit.path.setText(str(self.path))
        edit.preview.setChecked(True)
        edit.needs_text.setChecked(True)
        button.click()
        self.assertEqual(edit.result(), QDialog.Accepted)
        page.refresh()
        self.assertTrue(page.try_button.isEnabled())
        self.assertTrue(page.current().preview and page.current().needs_text)
        self.assertEqual(page.detail.text(), str(self.path))
        second = ScriptEditor(self.settings, page.current(), page)
        second.name.setText("Echo words")
        second.commit()
        page.refresh(second.script.ident)
        with patch("script_page.QProcess.startDetached", return_value=(True, 1)) as launch:
            page.try_button.click()
        launch.assert_called_once_with("krunner", ["--runner", "monet-utilities", "script: Echo words "])
        self.assertEqual(len(library(self.settings)), 1)
        page.remove_button.click()
        self.assertFalse(library(self.settings))
        self.assertTrue(self.path.is_file())
        page.deleteLater()

    def test_longest_matching_name_and_argument_boundaries(self):
        from saved_scripts import choices, save
        self.file("")
        short = save(self.settings, "Price", str(self.path), False, False)
        long = save(self.settings, "Price quote", str(self.path), True, False)
        self.assertEqual(choices([short, long], 'pRiCe quote C++  "a b"'), [(long, 'C++  "a b"', True)])
        self.assertEqual(choices([short, long], "quote"), [(long, "", False)])
        with self.assertRaises(ValueError):
            save(self.settings, "PRICE", str(self.path), True, False)

    def test_limited_output_errors_and_descendant_timeout(self):
        from saved_scripts import Script
        from script_search import execute
        job = Script("test", "Test", str(self.path), False, False)
        def run(body, preview=False):
            self.file(body)
            return execute(job, "", threading.Event(), preview)
        self.assertEqual(run("print('Hello\\nworld')").text, "Hello\nworld")
        self.assertTrue(run("import os;os.write(1, b'a\\0b')").error)
        self.assertTrue(run("print('o' * 80000)").error)
        with patch("script_search.PREVIEW_TIMEOUT", .25):
            answer = run("import subprocess,sys\nsubprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'])", preview=True)
        self.assertIn("timed out", answer.error)
        self.assertFalse(answer.text)
        with patch("script_search.PREVIEW_TIMEOUT", .01):
            self.assertEqual(run("import time;time.sleep(.1);print('done')").text, "done")
        answer = run("from pathlib import Path;print('o' * 80000);Path('finished').touch()")
        self.assertTrue(answer.error and (self.folder/"finished").exists())
        self.path.unlink()
        self.assertTrue(execute(job, "", threading.Event()).error)
