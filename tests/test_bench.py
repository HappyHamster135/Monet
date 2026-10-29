"""The test bench (tools/vm.py): what it asks Hyper-V for, checked without Hyper-V."""
import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("vm", ROOT / "tools/vm.py")
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)


def asked(*argv, answer=""):
    """What main() asks PowerShell for (its environment), with PowerShell faked."""
    calls = []

    def fake(script, **env):
        calls.append((script, env))
        return answer

    with mock.patch.object(vm, "powershell", fake):
        vm.main(list(argv))
    return calls


class Keys(unittest.TestCase):
    def test_combos_become_virtual_keys(self):
        self.assertEqual(vm.combo("enter"), ([], 0x0D))
        self.assertEqual(vm.combo("ctrl+alt+t"), ([0x11, 0x12], 0x54))
        self.assertEqual(vm.combo("Meta"), ([], 0x5B))
        self.assertEqual(vm.combo("shift+f10"), ([0x10], 0x79))
        for bad in ("", "ctrl+", "hyper", "t+ctrl", "a+b"):
            with self.assertRaises(SystemExit, msg=bad):
                vm.combo(bad)

    def test_keys_and_text_go_through_the_environment(self):
        script, env = asked("keys", "ctrl+alt+t", "enter")[0]
        self.assertEqual(env["MONET_KEYS"], "17,18,84;13")
        self.assertIn("$kb.PressKey($m)", script)
        # Typed key by key as a US keyboard would (Hyper-V's TypeText lost most letters in Monet).
        script, env = asked("type", "Hi ~/a_b")[0]
        self.assertEqual(env["MONET_KEYS"], "16,72;73;32;16,192;191;65;16,189;66")
        self.assertNotIn("TypeText", script)
        self.assertEqual(vm.keystrokes('"|'), [([0x10], 0xDE), ([0x10], 0xDC)])
        for bad in ("héllo", "two\nlines", "tab\there"):
            with self.assertRaises(SystemExit):
                asked("type", bad)


class Mouse(unittest.TestCase):
    def test_clicks_and_drags(self):
        _, env = asked("click", "5", "6", "--right", "--double")[0]
        self.assertEqual((env["MONET_MOUSE"], env["MONET_POINTS"], env["MONET_BUTTON"], env["MONET_CLICKS"]), ("click", "5,6", 2, 2))
        _, env = asked("drag", "1", "2", "30", "40")[0]
        self.assertEqual((env["MONET_MOUSE"], env["MONET_POINTS"], env["MONET_BUTTON"]), ("drag", "1,2;30,40", 1))


class Screen(unittest.TestCase):
    def test_hyper_vs_picture_becomes_a_png(self):
        # Two pixels, 5-6-5: pure red, pure blue.
        picture = struct.pack("<2H", 0xF800, 0x001F)
        data = vm.png(2, 1, picture)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        chunks, at = {}, 8
        while at < len(data):
            length, kind = struct.unpack(">I4s", data[at:at + 8])
            body = data[at + 8:at + 8 + length]
            self.assertEqual(struct.unpack(">I", data[at + 8 + length:at + 12 + length])[0], zlib.crc32(kind + body) & 0xFFFFFFFF)
            chunks[kind] = body
            at += 12 + length
        self.assertEqual(struct.unpack(">II", chunks[b"IHDR"][:8]), (2, 1))
        self.assertEqual(zlib.decompress(chunks[b"IDAT"]), b"\0" + bytes([255, 0, 0, 0, 0, 255]))
        with self.assertRaises(SystemExit):
            vm.png(4, 4, picture)

    def test_screen_saves_what_hyper_v_sent(self):
        import base64
        answer = "2 1\n" + base64.b64encode(struct.pack("<2H", 0xF800, 0x001F)).decode()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shot.png"
            script, _ = asked("screen", str(out), answer=answer)[0]
            self.assertTrue(out.read_bytes().startswith(b"\x89PNG"))
        self.assertIn("GetVirtualSystemThumbnailImage($vssd, $w, $h)", script)


class Safety(unittest.TestCase):
    def test_names_never_reach_powershell_unchecked(self):
        for argv in (["--vm", "Monet'; Remove-VM *", "state"], ["checkpoint", "a b"], ["restore", "../x"], ["ip", "--set", "evil"]):
            with self.assertRaises(SystemExit, msg=argv):
                asked(*argv)
        script, env = asked("checkpoint", "fresh-0.9.4")[0]
        self.assertEqual(env["MONET_ARG"], "fresh-0.9.4")
        self.assertIn("$env:MONET_ARG", script)

    def test_ssh_setup_only_lets_its_own_key_in(self):
        line = vm.guest_setup("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample+/= monet-testbench")
        self.assertTrue(line.isascii())
        self.assertIn("sudo systemctl enable --now sshd", line)
        self.assertIn("firewall-cmd --permanent --add-service=ssh", line)
        key_only = vm.guest_setup("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample+/= monet-testbench", key_only=True)
        self.assertNotIn("sudo", key_only)
        self.assertIn("authorized_keys", key_only)
        for bad in ("ssh-rsa AAAA monet-testbench", "ssh-ed25519 AAAA' && rm -rf ~ '", "ssh-ed25519 AAAA someone"):
            with self.assertRaises(SystemExit):
                vm.guest_setup(bad)

    def test_a_drag_can_stop_halfway(self):
        (script, env), = asked("press", "300", "40")
        self.assertEqual((env["MONET_MOUSE"], env["MONET_POINTS"], env["MONET_BUTTON"]), ("press", "300,40", 1))
        self.assertIn("SetButtonState($button, $true)", script)
        (script, env), = asked("release", "960", "2", "--right")
        self.assertEqual((env["MONET_MOUSE"], env["MONET_BUTTON"]), ("release", 2))

    def test_the_wheel_turns_notch_by_notch(self):
        (script, env), = asked("scroll", "1100", "650", "-5")
        self.assertEqual((env["MONET_MOUSE"], env["MONET_POINTS"], env["MONET_NOTCHES"]), ("scroll", "1100,650", -5))
        self.assertIn("$mouse.SetScrollPosition([Math]::Sign($notches) * 120)", script)

    def test_the_tests_go_to_the_vm_as_linux_has_them(self):
        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(vm.checkout())) as tar:
            names = tar.getnames()
            self.assertIn("tests/test_look.py", names)
            self.assertFalse([n for n in names if n.split("/")[0] in (".git", "target", ".claude") or "__pycache__" in n])
            script = tar.extractfile("linux/libexec/monet-light").read()
            self.assertNotIn(b"\r\n", script)  # Git for Windows' line ends would break bash there
            self.assertEqual(tar.getmember("linux/libexec/monet-light").mode, 0o755)
        with self.assertRaises(SystemExit), mock.patch.object(vm, "remembered", lambda name: "j"):
            vm.main(["tests", "tests.test_look; rm -rf ~"])

    def test_the_vm_is_made_strong_enough(self):
        script = (ROOT / "tools/hyperv-vm.ps1").read_text(encoding="utf-8")
        self.assertIn("[int]$MemoryGB = 16", script)
        self.assertIn("$Processors = [math]::Max(4, [math]::Min(12, $logical - 4))", script)
        self.assertIn("-CheckpointType Standard", script)
        self.assertIn("[switch]$Tune", script)


if __name__ == "__main__":
    unittest.main()
