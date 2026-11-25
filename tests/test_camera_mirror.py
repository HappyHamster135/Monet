"""Exercise the camera mirror with video test patterns and a private screen locker."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("gi") and importlib.util.find_spec("PySide6")
                     and importlib.util.find_spec("dbus"), "requires Qt, GStreamer and D-Bus")
class CameraMirror(unittest.TestCase):
    def test_mirrored_frames_camera_changes_and_lock_release(self):
        with private_session() as env:
            env.update(QT_MEDIA_BACKEND="gstreamer", LP_NUM_THREADS="1")
            self.assertEqual(env.get("MONET_PASSWORDS_PRIVATE_BUS"), "1")
            with subprocess.Popen([sys.executable, str(ROOT / "tests/passwords_bus_fixture.py")],
                                  env=env, stdout=subprocess.PIPE, text=True) as locker:
                try:
                    self.assertEqual(locker.stdout.readline().strip(), "ready")
                    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/camera-mirror.py")],
                                   env=env, timeout=35, check=True)
                finally:
                    locker.terminate()
