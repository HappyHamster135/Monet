"""Partition retries use saved identities; all storage is fake or disposable files."""
import copy
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_installer import load


class PartitionDiscovery(unittest.TestCase):
    def setUp(self):
        self.p = load("linux/libexec/monet-prepare-windows", "partition_discovery_fixture")
        self.p.log = lambda message: None

    def test_explicit_tree_finds_partitions_when_path_omits_name_and_excludes_mapper(self):
        child = dict(path="/dev/fixturep1", type="part", children=[dict(path="/dev/mapper/fixture", type="crypt")])
        def command(*args, **kwargs):
            # Reproduce lsblk's native flat output contract, rather than always
            # supplying the tree shape the caller expects.
            rows = [dict(path="/dev/mapper/fixture", type="crypt"), child, dict(path="/dev/fixture", type="disk")]
            if "--tree" in args:
                rows = [dict(path="/dev/fixture", type="disk", children=[child])]
            return json.dumps(dict(blockdevices=rows))
        self.p.run = command
        self.assertEqual(self.p.partitions("/dev/fixture"), [child])

    def test_missing_ambiguous_and_malformed_disk_roots_are_rejected(self):
        for rows in (None, [], [dict(path="/dev/foreign")],
                     [dict(path="/dev/fixture", children={})],
                     [dict(path="/dev/fixture"), dict(path="/dev/fixture")]):
            with self.subTest(rows=rows), patch.object(self.p, "lsblk", return_value=rows):
                with self.assertRaisesRegex(self.p.Stop, "partition list"):
                    self.p.partitions("/dev/fixture")

    @unittest.skipUnless(shutil.which("lsblk"), "native lsblk unavailable")
    def test_native_read_only_discovery_includes_kernel_partitions(self):
        candidates = [p for p in Path("/sys/class/block").glob("*") if (p / "partition").exists()]
        candidates = [p for p in candidates if Path("/dev", p.name).exists()]
        if not candidates:
            self.skipTest("no native partition devices exposed")
        part = candidates[0]
        parent = part.resolve().parent.name
        found = self.p.partitions(str(Path("/dev", parent)))
        self.assertIn(str(Path("/dev", part.name)), [row["path"] for row in found])
        self.assertTrue(all(row["type"] == "part" for row in found))


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="monet-windows-partitions-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.p = load("linux/libexec/monet-prepare-windows", "prepare_partition_fixture")
        self.p.STATE = self.root / "state"
        self.p.MOUNT = self.root / "run"
        self.p.MIN_WINDOWS_MIB, self.p.SETUP_MIB = 16, 8
        self.disk = "/dev/fixture-never-real"
        self.table = dict(label="gpt", unit="sectors", id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                          sectorsize=512, lastlba=262110,
                          partitions=[dict(uuid="11111111-1111-1111-1111-111111111111", start=2048, size=2048,
                                           type=self.p.BASIC_DATA, name="Keep this partition", node="/dev/fixture1")])
        self.calls, self.fs, self.nodes = [], {}, {}
        self.delays = 0
        self.partial_append = False
        self.fail_format = None
        self.fail_after_format = False
        self.mounted = False
        self.children = False
        self.windows = False
        self.signatures = []
        self.p.run = self.command
        self.p.sector_size = lambda disk: 512
        self.p.largest_free = lambda disk: (4096, self.table["lastlba"] - 4096 + 1)
        self.p.partitions = self.partitions
        self.p.filesystem = lambda path: copy.deepcopy(self.fs.get(path, {}))
        self.p.has_windows = lambda path: self.windows
        self.p.progress = lambda *args: None
        self.sleeps = []
        self.sleep_patch = patch.object(self.p.time, "sleep", side_effect=lambda seconds: self.sleeps.append(seconds))
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

    @property
    def receipt(self):
        return self.p.STATE / "windows-partitions.json"

    def command(self, *args, **kwargs):
        args = tuple(map(str, args))
        self.calls.append((args, kwargs))
        if args[:2] == ("sfdisk", "--json"):
            return json.dumps({"partitiontable": self.table})
        if args[:2] == ("sfdisk", "--append"):
            plan = json.loads(self.receipt.read_text())
            for owned in plan["owned"]:
                if owned["uuid"] not in kwargs["stdin"]:
                    continue
                node = str(self.root / ("partition-" + owned["uuid"]))
                Path(node).write_bytes(bytes(4096))
                part = self.p.part_identity(owned)
                part["node"] = node
                self.nodes[owned["uuid"]] = node
                self.table["partitions"].append(part)
                if self.partial_append:
                    raise self.p.Stop("failed", "fixture: interrupted append")
            return True
        if args[0] in ("partx", "udevadm"):
            return False  # An already-known kernel partition is harmless.
        if args[:3] == ("wipefs", "--no-act", "--json"):
            return json.dumps(dict(signatures=self.signatures))
        if args[0].startswith("mkfs."):
            if self.fail_format == args[0] and not self.fail_after_format:
                raise self.p.Stop("failed", "fixture: interrupted format")
            kind = "ntfs" if args[0] == "mkfs.ntfs" else "vfat"
            label = "MONETWIN" if kind == "ntfs" else "MONETSETUP"
            self.fs[args[-1]] = dict(TYPE=kind, LABEL=label,
                                   UUID="0123456789ABCDEF" if kind == "ntfs" else "1234-ABCD",
                                   VERSION="3.1" if kind == "ntfs" else "FAT32")
            if self.fail_format == args[0]:
                raise self.p.Stop("failed", "fixture: formatter exited after writing")
            return ""
        raise AssertionError(f"Unmocked command: {args}")

    def partitions(self, disk):
        if self.delays:
            self.delays -= 1
            return []
        return [dict(path=p["node"], partuuid=p["uuid"], partlabel=p["name"], size=p["size"] * 512,
                     partn=i + 1, mountpoints=["/fixture"] if self.mounted else [],
                     children=[{}] if self.children else []) for i, p in enumerate(self.table["partitions"])]

    def formats(self):
        return [cmd for cmd, _ in self.calls if cmd[0].startswith("mkfs.")]

    def appends(self):
        return [kwargs["stdin"] for cmd, kwargs in self.calls if cmd[:2] == ("sfdisk", "--append")]

    def test_new_partitions_are_recorded_before_creation_and_verified_before_return(self):
        result = self.p.make_partitions(self.disk)
        plan = json.loads(self.receipt.read_text())
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(self.appends()), 1)
        self.assertEqual(len(self.formats()), 2)
        self.assertEqual(result[2], 3)
        self.assertTrue(all(p["phase"] == "formatted" and p["fs_uuid"] for p in plan["owned"]))
        self.assertNotIn("-F", self.formats()[0])  # Do not override NTFS's mounted-device guard.
        self.assertEqual(self.table["partitions"][0]["name"], "Keep this partition")
        self.p.make_partitions(self.disk)
        self.assertEqual(len(self.formats()), 2)
        self.assertEqual(len(self.appends()), 1)

    def test_delayed_devices_and_retry_after_discovery_exhaustion_do_not_append_twice(self):
        self.delays = 6
        with self.assertRaisesRegex(self.p.Stop, "saved plan will be reused"):
            self.p.make_partitions(self.disk)
        self.assertEqual(self.sleeps, [1] * 5)
        self.assertFalse(self.formats())
        self.assertEqual(len(self.appends()), 1)
        self.delays = 2
        self.p.make_partitions(self.disk)
        self.assertEqual(len(self.appends()), 1)
        self.assertEqual(len(self.formats()), 2)

    def test_partial_partition_creation_only_adds_the_missing_recorded_partition(self):
        self.partial_append = True
        with self.assertRaisesRegex(self.p.Stop, "interrupted append"):
            self.p.make_partitions(self.disk)
        first = self.table["partitions"][-1]["uuid"]
        self.partial_append = False
        self.p.make_partitions(self.disk)
        self.assertEqual(len(self.table["partitions"]), 3)
        self.assertNotIn(first, self.appends()[-1])

    def test_retry_after_first_format_does_not_format_it_again(self):
        self.fail_format = "mkfs.vfat"
        with self.assertRaises(self.p.Stop):
            self.p.make_partitions(self.disk)
        self.fail_format = None
        self.p.make_partitions(self.disk)
        self.assertEqual(sum(c[0] == "mkfs.ntfs" for c in self.formats()), 1)
        self.assertEqual(sum(c[0] == "mkfs.vfat" for c in self.formats()), 2)

    def test_formatter_failure_after_writing_resumes_without_reformat(self):
        self.fail_format, self.fail_after_format = "mkfs.ntfs", True
        with self.assertRaises(self.p.Stop):
            self.p.make_partitions(self.disk)
        self.fail_format = None
        self.p.make_partitions(self.disk)
        self.assertEqual(sum(c[0] == "mkfs.ntfs" for c in self.formats()), 1)

    def test_labels_and_missing_filesystem_do_not_authorize_adopting_old_partitions(self):
        for label in (self.p.WINDOWS_LABEL, self.p.SETUP_LABEL):
            with self.subTest(label=label):
                self.table["partitions"][0]["name"] = label
                with self.assertRaisesRegex(self.p.Stop, "no ownership record"):
                    self.p.make_partitions(self.disk)
                self.assertFalse(self.receipt.exists())
                self.assertFalse(self.appends())
                self.assertFalse(self.formats())

    def pending(self):
        self.delays = 6
        with self.assertRaises(self.p.Stop):
            self.p.make_partitions(self.disk)

    def legacy_plan(self):
        self.pending()
        plan = json.loads(self.receipt.read_text())
        self.receipt.unlink()
        self.delays = 0
        self.calls.clear()
        return plan

    def test_legacy_inspection_changes_nothing_and_explicit_recovery_reuses_exact_partitions(self):
        plan = self.legacy_plan()
        before = copy.deepcopy(self.table)
        self.p.recover_partition_plan(self.disk, plan)
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.formats())
        self.assertFalse(self.appends())
        self.p.recover_partition_plan(self.disk, plan, adopt=True)
        self.assertEqual(json.loads(self.receipt.read_text()), plan)
        self.p.make_partitions(self.disk)
        self.assertEqual(self.table, before)
        self.assertFalse(self.appends())
        self.assertEqual(len(self.formats()), 2)
        # Re-running the explicit repair preserves both formatted filesystems.
        self.p.recover_partition_plan(self.disk, plan, adopt=True)
        self.p.make_partitions(self.disk)
        self.assertEqual(len(self.formats()), 2)

    def test_legacy_recovery_rejects_signatures_mounts_missing_and_changed_partitions(self):
        plan = self.legacy_plan()
        original = copy.deepcopy(self.table)
        cases = ("filesystem", "signature", "mounted", "holder", "missing", "changed", "other-disk", "staged")
        for case in cases:
            with self.subTest(case=case):
                self.table = copy.deepcopy(original)
                self.fs.clear()
                self.signatures = []
                self.mounted = self.children = False
                (self.p.STATE / "windows-staging.json").unlink(missing_ok=True)
                if case == "filesystem": self.fs[self.table["partitions"][2]["node"]] = dict(TYPE="ext4")
                if case == "signature": self.signatures = [dict(type="gpt")]
                if case == "mounted": self.mounted = True
                if case == "holder": self.children = True
                if case == "missing": self.table["partitions"].pop()
                if case == "changed": self.table["partitions"][0]["size"] += 1
                if case == "other-disk": self.table["id"] = "foreign"
                if case == "staged": (self.p.STATE / "windows-staging.json").write_text("{}")
                with self.assertRaises(self.p.Stop):
                    self.p.recover_partition_plan(self.disk, plan, adopt=True)
                self.assertFalse(self.receipt.exists())
                self.assertFalse(self.formats())
                self.assertFalse(self.appends())

    def test_legacy_probe_failure_cannot_authorize_recovery(self):
        plan = self.legacy_plan()
        with patch.object(self.p, "filesystem", side_effect=self.p.Stop("failed", "unreadable")):
            with self.assertRaisesRegex(self.p.Stop, "unreadable"):
                self.p.recover_partition_plan(self.disk, plan, adopt=True)
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.formats())

    def test_inspection_entry_point_does_not_change_status_or_start_preparation(self):
        plan = self.legacy_plan()
        file = self.root / "reviewed-plan.json"
        file.write_text(json.dumps(plan))
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                if invalid:
                    self.signatures = [dict(type="ntfs")]
                with patch.object(self.p.sys, "argv", ["monet-prepare-windows", "--inspect-recovery", str(file)]), \
                        patch.object(self.p.os, "geteuid", return_value=0), \
                        patch.object(self.p.Path, "is_dir", return_value=True), \
                        patch.object(self.p, "root_disk", return_value=self.disk), \
                        patch.object(self.p, "set_status") as status, \
                        patch.object(self.p, "make_partitions") as prepare:
                    self.assertEqual(self.p.prepare_main(), 2 if invalid else 0)
                    status.assert_not_called()
                    prepare.assert_not_called()
                self.assertFalse(self.receipt.exists())

    def test_unavailable_media_stops_before_recovery_receipt_or_any_storage_changes(self):
        plan = self.legacy_plan()
        file = self.root / "reviewed-plan.json"
        file.write_text(json.dumps(plan))
        self.p.STATUS = self.p.STATE / "windows-setup"
        self.p.WORK = self.root / "downloads"
        for kind in ("blocked", "interrupted", "missing-iso", "empty-iso"):
            with self.subTest(kind=kind):
                iso = self.root / "input.iso"
                iso.unlink(missing_ok=True)
                if kind == "empty-iso": iso.touch()
                args = ["monet-prepare-windows", "--recover-plan", str(file)]
                if kind.endswith("iso"): args += ["--iso", str(iso)]
                with patch.object(self.p.sys, "argv", args), \
                        patch.object(self.p.os, "geteuid", return_value=0), \
                        patch.object(self.p.Path, "is_dir", return_value=True), \
                        patch.object(self.p, "root_disk", return_value=self.disk), \
                        patch.object(self.p, "require_setup_payload"), \
                        patch.object(self.p, "resume_staged_setup", return_value=None), \
                        patch.object(self.p, "windows_download_link", side_effect=self.p.Stop("download-failed", "blocked") if kind == "blocked" else None,
                                     return_value=("https://example.invalid/windows.iso", "English")), \
                        patch.object(self.p, "download", side_effect=self.p.Stop("download-failed", "interrupted")):
                    self.assertEqual(self.p.prepare_main(), 2)
                self.assertFalse(self.receipt.exists())
                self.assertFalse(self.formats())
                self.assertFalse(self.appends())

    def test_legacy_recovery_refuses_preformatted_input_and_existing_record_changes(self):
        plan = self.legacy_plan()
        wrong = copy.deepcopy(plan)
        wrong["owned"][0]["phase"] = "formatted"
        with self.assertRaisesRegex(self.p.Stop, "unformatted partition plan"):
            self.p.recover_partition_plan(self.disk, wrong, adopt=True)
        self.p.save_partition_plan(wrong)
        self.table["partitions"][1]["size"] -= 1
        with self.assertRaises(self.p.Stop):
            self.p.recover_partition_plan(self.disk, plan, adopt=True)
        self.assertEqual(json.loads(self.receipt.read_text()), wrong)
        self.assertFalse(self.formats())

    def test_changed_disk_reused_partition_or_new_user_partition_is_never_formatted(self):
        self.pending()
        original = copy.deepcopy(self.table)
        for change in (lambda: self.table.update(id="different-disk"),
                       lambda: self.table["partitions"][1].update(size=10),
                       lambda: self.table["partitions"][1].update(uuid="22222222-2222-2222-2222-222222222222"),
                       lambda: self.table["partitions"].append(dict(self.table["partitions"][0], start=1, uuid="other"))):
            self.table = copy.deepcopy(original)
            change()
            with self.assertRaises(self.p.Stop):
                self.p.make_partitions(self.disk)
            self.assertFalse(self.formats())

    def test_foreign_second_filesystem_is_detected_before_first_format(self):
        self.pending()
        setup = self.table["partitions"][2]["node"]
        self.fs[setup] = dict(TYPE="ext4", UUID="personal-data")
        with self.assertRaisesRegex(self.p.Stop, "unexpected filesystem"):
            self.p.make_partitions(self.disk)
        self.assertFalse(self.formats())

    def test_missing_previously_formatted_setup_stops_before_any_new_format(self):
        self.pending()
        plan = json.loads(self.receipt.read_text())
        plan["owned"][1].update(phase="formatted", fs_uuid="lost-filesystem")
        self.p.save_partition_plan(plan)
        with self.assertRaisesRegex(self.p.Stop, "filesystem is missing"):
            self.p.make_partitions(self.disk)
        self.assertFalse(self.formats())

    def test_mounted_and_active_device_mapper_targets_are_rejected(self):
        self.pending()
        self.mounted = True
        with self.assertRaisesRegex(self.p.Stop, "in use"):
            self.p.make_partitions(self.disk)
        self.mounted, self.children = False, True
        with self.assertRaisesRegex(self.p.Stop, "in use"):
            self.p.make_partitions(self.disk)
        self.assertFalse(self.formats())

    def test_completed_or_changed_filesystem_is_not_reformatted(self):
        self.p.make_partitions(self.disk)
        count = len(self.formats())
        win = self.table["partitions"][1]["node"]
        saved = dict(self.fs[win])
        for replacement in ({}, {**saved, "UUID": "replacement"}, {**saved, "LABEL": "Windows"}):
            self.fs[win] = replacement
            with self.assertRaises(self.p.Stop):
                self.p.make_partitions(self.disk)
            self.assertEqual(len(self.formats()), count)
        self.fs[win], self.windows = saved, True
        with self.assertRaisesRegex(self.p.Stop, "automatic reinstall"):
            self.p.make_partitions(self.disk)
        self.assertEqual(len(self.formats()), count)

    def test_receipt_failure_does_not_change_the_partition_table(self):
        with patch.object(self.p, "save_partition_plan", side_effect=OSError("fixture: full disk")):
            with self.assertRaises(OSError):
                self.p.make_partitions(self.disk)
        self.assertFalse(self.appends())
        self.assertFalse(self.formats())

    def test_device_removal_between_preflight_and_format_cannot_format_a_stale_path(self):
        self.pending()
        original = self.p.mapped_partitions
        calls = []
        def remove_before_second_read(disk, plan):
            calls.append(True)
            if len(calls) == 2:
                self.table["partitions"].pop()
            return original(disk, plan)
        self.p.mapped_partitions = remove_before_second_read
        with self.assertRaisesRegex(self.p.Stop, "disappeared before formatting"):
            self.p.make_partitions(self.disk)
        self.assertFalse(self.formats())

    def test_stale_kernel_path_with_matching_cached_guid_is_rejected(self):
        self.pending()
        original = self.p.partitions
        def stale(disk):
            parts = original(disk)
            parts[1]["path"] = "/dev/someone-elses-data"
            return parts
        self.p.partitions = stale
        with self.assertRaisesRegex(self.p.Stop, "kernel's Windows partition identity"):
            self.p.make_partitions(self.disk)
        self.assertFalse(self.formats())

    def test_concurrent_setup_does_not_touch_status_or_storage(self):
        self.p.MOUNT.mkdir()
        with (self.p.MOUNT / "windows-setup.lock").open("a") as lock, \
                patch.object(self.p.os, "geteuid", return_value=0), patch.object(self.p, "prepare_main") as main:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.p.main(), 2)
            main.assert_not_called()

    def test_deployment_handoff_binds_both_filesystems_and_the_existing_shared_efi(self):
        esp = self.table["partitions"][0]
        esp["type"] = self.p.EFI_SYSTEM
        self.fs[esp["node"]] = dict(TYPE="vfat", VERSION="FAT32", UUID="CAFE-1234")
        self.p.make_partitions(self.disk)
        count = len(self.formats())
        manifest = self.p.deployment_manifest(self.disk)
        self.assertEqual(manifest["disk_guid"], self.table["id"])
        self.assertEqual(manifest["efi"]["guid"], esp["uuid"])
        self.assertEqual(manifest["efi"]["filesystem_id"], "CAFE-1234")
        self.assertEqual(manifest["windows"]["offset"], self.table["partitions"][1]["start"] * 512)
        self.assertEqual(manifest["setup"]["filesystem_id"], "1234-ABCD")
        self.assertEqual(len(self.formats()), count)
        self.fs[esp["node"]]["VERSION"] = "FAT16"
        with self.assertRaisesRegex(self.p.Stop, "verified FAT32"):
            self.p.deployment_manifest(self.disk)

    def test_handoff_rejects_missing_or_ambiguous_efi(self):
        self.p.make_partitions(self.disk)
        with self.assertRaisesRegex(self.p.Stop, "identified uniquely"):
            self.p.deployment_manifest(self.disk)

    def test_handoff_rejects_stale_efi_device_and_invalid_filesystem_ids(self):
        esp = self.table["partitions"][0]
        esp["type"] = self.p.EFI_SYSTEM
        self.fs[esp["node"]] = dict(TYPE="vfat", VERSION="FAT32", UUID="CAFE-1234")
        self.p.make_partitions(self.disk)
        original = self.p.partitions
        def stale(disk):
            rows = original(disk)
            rows[0]["path"] = "/dev/not-the-shared-efi"
            return rows
        with patch.object(self.p, "partitions", side_effect=stale):
            with self.assertRaisesRegex(self.p.Stop, "shared EFI identity"):
                self.p.deployment_manifest(self.disk)
        self.fs[esp["node"]]["UUID"] = "not-a-volume-id"
        with self.assertRaisesRegex(self.p.Stop, "invalid identity"):
            self.p.deployment_manifest(self.disk)
        self.fs[esp["node"]]["UUID"] = "CAFE-1234"
        setup = self.table["partitions"][-1]["node"]
        self.fs[setup]["VERSION"] = "FAT16"
        with self.assertRaisesRegex(self.p.Stop, "verified FAT32"):
            self.p.deployment_manifest(self.disk)


