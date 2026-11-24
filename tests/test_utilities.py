"""File shelf persistence, URL integrity, and opt-in session data."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULE))
from actions import clean_url
from agents import summary

class Tools(unittest.TestCase):
    def test_clean_link_preserves_real_parameters_and_signed_links(self):
        url = "https://example.org/a?utm_source=x&item=a%2Fb&item=c+d&fbclid=1#part"
        self.assertEqual(clean_url(url), "https://example.org/a?item=a%2Fb&item=c+d#part")
        signed = url.replace("fbclid=1", "X-Amz-Signature=123")
        self.assertEqual(clean_url(signed), signed)
        with self.assertRaises(ValueError):
            clean_url("file:///tmp/document")

    def test_agent_summary_reads_reported_numbers_only(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "sample.jsonl"
            log.write_text(json.dumps({"type":"event_msg", "payload":{"type":"token_count", "info":{
                "total_token_usage":{"total_tokens":1025}}, "rate_limits":{"primary":{"used_percent":2.5}}}})
                    + '\n' + json.dumps({"message":{"content":"PRIVATE"}}) + '\n{"partial"')
            self.assertEqual(summary(log), {"Total":1025, "Primary limit used (%)":2.5})

@unittest.skipUnless(importlib.util.find_spec("PySide6"), "needs Qt")
class DesktopTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_shelf_removal_keeps_the_actual_file(self):
        from PySide6.QtCore import QSettings
        from pages import ShelfList
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "photo #1.png")
            path.write_bytes(b"fixture")
            config = QSettings(str(Path(directory, "config")), QSettings.IniFormat)
            shelf = ShelfList(config)
            shelf.add_paths([str(path), str(path), "relative"])
            self.assertEqual(shelf.paths(), [str(path)])
            restored = ShelfList(config)
            self.assertEqual(restored.paths(), [str(path)])
            restored.setCurrentRow(0)
            restored.forget()
            self.assertEqual(ShelfList(config).paths(), [])
            self.assertEqual(path.read_bytes(), b"fixture")

    def test_scratchpad_and_named_snippets_survive_reopening(self):
        from PySide6.QtCore import QSettings
        from pages import Writing
        with tempfile.TemporaryDirectory() as directory:
            conf = QSettings(str(Path(directory,"notes.ini")), QSettings.IniFormat)
            note = Writing(conf)
            note.edit.setPlainText("A note")
            snips = Writing(conf, True)
            snips.names.addItem("Greeting")
            snips.names.setCurrentRow(0)
            snips.edit.setPlainText("A snippet")
            restored_note = Writing(conf)
            restored_snippets = Writing(conf, True)
            self.assertEqual(restored_note.edit.toPlainText(), "A note")
            self.assertEqual(restored_snippets.edit.toPlainText(), "A snippet")
