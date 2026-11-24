"""File shelf persistence, URL integrity, and opt-in session data."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

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
