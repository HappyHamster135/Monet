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
CHECK_SPEC = importlib.util.spec_from_file_location("release_checks", ROOT / "tools/require-release-checks.py")
checks = importlib.util.module_from_spec(CHECK_SPEC)
CHECK_SPEC.loader.exec_module(checks)


class ReleaseChecks(unittest.TestCase):
    def test_both_required_jobs_must_pass_even_when_the_build_is_still_packaging(self):
        run = {"id": 1, "status": "in_progress"}
        jobs = lambda _: [{"name": "test", "conclusion": "success"},
                          {"name": "desktop", "conclusion": "success"}]
        self.assertTrue(checks.check_runs([run], jobs))

    def test_missing_or_pending_desktop_checks_do_not_publish(self):
        self.assertFalse(checks.check_runs([], lambda _: []))
        self.assertFalse(checks.check_runs([{"id": 1, "status": "in_progress"}],
                         lambda _: [{"name": "test", "conclusion": "success"}]))

    def test_failed_or_cancelled_desktop_checks_block_publication(self):
        for conclusion in ("failure", "cancelled", "skipped", None):
            with self.subTest(conclusion=conclusion), self.assertRaises(RuntimeError):
                checks.check_runs([{"id": 1, "status": "completed"}],
                    lambda _: [{"name": "test", "conclusion": "success"},
                               {"name": "desktop", "conclusion": conclusion}])


