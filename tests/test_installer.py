"""Checks for the installer pieces that can run without real hardware.

    python3 -m unittest discover -s tests
"""

import builtins
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# No __pycache__ beside the helpers we load: the Linux package copies libexec/.
sys.dont_write_bytecode = True


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


prepare = load("linux/libexec/monet-prepare-windows", "prepare")
patch_grub = load("tools/patch-grub.py", "patch_grub")

GRUB = """set default="1"
set timeout=60
search --no-floppy --set=root -l 'Fedora-E-dvd-x86_64-44'
menuentry 'Install Fedora 44' --class fedora --class os {
\tlinux /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Fedora-E-dvd-x86_64-44 quiet inst.ks=hd:LABEL=Fedora-E-dvd-x86_64-44:/monet.ks
\tinitrd /images/pxeboot/initrd.img
}
menuentry 'Test this media & install Fedora 44' --class fedora --class os {
\tlinux /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Fedora-E-dvd-x86_64-44 rd.live.check quiet
\tinitrd /images/pxeboot/initrd.img
}
submenu 'Troubleshooting -->' {
\tmenuentry 'Rescue a Fedora Linux system' --class fedora --class os {
\t\tlinux /images/pxeboot/vmlinuz inst.rescue quiet
\t}
}
"""


def pre_install():
    """The kickstart's %pre-install functions and settings, without running it."""
    import ast
    import io
    ks = (ROOT / "image/monet.ks").read_text()
    code = re.search(r"%pre-install[^\n]*\n(.*?)\n%end", ks, re.S).group(1).replace("@IMAGE@", "ghcr.io/x/monet:latest")
    tree = ast.parse(code)
    keep = [n for n in tree.body if isinstance(n, (ast.Import, ast.FunctionDef))
            or (isinstance(n, ast.Assign) and all(isinstance(t, (ast.Name, ast.Tuple)) for t in n.targets))]
    def saved_image(path):
        assert path == "/tmp/monet-image"
        return io.StringIO("ghcr.io/x/monet@sha256:" + "a" * 64)
    ns = {"print": lambda *a, **k: None, "open": saved_image}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "pre-install", "exec"), ns)
    del ns["open"]
    return ns


class StartMenu(unittest.TestCase):
    def test_entries(self):
        out = patch_grub.patch(GRUB)
        titles = re.findall(r"menuentry '([^']*)'", out)
        self.assertEqual(titles[:3], [patch_grub.ERASE, patch_grub.KEEP, "Test this media & install Monet"])
        self.assertIn('set default="0"', out)
        keep = out.split(f"'{patch_grub.KEEP}'")[1].split("}")[0]
        self.assertIn("monet.keep", keep)
        erase = out.split(f"'{patch_grub.ERASE}'")[1].split("}")[0]
        self.assertNotIn("monet.keep", erase)
        self.assertNotIn("Fedora 44'", out)
        self.assertIn("submenu 'More options'", out)
        self.assertIn("set timeout=10", out)
        # Monet's own entries keep the open-source NVIDIA driver off.
        self.assertIn("nouveau.modeset=0", erase)
        self.assertIn("nouveau.modeset=0", keep)
        # The theme is loaded after the search line that sets $root.
        self.assertLess(out.index("search --no-floppy"), out.index("set theme="))
        self.assertLess(out.index("set theme="), out.index("menuentry"))


