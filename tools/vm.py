#!/usr/bin/env python3
"""Monet's test bench: the Hyper-V virtual machine on this Windows PC (tools/hyperv-vm.ps1),
driven from the command line by a person or an AI (Claude Code, Codex): its screen as a
picture, its keyboard and mouse, a shell inside it over SSH, and checkpoints that take it
back to where it was in seconds. Nothing to install: Windows' own PowerShell and OpenSSH.

    python tools/vm.py state | start | stop [--hard]
    python tools/vm.py screen OUT.png             what's on its screen, at its own size
    python tools/vm.py click X Y [--right] [--double]
    python tools/vm.py move X Y
    python tools/vm.py drag X1 Y1 X2 Y2
    python tools/vm.py press X Y | release X Y     the button down there, and up: a drag to look at
                                                   halfway (move between them, a screen in between)
    python tools/vm.py scroll X Y NOTCHES          the wheel turned there (negative: down)
    python tools/vm.py type TEXT                   types it (plain ASCII; keys for the rest)
    python tools/vm.py keys KEY...                 enter, esc, tab, meta, ctrl+alt+t, f2, a...
    python tools/vm.py checkpoint NAME | restore NAME | checkpoints
    python tools/vm.py ip [--set ADDRESS]          its address on the Default Switch
    python tools/vm.py ssh-setup [--user NAME]     types what lets this PC in, into the VM's Terminal
    python tools/vm.py ssh COMMAND...              runs a command inside it
    python tools/vm.py tests [NAME...]             this checkout's tests, run inside it (Linux: the ones
                                                   Windows can't run too), all or the ones named

--vm NAME (or MONET_VM) picks another VM than "Monet". Hyper-V wants an administrator or a
member of Hyper-V Administrators (docs/TESTBENCH.md).
"""

import argparse
import base64
import io
import os
import re
import struct
import subprocess
import sys
import tarfile
import time
import zlib
from pathlib import Path

BENCH = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Monet" / "testbench"
KEY = BENCH / "id_ed25519"

# Windows' virtual-key codes, which Hyper-V's keyboard takes.
KEYS = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "backspace": 0x08, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23, "pageup": 0x21,
    "pagedown": 0x22, "delete": 0x2E, "insert": 0x2D, "menu": 0x5D, "printscreen": 0x2C,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "meta": 0x5B, "super": 0x5B, "win": 0x5B,
    "minus": 0xBD, "plus": 0xBB, "equal": 0xBB, "comma": 0xBC, "period": 0xBE, "slash": 0xBF,
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
    **{chr(c): ord(chr(c).upper()) for c in range(ord("a"), ord("z") + 1)},
    **{str(d): 0x30 + d for d in range(10)},
}
MODIFIERS = {0x11, 0x12, 0x10, 0x5B}


def combo(text):
    """'ctrl+alt+t' -> ([ctrl, alt], t), as virtual-key codes."""
    names = text.lower().split("+")
    if any(n not in KEYS for n in names):
        raise SystemExit(f"not a key: {text} (keys: {', '.join(sorted(k for k in KEYS if len(k) > 1))}, a-z, 0-9)")
    codes = [KEYS[n] for n in names]
    if any(c not in MODIFIERS for c in codes[:-1]):
        raise SystemExit(f"only ctrl, alt, shift and meta go before the last key: {text}")
    return codes[:-1], codes[-1]


