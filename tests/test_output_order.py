"""Playback route identities, independent of transient PipeWire IDs."""
from collections import namedtuple
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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

    def test_speaker_limit_without_ranking_and_older_editors(self):
        with tempfile.TemporaryDirectory() as root, patch.object(order, "service") as service:
            path = Path(root) / "audio.json"
            initial = order.read(path)
            limited = dict(initial, headphoneLimitEnabled=True, headphoneLimit=0)
            self.assertEqual(order.save(path, limited, order.revision(initial)), "")
            service.assert_called_once_with(True)
            self.assertEqual(order.save(path, dict(enabled=False, devices=[device("Desk")]), order.revision(limited)), "")
            updated = order.read(path)
            self.assertTrue(updated["headphoneLimitEnabled"])
            self.assertEqual(updated["headphoneLimit"], 0)
            self.assertEqual(order.save(path, dict(updated, headphoneLimitEnabled=False), order.revision(updated)), "")
            service.assert_called_with(False)
            for value in (-1, 101, True, "20"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    order.validate(dict(limited, headphoneLimit=value))

    def test_wired_jack_and_separate_speaker_ports_on_one_sink(self):
        phones = SimpleNamespace(name="[Out] Headphones", available="yes")
        speakers = SimpleNamespace(name="[Out] Speaker", available="unknown")
        Volume = namedtuple("Volume", "values")
        sink = SimpleNamespace(name="card", index=2, proplist={"node.name": "alsa_output.card"},
                               volume=Volume([.7, .35]), port_active=phones, port_list=[phones, speakers])
        guard = order.SpeakerLimit(20)
        pulse = Mock()
        def observe(port):
            sink.port_active = port
            guard.update(pulse, order.available([sink]), sink.name)
        observe(phones)
        observe(speakers)
        pulse.volume_set.assert_not_called()  # Jack remains plugged after a manual selection.
        observe(phones)
        phones.available = "no"
        observe(speakers)
        limited = pulse.volume_set.call_args.args[1]
        self.assertAlmostEqual(limited.values[0], .2)
        self.assertAlmostEqual(limited.values[1], .1)
        phones.available = "yes"
        sink.volume = limited
        observe(phones)
        pulse.volume_set.assert_called_once()  # Never restore speaker volume onto the jack.

    def test_only_recognized_speakers_receive_the_limit(self):
        for port, props, kind in [
            ("[Out] HDMI1", {"device.icon_name": "audio-speakers"}, ""),
            ("analog-output-lineout", {"device.icon_name": "audio-speakers"}, ""),
            ("", {"device.description": "My headphones"}, ""),
            ("headphone-output", {"node.name": "bluez_output.test", "device.form_factor": "speaker"}, "speaker"),
            ("", {"device.icon_name": "audio-headset-bluetooth"}, "headphones"),
        ]:
            with self.subTest(port=port, props=props):
                sink = SimpleNamespace(proplist=props, port_active=SimpleNamespace(name=port) if port else None)
                self.assertEqual(order.output_kind(sink), kind)

    def test_stream_pinned_to_speakers_stays_quiet_after_reconnect(self):
        Volume = namedtuple("Volume", "values")
        def sink(name, kind, index, level):
            return SimpleNamespace(name=name, index=index, port_active=None, port_list=[],
                                   proplist={"node.name": name, "device.form_factor": kind}, volume=Volume([level]))
        speakers = sink("desk", "speaker", 2, .75)
        headphones = sink("usb", "headphone", 3, .5)
        pulse = Mock()
        guard = order.SpeakerLimit(0)
        both = order.available([speakers, headphones])
        guard.update(pulse, both, "usb")
        guard.update(pulse, order.available([]), "auto_null")
        guard.update(pulse, order.available([speakers]), "desk")
        speakers.volume = pulse.volume_set.call_args.args[1]
        self.assertEqual(speakers.volume.values, [0])
        pulse.sink_input_list.return_value = [SimpleNamespace(sink=2, corked=False)]
        guard.update(pulse, both, "usb")
        pulse.volume_set.assert_called_once()
