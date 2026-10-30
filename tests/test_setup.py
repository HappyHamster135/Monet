"""Monet Setup, the installer on the USB stick: its choices and steps, with
a pretend PC (no disks are touched).

    python3 -m unittest discover -s tests
"""

import importlib.util
import io
import json
import os
import re
import signal
import sys
import tempfile
import types
import unittest
from unittest import mock
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "setup"))
sys.dont_write_bytecode = True

from monet_setup import disks, install, network, pc, system  # noqa: E402

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


class InstallerCommands(unittest.TestCase):
    def test_live_output_arrives_before_exit_and_keeps_the_final_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            observed = Path(tmp) / "observed"
            lines = []

            def log(line):
                lines.append(line)
                if "unpacking" in line:
                    observed.touch()

            script = ("import pathlib, sys, time; print('unpacking', flush=True); "
                      f"marker = pathlib.Path({str(observed)!r})\n"
                      "while not marker.exists(): time.sleep(0.02)\n"
                      "sys.stderr.write('final diagnostic'); sys.stderr.flush()")
            with mock.patch.object(install, "log", side_effect=log):
                output = install.run(sys.executable, "-c", script, live=True, timeout=3, quiet=True)
            self.assertEqual(output, "unpacking\n")
            self.assertEqual(lines, ["  unpacking", "  final diagnostic"])

    def test_timeout_stops_child_processes_and_keeps_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            pid = Path(tmp) / "child.pid"
            script = ("import pathlib, subprocess, sys, time; "
                      "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                      f"pathlib.Path({str(pid)!r}).write_text(str(child.pid)); "
                      "print('last activity', flush=True); time.sleep(30)")
            try:
                with mock.patch.object(install, "LOG", Path(tmp) / "install.log"), redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(install.Stop, "took too long"):
                        install.run(sys.executable, "-c", script, timeout=0.5, quiet=True)
                    self.assertIn("last activity", install.LOG.read_text())
                status = Path(f"/proc/{int(pid.read_text())}/stat")
                try:
                    state = status.read_text().split(")", 1)[1].split()[0]
                except FileNotFoundError:
                    pass  # The child was already reaped between timeout and inspection.
                else:
                    self.assertEqual(state, "Z", "the timed-out command's child is still running")
            finally:
                if pid.exists():
                    try:
                        os.kill(int(pid.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_input_output_and_failure_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(install, "LOG", Path(tmp) / "install.log"), redirect_stdout(io.StringIO()):
                result = install.run(sys.executable, "-c",
                                     "import sys; print(sys.stdin.read()); print('warning', file=sys.stderr)",
                                     input="test input", quiet=True)
                self.assertEqual(result, "test input\n")
                self.assertIn("warning", install.LOG.read_text())
                with self.assertRaisesRegex(install.Stop, "exit 7"):
                    install.run(sys.executable, "-c", "raise SystemExit(7)", quiet=True)
                with self.assertRaisesRegex(install.Stop, "took too long"):
                    install.run(sys.executable, "-c", "import time; time.sleep(30)", timeout=0.1, quiet=True)

    def test_finished_command_does_not_wait_for_background_output_handles(self):
        # A helper can leave a background process holding stdout/stderr after it exits.
        with tempfile.TemporaryDirectory() as tmp:
            pid = Path(tmp) / "background.pid"
            script = (
                "import pathlib, subprocess, sys; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                f"pathlib.Path({str(pid)!r}).write_text(str(child.pid)); "
                "print('installed', flush=True)"
            )
            try:
                with mock.patch.object(install, "LOG", Path(tmp) / "install.log"), redirect_stdout(io.StringIO()):
                    self.assertEqual(install.run(sys.executable, "-c", script, timeout=2, quiet=True), "installed\n")
            finally:
                if pid.exists():
                    try:
                        os.kill(int(pid.read_text()), signal.SIGTERM)
                    except ProcessLookupError:
                        pass


class ThisPC(unittest.TestCase):
    def sysfs(self, root, cards):
        for i, (cls, vendor, device) in enumerate(cards):
            dev = Path(root) / f"0000-0{i}-00.0"  # sysfs names have colons, which Windows refuses
            dev.mkdir(parents=True)
            for name, value in (("class", cls), ("vendor", f"0x{vendor}"), ("device", f"0x{device}")):
                (dev / name).write_text(value + "\n")
        return Path(root)

    def test_both_installers_detect_the_destination_pc(self):
        # Exercise Setup and the fallback installer's actual detector with the same sysfs fixtures.
        ks = (ROOT / "image/monet.ks").read_text(encoding="utf-8")
        detector = ks.split('from pathlib import Path\n\ndef newer_nvidia', 1)[1].split('\nimage = "@IMAGE@"', 1)[0]
        scope = {"Path": Path}
        exec("def newer_nvidia" + detector, scope)
        intel, amd = ("8086", "9bc4"), ("1002", "744c")
        rtx, gtx16, old = ("10de", "2684"), ("10de", "1f82"), ("10de", "1c03")
        for cards, nvidia in (([intel], False), ([amd], False), ([rtx], True),
                              ([intel, rtx], True), ([amd, gtx16], True),
                              ([old], False), ([intel, old], False), ([], False)):
            with self.subTest(cards=cards), tempfile.TemporaryDirectory() as tmp:
                devices = self.sysfs(tmp, [("0x030000", *card) for card in cards]
                                     + [("0x020000", "10de", "2684")])
                facts = pc.check(pc.graphics(devices), 16, False)
                self.assertEqual(facts["newNvidia"], nvidia)
                self.assertEqual(scope["newer_nvidia"](devices), nvidia)
                self.assertEqual(pc.image_for("ghcr.io/x/monet:latest", facts),
                                 "ghcr.io/x/monet" + ("" if nvidia else "-amd") + ":latest")

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
        # The blue screen at the first start in pictures beside All set, with the password the
        # key was queued with, in shim's own words and order.
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        guide = qml.split("id: guide", 1)[1].split("// ---- Steps ----", 1)[0]
        self.assertIn("visible: installing && phase === \"done\" && !showingKey", guide)
        order = ['title: "Perform MOK management"', '"Enroll MOK"', '"View key 0"', '"Enroll the key(s)?"', '"Password:',
                 'lines: ["Reboot"']
        self.assertEqual([guide.index(w) for w in order], sorted(guide.index(w) for w in order))
        self.assertIn(f'"Type %1, then Enter", "{install.MOK_PASSWORD}"', guide)
        self.assertIn("Continue boot", guide)
        self.assertNotIn("any key", guide.lower())  # install's --timeout -1 skips shim's "Press any key"
        self.assertIn("component BlueScreen", qml)


class YourChoices(unittest.TestCase):
    """The time zone is chosen in Setup; the password is typed twice, and none at all is allowed."""

    def test_time_zones_by_region_then_city(self):
        with tempfile.TemporaryDirectory() as tmp:
            tab = Path(tmp) / "zone1970.tab"
            tab.write_text("# comment\nSE\t+5920+01803\tEurope/Stockholm\n"
                           "AR\t-3436-05827\tAmerica/Argentina/Buenos_Aires\tBuenos Aires (BA, CF)\n")
            zones = system.time_zones(tab)
        self.assertIn("America/Argentina/Buenos_Aires", zones)
        self.assertEqual(zones[-1], "UTC")                                     # under Other, last
        self.assertTrue(set(z for *_, z in system.LANGUAGES) <= set(zones))   # every language's guess is there
        regions = [system.zone_region(z) for z in zones]
        self.assertEqual(regions, sorted(regions, key=list(system.REGIONS).index))
        self.assertEqual(system.zone_city("America/Argentina/Buenos_Aires"), "Buenos Aires (Argentina)")
        self.assertEqual(system.zone_city("Europe/Stockholm"), "Stockholm")

    def test_the_zone_chosen_is_the_one_installed(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        setup = app.Setup.__new__(app.Setup)
        setup._zones = ["America/New_York", "America/Toronto", "Europe/Oslo", "Europe/Stockholm", "UTC"]
        setup._zone, setup._zone_chosen, setup._language = "Europe/Oslo", False, 2    # Svenska: Stockholm's
        setup.changed = setup.clockChanged = types.SimpleNamespace(emit=lambda: None)
        self.assertEqual(setup._regions(), ["America", "Europe", "UTC"])
        self.assertEqual(app.Setup.cities.fget(setup), ["Oslo", "Stockholm"])
        setup.setCity(1)
        self.assertEqual((setup._zone, setup._zone_chosen), ("Europe/Stockholm", True))
        setup.setRegion(0)                                    # America: its first city (no Swedish one there)
        self.assertEqual(setup._zone, "America/New_York")
        setup.setRegion(1)                                    # back to Europe: the language's own
        self.assertEqual(setup._zone, "Europe/Stockholm")
        source = (ROOT / "setup/monet_setup/app.py").read_text(encoding="utf-8")
        self.assertIn('"timezone": self._zone,', source)
        self.assertIn("if self._zone_asked or self._zone_chosen or DEMO:", source)   # the internet never overrules a choice
        installer = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertIn('zone = plan["timezone"]\n        if not (root / "usr/share/zoneinfo" / zone).exists():', installer)

    def test_the_password_twice_or_none(self):
        try:
            from monet_setup import app
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        setup = app.Setup.__new__(app.Setup)
        setup._name, setup._password = "", ""
        setup.changed = types.SimpleNamespace(emit=lambda: None)
        self.assertEqual(setup.setPerson("Ann", "secret", "secrte"), "The passwords don't match.")
        self.assertEqual(setup.setPerson("Ann", "abc", "abc"), "")               # any password: theirs to choose
        self.assertEqual(setup.setPerson("Ann", "", ""), "")                     # none at all, too
        self.assertEqual((setup._name, setup._password), ("Ann", ""))
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn('property bool ready: name.text.trim() !== "" && pass.text === again.text', qml)
        self.assertIn('tr("No password: Monet signs you in by itself, and anyone who uses this PC can open your account and change its settings.")', qml)
        test = (ROOT / "tools/vm-test.py").read_text(encoding="utf-8")
        self.assertIn("vm.click(*AGAIN_FIELD)", test)

    def test_no_password_signs_in_by_itself(self):
        commands = []
        saved = install.run
        install.run = lambda *args, **kw: commands.append([str(a) for a in args]) or ""
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                install.no_password(root, "ann")
                autologin = (root / "etc/plasmalogin.conf.d/50-monet-no-password.conf").read_text()
                locker = (root / "var/home/ann/.config/kscreenlockerrc").read_text()
        finally:
            install.run = saved
        self.assertEqual(autologin, "[Autologin]\nUser=ann\nSession=plasma.desktop\nRelogin=false\n")
        self.assertIn("Autolock=false", locker)
        self.assertIn(["chroot", tmp, "passwd", "-d", "ann"], commands)
        # Labelled against Monet's own policy, not the stick's.
        installer = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertIn('policy = ["-c", "/" + policies[-1].relative_to(root).as_posix()] if policies else []', installer)
        self.assertEqual(installer.count('"setfiles", "-F", "-T", "0", *policy, contexts'), 2)

    def test_a_password_set_later_ends_it(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("monet_ready", str(ROOT / "linux/libexec/monet-ready"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        ready = importlib.util.module_from_spec(spec)
        loader.exec_module(ready)
        with tempfile.TemporaryDirectory() as tmp:
            conf, shadow = Path(tmp) / "50-monet-no-password.conf", Path(tmp) / "shadow"
            conf.write_text("[Autologin]\nUser=ann\nSession=plasma.desktop\n")
            shadow.write_text("root:!:19000::::::\nann::19000:0:99999:7:::\n")
            ready.settle_no_password(conf, shadow)
            self.assertTrue(conf.exists())                    # still none: still signs in by itself
            shadow.write_text("root:!:19000::::::\nann:$y$j9T$abc:19001:0:99999:7:::\n")
            ready.settle_no_password(conf, shadow)
            self.assertFalse(conf.exists())                   # a password now: the sign-in screen asks
        unit = (ROOT / "linux/systemd/monet-ready-boot.service").read_text()
        self.assertIn("ConditionPathExists=|/etc/plasmalogin.conf.d/50-monet-no-password.conf", unit)


class TheBlueScreenSkipped(unittest.TestCase):
    """The first start's blue screen opens on Continue boot: choosing it leaves Monet unable to
    start (bad shim signature). The USB stick notices and asks the firmware again."""

    def run_with(self, secure_boot, has_key, enrolled):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            def fake_said(*args, input=None, timeout=60):
                if args[:2] == ("mokutil", "--sb-state"):
                    return "SecureBoot enabled\n" if secure_boot else "SecureBoot disabled\n"
                if args[0] == "lsblk":
                    return json.dumps({"blockdevices": [{"path": "/dev/sda", "parttype": None, "children": [
                        {"path": "/dev/sda1", "parttype": "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"}]}]})
                if args[:2] == ("mokutil", "--test-key"):
                    return f"{args[2]} is already enrolled\n" if enrolled else f"{args[2]} is not enrolled\n"
                return ""

            def fake_run(args, **kw):
                if args[0] == "mount" and has_key:
                    key = Path(args[-1]) / pc.ESP_KEY
                    key.parent.mkdir(parents=True, exist_ok=True)
                    key.write_bytes(b"0\x82key")
                return types.SimpleNamespace(returncode=0)

            with mock.patch.object(pc, "said", fake_said), mock.patch.object(pc.subprocess, "run", fake_run):
                found = pc.untrusted_key(Path(tmp))
                return found.name if found else None

    def test_only_an_installed_monet_that_cant_start(self):
        self.assertEqual(self.run_with(secure_boot=True, has_key=True, enrolled=False), "monet-key.der")
        self.assertIsNone(self.run_with(secure_boot=True, has_key=True, enrolled=True))     # trusted: fine
        self.assertIsNone(self.run_with(secure_boot=False, has_key=True, enrolled=False))   # Secure Boot off: it starts
        self.assertIsNone(self.run_with(secure_boot=True, has_key=False, enrolled=False))   # no Monet here

    def test_the_vm_test_knows_the_blue_screen(self):
        # 0.9.3's VM test looked for blue across the whole screen; OVMF draws the blue screen as an
        # 80-column box with black on either side, so it never saw it and 0.9.3 shipped without Setup.
        try:
            from PIL import Image, ImageDraw
        except ImportError as e:
            self.skipTest(f"no Pillow ({e})")
        spec = importlib.util.spec_from_file_location("vm_test", ROOT / "tools/vm-test.py")
        vm_test = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vm_test)
        boxed = Image.new("RGB", (1920, 1080))
        ImageDraw.Draw(boxed).rectangle((640, 64, 1280, 996), fill=(0, 0, 168))
        self.assertTrue(vm_test.blue_screen(boxed))
        whole = Image.new("RGB", (1920, 1080), (0, 0, 168))
        self.assertTrue(vm_test.blue_screen(whole))
        # All set's pictures of it: blue, but small beside the sheet.
        all_set = Image.new("RGB", (1920, 1080), (200, 200, 210))
        ImageDraw.Draw(all_set).rectangle((830, 360, 1075, 512), fill=(0, 0, 170))
        self.assertFalse(vm_test.blue_screen(all_set))
        self.assertFalse(vm_test.blue_screen(Image.new("RGB", (1920, 1080))))

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "requires Pillow in the VM test environment")
    def test_setup_vm_uses_the_usb_boot_path_with_secure_boot(self):
        from unittest import mock
        spec = importlib.util.spec_from_file_location("usb_vm_test", ROOT / "tools/vm-test.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module.subprocess, "run"), \
                mock.patch.object(module.subprocess, "Popen") as start, mock.patch.object(module.shutil, "copy"):
            (Path(tmp) / "qmp.sock").touch()
            machine = module.VM("installer.iso", tmp)
            command = start.call_args.args[0]
            self.assertIn("file=installer.iso,format=raw,readonly=on,if=none,id=usb", command)
            self.assertIn("usb-storage,drive=usb,removable=on,bootindex=1,id=stick", command)
            self.assertIn("q35,smm=on", command)
            self.assertTrue(any("OVMF_CODE_4M.ms.fd" in arg for arg in command))
            self.assertFalse(any("ide-cd" in arg for arg in command))
            # Reboot after installation still selects the installed disk ahead of the stick.
            with mock.patch.object(machine, "qmp") as qmp:
                machine.start_first("disk")
                self.assertEqual(qmp.call_args.args[0]["arguments"]["value"], 3)
            start.call_args.kwargs["stdout"].close()

    def test_the_vm_test_knows_monet_from_the_stick(self):
        # Up to 0.9.3 the VM started the stick again after the blue screen, and the "tour" was Setup's Hello.
        try:
            from PIL import Image, ImageDraw
        except ImportError as e:
            self.skipTest(f"no Pillow ({e})")
        spec = importlib.util.spec_from_file_location("vm_test", ROOT / "tools/vm-test.py")
        vm_test = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vm_test)
        self.assertTrue(vm_test.monet_started("[   3.1] monet systemd[1]: Reached target multi-user.target.\n"))
        self.assertFalse(vm_test.monet_started("[   3.1] monet-setup systemd[1]: Reached target multi-user.target.\n"))
        self.assertFalse(vm_test.monet_started("[   0.4] monet kernel: Secure boot enabled\n"))
        self.assertTrue(vm_test.monet_on_screen(Image.new("RGB", (1920, 1080), (120, 110, 100))))
        self.assertFalse(vm_test.monet_on_screen(Image.new("RGB", (1920, 1080))))
        boxed = Image.new("RGB", (1920, 1080))
        ImageDraw.Draw(boxed).rectangle((640, 64, 1280, 996), fill=(0, 0, 168))
        self.assertFalse(vm_test.monet_on_screen(boxed))

    def test_the_key_reaches_the_kernel_as_a_cpio(self):
        data = install.newc("monet-key.der", b"0\x82key!")
        self.assertEqual(data[:6], b"070701")
        name_size, size = int(data[94:102], 16), int(data[54:62], 16)
        self.assertEqual(data[110:110 + name_size], b"monet-key.der\0")
        start = 110 + name_size + (-(110 + name_size) % 4)
        self.assertEqual(data[start:start + size], b"0\x82key!")
        self.assertIn(b"TRAILER!!!\0", data)
        self.assertEqual(len(data) % 4, 0)

    def test_grub_falls_back_to_asking_again(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            boot, key, kernel, initrd = tmp / "boot", tmp / "key.der", tmp / "vmlinuz", tmp / "trust.img"
            (boot / "grub2").mkdir(parents=True)
            key.write_bytes(b"0\x82key")
            kernel.write_bytes(b"MZ kernel")
            initrd.write_bytes(b"\x1f\x8b initrd")
            with mock.patch.object(install, "TRUST_INITRD", initrd), mock.patch.object(install, "log"):
                (boot / "grub2/grub.cfg").write_text("blscfg\n")             # a menu that doesn't read custom.cfg
                install.trust_fallback(boot, key, kernel)
                self.assertFalse((boot / "monet-trust").exists())
                (boot / "grub2/grub.cfg").write_text("blscfg\nif [ -f $prefix/custom.cfg ]; then\n  source $prefix/custom.cfg\nfi\n")
                install.trust_fallback(boot, key, kernel)
                install.trust_fallback(boot, key, kernel)                    # a second try adds nothing
            custom = (boot / "grub2/custom.cfg").read_text()
            self.assertEqual(custom.count("set fallback=monet-trust"), 1)
            self.assertEqual((boot / "monet-trust/vmlinuz").read_bytes(), b"MZ kernel")
            self.assertEqual((boot / "monet-trust/initrd.img").read_bytes(), b"\x1f\x8b initrd")
            self.assertIn(b"0\x82key", (boot / "monet-trust/key.cpio").read_bytes())
        # GRUB's entry and the small start agree on names; it asks with All set's password.
        self.assertIn("--id monet-trust", install.TRUST_MENU)
        self.assertIn("rdinit=/monet-trust", install.TRUST_MENU)
        self.assertIn("initrd /monet-trust/initrd.img /monet-trust/key.cpio", install.TRUST_MENU)
        helper = (ROOT / "image/setup/monet-trust").read_text(encoding="utf-8")
        self.assertIn(f"PASSWORD={install.MOK_PASSWORD} ", helper)
        self.assertIn("KEY=/monet-key.der", helper)
        self.assertIn("echo b > /proc/sysrq-trigger", helper)
        build = (ROOT / "image/setup/build.sh").read_text(encoding="utf-8")
        self.assertIn('install -m 0755 "$HERE/monet-trust" "$T/monet-trust"', build)
        self.assertIn('> "$APP/trust-initrd.img"', build)
        self.assertEqual(str(install.TRUST_INITRD).replace("\\", "/"), "/usr/share/monet-setup/trust-initrd.img")
        self.assertIn('APP=$ROOT/usr/share/monet-setup', build)

    def test_setup_leaves_the_key_where_the_stick_finds_it(self):
        installer = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertIn('esp_key = Path(TARGET) / "boot/efi" / pc.ESP_KEY', installer)
        self.assertEqual(pc.ESP_KEY, "EFI/Monet/monet-key.der")
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("onClicked: setup.trustAndRestart()", qml)
        self.assertIn("visible: setup.untrusted", qml)


class TheStick(unittest.TestCase):
    """0.9.1's Setup failed at bootc: it reads prepare-root.conf from the stick, not the image."""

    def test_the_stick_carries_the_images_bootc_settings(self):
        workflow = (ROOT / ".github/workflows/image.yml").read_text(encoding="utf-8")
        self.assertIn("usr/lib/ostree/prepare-root.conf etc/ostree/prepare-root.conf usr/lib/bootc/install", workflow)
        self.assertEqual(workflow.count("name: bootc-settings"), 2)   # uploaded by image, taken by setup
        build = (ROOT / "image/setup/build.sh").read_text(encoding="utf-8")
        self.assertIn('tar -xf "$SETTINGS" -C "$ROOT"', build)
        self.assertIn('[ ! -e "$ROOT/usr/lib/ostree/prepare-root.conf" ]', build)

    def test_monet_starts_behind_the_splash_like_the_stick(self):
        # Setup's bootc install had none of these (Fedora's installer added rhgb quiet), so the
        # Monet it installed started as scrolling text.
        menu = (ROOT / "image/setup/grub.cfg").read_text(encoding="utf-8")
        stick = re.search(r"menuentry 'Monet Setup' .*?\n\s*linux (.*)", menu).group(1).split()
        for karg in install.QUIET:
            self.assertIn(karg, stick)
        source = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertIn('*(arg for karg in QUIET for arg in ("--karg", karg))', source)

    def test_why_an_install_stopped_is_easy_to_see(self):
        qml = (ROOT / "setup/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn("onVisibleChanged: if (visible) logView.toEnd()", qml)
        app = (ROOT / "setup/monet_setup/app.py").read_text(encoding="utf-8")
        self.assertEqual(app.count('print("install: " + '), 2)   # the journal, so a test PC's serial console
        test = (ROOT / "tools/vm-test.py").read_text(encoding="utf-8")
        self.assertIn('run.shot("failed-details")', test)


if __name__ == "__main__":
    unittest.main()
