"""Files recovery: native stream compatibility, private state and interruption safety."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from tests.test_resume import r, ROOT

f = r.files_helper()
STATE = {"tabs": [{"folders": ["/tmp"], "active": 0},
                  {"folders": ["/var/tmp", "/home/j/Water lilies % å"], "active": 1},
                  {"folders": ["/tmp"], "active": 0}], "active": 1}


def detailed():
    return {"tabs": [{"folders": ["/tmp", "/var/tmp"], "active": 1,
        "sizes": [400, 700], "label": "Water lilies 🌸",
        "views": [{"current": folder+"/a.txt", "selected": [folder+"/a.txt",folder+"/b.txt"],
                   "expanded": [folder+"/folder"], "scroll": [20, 123], "maximum": [200, 1000]}
                  for folder in ("/tmp", "/var/tmp")]}], "active": 0}


def decode_tab(tab):
    from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QPoint, QUrl
    data = QByteArray(f.tab_bytes(tab))
    stream = QDataStream(data, QIODevice.ReadOnly)
    assert stream.readUInt32() == 2
    assert stream.readBool() == (len(tab["folders"]) == 2)
    def url():
        value=QUrl(); stream >> value
        return value.toLocalFile() if not value.isEmpty() else None
    views=[]
    for folder in tab["folders"]:
        assert url()==folder and not stream.readBool() and stream.readUInt32()==1
        current=url()
        selected=[url() for _ in range(stream.readUInt32())]
        scroll=QPoint(); stream >> scroll
        expanded=[url() for _ in range(stream.readUInt32())]
        views.append({"current":current,"selected":selected,"scroll":[scroll.x(),scroll.y()],"expanded":expanded})
    assert stream.readBool() == (tab["active"]==0)
    splitter=QByteArray(); stream >> splitter
    label=stream.readQString()
    assert stream.atEnd() and stream.status()==QDataStream.Ok
    return views,splitter,label


class FilesState(unittest.TestCase):
    def test_view_metadata_rejects_unbounded_foreign_and_ambiguous_paths(self):
        original=detailed(); self.assertTrue(f.valid(original))
        for field,value in (("current","/elsewhere.txt"),("current","/tmp/../secret"),
                            ("selected",["/tmp/a.txt"]*2),("expanded",["/tmp"]),
                            ("selected",["/tmp/a"]*4097),("scroll",[True,0]),
                            ("scroll",[201,0]),("maximum",[-1,1000]),("text","contents")):
            state=copy.deepcopy(original); state["tabs"][0]["views"][0][field]=value
            with self.subTest(field=field,value=str(value)[:100]): self.assertFalse(f.valid(state))
        for field,value in (("sizes",[0,700]),("sizes",[True,700]),("label","\ud800"),("label","a"*1025),
                            ("views",[]),("contents","not metadata")):
            state=copy.deepcopy(original); state["tabs"][0][field]=value
            self.assertFalse(f.valid(state))
        state=copy.deepcopy(original); state["tabs"][0].pop("label")
        self.assertFalse(f.valid(state))

    def test_native_stream_preserves_known_view_state_and_unicode_tab_label(self):
        try: import PySide6
        except ImportError: self.skipTest("Qt runtime")
        tab=detailed()["tabs"][0]
        views,splitter,label=decode_tab(tab)
        self.assertEqual(views,[{k:v for k,v in view.items() if k!="maximum"} for view in tab["views"]])
        self.assertEqual(label,tab["label"])
        self.assertTrue(splitter)

    def test_existing_window_matches_without_resetting_changed_view_state(self):
        saved=detailed(); live=copy.deepcopy(saved)
        live["tabs"][0].update(label="Later",sizes=[600,500])
        live["tabs"][0]["views"][0].update(selected=[],scroll=[0,0])
        self.assertTrue(f.same_layout(saved,live))
        self.assertFalse(f.restored(saved,live))
        legacy={"tabs":[{"folders":saved["tabs"][0]["folders"],"active":1}],"active":0}
        self.assertTrue(f.same_layout(legacy,live))
        self.assertTrue(f.restored(legacy,live))
        self.assertFalse(f.restored(saved,legacy))

    def test_verification_requires_view_state_but_allows_missing_items_and_clamped_scroll(self):
        saved=detailed(); live=copy.deepcopy(saved)
        with patch.object(f.os.path,"lexists",return_value=True), patch.object(f.Path,"is_dir",return_value=True):
            self.assertTrue(f.restored(saved,live))
            for key,value in (("current","/tmp/other"),("selected",[]),("expanded",[]),("scroll",[19,123])):
                changed=copy.deepcopy(live); changed["tabs"][0]["views"][0][key]=value
                self.assertFalse(f.restored(saved,changed))
        for view in live["tabs"][0]["views"]:
            view.update(current=None,selected=[],expanded=[],scroll=[0,50],maximum=[0,50])
        live["tabs"][0]["sizes"]=[800,1400]
        with patch.object(f.os.path,"lexists",return_value=False), patch.object(f.Path,"is_dir",return_value=False):
            self.assertTrue(f.restored(saved,live))
            live["tabs"][0]["sizes"]=[1100,1100]
            self.assertFalse(f.restored(saved,live))

    def test_native_refusal_never_silently_downgrades_to_accessibility(self):
        try: from gi.repository import Gio, GLib
        except ImportError: self.skipTest("GObject runtime")
        connection=Mock()
        with patch.object(Gio,"bus_get_sync",return_value=connection), \
                patch.object(f,"native_paths",return_value=["/dolphin/Dolphin_2"]):
            connection.call_sync.return_value=GLib.Variant("(s)",(json.dumps(detailed()),))
            self.assertEqual(f.capture_native(42),(True,detailed()))
            connection.call_sync.return_value=GLib.Variant("(s)",("null",))
            self.assertEqual(f.capture_native(42),(True,None))
            connection.call_sync.side_effect=GLib.Error("unavailable")
            with patch.object(Gio.DBusError,"get_remote_error",return_value="org.freedesktop.DBus.Error.UnknownMethod"):
                self.assertEqual(f.capture_native(42),(False,None))
            with patch.object(Gio.DBusError,"get_remote_error",return_value="org.freedesktop.DBus.Error.NoReply"):
                with self.assertRaises(GLib.Error): f.capture_native(42)
        with patch.object(f,"capture_native",return_value=(True,None)):
            self.assertIsNone(f.capture_tree(42))

    def test_splitter_stream_in_separate_native_qt_process(self):
        try: import PySide6
        except ImportError: self.skipTest("Qt runtime")
        result=subprocess.run([sys.executable,"-m","unittest","tests.test_files_session.FilesWidgets"],
            cwd=ROOT,capture_output=True,text=True,timeout=30,
            env=dict(os.environ,QT_QPA_PLATFORM="offscreen",MONET_FILES_UI_TEST="1"))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_duplicate_tabs_and_split_active_side_are_valid(self):
        self.assertTrue(f.valid(STATE))
        for changed in ({}, dict(STATE, active=-1), dict(STATE, active=True),
                        dict(STATE, tabs=[]), dict(STATE, tabs=STATE["tabs"] * 33)):
            self.assertFalse(f.valid(changed))
        for bad in ("--new-window", "smb://server/private", "/tmp/new\nline", "/tmp/null\0", ""):
            state = copy.deepcopy(STATE)
            state["tabs"][0]["folders"] = [bad]
            self.assertFalse(f.valid(state))

    def test_capture_times_out_and_rejects_unexpected_output(self):
        with patch.object(f.subprocess, "run", side_effect=subprocess.TimeoutExpired("capture", 10)):
            self.assertIsNone(f.capture(42))
        with patch.object(f.subprocess, "run", return_value=Mock(stdout=b"null")) as run:
            self.assertIsNone(f.capture(42))
            self.assertEqual(run.call_args.kwargs["timeout"], 10)
        with patch.object(f.subprocess, "run") as run:
            self.assertIsNone(f.capture("42; sh"))
            run.assert_not_called()

    def test_native_window_lists_require_unique_real_ids_and_valid_states(self):
        ident = "{12345678-1111-2222-3333-444444444444}"
        item = {"id": ident, "files": STATE}
        self.assertTrue(f.valid_windows([item]))
        for state in (None, [], [None], [item, item], [item] * 17,
                      [dict(item, id="title")], [dict(item, id="{00000000-0000-0000-0000-000000000000}")],
                      [dict(item, files=None)], [dict(item, unexpected=True)]):
            self.assertFalse(f.valid_windows(state), state)
        with patch.object(f.subprocess, "run", return_value=Mock(stdout=json.dumps([item]).encode())):
            self.assertEqual(f.capture(42, windows=True), [item])
        with patch.object(f.subprocess, "run", return_value=Mock(stdout=json.dumps([item, item]).encode())):
            self.assertIsNone(f.capture(42, windows=True))

    def test_native_object_discovery_survives_first_window_closure_and_rejects_ambiguity(self):
        try: from gi.repository import Gio, GLib
        except ImportError: self.skipTest("GObject runtime")
        connection = Mock()
        connection.call_sync.return_value = GLib.Variant("(s)", ('<node><node name="Dolphin_2"/></node>',))
        self.assertEqual(f.native_paths(42, connection, Gio, GLib), ["/dolphin/Dolphin_2"])
        for xml in ('<node/>', '<node><node name="../other"/></node>',
                    '<node><node name="Dolphin_2"/><node name="Dolphin_2"/></node>'):
            connection.call_sync.return_value = GLib.Variant("(s)", (xml,))
            with self.assertRaises(ValueError): f.native_paths(42, connection, Gio, GLib)
        with patch.object(Gio, "bus_get_sync", return_value=connection), \
                patch.object(f, "native_paths", return_value=["/dolphin/Dolphin_1", "/dolphin/Dolphin_2"]):
            self.assertEqual(f.capture_native(42), (True, None))

    def test_each_files_process_is_captured_separately(self):
        frame = {"app": f.APP, "pid": 42, "id": "first"}
        with patch.object(f, "capture", return_value=STATE) as capture:
            self.assertEqual(r.checkpoint([f.APP], [frame])["groups"][f.APP][0]["files"], STATE)
            capture.assert_called_once_with(42)
            capture.reset_mock()
            groups = r.checkpoint([f.APP], [frame, dict(frame, pid=43, id="second")])["groups"][f.APP]
            self.assertEqual(len(groups), 2)
            self.assertEqual([c.args for c in capture.call_args_list], [(42,), (43,)])

    def test_native_stream_preserves_urls_and_avoids_file_selection(self):
        try:
            from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QPoint, QUrl
        except ImportError:
            self.skipTest("Qt runtime required for native stream validation")
        for tab in STATE["tabs"]:
            data = QByteArray(f.tab_bytes(tab))
            stream = QDataStream(data, QIODevice.ReadOnly)
            self.assertEqual(stream.readUInt32(), 2)
            self.assertEqual(stream.readBool(), len(tab["folders"]) == 2)
            for path in tab["folders"]:
                url = QUrl()
                stream >> url
                self.assertEqual(url.toLocalFile(), path)
                self.assertFalse(stream.readBool())
                self.assertEqual(stream.readUInt32(), 1)
                stream >> url
                self.assertTrue(url.isEmpty())
                self.assertEqual(stream.readUInt32(), 0)  # no selected file paths
                point = QPoint()
                stream >> point
                self.assertEqual(point, QPoint(0, 0))
                self.assertEqual(stream.readUInt32(), 0)  # no expanded folder list
            self.assertEqual(stream.readBool(), tab["active"] == 0)
            self.assertEqual(stream.readUInt32(), 0)  # no splitter history
            self.assertTrue(stream.atEnd())
            self.assertEqual(stream.status(), QDataStream.Ok)

    def test_session_is_private_and_uses_empty_key_for_wayland(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), \
                patch.object(f.Path, "is_dir", return_value=True), patch.object(f.subprocess, "Popen") as launch:
            launch.return_value.pid = 42
            path, pid = f.start(STATE)
            self.assertEqual(pid, 42)
            self.assertTrue(f.SESSION.fullmatch(path.name))
            args = launch.call_args.args[0]
            self.assertEqual(args[:3], ["dolphin", "--new-window", "--session"])
            self.assertNotIn("_", args[3])
            self.assertEqual(path.name, "dolphin_" + args[3] + "_")
            self.assertIn("Tab Count=3", path.read_text())
            self.assertEqual(launch.call_args.kwargs["env"]["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"], "1")
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            f.cleanup({"session": path.name})
            self.assertFalse(path.exists())
            launch.side_effect = OSError("failed launcher")
            with self.assertRaises(OSError):
                f.start(STATE)
            self.assertFalse(list((Path(tmp) / "session").iterdir()))

    def test_missing_folder_retains_work_without_opening_wrong_tabs(self):
        with patch.object(f.Path, "is_dir", return_value=False), patch.object(f.subprocess, "Popen") as launch:
            with self.assertRaises(OSError):
                f.start(STATE)
            launch.assert_not_called()

    def test_cleanup_cannot_escape_private_session_names(self):
        for name in ("../../dolphinrc", "dolphin_dolphin_dolphin", "/tmp/file", None):
            self.assertIsNone(f.session_path({"session": name}))
        receipt = {"session": "dolphin_monet-" + "a" * 32 + "_", "pid": 42}
        with patch.object(f.Path, "read_bytes", return_value=b"unrelated\0--session\0monet-" + b"a" * 32):
            self.assertFalse(f.alive(receipt))
        with patch.object(f.Path, "read_bytes", return_value=b"dolphin\0--session\0monet-" + b"a" * 32 + b"\0"):
            self.assertTrue(f.alive(receipt))


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class FilesReceipt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trip.json"
        self.off = self.path.with_name("off")
        self.state = {"version": 2, "time": 100, "boot": "old", "apps": [f.APP],
                      "windows": [{"app": f.APP, "id": "old", "pid": 1}], "files": STATE, "done": []}
        self.receipt = {"pid": 42, "session": "dolphin_monet-" + "a" * 32 + "_", "boot": "new"}
        self.current = {"app": f.APP, "id": "new", "pid": 42}
        for owner, name, value in ((r, "boot_id", "new"), (r.time, "time", 110),
                                   (r.time, "sleep", None), (r, "window_snapshot", [self.current]),
                                   (f, "cleanup", None), (f, "alive", True), (r, "place_windows", None)):
            p = patch.object(owner, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def run_restore(self):
        return r.restore(self.path, self.off, lambda: [], lambda _: True, lambda _: self.fail("generic launch"))

    def test_slow_pending_launch_is_reused_and_verified_before_receipt(self):
        self.state["files_launch"] = self.receipt
        r.atomic_write(self.path, self.state)
        with patch.object(f, "start") as start, patch.object(f, "capture", return_value=None):
            self.assertEqual(self.run_restore(), [])
            self.assertEqual(r.read_state(self.path)["done"], [])
            start.assert_not_called()
        with patch.object(f, "start") as start, patch.object(f, "capture", return_value=STATE):
            self.assertEqual(self.run_restore(), [f.APP])
            start.assert_not_called()
            self.assertFalse(self.path.exists())
            r.place_windows.assert_called_once()

    def test_native_view_state_must_be_verified_before_finishing_a_pending_launch(self):
        self.state.update(files=detailed(), files_launch=self.receipt)
        r.atomic_write(self.path, self.state)
        loading=copy.deepcopy(self.state['files'])
        loading['tabs'][0]['views'][0]['scroll']=[0,0]
        with patch.object(f,'start') as start, patch.object(f,'capture',return_value=loading) as capture, \
                patch.object(f.os.path,'lexists',return_value=True),patch.object(f.Path,'is_dir',return_value=True):
            self.assertEqual(self.run_restore(),[])
            self.assertEqual(r.read_state(self.path)['files_launch'],self.receipt)
            r.place_windows.assert_not_called()
            capture.return_value=self.state['files']
            self.assertEqual(self.run_restore(),[f.APP])
            self.assertFalse(self.path.exists())
            start.assert_not_called()
            r.place_windows.assert_called_once()

    def test_existing_files_window_is_left_alone(self):
        r.atomic_write(self.path, self.state)
        with patch.object(f, "start") as start:
            self.assertEqual(self.run_restore(), [])
            start.assert_not_called()
            r.place_windows.assert_not_called()

    def test_unavailable_folder_stays_pending_and_can_recover(self):
        r.atomic_write(self.path, self.state)
        r.window_snapshot.return_value = []
        with patch.object(f, "start", side_effect=OSError("drive missing")):
            self.assertEqual(self.run_restore(), [])
            self.assertEqual(r.read_state(self.path)["files"], STATE)
            self.assertEqual(r.read_state(self.path)["done"], [])
        r.window_snapshot.side_effect = [[], [self.current]]
        with patch.object(f, "start", return_value=(Path(self.receipt["session"]), 42)), \
                patch.object(f, "capture", return_value=STATE):
            self.assertEqual(self.run_restore(), [f.APP])
            self.assertFalse(self.path.exists())

    def test_off_during_capture_clears_state_and_does_not_move_window(self):
        self.state["files_launch"] = self.receipt
        r.atomic_write(self.path, self.state)
        def capture(_):
            self.off.touch()
            return STATE
        with patch.object(f, "capture", side_effect=capture):
            self.assertEqual(self.run_restore(), [])
            self.assertFalse(self.path.exists())
            r.place_windows.assert_not_called()
            f.cleanup.assert_called()


if os.environ.get("MONET_FILES_UI_TEST")=="1":
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication,QSplitter,QWidget

    class FilesWidgets(unittest.TestCase):
        def test_split_widths_use_qt_native_restore_in_both_directions(self):
            app=QApplication([])
            for direction in (Qt.LeftToRight,Qt.RightToLeft):
                widget=QSplitter(Qt.Horizontal)
                widget.setLayoutDirection(direction)
                widget.addWidget(QWidget());widget.addWidget(QWidget())
                widget.resize(1104,600);widget.show();app.processEvents()
                self.assertTrue(widget.restoreState(decode_tab(detailed()["tabs"][0])[1]))
                app.processEvents()
                widths=widget.sizes()
                self.assertLessEqual(abs(widths[0]/sum(widths)-400/1100)*sum(widths),1)
                self.assertFalse(widget.childrenCollapsible())
                self.assertEqual(widget.orientation(),Qt.Horizontal)
                widget.close()


if __name__ == "__main__":
    unittest.main()
