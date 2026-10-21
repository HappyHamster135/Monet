"""Checks for the installer pieces that can run without real hardware.

    python3 -m unittest discover -s tests
"""

import builtins
import importlib.machinery
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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

    def plan(self, cmdline, devices=None):
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
        fake.run = lambda cmd, **kw: types.SimpleNamespace(
            stdout=json.dumps({"blockdevices": devices}) if cmd[0] == "lsblk" else "/dev/sda1\n")

        def fake_open(path, mode="r", *a, **k):
            return io.StringIO(cmdline) if path == "/proc/cmdline" else Sink(path)

        def fake_import(name, *a, **k):
            return fake if name == "subprocess" else __import__(name, *a, **k)

        env = {"__builtins__": dict(vars(builtins), open=fake_open, print=lambda *a: None, __import__=fake_import)}
        exec(code, env)
        return written["/tmp/monet-storage.ks"]

    def test_erase_picks_internal_disk(self):
        plan = self.plan("inst.stage2=hd:LABEL=Fedora-E-dvd-x86_64-44 quiet")
        self.assertIn("ignoredisk --only-use=nvme0n1", plan)
        self.assertIn("clearpart --all --initlabel --disklabel=gpt --drives=nvme0n1", plan)
        size = int(re.search(r"--size=(\d+)", plan).group(1))
        total = 1_000_204_886_016 // 2**20
        self.assertGreater(total - size, 100 * 1024, "room left for Windows")
        self.assertGreater(size, 64 * 1024)

    def test_download_check_compiles(self):
        ks = (ROOT / "image/monet.ks").read_text()
        code = re.search(r"%pre-install[^\n]*\n(.*?)\n%end", ks, re.S).group(1)
        compile(code.replace("@IMAGE@", "ghcr.io/example/monet:latest"), "pre-install", "exec")

    def test_keep_asks(self):
        self.assertEqual(self.plan("inst.stage2=hd:LABEL=X monet.keep"), "")

    def test_no_internal_disk_asks(self):
        self.assertEqual(self.plan("quiet", devices=self.DEVICES[:3]), "")


class PrepareWindows(unittest.TestCase):
    def test_windows_names(self):
        self.assertEqual(prepare.windows_name("anna/ lind"), "annalind")
        self.assertEqual(prepare.windows_name("[]:"), "Player")
        self.assertEqual(len(prepare.windows_name("x" * 40)), 20)

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

    def test_free_space_parsing(self):
        sample = "  Start        End    Sectors   Size\n 2048     4095     2048     1M\n800000 1953525134 1952725135 931.1G\n"
        original = prepare.run
        prepare.run = lambda *a, **k: sample
        try:
            self.assertEqual(prepare.largest_free("/dev/x"), (800000, 1952725135))
        finally:
            prepare.run = original


class WindowsScripts(unittest.TestCase):
    def test_batch_files_use_crlf_in_checkouts(self):
        attributes = (ROOT / ".gitattributes").read_text()
        self.assertIn("*.cmd text eol=crlf", attributes)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell not installed")
    def test_powershell_parses(self):
        subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "tools/check-powershell.ps1")], check=True)


if __name__ == "__main__":
    sys.exit(unittest.main())
