"""Settings requests only the hardware used by the current page."""
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


class SettingsPolling(unittest.TestCase):
    def test_sound_does_not_probe_network_display_or_battery(self):
        q = quick_helper()
        with patch.object(q, "run", return_value="Volume: 0.40") as run:
            self.assertEqual(q.status("sound"), {"volume": 40, "mic": 40})
        self.assertEqual([call.args[:2] for call in run.call_args_list], [("wpctl", "get-volume"), ("wpctl", "get-volume")])

    def test_static_pages_do_no_hardware_queries(self):
        q = quick_helper()
        with patch.object(q, "run") as run, patch.object(q, "busjson") as bus:
            for page in ("about", "storage", "apps", "unrecognized"):
                self.assertEqual(q.status(page), {})
            run.assert_not_called(); bus.assert_not_called()

    def test_power_and_updates_retain_battery_state_without_other_queries(self):
        q = quick_helper()
        with patch.object(q, "busjson", return_value=[{"Percentage": 55, "State": 2}]) as bus, \
                patch.object(q, "battery_state", return_value={"battery": 55, "plugged": False}) as battery, \
                patch.object(q, "run") as run:
            for page in ("power", "updates"):
                self.assertEqual(q.status(page), {"battery": 55, "plugged": False})
            self.assertEqual(bus.call_count, 2); self.assertEqual(battery.call_count, 2)
            run.assert_not_called()

    def test_default_snapshot_still_has_every_quick_settings_field(self):
        q = quick_helper()
        with patch.object(q, "run", return_value=None):
            state = q.status()
        for field in ("wifi", "network", "bluetooth", "night", "quiet", "volume", "mic", "brightness", "keyboard", "battery", "light"):
            self.assertIn(field, state)

    def test_capacity_does_not_walk_home_or_start_disk_usage_commands(self):
        q = quick_helper()
        with patch.object(q, "du") as scan, patch.object(q, "run") as run:
            capacity = q.storage_capacity()
        self.assertGreater(capacity["total"], 0)
        self.assertFalse(capacity["measured"])
        self.assertIn("downloadsPath", capacity)
        scan.assert_not_called(); run.assert_not_called()
