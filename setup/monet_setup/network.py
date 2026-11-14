"""Wi-Fi and wired connections through NetworkManager's nmcli."""

import os
from pathlib import Path
import subprocess

from . import trust
from .words import _


def run(*args, timeout=30):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def fields(line):
    """Splits a line of `nmcli -t` output, where a literal ':' is written '\\:'."""
    out, cur, escaped = [], "", False
    for ch in line:
        if escaped:
            cur += ch
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def parse_wifi(listing):
    """Networks from `nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list`,
    the connected one first, then strongest first."""
    nets = {}
    for line in listing.splitlines():
        f = fields(line)
        if len(f) < 4 or not f[1]:
            continue
        active, ssid, signal, security = f[0] == "*", f[1], f[2], f[3]
        strength = int(signal) if signal.isdigit() else 0
        old = nets.get(ssid)
        if old is None or active or strength > old["signal"]:
            nets[ssid] = {"name": ssid, "signal": strength, "secure": security not in ("", "--"),
                          "active": active or bool(old and old["active"])}
    return sorted(nets.values(), key=lambda n: (not n["active"], -n["signal"]))


def wifi_networks(rescan="no"):
    out = run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
              "--rescan", rescan, timeout=40)
    return parse_wifi(out or "")


def carrier(device):
    try:
        return (Path("/sys/class/net") / device / "carrier").read_text().strip() == "1"
    except OSError:
        return False


def links():
    out = run("nmcli", "-t", "-f", "TYPE,STATE,DEVICE", "device", "status", timeout=3) or ""
    connected = [(f[0], f[2]) for f in map(fields, out.splitlines())
                 if len(f) == 3 and f[1] == "connected"]
    return (any(kind == "ethernet" and carrier(device) for kind, device in connected),
            any(kind == "wifi" for kind, _device in connected))


def check_connection(image):
    try:
        digest = trust.expected(image)
        source = trust.pinned_reference(image, digest) if digest else image
        trust.registry_manifest(source, timeout=8)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or b"").decode("utf-8", "replace")
        return trust.registry_error(details) or _("Can’t reach the Monet download server. Check your connection or continue offline.")
    except subprocess.TimeoutExpired:
        return _("Can’t reach the Monet download server. Check your connection or continue offline.")
    except (OSError, ValueError):
        return _("Setup couldn’t check the download server.")
    return ""


def join(name, password):
    """Connects to a Wi-Fi network; an empty string when it worked, otherwise
    what to tell the person."""
    args = ["nmcli", "device", "wifi", "connect", name]
    if password:
        args += ["password", password]
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=60,
                              env={**os.environ, "LC_ALL": "C"})
    except subprocess.TimeoutExpired:
        return _("The network didn't answer. Try again, or pick another network.")
    except OSError:
        return _("Wi-Fi isn't available on this PC.")
    if done.returncode == 0:
        return ""
    reason = (done.stderr or done.stdout).lower()
    if "secrets were required" in reason or "802-1x" in reason or "password" in reason:
        return _("That password didn't work.")
    return _("Couldn't connect. Try again, or pick another network.")
