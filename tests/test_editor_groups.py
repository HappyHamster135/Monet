"""Editor groups keep exact window ownership from departure through late-file retry."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_editor_session import APP, state, e
from tests.test_resume import r


def ident(n):
    return "{00000000-0000-0000-0000-%012d}" % n


@unittest.skipIf(os.name == "nt", "Linux editor recovery")
class EditorGroups(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path, self.off = self.root / "trip.json", self.root / "off"
        self.one, self.two = self.root / "one.txt", self.root / "two.txt"
        self.one.write_text("first", encoding="utf-8")
        self.two.write_text("second", encoding="utf-8")
        self.states = [{"id": ident(i), "editor": state(str(p))} for i, p in enumerate((self.one, self.two), 1)]
        self.frames = [{"app": APP, "pid": 12, "id": w["id"]} for w in reversed(self.states)]
        self.group = {"editor_windows": copy.deepcopy(self.states), "windows": self.frames}
        self.saved = {"version": 3, "id": "a" * 32, "time": 100, "boot": "old", "apps": [APP],
                      "windows": self.frames, "documents": {}, "groups": {APP: [self.group]}, "done": []}
        self.windows, self.live, self.launches, self.replacements = [], {}, [], {}
        for owner, name, kwargs in (
                (r, "boot_id", {"return_value": "new"}), (r.time, "sleep", {}),
                (r, "window_snapshot", {"side_effect": lambda: copy.deepcopy(self.windows)}),
                (r, "desktop_snapshot", {"return_value": {}}), (r, "restore_replacement_focus", {}),
                (r, "remember_placement", {}), (r, "editor_documents", {"return_value": []}),
                (e, "capture", {"side_effect": self.capture}), (e, "start", {"side_effect": self.start}),
                (e, "alive", {"side_effect": lambda receipt: receipt.get("pid") in self.live}),
                (e, "cleanup", {}), (r, "reopen_editor", {"side_effect": self.reopen}),
                (r, "replace_editor", {"return_value": None}),
                (r, "arm_editor", {"return_value": True}), (r, "disarm_editor", {})):
            p = patch.object(owner, name, **kwargs); p.start(); self.addCleanup(p.stop)
        r.atomic_write(self.path, self.saved)

    def capture(self, pid, cursors=None, *, windows=False):
        return copy.deepcopy(self.live.get(pid)) if windows else None

    def start(self, app, expected, *, windows=False):
        self.assertTrue(windows)
        pid = 20 + len(self.launches)
        self.launches.append(copy.deepcopy(expected))
        self.live[pid] = [dict(w, id=ident(pid * 100 + i)) for i, w in enumerate(copy.deepcopy(expected))]
        self.windows += [{"id": w["id"], "pid": pid, "app": app} for w in reversed(self.live[pid])]
        return {"pid": pid, "session": "kate_monet-" + "b" * 32 + "_"}

    def reopen(self, app, pid, target, paths, cursors=None, scrolls=None, selections=None, foldings=None):
        window = next(w for w in self.live[pid] if w["id"] == target)
        window["editor"] = state(*dict.fromkeys(e.paths(window["editor"]) + paths))
        return False  # A lost reply must be resolved by observing the exact target.

    def replace(self, app, pid, request):
        record = r.read_state(self.path)["groups"][APP][0]["editor_replacements"][ident(2)]
        self.assertEqual(record["request"], request)  # Persist the request before the native side can act.
        key = request.get("attempt", request["id"])
        if key not in self.replacements:
            new = ident(3000 + len(self.replacements))
            self.replacements[key] = new
            self.live[pid].append({"id": new, "editor": copy.deepcopy(request["editor"])})
            self.windows.append({"app": app, "pid": pid, "id": new})
        new = self.replacements[key]
        return new if any(w["id"] == new for w in self.live[pid]) else "closed"

    def missing_closed_window(self):
        self.two.unlink(); self.restore()
        self.two.write_text("returned", encoding="utf-8")
        self.windows = [w for w in self.windows if w["id"] != ident(2001)]
        self.live[20] = self.live[20][:1]
        r.replace_editor.side_effect = self.replace

    def restore(self, manual=False, before=None):
        return list(r.restore_editors(self.path, self.saved, APP, self.off,
                                     self.windows[:] if before is None else before, Mock(), manual))

    def prepare(self):
        self.saved["boot"] = "new"
        self.live[12], self.windows = self.states, self.frames
        r.atomic_write(self.path, self.saved)
        r.prepare_editor_close(self.path, self.saved["id"], self.frames[0], self.frames)

    def test_checkpoint_binds_native_order_to_exact_frames(self):
        self.live[12] = self.states
        saved = r.checkpoint([APP], self.frames)
        self.assertEqual(saved["groups"][APP][0]["editor_windows"], self.states)
        self.live[12][0]["id"] = ident(99)
        self.assertNotIn(APP, r.checkpoint([APP], self.frames).get("groups", {}))

    def test_save_as_receipt_updates_each_window_only_after_whole_group_closes(self):
        self.prepare()
        r.prepare_editor_close(self.path, self.saved["id"], self.frames[1], self.frames)
        r.arm_editor.assert_called_once_with(APP, 12, self.saved["id"], windows=True)
        final = copy.deepcopy(self.states)
        final[0]["editor"] = state(str(self.root / "renamed.txt"))
        final[1]["editor"] = state(str(self.root / "first-save.txt"))
        with patch.object(e, "departure", return_value={"windows": final}) as receipt:
            self.assertTrue(r.refresh_departure(self.path, self.saved["id"], self.frames[:1]))
            receipt.assert_not_called()
            self.assertTrue(r.refresh_departure(self.path, self.saved["id"], [], final=True))
            receipt.assert_called_once_with(APP, 12, self.saved["id"], windows=True)
        group = r.read_state(self.path)["groups"][APP][0]
        self.assertEqual(group["editor_windows"], final)
        self.assertNotIn("closing", group)

    def test_changed_group_or_wrong_final_ids_fail_without_rearming(self):
        self.prepare()
        with self.assertRaises(RuntimeError):
            r.prepare_editor_close(self.path, self.saved["id"], self.frames[0], self.frames[:1])
        r.arm_editor.assert_called_once()
        with patch.object(e, "departure", return_value={"windows": [dict(self.states[0], id=ident(99))]}), \
                self.assertRaises(ValueError):
            r.refresh_departure(self.path, self.saved["id"], [], final=True)
        self.assertIn("closing", r.read_state(self.path)["groups"][APP][0])

    def test_dialogs_are_ignored_and_cancellation_during_arm_disarms(self):
        dialog = dict(self.frames[0], id=ident(99), normal=False)
        r.prepare_editor_close(self.path, self.saved["id"], dialog, self.frames + [dialog])
        r.arm_editor.assert_not_called()
        self.saved["boot"] = "new"
        self.live[12], self.windows = self.states, self.frames
        r.atomic_write(self.path, self.saved)
        def cancel(*args, **kwargs):
            self.saved["cancelled_boot"] = "new"
            r.atomic_write(self.path, self.saved)
            return True
        r.arm_editor.side_effect = cancel
        r.prepare_editor_close(self.path, self.saved["id"], self.frames[0], self.frames + [dialog])
        r.disarm_editor.assert_called_once_with(APP, 12, self.saved["id"])
        self.assertNotIn("closing", r.read_state(self.path)["groups"][APP][0])

    def test_loss_of_previously_captured_identity_cancels_departure(self):
        self.saved["boot"] = "new"
        r.atomic_write(self.path, self.saved)
        with self.assertRaises(RuntimeError):
            r.prepare_editor_close(self.path, self.saved["id"], self.frames[0], self.frames)
        r.arm_editor.assert_not_called()
        self.assertNotIn("closing", r.read_state(self.path)["groups"][APP][0])

    def test_changed_membership_while_arming_disarms_before_cancelling(self):
        self.saved["boot"] = "new"
        self.live[12] = self.states
        self.windows = self.frames[:1]
        r.atomic_write(self.path, self.saved)
        with self.assertRaises(RuntimeError):
            r.prepare_editor_close(self.path, self.saved["id"], self.frames[0], self.frames)
        r.disarm_editor.assert_called_once_with(APP, 12, self.saved["id"])
        self.assertNotIn("closing", r.read_state(self.path)["groups"][APP][0])

    def test_native_order_maps_placement_even_when_kwin_order_is_reversed(self):
        self.restore()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.group["status"], "documents-opened")
        self.assertEqual(r.remember_placement.call_args.args[4],
                         {ident(1): ident(2000), ident(2): ident(2001)})
        self.assertEqual(r.editor_counts([self.group])["documents"], 2)
        self.restore(manual=True)
        self.assertEqual(len(self.launches), 1)

    def test_missing_window_placeholder_then_retry_targets_only_its_owner(self):
        self.two.unlink()
        self.restore()
        self.assertIsNone(self.launches[0][1]["editor"])
        self.assertEqual(self.group["status"], "documents-missing")
        self.assertEqual(r.editor_counts([self.group])["missing"], ["two.txt"])
        before = copy.deepcopy(self.live[20][0])
        self.two.write_text("returned", encoding="utf-8")
        self.restore()
        r.reopen_editor.assert_not_called()
        self.restore(manual=True)
        r.reopen_editor.assert_called_once_with(APP, 20, ident(2001), [str(self.two)], [42], [None], [None], [None])
        self.assertEqual(self.live[20][0], before)
        self.assertEqual(self.group["status"], "documents-opened")
        self.assertEqual(len(self.launches), 1)
        self.restore(manual=True)
        r.reopen_editor.assert_called_once()

    def test_all_missing_waits_but_intentionally_empty_windows_can_reopen(self):
        self.one.unlink(); self.two.unlink()
        self.restore()
        e.start.assert_not_called()
        self.assertEqual(self.group["status"], "documents-missing")
        self.group.pop("attempted"); self.group.pop("pending_windows")
        for window in self.group["editor_windows"]:
            window["editor"] = None
        self.restore()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.group["status"], "documents-opened")

    def test_interrupted_launch_is_reused_and_existing_windows_are_not_moved(self):
        job = r.restore_editors(self.path, self.saved, APP, self.off, [], Mock(), False)
        next(job)
        job.close()
        self.assertIn("editor_launch", self.group)
        before = self.windows[:]
        self.restore()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(r.remember_placement.call_args.args[3], {w["id"] for w in before})
        self.assertNotIn("editor_launch", self.group)

    def test_cancelled_switch_never_replays_over_surviving_buffers(self):
        self.saved["boot"] = "new"
        self.restore(before=self.frames)
        self.assertEqual(self.group["status"], "already-running")
        e.start.assert_not_called(); e.capture.assert_not_called()
        r.remember_placement.assert_not_called()

    def test_partial_survivor_is_not_reported_as_a_complete_group(self):
        self.saved["boot"] = "new"
        self.restore(before=self.frames[:1])
        self.assertEqual(self.group["status"], "unconfirmed")
        e.start.assert_not_called(); r.reopen_editor.assert_not_called()

    def test_matching_live_process_can_only_satisfy_one_saved_group(self):
        self.start(APP, self.states, windows=True)
        self.saved["groups"][APP].append(copy.deepcopy(self.group))
        self.restore()
        self.assertEqual([g["status"] for g in self.saved["groups"][APP]], ["already-running", "documents-opened"])
        self.assertEqual(len(self.launches), 2)

    def test_rejected_identity_and_closed_sibling_remain_pending(self):
        self.two.unlink(); self.restore()
        self.two.write_text("returned", encoding="utf-8")
        r.reopen_editor.side_effect = None; r.reopen_editor.return_value = False
        self.restore(manual=True)
        self.assertEqual(self.group["pending_windows"][ident(2)], [str(self.two)])
        self.windows = [w for w in self.windows if w["id"] != ident(2001)]
        self.live[20] = self.live[20][:1]
        r.reopen_editor.reset_mock()
        self.restore(manual=True)
        r.reopen_editor.assert_not_called()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.group["status"], "unconfirmed")

    def test_invalid_pending_or_owners_do_not_launch(self):
        for change in ({"pending_windows": {ident(1): ["/unrelated"]}},
                       {"editor_owners": {ident(1): {"boot": "new", "id": "ambiguous", "pid": 20}}},
                       {"windows": None}, {"windows": [dict(self.frames[0], id=[]), self.frames[1]]},
                       {"windows": [dict(self.frames[0], pid=True), self.frames[1]]},
                       {"editor_windows": [self.states[0]] * 2}):
            with self.subTest(change=change):
                old = copy.deepcopy(self.group)
                self.group.update(change)
                self.restore()
                e.start.assert_not_called()
                self.group.clear(); self.group.update(old)

    def test_disabling_during_capture_prevents_cursor_or_placement_changes(self):
        original = self.capture
        def disable(*args, **kwargs):
            self.off.touch()
            return original(*args, **kwargs)
        e.capture.side_effect = disable
        self.restore()
        r.remember_placement.assert_not_called()
        self.assertTrue(all(len(call.args) == 1 for call in e.capture.call_args_list))
        self.assertIn("editor_launch", self.group)

    def test_invalid_completed_group_cannot_confirm_recovery(self):
        self.group.update(status="documents-opened", pending_windows={"unrelated": []})
        job = r.restore_editors(self.path, self.saved, APP, self.off, [], Mock(), False)
        with self.assertRaises(StopIteration) as result:
            next(job)
        self.assertFalse(result.exception.value)
        e.start.assert_not_called()

    def test_closed_missing_window_reopens_in_its_existing_process(self):
        self.missing_closed_window()
        sibling = copy.deepcopy(self.live[20][0])
        self.restore()
        r.replace_editor.assert_not_called()
        self.restore(manual=True)
        self.assertEqual(self.group["status"], "documents-opened")
        self.assertEqual(self.group["editor_owners"][ident(2)], {"boot": "new", "pid": 20, "id": ident(3000)})
        self.assertEqual(self.live[20][0], sibling)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(r.remember_placement.call_args.args[4], {ident(2): ident(3000)})
        r.restore_replacement_focus.assert_called_once_with({}, ident(3000))
        self.restore(manual=True)
        r.replace_editor.assert_called_once()

    def test_uncertain_replacement_reply_reuses_the_same_native_request(self):
        self.missing_closed_window()
        def uncertain(*args):
            value = self.replace(*args)
            return None if r.replace_editor.call_count == 1 else value
        r.replace_editor.side_effect = uncertain
        self.restore(manual=True)
        self.assertEqual(len(self.live[20]), 2)
        self.assertEqual(r.replace_editor.call_count, 2)
        self.assertEqual(r.replace_editor.call_args_list[0], r.replace_editor.call_args_list[1])
        self.assertEqual(self.group["status"], "documents-opened")

    def test_interrupted_replacement_can_finish_automatically_without_moving_live_windows(self):
        self.missing_closed_window()
        job = r.restore_editors(self.path, self.saved, APP, self.off, self.windows[:], Mock(), True)
        next(job); job.close()
        self.assertTrue(self.group["editor_replacements"])
        r.remember_placement.reset_mock(); e.capture.reset_mock(); r.restore_replacement_focus.reset_mock()
        self.restore()
        self.assertEqual(len(self.live[20]), 2)
        self.assertFalse(self.group["editor_replacements"])
        self.assertEqual(self.group["status"], "documents-opened")
        r.remember_placement.assert_not_called()
        r.restore_replacement_focus.assert_not_called()
        self.assertTrue(all(len(call.args) == 1 for call in e.capture.call_args_list))

    def test_disabled_recovery_stops_after_dispatch_without_closing_or_moving_any_window(self):
        self.missing_closed_window()
        r.remember_placement.reset_mock()
        job = r.restore_editors(self.path, self.saved, APP, self.off, self.windows[:], Mock(), True)
        next(job); self.off.touch(); list(job)
        self.assertEqual(len(self.live[20]), 2)
        self.assertTrue(self.group["editor_replacements"])
        self.assertEqual(self.group["editor_owners"][ident(2)]["id"], ident(2001))
        r.remember_placement.assert_not_called()

    def test_closed_unconfirmed_attempt_waits_for_another_explicit_retry(self):
        self.missing_closed_window()
        job = r.restore_editors(self.path, self.saved, APP, self.off, self.windows[:], Mock(), True)
        next(job); job.close()
        first = copy.deepcopy(self.group["editor_replacements"][ident(2)]["request"])
        self.live[20] = self.live[20][:1]
        self.windows = [w for w in self.windows if w["id"] != ident(3000)]
        r.restore_replacement_focus.reset_mock(); r.remember_placement.reset_mock()
        self.restore()
        self.assertFalse(self.group["editor_replacements"])
        self.assertEqual(self.group["pending_windows"][ident(2)], [str(self.two)])
        self.assertEqual(len(self.live[20]), 1)
        r.restore_replacement_focus.assert_not_called(); r.remember_placement.assert_not_called()
        r.replace_editor.reset_mock()
        self.restore()
        r.replace_editor.assert_not_called()
        self.restore(manual=True)
        second = r.replace_editor.call_args.args[2]
        self.assertNotEqual(first["attempt"], second["attempt"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.live[20]), 2)
        self.assertEqual(self.group["status"], "documents-opened")

    def test_closed_reply_write_failure_replays_the_original_attempt(self):
        self.missing_closed_window()
        job = r.restore_editors(self.path, self.saved, APP, self.off, self.windows[:], Mock(), True)
        next(job); job.close()
        previous = self.path.read_bytes()
        self.live[20] = self.live[20][:1]
        self.windows = [w for w in self.windows if w["id"] != ident(3000)]
        with patch.object(r, "atomic_write", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.restore()
        self.assertEqual(self.path.read_bytes(), previous)
        self.saved = r.read_state(self.path)
        self.group = self.saved["groups"][APP][0]
        self.restore()
        self.assertEqual(len(self.replacements), 1)
        self.assertFalse(self.group["editor_replacements"])
        self.assertEqual(len(self.live[20]), 1)

    def test_missing_file_or_stale_owner_cannot_create_a_replacement(self):
        self.missing_closed_window()
        self.two.unlink(); self.restore(manual=True)
        r.replace_editor.assert_not_called()
        self.two.write_text("returned", encoding="utf-8")
        self.group["editor_owners"][ident(2)]["boot"] = "previous"
        self.restore(manual=True)
        r.replace_editor.assert_not_called()

    def test_bad_replacement_receipt_cannot_mutate_the_editor(self):
        self.missing_closed_window()
        self.group["editor_replacements"] = {ident(2): {"boot": "new", "pid": 20,
            "request": {"id": ident(2001), "anchor": ident(2000), "editor": state("/unrelated")}}}
        self.restore(manual=True)
        r.replace_editor.assert_not_called()
        self.assertEqual(len(self.live[20]), 1)

    def test_failed_receipt_write_prevents_native_window_creation(self):
        self.missing_closed_window()
        previous = self.path.read_bytes()
        with patch.object(r, "atomic_write", side_effect=OSError("checkpoint full")), self.assertRaises(OSError):
            self.restore(manual=True)
        r.replace_editor.assert_not_called()
        self.assertEqual(self.path.read_bytes(), previous)


class ExactPlacement(unittest.TestCase):
    def test_exact_identity_never_falls_back_to_title_or_role(self):
        rect = {"x": 0, "y": 0, "width": 800, "height": 600}
        old = [{"app": APP, "id": "old", "rect": rect}]
        current = [{"app": APP, "id": "wrong", "area": rect}]
        with patch.object(r, "kwin_script") as script:
            self.assertEqual(r.place_windows(old, current, set(), {"old": "absent"}), [])
            script.assert_not_called()
