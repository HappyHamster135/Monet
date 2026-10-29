"""A late-file retry must never fall through a rejected window identity."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_editor_session import APP
from tests.test_editor_session import state
from tests.test_resume import r


@unittest.skipIf(os.name == "nt", "Linux editor paths")
class TargetedEditorRetry(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.file = Path(temporary.name) / "Late [copy].txt"
        self.file.write_text("saved contents", encoding="utf-8")
        self.ident = "{12345678-1234-1234-1234-123456789abc}"

    def test_exact_window_and_literal_paths_are_sent_without_text(self):
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)]))
        args = call.call_args.args
        self.assertEqual(args[:4], ("org.kde.kate-12", "/MainApplication", "org.kde.Kate.Application", "monetReopenDocuments"))
        self.assertEqual(json.loads(args[4]), {"id": self.ident, "documents": [str(self.file)]})
        self.assertNotIn("saved contents", args[4])

    def test_invalid_or_missing_targets_never_call_the_editor(self):
        good = (APP, 12, self.ident, [str(self.file)])
        for index, value in ((0, "unknown.desktop"), (1, True), (1, 0), (2, "old-window"),
                             (3, []), (3, [str(self.file)] * 101), (3, [str(self.file)] * 2),
                             (3, [str(self.file.parent)]), (3, [str(self.file) + ".missing"]),
                             (3, ["https://example.org/private"]), (3, [None])):
            args = list(good); args[index] = value
            with self.subTest(index=index, value=value), patch.object(r, "dbus") as call:
                self.assertFalse(r.reopen_editor(*args))
                call.assert_not_called()

    def test_only_an_unknown_method_allows_the_legacy_fallback(self):
        with patch.object(r, "dbus", side_effect=RuntimeError("org.freedesktop.DBus.Error.UnknownMethod")):
            self.assertIsNone(r.reopen_editor(APP, 12, self.ident, [str(self.file)]))
        with patch.object(r, "dbus", side_effect=RuntimeError("org.freedesktop.DBus.Error.NoReply")):
            self.assertIs(r.reopen_editor(APP, 12, self.ident, [str(self.file)]), False)
        for reply in ([False], [1], ["true"], [], None):
            with self.subTest(reply=reply), patch.object(r, "dbus", return_value=reply):
                self.assertIs(r.reopen_editor(APP, 12, self.ident, [str(self.file)]), False)

    def test_retry_sends_validated_offsets_with_the_matching_paths(self):
        for offsets in ([27], [None], [0], [2**31-1]):
            with patch.object(r, "dbus", return_value=[True]) as call:
                self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], offsets))
                self.assertEqual(json.loads(call.call_args.args[4])["cursors"], offsets)
        for offsets in ([], [0, 1], [True], [-1], [2**31], [1.2], "27", ["27"]):
            with patch.object(r, "dbus") as call:
                self.assertFalse(r.reopen_editor(APP, 12, self.ident, [str(self.file)], offsets))
                call.assert_not_called()

    def test_retry_accepts_a_full_bounded_batch_without_truncating_it(self):
        files = []
        for i in range(201):
            file = self.file.parent / f"late-{i}.txt"
            file.write_text(str(i), encoding="utf-8")
            files.append(str(file))
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, files[:200]))
            self.assertEqual(json.loads(call.call_args.args[4])["documents"], files[:200])
            call.reset_mock()
            self.assertFalse(r.reopen_editor(APP, 12, self.ident, files))
            call.assert_not_called()

    def test_retry_preserves_scroll_identity_and_rejects_invalid_coordinates(self):
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], [9], [[80, 12, 5, False]]))
            self.assertEqual(json.loads(call.call_args.args[4])["scrolls"], [[80, 12, 5, False]])
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], [9], [None]))
            self.assertNotIn("scrolls", json.loads(call.call_args.args[4]))
        for positions in ([], [None, None], [[0]], [[True, 0, 0, False]], [[0, -1, 0, False]], [[0, 0, 2**31, False]], ["0"], [[0, 0, None]]):
            with self.subTest(positions=positions), patch.object(r, "dbus") as call:
                self.assertFalse(r.reopen_editor(APP, 12, self.ident, [str(self.file)], [9], positions))
                call.assert_not_called()

    def test_retry_carries_only_bounded_folding_metadata(self):
        folding = {"checksum": "a" * 40, "ranges": [dict(startLine=1, startColumn=2, endLine=5, endColumn=3, flags=2)]}
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], foldings=[folding]))
            self.assertEqual(json.loads(call.call_args.args[4])["foldings"], [folding])
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], foldings=[None]))
            self.assertNotIn("foldings", json.loads(call.call_args.args[4]))
        for foldings in ([], [None, None], [True], [dict(folding, checksum="no")], [dict(folding, text="private")]):
            with self.subTest(foldings=foldings), patch.object(r, "dbus") as call:
                self.assertFalse(r.reopen_editor(APP, 12, self.ident, [str(self.file)], foldings=foldings))
                call.assert_not_called()

    def test_retry_carries_selection_coordinates_without_selected_text(self):
        selection = {"block": True, "cursor": [2, 40], "range": [0, 3, 2, 40]}
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], selections=[selection]))
            self.assertEqual(json.loads(call.call_args.args[4])["selections"], [selection])
            self.assertTrue(r.reopen_editor(APP, 12, self.ident, [str(self.file)], selections=[None]))
            self.assertNotIn("selections", json.loads(call.call_args.args[4]))
        for selections in ([], [None, None], [True], [dict(selection, range=[1, 0, 0, 0])],
                           [dict(selection, cursor=[-1, 0])], [dict(selection, text="private")]):
            with self.subTest(selections=selections), patch.object(r, "dbus") as call:
                self.assertFalse(r.reopen_editor(APP, 12, self.ident, [str(self.file)], selections=selections))
                call.assert_not_called()

    def test_window_replacement_requires_exact_identity_and_native_confirmation(self):
        anchor = "{87654321-1234-1234-1234-123456789abc}"
        new = "{abcdefab-1234-1234-1234-123456789abc}"
        editor = r.editor_helper().available(state(str(self.file)))
        request = {"id": self.ident, "anchor": anchor, "editor": editor}
        with patch.object(r, "dbus", return_value=[new]) as call:
            self.assertEqual(r.replace_editor(APP, 12, request), new)
            self.assertEqual(call.call_args.args[3], "monetReplaceWindow")
            self.assertEqual(json.loads(call.call_args.args[4]), request)
        with patch.object(r, "dbus", return_value=["closed"]):
            self.assertEqual(r.replace_editor(APP, 12, dict(request, attempt="a" * 32)), "closed")
        for reply in ([], [None], [True], [anchor], [self.ident], ["ambiguous"], ["closed", new], [{"closed": True}]):
            with self.subTest(reply=reply), patch.object(r, "dbus", return_value=reply):
                self.assertIsNone(r.replace_editor(APP, 12, request))
        for error in ("UnknownMethod", "NoReply"):
            with patch.object(r, "dbus", side_effect=RuntimeError("org.freedesktop.DBus.Error." + error)):
                self.assertIsNone(r.replace_editor(APP, 12, request))
        for invalid in (dict(request, id=anchor), dict(request, text="secret"), dict(request, editor=None),
                        *(dict(request, attempt=value) for value in (None, True, "", "a" * 31, "A" * 32, "a" * 32 + "\n"))):
            with patch.object(r, "dbus") as call:
                self.assertIsNone(r.replace_editor(APP, 12, invalid)); call.assert_not_called()
