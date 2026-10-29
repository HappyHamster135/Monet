"""Final PDF paths belong to exact windows, including surviving shared processes."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_resume import r


class PDFDeparture(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "trip.json"
        self.pdf = r.pdf_helper()
        self.ids = ["{11111111-2222-3333-4444-555555555555}", "{22222222-2222-3333-4444-555555555555}"]
        self.windows = [{"id": wid, "app": r.PDF, "pid": 12, "normal": True} for wid in self.ids]
        self.states = {wid: {"tabs": [{"path": "/saved-" + str(i) + ".pdf", "page": i+1, "modified": False}], "active": 0}
                       for i, wid in enumerate(self.ids)}
        self.saved = {"version": 3, "id": "a"*32, "boot": "same", "time": 100, "apps": [r.PDF],
                      "windows": self.windows, "documents": {}, "done": []}
        r.atomic_write(self.path, self.saved)
        for target, attribute, result in ((r, "boot_id", "same"), (r, "window_snapshot", self.windows),
                                           (self.pdf, "capture_windows", self.states), (self.pdf, "arm", True)):
            guard = patch.object(target, attribute, return_value=result)
            guard.start()
            self.addCleanup(guard.stop)

    def watch(self):
        r.prepare_pdf_close(self.path, self.saved["id"], self.windows[0], self.windows)

    def test_checkpoint_keeps_same_process_windows_separate(self):
        saved = r.checkpoint([r.PDF], self.windows)
        groups = saved["groups"][r.PDF]
        self.assertEqual([g["windows"] for g in groups], [[w] for w in self.windows])
        self.assertEqual([g["pdf"] for g in groups], list(self.states.values()))

    def test_each_process_is_armed_once_and_native_frames_are_kept(self):
        self.watch()
        self.watch()
        self.pdf.arm.assert_called_once_with(12, self.saved["id"])
        groups = r.read_state(self.path)["groups"][r.PDF]
        self.assertEqual([g["closing"]["window"] for g in groups], self.ids)
        self.assertTrue(all(g["closing"]["native"] for g in groups))

    def test_save_as_is_refreshed_when_only_one_shared_process_window_closes(self):
        self.watch()
        final = copy.deepcopy(self.states[self.ids[0]])
        final["tabs"][0]["path"] = "/renamed å.pdf"
        with patch.object(self.pdf, "departure", return_value={"supported": True, "document": final}) as read:
            self.assertTrue(r.refresh_departure(self.path, self.saved["id"], self.windows[1:]))
        read.assert_called_once_with(12, self.saved["id"], self.ids[0])
        groups = r.read_state(self.path)["groups"][r.PDF]
        self.assertEqual(groups[0]["pdf"], final)
        self.assertNotIn("closing", groups[0])
        self.assertEqual(groups[1]["pdf"], self.states[self.ids[1]])
        self.assertIn("closing", groups[1])
        self.assertTrue(r.cancel_departure(self.path, self.saved["id"]))
        self.pdf.arm.assert_called_with(12, self.saved["id"], False)
        groups = r.read_state(self.path)["groups"][r.PDF]
        self.assertNotIn("final_unverified", groups[0])
        self.assertTrue(groups[1]["final_unverified"])

    def test_cancel_during_arming_disarms_without_installing_a_late_watch(self):
        def arm(pid, ident, armed=True):
            if armed:
                r.cancel_departure(self.path, ident)
            return True
        self.pdf.arm.side_effect = arm
        self.watch()
        saved = r.read_state(self.path)
        self.assertEqual(saved["cancelled_boot"], "same")
        self.assertNotIn("groups", saved)
        self.assertEqual([call.args for call in self.pdf.arm.call_args_list], [(12, self.saved["id"]), (12, self.saved["id"], False)])

    def test_failed_final_read_preserves_the_last_checkpoint_and_vetoes_restart(self):
        self.watch()
        before = r.read_state(self.path)
        with patch.object(self.pdf, "departure", side_effect=FileNotFoundError):
            with self.assertRaises(RuntimeError):
                r.refresh_departure(self.path, self.saved["id"], [], final=True)
        self.assertEqual(r.read_state(self.path), before)

    def test_new_window_is_watched_without_erasing_already_closed_work(self):
        self.watch()
        with patch.object(self.pdf, "departure", return_value={"supported": True, "document": self.states[self.ids[0]]}):
            r.refresh_departure(self.path, self.saved["id"], self.windows[1:])
        added = dict(self.windows[0], id="{33333333-2222-3333-4444-555555555555}")
        current = [self.windows[1], added]
        latest = {self.ids[1]: self.states[self.ids[1]], added["id"]: {"tabs": [], "active": -1}}
        self.pdf.capture_windows.return_value = latest
        r.window_snapshot.return_value = current
        r.prepare_pdf_close(self.path, self.saved["id"], added, current)
        saved = r.read_state(self.path)
        self.assertEqual(len(saved["groups"][r.PDF]), 3)
        self.assertNotIn("closing", saved["groups"][r.PDF][0])
        self.assertEqual({w["id"] for w in saved["windows"]}, {*self.ids, added["id"]})

    def test_lost_identity_after_capture_is_not_silently_treated_as_unpatched(self):
        saved = r.checkpoint([r.PDF], self.windows)
        saved.update(id=self.saved["id"], boot="same")
        r.atomic_write(self.path, saved)
        self.pdf.capture_windows.return_value = {}
        with self.assertRaises(RuntimeError):
            self.watch()
        self.pdf.arm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
