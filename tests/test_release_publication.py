"""Publishing may update rolling images without replacing a released version."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImagePublication(unittest.TestCase):
    def publish(self, git_status, push_status=0):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, script in {
                "git": '#!/bin/sh\nexit "$GIT_STATUS"\n',
                "sudo": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\nexit "$PUSH_STATUS"\n',
            }.items():
                path = root / name
                path.write_text(script)
                path.chmod(0o700)
            calls = root / "calls"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       GIT_STATUS=str(git_status), PUSH_STATUS=str(push_status), CALLS=str(calls))
            result = subprocess.run(["bash", str(ROOT / "tools/push-image.sh"),
                                     "ghcr.io/example/monet", "0.9.6"],
                                    env=env, capture_output=True, text=True, timeout=10)
            return result.returncode, calls.read_text().splitlines() if calls.exists() else []

    def test_released_version_is_never_overwritten(self):
        self.assertEqual(self.publish(0), (0, ["podman push ghcr.io/example/monet:latest"]))

    def test_new_version_precedes_rolling_update(self):
        self.assertEqual(self.publish(2), (0, ["podman push ghcr.io/example/monet:0.9.6",
                                              "podman push ghcr.io/example/monet:latest"]))

    def test_remote_failure_publishes_nothing(self):
        self.assertEqual(self.publish(128), (128, []))

    def test_failed_version_push_does_not_move_latest(self):
        self.assertEqual(self.publish(2, 1), (1, ["podman push ghcr.io/example/monet:0.9.6"]))


if __name__ == "__main__":
    unittest.main()
