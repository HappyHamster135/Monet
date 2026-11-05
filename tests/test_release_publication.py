"""Publishing may update rolling images without replacing a released version."""
import os
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qualified_release", ROOT / "tools/publish-qualified.py")
qualified = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualified)


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


class QualifiedPublication(unittest.TestCase):
    def test_corrupt_missing_and_duplicate_parts_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "Monet-0.9.6-oci.tar.part-aa"
            path.write_bytes(b"verified export")
            part = {"name": path.name, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(qualified.verify_parts({"parts": [part]}, folder), [path])
            for parts in ([], [part, part], [dict(part, name="../" + path.name)]):
                with self.assertRaises(ValueError):
                    qualified.verify_parts({"parts": parts}, folder)
            path.write_bytes(b"corrupt export!")
            with self.assertRaises(ValueError):
                qualified.verify_parts({"parts": [part]}, folder)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                qualified.verify_parts({"parts": [part]}, folder)

    def test_different_existing_version_is_not_replaced(self):
        record = {"images": {"amd": {"image": "example/monet:0.9.6", "manifest": "sha256:expected"}}}
        with patch.object(qualified, "remote_digest", return_value="sha256:other"), \
                patch.object(qualified.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                qualified.publish(record, Path("unused"))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
