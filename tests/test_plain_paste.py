"""Exercise clipboard negotiation and focus changes without using the session clipboard."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
try:
    import plain_paste as paste
except (ImportError, ValueError):
    paste = None


@unittest.skipIf(paste is None, "AT-SPI bindings unavailable")
class PlainPaste(unittest.TestCase):
    def test_file_transfers_and_image_only_copies_are_left_alone(self):
        for formats in (["image/png"], ["text/plain", "x-special/gnome-copied-files"],
                        ["text/plain", "application/x-kde-cutselection"]):
            with self.subTest(formats=formats), self.assertRaises(paste.PasteUnavailable):
                paste.text_format(formats)
        with patch.object(paste, "read_clipboard", return_value=b"# file list\r\nfile:///tmp/one\r\n") as read:
            with self.assertRaises(paste.PasteUnavailable):
                paste.clipboard_text("text/plain", ["text/plain", "text/uri-list"])
            read.assert_called_once_with("--no-newline", "--type", "text/uri-list")

    def test_link_with_text_and_html_prefers_the_text_representation(self):
        formats = ["text/html", "text/uri-list", "text/plain;charset=UTF-8"]
        mime = paste.text_format(formats)
        self.assertEqual(mime, formats[2])
        with patch.object(paste, "read_clipboard", side_effect=[b"https://example.org/", "A 🦊\r\nB".encode()]):
            self.assertEqual(paste.clipboard_text(mime, formats), "A 🦊\nB")

    @unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt bindings unavailable")
    def test_html_only_selection_becomes_plain_text(self):
        with patch.object(paste, "read_clipboard", return_value=b"<b>A &amp; B</b>"):
            self.assertEqual(paste.clipboard_text("text/html", ["text/html"]), "A & B")

    def editor(self, stack):
        window, node = Mock(), Mock()
        node.get_role.return_value = paste.Atspi.Role.TEXT
        node.get_application.return_value.get_toolkit_name.return_value = "Qt"
        stack.enter_context(patch.object(paste, "focused_editor", return_value=(window, node)))
        stack.enter_context(patch.object(paste, "states")).return_value.contains.return_value = True
        stack.enter_context(patch.object(paste, "editable", return_value=True))
        stack.enter_context(patch.object(paste, "selection", return_value=(5, 1, 3)))
        stack.enter_context(patch.object(paste.select, "select", return_value=([], [], [])))
        return node

    def test_plain_clipboard_uses_native_paste_and_does_not_read_the_contents(self):
        with ExitStack() as stack:
            self.editor(stack)
            stack.enter_context(patch.object(paste, "clipboard_formats", return_value=["text/plain"]))
            read = stack.enter_context(patch.object(paste, "clipboard_text"))
            self.assertEqual(paste.paste(20, "edit"), 23)
            read.assert_not_called()

    def test_focus_leaving_during_clipboard_read_cancels_the_paste(self):
        with ExitStack() as stack:
            self.editor(stack)
            stack.enter_context(patch.object(paste, "clipboard_formats", return_value=["text/plain", "text/html"]))
            def read(*unused):
                paste.select.select.return_value = ([True], [], [])
                return "Private text"
            stack.enter_context(patch.object(paste, "clipboard_text", side_effect=read))
            insert = stack.enter_context(patch.object(paste.Atspi.EditableText, "insert_text"))
            for mode in ("commit", "edit"):
                with self.subTest(mode=mode), self.assertRaises(paste.PasteUnavailable):
                    paste.paste(20, mode)
            insert.assert_not_called()

    def test_partial_legacy_insertion_does_not_delete_original_selection(self):
        with ExitStack() as stack:
            node = self.editor(stack)
            node.get_character_count.return_value = 6
            stack.enter_context(patch.object(paste, "clipboard_formats", return_value=["text/plain", "text/html"]))
            stack.enter_context(patch.object(paste, "clipboard_text", return_value="x🦊"))
            stack.enter_context(patch.object(paste.Atspi.Text, "get_text", return_value="AB"))
            insert = stack.enter_context(patch.object(paste.Atspi.EditableText, "insert_text", return_value=True))
            delete = stack.enter_context(patch.object(paste.Atspi.EditableText, "delete_text"))
            with self.assertRaises(paste.PasteUnavailable):
                paste.paste(20, "edit")
            insert.assert_called_once_with(node, 3, "x🦊", 3)
            delete.assert_not_called()
