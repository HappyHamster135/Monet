"""A confirmed Windows trip, not elapsed wall time, owns its recovery checkpoint."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r
from tests.test_look import quick_helper


class TripLifetime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trip-apps.json"
        self.off = self.path.with_name("off")
        self.receipt = self.path.with_name("system-return.json")
        self.state = {"version": 3, "id": "a" * 32, "time": 100, "boot": "departure",
                      "apps": ["a.desktop", "b.desktop"], "windows": [], "done": []}
        self.confirmed = {"id": self.state["id"], "boot": "departure", "returned_boot": "return"}
        r.atomic_write(self.path, self.state)
        r.atomic_write(self.receipt, self.confirmed)
        for owner, name, value in ((r, "boot_id", "return"), (r, "window_snapshot", []),
                                   (r.time, "time", 30 * 86400), (r.time, "sleep", None)):
            p = patch.object(owner, name, return_value=value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(r, "TRIP_RETURN", self.receipt)
        p.start(); self.addCleanup(p.stop)

    def test_confirmed_trip_survives_long_absence_and_clock_changes(self):
        for now in (0, 100, 13 * 3600, 30 * 86400):
            self.assertTrue(r.usable(self.state, now, "return", 12 * 3600))
        self.assertFalse(r.usable(self.state, 110, "departure", 12 * 3600))
        self.assertFalse(r.usable(self.state, 110, "", 12 * 3600))

    def test_nearby_or_cancelled_trips_and_malformed_receipts_cannot_replay(self):
        for receipt in ({}, dict(self.confirmed, id="b" * 32), dict(self.confirmed, boot="other"),
                        dict(self.confirmed, returned_boot="departure"),
                        dict(self.confirmed, returned_boot=""), dict(self.confirmed, returned_boot=[])):
            r.atomic_write(self.receipt, receipt)
            self.assertFalse(r.usable(self.state, 110, "return", 12 * 3600))
        self.receipt.write_text("broken")
        self.assertFalse(r.usable(self.state, 110, "return", 12 * 3600))
        self.receipt.unlink()
        self.assertFalse(r.usable(self.state, 110, "return", 12 * 3600))

    def test_confirmation_does_not_bypass_checkpoint_validation(self):
        for bad in (dict(self.state, time=True), dict(self.state, time=float("nan")),
                    dict(self.state, apps="a.desktop"), dict(self.state, boot=""),
                    dict(self.state, id=[]), dict(self.state, version=99)):
            self.assertFalse(r.usable(bad, 110, "return", 12 * 3600))

    @unittest.skipIf(os.name == "nt", "Linux restore lock")
    def test_partial_return_keeps_its_receipt_across_other_trips_and_reboots(self):
        launch = Mock()
        r.window_snapshot.side_effect = [[], [{"app": "a.desktop", "id": "new-a"}]]
        result = r.restore(self.path, self.off, lambda: [], lambda app: app == "a.desktop", launch)
        self.assertEqual(result, ["a.desktop"])
        self.assertEqual(r.read_state(self.path)["trip_return"], self.confirmed)
        r.atomic_write(self.receipt, dict(self.confirmed, id="b" * 32))
        r.boot_id.return_value = "later-boot"
        r.time.time.return_value = 60 * 86400
        status = r.return_status(self.path, self.off)
        self.assertFalse(status["items"][0]["retry"])
        self.assertTrue(status["items"][1]["retry"])
        r.window_snapshot.side_effect = [[], [{"app": "b.desktop", "id": "new-b"}]]
        self.assertEqual(r.restore(self.path, self.off, lambda: [], lambda _: True, launch), ["b.desktop"])
        self.assertEqual([call.args[0] for call in launch.call_args_list], ["a.desktop", "b.desktop"])
        self.assertFalse(self.path.exists())

    @unittest.skipIf(os.name == "nt", "Linux restore lock")
    def test_delayed_confirmation_preserves_work_then_allows_retry(self):
        self.receipt.unlink()
        launch = Mock()
        self.assertEqual(r.restore(self.path, self.off, lambda: [], lambda _: True, launch), [])
        launch.assert_not_called()
        self.assertTrue(self.path.exists())
        status = r.return_status(self.path, self.off)
        self.assertEqual(status["items"][0]["status"], "trip-unconfirmed")
        self.assertFalse(status["retry"])
        q = quick_helper()
        with patch.object(q, "resume_helper", return_value=r), patch.object(q, "TRIP_APPS", self.path), \
                patch.object(q, "TRIP_APPS_OFF", self.off), patch.object(q, "return_worker_active", return_value=False), \
                patch.object(q, "entry_by_id", return_value={}):
            self.assertTrue(q.return_status()["items"][0]["needsAttention"])
        r.atomic_write(self.receipt, self.confirmed)
        self.assertTrue(r.return_status(self.path, self.off)["retry"])

    @unittest.skipIf(os.name == "nt", "Linux restore lock")
    def test_off_and_dismiss_still_forget_a_long_trip(self):
        r.save_return(self.path, self.state, r.initial_return(self.state))
        self.assertTrue(r.clear_return(self.path, self.off, self.state["id"]))
        self.assertTrue(self.receipt.exists())
        r.atomic_write(self.path, self.state)
        self.off.touch()
        launch = Mock()
        r.restore(self.path, self.off, lambda: [], lambda _: True, launch)
        launch.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_live_capture_prints_the_exact_saved_id_even_without_kwin_windows(self):
        q = quick_helper()
        with patch.object(q, "TRIP_APPS", self.path), patch.object(q, "TRIP_APPS_OFF", self.off), \
                patch.object(q, "resume_helper", return_value=r), \
                patch.object(r, "desktop_snapshot", return_value={}), \
                patch.object(q, "running_apps", return_value=["a.desktop"]), \
                patch.object(q, "entry_by_id", return_value={"Type": "Application"}), \
                patch.object(q, "starts_anyway", return_value=False):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(q.remember_apps(), ["a.desktop"])
            saved = r.read_state(self.path)
            self.assertEqual(saved["version"], 3)
            self.assertEqual(output.getvalue().strip(), saved["id"])
            self.assertEqual(saved["boot"], "return")
            self.assertFalse(r.usable(saved, 110, "later", 12 * 3600))
            self.off.touch()
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(q.remember_apps(), [])
            self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