class BootMenu(unittest.TestCase):
    GRUB = ROOT / "image/installer/grub"

    @staticmethod
    def pf2_name(path):
        data = path.read_bytes()
        i = data.index(b"NAME")
        n = int.from_bytes(data[i + 4:i + 8], "big")
        return data[i + 8:i + 8 + n].rstrip(b"\0").decode()

    def test_theme_has_its_pictures(self):
        theme = (self.GRUB / "theme.txt").read_text()
        for name in re.findall(r'(?:desktop-image|file)\s*[:=]\s*"([^"]+)"', theme):
            self.assertTrue((self.GRUB / name).is_file(), name)
        for style in re.findall(r'pixmap_style\s*=\s*"([^"]+)"', theme):
            for piece in ("nw", "n", "ne", "w", "c", "e", "sw", "s", "se"):
                self.assertTrue((self.GRUB / style.replace("*", piece)).is_file(), style + " " + piece)

    def test_theme_fonts_are_loaded(self):
        theme = (self.GRUB / "theme.txt").read_text()
        loaded = {self.pf2_name(self.GRUB / Path(f).name) for f in re.findall(r"loadfont (\S+)", patch_grub.THEME)}
        for font in set(re.findall(r'font\s*[:=]\s*"([^"]+)"', theme)):
            self.assertIn(font, loaded)

    def test_highlight_stays_between_its_neighbours(self):
        # GRUB draws the highlight's border outside the line: above and below
        # it, it may take at most the gap between lines.
        theme = (self.GRUB / "theme.txt").read_text()
        spacing = int(re.search(r"item_spacing = (\d+)", theme).group(1))
        style = re.search(r'selected_item_pixmap_style = "([^"]+)"', theme).group(1)
        # A PNG's height: bytes 20-24 of its header.
        pads = sum(int.from_bytes((self.GRUB / style.replace("*", side)).read_bytes()[20:24], "big") for side in ("n", "s"))
        self.assertGreaterEqual(spacing, pads)

    def test_text_layer_gets_a_small_font(self):
        # GRUB's text layer needs 40 columns; the 56px title doesn't fit them,
        # and with no name given it takes the newest font.
        files = re.findall(r"loadfont (\S+)", patch_grub.THEME)
        named = re.search(r'set gfxterm_font="([^"]+)"', patch_grub.THEME).group(1)
        self.assertEqual(named, self.pf2_name(self.GRUB / Path(files[-1]).name))
        self.assertLessEqual(int(named.rsplit(" ", 1)[1]), 24)


