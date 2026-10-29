"""Capture controls never claim a mute/unmute succeeded without reading it back."""
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


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


if __name__ == "__main__":
    unittest.main()
