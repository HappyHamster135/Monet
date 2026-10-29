"""Durable PDF return, exact-window retry and preservation of newer live work."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from tests.test_resume import r


class PDFReturn(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path, self.off = self.root / "trip.json", self.root / "off"
        self.present, self.late = self.root / "Present.pdf", self.root / "Late.pdf"
        self.present.touch()
        self.helper = r.pdf_helper()
        self.windows, self.states, self.launches, self.sessions, self.requests = [], {}, [], {}, {}
        self.state = {"tabs": [{"path": str(self.present), "page": 3, "modified": False},
                              {"path": str(self.late), "page": 2, "modified": False},
                              {"path": str(self.present), "page": 4, "modified": False}], "active": 2}
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root / "config"))
        env.start(); self.addCleanup(env.stop)
        for target, name, replacement in (
                (r, "boot_id", lambda: "new"), (r.time, "time", lambda: 110), (r.time, "sleep", lambda _: None),
                (r, "window_snapshot", lambda: copy.deepcopy(self.windows)), (r, "place_windows", lambda *a: []),
                (self.helper, "capture_windows", self.capture), (self.helper, "discover", self.discover),
                (self.helper, "launching", lambda _: False), (self.helper, "start", self.start),
                (self.helper, "append", self.append)):
            spy = patch.object(target, name, side_effect=replacement)
            spy.start(); self.addCleanup(spy.stop)

    def window(self, pid):
        return {"id": "{" + str(uuid.uuid4()) + "}", "pid": pid, "app": r.PDF, "normal": True}

    def save(self, states=None, boot="old"):
        self.groups = [{"pdf": copy.deepcopy(state), "windows": [self.window(10+i)]}
                       for i, state in enumerate(states or [self.state])]
        r.atomic_write(self.path, {"version": 3 if boot == "new" else 2, "id": uuid.uuid4().hex, "time": 100, "boot": boot,
            "cancelled_boot": "new" if boot == "new" else None, "apps": [r.PDF], "done": [], "groups": {r.PDF: self.groups}})

    def add_live(self, state, pid=88, frame=None):
        frame = frame or self.window(pid)
        self.windows.append(frame)
        self.states[frame["id"]] = copy.deepcopy(state)
        return frame

    def capture(self, pid, frames):
        return {w["id"]: copy.deepcopy(self.states[w["id"]]) for w in self.windows if w["pid"] == pid}

    def discover(self, receipt):
        pid = self.sessions.get(receipt.get("session"))
        return pid if any(w["pid"] == pid for w in self.windows) else None

    def start(self, receipt):
        stored = r.read_state(self.path)["groups"][r.PDF]
        self.assertTrue(any(g.get("pdf_launch") == receipt for g in stored), "Persist the launch identity before starting")
        self.launches.append(copy.deepcopy(receipt))
        pid = 100 + len(self.launches)
        self.sessions[receipt["session"]] = pid
        self.add_live(receipt["expected"], pid)
        return pid

    def append(self, pid, request):
        stored = r.read_state(self.path)["groups"][r.PDF]
        self.assertTrue(any(g.get("pdf_retry", {}).get("request") == request for g in stored))
        token = request["attempt"]
        if token not in self.requests:
            self.assertEqual(self.states[request["window"]], request["before"])
            self.states[request["window"]]["tabs"].append(copy.deepcopy(request["tab"]))
            self.requests[token] = copy.deepcopy(request)
        else:
            self.assertEqual(self.requests[token], request)
        return "opened"

    def restore(self, manual=False):
        return r.restore(self.path, self.off, lambda: [w["app"] for w in self.windows], lambda _: True,
                         lambda _: self.fail("Supported PDFs must use their private session"),
                         selected=r.PDF if manual else None)

    def test_available_duplicate_tabs_keep_late_file_pending_and_explicit_retry_preserves_newer_work(self):
        self.save()
        self.restore()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual([t["page"] for t in self.launches[0]["expected"]["tabs"]], [3, 4])
        group = r.read_state(self.path)["groups"][r.PDF][0]
        self.assertEqual(group["pending"], [1])
        report = r.read_return(self.path)["items"][r.PDF]
        self.assertEqual((report["documents"], report["missingCount"], report["status"]), (2, 1, "documents-missing"))
        current = self.states[self.windows[0]["id"]]
        current["tabs"][0].update(page=9, modified=True)
        current["active"] = 0
        self.late.touch()
        self.restore()
        self.assertEqual(len(current["tabs"]), 2)
        self.restore(manual=True)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(len(current["tabs"]), 3)
        self.assertEqual(current["tabs"][0], {"path": str(self.present), "page": 9, "modified": True})
        self.assertEqual(current["active"], 0)
        self.assertFalse(self.path.exists())
        self.restore(manual=True)
        self.assertEqual(len(self.requests), 1)

    def test_identical_siblings_get_independent_launches_and_reserve_manual_windows(self):
        self.late.touch()
        self.save([self.state, self.state, self.state])
        frame = self.add_live(dict(self.state, active=0))
        before = copy.deepcopy(self.states[frame["id"]])
        self.restore()
        self.assertEqual(len(self.launches), 2)
        self.assertEqual(len(self.windows), 3)
        self.assertEqual(self.states[frame["id"]], before)
        self.assertFalse(self.path.exists())

    def test_cancelled_original_window_keeps_newer_unsaved_tabs(self):
        self.save(boot="new")
        frame = self.add_live({"tabs": [{"path": str(self.late), "page": 1, "modified": True}], "active": 0}, frame=self.groups[0]["windows"][0])
        before = copy.deepcopy(self.states[frame["id"]])
        self.restore()
        self.assertEqual(self.states[frame["id"]], before)
        self.assertEqual(self.launches, [])
        self.assertEqual(r.read_return(self.path)["items"][r.PDF]["status"], "already-running")

    def test_interruption_after_start_before_confirmation_rediscovers_same_process(self):
        self.save()
        def interrupted(receipt):
            self.start(receipt)
            raise OSError("Controller lost its reply")
        with patch.object(self.helper, "start", side_effect=interrupted):
            self.restore()
        self.assertIn("pdf_launch", r.read_state(self.path)["groups"][r.PDF][0])
        self.states[self.windows[0]["id"]]["tabs"][0].update(page=17, modified=True)
        with patch.object(r, "place_windows") as place:
            self.restore()
            place.assert_not_called()
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.states[self.windows[0]["id"]]["tabs"][0]["page"], 17)
        self.assertEqual(r.read_state(self.path)["groups"][r.PDF][0]["pending"], [1])

    def test_pending_launch_lock_never_starts_another_process(self):
        self.save()
        with patch.object(self.helper, "launching", return_value=True), patch.object(self.helper, "start") as launch:
            self.restore()
            launch.assert_not_called()
        self.assertIn("pdf_launch", r.read_state(self.path)["groups"][r.PDF][0])

    def test_unconfirmed_window_closed_before_retry_is_not_automatically_resurrected(self):
        self.save()
        def interrupted(receipt):
            self.start(receipt)
            raise OSError("Lost launch reply")
        with patch.object(self.helper, "start", side_effect=interrupted):
            self.restore()
        self.windows.clear()
        self.restore()
        self.assertEqual(len(self.launches), 1)
        self.restore(manual=True)
        self.assertEqual(len(self.launches), 2)

    def test_lost_append_reply_reuses_persisted_attempt_across_controller_runs(self):
        self.save(); self.restore(); self.late.touch()
        def interrupted(pid, request):
            self.append(pid, request)
            raise OSError("Lost append result")
        with patch.object(self.helper, "append", side_effect=interrupted):
            self.restore(manual=True)
        pending = r.read_state(self.path)["groups"][r.PDF][0]["pdf_retry"]
        self.restore()
        self.assertEqual(list(self.requests), [pending["request"]["attempt"]])
        self.assertEqual(len(self.states[self.windows[0]["id"]]["tabs"]), 3)
        self.assertFalse(self.path.exists())

    def test_closed_recovered_tab_is_not_appended_again_after_lost_reply(self):
        self.save(); self.restore(); self.late.touch()
        def interrupted(pid, request):
            self.append(pid, request)
            raise OSError("Lost reply")
        with patch.object(self.helper, "append", side_effect=interrupted):
            self.restore(manual=True)
        self.states[self.windows[0]["id"]]["tabs"].pop()
        with patch.object(self.helper, "append", return_value="closed") as retry:
            self.restore()
            self.assertEqual(retry.call_count, 1)
        self.assertEqual(len(self.states[self.windows[0]["id"]]["tabs"]), 2)
        self.assertFalse(self.path.exists())

    def test_closed_owner_retry_only_opens_remaining_tabs_and_never_reuses_a_sibling(self):
        self.save([self.state, self.state]); self.restore()
        closed = self.windows.pop(0)
        sibling = self.windows[0]
        original = copy.deepcopy(self.states[sibling["id"]])
        self.late.touch()
        self.restore(manual=True)
        self.assertEqual(len(self.launches), 3)
        self.assertEqual(self.launches[-1]["expected"]["tabs"], [self.state["tabs"][1]])
        self.assertNotEqual(self.windows[-1]["id"], closed["id"])
        self.assertEqual(self.states[sibling["id"]]["tabs"][:2], original["tabs"])
        self.assertFalse(self.path.exists())

    def test_manually_reopened_missing_file_is_reused_after_owner_closed(self):
        self.save(); self.restore(); self.windows.clear(); self.late.touch()
        self.add_live({"tabs": [dict(self.state["tabs"][1], page=8, modified=True)], "active": 0})
        self.restore(manual=True)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.requests, {})
        self.assertFalse(self.path.exists())

    def test_failed_checkpoint_write_never_starts_a_private_session(self):
        self.save()
        original = r.atomic_write
        def write(path, state):
            if path == self.path and any(g.get("pdf_launch") for g in state.get("groups", {}).get(r.PDF, [])):
                raise OSError("Disk full")
            original(path, state)
        with patch.object(r, "atomic_write", side_effect=write), self.assertRaises(OSError):
            self.restore()
        self.assertEqual(self.launches, [])
        self.assertFalse(list((self.root / "config/session").glob("okular_monet-*")))

    def test_malformed_pending_and_retry_metadata_never_launch_or_append(self):
        for pending in ([True], [-1], [3], [1, 1], [2, 0]):
            self.save()
            data = r.read_state(self.path); data["groups"][r.PDF][0]["pending"] = pending
            r.atomic_write(self.path, data)
            self.restore(manual=True)
        self.assertEqual(self.launches, [])
        self.assertEqual(self.requests, {})

    def test_dismiss_cleans_private_launch_metadata_without_touching_documents(self):
        self.save()
        with patch.object(self.helper, "launching", return_value=True):
            self.restore()
        receipt = r.read_state(self.path)["groups"][r.PDF][0]["pdf_launch"]
        self.assertTrue(self.helper.session_path(receipt).exists())
        self.off.touch(); self.restore()
        self.assertFalse(self.helper.session_path(receipt).exists())
        self.assertTrue(self.present.exists())


if __name__ == "__main__":
    unittest.main()
