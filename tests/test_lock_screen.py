"""Exercise the current native locker API rather than checking QML strings."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(Path('/usr/libexec/kscreenlocker_greet').is_file(), 'native KDE greeter')
class LockScreen(unittest.TestCase):
    def test_clock_and_password_layouts_load_in_native_greeter(self):
        for width, height in ((1280, 800), (960, 540), (480, 800)):
            for mode in ('clock', 'prompt'):
                with self.subTest(width=width, height=height, mode=mode):
                    subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/lockscreen-native.py'),
                                    str(width), str(height), mode], check=True, timeout=20)
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/lockscreen-native.py'),
                        '960', '540', 'consent'], check=True, timeout=20)
