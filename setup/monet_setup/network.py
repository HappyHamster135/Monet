"""Wi-Fi and wired connections through NetworkManager's nmcli."""

import os
from pathlib import Path
import subprocess

from .words import _

NET = Path("/sys/class/net")


def plain_env():
    """nmcli in plain English, so its states and errors read the same in every language,
    with UTF-8 kept: in the C locale it writes a Wi-Fi name like "Café" as "Caf?"."""
    env = {k: v for k, v in os.environ.items() if k != "LANGUAGE"}
    env["LC_ALL"] = "C.UTF-8"
    return env


def run(*args, timeout=30):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=plain_env())
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


def wifi_networks(rescan=False):
    out = run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
              "--rescan", "yes" if rescan else "auto", timeout=40)
    return parse_wifi(out or "")


def unplugged(device):
    """True when the network port says its cable is out. NetworkManager waits a few
    seconds before it calls the connection gone; a port that doesn't say counts as in."""
    try:
        return (NET / device / "carrier").read_text().strip() == "0"
    except (OSError, ValueError):
        return False


def links():
    """(cable, Wi-Fi): whether each is connected now, or None when NetworkManager didn't say."""
    out = run("nmcli", "-t", "-f", "TYPE,STATE,DEVICE", "device", "status", timeout=5)
    if out is None:
        return None
    connected = [(f[0], f[2]) for f in map(fields, out.splitlines()) if len(f) == 3 and f[1] == "connected"]
    return (any(kind == "ethernet" and not unplugged(device) for kind, device in connected),
            any(kind == "wifi" for kind, _device in connected))


def wired():
    """True when a cable connection is up."""
    return bool((links() or (False, False))[0])


def online():
    """True when NetworkManager reaches the internet."""
    return (run("nmcli", "networking", "connectivity", "check", timeout=15) or "").strip() == "full"


def join(name, password):
    """Connects to a Wi-Fi network; an empty string when it worked, otherwise
    what to tell the person."""
    args = ["nmcli", "device", "wifi", "connect", name]
    if password:
        args += ["password", password]
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=60, env=plain_env())
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
