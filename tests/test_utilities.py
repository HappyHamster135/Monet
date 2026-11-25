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

    def test_search_arrows_keep_typing_focus_and_enter_uses_selection_once(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from unittest.mock import patch
        from window import Window
        window = Window("/usr/libexec")
        self.addCleanup(window.close)
        window.show()
        window.activateWindow()
        QTest.qWait(50)
        window.search.setText("sound")
        self.assertGreater(window.catalog.count(), 1)
        QTest.keyClick(window.search, Qt.Key_Up)
        self.assertEqual(window.catalog.currentRow(), 0)
        QTest.keyClick(window.search, Qt.Key_Down)
        self.assertEqual(window.catalog.currentRow(), 1)
        self.assertTrue(window.search.hasFocus())
        selected = window.catalog.currentItem().data(Qt.UserRole)
        with patch.object(window, "run_tool") as launch:
            QTest.keyClick(window.search, Qt.Key_Return)
            launch.assert_called_once_with(selected)
        QTest.keyClicks(window.search, " settings")
        self.assertEqual(window.search.text(), "sound settings")
        self.assertEqual(window.catalog.currentRow(), 0)

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

    def test_notch_and_window_share_one_shelf_without_stealing_focus(self):
        from PySide6.QtCore import QSettings
        from window import Receiver, Window
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            photo = base / "Målning %20 #1.png"
            photo.write_bytes(b"picture")
            folder = base / "Studies"
            folder.mkdir()
            window = Window("/usr/libexec", defer_catalog=True)
            window.settings = QSettings(str(base / "shelf.ini"), QSettings.IniFormat)
            receiver = Receiver(window)
            def request(action, *urls):
                return json.loads(receiver.shelf_request(json.dumps({"action": action, "urls": urls})))
            observed = []
            window.shelfChanged.connect(lambda: observed.append(True))
            data = request("add", photo.as_uri(), folder.as_uri(), photo.as_uri(), (base / "gone").as_uri())
            self.assertTrue(data["missing"])
            self.assertEqual([r["url"] for r in data["rows"]], [photo.as_uri(), folder.as_uri()])
            self.assertEqual(data["rows"][1]["icon"], "folder")
            self.assertFalse(window.isVisible())
            self.assertEqual(window.stack.currentIndex(), 0)
            self.assertTrue(receiver.AddToShelf(photo.as_uri()))
            self.assertEqual(len(observed), 1)
            for invalid in ("file://server/share/item", "file:relative", "file:///tmp/bad%00", "https://example.org"):
                self.assertEqual(request("remove", photo.as_uri(), invalid), {})
            self.assertEqual(request("add", *([photo.as_uri()] * 101)), {})
            self.assertEqual(len(request("view")["rows"]), 2)
            shelf = window.pages["shelf"].files
            shelf.setCurrentRow(1)
            shelf.forget()
            self.assertEqual([r["name"] for r in request("view")["rows"]], [photo.name])
            self.assertEqual(request("remove", photo.as_uri())["rows"], [])
            self.assertEqual(len(observed), 3)
            self.assertEqual(photo.read_bytes(), b"picture")
            self.assertTrue(folder.is_dir())
            self.assertEqual(json.loads(window.settings.value("shelf")), [])
            receiver.idle.stop()
            window.close()

    def test_shelf_text_and_web_links_survive_a_restart_and_export_native_formats(self):
        from PySide6.QtCore import QMimeData, QSettings, QUrl
        from pages import ShelfList
        from shelf_content import from_mime, to_mime
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory, "Målning #1.png")
            file.touch()
            config = QSettings(str(Path(directory, "settings")), QSettings.IniFormat)
            config.setValue("shelf", json.dumps([str(file)]))
            shelf = ShelfList(config)
            text = "  A line\n\nAnother <b>line</b> å\t"
            link = "https://example.org/a%2Fb?q=a%26b#top"
            def request(action, **values):
                return json.loads(shelf.for_notch(json.dumps(dict(action=action, version=2, **values))))
            request("add", text=text)
            request("add", urls=[link])
            request("add", text=link)
            shelf = ShelfList(config)
            entries = shelf.entries()
            self.assertEqual([(e.kind, e.value) for e in entries], [("file", str(file)), ("text", text), ("link", link)])
            self.assertEqual(to_mime(entries[1:2]).text(), text)
            uris = to_mime([entries[0], entries[2]])
            self.assertEqual([u.toString(QUrl.FullyEncoded) for u in uris.urls()], [file.as_uri(), link])
            mixed = to_mime(entries)
            self.assertFalse(mixed.hasUrls())
            self.assertEqual(mixed.text(), "\n".join([str(file), text, link]))
            self.assertEqual(from_mime(uris), [entries[0], entries[2]])
            mime = QMimeData()
            mime.setText(text)
            self.assertEqual(from_mime(mime), [entries[1]])
            for unsupported in ("javascript:alert(1)", "file://server/private"):
                mime.setUrls([QUrl(unsupported)])
                self.assertEqual(from_mime(mime), [])
                self.assertEqual(request("add", urls=[link, unsupported]), {})
            legacy = json.loads(shelf.for_notch('{"action":"view"}'))
            self.assertEqual([row["url"] for row in legacy["rows"]], [file.as_uri()])
            rows = request("view")["rows"]
            self.assertEqual(len({row["key"] for row in rows}), 3)
            request("remove", keys=[rows[1]["key"]])
            self.assertEqual([e.kind for e in ShelfList(config).entries()], ["file", "link"])
            self.assertTrue(file.is_file())

    def test_shelf_keyboard_paste_and_copy_preserve_selected_text_and_link_spelling(self):
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtTest import QTest
        from pages import ShelfList
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory, "shelf.ini")), QSettings.IniFormat)
            shelf = ShelfList(settings)
            shelf.show()
            shelf.setFocus()
            QTest.qWait(20)
            clipboard = QGuiApplication.clipboard()
            self.addCleanup(clipboard.clear)
            values = ["a\n\nline\t", "HTTPS://Example.org/%7e?q=a%2fb#part"]
            for value in values:
                clipboard.setText(value)
                QTest.keyClick(shelf, Qt.Key_V, Qt.ControlModifier)
            self.assertEqual([e.value for e in ShelfList(settings).entries()], values)
            self.assertEqual(shelf.entries()[1].kind, "link")
            shelf.selectAll()
            QTest.keyClick(shelf, Qt.Key_C, Qt.ControlModifier)
            self.assertEqual(clipboard.text(), "\n".join(values))
            shelf.close()

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
            self.assertEqual(expansion_table(settings)[0], {";hello;": ("Hej 🌷", False)})
            page.names.setCurrentRow(1)
            with patch.object(QInputDialog, "getText", side_effect=[("hello", True), ("my sig", True), ("sig", True)]), \
                    patch.object(QMessageBox, "information") as validation:
                page.edit_shortcut()
            self.assertEqual(validation.call_count, 2)
            page = Snippets(settings)
            self.assertEqual(expansion_table(settings)[0][";sig;"], ("Ada", False))
            page.remove()
            self.assertEqual(expansion_table(settings)[0], {";sig;": ("Ada", False)})
            with patch.object(QInputDialog, "getText", return_value=("", True)):
                page.edit_shortcut()
            self.assertEqual(expansion_table(settings), ({}, set()))
            self.assertEqual(page.edit.toPlainText(), "Ada")

    def test_snippet_variables_preserve_old_templates_and_expand_at_use(self):
        from PySide6.QtCore import QDateTime, QLocale, QSettings, Qt
        from PySide6.QtWidgets import QApplication
        from pages import Snippets
        from snippet_variables import expand
        clock = QDateTime.fromString("2026-08-01T23:30:00Z", Qt.ISODate)
        clipboard = Mock(return_value="{{date}} / Ω")
        pattern = "{{date-tz(Europe/Stockholm):yyyy-MM-dd HH:mm}} {{unknown}} {{clipboard}} {{clipboard}}"
        self.assertEqual(expand(pattern, clipboard, now=clock, locale=QLocale.c()),
                         "2026-08-02 01:30 {{unknown}} {{date}} / Ω {{date}} / Ω")
        clipboard.assert_called_once_with()
        self.assertEqual(expand("{{time-tz(No/SuchZone):HH:mm}}", clipboard, now=clock),
                         "{{time-tz(No/SuchZone):HH:mm}}")
        clipboard.assert_called_once_with()
        with tempfile.TemporaryDirectory() as root:
            settings = QSettings(str(Path(root, "snippets.ini")), QSettings.IniFormat)
            settings.setValue("snippets", json.dumps({"Template": "{{clipboard}}"}))
            page = Snippets(settings)
            page.copy()
            self.assertEqual(QApplication.clipboard().text(), "{{clipboard}}")
            page.edit.selectAll()
            action = next(item for item in page.variables_menu.actions() if item.text() == "Clipboard text")
            action.trigger()
            self.assertTrue(page.expand_action.isChecked())
            page = Snippets(settings)
            self.assertTrue(page.expand_action.isChecked())
            page.edit.insertPlainText("New ")
            QApplication.clipboard().setText("first line\n{{time}}")
            page.copy()
            self.assertEqual(QApplication.clipboard().text(), "New first line\n{{time}}")
            page.expand_action.trigger()
            page.copy()
            self.assertEqual(QApplication.clipboard().text(), "New {{clipboard}}")
            page.enable_variables(True)
            page.remove()
            self.assertEqual(json.loads(settings.value("snippetVariables")), {})

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
