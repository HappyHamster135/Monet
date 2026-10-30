"""Trusted WinPE staging and retries: ordinary files, simulated mounts, no real disks."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_installer import load, ROOT


class Handoff(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="monet winpe fixture ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.p = load("linux/libexec/monet-prepare-windows", "prepare_winpe_fixture")
        self.p.STATE, self.p.WORK, self.p.MOUNT = (self.root / n for n in ("state", "work", "run"))
        self.p.SHARE, self.p.LOG = self.root / "share", self.root / "log"
        self.setup = self.p.MOUNT / "setup-resume"
        for path in (self.p.STATE, self.p.WORK, self.setup / "sources", self.setup / "monet/bridge", self.p.SHARE / "winpe"):
            path.mkdir(parents=True, exist_ok=True)
        for name in ("monet-start.cmd", "deploy.cmd", "winpeshl.ini"):
            shutil.copyfile(ROOT / "linux/share/monet/winpe" / name, self.p.SHARE / "winpe" / name)
        (self.p.SHARE / "winpe/monet-setup-check.exe").write_bytes(b"MZ disposable fixture; not executed")
        for name in ("sources/install.swm", "sources/install2.swm", "monet/unattend.xml", "monet/bridge/Install-Monet.ps1", "monet/bridge/monet-bridge.exe"):
            (self.setup / name).write_text(name)
        self.identities = dict(version=1, disk_guid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        for i, name in enumerate(("windows", "setup", "efi"), 1):
            self.identities[name] = dict(guid=f"11111111-1111-1111-1111-{i:012d}", offset=i*1024**2, length=1024**2,
                                        filesystem="ntfs" if i == 1 else "vfat", filesystem_id="0123456789ABCDEF" if i == 1 else "1234-ABCD")

    def saved_fixture(self):
        (self.setup / "sources/boot.wim").write_bytes(b"fixture boot image")
        files = [p for p in self.setup.rglob("*") if p.is_file() and p.name not in ("boot.wim", "deployment.json")]
        self.job = dict(version=1, id="22222222-2222-2222-2222-222222222222", partitions=self.identities,
                        files=[dict(path=p.relative_to(self.setup).as_posix(), size=p.stat().st_size, sha256=self.p.file_digest(p)) for p in files])
        data = json.dumps(self.job).encode()
        (self.setup / "monet/deployment.json").write_bytes(data)
        self.hash = hashlib.sha256(data).hexdigest()
        self.p.save_state("windows-staging.json", dict(version=1, job=self.job, manifest_sha256=self.hash,
                                                       boot_sha256=self.p.file_digest(self.setup / "sources/boot.wim")))
        self.p.save_partition_plan({})
        self.p.deployment_manifest = lambda disk: copy.deepcopy(self.identities)
        self.p.mapped_partitions = lambda disk, plan: ({"path": "/fixture/windows"}, {"path": "/fixture/setup", "partn": 7})
        self.calls = []
        def run(*args, **kwargs):
            self.calls.append(args)
            if args[0] not in ("mount", "umount"):
                raise AssertionError(f"unexpected storage mutation: {args}")
            self.assertIn(args[0], ("mount", "umount"))
            if args[0] == "mount": self.assertEqual(args[1:3], ("-o", "ro"))
            return True
        self.p.run = run

    def resume(self, phase=None, names="", bad_job=False):
        checkpoint = dict(version=1, job_id="different" if bad_job else self.job["id"], manifest_sha256=self.hash, phase=phase)
        def command(args, **kwargs):
            if args[0] == "ntfsls": return subprocess.CompletedProcess(args, 0, names, "")
            if args[0] == "ntfscat":
                kwargs["stdout"].write(json.dumps(checkpoint).encode())
                return subprocess.CompletedProcess(args, 0, None, b"")
            raise AssertionError(args)
        with patch.object(self.p.subprocess, "run", side_effect=command):
            return self.p.resume_staged_setup("/fixture/disk")

    def test_newly_staged_and_interrupted_jobs_resume_without_reformatting_or_restaging(self):
        self.saved_fixture()
        self.assertEqual(self.resume(names=""), (7, "applying"))
        for phase in ("applying", "applied"):
            self.assertEqual(self.resume(phase, ".monet-setup.json\nWindows"), (7, phase))
        self.assertTrue(all(c[0] in ("mount", "umount") for c in self.calls))

    def test_complete_job_requires_its_windows_loader_and_does_not_reinstall(self):
        self.saved_fixture()
        self.p.has_windows = lambda path: True
        self.assertEqual(self.resume("complete", ".monet-setup.json\nWindows"), (7, "complete"))
        self.p.has_windows = lambda path: False
        with self.assertRaisesRegex(self.p.Stop, "missing its boot loader"):
            self.resume("complete", ".monet-setup.json\nWindows")

    def test_changed_payload_or_boot_image_stops_and_unmounts_the_read_only_probe(self):
        for name in ("sources/install.swm", "sources/boot.wim", "monet/deployment.json"):
            with self.subTest(name=name):
                self.saved_fixture()
                path = self.setup / name
                previous = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises(self.p.Stop): self.resume()
                self.assertEqual(self.calls[-1][0], "umount")
                path.write_bytes(previous)

    def test_foreign_checkpoint_or_unrecorded_target_is_not_adopted(self):
        self.saved_fixture()
        with self.assertRaisesRegex(self.p.Stop, "another preparation"):
            self.resume("applying", ".monet-setup.json\nWindows", bad_job=True)
        with self.assertRaisesRegex(self.p.Stop, "unrecorded files"):
            self.resume(names="Windows\nUsers")

    def test_missing_checker_is_detected_before_any_storage_operation(self):
        (self.p.SHARE / "winpe/monet-setup-check.exe").unlink()
        with patch.object(self.p, "run", side_effect=AssertionError("no storage command")):
            with self.assertRaisesRegex(self.p.Stop, "does not include"):
                self.p.require_setup_payload()

    @unittest.skipUnless(shutil.which("mkfs.ntfs") and shutil.which("ntfscp"), "native NTFS image tools")
    def test_checkpoint_is_read_from_a_real_ntfs_image_without_mounting_or_reformatting(self):
        self.saved_fixture()
        image = self.root / "disposable-ntfs.img"
        with image.open("xb") as stream:
            stream.truncate(64 * 1024**2)
        subprocess.run(["mkfs.ntfs", "-F", "-Q", str(image)], capture_output=True, check=True, timeout=30)
        self.p.mapped_partitions = lambda disk, plan: ({"path": str(image)}, {"path": "/fixture/setup", "partn": 7})
        self.assertEqual(self.p.resume_staged_setup("/fixture/disk"), (7, "applying"))
        checkpoint = self.root / "checkpoint.json"
        for phase in ("applying", "applied"):
            checkpoint.write_text(json.dumps(dict(version=1, job_id=self.job["id"], manifest_sha256=self.hash, phase=phase)))
            subprocess.run(["ntfscp", str(image), str(checkpoint), "/.monet-setup.json"], capture_output=True, check=True, timeout=30)
            self.assertEqual(self.p.resume_staged_setup("/fixture/disk"), (7, phase))
        checkpoint.write_bytes(b"x" * (1024 * 1024))
        subprocess.run(["ntfscp", str(image), str(checkpoint), "/.monet-setup.json"], capture_output=True, check=True, timeout=30)
        with self.assertRaisesRegex(self.p.Stop, "checkpoint could not be read"):
            self.p.resume_staged_setup("/fixture/disk")
        self.assertTrue(all(c[0] in ("mount", "umount") for c in self.calls))

    def test_packaging_refuses_a_missing_checker_before_changing_existing_output(self):
        output = self.root / "package"
        output.mkdir()
        marker = output / "preserve.txt"
        marker.write_text("untouched")
        result = subprocess.run(["bash", str(ROOT / "tools/package.sh"), "linux", "/fixture/monet", str(output),
                                 "/fixture/bridge.exe"], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires monet-setup-check.exe", result.stderr)
        self.assertEqual(marker.read_text(), "untouched")

    @unittest.skipUnless(shutil.which("wimlib-imagex"), "native wimlib fixture")
    def test_real_boot_image_embeds_exact_manifest_program_and_script(self):
        source = self.root / "fake WinPE"
        (source / "Windows/System32").mkdir(parents=True)
        (source / "monet").mkdir()
        (source / "monet/old.cmd").write_text("foreign script must disappear")
        (source / "Windows/System32/winpeshl.ini").write_text("old launcher")
        boot = self.setup / "sources/boot.wim"
        for command in (["capture", str(source), str(boot), "First"], ["append", str(source), str(boot), "Second"]):
            subprocess.run(["wimlib-imagex", *command], capture_output=True, check=True, timeout=30)
        self.p.write_setup_handoff(self.setup, self.identities)
        saved = json.loads((self.p.STATE / "windows-staging.json").read_text())
        self.assertEqual(saved["job"]["partitions"], self.identities)
        self.assertEqual(saved["boot_sha256"], self.p.file_digest(boot))
        self.assertEqual((self.p.STATE / "windows-staging.json").stat().st_mode & 0o777, 0o600)
        for name in ("deployment.json", "deploy.cmd", "monet-setup-check.exe"):
            out = subprocess.run(["wimlib-imagex", "extract", str(boot), "2", f"/monet/{name}", "--to-stdout"], capture_output=True, check=True, timeout=30)
            expected = (self.setup / "monet" if name == "deployment.json" else self.p.SHARE / "winpe") / name
            self.assertEqual(out.stdout, expected.read_bytes())
        out = subprocess.run(["wimlib-imagex", "extract", str(boot), "2", "/monet/old.cmd", "--to-stdout"], capture_output=True, timeout=30)
        self.assertNotEqual(out.returncode, 0)
        self.assertFalse((self.setup / "monet/deploy.cmd").exists())


if __name__ == "__main__":
    unittest.main()
