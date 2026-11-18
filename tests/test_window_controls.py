"""Check restored geometry against KWin, including its transient Wayland states."""
import importlib.util
import json
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
    def test_restore_preserves_geometry_and_close_reaches_the_screen_corner(self):
        with tempfile.TemporaryDirectory(prefix="monet-window-controls-") as folder:
            output = Path(folder)
            run = subprocess.run([sys.executable, str(ROOT / "tests/fixtures/window-controls-wayland.py"), folder],
                                 capture_output=True, text=True, timeout=100)
            log = output / "kwin.log"
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr + (log.read_text()[-16000:] if log.exists() else ""))
            result = json.loads((output / "result.json").read_text())
            self.assertTrue(result["ok"])
            self.assertTrue(result["corner_close"])
            self.assertEqual([record["mode"] for record in result["records"]], ["windowed", "maximized", "fullscreen"])
            for record in result["records"]:
                self.assertFalse(record["compositor"]["minimized"])
                self.assertEqual(record["page"], "sound")
                if record["mode"] != "windowed":
                    self.assertEqual(record["compositor"]["frame"][2:], record["available"])


if __name__ == "__main__":
    unittest.main()