class DiskPlan(unittest.TestCase):
    """Runs the kickstart's %pre with a pretend PC."""

    DEVICES = [
        {"name": "sda", "path": "/dev/sda", "size": 16 * 10**9, "type": "disk", "rm": True, "ro": False, "tran": "usb"},
        {"name": "sda1", "path": "/dev/sda1", "size": 10**9, "type": "part", "rm": True, "ro": False, "pkname": "sda"},
        {"name": "sdb", "path": "/dev/sdb", "size": 2 * 10**12, "type": "disk", "rm": "0", "ro": "0", "tran": "usb"},
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 1_000_204_886_016, "type": "disk", "rm": "0", "ro": "0",
         "tran": "nvme"},
        {"name": "zram0", "path": "/dev/zram0", "size": 8 * 10**9, "type": "disk", "rm": False, "ro": False},
    ]

    def plan(self, cmdline, devices=None, media="/dev/sda1", settled=True):
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%pre[^\n]*\n(.*?)\n%end", ks, re.S).group(1)
        written = {}
        devices = self.DEVICES if devices is None else devices

        class Sink:
            def __init__(self, path):
                self.path = path

            def write(self, text):
                written[self.path] = text

        fake = types.ModuleType("subprocess")
        fake.SubprocessError = subprocess.SubprocessError
        output = {"lsblk": json.dumps({"blockdevices": devices}), "blkid": media, "udevadm": "", "tmux": ""}

        def run(cmd, **kwargs):
            if cmd[0] == "udevadm" and not settled:
                self.assertTrue(kwargs["check"])
                raise subprocess.CalledProcessError(1, cmd)
            return types.SimpleNamespace(stdout=output[cmd[0]])

        fake.run = run

        def fake_open(path, mode="r", *a, **k):
            return io.StringIO(cmdline) if path == "/proc/cmdline" else Sink(path)

        def fake_import(name, *a, **k):
            return fake if name == "subprocess" else __import__(name, *a, **k)

        env = {"__builtins__": dict(vars(builtins), open=fake_open, print=lambda *a: None, __import__=fake_import)}
        exec(code, env)
        return written["/tmp/monet-storage.ks"]

    def test_erase_picks_the_only_internal_disk(self):
        plan = self.plan("inst.stage2=hd:LABEL=Fedora-E-dvd-x86_64-44 quiet")
        self.assertIn("ignoredisk --only-use=nvme0n1", plan)
        self.assertIn("clearpart --all --initlabel --disklabel=gpt --drives=nvme0n1", plan)
        size = int(re.search(r"--size=(\d+)", plan).group(1))
        total = 1_000_204_886_016 // 2**20
        self.assertEqual(total - size, (128 + 8 + 4) * 1024)
        self.assertGreater(size, 64 * 1024)

    def test_erase_stops_with_two_internal_disks(self):
        other = {"name": "nvme1n1", "path": "/dev/nvme1n1", "size": 2 * 10**12,
                 "type": "disk", "rm": False, "ro": False, "tran": "nvme"}
        devices = [*self.DEVICES, other]
        boot = "inst.stage2=hd:LABEL=Monet-0.9.7"
        with self.assertRaisesRegex(SystemExit, "Restart with Monet Setup"):
            self.plan(boot, devices=devices)
        pre = (ROOT / "image/monet.ks").read_text().split("%pre ", 1)[1].splitlines()[0]
        self.assertIn("--erroronfail", pre)
        self.assertEqual(self.plan(boot + " monet.keep", devices=devices), "")

    def test_erase_needs_a_known_boot_disk_and_a_settled_scan(self):
        boot = "inst.stage2=hd:LABEL=Monet-0.9.7"
        with self.assertRaisesRegex(SystemExit, "recognized installation media"):
            self.plan(boot, media="")
        with self.assertRaisesRegex(SystemExit, "could not finish checking the drives"):
            self.plan(boot, settled=False)

    def test_never_the_stick_even_when_it_looks_internal(self):
        # A USB-to-SATA drive or card reader may not say "usb"; the stick is
        # still found from the installer's own label.
        devices = [
            {"name": "sdc", "path": "/dev/sdc", "size": 4 * 10**12, "type": "disk", "rm": "0", "ro": "0", "tran": "sata"},
            {"name": "sdc1", "path": "/dev/sdc1", "size": 10**9, "type": "part", "rm": "0", "ro": "0", "pkname": "sdc"},
            {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 500 * 10**9, "type": "disk", "rm": "0", "ro": "0",
             "tran": "nvme"},
        ]
        plan = self.plan("inst.stage2=hd:LABEL=MONET-0.6 quiet", devices=devices, media="/dev/sdc1")
        self.assertIn("ignoredisk --only-use=nvme0n1", plan)

    def test_monet_for_the_graphics(self):
        import ast
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%pre[^\n]*monet-image\.log\n(.*?)\n%end", ks, re.S).group(1)
        ns = {}
        tree = ast.parse(code)
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.ImportFrom, ast.FunctionDef))],
                                type_ignores=[]), "pre", "exec"), ns)
        for cards, newer in (([("0x030000", "0x10de", "0x2684")], True), ([("0x030000", "0x10de", "0x1c03")], False),
                             ([("0x030000", "0x1002", "0x73bf"), ("0x020000", "0x10de", "0x2684")], False)):
            with tempfile.TemporaryDirectory() as tmp:
                for i, (cls, vendor, device) in enumerate(cards):
                    dev = Path(tmp) / f"0000-0{i}-00.0"
                    dev.mkdir()
                    for name, value in (("class", cls), ("vendor", vendor), ("device", device)):
                        (dev / name).write_text(value + "\n")
                self.assertEqual(ns["newer_nvidia"](Path(tmp)), newer, cards)
        self.assertIn('image = "@AMD_IMAGE@"', code)
        self.assertIn('sha256:[0-9a-f]{64}', code)
        self.assertIn("%include /tmp/monet-image.ks", ks)
        self.assertNotIn("ostreecontainer --url=@IMAGE@", ks)
        self.assertIn('open("/tmp/monet-image")', re.search(r"%pre-install[^\n]*\n(.*?)\n%end", ks, re.S).group(1))

    def test_download_check_compiles(self):
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%pre-install[^\n]*\n(.*?)\n%end", ks, re.S).group(1)
        compile(code.replace("@IMAGE@", "ghcr.io/example/monet:latest"), "pre-install", "exec")

    def test_fallback_records_the_update_channel_for_the_pinned_deployments(self):
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%post[^\n]*monet-update-origin\.log\n(.*?)\n%end", ks, re.S).group(1)
        ns = {"__name__": "fixture"}
        exec(compile(code, "post-install", "exec"), ns)

        image = "registry.invalid:8443/project_name/monet-amd"
        digest = "a" * 64
        pinned, channel = f"{image}@sha256:{digest}", f"{image}:latest"
        ref_prefix = "ostree/container/image/docker_3A__2F__2F_registry_2E_invalid_3A_8443/project__name/monet-amd"
        pinned_ref = ref_prefix + "_40_sha256_3A_" + digest
        channel_ref = ref_prefix + "_3A_latest"
        origin_key = "container-image-reference"
        commit = "b" * 64

        def deployment(reference, checksum=commit):
            result = Mock()
            result.get_csum.return_value = checksum
            origin = result.get_origin.return_value
            origin.has_group.return_value = True
            origin.get_keys.return_value = ([origin_key], 1)
            origin.get_string.return_value = reference
            return result

        for outcome in ("success", "official", "unrelated default", "wrong commit", "conflicting cache"):
            with self.subTest(outcome=outcome):
                signed = "ostree-image-signed:docker://"
                unsigned = "ostree-unverified-registry:"
                test_pinned, test_channel = pinned, channel
                test_pinned_ref, test_channel_ref = pinned_ref, channel_ref
                if outcome == "official":
                    test_pinned = f"ghcr.io/happyhamster135/monet-amd@sha256:{digest}"
                    test_channel = "ghcr.io/happyhamster135/monet-amd:latest"
                    test_pinned_ref = ns["container_ref"](test_pinned)
                    test_channel_ref = ns["container_ref"](test_channel)
                other = deployment(unsigned + "registry.invalid/another:latest")
                current = deployment(signed + test_pinned, "c" * 64 if outcome == "wrong commit" else commit)
                rollback = deployment(unsigned + test_pinned)
                sysroot = Mock()
                sysroot.get_deployments.return_value = [other, current, rollback] if outcome == "unrelated default" \
                    else [current, rollback, other]
                repo = Mock()
                sysroot.get_repo.return_value = (True, repo)
                refs = {test_pinned_ref: commit, test_channel_ref: "c" * 64 if outcome == "conflicting cache" else None}
                repo.resolve_rev.side_effect = lambda ref, allow_noent: (True, refs[ref])

                if outcome in ("success", "official"):
                    self.assertEqual(ns["set_update_origin"](sysroot, test_pinned), test_channel)
                    repo.set_ref_immediate.assert_called_once_with(None, test_channel_ref, commit)
                    for item, prefix in ((current, signed), (rollback, signed if outcome == "official" else unsigned)):
                        origin = item.get_origin.return_value
                        origin.set_string.assert_called_once_with("origin", origin_key, prefix + test_channel)
                    self.assertEqual(sysroot.write_origin_file.call_count, 2)
                else:
                    with self.assertRaisesRegex(RuntimeError, "does not match|different local image"):
                        ns["set_update_origin"](sysroot, test_pinned)
                    repo.set_ref_immediate.assert_not_called()
                    sysroot.write_origin_file.assert_not_called()
                other.get_origin.return_value.set_string.assert_not_called()
                sysroot.unlock.assert_called_once_with()

    def test_monet_is_downloaded_with_retries(self):
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%pre-install[^\n]*\n(.*?)\n%end", ks, re.S).group(1)
        self.assertIn("nm-online", code)
        self.assertIn('"container", "image", "pull"', code)
        self.assertIn("for attempt in range(", code)
        # Windows waits for the first sign-in instead of the end of the install.
        post = ks.split("%post --log=/var/log/monet-install.log", 1)[1]
        self.assertIn("echo waiting > /var/lib/monet/windows-setup", post)
        self.assertNotIn("monet-prepare-windows", post)

    def test_download_restarts_when_it_stops_moving(self):
        ns = pre_install()
        clock = types.SimpleNamespace(now=0.0)
        ns["time"] = types.SimpleNamespace(time=lambda: clock.now,
                                           sleep=lambda n: setattr(clock, "now", clock.now + n))
        killed = []

        class Stuck:
            returncode = None
            def poll(self):
                return None
            def kill(self):
                killed.append(clock.now)
            def wait(self):
                pass

        ns["subprocess"] = types.SimpleNamespace(Popen=lambda *a, **k: Stuck(), STDOUT=-2)
        ns["received"] = lambda: 1000
        ns["written"] = lambda root: 5000
        ns["tell"] = lambda **status: None
        self.assertFalse(ns["pull"]("/mnt/sysimage", 5 * 10**9, 0, None))
        self.assertTrue(killed)
        self.assertLessEqual(killed[0], ns["STALL"] + 10)

    def test_download_reports_progress(self):
        ns = pre_install()
        clock = types.SimpleNamespace(now=0.0)
        ns["time"] = types.SimpleNamespace(time=lambda: clock.now,
                                           sleep=lambda n: setattr(clock, "now", clock.now + n))

        class Moving:
            returncode = None
            def poll(self):
                self.returncode = 0 if clock.now > 60 else None
                return self.returncode

        told = []
        ns["subprocess"] = types.SimpleNamespace(Popen=lambda *a, **k: Moving(), STDOUT=-2)
        ns["received"] = lambda: int(clock.now * 10**7)
        ns["written"] = lambda root: int(clock.now * 2 * 10**7)
        ns["tell"] = lambda **status: told.append(status)
        self.assertTrue(ns["pull"]("/mnt/sysimage", 5 * 10**9, 0, None))
        last = told[-1]
        self.assertEqual(last["total"], 5 * 10**9)
        self.assertGreater(last["got"], 5 * 10**8)
        self.assertGreater(last["eta"], 0)

    def test_download_window(self):
        gi = types.ModuleType("gi")
        gi.require_version = lambda *a: None
        gi.repository = types.SimpleNamespace(Gdk=None, GdkPixbuf=None, GLib=None,
                                              Gtk=types.SimpleNamespace(Window=object))
        saved = {k: sys.modules.get(k) for k in ("gi", "gi.repository")}
        sys.modules.update({"gi": gi, "gi.repository": gi.repository})
        try:
            window = load("image/installer/product/usr/libexec/monet-download", "monet_download")
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        line, fraction = window.describe({"got": 2_140_000_000, "total": 5_710_000_000, "eta": 372})
        self.assertEqual(line, "2.1 of 5.7 GB · about 6 minutes left")
        self.assertAlmostEqual(fraction, 0.375, places=2)
        self.assertEqual(window.describe({"got": 3 * 10**8, "total": 0})[0], "0.3 GB so far")
        self.assertEqual(window.describe({"got": 10**9, "total": 10**9, "note": "Picking up"})[0], "Picking up")
        self.assertLess(window.describe({"got": 10**9, "total": 10**9})[1], 1)
        # The page before the restart: the blue screen's choices and the password the key was queued with.
        title, intro, steps, note = window.BEFORE_RESTART
        words = " ".join([intro, *steps, note])
        self.assertIn("Enroll MOK", words)
        self.assertIn("monetsetup", words)
        self.assertIn("printf 'monetsetup\\nmonetsetup\\n' | mokutil --import", self.KS)
        # --timeout -1 skips shim's "Press any key": the menu opens on Continue boot, and Enter there skips it.
        self.assertIn("mokutil --timeout -1", self.KS)
        self.assertNotIn("any key", words.lower())

    KS = (ROOT / "image/monet.ks").read_text()

    def test_the_last_thing_is_the_first_start(self):
        # After everything else, before the installer offers to restart.
        last = self.KS.rsplit("%post", 1)[1]
        self.assertIn("--nochroot", last.splitlines()[0])
        self.assertIn("monet-download --before-restart", last)
        # Backgrounded and off anaconda's pipe: a hidden window can't hold up the install.
        self.assertRegex(last, r"--before-restart </dev/null >\S+ 2>&1 &\n")

    def test_keep_asks(self):
        self.assertEqual(self.plan("inst.stage2=hd:LABEL=X monet.keep"), "")

    def test_erase_stops_without_an_internal_disk(self):
        with self.assertRaisesRegex(SystemExit, "one eligible internal drive"):
            self.plan("inst.stage2=hd:LABEL=Monet-0.9.7", devices=self.DEVICES[:3])


