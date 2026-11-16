"""Capture controls never claim a mute/unmute succeeded without reading it back."""
from pathlib import Path
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


class BarMicrophone(unittest.TestCase):
    def setUp(self):
        self.quick = quick_helper()

    def test_audio_sources_exclude_video_and_preserve_default_and_names(self):
        found = self.quick.microphones('''Audio
 ├─ Sinks:
 │  *   52. Speakers [vol: 0.60]
 ├─ Sources:
 │  *   57. USB microphone [vol: 0.80 MUTED]
 │      60. Headset [vol: 0.40]
 ├─ Filters:
 │      65. capture stream [Stream/Input/Audio]
 │      67. Noise reduced microphone [Audio/Source]
Video
 ├─ Sources:
 │  *   71. Camera
Settings
''')
        self.assertEqual(found, [{"id": 57, "name": "USB microphone", "default": True},
                                 {"id": 60, "name": "Headset", "default": False},
                                 {"id": 67, "name": "Noise reduced microphone", "default": False}])

    def test_sound_reads_muted_state_from_selected_device_and_handles_unplug(self):
        source = {"id": 57, "name": "Microphone", "default": True}
        with patch.object(self.quick, "outputs", return_value=[]), patch.object(self.quick, "apps_sound", return_value=[]), \
             patch.object(self.quick, "microphones", return_value=[source]), \
             patch.object(self.quick, "run", return_value="Volume: 0.80 [MUTED]"):
            self.assertEqual(self.quick.bar_sound()["microphone"], dict(source, volume=80, muted=True))
        with patch.object(self.quick, "run", return_value=None):
            self.assertIsNone(self.quick.bar_sound()["microphone"])

    def test_success_failure_and_default_change_do_not_report_false_mute(self):
        old = {"microphone": {"id": 57, "muted": False}}
        muted = {"microphone": {"id": 57, "muted": True}}
        with patch.object(self.quick, "bar_sound", side_effect=[old, muted]), patch.object(self.quick, "ok", return_value=True) as change:
            self.assertTrue(self.quick.microphone_action("mute", "on", 57)["ok"])
            change.assert_called_once_with("wpctl", "set-mute", "57", "1")
        with patch.object(self.quick, "bar_sound", return_value=old), patch.object(self.quick, "ok", return_value=False):
            self.assertFalse(self.quick.microphone_action("mute", "on", 57)["ok"])
        with patch.object(self.quick, "bar_sound", return_value=old), patch.object(self.quick, "ok") as change:
            self.assertFalse(self.quick.microphone_action("mute", "off", 60)["ok"])
            change.assert_not_called()  # The headset changed since the UI was drawn.

    def test_unknown_input_id_cannot_change_a_speaker_default(self):
        with patch.object(self.quick, "microphones", return_value=[{"id": 57}]), \
             patch.object(self.quick, "bar_sound", return_value={}), patch.object(self.quick, "run", return_value=""), \
             patch.object(self.quick, "ok") as change:
            self.assertFalse(self.quick.microphone_action("input", "52")["ok"])
            change.assert_not_called()

    def test_disconnected_port_is_not_listed_or_selectable(self):
        nodes = [{"id": 64, "name": "Stereo Microphone", "default": False},
                 {"id": 65, "name": "Digital Microphone", "default": True},
                 {"id": 67, "name": "Virtual Microphone", "default": False}]
        ports = {64: {"active_port": "Mic2", "ports": [{"name": "Mic2", "availability": "not available"}]},
                 65: {"active_port": "Mic1", "ports": [{"name": "Mic1", "availability": "availability unknown"}]}}
        with patch.object(self.quick, "microphones", return_value=nodes), \
             patch.object(self.quick, "pulse_nodes", return_value=ports), \
             patch.object(self.quick, "bar_sound", return_value={}), patch.object(self.quick, "run", return_value=""), \
             patch.object(self.quick, "ok") as change:
            self.assertEqual(self.quick.available_microphones(), nodes[1:])
            self.assertFalse(self.quick.microphone_action("input", "64")["ok"])
            change.assert_not_called()


    # A Scarlett 2i2 as WirePlumber lists it: each input a source of its own (shown under Filters,
    # by its internal name) and the hidden source of both inputs, which WirePlumber names after the card.
    SCARLETT = """Audio
 ├─ Sources:
 │  *   71. Focusrite Scarlett 2i2 2nd Gen 0    [vol: 1.00]
 │      80. DualSense wireless controller (PS5) Direct DualSense Wireless Controller [vol: 1.00]
 │
 ├─ Filters:
 │  *   74. alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic1__source [Audio/Source]
 │      76. alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic2__source [Audio/Source]
 │
 └─ Streams:
"""
    HW = "alsa_input.hw_USB_0"

    def split(self, ident, number, description=""):
        return {"description": description, "properties": {
            "node.name": "alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic%d__source" % number,
            "media.class": "Audio/Source", "api.alsa.split.position": "[AUX%d]" % (number - 1),
            "api.alsa.split.name": self.HW}}

    def test_an_interface_is_listed_once_for_each_input_by_name(self):
        metadata = {74: self.split(74, 1), 76: self.split(76, 2),
                    71: {"description": "Focusrite Scarlett 2i2 2nd Gen 0", "properties": {
                        "node.name": self.HW, "media.class": "Audio/Source/Internal", "api.alsa.split.parent": "true"}},
                    80: {"description": "DualSense wireless controller (PS5) Direct DualSense Wireless Controller",
                         "properties": {"node.name": "alsa_input.usb-Sony_DualSense-00.direct"}}}
        with patch.object(self.quick, "run", return_value=self.SCARLETT), patch.object(self.quick, "pulse_nodes", return_value=metadata):
            found = self.quick.available_microphones()
        self.assertEqual([(m["id"], m["name"], m["default"]) for m in found], [
            (80, "DualSense wireless controller (PS5)", False),  # not its name twice
            (74, "Focusrite Scarlett 2i2 USB · Input 1", True),
            (76, "Focusrite Scarlett 2i2 USB · Input 2", False)])

    def test_an_input_keeps_its_own_description_and_says_which_input(self):
        metadata = {74: self.split(74, 1, "Scarlett 2i2 USB Mic1"), 76: self.split(76, 2, "Scarlett 2i2 USB Input 2"),
                    80: {"description": "DualSense", "properties": {}}}
        # The hidden source isn't in Pulse's list: wpctl says what it is, and it's left out by name.
        def run(*args, **kwargs):
            return self.SCARLETT if args[1] == "status" else '  * node.name = "%s"\n    media.class = "Audio/Source"\n' % self.HW
        with patch.object(self.quick, "run", side_effect=run), patch.object(self.quick, "pulse_nodes", return_value=metadata):
            found = self.quick.available_microphones()
        self.assertEqual([m["name"] for m in found], ["DualSense", "Scarlett 2i2 USB Mic1 · Input 1", "Scarlett 2i2 USB Input 2"])

    def test_the_settings_page_chooses_the_microphone(self):
        settings = (ROOT / "linux/share/monet/settings-app/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('ask("input " + input.id + deviceKey(input), (out, code) => {', settings)
        self.assertIn('onTapped: sheet.pickMicrophone(modelData)', settings)
        self.assertIn('ask("microphones", out =>', settings)
        with patch.object(self.quick, "available_microphones", return_value=[{"id": 1, "name": "Mic", "default": True}]), \
                patch("builtins.print") as said:
            self.quick.main(["microphones"])
        self.assertEqual(said.call_args.args[0], '[{"id": 1, "name": "Mic", "default": true}]')


if __name__ == "__main__":
    unittest.main()
