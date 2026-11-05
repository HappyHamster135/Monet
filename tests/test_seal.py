"""Interrupted encrypted-boot cleanup; never operate on the host's disks or TPM."""
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from tests.test_look import libexec_helper


class Cleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="monet-seal-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.seal = libexec_helper("monet-seal")
        self.seal.FIRST_KEY = self.root / "boot/monet-firstboot.key"
        self.seal.FIRST_KEY.parent.mkdir()
        self.seal.FIRST_KEY.write_bytes(b"k" * 64)
        self.seal.STATE = self.root / "state/firstboot-seal.json"
        self.seal.RUNDIR = self.root
        self.seal.CMDLINE = self.root / "cmdline"
        self.karg = "rd.luks.key=ab12=/monet-firstboot.key:UUID=cd34"
        self.seal.CMDLINE.write_text("rd.luks.uuid=luks-ab12 " + self.karg)
        self.data = {"keyslots": {"0": {"salt": "first"}, "1": {"salt": "recovery"}},
                     "tokens": {}, "digests": {"0": {"keyslots": ["0", "1"], "segments": ["0"]}}}
        self.calls = []
        self.fail = None
        self.lie = None
        self.ro = True
        self.args = self.karg
        self.key_matches = True
        self.tpm_works = True
        self.seal.run = self.command

    def command(self, *args, timeout=300):
        args = tuple(map(str, args))
        self.calls.append(args)
        command = args[1]
        operation = ("tpm-test" if "--token-only" in args else "key-test") if command == "open" else command
        if args[0] == "systemd-cryptenroll":
            operation = "enroll"
        if args[0] == "mount":
            operation = args[2]
        if args[:2] == ("rpm-ostree", "kargs"):
            operation = "kargs-delete" if len(args) > 2 else "kargs-read"
        if operation == self.fail:
            return None
        if args[0] == "findmnt":
            return json.dumps({"filesystems": [{"target": str(self.seal.FIRST_KEY.parent),
                                                "vfs-options": "ro,relatime" if self.ro else "rw,relatime"}]})
        if args[0] == "mount":
            if operation != self.lie:
                self.ro = operation == "remount,ro"
            return ""
        if command == "luksUUID":
            return "ab12\n"
        if command == "luksDump":
            return json.dumps(self.data)
        if operation == "key-test":
            return "Key slot 0 unlocked.\n" if self.key_matches else None
        if args[0] == "systemd-cryptenroll":
            self.data["keyslots"]["2"] = {"salt": "tpm"}
            self.data["tokens"]["0"] = {"type": "systemd-tpm2", "keyslots": ["2"]}
            self.data["digests"]["0"]["keyslots"].append("2")
            return ""
        if operation == "tpm-test":
            return "" if self.tpm_works else None
        if operation == "kargs-delete":
            if self.lie != operation:
                self.args = ""
            return ""
        if operation == "kargs-read":
            return self.args
        if command == "luksKillSlot":
            if self.lie != command:
                self.data["keyslots"].pop(args[-1], None)
            return ""
        self.fail_test = args
        raise AssertionError(f"Unmocked command: {args}")

    def start(self, expected):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            result = self.seal.first_start()
        self.assertEqual(result, expected, output.getvalue())
        return output.getvalue()

    def test_success_verifies_tpm_and_arguments_before_retiring_only_bootstrap(self):
        self.start(0)
        self.assertEqual(set(self.data["keyslots"]), {"1", "2"})
        self.assertFalse(self.seal.FIRST_KEY.exists())
        self.assertFalse(self.seal.STATE.exists())
        self.assertTrue(self.ro)
        enrollment = next(c for c in self.calls if c[0] == "systemd-cryptenroll")
        self.assertNotIn("--wipe-slot=tpm2", enrollment)
        kill = next(i for i, c in enumerate(self.calls) if c[1] == "luksKillSlot")
        self.assertTrue(any("--token-only" in c for c in self.calls[:kill]))
        self.assertIn(("rpm-ostree", "kargs"), self.calls[:kill])
        self.assertIn(("mount", "-o", "remount,ro", str(self.seal.FIRST_KEY.parent)), self.calls)
        self.calls.clear()
        self.start(0)
        self.assertEqual(self.calls, [])

    def test_failure_and_retry_of_each_external_step(self):
        for operation in ("luksUUID", "luksDump", "key-test", "--json", "remount,rw",
                          "enroll", "kargs-delete", "kargs-read", "luksKillSlot"):
            with self.subTest(operation=operation):
                # Each failure starts from a fresh fixture, including its receipt.
                case = Cleanup()
                case.setUp()
                try:
                    case.fail = operation
                    case.start(1)
                    self.assertEqual(case.seal.FIRST_KEY.read_bytes(), b"k" * 64)
                    self.assertIn("0", case.data["keyslots"])
                    self.assertTrue(case.ro)
                    case.fail = None
                    case.start(0)
                finally:
                    case.doCleanups()

    def test_enrollment_failure_and_tpm_unlock_failure_keep_original_key(self):
        self.tpm_works = False
        self.start(1)
        self.assertIn("0", self.data["keyslots"])
        self.assertEqual(self.seal.FIRST_KEY.read_bytes(), b"k" * 64)
        self.assertEqual(self.args, self.karg)
        self.assertTrue(self.ro)
        self.tpm_works = True
        self.calls.clear()
        self.start(0)
        self.assertFalse(any(c[0] == "systemd-cryptenroll" for c in self.calls))

    def test_a_success_exit_code_is_not_enough(self):
        for operation in ("remount,rw", "kargs-delete", "luksKillSlot"):
            with self.subTest(operation=operation):
                self.lie = operation
                self.start(1)
                self.assertIn("0", self.data["keyslots"])
                self.assertEqual(self.seal.FIRST_KEY.read_bytes(), b"k" * 64)
                self.assertTrue(self.ro)
        self.lie = None
        self.start(0)

    def test_unlink_failure_resumes_after_slot_is_gone(self):
        original = Path.unlink
        def deny_key(path, *args, **kwargs):
            if path == self.seal.FIRST_KEY:
                raise PermissionError("fixture: unlink denied")
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", deny_key):
            self.start(1)
        self.assertNotIn("0", self.data["keyslots"])
        self.assertTrue(self.seal.STATE.exists())
        self.assertEqual(self.seal.FIRST_KEY.read_bytes(), b"\0" * 64)
        self.assertTrue(self.ro)
        self.calls.clear()
        self.key_matches = False
        self.start(0)
        self.assertFalse(any(c[1] == "luksKillSlot" or c[0] == "systemd-cryptenroll" for c in self.calls))

    def test_power_loss_after_key_removal_keeps_receipt_and_restores_mount_on_retry(self):
        self.fail = "remount,ro"
        self.start(1)
        self.assertFalse(self.seal.FIRST_KEY.exists())
        self.assertTrue(self.seal.STATE.exists())
        self.assertFalse(self.ro)
        self.seal.CMDLINE.write_text("rd.luks.uuid=luks-ab12")
        self.fail = None
        self.start(0)
        self.assertTrue(self.ro)
        self.assertFalse(self.seal.STATE.exists())

    def test_receipt_failure_prevents_enrollment_and_retirement(self):
        with patch.object(self.seal, "save_state", side_effect=OSError("fixture: full disk")):
            self.start(1)
        self.assertFalse(any(c[0] in ("systemd-cryptenroll", "mount", "rpm-ostree") or c[1] == "luksKillSlot"
                             for c in self.calls))

    def test_reused_slot_and_missing_recovery_key_are_not_deleted(self):
        self.fail = "kargs-delete"
        self.start(1)
        self.fail = None
        original = copy.deepcopy(self.data)
        for mutate in (lambda: self.data["keyslots"]["0"].update(salt="reused"),
                       lambda: self.data["keyslots"].pop("1"),
                       lambda: self.data["tokens"].update({"4": {"type": "other", "keyslots": ["0"]}}),
                       lambda: self.data["digests"].clear()):
            self.data = copy.deepcopy(original)
            mutate()
            self.calls.clear()
            self.start(1)
            self.assertFalse(any(c[1] == "luksKillSlot" for c in self.calls))
            self.assertTrue(self.ro)
        self.data = original
        self.start(0)

    def test_invalid_legacy_key_is_reported_without_guessing_or_enrolling(self):
        self.key_matches = False
        self.assertIn("legacy cleanup", self.start(1))
        self.assertTrue(self.seal.FIRST_KEY.exists())
        self.assertFalse(self.seal.STATE.exists())
        self.assertFalse(any(c[0] in ("systemd-cryptenroll", "mount", "rpm-ostree") for c in self.calls))

    def test_already_writable_boot_is_not_remounted_read_only(self):
        self.ro = False
        self.start(0)
        self.assertFalse(self.ro)
        self.assertFalse(any(c[0] == "mount" for c in self.calls))

    def test_wrong_or_invalid_receipt_does_not_modify_disk(self):
        self.fail = "kargs-delete"
        self.start(1)
        state = json.loads(self.seal.STATE.read_text())
        for value in (None, [], {**state, "uuid": "cafe"}, {**state, "karg": None}, {**state, "karg": "root=/dev/bad"},
                      {**state, "fingerprint": "bad"}, {**state, "slot": "-1"}):
            self.seal.STATE.write_text(json.dumps(value))
            self.calls.clear()
            self.start(1)
            self.assertFalse(any(c[0] in ("systemd-cryptenroll", "mount", "rpm-ostree") or c[1] == "luksKillSlot"
                                 for c in self.calls))

    def test_receipt_has_no_key_material_and_is_private(self):
        self.fail = "kargs-delete"
        self.start(1)
        self.assertEqual(self.seal.STATE.stat().st_mode & 0o777, 0o600)
        self.assertEqual(set(json.loads(self.seal.STATE.read_text())),
                         {"version", "uuid", "karg", "slot", "fingerprint", "boot_read_only"})

    def test_a_second_cleanup_cannot_race_the_first(self):
        with (self.root / "monet-seal.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.start(1)
        self.assertEqual(self.calls, [])

    def test_multiple_disks_choose_the_monet_key_and_reject_ambiguous_paths(self):
        self.seal.CMDLINE.write_text("rd.luks.uuid=luks-cafe " + self.seal.CMDLINE.read_text())
        self.fail = "remount,ro"
        self.start(1)
        self.seal.CMDLINE.write_text("rd.luks.uuid=luks-cafe rd.luks.uuid=luks-ab12")
        self.fail = None
        self.start(0)
        for cmdline in ("rd.luks.uuid=../../etc/passwd", "rd.luks.uuid=cafe " + self.karg,
                        "rd.luks.uuid=ab12 " + self.karg + " " + self.karg):
            with self.assertRaises(ValueError):
                self.seal.disk(cmdline)

    def test_command_runner_is_noninteractive_and_locale_independent(self):
        seal = libexec_helper("monet-seal")
        with patch.object(seal.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as ran:
            self.assertEqual(seal.run("cryptsetup", "luksUUID", "fixture"), "ok")
        self.assertEqual(ran.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(ran.call_args.kwargs["env"]["LC_ALL"], "C")

    def test_tpm_lost_while_kernel_arguments_change_does_not_retire_slot(self):
        original = self.command
        def stop_tpm(*args, **kwargs):
            out = original(*args, **kwargs)
            if args == ("rpm-ostree", "kargs"):
                self.tpm_works = False
            return out
        self.seal.run = stop_tpm
        self.start(1)
        self.assertIn("0", self.data["keyslots"])
        self.assertEqual(self.seal.FIRST_KEY.read_bytes(), b"k" * 64)
        self.assertTrue(self.ro)

    def test_key_symlinks_are_not_followed_on_resume(self):
        self.fail = "kargs-delete"
        self.start(1)
        self.seal.FIRST_KEY.unlink()
        unrelated = self.root / "unrelated"
        unrelated.write_bytes(b"keep me")
        self.seal.FIRST_KEY.symlink_to(unrelated)
        self.start(1)
        self.assertEqual(unrelated.read_bytes(), b"keep me")


class BootMount(unittest.TestCase):
    @unittest.skipUnless(all(shutil.which(c) for c in ("unshare", "mount", "findmnt")), "Linux mount tools")
    def test_actual_read_only_boot_is_restored_on_success_and_error_in_private_namespace(self):
        available = subprocess.run(["unshare", "--user", "--map-root-user", "--mount", "--fork", "true"],
                                   capture_output=True, timeout=10)
        if available.returncode:
            self.skipTest("Private user/mount namespaces are unavailable")
        fixture = Path(__file__).with_name("fixtures") / "seal-boot-mount.py"
        run = subprocess.run(["unshare", "--user", "--map-root-user", "--mount", "--fork", sys.executable, str(fixture)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd unit condition evaluator")
    def test_service_runs_when_either_key_or_receipt_remains(self):
        with tempfile.TemporaryDirectory(prefix="monet-seal-unit-") as tmp:
            key, receipt = Path(tmp) / "key", Path(tmp) / "receipt"
            for has_key, has_receipt in ((False, False), (True, False), (False, True), (True, True)):
                key.unlink(missing_ok=True)
                receipt.unlink(missing_ok=True)
                if has_key: key.touch()
                if has_receipt: receipt.touch()
                # New systemd initializes a manager even for condition evaluation.
                # Keep its runtime directory private and never use the host manager.
                result = subprocess.run(["systemd-analyze", "--user", "condition", f"ConditionPathExists=|{key}",
                                         f"ConditionPathExists=|{receipt}"],
                                        env=dict(os.environ, XDG_RUNTIME_DIR=tmp), capture_output=True, timeout=10)
                self.assertEqual(result.returncode == 0, has_key or has_receipt, result.stderr)


@unittest.skipUnless(shutil.which("cryptsetup"), "cryptsetup is needed for disposable LUKS2 fixtures")
class RealLuks(unittest.TestCase):
    def test_slot_retirement_and_retry_preserve_real_recovery_unlock(self):
        with tempfile.TemporaryDirectory(prefix="monet-luks-fixture-") as tmp:
            root = Path(tmp)
            ident = str(uuid.uuid4())
            disk = root / ident
            with disk.open("wb") as f:
                f.truncate(32 * 1024 * 1024)
            first, recovery, surrogate = [root / name for name in ("monet-firstboot.key", "recovery", "surrogate")]
            for key in (first, recovery, surrogate):
                key.write_bytes(os.urandom(64))
                key.chmod(0o600)
            seal = libexec_helper("monet-seal")
            original_run = seal.run
            def crypt(*args):
                output = original_run("cryptsetup", *args, timeout=30)
                self.assertIsNotNone(output, str(args[:2]))
                return output
            # Fast PBKDF parameters belong only to this disposable test file.
            fast = ("--pbkdf", "pbkdf2", "--pbkdf-force-iterations", "1000")
            crypt("luksFormat", "--type", "luks2", "--batch-mode", "--uuid", ident,
                  *fast, "--key-file", first, disk)
            for new in (recovery, surrogate):
                crypt("luksAddKey", "--batch-mode", *fast, "--key-file", first, disk, new)
            karg = f"rd.luks.key={ident}=/monet-firstboot.key:UUID=abcd"
            seal.FIRST_KEY, seal.STATE, seal.RUNDIR = first, root / "state/receipt.json", root
            seal.disk = lambda **kwargs: (disk, karg)
            kernel_args = [karg]
            commands = []
            def run(*args, timeout=300):
                commands.append(tuple(map(str, args)))
                if args[0] == "rpm-ostree":
                    if len(args) > 2:
                        kernel_args.clear()
                    return " ".join(kernel_args)
                self.assertEqual(args[0], "cryptsetup")
                self.assertIn(str(disk), list(map(str, args)))
                return original_run(*args, timeout=30)
            seal.run = run
            seal.boot_read_only = lambda: False
            # Substitute only the hardware TPM proof with a separate real key slot.
            # No host TPM, mount, keyring or kernel-argument command is executed.
            seal.tpm_unlocks = lambda device, data: original_run(
                "cryptsetup", "open", "--test-passphrase", "--key-slot", "2", "--key-file", surrogate, device) is not None
            with patch.object(seal, "wipe", side_effect=OSError("simulated power loss after slot retirement")), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(seal.first_start(), 1)
            self.assertTrue(seal.STATE.exists())
            self.assertNotIn("0", seal.metadata(disk)["keyslots"])
            self.assertIsNone(original_run("cryptsetup", "open", "--test-passphrase", "--key-file", first, disk))
            crypt("open", "--test-passphrase", "--key-file", recovery, disk)
            self.assertEqual(seal.first_start(), 0)
            self.assertFalse(first.exists())
            self.assertFalse(seal.STATE.exists())
            crypt("open", "--test-passphrase", "--key-file", recovery, disk)
            self.assertEqual(sum(c[1] == "luksKillSlot" for c in commands), 1)


if __name__ == "__main__":
    unittest.main()
