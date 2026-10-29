"""Editor recovery keeps missing files pending and never replays completed windows."""
import copy
import configparser
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r, ROOT

e = r.editor_helper()
APP = "org.kde.kate.desktop"


def state(*paths):
    return {"views": [{"documents": list(paths), "active": len(paths)-1, "cursor": 42}],
            "active": 0, "orientation": 1, "sizes": [800]}


def nested():
    return {"views": [state("/one")["views"][0], state("/two", "/three")["views"][0],
                      state("/four")["views"][0], state("/five")["views"][0]], "active": 2,
            "layout": {"orientation": 1, "sizes": [300, 600], "children": [0,
                {"orientation": 2, "sizes": [200, 500], "children": [1,
                    {"orientation": 1, "sizes": [250, 350], "children": [2, 3]}]}]}}


class EditorFormat(unittest.TestCase):
    def test_multicaret_selection_follows_its_document_and_window(self):
        selection = {"block": False, "cursor": [0, 4], "range": [0, 4, 0, 8], "anchor": [0, 8],
                     "secondary": [{"cursor": [2, 3], "range": [2, 3, 2, 7], "anchor": [2, 7]},
                                   {"cursor": [4, 2], "range": None, "anchor": None}]}
        original = state("/missing", "/saved")
        original["views"][0]["selections"] = [None, selection]
        self.assertTrue(e.valid(original))
        with patch.object(Path, "is_file", return_value=True):
            remaining = e.available(original, ["/saved"])
        self.assertEqual(remaining["views"][0]["selections"], [selection])
        self.assertEqual(e.document_selection(remaining, "/saved"), selection)
        self.assertEqual(e.document_selection(original, "/saved"), selection)
        self.assertIsNone(e.document_selection(remaining, "/missing"))

    def test_multicaret_metadata_refuses_invalid_anchors_and_duplicate_cursors(self):
        selection = {"block": False, "cursor": [0, 4], "range": None, "anchor": None,
                     "secondary": [{"cursor": [2, 3], "range": [2, 3, 2, 7], "anchor": [2, 7]}]}
        changes = [{"block": True}, {"anchor": [True, 0]}, {"anchor": [0, 2**31]},
                   {"secondary": []}, {"secondary": "invalid"}, {"text": "not checkpointed"}]
        for bad in ({"anchor": None}, {"cursor": [0, 4]}, {"range": [2, 7, 2, 3]},
                    {"anchor": [0, -1]}, {"extra": 1}):
            changes.append({"secondary": [dict(selection["secondary"][0], **bad)]})
        changes.append({"secondary": selection["secondary"] * 2})
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(e.valid_selection(dict(selection, **change)))
        self.assertFalse(e.valid_selection({k: v for k, v in selection.items() if k != "anchor"}))

    def test_multicaret_metadata_is_bounded_and_legacy_selections_still_work(self):
        selection = {"block": False, "cursor": [0, 0], "range": None, "anchor": None,
                     "secondary": [{"cursor": [i, 0], "range": None, "anchor": None} for i in range(1, 1024)]}
        self.assertTrue(e.valid_selection(selection))
        selection["secondary"].append({"cursor": [1024, 0], "range": None, "anchor": None})
        self.assertFalse(e.valid_selection(selection))
        self.assertTrue(e.valid_selection({"block": True, "cursor": [1, 99], "range": [0, 1, 1, 99]}))

    def test_folding_keeps_document_identity_and_active_pane_precedence(self):
        folded = {"checksum": "a" * 40, "ranges": [dict(startLine=1, startColumn=2, endLine=5, endColumn=3, flags=2)]}
        unfolded = dict(folded, ranges=[])
        first = dict(state("/shared", "/missing")["views"][0], foldings=[folded, None])
        second = dict(state("/shared")["views"][0], foldings=[unfolded])
        original = {"views": [first, second], "active": 1, "orientation": 1, "sizes": [300, 300]}
        self.assertTrue(e.valid(original))
        self.assertEqual(e.document_folding(original, "/shared"), unfolded)
        original["active"] = 0
        self.assertEqual(e.document_folding(original, "/shared"), folded)
        with patch.object(Path, "is_file", return_value=True):
            remaining = e.available(original, ["/shared"])
        self.assertEqual([v["foldings"] for v in remaining["views"]], [[folded], [unfolded]])
        self.assertIsNone(e.document_folding(remaining, "/missing"))

    def test_folding_rejects_malformed_crossing_duplicate_and_excessive_ranges(self):
        span = dict(startLine=1, startColumn=0, endLine=8, endColumn=0, flags=2)
        valid = {"checksum": "a" * 40, "ranges": [span, dict(span, startLine=2, endLine=4)]}
        self.assertTrue(e.valid_folding(valid))
        for bad in ({}, dict(valid, checksum="A" * 40), dict(valid, checksum="a" * 40 + "\n"),
                    dict(valid, text="private"), dict(valid, ranges=[dict(span, flags=True)]),
                    dict(valid, ranges=[dict(span, flags=4)]), dict(valid, ranges=[dict(span, endLine=2**31)]),
                    dict(valid, ranges=[dict(span, startLine=-1)]), dict(valid, ranges=[dict(span, endLine=1)]),
                    dict(valid, ranges=[span, dict(span, startLine=3, endLine=9)]),
                    dict(valid, ranges=[span, span]), dict(valid, ranges=list(reversed(valid["ranges"]))),
                    dict(valid, ranges=[dict(span, startLine=i, endLine=3000-i) for i in range(65)]),
                    dict(valid, ranges=[dict(span, startLine=2*i, endLine=2*i+1) for i in range(1025)])):
            with self.subTest(bad=bad): self.assertFalse(e.valid_folding(bad))
        for spans in ([dict(span, startLine=i, endLine=3000-i) for i in range(64)],
                      [dict(span, startLine=2*i, endLine=2*i+1) for i in range(1024)]):
            self.assertTrue(e.valid_folding(dict(valid, ranges=spans)))
        for entries in (None, [], [valid, None], [True]):
            bad = state("/one"); bad["views"][0]["foldings"] = entries
            self.assertFalse(e.valid(bad))

    def test_selections_follow_documents_through_missing_file_pruning(self):
        selection = {"block": True, "cursor": [4, 40], "range": [1, 3, 4, 40]}
        original = state("/one", "/missing", "/three")
        original["views"][0]["selections"] = [selection, None, dict(selection, block=False)]
        self.assertTrue(e.valid(original))
        with patch.object(Path, "is_file", return_value=True):
            remaining = e.available(original, ["/one", "/missing"])
        self.assertEqual(remaining["views"][0]["selections"], [selection, None])
        self.assertEqual(e.document_selection(remaining, "/one"), selection)
        self.assertIsNone(e.document_selection(remaining, "/three"))
        for value in ({}, dict(selection, block=1), dict(selection, cursor=[True, 0]),
                      dict(selection, cursor=[0, 2**31]), dict(selection, range=[1, 8, 1, 3]),
                      dict(selection, range=[3, 0, 1, 0]), dict(selection, range=[0, -1, 1, 2]),
                      dict(selection, text="never stored"), dict(selection, range=[0, 1])):
            bad = copy.deepcopy(original); bad["views"][0]["selections"][0] = value
            with self.subTest(value=value): self.assertFalse(e.valid(bad))

    def test_selection_retry_prefers_the_original_active_pane(self):
        selection = {"block": False, "cursor": [0, 2], "range": [0, 2, 0, 8]}
        first = dict(state("/shared")["views"][0], selections=[selection])
        second = dict(state("/shared")["views"][0], selections=[dict(selection, cursor=[0, 8])])
        original = {"views": [first, second], "active": 1, "orientation": 1, "sizes": [300, 300]}
        self.assertEqual(e.document_selection(original, "/shared")["cursor"], [0, 8])
        original["active"] = 0
        self.assertEqual(e.document_selection(original, "/shared")["cursor"], [0, 2])

    def test_scroll_positions_are_optional_bounded_and_follow_their_tabs(self):
        original = state("/one", "/two", "/three")
        original["views"][0]["scrolls"] = [[10, 0, 12, False], None, [200, 40, 0, True]]
        self.assertTrue(e.valid(original))
        self.assertEqual(e.document_scroll(original, "/one"), [10, 0, 12, False])
        self.assertEqual(e.document_scroll(original, "/three"), [200, 40, 0, True])
        self.assertIsNone(e.document_scroll(original, "/two"))
        with patch.object(Path, "is_file", return_value=True):
            remaining = e.available(original, ["/one", "/two"])
        self.assertEqual(remaining["views"][0]["scrolls"], [[10, 0, 12, False], None])
        self.assertTrue(e.valid(remaining))
        for invalid in (None, [], [None], [[True, 0, 0, False], None, None], [[-1, 0, 0, False], None, None],
                        [[0, 2**31, 0, False], None, None], [[0, 0, 1.5, False], None, None], [[0, 0], None, None],
                        [[0, 0, 0, 0], None, None], [{"line": 0}, None, None]):
            bad = copy.deepcopy(original); bad["views"][0]["scrolls"] = invalid
            with self.subTest(invalid=invalid): self.assertFalse(e.valid(bad))

    def test_shared_file_scroll_prefers_the_original_active_pane(self):
        first = dict(state("/shared")["views"][0], scrolls=[[19, 0, 0, None]])
        second = dict(state("/shared")["views"][0], scrolls=[[83, 4, 20, False]])
        original = {"views": [first, second], "active": 1, "orientation": 1, "sizes": [300, 300]}
        self.assertEqual(e.document_scroll(original, "/shared"), [83, 4, 20, False])
        original["active"] = 0
        self.assertEqual(e.document_scroll(original, "/shared"), [19, 0, 0, None])

    def test_inactive_cursors_are_optional_bounded_metadata(self):
        original = state("/one", "/two")
        self.assertTrue(e.valid(original))
        original["views"][0]["cursors"] = [123, None]
        self.assertTrue(e.valid(original))
        self.assertEqual(e.document_cursor(original, "/one"), 123)
        self.assertEqual(e.document_cursor(original, "/two"), 42)
        self.assertIsNone(e.document_cursor(original, "/missing"))
        for offsets in (None, [], [12], [12, 0], [True, None], [-1, None], [2**31, None], [1.5, None], ["12", None]):
            with self.subTest(offsets=offsets):
                bad = copy.deepcopy(original); bad["views"][0]["cursors"] = offsets
                self.assertFalse(e.valid(bad))
        original["views"][0]["active"] = 10
        self.assertFalse(e.valid(original))

    def test_pruning_keeps_hidden_offsets_and_promotes_the_new_selected_tab(self):
        original = state("/one", "/two", "/three")
        original["views"][0]["cursors"] = [17, 29, None]
        with patch.object(Path, "is_file", return_value=True):
            available = e.available(original, ["/one", "/two"])
            self.assertEqual(available["views"], [{"documents": ["/one", "/two"], "active": 0,
                                                  "cursor": 17, "cursors": [None, 29]}])
            self.assertTrue(e.valid(available))
            self.assertEqual(e.available(original)["views"], original["views"])
        self.assertEqual(original["views"][0]["cursors"], [17, 29, None])

    def test_retry_uses_the_active_panes_position_for_a_shared_document(self):
        original = {"views": [dict(state("/shared", "/one")["views"][0], cursors=[13, None]),
                              dict(state("/shared", "/two")["views"][0], cursors=[27, None])],
                    "active": 1, "layout": {"orientation": 1, "sizes": [300, 600], "children": [0, 1]}}
        self.assertEqual(e.document_cursor(original, "/shared"), 27)
        original["active"] = 0
        self.assertEqual(e.document_cursor(original, "/shared"), 13)

    def test_one_pane_can_use_the_full_process_tab_budget(self):
        many = state(*[f"/file-{i}" for i in range(200)])
        self.assertTrue(e.valid(many))
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(e.session_text(many))
        self.assertEqual(parser.getint("Open Documents", "Count"), 200)
        self.assertEqual(len(e.paths(many)), 200)
        self.assertFalse(e.valid(state(*many["views"][0]["documents"], "/too-many")))
        group = [{"id": "{12345678-1234-1234-1234-123456789abc}", "editor": many},
                 {"id": "{87654321-1234-1234-1234-123456789abc}", "editor": state("/extra")}]
        self.assertFalse(e.valid_windows(group))

    def test_multi_window_native_session_shares_document_ids_and_keeps_each_layout(self):
        windows = [{"id": "{12345678-1234-1234-1234-123456789abc}", "editor": nested()},
                   {"id": "{87654321-1234-1234-1234-123456789abc}", "editor": state("/five", "/one")}]
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(e.session_text(windows, windows=True))
        self.assertEqual(parser.getint("Number", "NumberOfWindows"), 2)
        self.assertEqual(parser.getint("Open Documents", "Count"), 5)
        self.assertEqual(parser.get("WindowProperties2", "ObjectName"), "MainWindow#2")
        self.assertEqual(parser.get("1-Splitter 1", "Children"), "1-ViewSpace 1,1-Splitter 2")
        self.assertEqual(parser.get("2-ViewSpace 0", "Documents"), "4,0")
        self.assertEqual(parser.get("2-ViewSpace 0", "Active View"), "0")
        self.assertEqual(parser.getint("1", "Active ViewSpace"), 2)
        self.assertEqual(parser.getint("2", "Active ViewSpace"), 0)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), \
                patch.object(Path, "is_file", return_value=True), patch.object(e.subprocess, "Popen") as start:
            start.return_value.pid = 123
            receipt = e.start(APP, windows, windows=True)
            self.assertEqual(e.session_path(receipt).read_text(encoding="ascii"), e.session_text(windows, windows=True))
            start.assert_called_once()
            e.cleanup(receipt)
            windows[1]["editor"] = None
            receipt = e.start(APP, windows, windows=True)
            empty = configparser.ConfigParser(interpolation=None)
            empty.read_string(e.session_path(receipt).read_text(encoding="ascii"))
            self.assertEqual(empty.getint("Number", "NumberOfWindows"), 2)
            self.assertEqual(empty.getint("2-ViewSpace 0", "Count"), 0)
            self.assertEqual(empty.get("2-ViewSpace 0", "Documents"), "")
            self.assertEqual(start.call_count, 2)
            e.cleanup(receipt)

    def test_window_metadata_requires_unique_exact_identities_and_bounded_content(self):
        first = {"id": "{12345678-1234-1234-1234-123456789abc}", "editor": nested()}
        second = {"id": "{87654321-1234-1234-1234-123456789abc}", "editor": None}
        self.assertTrue(e.valid_windows([first, second]))
        for bad in (None, [], [first, first], [first] * 17,
                    [dict(first, id="window title")], [dict(first, id="{00000000-0000-0000-0000-000000000000}")],
                    [dict(first, text="document contents")], [dict(first, editor={})]):
            with self.subTest(bad=bad): self.assertFalse(e.valid_windows(bad))
        many = state(*[f"/file-{i}" for i in range(100)])
        many["views"] *= 2
        many["sizes"] = [100, 100]
        self.assertTrue(e.valid_windows([dict(first, editor=many)]))
        self.assertFalse(e.valid_windows([dict(first, editor=many), dict(second, editor=state("/extra"))]))

    def test_window_capture_is_bounded_and_rejects_ambiguous_child_results(self):
        windows = [{"id": "{12345678-1234-1234-1234-123456789abc}", "editor": state("/file")}]
        with patch.object(e.subprocess, "run", return_value=Mock(stdout=json.dumps(windows).encode())) as run:
            self.assertEqual(e.capture(123, windows=True), windows)
            self.assertEqual(run.call_args.args[0][-1], "--windows")
            self.assertEqual(run.call_args.kwargs["timeout"], 10)
            run.return_value.stdout = json.dumps(windows * 2).encode()
            self.assertIsNone(e.capture(123, windows=True))
            run.return_value.stdout = b" " * (2 * 1024 * 1024 + 1)
            self.assertIsNone(e.capture(123, windows=True))

    @unittest.skipIf(os.name == "nt", "Linux editor D-Bus")
    def test_window_cursor_requests_keep_identity_and_never_use_ambiguous_fallback(self):
        from gi.repository import Gio, GLib
        windows = [{"id": "{12345678-1234-1234-1234-123456789abc}", "editor": nested()}]
        connection = Mock()
        connection.call_sync.return_value.unpack.return_value = [json.dumps(windows)]
        with patch.object(Path, "read_text", return_value="kate"), patch.object(Gio, "bus_get_sync", return_value=connection):
            self.assertEqual(e.capture_native(123, windows, windows=True), windows)
            args = connection.call_sync.call_args.args
            self.assertEqual(args[3], "monetEditorWindows")
            expected = json.loads(args[4].unpack()[0])
            self.assertEqual(expected[0]["id"], windows[0]["id"])
            self.assertEqual(expected[0]["editor"]["layout"], e.layout(nested(), False))
            connection.call_sync.reset_mock()
            self.assertIsNone(e.capture_native(123, windows * 2, windows=True))
            connection.call_sync.assert_not_called()
            connection.call_sync.side_effect = GLib.Error("Unavailable")
            with patch.object(Gio.DBusError, "get_remote_error", return_value="org.freedesktop.DBus.Error.UnknownMethod"), \
                    patch.object(e, "capture_tree") as fallback:
                self.assertIsNone(e.capture_native(123, windows=True))
                fallback.assert_not_called()

    def test_nested_session_retains_tree_order_and_active_pane(self):
        original = nested()
        self.assertTrue(e.valid(original))
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(e.session_text(original))
        self.assertEqual(parser.get("1-Splitter 0", "Children"), "1-ViewSpace 0,1-Splitter 1")
        self.assertEqual(parser.get("1-Splitter 1", "Children"), "1-ViewSpace 1,1-Splitter 2")
        self.assertEqual(parser.get("1-Splitter 2", "Children"), "1-ViewSpace 2,1-ViewSpace 3")
        self.assertEqual(parser.getint("1-Splitter 1", "Orientation"), 2)
        self.assertEqual(parser.get("1-Splitter 2", "Sizes"), "250,350")
        self.assertEqual(parser.getint("1", "Active ViewSpace"), 2)
        self.assertEqual(parser.get("1-ViewSpace 1", "Documents"), "1,2")
        self.assertEqual(parser.get("1-ViewSpace 1", "Active View"), "2")

    def test_nested_tree_rejects_ambiguous_indices_unbounded_and_extra_data(self):
        for change in (lambda s: s["layout"].update(children=[0, 0]),
                       lambda s: s["layout"].update(children=[1, 0]),
                       lambda s: s["layout"].update(children=[True, 0]),
                       lambda s: s["layout"].update(sizes=[0, 1]),
                       lambda s: s["layout"].update(text="secret"),
                       lambda s: s["views"][0].update(text="secret"),
                       lambda s: s.update(orientation=1),
                       lambda s: s.update(active=True)):
            bad = nested(); change(bad)
            self.assertFalse(e.valid(bad), bad)
        bad = nested()
        for _ in range(18):
            bad["layout"] = {"orientation": 1, "sizes": [100], "children": [bad["layout"]]}
        self.assertFalse(e.valid(bad))
        bad = nested(); bad["views"] *= 5
        self.assertFalse(e.valid(bad))

    def test_missing_panes_prune_only_their_branch(self):
        original = nested()
        with patch.object(Path, "is_file", autospec=True, side_effect=lambda p: str(p) in ("/two", "/four", "/five")):
            got = e.available(original)
        self.assertEqual(got["layout"], {"orientation": 2, "sizes": [200, 500], "children": [0,
            {"orientation": 1, "sizes": [250, 350], "children": [1, 2]}]})
        self.assertEqual(got["active"], 1)
        self.assertEqual(got["views"][0], {"documents": ["/two"], "active": 0, "cursor": 0})
        self.assertTrue(e.valid(got))
        self.assertEqual(original, nested())
        with patch.object(Path, "is_file", return_value=True):
            only = e.available(original, ["/five"])
        self.assertEqual(only["layout"], 0)
        self.assertEqual(only["active"], 0)

    def test_legacy_layout_compares_to_tree_without_sizes_or_cursors(self):
        old = state("/one")
        current = {"views": copy.deepcopy(old["views"]), "active": 0, "layout": 0}
        current["views"][0]["cursor"] = 0
        self.assertTrue(e.same_layout(current, old))
        before = nested(); after = copy.deepcopy(before)
        after["layout"]["sizes"] = [100, 200]
        after["views"][0]["cursor"] = 17
        self.assertTrue(e.same_layout(before, after))
        after["layout"]["children"][1]["orientation"] = 1
        self.assertFalse(e.same_layout(before, after))

    @unittest.skipIf(os.name == "nt", "Linux editor D-Bus")
    def test_native_capture_and_old_editor_fallback(self):
        from gi.repository import Gio, GLib
        connection = Mock()
        connection.call_sync.return_value.unpack.return_value = [json.dumps(nested())]
        with patch.object(Path, "read_text", return_value="kate"), patch.object(Gio, "bus_get_sync", return_value=connection):
            self.assertEqual(e.capture_native(123, nested()), nested())
            args = connection.call_sync.call_args.args
            self.assertEqual(args[0], "org.kde.kate-123")
            self.assertEqual(args[3], "monetEditorState")
            expected = json.loads(args[4].unpack()[0])
            self.assertEqual(expected["layout"], e.layout(nested(), False))
            connection.call_sync.side_effect = GLib.Error("Unavailable")
            with patch.object(Gio.DBusError, "get_remote_error", return_value="org.freedesktop.DBus.Error.UnknownMethod"), \
                    patch.object(e, "capture_tree", return_value=state("/old")) as fallback:
                self.assertEqual(e.capture_native(123), state("/old"))
                fallback.assert_called_once_with(123, None)
            with patch.object(Gio.DBusError, "get_remote_error", return_value="org.freedesktop.DBus.Error.NoReply"), \
                    patch.object(e, "capture_tree") as fallback:
                with self.assertRaises(GLib.Error): e.capture_native(123)
                fallback.assert_not_called()

    def test_background_active_pane_uses_current_file_and_rejects_ambiguity(self):
        views = state("/one")["views"] + state("/two")["views"]
        self.assertEqual(e.active_pane(views, [], "/one"), 0)
        self.assertEqual(e.active_pane(views, [], "/two"), 1)
        self.assertEqual(e.active_pane(views, [0], "/two"), 0)
        views[1] = views[0]
        self.assertIsNone(e.active_pane(views, [], "/one"))

    def test_paths_are_local_bounded_and_never_session_syntax(self):
        for path in ("relative", "https://private/path", "/ok\n[Injected]", "/" + "x"*8192):
            self.assertFalse(e.valid(state(path)))
        native = e.session_text(state("/home/j/a,b%[x].txt", "/home/j/hello world.txt"))
        self.assertIn("a%2Cb%25%5Bx%5D.txt", native)
        self.assertIn("Documents=0,1", native)
        self.assertIn("Active View=1", native)
        self.assertNotIn("42", native)  # Caret metadata is applied without copying any text.

    def test_missing_files_are_excluded_without_changing_the_checkpoint(self):
        original = state("/here", "/missing")
        with patch.object(Path, "is_file", side_effect=lambda: False):
            self.assertIsNone(e.available(original))
        with patch.object(Path, "is_file", autospec=True, side_effect=lambda p: str(p) == "/here"):
            got = e.available(original)
        self.assertEqual(got["views"][0], {"documents": ["/here"], "active": 0, "cursor": 0})
        self.assertEqual(original["views"][0]["documents"], ["/here", "/missing"])

    def test_private_native_session_and_supported_app_arguments(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), \
                patch.object(Path, "is_file", return_value=True), patch.object(e.subprocess, "Popen") as start:
            start.return_value.pid = 123
            for app in e.EDITORS:
                receipt = e.start(app, state("/some/file.txt"))
                path = e.session_path(receipt)
                if os.name != "nt":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                args = start.call_args.args[0]
                self.assertEqual("--block" in args, app == APP)
                self.assertNotIn("--start", args)
                self.assertIn("--session", args)
                e.cleanup(receipt); self.assertFalse(path.exists())
            self.assertIsNone(e.session_path({"session": "../../personal.txt"}))

    def test_capture_is_bounded_and_no_document_text_api_is_called(self):
        with patch.object(e.subprocess, "run", return_value=Mock(stdout=b'{}')) as run:
            self.assertIsNone(e.capture(1))
            self.assertEqual(run.call_args.kwargs["timeout"], 10)
        source = (ROOT / "linux/libexec/monet-editor-session").read_text(encoding="utf-8")
        for api in ("get_text(", "get_text_at_offset(", "get_name("):
            self.assertNotIn(api, source)

    def test_receipt_rejects_pid_reuse_and_unrelated_sessions(self):
        receipt = {"session": "kate_monet-" + "a"*32 + "_", "pid": 12}
        for command, expected in ((b'kate\0--session\0monet-' + b'a'*32 + b'\0', True),
                                  (b'kate\0--session\0different\0', False),
                                  (b'other-app\0--session\0monet-' + b'a'*32 + b'\0', False)):
            with patch.object(Path, "read_bytes", return_value=command):
                self.assertEqual(e.alive(receipt), expected)

    def test_checkpoint_captures_separate_editor_instances(self):
        frames = [{"app": APP, "pid": n, "id": str(n)} for n in (1, 2)]
        with patch.object(e, "capture", side_effect=lambda pid: state("/file"+str(pid))), \
                patch.object(r, "editor_documents", return_value=[]), patch.object(r.time, "sleep"):
            saved = r.checkpoint([APP], frames)
        self.assertEqual([g["editor"] for g in saved["groups"][APP]], [state("/file1"), state("/file2")])


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class EditorRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.off = self.root/"trip.json", self.root/"off"
        self.one, self.two, self.other = [self.root/name for name in ("one.txt", "two.txt", "other.txt")]
        self.one.write_text("first", encoding="utf-8"); self.other.write_text("second", encoding="utf-8")
        self.windows, self.live, self.launches, self.opens = [], {}, [], []
        self.saved = {"version": 2, "id": "a"*32, "time": 100, "boot": "old", "apps": [APP], "done": [],
                      "groups": {APP: [{"editor": state(str(self.one), str(self.two)), "windows": []},
                                       {"editor": state(str(self.other)), "windows": []}]}}
        for owner, name, kwargs in (
                (r, "boot_id", {"return_value": "new"}), (r.time, "time", {"return_value": 110}),
                (r.time, "sleep", {}), (r, "window_snapshot", {"side_effect": lambda: copy.deepcopy(self.windows)}),
                (r, "remember_placement", {}), (e, "capture", {"side_effect": lambda pid, *a, **kw: copy.deepcopy(self.live.get(pid))}),
                (e, "start", {"side_effect": self.start}), (e, "alive", {"side_effect": lambda receipt: receipt.get("pid") in self.live}),
                (e, "cleanup", {}), (r, "dbus", {"side_effect": self.open})):
            p = patch.object(owner, name, **kwargs); p.start(); self.addCleanup(p.stop)
        r.atomic_write(self.path, self.saved)

    def start(self, app, expected):
        pid = len(self.launches)+10
        self.launches.append(copy.deepcopy(expected)); self.live[pid] = copy.deepcopy(expected)
        self.windows.append({"id": str(pid), "pid": pid, "app": app})
        return {"pid": pid, "session": "kate_monet-"+"a"*32+"_"}

    def open(self, service, path, interface, method, url, encoding):
        from urllib.parse import unquote, urlsplit
        pid = int(service.rsplit("-", 1)[1]); document = unquote(urlsplit(url).path)
        self.opens.append(document)
        self.live[pid]["views"][0]["documents"].append(document)
        return [True]

    def restore(self, retry=False):
        return r.restore(self.path, self.off, lambda: [], lambda _: True, Mock(),
                         request=self.saved["id"] if retry else None)

    def test_partial_return_then_explicit_retry_reuses_window_and_completed_sibling(self):
        self.restore()
        self.assertEqual(len(self.launches), 2)
        status = r.return_status(self.path, self.off)
        self.assertTrue(status["items"][0]["retry"])
        self.assertEqual(status["items"][0]["missing"], [self.two.name])
        self.assertFalse(self.two.exists())
        self.two.write_text("returned", encoding="utf-8")
        self.restore()  # Another login/automatic invocation must not reopen late files.
        self.assertEqual(self.opens, [])
        self.restore(retry=True)
        self.assertEqual(self.opens, [str(self.two)])
        self.assertEqual(len(self.launches), 2)
        self.assertFalse(self.path.exists())
        self.restore(retry=True)
        self.assertEqual(len(self.opens), 1)

    def test_native_retry_targets_its_owned_window_without_application_open(self):
        self.restore()
        ident = "{12345678-1234-1234-1234-123456789abc}"
        self.windows[0]["id"] = ident
        saved = r.read_state(self.path)
        saved["groups"][APP][0]["editor_owner"]["id"] = ident
        r.atomic_write(self.path, saved)
        self.two.write_text("returned", encoding="utf-8")
        def capture(pid, *args, **kwargs):
            current = copy.deepcopy(self.live.get(pid))
            return [{"id": ident, "editor": current}] if kwargs.get("windows") else current
        def reopen(app, pid, window, documents, cursors, scrolls, selections, foldings):
            self.assertEqual((app, pid, window, documents), (APP, 10, ident, [str(self.two)]))
            self.assertEqual(cursors, [42])
            self.assertEqual(scrolls, [None])
            self.assertEqual(selections, [None])
            self.assertEqual(foldings, [None])
            self.live[pid]["views"][0]["documents"].extend(documents)
            return True
        with patch.object(e, "capture", side_effect=capture), patch.object(r, "reopen_editor", side_effect=reopen) as call:
            self.restore(retry=True)
        call.assert_called_once()
        self.assertEqual(self.opens, [])
        self.assertEqual(len(self.launches), 2)
        self.assertFalse(self.path.exists())

    def test_native_rejection_never_falls_back_to_the_active_window(self):
        self.restore()
        ident = "{12345678-1234-1234-1234-123456789abc}"
        self.two.write_text("returned", encoding="utf-8")
        def capture(pid, *args, **kwargs):
            current = copy.deepcopy(self.live.get(pid))
            return [{"id": ident, "editor": current}] if kwargs.get("windows") else current
        with patch.object(e, "capture", side_effect=capture), patch.object(r, "reopen_editor", return_value=False):
            self.restore(retry=True)
        self.assertEqual(self.opens, [])
        self.assertEqual(r.read_state(self.path)["groups"][APP][0]["pending"], [str(self.two)])

    def test_late_native_completion_after_timeout_is_verified_without_fallback(self):
        self.restore()
        ident = "{12345678-1234-1234-1234-123456789abc}"
        self.two.write_text("returned", encoding="utf-8")
        def capture(pid, *args, **kwargs):
            current = copy.deepcopy(self.live.get(pid))
            return [{"id": ident, "editor": current}] if kwargs.get("windows") else current
        def delayed_reply(*args):
            self.live[10]["views"][0]["documents"].append(str(self.two))
            return False
        with patch.object(e, "capture", side_effect=capture), patch.object(r, "reopen_editor", side_effect=delayed_reply) as call:
            self.restore(retry=True)
        call.assert_called_once()
        self.assertEqual(self.opens, [])
        self.assertEqual(len(self.launches), 2)
        self.assertFalse(self.path.exists())

    def test_manually_reopened_missing_document_is_not_duplicated(self):
        self.restore(); self.two.write_text("returned", encoding="utf-8")
        self.live[10]["views"][0]["documents"].append(str(self.two))
        self.restore(retry=True)
        self.assertFalse(self.path.exists()); self.assertEqual(self.opens, [])

    def test_all_missing_never_launches_blank_files_and_can_recover_later(self):
        self.one.unlink(); self.other.unlink(); self.restore()
        self.assertEqual(self.launches, []); self.assertTrue(self.path.exists())
        for p in (self.one, self.two, self.other): p.write_text("returned", encoding="utf-8")
        self.restore(retry=True)
        self.assertEqual(len(self.launches), 2); self.assertFalse(self.path.exists())

    def test_closed_owner_reopens_only_the_pending_documents(self):
        self.restore(); del self.live[10]; self.windows = [w for w in self.windows if w["pid"] != 10]
        self.two.write_text("returned", encoding="utf-8"); self.restore(retry=True)
        self.assertEqual(e.paths(self.launches[-1]), [str(self.two)])
        self.assertEqual(len(self.launches), 3)

    def test_matching_existing_windows_are_consumed_one_for_one(self):
        self.saved["groups"][APP] = [{"editor": state(str(self.one)), "windows": []} for _ in range(2)]
        self.windows = [{"id": "existing", "pid": 9, "app": APP}]; self.live[9] = state(str(self.one))
        r.atomic_write(self.path, self.saved); self.restore()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.windows[0]["id"], "existing")
        self.assertFalse(self.path.exists())

    def test_completed_identical_sibling_cannot_consume_a_failed_windows_retry(self):
        self.saved["groups"][APP] = [{"editor": state(str(self.one)), "windows": []} for _ in range(2)]
        r.atomic_write(self.path, self.saved)
        with patch.object(e, "capture", side_effect=lambda pid, *a: self.live.get(pid) if pid != 11 else None):
            self.restore()
        del self.live[11]; self.windows = [w for w in self.windows if w["pid"] != 11]
        self.restore(retry=True)
        self.assertEqual(len(self.launches), 3)
        self.assertFalse(self.path.exists())

    def test_slow_launch_is_reused_instead_of_started_again(self):
        with patch.object(e, "capture", return_value=None): self.restore()
        self.assertEqual(len(self.launches), 2)
        self.restore(retry=True)
        self.assertEqual(len(self.launches), 2)
        self.assertEqual(r.return_status(self.path, self.off)["items"][0]["missing"], [self.two.name])

    def test_unconfirmed_cursor_restore_keeps_its_launch_for_retry(self):
        self.two.write_text("returned", encoding="utf-8")
        def capture(pid, cursors=None, **kwargs):
            return None if cursors else copy.deepcopy(self.live.get(pid))
        with patch.object(e, "capture", side_effect=capture):
            self.restore()
        pending = r.read_state(self.path)
        self.assertTrue(all("editor_launch" in group and "editor_owner" not in group for group in pending["groups"][APP]))
        self.assertEqual(pending["done"], [])
        self.assertEqual(len(self.launches), 2)
        self.restore(retry=True)
        self.assertEqual(len(self.launches), 2)
        self.assertFalse(self.path.exists())

    def test_cancelled_switch_leaves_surviving_editor_untouched(self):
        self.saved.update(version=3, boot="new", cancelled_boot="new")
        self.saved["groups"][APP][0]["windows"] = [{"id": "survivor", "pid": 9, "app": APP}]
        self.saved["groups"][APP][0]["final_unverified"] = True
        self.windows = [{"id": "survivor", "pid": 9, "app": APP}]
        self.live[9] = state("/changed-and-unsaved.txt")
        r.atomic_write(self.path, self.saved); self.restore(retry=True)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(e.paths(self.live[9]), ["/changed-and-unsaved.txt"])
        self.assertFalse(self.path.exists())
        self.assertNotEqual(r.return_status(self.path,self.off)["items"][0]["status"], "documents-unconfirmed")

    def test_unconfirmed_final_paths_remain_visible_after_old_documents_reopen(self):
        self.two.write_text("available",encoding="utf-8")
        self.saved["groups"][APP][0]["final_unverified"] = True
        r.atomic_write(self.path,self.saved);self.restore()
        self.assertFalse(self.path.exists())
        self.assertEqual(r.return_status(self.path,self.off)["items"][0]["status"], "documents-unconfirmed")

    def test_wrong_tabs_or_split_layout_is_not_reported_as_complete(self):
        with patch.object(e, "same_layout", return_value=False): self.restore()
        self.assertTrue(self.path.exists())
        self.assertEqual(r.read_state(self.path)["done"], [])

    def test_malformed_groups_or_pending_lists_do_not_launch_or_discard(self):
        for groups in (None, [None], [{"editor": state(str(self.one)), "pending": {"bad": True}}]):
            self.saved["groups"][APP] = groups
            r.atomic_write(self.path, self.saved)
            self.restore()
            self.assertTrue(self.path.exists()); self.assertEqual(self.launches, [])

    def test_legacy_missing_files_keep_the_existing_window_as_the_retry_target(self):
        self.saved.pop("groups")
        self.saved["documents"] = {APP: [str(self.one), str(self.two)]}
        r.atomic_write(self.path, self.saved)
        def legacy_start(*args, **kwargs):
            self.start(APP, state(str(self.one)))
        with patch.object(r.subprocess, "Popen", side_effect=legacy_start): self.restore()
        self.assertTrue(self.path.exists()); self.assertEqual(len(self.launches), 1)
        self.two.write_text("returned", encoding="utf-8")
        self.restore(retry=True)
        self.assertEqual(self.opens, [str(self.two)])
        self.assertEqual(len(self.launches), 1); self.assertFalse(self.path.exists())