def png(width, height, rgb565):
    """A PNG of Hyper-V's screen picture (16 bits a pixel, 5-6-5), with nothing but the standard library."""
    if len(rgb565) < width * height * 2:
        raise SystemExit("the VM's picture came back short")
    table = [bytes((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)) for v in range(65536)]
    pixels = struct.unpack(f"<{width * height}H", rgb565[:width * height * 2])
    raw = b"".join(b"\0" + b"".join(table[v] for v in pixels[y * width:(y + 1) * width]) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# Each piece of PowerShell finds the VM first ($vm, through Hyper-V's WMI), from MONET_VM.
FIND = r"""
$ErrorActionPreference = 'Stop'
$ns = 'root\virtualization\v2'
try {
    $vm = Get-WmiObject -Namespace $ns -Class Msvm_ComputerSystem -Filter ("ElementName='" + $env:MONET_VM + "'")
} catch {
    [Console]::Error.WriteLine("Hyper-V said no: run as administrator, or join Hyper-V Administrators (docs/TESTBENCH.md).")
    exit 3
}
if (-not $vm) { throw "There's no VM called $env:MONET_VM here, or no rights to see it (Hyper-V Administrators: docs/TESTBENCH.md)." }
function Check($result, $what) { if ($result.ReturnValue -ne 0) { throw "$what failed ($($result.ReturnValue))" } }
"""

SCREEN = FIND + r"""
$head = $vm.GetRelated('Msvm_VideoHead') | Select-Object -First 1
$w = [int]$head.CurrentHorizontalResolution
$h = [int]$head.CurrentVerticalResolution
if ($w -le 0 -or $h -le 0) { $w = 1920; $h = 1080 }
$svc = Get-WmiObject -Namespace $ns -Class Msvm_VirtualSystemManagementService
$vssd = $vm.GetRelated('Msvm_VirtualSystemSettingData') | Where-Object { $_.VirtualSystemType -eq 'Microsoft:Hyper-V:System:Realized' } | Select-Object -First 1
$r = $svc.GetVirtualSystemThumbnailImage($vssd, $w, $h)
Check $r 'the screen picture'
"$w $h"
[Convert]::ToBase64String($r.ImageData)
"""

# Key by key (Hyper-V's own TypeText loses most of a Linux guest's letters), a pause after each.
KEYBOARD = FIND + r"""
$kb = $vm.GetRelated('Msvm_Keyboard') | Select-Object -First 1
$pause = [int]$env:MONET_PAUSE
foreach ($combo in ($env:MONET_KEYS -split ';' | Where-Object { $_ })) {
    $codes = @($combo -split ',' | ForEach-Object { [int]$_ })
    $mods = @(if ($codes.Count -gt 1) { $codes[0..($codes.Count - 2)] })
    foreach ($m in $mods) { Check $kb.PressKey($m) 'a key' }
    Check $kb.TypeKey($codes[-1]) 'a key'
    [array]::Reverse($mods)
    foreach ($m in $mods) { Check $kb.ReleaseKey($m) 'a key' }
    Start-Sleep -Milliseconds $pause
}
"""

# What a US keyboard types with each key, shifted or not.
PLAIN = "`1234567890-=[]\\;',./"
SHIFTED = '~!@#$%^&*()_+{}|:"<>?'
OEM = {"`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF}


def keystrokes(text):
    """The keys a US keyboard types `text` with: [(modifiers, key)], as virtual-key codes."""
    out = []
    for c in text:
        shift = c.isupper() or c in SHIFTED
        plain = PLAIN[SHIFTED.index(c)] if c in SHIFTED else c.lower()
        if plain == " ":
            key = 0x20
        elif plain.isascii() and (plain.isalpha() or plain.isdigit()):
            key = ord(plain.upper())
        elif plain in OEM:
            key = OEM[plain]
        else:
            raise SystemExit(f"type takes one line of plain ASCII, not {c!r}; use keys for Enter and the rest")
        out.append(([0x10] if shift else [], key))
    return out


def keys_env(combos):
    return ";".join(",".join(map(str, [*m, k])) for m, k in combos)

MOUSE = FIND + r"""
$mouse = $vm.GetRelated('Msvm_SyntheticMouse') | Select-Object -First 1
if (-not $mouse) { throw "the VM has no synthetic mouse yet (is Monet up?)" }
$points = @($env:MONET_POINTS -split ';' | Where-Object { $_ } | ForEach-Object { ,@($_ -split ',' | ForEach-Object { [int]$_ }) })
$button = [int]$env:MONET_BUTTON
Check $mouse.SetAbsolutePosition($points[0][0], $points[0][1]) 'moving the mouse'
Start-Sleep -Milliseconds 80
if ($env:MONET_MOUSE -eq 'click') {
    for ($i = 0; $i -lt [int]$env:MONET_CLICKS; $i++) { Check $mouse.ClickButton($button) 'a click'; Start-Sleep -Milliseconds 70 }
} elseif ($env:MONET_MOUSE -eq 'drag') {
    Check $mouse.SetButtonState($button, $true) 'pressing'
    $from = $points[0]; $to = $points[1]
    for ($s = 1; $s -le 12; $s++) {
        Check $mouse.SetAbsolutePosition([int]($from[0] + ($to[0] - $from[0]) * $s / 12), [int]($from[1] + ($to[1] - $from[1]) * $s / 12)) 'dragging'
        Start-Sleep -Milliseconds 25
    }
    Check $mouse.SetButtonState($button, $false) 'letting go'
} elseif ($env:MONET_MOUSE -eq 'press') {
    Check $mouse.SetButtonState($button, $true) 'pressing'
} elseif ($env:MONET_MOUSE -eq 'release') {
    Check $mouse.SetButtonState($button, $false) 'letting go'
} elseif ($env:MONET_MOUSE -eq 'scroll') {
    # A wheel's notches, one at a time as a hand turns it (negative: down).
    $notches = [int]$env:MONET_NOTCHES
    for ($i = 0; $i -lt [Math]::Abs($notches); $i++) {
        Check $mouse.SetScrollPosition([Math]::Sign($notches) * 120) 'turning the wheel'
        Start-Sleep -Milliseconds 60
    }
}
"""

# The Hyper-V module's own commands, for the rest.
MODULE = {
    "state": "(Get-VM -Name $env:MONET_VM).State",
    "start": "Start-VM -Name $env:MONET_VM",
    "stop": "Stop-VM -Name $env:MONET_VM -Force",
    "turnoff": "Stop-VM -Name $env:MONET_VM -TurnOff -Force",
    "checkpoint": "Checkpoint-VM -Name $env:MONET_VM -SnapshotName $env:MONET_ARG",
    "restore": ("Restore-VMCheckpoint -VMName $env:MONET_VM -Name $env:MONET_ARG -Confirm:$false\n"
                "if ((Get-VM -Name $env:MONET_VM).State -ne 'Running') { Start-VM -Name $env:MONET_VM }"),
    "checkpoints": "Get-VMCheckpoint -VMName $env:MONET_VM | ForEach-Object { '{0}  {1:yyyy-MM-dd HH:mm}' -f $_.Name, $_.CreationTime }",
    # Its address: Hyper-V's own when Linux tells it (hv_kvp_daemon), else this PC's neighbor table.
    "ip": r"""
$adapter = Get-VMNetworkAdapter -VMName $env:MONET_VM | Select-Object -First 1
$ip = $adapter.IPAddresses | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } | Select-Object -First 1
if (-not $ip) {
    $mac = ($adapter.MacAddress -replace '(..)(?=.)', '$1-')
    $ip = (Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.LinkLayerAddress -eq $mac } | Select-Object -First 1).IPAddress
}
$ip
""",
}


def powershell(script, **env):
    """Runs a piece of PowerShell with its arguments in the environment (never in the script),
    and returns what it printed; its complaints end this program."""
    # Its errors as plain words, without its progress notes (which it sends as XML to a program).
    wrapped = (f"$ErrorActionPreference = 'Stop'\n$ProgressPreference = 'SilentlyContinue'\ntry {{\n{script}\n}}"
               " catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }")
    encoded = base64.b64encode(wrapped.encode("utf-16-le")).decode()
    run_env = dict(os.environ, **{k: str(v) for k, v in env.items()})
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-EncodedCommand", encoded], capture_output=True, text=True, env=run_env)
    if done.returncode != 0:
        said = [line for line in (done.stderr + done.stdout).splitlines() if line.strip() and not line.startswith(("#< CLIXML", "<Objs"))]
        raise SystemExit(said[0] if said else f"PowerShell failed ({done.returncode})")
    return done.stdout


def remembered(name):
    try:
        return (BENCH / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def remember(name, value):
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / name).write_text(value, encoding="utf-8")


def address(vm):
    ip = remembered("ip") or powershell(MODULE["ip"], MONET_VM=vm).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip):
        raise SystemExit("Can't tell the VM's address: in its Terminal, `ip -4 -br addr`; then python tools/vm.py ip --set ADDRESS")
    return ip


def ssh_key():
    """This bench's own key (made once): only the test VM is ever given it."""
    if not KEY.exists():
        BENCH.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "monet-testbench", "-f", str(KEY)], check=True)
    return KEY.with_suffix(".pub").read_text(encoding="utf-8").strip()


