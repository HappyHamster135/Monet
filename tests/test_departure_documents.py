"""Save As at close is committed before reboot, without trusting shared editor files."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_editor_session import APP, state, e
from tests.test_resume import r


def native(paths, split=False):
    from urllib.parse import quote
    text = "[Open Documents]\nCount="+str(len(paths))+"\n[Open MainWindows]\nCount=1\n"
    for i, path in enumerate(paths):
        text += f"[Document {i}]\nURL=" + ("file://"+quote(path,safe="/") if path else "") + "\n"
    if split:
        text += "[MainWindow0]\nActive ViewSpace=1\n[MainWindow0-Splitter 0]\nOrientation=2\nSizes=400,600\nChildren=MainWindow0-ViewSpace 0,MainWindow0-ViewSpace 1\n"
        for i in range(2):
            text += f"[MainWindow0-ViewSpace {i}]\nDocuments={i}\nActive View={i}\n"
    return text


class FinalDocumentParser(unittest.TestCase):
    def test_final_urls_exclude_discarded_unsaved_recent_and_stale_documents(self):
        text = native(["/new name [x].txt", "", "/other.txt"])
        text += "[Document 3]\nURL=file:///closed.txt\n[Recent Files]\nFile1=/unrelated.txt\n"
        self.assertEqual(e.paths(e.final_documents(text)), ["/new name [x].txt", "/other.txt"])
        self.assertIsNone(e.final_documents(native([""])))

    def test_saved_as_paths_keep_their_panes_and_previously_captured_cursor(self):
        old = {"views": [state("/old.txt")["views"][0], state("/other.txt")["views"][0]],
               "orientation": 2, "sizes": [400,600], "active": 1}
        result = e.final_documents(native(["/renamed.txt", "/new.txt"], split=True), old)
        self.assertEqual([v["documents"] for v in result["views"]], [["/renamed.txt"], ["/new.txt"]])
        self.assertEqual([v["cursor"] for v in result["views"]], [42,42])
        self.assertEqual(result["active"], 1); self.assertEqual(result["orientation"], 2)

    def test_remote_urls_and_malformed_layout_are_never_replayed(self):
        self.assertIsNone(e.final_documents(native(["/x"]).replace("file:///x", "https://private.example/path")))
        for text in (native(["/x"]).replace("Count=1", "Count=201", 1),
                     native(["/x"]).replace("[Open MainWindows]\nCount=1", "[Open MainWindows]\nCount=2"),
                     native(["/a", "/b"], split=True).replace("Documents=1", "Documents=200")):
            with self.assertRaises(ValueError): e.final_documents(text)

    def test_session_names_cannot_escape_the_editor_directory(self):
        path = e.native_path(APP, "../../strange.session")
        self.assertEqual(path.parent.name, "sessions")
        self.assertNotIn("..", path.name)
        with self.assertRaises(ValueError):e.native_path(APP, "bad\nname")

    def test_single_document_rename_retains_the_visible_cursor(self):
        result = e.final_documents(native(["/renamed.txt"]), state("/old.txt"))
        self.assertEqual(result["views"][0]["cursor"], 42)
        with self.assertRaises(ValueError):
            e.final_documents("[DEFAULT]\nURL=file:///inherited.txt\n" + native([""]))

    def test_kwrite_final_urls_preserve_tab_order_selection_and_cursor(self):
        old = state("/b.txt", "/a.txt");old["views"][0]["active"]=1
        self.assertEqual(e.final_documents(native(["/a.txt", "/b.txt"]),old),old)
        result=e.final_documents(native(["/renamed.txt", "/b.txt"]),old)
        self.assertEqual(result["views"][0],{"documents":["/b.txt","/renamed.txt"],"active":1,"cursor":42})
        many = state(*[f"/file-{i}" for i in range(200)])
        self.assertEqual(e.final_documents(native(many["views"][0]["documents"]), many), many)


class EditorDiscovery(unittest.TestCase):
    def test_group_departure_explicitly_uses_the_group_protocol(self):
        with patch.object(r, "dbus", return_value=[True]) as call:
            self.assertTrue(r.arm_editor(APP,12,"a"*32,windows=True))
            self.assertEqual(call.call_args.args[3:],("monetDepartureWindows","a"*32,True))

    def test_old_editor_falls_back_but_failed_native_arm_cancels(self):
        with patch.object(r, "dbus", side_effect=RuntimeError("org.freedesktop.DBus.Error.UnknownMethod")):
            self.assertFalse(r.arm_editor(APP, 12, "a"*32))
        for result in ([False], [], ["true"], [1]):
            with patch.object(r, "dbus", return_value=result), self.assertRaises(RuntimeError):
                r.arm_editor(APP, 12, "a"*32)
        with patch.object(r, "dbus", side_effect=RuntimeError("org.freedesktop.DBus.Error.NoReply")), self.assertRaises(RuntimeError):
            r.arm_editor(APP, 12, "a"*32)

    def test_closed_process_is_not_queried_during_dbus_teardown(self):
        def query(service, path, interface, method, *args):
            if method == "ListNames":return [["org.kde.kate-12", "org.kde.kate-13", "org.kde.kwrite-14"]]
            if service == "org.kde.kate-12":raise RuntimeError("UnknownObject")
            return ["writing"]
        with patch.object(r, "dbus", side_effect=query) as calls:
            self.assertEqual(r.editor_sessions(APP, exclude={12}), {13:"writing"})
            self.assertEqual(calls.call_count, 2)


@unittest.skipIf(os.name == "nt", "Linux checkpoint lock")
class DepartureDocuments(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path=self.root/"trip.json"
        self.window = {"app":APP,"pid":12,"id":"editor","rect":{"x":10,"y":20,"width":800,"height":600}}
        self.saved = {"version":3,"id":"a"*32,"boot":"same","time":100,"apps":[APP],
                      "windows":[self.window],"documents":{},"groups":{APP:[{"editor":state("/old.txt"),"windows":[self.window]}]}}
        self.sessions = {12:""}
        for owner,name,kwargs in ((r,"boot_id",{"return_value":"same"}),
                                  (r,"arm_editor",{"return_value":False}),
                                  (r,"editor_sessions",{"side_effect":lambda _,**kw:self.sessions.copy()}),
                                  (e,"capture",{"return_value":None})):
            p=patch.object(owner,name,**kwargs);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{"XDG_DATA_HOME":str(self.root)});p.start();self.addCleanup(p.stop)
        self.source=e.native_path(APP,"");self.source.parent.mkdir(parents=True)
        self.source.write_text(native(["/old.txt"]),encoding="utf-8")
        r.atomic_write(self.path,self.saved)

    def prepare(self):
        r.prepare_editor_close(self.path,self.saved["id"],self.window,[self.window])

    def group(self):return r.read_state(self.path)["groups"][APP][0]

    def test_save_as_uses_final_urls_not_the_still_existing_old_file(self):
        self.prepare(); self.source.write_text(native(["/renamed.txt", "/new.txt"]),encoding="utf-8")
        self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[]))
        self.assertEqual(e.paths(self.group()["editor"]),["/renamed.txt","/new.txt"])
        self.assertEqual(self.group()["windows"],[self.window])
        self.assertNotIn("closing",self.group())
        self.source.write_text(native(["/unrelated-later.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/renamed.txt","/new.txt"])

    def test_untitled_only_capture_gains_its_first_saved_document(self):
        self.saved.pop("groups");r.atomic_write(self.path,self.saved)
        self.prepare();self.source.write_text(native(["/first-save.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/first-save.txt"])

    def test_repeated_watch_retains_the_baseline_for_an_independent_exit(self):
        self.prepare();receipt=self.group()["closing"].copy()
        self.source.write_text(native(["/saved-while-another-app-waited.txt"]),encoding="utf-8")
        self.prepare()
        self.assertEqual(self.group()["closing"],receipt)
        e.capture.assert_called_once()
        self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[{"app":"other.desktop","pid":42}]))
        self.assertEqual(e.paths(self.group()["editor"]),["/saved-while-another-app-waited.txt"])

    def test_cancellation_during_watch_cannot_add_a_late_close_receipt(self):
        def cancel(pid):
            r.cancel_departure(self.path,self.saved["id"])
            return state("/current.txt")
        e.capture.side_effect=cancel
        self.prepare()
        self.assertNotIn("closing",self.group())
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_an_editor_opened_during_the_wait_gets_an_independent_watch(self):
        self.prepare();self.sessions[13]="new-window"
        target=dict(self.window,pid=13,id="new-window")
        r.prepare_editor_close(self.path,self.saved["id"],target,[self.window,target])
        groups=r.read_state(self.path)["groups"][APP]
        self.assertEqual(len(groups),2)
        self.assertEqual(groups[1]["windows"],[target])
        self.assertEqual(groups[1]["closing"]["pid"],13)
        r.prepare_editor_close(self.path,self.saved["id"],target,[self.window,target])
        self.assertEqual(len(r.read_state(self.path)["groups"][APP]),2)

    def test_later_shared_writer_invalidates_the_earlier_exclusive_watch(self):
        self.prepare();self.sessions[13]=""
        other=dict(self.window,pid=13,id="other")
        r.prepare_editor_close(self.path,self.saved["id"],other,[self.window,other])
        self.assertTrue(all(g["closing"]["shared"] for g in r.read_state(self.path)["groups"][APP]))
        self.source.write_text(native(["/other.txt"]),encoding="utf-8")
        self.sessions={}
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertTrue(all(g["final_unverified"] for g in r.read_state(self.path)["groups"][APP]))
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_cancelled_save_dialog_does_not_replace_the_live_editors_checkpoint(self):
        self.prepare();self.source.write_text(native(["/wrong.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[self.window],final=True)
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])
        self.assertTrue(r.cancel_departure(self.path,self.saved["id"]))
        self.assertNotIn("closing",self.group())

    def test_discarded_untitled_does_not_keep_an_outdated_document_list(self):
        self.prepare();self.source.write_text(native([""]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertIsNone(self.group()["editor"])

    def test_shared_anonymous_sessions_never_mix_documents(self):
        self.sessions[13]="";self.prepare();self.source.write_text(native(["/other-editor.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])
        self.assertTrue(self.group()["final_unverified"])

    def test_distinct_named_sessions_can_refresh_independently(self):
        self.sessions={12:"writing",13:"other"};self.source=e.native_path(APP,"writing")
        self.source.parent.mkdir(parents=True);self.source.write_text(native(["/old.txt"]),encoding="utf-8")
        self.prepare();self.source.write_text(native(["/new.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/new.txt"])

    def test_changing_session_while_waiting_cancels_before_accepting_its_old_saved_list(self):
        self.prepare()
        self.source.write_text(native(["/saved-before-session-change.txt"]),encoding="utf-8")
        self.sessions[12]="different work"
        before=self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError,"session changed"):
            r.refresh_departure(self.path,self.saved["id"],[self.window])
        self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(r.cancel_departure(self.path,self.saved["id"]))
        self.assertNotIn("closing",self.group())

    def test_shared_writer_seen_while_waiting_stays_unconfirmed_after_it_exits(self):
        self.prepare();self.sessions[13]=""
        self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[self.window]))
        self.assertTrue(self.group()["closing"]["shared"])
        self.sessions={}
        self.source.write_text(native(["/other-process-save-as.txt"]),encoding="utf-8")
        self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[]))
        self.assertTrue(self.group()["final_unverified"])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_native_receipt_can_follow_a_changed_session_without_using_the_fallback(self):
        r.arm_editor.return_value=True;self.prepare()
        self.sessions[12]="different work"
        with patch.object(r,"editor_sessions",side_effect=AssertionError("Native receipts own their paths")):
            self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[self.window]))
            self.native_receipt(editor=state("/renamed-in-new-session.txt"))
            self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[]))
        self.assertEqual(e.paths(self.group()["editor"]),["/renamed-in-new-session.txt"])

    def test_new_owner_of_the_shared_file_makes_the_final_read_ambiguous(self):
        self.prepare();self.sessions[13]="";self.source.write_text(native(["/other.txt"]),encoding="utf-8")
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertTrue(self.group()["final_unverified"])

    def test_no_fresh_final_write_waits_then_cancels_without_losing_the_checkpoint(self):
        self.prepare()
        with patch.object(r.time,"monotonic",return_value=10):
            self.assertFalse(r.refresh_departure(self.path,self.saved["id"],[]))
        with patch.object(r.time,"monotonic",return_value=14):
            with self.assertRaises(RuntimeError):r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_stale_attempt_or_boot_cannot_edit_another_checkpoint(self):
        before=self.path.read_bytes()
        r.prepare_editor_close(self.path,"b"*32,self.window,[self.window])
        r.refresh_departure(self.path,"b"*32,[])
        self.assertEqual(self.path.read_bytes(),before)
        r.boot_id.return_value="other"
        self.prepare();self.assertEqual(self.path.read_bytes(),before)

    def test_bad_native_file_does_not_destroy_the_previous_state(self):
        self.prepare();self.source.write_text("broken",encoding="utf-8")
        with self.assertRaises(ValueError):r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_final_read_cannot_overwrite_cancellation_during_ipc(self):
        import fcntl
        self.prepare();self.source.write_text(native(["/new.txt"]),encoding="utf-8")
        def cancel(*args, **kwargs):
            # A nested Qt event must be able to take the checkpoint lock.
            with self.path.with_suffix(".lock").open("a") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(stream, fcntl.LOCK_UN)
            r.cancel_departure(self.path,self.saved["id"])
            return {}
        with patch.object(r,"editor_sessions",side_effect=cancel):
            self.assertFalse(r.refresh_departure(self.path,self.saved["id"],[]))
        self.assertEqual(r.read_state(self.path)["cancelled_boot"],"same")
        self.assertNotIn("closing",self.group())

    def test_malformed_groups_and_close_receipts_fail_closed(self):
        self.prepare();good=r.read_state(self.path)
        for groups in (None, [None], [{"closing":None}], [{"closing":{"pid":[]}}],
                       [{"closing":{"pid":12,"session":"","shared":False,"closed_at":"bad"}}]):
            saved=copy.deepcopy(good);saved["groups"][APP]=groups;r.atomic_write(self.path,saved)
            before=self.path.read_bytes()
            with self.assertRaises(ValueError):r.refresh_departure(self.path,self.saved["id"],[])
            self.assertEqual(self.path.read_bytes(),before)

    def native_receipt(self, pid=12, editor=None, supported=True):
        runtime=self.root/"runtime";runtime.mkdir(mode=0o700,exist_ok=True)
        (runtime/"monet-editor").mkdir(mode=0o700,exist_ok=True)
        p=patch.dict(os.environ,{"XDG_RUNTIME_DIR":str(runtime)});p.start();self.addCleanup(p.stop)
        path=e.departure_path(APP,pid,self.saved["id"])
        receipt={"version":1,"id":self.saved["id"],"pid":pid,"app":APP,"supported":supported,"editor":editor}
        r.atomic_write(path,receipt)
        return path

    def test_private_receipts_keep_shared_instances_separate(self):
        r.arm_editor.return_value=True
        self.sessions[13]=""
        other=dict(self.window,pid=13,id="other")
        self.prepare();r.prepare_editor_close(self.path,self.saved["id"],other,[self.window,other])
        self.native_receipt(editor=state("/renamed-first.txt"))
        self.native_receipt(13,state("/first-save-second.txt"))
        self.source.write_text(native(["/wrong-shared-file.txt"]),encoding="utf-8")
        self.assertTrue(r.refresh_departure(self.path,self.saved["id"],[]))
        groups=r.read_state(self.path)["groups"][APP]
        self.assertEqual([e.paths(g["editor"]) for g in groups],[["/renamed-first.txt"],["/first-save-second.txt"]])
        self.assertFalse(any(g.get("final_unverified") for g in groups))

    def test_native_receipt_is_ignored_until_the_window_closes_and_disarmed_on_cancel(self):
        r.arm_editor.return_value=True;self.prepare()
        self.native_receipt(editor=state("/new.txt"))
        r.refresh_departure(self.path,self.saved["id"],[self.window])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])
        r.cancel_departure(self.path,self.saved["id"])
        r.arm_editor.assert_called_with(APP,12,self.saved["id"],False)
        self.assertNotIn("closing",self.group())

    def test_cancellation_inside_native_arm_disarms_the_late_watch(self):
        def arm(app,pid,ident,armed=True):
            if armed:r.cancel_departure(self.path,ident)
            return True
        r.arm_editor.side_effect=arm
        self.prepare()
        self.assertNotIn("closing",self.group())
        r.arm_editor.assert_called_with(APP,12,self.saved["id"],False)

    def test_native_unsupported_layout_retains_the_old_checkpoint_with_warning(self):
        r.arm_editor.return_value=True;self.prepare()
        self.native_receipt(supported=False)
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])
        self.assertTrue(self.group()["final_unverified"])

    def test_native_discarded_untitled_removes_stale_saved_paths(self):
        r.arm_editor.return_value=True;self.prepare();self.native_receipt()
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertIsNone(self.group()["editor"])

    def test_nested_final_receipt_keeps_new_paths_in_their_panes(self):
        from tests.test_editor_session import nested
        r.arm_editor.return_value=True;self.prepare()
        final=nested();final["views"][2]["documents"]=["/saved-as.txt"]
        path=self.native_receipt(editor=final)
        r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(self.group()["editor"],final)
        receipt=r.read_state(path);receipt["editor"]["layout"]["children"]=[0,0]
        r.atomic_write(path,receipt)
        with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])

    def test_native_missing_receipt_never_falls_back_to_another_instances_file(self):
        r.arm_editor.return_value=True;self.prepare()
        path=self.native_receipt();path.unlink()
        self.source.write_text(native(["/wrong-shared-file.txt"]),encoding="utf-8")
        self.assertFalse(r.refresh_departure(self.path,self.saved["id"],[]))
        with self.assertRaises(RuntimeError):r.refresh_departure(self.path,self.saved["id"],[],final=True)
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])

    def test_group_receipt_keeps_final_urls_and_empty_windows_with_exact_ids(self):
        path = self.native_receipt()
        receipt = r.read_state(path)
        receipt.pop("editor")
        receipt.update(version=2, windows=[
            {"id":"{12345678-1234-1234-1234-123456789abc}","editor":state("/renamed.txt")},
            {"id":"{87654321-1234-1234-1234-123456789abc}","editor":None}])
        r.atomic_write(path, receipt)
        self.assertEqual(e.departure(APP,12,self.saved["id"],windows=True),receipt)
        with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])
        bad = [dict(receipt, version=1), dict(receipt, supported=False), dict(receipt, windows=None),
               dict(receipt, windows=receipt["windows"][:1]*2), dict(receipt, editor=None)]
        private = copy.deepcopy(receipt)
        private["windows"][0]["editor"]["views"][0]["text"] = "unsaved contents"
        bad.append(private)
        for value in bad:
            r.atomic_write(path, value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                e.departure(APP,12,self.saved["id"],windows=True)

    def test_private_receipt_rejects_wrong_identity_unexpected_fields_and_public_files(self):
        path=self.native_receipt(editor=state("/new.txt"));good=r.read_state(path)
        for key,value in (("pid",13),("id","b"*32),("app","other.desktop"),("supported",1),("version",True),("text","secret")):
            receipt=dict(good);receipt[key]=value;r.atomic_write(path,receipt)
            with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])
        receipt=copy.deepcopy(good);receipt["editor"]["views"][0]["text"]="secret";r.atomic_write(path,receipt)
        with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])

        r.atomic_write(path,good);path.chmod(0o644)
        with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])
        target=path.with_suffix(".original");path.rename(target);path.symlink_to(target)
        with self.assertRaises(OSError):e.departure(APP,12,self.saved["id"])
        path.unlink();target.rename(path);path.parent.chmod(0o755)
        with self.assertRaises(ValueError):e.departure(APP,12,self.saved["id"])

    def test_cancel_removes_malformed_watches_without_sending_unknown_process_ids(self):
        for closing in ([1], {"native":True}, {"native":True,"pid":[]}, {"native":True,"pid":True}):
            saved=copy.deepcopy(self.saved);saved["groups"][APP][0]["closing"]=closing;r.atomic_write(self.path,saved)
            r.cancel_departure(self.path,self.saved["id"])
            self.assertNotIn("closing",self.group())
        r.arm_editor.assert_not_called()

    def test_native_file_replaced_during_read_never_commits_mixed_state(self):
        self.prepare();self.source.write_text(native(["/new.txt"]),encoding="utf-8")
        with patch.object(e,"native_stamp",side_effect=[[1,2,3,4],[4,3,2,1]]):
            with self.assertRaises(RuntimeError):r.refresh_departure(self.path,self.saved["id"],[])
        self.assertEqual(e.paths(self.group()["editor"]),["/old.txt"])
