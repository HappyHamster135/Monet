"""Playback choices use port availability and acknowledge the observed default."""
import json
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


class Playback(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.status = '''Audio
 ├─ Sinks:
 │      85. HDMI 3 [vol: 1.00]
 │  *   65. Speakers [vol: 0.60]
 │      73. USB headset [vol: 0.40]
 │      80. Dummy output [vol: 1.00]
 ├─ Sources:
'''

    def sink(self, ident, available, name="speakers"):
        return {"index": ident + 3000, "properties": {"object.id": str(ident), "node.name": name},
                "active_port": "output", "ports": [{"name": "output", "availability": available}]}

    def test_disconnected_ports_are_hidden_but_unknown_and_available_stay(self):
        metadata = [self.sink(85, "not available"), self.sink(65, "availability unknown"),
                    self.sink(73, "available"), self.sink(80, "unknown", "auto_null")]
        with patch.object(self.q, "run", side_effect=[self.status, json.dumps(metadata)]) as run:
            outputs = self.q.outputs()
        self.assertEqual([o["id"] for o in outputs], [65, 73, 80])
        self.assertTrue(outputs[0]["default"])
        self.assertFalse(outputs[0]["none"])
        self.assertTrue(outputs[2]["none"])
        self.assertEqual(run.call_count, 2)  # No per-device inspect processes.

    def test_port_names_are_used_and_shared_ones_also_name_the_device(self):
        status = '''Audio
 ├─ Sinks:
 │  *   65. Built-in Audio Analog Stereo [vol: 0.60]
 │      73. USB DAC Analog Stereo [vol: 0.40]
 │      85. Navi 21 HDMI/DP Audio Digital Stereo (HDMI) [vol: 1.00]
 ├─ Sources:
'''
        def sink(ident, port):
            return {"index": ident + 3000, "properties": {"object.id": str(ident), "node.name": f"sink{ident}"},
                    "active_port": "out", "ports": [{"name": "out", "description": port, "availability": "available"}]}
        metadata = [sink(65, "Analog Output"), sink(73, "Analog Output"), sink(85, "HDMI / DisplayPort")]
        with patch.object(self.q, "run", side_effect=[status, json.dumps(metadata)]):
            names = [o["name"] for o in self.q.outputs()]
        self.assertEqual(names, ["Speakers", "USB DAC", "Display audio"])

    def test_missing_or_malformed_metadata_keeps_wpctl_fallback(self):
        for raw in (None, "bad json", "{}", '[null, {"properties": null}]'):
            with self.subTest(raw=raw), patch.object(self.q, "run", side_effect=[
                    self.status, raw, "", "", "", 'node.name = "auto_null"']):
                outputs = self.q.outputs()
                self.assertEqual(len(outputs), 4)
                self.assertTrue(outputs[-1]["none"])

    def test_failed_or_unconfirmed_switch_does_not_claim_success(self):
        before = [{"id": 65, "none": False, "default": True},
                  {"id": 73, "none": False, "default": False}]
        after = [dict(o, default=o["id"] == 73) for o in before]
        # One that doesn't show is read again for a moment, then said: still there, or gone.
        for success, observed, expected, reads in ((True, after, {"ok": True}, 2),
                                                   (False, before, {"ok": False, "problem": "unchanged"}, 2),
                                                   (True, before, {"ok": False, "problem": "unchanged"}, 8),
                                                   (True, [], {"ok": False, "problem": "gone"}, 2)):
            with self.subTest(success=success, observed=observed), \
                    patch.object(self.q, "outputs", side_effect=[before] + [observed] * 8) as read, \
                    patch.object(self.q, "ok", return_value=success) as change, patch.object(self.q.time, "sleep") as wait:
                result = self.q.output_action(73)
                self.assertEqual(result, dict(expected, outputs=observed))
                change.assert_called_once_with("wpctl", "set-default", "73")
                self.assertEqual(read.call_count, reads)
                self.assertLessEqual(sum(call.args[0] for call in wait.call_args_list), 2)

    def test_removed_disconnected_or_dummy_output_cannot_be_selected(self):
        with patch.object(self.q, "outputs", return_value=[{"id": 80, "none": True, "default": True}]), \
                patch.object(self.q, "ok") as change:
            for ident in (85, 80, 999):
                self.assertFalse(self.q.output_action(ident)["ok"])
            change.assert_not_called()
