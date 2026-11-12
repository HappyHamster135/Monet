"""Publishing may update rolling images without replacing a released version."""
import os
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qualified_release", ROOT / "tools/publish-qualified.py")
qualified = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualified)


class ImagePublication(unittest.TestCase):
    def publish(self, git_status, push_status=0, *, record_digest=False, digest="sha256:" + "a" * 64, rolling_status=0):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, script in {
                "git": '#!/bin/sh\nexit "$GIT_STATUS"\n',
                "sudo": r'''#!/bin/sh
printf '%s\n' "$*" >> "$CALLS"
for arg do
    case "$arg" in --digestfile=*) printf '%s\n' "$PUSH_DIGEST" > "${arg#--digestfile=}" ;; esac
done
case "$arg" in *:latest) exit "$ROLLING_STATUS" ;; esac
exit "$PUSH_STATUS"
''',
            }.items():
                path = root / name
                path.write_text(script)
                path.chmod(0o700)
            calls = root / "calls"
            output = root / "output"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       GIT_STATUS=str(git_status), PUSH_STATUS=str(push_status), CALLS=str(calls),
                       PUSH_DIGEST=digest, ROLLING_STATUS=str(rolling_status), TMPDIR=folder)
            result = subprocess.run(["bash", str(ROOT / "tools/push-image.sh"),
                                     "ghcr.io/example/monet", "0.9.6", *([str(output)] if record_digest else [])],
                                    env=env, capture_output=True, text=True, timeout=10)
            commands = calls.read_text().splitlines() if calls.exists() else []
            return result.returncode, commands, output.read_text() if output.exists() else ""

    def test_released_version_is_never_overwritten(self):
        self.assertEqual(self.publish(0), (0, ["podman push ghcr.io/example/monet:latest"], ""))

    def test_new_version_precedes_rolling_update(self):
        self.assertEqual(self.publish(2), (0, ["podman push ghcr.io/example/monet:0.9.6",
                                              "podman push ghcr.io/example/monet:latest"], ""))

    def test_remote_failure_publishes_nothing(self):
        self.assertEqual(self.publish(128), (128, [], ""))

    def test_failed_version_push_does_not_move_latest(self):
        self.assertEqual(self.publish(2, 1), (1, ["podman push ghcr.io/example/monet:0.9.6"], ""))

    def test_installer_digest_comes_from_the_versioned_oci_push(self):
        digest = "sha256:" + "b" * 64
        status, calls, output = self.publish(2, record_digest=True, digest=digest)
        self.assertEqual(status, 0)
        self.assertRegex(calls[0], r"^podman push --format oci --digestfile=.+ ghcr\.io/example/monet:0\.9\.6$")
        self.assertEqual(calls[1:], ["podman push ghcr.io/example/monet:latest"])
        self.assertEqual(output, f"digest={digest}\n")

    def test_already_released_images_produce_no_installer_digest(self):
        self.assertEqual(self.publish(0, record_digest=True), (0, ["podman push ghcr.io/example/monet:latest"], ""))

    def test_invalid_digest_or_failed_publication_produces_no_installer_digest(self):
        status, calls, output = self.publish(2, record_digest=True, digest="sha256:broken")
        self.assertNotEqual(status, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(output, "")
        for options in ({"push_status": 1}, {"rolling_status": 1}):
            with self.subTest(options=options):
                status, _, output = self.publish(2, record_digest=True, **options)
                self.assertNotEqual(status, 0)
                self.assertEqual(output, "")


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

    def test_signing_failure_stops_rolling_promotion(self):
        record = {"images": {
            "nvidia": {"image": "example/monet:0.9.8", "manifest": "sha256:nvidia"},
            "mesa": {"image": "example/monet-amd:0.9.8", "manifest": "sha256:mesa"},
        }}
        with patch.object(qualified, "remote_digest", side_effect=[None, "sha256:nvidia", None]), \
                patch.object(qualified.subprocess, "run",
                             side_effect=[None, subprocess.CalledProcessError(1, "signer")]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                qualified.publish(record, Path("exports"), Path("signer"))
            self.assertEqual([call.args[0][-2:] for call in run.call_args_list], [
                ["oci:exports:nvidia", "example/monet:0.9.8"],
                ["oci:exports:mesa", "example/monet-amd:0.9.8"],
            ])


@unittest.skipIf(os.name == "nt", "Linux systemd installation path")
class PortableSources(unittest.TestCase):
    def test_nvidia_dropin_installs_with_systemd_escaping_from_a_portable_source(self):
        script = (ROOT / "linux/install.sh").read_text()
        functions = script[script.index("subst() {"):script.index("# Copies a folder")]
        command = re.search(r'(?m)^put 644 "\$SRC/systemd/user/monet-nvidia-settings.conf" \\\n.*', script).group()
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, SRC=str(ROOT / "linux"), USERUNITDIR=folder,
                       BINDIR="/usr/bin", DATADIR="/usr/share", LIBEXECDIR="/usr/libexec")
            subprocess.run(["bash", "-eu", "-c", functions + command], env=env, check=True, timeout=10)
            path = Path(folder) / r"app-nvidia\x2dsettings\x2dload@autostart.service.d/monet-saved-settings.conf"
            self.assertEqual(path.read_bytes(), (ROOT / "linux/systemd/user/monet-nvidia-settings.conf").read_bytes())
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
