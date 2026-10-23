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

    def test_offer(self):
        offered = disks.offer([STICK, NVME], free=lambda path: (2048, 30 * GB // 512, 512))
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


if __name__ == "__main__":
    unittest.main()
