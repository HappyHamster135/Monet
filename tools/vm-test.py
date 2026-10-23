#!/usr/bin/env python3
"""Boots Monet Setup's USB stick in a virtual machine and walks through it.

    python3 tools/vm-test.py Monet-X-Setup.iso SCREENS/ [--install]

QEMU with KVM and UEFI firmware with Secure Boot on (Microsoft's keys, like a
real PC), a blank 96 GB disk and a wired network. Waits for Monet Setup,
takes a screenshot of each step, and with --install goes on: types a name and
password, chooses "Monet and Windows", installs, confirms Universal Blue's
driver key on the firmware's blue screen, and starts the installed Monet.
Then it looks around Monet the way someone would: signs in, and shows the
desktop, the app menu, Files and Settings, then locks the screen, wakes it
and unlocks it with the password (which says whether Monet's lock screen
really lets people back in).
Screenshots go to SCREENS/ (NN-name.png); the exit code says how far the
install got. The look around never changes it: it prints what it saw.
"""

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

W, H = 1920, 1080
U = min(W / 1440, H / 900)          # Monet Setup's scale on this screen
OVMF = Path("/usr/share/OVMF")


class VM:
    def __init__(self, iso, work):
        self.work = Path(work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.sock = self.work / "qmp.sock"
        disk = self.work / "disk.qcow2"
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), "96G"], check=True)
        code, vars_ = OVMF / "OVMF_CODE_4M.ms.fd", self.work / "vars.fd"
        shutil.copy(OVMF / "OVMF_VARS_4M.ms.fd", vars_)
        cmd = ["qemu-system-x86_64", "-machine", "q35,smm=on", "-accel", "kvm", "-cpu", "host", "-smp", "4",
               "-m", "8192", "-global", "driver=cfi.pflash01,property=secure,value=on",
               "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
               "-drive", f"if=pflash,format=raw,unit=1,file={vars_}",
               "-drive", f"file={iso},media=cdrom,readonly=on,if=none,id=cd", "-device", "ide-cd,drive=cd,bootindex=1",
               "-drive", f"file={disk},if=none,id=hd,format=qcow2", "-device", "virtio-blk-pci,drive=hd,bootindex=2",
               "-device", f"VGA,edid=on,xres={W},yres={H},vgamem_mb=64",
               "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd",
               "-nic", "user,model=virtio-net-pci", "-display", "none",
               "-qmp", f"unix:{self.sock},server,nowait", "-serial", f"file:{self.work / 'serial.log'}"]
        # The journal on the serial port too, so serial.log says why when a screen never comes.
        # systemd (256+) reads these credentials from the VM's firmware; the stick stays as it is.
        for name, text in [
            ("systemd.extra-unit.monet-vm-journal.service",
             "[Service]\nExecStart=/bin/sh -c 'exec journalctl -b -f -o short-monotonic >/dev/ttyS0'\n"),
            ("systemd.unit-dropin.sysinit.target", "[Unit]\nWants=monet-vm-journal.service\n"),
        ]:
            cmd += ["-smbios", f"type=11,value=io.systemd.credential.binary:{name}={base64.b64encode(text.encode()).decode()}"]
        self.proc = subprocess.Popen(cmd, stdout=open(self.work / "qemu.log", "w"), stderr=subprocess.STDOUT)
        for _ in range(100):
            if self.sock.exists():
                break
            time.sleep(0.1)

    def qmp(self, *cmds):
        s = socket.socket(socket.AF_UNIX)
        s.connect(str(self.sock))
        f = s.makefile("rw")
        json.loads(f.readline())
        out = []
        for c in [{"execute": "qmp_capabilities"}, *cmds]:
            f.write(json.dumps(c) + "\n")
            f.flush()
            while True:
                r = json.loads(f.readline())
                if "event" not in r:
                    out.append(r)
                    break
        s.close()
        return out[1:]

    def screen(self):
        ppm = self.work / "now.ppm"
        self.qmp({"execute": "screendump", "arguments": {"filename": str(ppm)}})
        return Image.open(ppm).convert("RGB")

    def click(self, x, y):
        img = self.screen()
        ax, ay = int(x * 32767 / (img.width - 1)), int(y * 32767 / (img.height - 1))
        self.qmp({"execute": "input-send-event", "arguments": {"events": [
            {"type": "abs", "data": {"axis": "x", "value": ax}}, {"type": "abs", "data": {"axis": "y", "value": ay}}]}})
        time.sleep(0.3)
        for down in (True, False):
            self.qmp({"execute": "input-send-event",
                      "arguments": {"events": [{"type": "btn", "data": {"down": down, "button": "left"}}]}})
            time.sleep(0.1)

    def keys(self, *combos):
        for combo in combos:
            self.qmp({"execute": "send-key", "arguments": {"keys": [{"type": "qcode", "data": k}
                                                                       for k in combo.split("-")]}})
            time.sleep(0.25)

    def type(self, text):
        names = {" ": "spc", ".": "dot", "-": "minus", "/": "slash", "'": "apostrophe", ";": "semicolon"}
        for ch in text:
            keys = ["shift", ch.lower()] if ch.isupper() else [names.get(ch, ch)]
            self.qmp({"execute": "send-key", "arguments": {"keys": [{"type": "qcode", "data": k} for k in keys]}})
            time.sleep(0.08)

    def stop(self):
        self.proc.terminate()


