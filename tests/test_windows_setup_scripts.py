"""Run setup behavior fixtures on Linux PowerShell and Windows PowerShell CI."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = os.environ.get("MONET_TEST_POWERSHELL") or shutil.which("pwsh") or shutil.which("powershell")


class WindowsSetupScripts(unittest.TestCase):
    @unittest.skipUnless(POWERSHELL, "PowerShell runtime not installed")
    def test_setup_behaviors(self):
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-File", str(ROOT / "tests/windows_setup.tests.ps1")],
            cwd=ROOT, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PowerShell setup checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