class ImagePublication(unittest.TestCase):
    def publish(self, git_status, push_status=0, *, record_digest=False, digest="sha256:" + "a" * 64, rolling_status=0,
                beta=None, inspect_status=1, inspect_error="reading manifest: manifest unknown"):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, script in {
                "git": '#!/bin/sh\nexit "$GIT_STATUS"\n',
                "sudo": r'''#!/bin/sh
printf '%s\n' "$*" >> "$CALLS"
if [ "$1" = skopeo ]; then
    printf '%s\n' "$INSPECT_ERROR" >&2
    exit "$INSPECT_STATUS"
fi
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
                       PUSH_DIGEST=digest, ROLLING_STATUS=str(rolling_status), TMPDIR=folder,
                       INSPECT_STATUS=str(inspect_status), INSPECT_ERROR=inspect_error)
            arguments = [str(output)] if record_digest or beta is not None else []
            if beta is not None:
                arguments.append(beta)
            result = subprocess.run(["bash", str(ROOT / "tools/push-image.sh"),
                                     "ghcr.io/example/monet", "0.9.6", *arguments],
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


class BetaPublication(unittest.TestCase):
    """A beta (tools/beta-release.py) publishes its own tag only: never latest or the version."""
    publish = ImagePublication.publish
    BETA = "0.9.6-beta.2"
    INSPECT = "skopeo inspect --raw docker://ghcr.io/example/monet:0.9.6-beta.2"

    def test_only_the_betas_own_tag_is_published_with_its_digest(self):
        digest = "sha256:" + "c" * 64
        status, calls, output = self.publish(2, beta=self.BETA, digest=digest)
        self.assertEqual(status, 0)
        self.assertEqual(calls[:2], [self.INSPECT, "podman tag ghcr.io/example/monet:0.9.6 ghcr.io/example/monet:0.9.6-beta.2"])
        self.assertRegex(calls[2], r"^podman push --format oci --digestfile=.+ ghcr\.io/example/monet:0\.9\.6-beta\.2$")
        self.assertEqual(len(calls), 3)
        self.assertFalse(any(call.endswith((":latest", ":0.9.6")) for call in calls if call.startswith("podman push")))
        self.assertEqual(output, f"digest={digest}\n")

    def test_a_released_version_gets_no_beta(self):
        status, calls, output = self.publish(0, beta=self.BETA)
        self.assertNotEqual(status, 0)
        self.assertEqual((calls, output), ([], ""))

    def test_an_unknown_release_state_publishes_nothing(self):
        self.assertEqual(self.publish(128, beta=self.BETA), (128, [], ""))

    def test_a_published_beta_is_never_replaced(self):
        status, calls, output = self.publish(2, beta=self.BETA, inspect_status=0, inspect_error="")
        self.assertNotEqual(status, 0)
        self.assertEqual((calls, output), ([self.INSPECT], ""))

    def test_a_registry_that_cant_be_asked_publishes_nothing(self):
        status, calls, output = self.publish(2, beta=self.BETA, inspect_error="pinging container registry: connection refused")
        self.assertNotEqual(status, 0)
        self.assertEqual((calls, output), ([self.INSPECT], ""))

    def test_only_a_numbered_beta_of_this_version(self):
        for beta in ("latest", "0.9.6", "0.9.5-beta.1", "0.9.6-beta.0", "0.9.6-beta.x", "0.9.6-beta.1/x", ""):
            with self.subTest(beta=beta):
                status, calls, output = self.publish(2, beta=beta)
                if beta == "":
                    continue   # no beta: the release path, tested above
                self.assertNotEqual(status, 0)
                self.assertEqual((calls, output), ([], ""))

    def test_a_failed_push_records_no_digest(self):
        for options in ({"push_status": 1}, {"digest": "sha256:broken"}):
            with self.subTest(options=options):
                status, calls, output = self.publish(2, beta=self.BETA, **options)
                self.assertNotEqual(status, 0)
                self.assertEqual(output, "")
                self.assertFalse(any(call.endswith(":latest") for call in calls))


class QualifiedPublication(unittest.TestCase):
    def test_corrupt_missing_and_duplicate_parts_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "Monet-0.9.6-oci.tar.part-aa"
            path.write_bytes(b"verified export")
            part = {"name": path.name, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(qualified.verify_parts({"version": "0.9.6", "parts": [part]}, folder), [path])
            for parts in ([], [part, part], [dict(part, name="../" + path.name)]):
                with self.assertRaises(ValueError):
                    qualified.verify_parts({"version": "0.9.6", "parts": parts}, folder)
            path.write_bytes(b"corrupt export!")
            with self.assertRaises(ValueError):
                qualified.verify_parts({"version": "0.9.6", "parts": [part]}, folder)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                qualified.verify_parts({"version": "0.9.6", "parts": [part]}, folder)

    def test_archive_parts_can_include_a_version_suffix_and_must_match_the_release(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "Monet-0.9.8-5-oci.tar.part-aa"
            data = b"verified export"
            path.write_bytes(data)
            part = {"name": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            self.assertEqual(qualified.verify_parts({"version": "0.9.8-5", "parts": [part]}, folder), [path])
            with self.assertRaises(ValueError):
                qualified.verify_parts({"version": "0.9.8-4", "parts": [part]}, folder)

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

    def test_prerelease_verifies_the_versioned_image_without_moving_latest(self):
        record = {"images": {"amd": {"image": "example/monet:0.9.8-5", "manifest": "sha256:expected"}}}
        with patch.object(qualified, "remote_digest", side_effect=[None, "sha256:expected"]), \
                patch.object(qualified.subprocess, "run") as run:
            qualified.publish(record, Path("exports"), Path("signer"), promote=False)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-2:], ["oci:exports:amd", "example/monet:0.9.8-5"])


class PromoteExisting(unittest.TestCase):
    def setUp(self):
        self.repositories = {"amd": "ghcr.io/happyhamster135/monet-amd", "nvidia": "ghcr.io/happyhamster135/monet"}
        self.candidate = self.record("0.9.8-5", ("a", "b"))
        self.previous = self.record("0.9.8", ("c", "d"))
        self.remote = {info["image"]: info["manifest"] for info in self.candidate["images"].values()}
        self.remote.update({repo + ":latest": self.previous["images"][variant]["manifest"]
                            for variant, repo in self.repositories.items()})

    def record(self, version, digits):
        return {"version": version, "images": {
            variant: {"image": f"{repo}:{version}", "manifest": "sha256:" + digit * 64}
            for (variant, repo), digit in zip(self.repositories.items(), digits)
        }}

    def test_both_signatures_are_verified_before_promoting_the_recorded_digests(self):
        def copy(command, *, check):
            source, target = command[-2:]
            if target.startswith("docker://"):
                self.remote[target.removeprefix("docker://")] = source.split("@", 1)[1]

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(qualified, "remote_digest", side_effect=self.remote.get), \
                patch.object(qualified.subprocess, "run", side_effect=copy) as run:
            qualified.promote_existing(self.candidate, self.previous, Path(folder))
            qualified.promote_existing(self.candidate, self.previous, Path(folder))
        targets = [call.args[0][-1] for call in run.call_args_list]
        self.assertEqual([target.split(":", 1)[0] for target in targets],
                         ["oci", "oci", "docker", "docker", "oci", "oci"])
        for variant, repo in self.repositories.items():
            self.assertEqual(self.remote[repo + ":latest"], self.candidate["images"][variant]["manifest"])

    def test_unexpected_rolling_digest_stops_before_copying(self):
        self.remote[self.repositories["nvidia"] + ":latest"] = "sha256:" + "f" * 64
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(qualified, "remote_digest", side_effect=self.remote.get), \
                patch.object(qualified.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Rolling tag has changed unexpectedly"):
                qualified.promote_existing(self.candidate, self.previous, Path(folder))
            run.assert_not_called()

    def test_second_signature_failure_keeps_both_rolling_tags(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(qualified, "remote_digest", side_effect=self.remote.get), \
                patch.object(qualified.subprocess, "run",
                             side_effect=[None, subprocess.CalledProcessError(1, "skopeo")]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                qualified.promote_existing(self.candidate, self.previous, Path(folder))
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all(call.args[0][-1].startswith("oci:") for call in run.call_args_list))


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