def u(n):
    return round(n * U)


# Where things are in Monet Setup (its 1440 x 900 grid, scaled).
SHEET = (u(64), u(64), u(604), H - u(64))
NEXT = (u(540), H - u(123))                               # inside Continue, Restart and Install
NAME_FIELD = (u(300), u(279))                             # person step: name entry
PASSWORD_FIELD = (u(300), u(388))                         # person step: password entry
TRY_AGAIN = (u(130), u(258))                              # failed step: Try again


def brightness(img, box):
    return ImageStat.Stat(img.crop(box).convert("L")).mean[0]


def is_ink(img, point):
    r, g, b = img.getpixel(point)
    return r < 70 and g < 70 and b < 70


def setup_showing(img):
    """The glass sheet (light) over the painting."""
    return brightness(img, (u(80), u(300), u(580), u(600))) > 170 and brightness(img, (u(900), u(20), W - 20, u(60))) < 200


def changed(a, b):
    """How different two screenshots are: 0 (the same) to 255."""
    return ImageStat.Stat(ImageChops.difference(a, b).convert("L")).mean[0]


def settle(vm, seconds, every=5, quiet=1.0):
    """The screen once it stops changing (and isn't black), or None after `seconds`.
    The wallpaper's light and the clock move a little; that's below `quiet`."""
    end = time.time() + seconds
    last = vm.screen()
    while time.time() < end:
        time.sleep(every)
        now = vm.screen()
        if changed(last, now) < quiet and brightness(now, (0, 0, now.width, now.height)) > 12:
            return now
        last = now
    return None


PASSWORD = "monet-test"


def tour(vm, run):
    """Monet as people see it, after the first start: the sign-in screen, the
    desktop, the app menu and its search, the restart and shut-down screen, the
    widget gallery, Files, Settings, and the lock screen, at rest, awake and
    unlocked. Returns whether the password unlocked it."""
    if not settle(vm, 600, every=10):
        run.shot("sign-in-timeout")
        return False
    run.shot("sign-in")
    vm.type(PASSWORD)
    vm.keys("ret")
    time.sleep(30)
    # The first sign-in gives the account Monet's look, which redraws the desktop.
    settle(vm, 300, every=10)
    run.shot("first-sign-in")
    # Whatever opened by itself then (Bazzite's portal, Steam): close it, and
    # dismiss the leave screen in case nothing was open.
    for _ in range(3):
        vm.keys("alt-f4")
        time.sleep(3)
        vm.keys("esc")
        time.sleep(2)
    # Only the processor draws this PC's screen, so Monet starts without glass;
    # the look around is to show the glass, so turn it on, as Settings would.
    vm.keys("ctrl-alt-t")
    time.sleep(8)
    vm.type("/usr/libexec/monet-quick pref glass on")
    vm.keys("ret")
    time.sleep(10)
    vm.keys("ctrl-d")
    time.sleep(3)
    desktop = settle(vm, 90) or vm.screen()
    run.shot("desktop")
    vm.keys("meta_l")
    time.sleep(4)
    run.shot("app-menu")
    # Typing goes straight into the menu's search.
    vm.type("te")
    time.sleep(4)
    run.shot("app-menu-search")
    vm.keys("esc")
    time.sleep(1)
    vm.keys("esc")
    time.sleep(2)
    # Ctrl+Alt+Del asks what to do: Monet's restart and shut-down screen.
    vm.keys("ctrl-alt-delete")
    time.sleep(5)
    run.shot("leave-screen")
    vm.keys("esc")
    time.sleep(3)
    # The widget gallery, opened the way Add Widgets… does, once Terminal has closed.
    vm.keys("ctrl-alt-t")
    time.sleep(8)
    vm.type("setsid -f sh -c 'sleep 4; busctl --user call org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell toggleWidgetExplorer'")
    vm.keys("ret")
    time.sleep(1)
    vm.keys("ctrl-d")
    time.sleep(10)
    run.shot("widget-gallery")
    vm.keys("esc")
    time.sleep(2)
    vm.keys("meta_l-e")
    time.sleep(10)
    settle(vm, 60)
    run.shot("files")
    vm.keys("alt-f4")
    time.sleep(3)
    vm.keys("alt-spc")
    time.sleep(3)
    vm.type("Monet Settings")
    time.sleep(3)
    vm.keys("ret")
    time.sleep(8)
    settle(vm, 60)
    run.shot("settings")
    vm.keys("esc")
    time.sleep(3)
    vm.keys("meta_l-l")
    time.sleep(8)
    settle(vm, 60)
    run.shot("lock-screen")
    vm.keys("shift_r")
    time.sleep(3)
    awake = run.shot("lock-screen-awake")
    vm.type(PASSWORD)
    vm.keys("ret")
    time.sleep(8)
    back = settle(vm, 60) or vm.screen()
    run.shot("unlocked")
    # Unlocked looks like the desktop again; still locked looks like the lock screen.
    return changed(back, desktop) < changed(back, awake)


