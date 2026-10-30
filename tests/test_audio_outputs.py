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
        for success, observed, expected in ((True, after, True), (False, before, False),
                                            (True, before, False), (True, [], False)):
            with self.subTest(success=success, observed=observed), \
                    patch.object(self.q, "outputs", side_effect=[before, observed]), \
                    patch.object(self.q, "ok", return_value=success) as change:
                result = self.q.output_action(73)
                self.assertEqual(result, {"ok": expected, "outputs": observed})
                change.assert_called_once_with("wpctl", "set-default", "73")

    def test_removed_disconnected_or_dummy_output_cannot_be_selected(self):
        with patch.object(self.q, "outputs", return_value=[{"id": 80, "none": True, "default": True}]), \
                patch.object(self.q, "ok") as change:
            for ident in (85, 80, 999):
                self.assertFalse(self.q.output_action(ident)["ok"])
            change.assert_not_called()