class PrepareWindows(unittest.TestCase):
    def test_windows_names(self):
        self.assertEqual(prepare.windows_name("anna/ lind"), "annalind")
        self.assertEqual(prepare.windows_name("[]:"), "Player")
        self.assertEqual(len(prepare.windows_name("x" * 40)), 20)

    def test_windows_computer_name_does_not_shadow_the_account(self):
        for user in ("monet-games", "MONET-GAMES", "Monet- Games", "anna", "monet-play", "[]:"):
            with self.subTest(user=user):
                computer = prepare.windows_computer_name(user)
                self.assertNotEqual(computer.casefold(), prepare.windows_name(user).casefold())
                self.assertLessEqual(len(computer), 15)
        self.assertEqual(prepare.windows_computer_name("anna"), "MONET-GAMES")

    def test_edition(self):
        images = [(1, "Windows 11 Home"), (2, "Windows 11 Home N"), (6, "Windows 11 Pro")]
        self.assertIn(prepare.pick_edition(images), [(1, "Windows 11 Home"), (6, "Windows 11 Pro")])
        self.assertEqual(prepare.pick_edition([(3, "Windows 11 Education")]), (3, "Windows 11 Education"))

    def test_answer_file_is_valid_xml(self):
        template = (ROOT / "linux/share/monet/winpe/unattend.xml").read_text()
        values = {"USER": "a<b", "FULLNAME": "Anna & Co", "COMPUTER": "MONET-GAMES",
                  "TIMEZONE": "W. Europe Standard Time", "UILANG": "sv-SE", "LOCALE": "sv-SE", "INPUT": "sv-SE"}
        out = prepare.fill(template, values)
        xml.dom.minidom.parseString(out.encode())
        self.assertNotRegex(out.split("-->", 1)[1], r"@[A-Z]+@")
        self.assertIn("PreventDeviceEncryption", out)
        self.assertIn('<LogonCount>1</LogonCount>', out)
        self.assertIn('/v AutoLogonCount /t REG_DWORD /d 0 /f', out)
        self.assertIn('/v AutoAdminLogon /t REG_SZ /d 0 /f', out)

    def test_wifi_profiles_for_windows(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "home.nmconnection").write_text(
                "[connection]\nid=Home\ntype=wifi\n[wifi]\nssid=Home & Co\n[wifi-security]\nkey-mgmt=wpa-psk\npsk=p<ss\n")
            Path(d, "work.nmconnection").write_text(
                "[connection]\nid=Work\ntype=wifi\n[wifi]\nssid=Work\n[wifi-security]\nkey-mgmt=wpa-eap\n")
            Path(d, "cafe.nmconnection").write_text("[connection]\nid=Cafe\ntype=wifi\n[wifi]\nssid=Cafe\n")
            original = prepare.WIFI_DIRS
            prepare.WIFI_DIRS = (Path(d),)
            try:
                profiles = prepare.wifi_profiles()
            finally:
                prepare.WIFI_DIRS = original
        self.assertEqual(len(profiles), 2, "enterprise Wi-Fi is skipped")
        for xml_text in profiles:
            xml.dom.minidom.parseString(xml_text.encode())
        home = next(p for p in profiles if "Home" in p)
        self.assertIn("<keyMaterial>p&lt;ss</keyMaterial>", home)
        self.assertIn("<name>Home &amp; Co</name>", home)
        self.assertIn("<authentication>open</authentication>", next(p for p in profiles if "Cafe" in p))

    def test_free_space_parsing(self):
        sample = "  Start        End    Sectors   Size\n 2048     4095     2048     1M\n800000 1953525134 1952725135 931.1G\n"
        original = prepare.run
        prepare.run = lambda *a, **k: sample
        try:
            self.assertEqual(prepare.largest_free("/dev/x"), (800000, 1952725135))
        finally:
            prepare.run = original