class FilesystemProbe(unittest.TestCase):
    def test_unreadable_or_conflicting_probe_is_not_treated_as_empty(self):
        prepare = load("linux/libexec/monet-prepare-windows", "prepare_probe_fixture")
        with tempfile.NamedTemporaryFile() as file:
            file.write(bytes(4096)); file.flush()
            for code, out, error, empty in ((2, "", "", True), (2, "", "read error", False),
                                           (8, "TYPE=ntfs", "", False), (4, "", "", False)):
                with self.subTest(code=code, error=error), patch.object(prepare.subprocess, "run", return_value=
                        subprocess.CompletedProcess([], code, out, error)):
                    if empty:
                        self.assertEqual(prepare.filesystem(file.name), {})
                    else:
                        with self.assertRaises(prepare.Stop):
                            prepare.filesystem(file.name)


@unittest.skipUnless(shutil.which("sfdisk") and shutil.which("blkid"), "native GPT/blkid tools")
class NativeImages(unittest.TestCase):
    @unittest.skipUnless(shutil.which("mkfs.ntfs") and shutil.which("mkfs.vfat"), "native NTFS/FAT formatters")
    def test_real_filesystems_are_verified_and_an_interrupted_receipt_does_not_reformat(self):
        with tempfile.TemporaryDirectory(prefix="monet-fs-fixture-") as tmp:
            root = Path(tmp)
            prepare = load("linux/libexec/monet-prepare-windows", "prepare_native_fs")
            prepare.STATE = root / "state"
            for kind, label in (("ntfs", "MONETWIN"), ("vfat", "MONETSETUP")):
                disk = root / (kind + ".img")
                with disk.open("wb") as output:
                    output.truncate(64 * 1024**2)
                # Force is used only by this fixture to create a regular-file NTFS image.
                # Production formatting deliberately omits that mounted-device override.
                args = ["mkfs.ntfs", "-F", "-Q", "-L", label] if kind == "ntfs" else ["mkfs.vfat", "-F", "32", "-n", label]
                subprocess.run([*args, str(disk)], capture_output=True, check=True, timeout=30)
                found = prepare.filesystem(disk)
                self.assertEqual((found["TYPE"], found["LABEL"]), (kind, label))
                wanted = dict(phase="formatting", fstype=kind, fslabel=label)
                with patch.object(prepare, "run", side_effect=AssertionError("must not format on recovery")):
                    prepare.prepare_filesystem({"path": str(disk)}, wanted, {"owned": [wanted]})
                self.assertEqual(wanted["phase"], "formatted")
                self.assertEqual(wanted["fs_uuid"], found["UUID"])

    def test_real_gpt_guids_survive_lost_discovery_and_partial_append(self):
        with tempfile.TemporaryDirectory(prefix="monet-gpt-fixture-") as tmp:
            root = Path(tmp)
            disk = root / "disk.img"
            with disk.open("wb") as file:
                file.truncate(128 * 1024**2)
            subprocess.run(["sfdisk", str(disk)], input="label: gpt\nstart=2048, size=2048, name=Keep\n",
                           text=True, capture_output=True, check=True, timeout=10)
            prepare = load("linux/libexec/monet-prepare-windows", "prepare_native_gpt")
            prepare.STATE, prepare.LOG = root / "state", root / "log"
            prepare.MIN_WINDOWS_MIB, prepare.SETUP_MIB = 16, 8
            prepare.sector_size = lambda disk: 512
            table = prepare.partition_table(disk)
            plan = prepare.new_partition_plan(disk, table)
            prepare.save_partition_plan(plan)
            owned = plan["owned"][0]
            first = f'start={owned["start"]}, size={owned["size"]}, type={owned["type"]}, uuid={owned["uuid"]}, name="{owned["name"]}"\n'
            subprocess.run(["sfdisk", "--append", str(disk)], input=first, text=True, capture_output=True, check=True, timeout=10)
            missing = prepare.check_partition_plan(prepare.partition_table(disk), plan)
            self.assertEqual([p["uuid"] for p in missing], [plan["owned"][1]["uuid"]])
            second = missing[0]
            line = f'start={second["start"]}, size={second["size"]}, type={second["type"]}, uuid={second["uuid"]}, name="{second["name"]}"\n'
            subprocess.run(["sfdisk", "--append", str(disk)], input=line, text=True, capture_output=True, check=True, timeout=10)
            after = prepare.partition_table(disk)
            self.assertEqual(prepare.check_partition_plan(after, plan), [])
            self.assertEqual(prepare.part_identity(after["partitions"][0]), prepare.part_identity(table["partitions"][0]))
            blank = root / "empty-partition"
            blank.write_bytes(bytes(8192))
            self.assertEqual(prepare.filesystem(blank), {})


if __name__ == "__main__":
    unittest.main()
