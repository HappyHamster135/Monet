"""On the NVIDIA image Bazzite checked the Flatpak NVIDIA runtimes while the PC
started, 7 s of the boot on a ThinkPad. Monet runs that check 30 s after startup."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "image/nvidia-flatpak"
SYNC = "ublue-nvidia-flatpak-runtime-sync.service"
VERIFY = "ublue-nvidia-flatpak-runtime-verify.service"


class NvidiaFlatpakAfterStartup(unittest.TestCase):
    def install(self, services):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name) / "root"
        units = root / "usr/lib/systemd/system"
        units.mkdir(parents=True)
        for name in services:
            (units / name).write_text("[Service]\nType=oneshot\n")
        bin_dir = Path(folder.name) / "bin"
        bin_dir.mkdir()
        calls = Path(folder.name) / "calls"
        (bin_dir / "systemctl").write_text('#!/bin/sh\necho "$@" >> "%s"\n' % calls)
        (bin_dir / "systemctl").chmod(0o755)
        done = subprocess.run(["bash", str(FOLDER / "install.sh"), str(root)], capture_output=True, text=True,
                              env=dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}"), timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return units, calls.read_text().splitlines() if calls.exists() else []

    def test_the_check_moves_behind_a_timer(self):
        units, calls = self.install([SYNC, VERIFY])
        root = str(units.parents[3])
        self.assertEqual(calls, [f"--root={root} disable {SYNC} {VERIFY}",
                                 f"--root={root} enable monet-nvidia-flatpak.timer"])
        timer = (units / "monet-nvidia-flatpak.timer").read_text()
        self.assertIn("OnBootSec=30s", timer)
        self.assertIn(f"Unit={VERIFY}", timer)
        self.assertIn("WantedBy=timers.target", timer)
        # The check brings the sync with it, and waits for it.
        dropin = (units / f"{VERIFY}.d/10-monet-sync.conf").read_text()
        self.assertIn(f"Wants={SYNC}", dropin)
        self.assertIn(f"After={SYNC}", dropin)

    def test_nothing_changes_without_the_nvidia_services(self):
        # The AMD/Intel image is built from the same Containerfile.
        units, calls = self.install([])
        self.assertEqual(calls, [])
        self.assertEqual(list(units.iterdir()), [])

    def test_the_image_runs_it(self):
        image = (ROOT / "image/Containerfile").read_text()
        self.assertIn("--mount=type=bind,source=image/nvidia-flatpak,target=/tmp/monet-nvidia-flatpak,ro", image)
        self.assertIn("&& bash /tmp/monet-nvidia-flatpak/install.sh \\", image)


if __name__ == "__main__":
    unittest.main()
