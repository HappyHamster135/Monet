"""Playback route identities, independent of transient PipeWire IDs."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet"))
from monet_runtime import output_order as order


def device(name, port=""):
    return {"name": name, "key": name.encode().hex(), "port": port}


class OutputOrder(unittest.TestCase):
    def test_jack_and_speakers_have_separate_priorities_bluetooth_profiles_reconnect(self):
        def sink(node, port="", availability="unknown"):
            active = SimpleNamespace(name=port, available=availability) if port else None
            return SimpleNamespace(proplist={"node.name": node}, port_active=active)
        speaker = sink("alsa_output.laptop", "speaker")
        jack = sink("alsa_output.laptop", "headphones", "no")
        headset = sink("bluez_output.AA_BB_CC_DD_EE_FF.1", "headset-output")
        found = order.available([speaker, jack, headset, sink("auto_null")])
        self.assertEqual(len(found), 2)
        self.assertEqual(found[order.route(speaker.proplist, "speaker")], [speaker])
        jack.port_active.available = "yes"
        self.assertIn(order.route(jack.proplist, "headphones"), order.available([jack]))
        new = sink("bluez_output.AA_BB_CC_DD_EE_FF.2", "handsfree-output")
        self.assertEqual(order.available([headset]).keys(), order.available([new]).keys())

    def test_saves_order_and_disabled_choices_and_rejects_stale_edits(self):
        with tempfile.TemporaryDirectory() as root, patch.object(order, "service") as service:
            path = Path(root) / "prefs.json"
            initial = order.read(path)
            choices = dict(enabled=True, devices=[device("Headset"), device("Speakers")])
            self.assertEqual(order.save(path, choices, order.revision(initial)), "")
            service.assert_called_once_with(True)
            self.assertEqual(order.read(path), choices)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(order.save(path, initial, order.revision(initial)), "changed")
            disabled = dict(choices, enabled=False)
            self.assertEqual(order.save(path, disabled, order.revision(choices)), "")
            service.assert_called_with(False)
            self.assertEqual(order.read(path), disabled)
            with self.assertRaises(ValueError):
                order.save(path, dict(enabled=True, devices=[]), order.revision(disabled))
            with self.assertRaises(ValueError):
                order.validate(dict(enabled=True, devices=[device("Same"), device("Same")]))

    def test_service_failure_restores_last_saved_settings(self):
        with tempfile.TemporaryDirectory() as root, patch.object(order, "service", side_effect=[OSError(), None]) as service:
            path = Path(root) / "prefs.json"
            old = order.read(path)
            self.assertEqual(order.save(path, dict(enabled=True, devices=[device("Speakers")]), order.revision(old)), "service")
            self.assertEqual(order.read(path), old)
            self.assertEqual([c.args[0] for c in service.call_args_list], [True, False])
