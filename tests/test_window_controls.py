"""Check restored geometry against KWin, including its transient Wayland states."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (importlib.util.find_spec("PySide6") is not None
          and shutil.which("kwin_wayland") and Path("/dev/udmabuf").exists())


@unittest.skipUnless(NATIVE, "requires the private KWin runtime and udmabuf")
class WaylandControls(unittest.TestCase):
    def test_settings_restore_and_screen_corner(self):
        self.exercise("settings")

    def test_store_fills_a_portrait_screen_and_restores_without_shrinking(self):
        self.exercise("store")

    def exercise(self, kind):
        with tempfile.TemporaryDirectory(prefix="monet-window-controls-") as folder:
            output = Path(folder)
            run = subprocess.run([sys.executable, str(ROOT / "tests/fixtures/window-controls-wayland.py"), folder, kind],
                                 capture_output=True, text=True, timeout=100)
            log = output / "kwin.log"
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr + (log.read_text()[-16000:] if log.exists() else ""))
            result = json.loads((output / "result.json").read_text())
            self.assertTrue(result["ok"])
            self.assertTrue(result["corner_close"])
            self.assertEqual([record["mode"] for record in result["records"]], ["windowed", "maximized", "fullscreen"])
            for record in result["records"]:
                self.assertFalse(record["compositor"]["minimized"])
                self.assertEqual(record["page"], "games" if kind == "store" else "sound")
                if record["mode"] != "windowed":
                    self.assertEqual(record["compositor"]["frame"][2:], record["available"])


@unittest.skipUnless(NATIVE and os.environ.get("MONET_TITLE_NATIVE"), "requires the candidate native title-bar bridge")
class NativeTitleGrabs(unittest.TestCase):
    def test_repeated_wayland_and_xwayland_grabs_restore_and_snap(self):
        with tempfile.TemporaryDirectory(prefix="monet-title-grabs-") as folder:
            output = Path(folder)
            run = subprocess.run([sys.executable, str(ROOT / "tests/fixtures/title-drag-wayland.py"), folder],
                                 capture_output=True, text=True, timeout=110)
            log = output / "kwin.log"
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr + (log.read_text()[-16000:] if log.exists() else ""))
            result = json.loads((output / "result.json").read_text())
            self.assertTrue(result["ok"])
            self.assertEqual(len(result["drags"]), 12)
            self.assertEqual(len(result["closes"]), 12)
            self.assertEqual({record["platform"] for record in result["drags"]}, {"wayland", "xcb"})
            self.assertTrue(result["quick_release"])
            self.assertTrue(result["restored_and_snapped"])


if __name__ == "__main__":
    unittest.main()
