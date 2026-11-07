"""Brightness survives a new login without remembering dimming or HDR backlight."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'linux/share/monet'))
from monet_runtime.brightness import Memory


class BrightnessMemory(unittest.TestCase):
    def test_atomic_memory_and_changed_device_range_restore_same_percentage(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'monet/brightness.json'
            memory = Memory(path)
            self.assertIsNone(memory.target(1000))
            self.assertTrue(memory.remember(2700, 10000))
            memory.save()
            self.assertFalse(memory.dirty)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            restored = Memory(path)
            self.assertEqual(restored.target(400), 108)
            self.assertEqual(list(path.parent.iterdir()), [path])
            self.assertFalse(restored.remember(108, 400))

    def test_profile_dimming_restore_and_invalid_data_do_not_replace_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'brightness.json'
            memory = Memory(path); memory.remember(43, 100); memory.save()
            for context in ('profile_brightness', 'monet_restore'):
                self.assertFalse(memory.remember(100, 100, context))
                self.assertEqual(memory.target(100), 43)
            for value, maximum in [(True, 100), (100, 0), (-1, 100), (101, 100), (1, True), (2.5, 100)]:
                self.assertFalse(memory.remember(value, maximum))
                self.assertEqual(memory.target(100), 43)
            for content in ['broken', '[]', 'null', '{"version":1,"internal":true}',
                            '{"version":1,"internal":NaN}', '{"version":1,"internal":2}']:
                path.write_text(content)
                self.assertIsNone(Memory(path).target(100))

    @unittest.skipUnless(sys.platform == 'linux' and importlib.util.find_spec('gi'), 'Linux GLib D-Bus')
    def test_private_native_brightness_keys_slider_new_login_and_late_power_service(self):
        from tools.test import private_session
        with private_session() as env:
            result = subprocess.run([sys.executable, str(ROOT/'tests/fixtures/brightness-native.py')],
                                    env=env, capture_output=True, text=True, timeout=35)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('BRIGHTNESS_MEMORY_OK', result.stdout)
