"""Run the placement script with real Wayland clients and a private compositor."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


@unittest.skipUnless(shutil.which("kwin_wayland"), "native KWin virtual compositor")
class WindowPlacement(unittest.TestCase):
    def test_app_placement_survives_close_reopen_and_monitor_changes(self):
        fixture = Path(__file__).with_name("fixtures") / "window-placement.py"
        subprocess.run([sys.executable, str(fixture)], check=True, timeout=75)