def guest_setup(public, key_only=False):
    """What lets the bench in, typed into the VM's Terminal: its key for this account, SSH on,
    and the firewall letting SSH in (unless the person did those, which need the password).
    Only ever for the test VM: Monet keeps SSH off."""
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]+ monet-testbench", public):
        raise SystemExit("the bench's key isn't one it made")
    key = f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{public}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    services = (" && sudo systemctl enable --now sshd && sudo firewall-cmd --permanent --add-service=ssh"
                " && sudo firewall-cmd --reload")
    return key + ("" if key_only else services) + " && ip -4 -br addr"


def checkout():
    """This checkout as a tar for the VM: no build output, Git's insides or caches, and text
    with Linux's line ends (Git for Windows gives it Windows' ones)."""
    root = Path(__file__).resolve().parent.parent
    skip = {".git", "target", ".claude", "__pycache__"}
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tar:
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in skip)
            for name in sorted(files):
                path = Path(folder) / name
                data = path.read_bytes()
                if b"\0" not in data[:8192]:
                    data = data.replace(b"\r\n", b"\n")
                info = tarfile.TarInfo(path.relative_to(root).as_posix())
                info.size, info.mode, info.mtime = len(data), 0o755 if data.startswith(b"#!") else 0o644, int(path.stat().st_mtime)
                tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Drive Monet's test VM (docs/TESTBENCH.md).")
    parser.add_argument("--vm", default=os.environ.get("MONET_VM", "Monet"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("state", "start", "checkpoints"):
        sub.add_parser(name)
    sub.add_parser("stop").add_argument("--hard", action="store_true", help="turn it off, as pulling the plug")
    sub.add_parser("screen").add_argument("out")
    click = sub.add_parser("click")
    click.add_argument("x", type=int)
    click.add_argument("y", type=int)
    click.add_argument("--right", action="store_true")
    click.add_argument("--double", action="store_true")
    for name in ("move", "press", "release"):
        at = sub.add_parser(name)
        at.add_argument("x", type=int)
        at.add_argument("y", type=int)
        at.add_argument("--right", action="store_true")
    drag = sub.add_parser("drag")
    for n in ("x1", "y1", "x2", "y2"):
        drag.add_argument(n, type=int)
    scroll = sub.add_parser("scroll")
    for n in ("x", "y", "notches"):
        scroll.add_argument(n, type=int)
    sub.add_parser("type").add_argument("text")
    sub.add_parser("keys").add_argument("keys", nargs="+")
    for name in ("checkpoint", "restore"):
        sub.add_parser(name).add_argument("name")
    sub.add_parser("ip").add_argument("--set")
    setup = sub.add_parser("ssh-setup")
    setup.add_argument("--user")
    setup.add_argument("--key-only", action="store_true", help="SSH and the firewall are on already (done by hand with sudo)")
    sub.add_parser("ssh").add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("tests").add_argument("names", nargs="*")
    args = parser.parse_args(argv)
    vm = args.vm
    if not re.fullmatch(r"[\w .-]{1,64}", vm):
        raise SystemExit(f"not a VM name: {vm}")

    if args.cmd == "screen":
        lines = powershell(SCREEN, MONET_VM=vm).split()
        width, height = int(lines[0]), int(lines[1])
        Path(args.out).write_bytes(png(width, height, base64.b64decode(lines[2])))
        print(f"{args.out}: {width}x{height}")
    elif args.cmd in ("click", "move", "drag", "press", "release", "scroll"):
        points = [(args.x, args.y)] if args.cmd != "drag" else [(args.x1, args.y1), (args.x2, args.y2)]
        powershell(MOUSE, MONET_VM=vm, MONET_MOUSE=args.cmd, MONET_POINTS=";".join(f"{x},{y}" for x, y in points),
                   MONET_BUTTON=2 if getattr(args, "right", False) else 1, MONET_CLICKS=2 if getattr(args, "double", False) else 1,
                   MONET_NOTCHES=getattr(args, "notches", 0))
    elif args.cmd == "type":
        powershell(KEYBOARD, MONET_VM=vm, MONET_KEYS=keys_env(keystrokes(args.text)), MONET_PAUSE=15)
    elif args.cmd == "keys":
        powershell(KEYBOARD, MONET_VM=vm, MONET_KEYS=keys_env([combo(k) for k in args.keys]), MONET_PAUSE=120)
    elif args.cmd in ("checkpoint", "restore"):
        if not re.fullmatch(r"[\w.-]{1,40}", args.name):
            raise SystemExit("a checkpoint's name: letters, digits, . _ -")
        powershell(MODULE[args.cmd], MONET_VM=vm, MONET_ARG=args.name)
        print(f"{args.cmd}: {args.name}")
    elif args.cmd == "stop":
        powershell(MODULE["turnoff" if args.hard else "stop"], MONET_VM=vm)
    elif args.cmd == "ip":
        if args.set:
            if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", args.set):
                raise SystemExit("an address like 172.20.144.5")
            remember("ip", args.set)
        print(address(vm))
    elif args.cmd == "ssh-setup":
        if args.user:
            if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", args.user):
                raise SystemExit("not an account name")
            remember("user", args.user)
        line = keystrokes(guest_setup(ssh_key(), args.key_only)) + [([], KEYS["enter"])]
        powershell(KEYBOARD, MONET_VM=vm, MONET_KEYS=keys_env(line), MONET_PAUSE=15)
        print("Typed it into what has the keyboard in the VM (its Terminal, which you opened)."
              + ("" if args.key_only else " sudo asks for the password there: the person types it."))
    elif args.cmd in ("ssh", "tests"):
        user = remembered("user")
        if not user:
            raise SystemExit("Which account? python tools/vm.py ssh-setup --user NAME first")
        ssh_key()
        target = f"{user}@{address(vm)}"
        known = BENCH / "known_hosts"
        command, given = args.command if args.cmd == "ssh" else [], None
        if args.cmd == "tests":
            if not all(re.fullmatch(r"[\w.]+", n) for n in args.names):
                raise SystemExit("test names like tests.test_look.Light")
            # A fresh copy each time, in the VM's /tmp: nothing of the person's is touched.
            command = ["rm -rf /tmp/monet-tests && mkdir -p /tmp/monet-tests && tar -C /tmp/monet-tests -xf - && "
                       "cd /tmp/monet-tests && python3 " + ("-m unittest " + " ".join(args.names) if args.names else "tools/test.py")]
            given = checkout()
        return subprocess.run(["ssh", "-i", str(KEY), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
                               "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={known}",
                               "-o", "ConnectTimeout=10", target, *command], input=given).returncode
    else:
        out = powershell(MODULE[args.cmd], MONET_VM=vm).strip()
        if out:
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