class InstallerLook(unittest.TestCase):
    PRODUCT = ROOT / "image/installer/product"

    def test_buildstamp_names_monet(self):
        import configparser
        stamp = configparser.ConfigParser()
        stamp.read(self.PRODUCT / ".buildstamp")
        self.assertEqual(stamp["Main"]["Product"], "Monet")
        self.assertIn("@VERSION@", stamp["Main"]["Version"])

    def test_config_is_where_anaconda_reads_it(self):
        # Anaconda reads conf.d (after Fedora's profile); product.d never.
        import configparser
        self.assertFalse((self.PRODUCT / "etc/anaconda/product.d").exists())
        conf = configparser.ConfigParser()
        conf.read(self.PRODUCT / "etc/anaconda/conf.d/90-monet.conf")
        stylesheet = conf["User Interface"]["custom_stylesheet"]
        self.assertTrue((self.PRODUCT / stylesheet.lstrip("/")).is_file())
        self.assertIn("PasswordSpoke", conf["User Interface"]["hidden_spokes"].split())

    def test_stylesheet_parses_in_gtk3(self):
        # Anaconda loads it with an error check: one bad line and none of it
        # applies. Checked with the GTK 3 Python bindings when they're there.
        css = self.PRODUCT / "usr/share/anaconda/pixmaps/monet.css"
        probe = "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk"
        candidates = [sys.executable, "/usr/bin/python3", shutil.which("python3")]
        python = next((c for c in candidates if c and subprocess.run([c, "-c", probe], capture_output=True).returncode == 0), None)
        if python is None:
            self.skipTest("GTK 3 Python bindings aren't installed")
        # Monet's colors for GTK 3 apps on the desktop too (light and dark),
        # next to a colors.css like the one KDE writes, which they import.
        desktop = sorted((ROOT / "linux/share/monet/gtk/gtk-3.0").glob("*.css"))
        self.assertEqual(len(desktop), 2)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "colors.css").write_text("@define-color theme_bg_color #f3f1ec;\n")
            for path in [css] + desktop:
                label = path.name
                if path in desktop:
                    shutil.copy(path, Path(tmp) / "gtk.css")
                    path = Path(tmp) / "gtk.css"
                check = subprocess.run([python, "-c", "import sys, gi; gi.require_version('Gtk', '3.0'); "
                                        "from gi.repository import Gtk; Gtk.CssProvider().load_from_path(sys.argv[1])",
                                        str(path)], capture_output=True, text=True, env={**os.environ, "DISPLAY": ""})
                self.assertEqual(check.returncode, 0, f"{label}: {check.stderr}")

    def test_stylesheet_targets_anaconda(self):
        css = (self.PRODUCT / "usr/share/anaconda/pixmaps/monet.css").read_text()
        for part in (".logo-sidebar", ".logo", "#nav-box", "#anaconda-name-label", "button.suggested-action",
                     "#anaconda-spoke-window-done", "AnacondaStandaloneWindow .background", "AnacondaSpokeSelector"):
            self.assertIn(part, css)

    def test_fonts_ship_without_replacing_cantarell(self):
        fonts = self.PRODUCT / "usr/share/fonts/monet"
        for name in ("Inter-Regular.otf", "Inter-SemiBold.otf", "Inter-Bold.otf",
                     "Fraunces72ptSuperSoft-Light.ttf", "OFL-Inter.txt", "OFL-Fraunces.txt"):
            self.assertTrue((fonts / name).is_file(), name)
        # Anaconda's screens are laid out for Cantarell at fixed sizes; Inter in
        # its place is wider and pushed labels and buttons out of their boxes.
        self.assertFalse((self.PRODUCT / "etc/fonts/conf.d/00-monet.conf").exists())

    def test_buttons_keep_anacondas_sizes(self):
        css = (self.PRODUCT / "usr/share/anaconda/pixmaps/monet.css").read_text()
        for rule in re.findall(r"([^{}]+)\{([^}]*)\}", css):
            if "button" in rule[0] or "entry" in rule[0] or "done" in rule[0]:
                for prop in ("padding", "min-height", "min-width", "font-size"):
                    self.assertNotIn(prop + ":", rule[1], rule[0].strip())

    def test_artwork_present(self):
        from_css = re.findall(r'url\("(/[^"]+)"\)', (self.PRODUCT / "usr/share/anaconda/pixmaps/monet.css").read_text())
        self.assertTrue(from_css)
        for path in from_css:
            self.assertTrue((self.PRODUCT / path.lstrip("/")).is_file(), path)


class WindowsScripts(unittest.TestCase):
    def test_batch_files_use_crlf_in_checkouts(self):
        attributes = (ROOT / ".gitattributes").read_text()
        self.assertIn("*.cmd text eol=crlf", attributes)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell not installed")
    def test_powershell_parses(self):
        subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "tools/check-powershell.ps1")], check=True)


if __name__ == "__main__":
    sys.exit(unittest.main())
