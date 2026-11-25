"""File shelf persistence, URL integrity, and opt-in session data."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULE))
from actions import clean_url
from agents import summary
from player import MAX_LYRICS, parse_lyrics, track_lyrics, upcoming

class Tools(unittest.TestCase):
    def test_clean_link_preserves_real_parameters_and_signed_links(self):
        url = "https://example.org/a?utm_source=x&item=a%2Fb&item=c+d&fbclid=1#part"
        self.assertEqual(clean_url(url), "https://example.org/a?item=a%2Fb&item=c+d#part")
        signed = url.replace("fbclid=1", "X-Amz-Signature=123")
        self.assertEqual(clean_url(signed), signed)
        with self.assertRaises(ValueError):
            clean_url("file:///tmp/document")

    def test_tracking_cleanup_keeps_the_original_url_spelling(self):
        url = "HTTPS://example.org/A%2Fb?item=one+two&%75tm_source=ref&item=%2B#"
        self.assertEqual(clean_url(url), "HTTPS://example.org/A%2Fb?item=one+two&item=%2B#")
        self.assertEqual(clean_url("https://e.org/?utm_source=x#?gclid=a"), "https://e.org/#?gclid=a")
        for field in ("X-Amz-Signature", "X-Goog-Signature", "access_token", "hmac", "expires", "%73ig"):
            url = f"https://e.org/?utm_campaign=a&{field}=abc"
            self.assertEqual(clean_url(url), url)
        for url in ("https://name@e.org/?fbclid=a", "https://e.org/?", "https://e.org/#"):
            self.assertEqual(clean_url(url), url)
        for value in ("https://e.org/\x00?a=b", "https://e.org/\\bad?gclid=a", "https://e.org text"):
            with self.assertRaises(ValueError):
                clean_url(value)

    def test_agent_summary_reads_reported_numbers_only(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "sample.jsonl"
            log.write_text(json.dumps({"type":"event_msg", "payload":{"type":"token_count", "info":{
                "total_token_usage":{"total_tokens":1025}}, "rate_limits":{"primary":{"used_percent":2.5}}}})
                    + '\n' + json.dumps({"message":{"content":"PRIVATE"}}) + '\n{"partial"')
            self.assertEqual(summary(log), {"Total":1025, "Primary limit used (%)":2.5})

class PlayerDetails(unittest.TestCase):
    def test_timed_lyrics_group_translations_repeats_and_breaks(self):
        song = "\ufeff[ar:Fixture]\r\n[offset:+125]\r\n[00:02.20][00:12.2]Words\n[00:02.200]Translation\n[00:03.9]"
        self.assertEqual(parse_lyrics(song), {"text": "", "timed": [
            {"at": 2075, "text": "Words\nTranslation"}, {"at": 3775, "text": ""},
            {"at": 12075, "text": "Words"}]})
        self.assertEqual(parse_lyrics("[offset:-200]\n[00:00.1]Intro")["timed"][0]["at"], 300)

    def test_sidecar_precedence_encodings_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            song = Path(directory) / "A song #1.ogg"
            meta = {"xesam:url": song.as_uri(), "xesam:asText": "Player words"}
            sidecar = song.with_suffix(".lrc")
            for raw in (b"", b"[ar:artist]", b"\xff", b"x" * (MAX_LYRICS + 1)):
                sidecar.write_bytes(raw)
                self.assertEqual(track_lyrics(meta)["text"], "Player words")
            sidecar.write_text("[00:01]Local words", encoding="utf-16")
            self.assertEqual(track_lyrics(meta)["timed"], [{"at": 1000, "text": "Local words"}])
            supplied = dict(meta, **{"xesam:asText": "[00:02]Player timing"})
            self.assertEqual(track_lyrics(supplied)["timed"], [{"at": 2000, "text": "Player timing"}])
            for url in (song.as_uri().replace("file://", "file://server"), "https://example.org/song.ogg"):
                self.assertEqual(track_lyrics(dict(meta, **{"xesam:url": url}))["text"], "Player words")
            sidecar.unlink()
            if hasattr(os, "mkfifo"):
                os.mkfifo(sidecar)
                self.assertEqual(track_lyrics(meta)["text"], "Player words")

    @unittest.skipUnless(importlib.util.find_spec("dbus"), "needs desktop D-Bus bindings")
    def test_queue_uses_playlist_order_and_only_upcoming_tracks(self):
        obj, props = Mock(), Mock()
        ids = ["/tracks/t" + str(n) for n in range(40)]
        props.Get.return_value = ids
        obj.GetTracksMetadata.return_value = [{"mpris:trackid": key, "xesam:title": key}
                                              for key in reversed(ids[5:25])]
        rows = upcoming(obj, props, {"mpris:trackid": ids[4]})
        self.assertEqual([row["title"] for row in rows], ids[5:25])
        self.assertEqual(list(obj.GetTracksMetadata.call_args.args[0]), ids[5:25])
        for current in ("/unknown", ids[-1]):
            self.assertEqual(upcoming(obj, props, {"mpris:trackid": current}), [])
        self.assertEqual(obj.GetTracksMetadata.call_count, 1)


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

    def test_migrated_scratchpad_and_named_snippets_survive_reopening(self):
        from PySide6.QtCore import QSettings
        from scratchpads import Pads
        from pad_editor import PadEditor
        from pages import Snippets
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_DATA_HOME=directory):
            conf = QSettings(str(Path(directory,"notes.ini")), QSettings.IniFormat)
            conf.setValue("scratchpad", "A note")
            pads = Pads(conf)
            note = PadEditor(pads)
            self.assertEqual(note.edit.toPlainText(), "A note")
            self.assertFalse(conf.contains("scratchpad"))
            note.edit.setPlainText("A note with edits")
            self.assertTrue(note.close())
            snips = Snippets(conf)
            snips.names.addItem("Greeting")
            snips.names.setCurrentRow(0)
            snips.edit.setPlainText("A snippet")
            reopened = PadEditor(Pads(conf))
            self.assertEqual(reopened.edit.toPlainText(), "A note with edits")
            restored_snips = Snippets(conf)
            self.assertEqual(restored_snips.edit.toPlainText(), "A snippet")

    def test_snippet_shortcuts_are_optional_unique_and_removed_with_the_snippet(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        from pages import Snippets
        from snippet_rules import expansion_table
        with tempfile.TemporaryDirectory() as root:
            settings = QSettings(str(Path(root, "snippets.ini")), QSettings.IniFormat)
            settings.setValue("snippets", json.dumps({"Greeting": "Hej 🌷", "Signature": "Ada"}))
            page = Snippets(settings)
            self.assertEqual(expansion_table(settings), ({}, set()))
            with patch.object(QInputDialog, "getText", return_value=("hello", True)):
                page.edit_shortcut()
            self.assertEqual(expansion_table(settings)[0], {";hello;": "Hej 🌷"})
            page.names.setCurrentRow(1)
            with patch.object(QInputDialog, "getText", side_effect=[("hello", True), ("my sig", True), ("sig", True)]), \
                    patch.object(QMessageBox, "information") as validation:
                page.edit_shortcut()
            self.assertEqual(validation.call_count, 2)
            page = Snippets(settings)
            self.assertEqual(expansion_table(settings)[0][";sig;"], "Ada")
            page.remove()
            self.assertEqual(expansion_table(settings)[0], {";sig;": "Ada"})
            with patch.object(QInputDialog, "getText", return_value=("", True)):
                page.edit_shortcut()
            self.assertEqual(expansion_table(settings), ({}, set()))
            self.assertEqual(page.edit.toPlainText(), "Ada")

    def test_named_pad_selection_preview_export_and_confirmed_deletion(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from pad_editor import PadEditor
        from scratchpads import Pads
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_DATA_HOME=directory):
            settings = QSettings(str(Path(directory, "notes.ini")), QSettings.IniFormat)
            pads = Pads(settings)
            editor = PadEditor(pads)
            first = editor.ident
            editor.new()
            second = editor.ident
            with patch.object(QInputDialog, "getText", return_value=("Plans", True)):
                editor.rename()
            self.assertEqual(editor.choice.currentText(), "Plans")
            text = "# Plan\n\n- café"
            editor.edit.setPlainText(text)
            editor.preview_action.setChecked(True)
            self.assertIn("café", editor.rendered.toPlainText())
            self.assertNotIn("# Plan", editor.rendered.toPlainText())
            dest = Path(directory, "Plans.md")
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(dest), "")):
                editor.export()
            self.assertEqual(dest.read_text(), text)
            self.assertTrue(editor.flush())
            editor.choose(editor.choice.findData(first))
            self.assertEqual(PadEditor(Pads(settings)).ident, first)
            editor.choose(editor.choice.findData(second))
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
                editor.remove()
            self.assertEqual(editor.ident, second)
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                editor.remove()
            self.assertEqual(editor.ident, first)
            self.assertEqual(len(pads.request("view")["pads"]), 1)

    def test_concurrent_pad_edits_deletion_and_restart_preserve_both_drafts(self):
        from PySide6.QtCore import QSettings
        from scratchpads import Pads
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_DATA_HOME=directory):
            conf = QSettings(str(Path(directory, "test.ini")), QSettings.IniFormat)
            pads = Pads(conf)
            first = pads.request("view")["pad"]
            saved = pads.request("save", first["id"], first["revision"], "first")["pad"]
            fork = pads.request("save", first["id"], first["revision"], "second")
            self.assertTrue(fork["recovered"])
            self.assertEqual(fork["pad"]["body"], "second")
            self.assertEqual(pads.request("view", first["id"])["pad"]["body"], "first")
            self.assertFalse(pads.request("delete", first["id"], first["revision"])["ok"])
            self.assertTrue(pads.request("delete", first["id"], saved["revision"])["ok"])
            restored = pads.request("save", first["id"], saved["revision"], "late edit")
            self.assertTrue(restored["recovered"])
            after = Pads(conf)
            self.assertEqual(after.request("view", restored["pad"]["id"])["pad"]["body"], "late edit")
            self.assertEqual(len(after.request("view")["pads"]), 2)

    def test_corrupt_store_never_consumes_or_replaces_legacy_note(self):
        from PySide6.QtCore import QSettings
        from scratchpads import Pads
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_DATA_HOME=directory):
            conf = QSettings(str(Path(directory, "test.ini")), QSettings.IniFormat)
            conf.setValue("scratchpad", "Keep")
            path = Path(directory, "monet/scratchpads/pads.sqlite3")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"unreadable")
            self.assertFalse(Pads(conf).request("view")["ok"])
            self.assertEqual(conf.value("scratchpad"), "Keep")
            self.assertEqual(path.read_bytes(), b"unreadable")