class Run:
    def __init__(self, vm, out):
        self.vm, self.out, self.n = vm, Path(out), 0
        self.out.mkdir(parents=True, exist_ok=True)

    def shot(self, name):
        self.n += 1
        img = self.vm.screen()
        img.save(self.out / f"{self.n:02d}-{name}.png")
        print(f"{time.strftime('%H:%M:%S')} screenshot {self.n:02d}-{name}", flush=True)
        return img

    def wait(self, test, seconds, every=3, name=None):
        end = time.time() + seconds
        while time.time() < end:
            img = self.vm.screen()
            if test(img):
                return img
            time.sleep(every)
        if name:
            self.shot(name + "-timeout")
        return None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    iso, out = sys.argv[1], sys.argv[2]
    full = "--install" in sys.argv
    vm = VM(iso, Path(out).parent / "vm-work")
    run = Run(vm, out)
    try:
        time.sleep(8)
        run.shot("firmware")
        time.sleep(12)
        run.shot("starting")
        if not run.wait(setup_showing, 300, name="setup"):
            print("Monet Setup didn't appear")
            return 2
        time.sleep(3)
        run.shot("hello")
        vm.click(*NEXT)
        time.sleep(2)
        run.shot("network")
        vm.click(*NEXT)
        time.sleep(2)
        run.shot("person")
        vm.click(*NAME_FIELD)
        vm.type("Test Player")
        vm.click(*PASSWORD_FIELD)
        vm.type("monet-test")
        time.sleep(1)
        run.shot("person-filled")
        vm.click(*NEXT)
        time.sleep(3)
        run.shot("apps")
        vm.click(*NEXT)
        time.sleep(3)
        run.shot("ready")
        if not full:
            return 0
        vm.click(*NEXT)                                    # Erase & Install
        start = time.time()
        while time.time() - start < 3600:
            time.sleep(60)
            img = run.shot(f"installing-{int((time.time() - start) // 60)}m")
            if is_ink(img, NEXT):                          # Restart: done
                break
            if is_ink(img, TRY_AGAIN):
                run.shot("failed")
                return 3
        else:
            return 4
        run.shot("all-set")
        vm.click(*NEXT)
        # The firmware's blue screen for Universal Blue's driver key:
        # Enroll MOK, Continue, Yes, the password, Reboot.
        time.sleep(40)
        run.shot("mok")
        vm.keys("down", "ret")
        time.sleep(2)
        vm.keys("down", "ret")
        time.sleep(2)
        vm.keys("down", "ret")
        time.sleep(2)
        vm.type("monetsetup")
        vm.keys("ret")
        time.sleep(2)
        run.shot("mok-done")
        vm.keys("ret")
        time.sleep(60)
        run.shot("monet-starting")
        try:
            unlocked = tour(vm, run)
            print("tour: the lock screen " + ("unlocked with the password" if unlocked else "did NOT unlock"), flush=True)
        except Exception as e:  # the look around never fails the install test
            print(f"tour: stopped ({e})", flush=True)
            run.shot("tour-stopped")
        return 0
    finally:
        vm.stop()


if __name__ == "__main__":
    sys.exit(main())
