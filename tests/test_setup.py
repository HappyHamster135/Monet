"""Monet Setup, the installer on the USB stick: its choices and steps, with
a pretend PC (no disks are touched).

    python3 -m unittest discover -s tests
"""

import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "setup"))
sys.dont_write_bytecode = True

from monet_setup import disks, install, network, system  # noqa: E402

GB = 10**9


def disk(name, size, tran="nvme", rm=False, children=(), model="Samsung SSD 990 PRO"):
    return {"name": name, "path": f"/dev/{name}", "size": size, "type": "disk", "rm": rm, "ro": False,
            "tran": tran, "model": model, "children": list(children)}


def part(name, parttype="", fstype="", label="", mounts=()):
    return {"name": name, "path": f"/dev/{name}", "type": "part", "parttype": parttype, "fstype": fstype,
            "label": label, "mountpoints": list(mounts)}


STICK = disk("sda", 32 * GB, tran="usb", rm=True, model="SanDisk",
             children=[part("sda1", label="Monet-0.7.0", mounts=["/run/initramfs/live"])])
NVME = disk("nvme0n1", 1000 * GB, children=[part("nvme0n1p1", parttype=disks.EFI_TYPE, fstype="vfat"),
                                            part("nvme0n1p3", fstype="ntfs")])


class Disks(unittest.TestCase):
    def test_never_the_stick(self):
        self.assertEqual([d["name"] for d in disks.disks([STICK, NVME])], ["nvme0n1"])

    def test_never_the_stick_even_when_it_looks_internal(self):
        inside = dict(STICK, tran="sata", rm=False)
        self.assertEqual([d["name"] for d in disks.disks([inside, NVME])], ["nvme0n1"])

    def test_never_the_stick_by_its_labels_alone(self):
        stick = disk("sdc", 16 * GB, tran="sata", children=[part("sdc1", label="Monet-0.7.0"),
                                                            part("sdc2", label="MONETEFI")])
        self.assertEqual([d["name"] for d in disks.disks([stick, NVME])], ["nvme0n1"])

    def test_a_pc_that_has_monet_can_get_it_again(self):
        again = disk("nvme1n1", 1000 * GB, children=[part("nvme1n1p3", label="monet", fstype="btrfs"),
                                                     part("nvme1n1p4", label="MONETWIN", fstype="ntfs"),
                                                     part("nvme1n1p5", label="MONETSETUP", fstype="vfat")])
        self.assertEqual([d["name"] for d in disks.disks([STICK, again])], ["nvme1n1"])

    def test_usb_disks_only_when_nothing_else(self):
        usb = disk("sdb", 500 * GB, tran="usb")
        self.assertEqual([d["name"] for d in disks.disks([STICK, usb])], ["sdb"])
        self.assertEqual([d["name"] for d in disks.disks([STICK, usb, NVME])], ["nvme0n1"])

    def test_erase_leaves_windows_its_share(self):
        plan = disks.plan_erase(1000 * GB)
        size_mib = 1000 * GB // disks.MIB
        free = size_mib - plan["efi"] - plan["boot"] - plan["monet"]
        # What monet-prepare-windows needs: 64 GiB for Windows and 8 for setup.
        self.assertGreaterEqual(free, plan["windows"] + disks.WINDOWS_SETUP_MIB)
        self.assertGreaterEqual(plan["windows"], 100 * 1024)
        self.assertGreaterEqual(plan["monet"], disks.MIN_MONET_MIB)

    def test_small_disk_is_all_monet_and_tiny_disk_is_refused(self):
        self.assertEqual(disks.plan_erase(128 * GB)["windows"], 0)
        self.assertIsNone(disks.plan_erase(64 * GB))

    def test_keep_needs_room_and_an_efi_partition(self):
        plan, why = disks.plan_keep(NVME, 200 * GB)
        self.assertEqual(why, "")
        self.assertGreaterEqual(plan["monet"], disks.MIN_MONET_MIB)
        plan, why = disks.plan_keep(NVME, 20 * GB)
        self.assertIsNone(plan)
        self.assertIn("Disk Management", why)
        plan, why = disks.plan_keep(disk("sdb", 500 * GB), 200 * GB)
        self.assertIn("EFI", why)

    def test_keep_makes_room_by_shrinking_windows(self):
        efi = part("nvme0n1p1", parttype=disks.EFI_TYPE, fstype="vfat")
        pc = disk("nvme0n1", 1000 * GB, children=[efi, dict(part("nvme0n1p3", fstype="ntfs"), size=999 * GB)])
        # Windows uses 300 GB: it keeps that and half the rest; Monet gets the other half.
        plan, why = disks.plan_keep(pc, 0, shrink=lambda path: (300 * GB, ""))
        self.assertEqual(why, "")
        self.assertEqual(plan["shrink"]["partition"], "/dev/nvme0n1p3")
        self.assertAlmostEqual(plan["shrink"]["to"] / GB, 649.5, delta=1)
        self.assertEqual(plan["shrink"]["to"] % disks.MIB, 0)
        self.assertGreaterEqual(plan["monet"], disks.MIN_MONET_MIB)
        # Nearly full: Monet still gets what it needs, and Windows keeps 30 GiB to grow into.
        plan, why = disks.plan_keep(pc, 0, shrink=lambda path: (880 * GB, ""))
        self.assertGreaterEqual(plan["monet"], disks.MIN_MONET_MIB)
        self.assertGreaterEqual(plan["shrink"]["to"], 880 * GB + disks.WINDOWS_ROOM_MIB * disks.MIB)
        # Full: it says how much to free up.
        plan, why = disks.plan_keep(pc, 0, shrink=lambda path: (960 * GB, ""))
        self.assertIsNone(plan)
        self.assertIn("64 GB", why)
        # Asleep (Fast Startup) or BitLocker: it says what to do instead.
        asleep = disks.smallest_size("ERROR: Windows is hibernated, refused to resize.")
        self.assertIn("Shift", disks.plan_keep(pc, 0, shrink=lambda path: asleep)[1])
        locked = disk("nvme0n1", 1000 * GB, children=[efi, dict(part("nvme0n1p3", fstype="BitLocker"), size=999 * GB)])
        self.assertIn("BitLocker", disks.plan_keep(locked, 0, shrink=lambda path: (1, ""))[1])
        self.assertEqual(disks.smallest_size("You might resize at 25369563136 bytes or 25370 MB (freeing 474626 MB)."),
                         (25369563136, ""))
        # Enough free space already: nothing in Windows changes.
        self.assertNotIn("shrink", disks.plan_keep(pc, 200 * GB, shrink=lambda path: (300 * GB, ""))[0])

    def test_windows_files_of_the_account_used_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel, data in (("Users/Ann/Documents/letter.txt", "x" * 10), ("Users/Ann/Desktop/desktop.ini", "x"),
                              ("Users/Ann/OneDrive/Pictures/sea.jpg", "x" * 20), ("Users/Bob/Documents/b.txt", "x"),
                              ("Users/Public/Documents/p.txt", "x"), ("Users/Ann/NTUSER.DAT", ""),
                              ("Users/Bob/NTUSER.DAT", "")):
                (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp) / rel).write_text(data)
            os.utime(Path(tmp) / "Users/Bob/NTUSER.DAT", (1, 1))
            found = disks.your_files(tmp)
            self.assertEqual(found["person"], "Ann")
            # OneDrive keeps Ann's pictures.
            self.assertEqual(found["folders"], {"Desktop": "Users/Ann/Desktop", "Documents": "Users/Ann/Documents",
                                                "Pictures": "Users/Ann/OneDrive/Pictures"})
            self.assertEqual(found["total"], 31)
            # Copied while installing; desktop.ini stays behind.
            dest = Path(tmp) / "home/.local/share/monet/from-windows"
            done, stayed = install.copy_files(tmp, found["folders"], dest)
            self.assertEqual((done, stayed), (30, 0))
            self.assertEqual((dest / "Pictures/sea.jpg").read_text(), "x" * 20)
            self.assertFalse((dest / "Desktop/desktop.ini").exists())
        self.assertIsNone(disks.your_files("/nonexistent"))

    def test_offer(self):
        offered = disks.offer([STICK, NVME], free=lambda path: (2048, 30 * GB // 512, 512),
                              shrink=lambda path: (None, ""), files=lambda d: None)
        self.assertEqual(len(offered), 1)
        self.assertEqual(offered[0]["label"], "Samsung SSD 990 PRO · 1 TB")
        self.assertTrue(offered[0]["hasWindows"])
        self.assertIsNone(offered[0]["keep"])

    def test_partition_names(self):
        self.assertEqual(install.partition_path("/dev/nvme0n1", 3), "/dev/nvme0n1p3")
        self.assertEqual(install.partition_path("/dev/sda", 3), "/dev/sda3")


class Choices(unittest.TestCase):
    def test_every_language_has_its_keyboard(self):
        layouts = {k[1] for k in system.KEYBOARDS}
        for name, locale, layout, zone in system.LANGUAGES:
            self.assertIn(layout, layouts, name)
            self.assertIn("/", zone)
            self.assertTrue(locale.endswith(".UTF-8"))
            system.keyboard_for(system.LANGUAGES.index((name, locale, layout, zone)))

    def test_every_language_has_its_words(self):
        for name, locale, *_ in system.LANGUAGES:
            code = locale.split(".")[0]
            if code.startswith("en_"):
                continue
            built = [c for c in (code, code.split("_")[0])
                     if (ROOT / "setup/locale" / c / "LC_MESSAGES/monet-setup.mo").is_file()]
            self.assertTrue(built, name)

    def test_setup_speaks_the_language_picked(self):
        from monet_setup import words
        try:
            words.use("sv_SE.UTF-8")
            self.assertNotEqual(words.tr("%1 of %2 GB", 3, 8), "3 of 8 GB")
            self.assertIn("3", words.tr("%1 of %2 GB", 3, 8))
            words.use("pt_PT.UTF-8")  # Portugal's words are "pt"
            self.assertNotEqual(words._("Language"), "Language")
            words.use("xx_XX.UTF-8")
            self.assertEqual(words.tr("%1 of %2 GB", 3, 8), "3 of 8 GB")
        finally:
            words.use("")

    def test_keyboards_without_latin_letters_keep_us(self):
        self.assertEqual(system.xkb("ru", ""), ("ru,us", ",", "grp:alt_shift_toggle"))
        self.assertEqual(system.xkb("se", ""), ("se", "", ""))
        self.assertEqual(system.xkb("us", "intl"), ("us", "intl", ""))
        self.assertLessEqual(system.NON_LATIN, {k[1] for k in system.KEYBOARDS})

    def test_account_names(self):
        account_name = system.account_name
        self.assertEqual(account_name("Jonas Wenell"), "jonas")
        self.assertEqual(account_name("Élodie Monet"), "elodie")
        self.assertEqual(account_name("李"), "player")
        self.assertEqual(account_name("3D Artist"), "player3d")

    def test_wifi_listing(self):
        listing = "*:Harbor:80:WPA2\n:Harbor:90:WPA2\n:Giverny 5G:70:WPA3\n:Le\\:Havre:50:\n::40:WPA2\n"
        nets = network.parse_wifi(listing)
        self.assertEqual([n["name"] for n in nets], ["Harbor", "Giverny 5G", "Le:Havre"])
        self.assertTrue(nets[0]["active"])
        self.assertFalse(nets[2]["secure"])


class Install(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.saved = install.run

        def fake_run(*args, check=True, input=None, timeout=1800, quiet=False):
            self.commands.append([str(a) for a in args])
            return ""

        install.run = fake_run

    def tearDown(self):
        install.run = self.saved

    def test_erase_layout(self):
        plan = {"disk": "/dev/nvme0n1", "mode": "erase", "sizes": disks.plan_erase(1000 * GB)}
        with redirect_stdout(io.StringIO()):
            parts = install.prepare_erase(plan)
        self.assertEqual(parts, {"efi": "/dev/nvme0n1p1", "boot": "/dev/nvme0n1p2", "monet": "/dev/nvme0n1p3"})
        sgdisk = next(c for c in self.commands if c[0] == "sgdisk" and "-n" in c)
        self.assertIn("1:EF00", sgdisk)
        self.assertIn(f"3:0:+{plan['sizes']['monet']}M", sgdisk)
        self.assertIn(["mkfs.fat", "-F", "32", "-n", "EFI", "/dev/nvme0n1p1"], self.commands)

    def test_firmware_lists_monet_not_fedora(self):
        listing = ("BootOrder: 0001,0000\n"
                   "Boot0000* Windows Boot Manager\tHD(1,GPT,aaaa-1111,0x800,0x32000)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n"
                   "Boot0001* Fedora\tHD(1,GPT,cccc-2222,0x800,0x200000)/File(\\EFI\\fedora\\shimx64.efi)\n")

        def fake_run(*args, check=True, input=None, timeout=1800, quiet=False):
            self.commands.append([str(a) for a in args])
            return {"blkid": "CCCC-2222\n", "efibootmgr": listing if "-v" in args else ""}.get(args[0], "")

        install.run = fake_run
        install.boot_entry({"disk": "/dev/nvme0n1"}, {"efi": "/dev/nvme0n1p1"})
        self.assertIn(["efibootmgr", "-b", "0001", "-B"], self.commands)
        self.assertNotIn(["efibootmgr", "-b", "0000", "-B"], self.commands)
        create = next(c for c in self.commands if "--create" in c)
        self.assertEqual(create[create.index("--label") + 1], "Monet")
        self.assertEqual(create[create.index("--part") + 1], "1")

    def test_stalled_download_starts_again(self):
        clock = types.SimpleNamespace(now=0.0)
        fake_time = types.SimpleNamespace(time=lambda: clock.now, sleep=lambda n: setattr(clock, "now", clock.now + n))
        killed = []

        class Stuck:
            returncode = None
            def poll(self):
                return None
            def kill(self):
                killed.append(clock.now)
            def wait(self):
                pass

        saved = install.received
        install.received = lambda: 1000
        try:
            with redirect_stdout(io.StringIO()):
                self.assertFalse(install.copy_once("ghcr.io/x/monet:latest", 5 * GB, 0,
                                                   popen=lambda *a, **k: Stuck(), clock=fake_time))
        finally:
            install.received = saved
        self.assertTrue(killed)
        self.assertLessEqual(killed[0], install.STALL + 5)

    def test_download_reports_progress(self):
        clock = types.SimpleNamespace(now=0.0)
        fake_time = types.SimpleNamespace(time=lambda: clock.now, sleep=lambda n: setattr(clock, "now", clock.now + n))

        class Moving:
            returncode = None
            def poll(self):
                self.returncode = 0 if clock.now > 60 else None
                return self.returncode

        saved = install.received
        install.received = lambda: int(clock.now * 10**7)
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                self.assertTrue(install.copy_once("ghcr.io/x/monet:latest", 5 * GB, 0,
                                                  popen=lambda *a, **k: Moving(), clock=fake_time))
        finally:
            install.received = saved
        events = [json.loads(line) for line in out.getvalue().splitlines() if '"phase"' in line]
        self.assertEqual(events[-1]["total"], 5 * GB)
        self.assertGreater(events[-1]["got"], 5 * 10**8)
        self.assertGreater(events[-1]["eta"], 0)

    def test_retry_remembers_the_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = install.STATE
            install.STATE = Path(tmp) / "install.json"
            try:
                plan = {"disk": "/dev/sda", "mode": "erase"}
                parts = {"efi": "/dev/sda1", "boot": "/dev/sda2", "monet": "/dev/sda3"}
                install.remember(plan, parts)
                self.assertEqual(install.remembered(plan), parts)
                self.assertIsNone(install.remembered({"disk": "/dev/sdb", "mode": "erase"}))
                self.assertIsNone(install.remembered({"disk": "/dev/sda", "mode": "keep"}))
            finally:
                install.STATE = saved


class ThisPC(unittest.TestCase):
    def sysfs(self, root, cards):
        for i, (cls, vendor, device) in enumerate(cards):
            dev = Path(root) / f"0000-0{i}-00.0"  # sysfs names have colons, which Windows refuses
            dev.mkdir(parents=True)
            for name, value in (("class", cls), ("vendor", f"0x{vendor}"), ("device", f"0x{device}")):
                (dev / name).write_text(value + "\n")
        return Path(root)

    def test_graphics_and_memory(self):
        from monet_setup import pc
        with tempfile.TemporaryDirectory() as tmp:
            # An RTX 4090 and a network card: only the graphics counts.
            devices = self.sysfs(tmp, [("0x030000", "10de", "2684"), ("0x020000", "8086", "15f3")])
            self.assertEqual(pc.graphics(devices), [("10de", "2684")])
            meminfo = Path(tmp) / "meminfo"
            meminfo.write_text("MemTotal:        3884524 kB\nMemFree:  1 kB\n")
            self.assertAlmostEqual(pc.memory(meminfo), 3.7, places=1)
        self.assertIsNone(pc.memory(Path("/nonexistent/meminfo")))
        rtx2060, gtx1060, gtx1650, intel = ("10de", "1f08"), ("10de", "1c03"), ("10de", "1f82"), ("8086", "9bc4")
        self.assertEqual(pc.check([rtx2060], 16)["oldNvidia"], "")
        self.assertEqual(pc.check([gtx1650, intel], 16)["oldNvidia"], "")
        self.assertEqual(pc.check([gtx1060], 16)["oldNvidia"], "only")
        self.assertEqual(pc.check([intel, gtx1060], 16)["oldNvidia"], "beside")
        self.assertEqual(pc.check([intel], 16)["oldNvidia"], "")
        # The NVIDIA Monet only with a GTX 16 / RTX 20 or newer; everything else gets the AMD and Intel one.
        self.assertEqual([pc.check(c, 16)["newNvidia"] for c in ([rtx2060], [gtx1650, intel], [gtx1060], [intel])],
                         [True, True, False, False])
        image = "ghcr.io/x/monet:latest"
        self.assertEqual(pc.image_for(image, {"newNvidia": True}), image)
        self.assertEqual(pc.image_for(image, {"newNvidia": False}), "ghcr.io/x/monet-amd:latest")
        self.assertEqual(pc.image_for("localhost:5000/monet", {"newNvidia": False}), "localhost:5000/monet-amd")
        self.assertEqual(pc.image_for("ghcr.io/x/monet-amd:0.8.3", {"newNvidia": False}), "ghcr.io/x/monet-amd:0.8.3")

    def test_setup_says_it_before_erasing(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        setup = app.Setup.__new__(app.Setup)
        setup._disks, setup._disk, setup._mode = [{"erase": {"plan": 1}, "keep": None}], 0, "erase"
        setup._pc = {"oldNvidia": "", "memory": 15.5}
        self.assertEqual((app.Setup.pcBlocker.fget(setup), app.Setup.pcNotes.fget(setup)), ("", []))
        self.assertEqual(app.Setup.blocker.fget(setup), "")
        setup._pc = {"oldNvidia": "beside", "memory": 3.7}
        self.assertEqual(app.Setup.pcBlocker.fget(setup), "")
        notes = app.Setup.pcNotes.fget(setup)
        self.assertEqual(len(notes), 2)
        self.assertIn("4 GB", notes[1])
        # Only an old NVIDIA card: the AMD and Intel Monet draws with its open driver, so just a note.
        setup._pc = {"oldNvidia": "only", "memory": 16}
        self.assertEqual(app.Setup.pcBlocker.fget(setup), "")
        self.assertIn("RTX 20", app.Setup.pcNotes.fget(setup)[0])
        # Too little memory: Install can't go ahead.
        setup._pc = {"oldNvidia": "", "memory": 1.8}
        self.assertNotEqual(app.Setup.pcBlocker.fget(setup), "")
        self.assertEqual(app.Setup.blocker.fget(setup), app.Setup.pcBlocker.fget(setup))
        self.assertIn('"image": pc.image_for(IMAGE, self._pc)', (ROOT / "setup/monet_setup/app.py").read_text(encoding="utf-8"))
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        hello = qml.split("id: helloStep", 1)[1].split("Component {", 1)[0]
        self.assertIn("Note { text: setup.pcBlocker; warm: true; visible: text !== \"\" }", hello)
        self.assertIn("model: setup.blocker === \"\" ? setup.pcNotes : []", qml)


class Encrypting(unittest.TestCase):
    """0.9.1: encrypted where the PC's TPM 2.0 unlocks it by itself, with a recovery key shown once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.commands = []
        self.saved = {name: getattr(install, name) for name in ("run", "KEY", "TOP", "TARGET")}
        install.KEY = Path(self.tmp.name) / "run/disk.key"
        install.TOP = str(Path(self.tmp.name) / "top")
        install.TARGET = str(Path(self.tmp.name) / "target")

        def fake_run(*args, check=True, input=None, timeout=1800, quiet=False):
            self.commands.append([str(a) for a in args])
            if args[0] == "blkid":
                return {"/dev/nvme0n1p3": "ab12\n", "/dev/nvme0n1p2": "cd34\n"}.get(str(args[-1]), "")
            return ""

        install.run = fake_run

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(install, name, value)
        self.tmp.cleanup()

    def test_only_with_a_tpm_2(self):
        from monet_setup import pc
        chips = Path(self.tmp.name) / "tpm"
        self.assertFalse(pc.tpm2(chips))
        (chips / "tpm0").mkdir(parents=True)
        (chips / "tpm0/tpm_version_major").write_text("1\n")
        self.assertFalse(pc.tpm2(chips))
        (chips / "tpm0/tpm_version_major").write_text("2\n")
        self.assertTrue(pc.tpm2(chips))
        self.assertTrue(pc.check([], 16, tpm=True)["tpm"])
        app_code = (ROOT / "setup/monet_setup/app.py").read_text(encoding="utf-8")
        self.assertIn('"encrypt": self._encrypt and bool(self._pc.get("tpm")),', app_code)
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("visible: setup.blocker === \"\" && setup.tpm", qml)
        self.assertIn("onClicked: setup.setEncrypt(!setup.encrypt)", qml)

    def test_the_disk_is_encrypted_with_a_key_of_its_own(self):
        plan = {"disk": "/dev/nvme0n1", "mode": "erase", "sizes": disks.plan_erase(1000 * GB), "encrypt": True}
        with redirect_stdout(io.StringIO()):
            parts = install.prepare_disk(plan)
        self.assertEqual(parts["fs"], "/dev/mapper/monet")
        key = str(install.KEY)
        self.assertEqual(len(install.KEY.read_bytes()), 64)
        luks = next(c for c in self.commands if c[:2] == ["cryptsetup", "luksFormat"])
        self.assertEqual(luks[-3:], ["--key-file", key, "/dev/nvme0n1p3"])
        self.assertIn("luks2", luks)
        self.assertIn(["cryptsetup", "open", "--key-file", key, "/dev/nvme0n1p3", "monet"], self.commands)
        self.assertIn(["mkfs.btrfs", "-f", "-q", "-L", "monet", "/dev/mapper/monet"], self.commands)
        self.assertIn(["mount", "/dev/mapper/monet", install.TOP], self.commands)
        # The kernel's command line: the disk, unlocked by the TPM, and by the boot partition's key until then.
        self.assertEqual(install.luks_kargs({"monet": "/dev/nvme0n1p3", "boot": "/dev/nvme0n1p2"}),
                         ["--karg", "rd.luks.uuid=ab12", "--karg", "rd.luks.options=ab12=tpm2-device=auto",
                          "--karg", "rd.luks.key=ab12=/monet-firstboot.key:UUID=cd34"])
        # Not encrypted: the btrfs goes straight on the partition.
        self.commands.clear()
        with redirect_stdout(io.StringIO()):
            parts = install.prepare_disk(dict(plan, encrypt=False))
        self.assertNotIn("fs", parts)
        self.assertFalse(any(c[0] == "cryptsetup" for c in self.commands))

    def test_the_recovery_key_is_added_and_shown_once(self):
        import re
        key = install.recovery_key()
        self.assertRegex(key, r"^([cbdefghijklnrtuv]{8}-){7}[cbdefghijklnrtuv]{8}$")
        self.assertNotEqual(key, install.recovery_key())
        install.KEY.parent.mkdir(parents=True)
        install.KEY.write_bytes(b"k" * 64)
        (Path(install.TARGET) / "boot").mkdir(parents=True)
        with redirect_stdout(io.StringIO()):
            shown = install.seal({"monet": "/dev/nvme0n1p3", "fs": "/dev/mapper/monet"})
        self.assertRegex(shown, r"^([cbdefghijklnrtuv]{8}-){7}[cbdefghijklnrtuv]{8}$")
        self.assertEqual((Path(install.TARGET) / "boot/monet-firstboot.key").read_bytes(), b"k" * 64)
        add = next(c for c in self.commands if c[:2] == ["cryptsetup", "luksAddKey"])
        self.assertEqual(add[3:6], ["--key-file", str(install.KEY), "/dev/nvme0n1p3"])
        # Never on a command line, never left on disk, never in the log.
        self.assertFalse(any(shown in " ".join(c) for c in self.commands))
        self.assertFalse(Path(add[-1]).exists())
        code = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertLess(code.index("emit(recovery=recovery)"), code.index("emit(done=True)"))
        self.assertNotRegex(code, r"log\([^)]*recovery")
        self.assertEqual(install.seal({"monet": "/dev/nvme0n1p3"}), "")
        try:
            from monet_setup import app
        except ImportError:
            return
        setup = app.Setup.__new__(app.Setup)
        setup._phase, setup._progress, setup._status, setup._error, setup._log = "", 0.0, "", "", []
        setup._recovery = ""
        setup.progressChanged = types.SimpleNamespace(emit=lambda: None)
        setup.report({"recovery": shown})
        setup.report({"done": True})
        self.assertEqual(app.Setup.recoveryKey.fget(setup), shown)
        self.assertFalse(any(shown in line for line in setup._log))
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn('installing && phase === "done" && setup.recoveryKey !== "" && !keyKept', qml)
        self.assertIn("readonly property bool ready: kept.checked", qml)


class KeepYourFiles(unittest.TestCase):
    def test_setup_offers_the_files_next_to_windows(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        setup = app.Setup.__new__(app.Setup)
        files = {"person": "Ann", "partition": "/dev/nvme0n1p3", "total": 41 * GB, "fits": True,
                 "folders": {"Documents": "Users/Ann/Documents"}, "sizes": {}}
        keep = {"boot": 2048, "monet": 488000, "shrink": {"partition": "/dev/nvme0n1p3", "from": 999 * GB, "to": 487 * GB}}
        setup._disks, setup._disk, setup._mode, setup._bring = [{"keep": keep, "files": files}], 0, "keep", True
        self.assertIn("999 GB", app.Setup.roomNote.fget(setup))
        self.assertIn("41 GB", app.Setup.files.fget(setup)["text"])
        self.assertEqual(setup._files_plan(), {"partition": "/dev/nvme0n1p3", "folders": files["folders"],
                                               "total": 41 * GB})
        # Not ticked, too big, or erasing: nothing comes along.
        setup._bring = False
        self.assertIsNone(setup._files_plan())
        setup._bring, files["fits"] = True, False
        self.assertIsNone(setup._files_plan())
        self.assertFalse(app.Setup.files.fget(setup)["fits"])
        setup._mode = "erase"
        self.assertIsNone(setup._files_plan())
        self.assertEqual(app.Setup.roomNote.fget(setup), "")
        self.assertEqual(app.PHASES["files"][1:], (0.95, 0.99))
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("onClicked: setup.setBring(!setup.bring)", qml)

    def test_windows_drive_is_shrunk_file_system_first(self):
        code = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        shrink = code.split("def shrink_windows", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(shrink.index('"--no-action"'), shrink.index('run("ntfsresize", "--force"'))
        self.assertLess(shrink.index('run("ntfsresize", "--force"'), shrink.index('run("sfdisk"'))
        packages = (ROOT / "image/setup/packages.txt").read_text()
        for name in ("ntfsprogs", "ntfs-3g", "systemd-pam", "seatd"):
            self.assertIn(f"\n{name}\n", packages)
        self.assertIn("seat=(seatd-launch --)", (ROOT / "image/setup/files/usr/libexec/monet-setup-session").read_text())


class Window(unittest.TestCase):
    def test_progress_events_become_words(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        os.environ["MONET_SETUP_STATE"] = "/nonexistent/state.json"
        setup = app.Setup.__new__(app.Setup)
        setup._phase, setup._progress, setup._status, setup._error, setup._log = "", 0.0, "", "", []
        setup.progressChanged = types.SimpleNamespace(emit=lambda: None)
        setup.report({"phase": "download", "fraction": 0.5, "got": 2.6 * GB, "total": 5.7 * GB, "eta": 540})
        self.assertEqual(setup._status, "Downloading Monet · 2.6 of 5.7 GB · about 9 minutes left")
        start, end = app.PHASES["download"][1:]
        self.assertAlmostEqual(setup._progress, start + (end - start) * 0.5)
        setup.report({"done": True})
        self.assertEqual(setup._phase, "done")

    def test_your_apps_go_into_the_plan(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        setup = app.Setup.__new__(app.Setup)
        setup._apps = [ticked for *_, ticked in app.APPS]
        setup.changed = types.SimpleNamespace(emit=lambda: None)
        everyday = [app_id for app_id, _, _, ticked in app.APPS if ticked]
        self.assertEqual(setup.picked_apps(), everyday)
        office = next(i for i, (app_id, *_) in enumerate(app.APPS) if app_id == "org.libreoffice.LibreOffice")
        setup.toggleApp(office)
        setup.toggleApp(0)
        self.assertEqual(setup.picked_apps(), everyday[1:] + ["org.libreoffice.LibreOffice"])
        self.assertEqual(len({app_id for app_id, *_ in app.APPS}), len(app.APPS))
        # A PC that never chose gets what Setup ticks to start with, and the built-in ones
        # where Monet hasn't built them in; what's built in is shown, never chosen.
        script = (ROOT / "linux/libexec/monet-apps").read_text()
        built_in = [app_id for app_id, _ in app.BUILT_IN]
        self.assertIn(f'EVERYDAY="{" ".join(everyday + built_in)}"', script)
        self.assertIn('[ -f "/usr/share/applications/$app.desktop" ] && continue', script)
        shown = app.Setup.apps.fget(setup)
        self.assertEqual([a["name"] for a in shown if a["index"] < 0], [name for _, name in app.BUILT_IN])
        self.assertTrue(all(a["picked"] and a["everyday"] for a in shown if a["index"] < 0))
        image = (ROOT / "image/Containerfile").read_text()
        for package in ("gwenview", "okular", "haruna", "elisa-player", "kcalc", "ark"):
            self.assertIn(f" {package}", image)
        # The step sits between the person and Ready, and install writes the list for monet-apps.
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("[helloStep, wifiStep, personStep, appsStep, readyStep][step]", qml)
        self.assertIn("readonly property bool installing: step === 5", qml)
        self.assertIn("onClicked: if (!builtIn) setup.toggleApp(modelData.index)", qml)
        configure = (ROOT / "setup/monet_setup/install.py").read_text()
        self.assertIn('write(var / "lib/monet/apps", "".join(f"{app}\\n" for app in plan.get("apps", [])))', configure)

    def test_all_set_explains_the_first_start(self):
        # The blue screen at the first start, with the password the key was queued with.
        done = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8").split("id: doneStep", 1)[1].split("Component {", 1)[0]
        self.assertIn("Enroll MOK", done)
        self.assertIn(install.MOK_PASSWORD, done)
        self.assertIn("Continue boot", done)
        self.assertNotIn("any key", done.lower())  # install's --timeout -1 skips shim's "Press any key"


class TheStick(unittest.TestCase):
    """0.9.1's Setup failed at bootc: it reads prepare-root.conf from the stick, not the image."""

    def test_the_stick_carries_the_images_bootc_settings(self):
        workflow = (ROOT / ".github/workflows/image.yml").read_text(encoding="utf-8")
        self.assertIn("usr/lib/ostree/prepare-root.conf etc/ostree/prepare-root.conf usr/lib/bootc/install", workflow)
        self.assertEqual(workflow.count("name: bootc-settings"), 2)   # uploaded by image, taken by setup
        build = (ROOT / "image/setup/build.sh").read_text(encoding="utf-8")
        self.assertIn('tar -xf "$SETTINGS" -C "$ROOT"', build)
        self.assertIn('[ ! -e "$ROOT/usr/lib/ostree/prepare-root.conf" ]', build)

    def test_why_an_install_stopped_is_easy_to_see(self):
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("onVisibleChanged: if (visible) logView.toEnd()", qml)
        app = (ROOT / "setup/monet_setup/app.py").read_text(encoding="utf-8")
        self.assertEqual(app.count('print("install: " + '), 2)   # the journal, so a test PC's serial console
        test = (ROOT / "tools/vm-test.py").read_text(encoding="utf-8")
        self.assertIn('run.shot("failed-details")', test)


if __name__ == "__main__":
    unittest.main()
