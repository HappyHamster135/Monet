"""Can this PC run Monet, and which Monet? What Setup looks at before anything is
erased: the graphics, which choose the image (NVIDIA's open driver, for GTX 16 and
RTX 20 and newer, or AMD's and Intel's, Mesa, which also drives older NVIDIA cards
with the open nouveau driver), and the memory. UEFI needs no check: the stick only
starts that way.
"""

import json
import shutil
import subprocess
from pathlib import Path

NVIDIA = "10de"
# NVIDIA's open driver starts with Turing (GTX 16, RTX 20), whose chips' PCI ids begin at 1e00.
TURING = 0x1E00


def graphics(devices=Path("/sys/bus/pci/devices")):
    """(vendor, device) of each display controller, like ("10de", "2684")."""
    found = []
    for dev in sorted(devices.glob("*")):
        try:
            if (dev / "class").read_text().strip().startswith("0x03"):
                found.append(((dev / "vendor").read_text().strip().lower().removeprefix("0x"),
                              (dev / "device").read_text().strip().lower().removeprefix("0x")))
        except OSError:
            continue
    return found


def memory(meminfo=Path("/proc/meminfo")):
    """The memory in GB (GiB, as the PC counts it), or None."""
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 1024 ** 2
    except (OSError, ValueError, IndexError):
        pass
    return None


def tpm2(chips=Path("/sys/class/tpm")):
    """Whether the PC has a TPM 2.0, the security chip that unlocks an encrypted disk by itself."""
    for chip in sorted(chips.glob("tpm[0-9]*")):
        try:
            if (chip / "tpm_version_major").read_text().strip() == "2":
                return True
        except OSError:
            continue
    return False


def check(cards=None, gb=None, tpm=None):
    """{"newNvidia": a GTX 16 / RTX 20 or newer, "oldNvidia": "only" (nothing else to draw with),
    "beside" (built-in graphics too) or "", "memory": GB or None, "tpm": a TPM 2.0}."""
    cards = graphics() if cards is None else cards
    gb = memory() if gb is None else gb
    old = [c for c in cards if c[0] == NVIDIA and int(c[1], 16) < TURING]
    rest = [c for c in cards if c not in old]
    return {"newNvidia": any(c[0] == NVIDIA for c in rest), "memory": gb,
            "oldNvidia": "only" if old and not rest else "beside" if old else "",
            "tpm": tpm2() if tpm is None else tpm}


# Universal Blue's key, which Monet's kernel and drivers are signed with: Monet Setup leaves a
# copy on the EFI partition, for when the firmware hasn't been told to trust it yet.
ESP_KEY = "EFI/Monet/monet-key.der"
ESP_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
WORK = Path("/run/monet-setup")
MOK_PASSWORD = "monetsetup"


def said(*args, input=None, timeout=60):
    """What a command printed (and its errors), or "" when it couldn't run."""
    try:
        done = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout + done.stderr


def untrusted_key(work=WORK):
    """A Monet installed here that can't start: Secure Boot is on, and its key isn't trusted
    (the blue screen at its first start was skipped: it opens on Continue boot). The key,
    copied off its EFI partition, or None."""
    if "SecureBoot enabled" not in said("mokutil", "--sb-state"):
        return None
    try:
        devices = json.loads(said("lsblk", "-J", "-p", "-o", "PATH,PARTTYPE") or "{}").get("blockdevices") or []
    except ValueError:
        return None
    esps, pending = [], list(devices)
    while pending:
        dev = pending.pop()
        pending.extend(dev.get("children") or [])
        if (dev.get("parttype") or "").lower() == ESP_TYPE:
            esps.append(dev["path"])
    mount, key = work / "esp", work / "monet-key.der"
    for esp in esps:
        mount.mkdir(parents=True, exist_ok=True)
        if subprocess.run(["mount", "-o", "ro", esp, str(mount)], capture_output=True).returncode != 0:
            continue
        try:
            if (mount / ESP_KEY).is_file():
                shutil.copyfile(mount / ESP_KEY, key)
        finally:
            subprocess.run(["umount", str(mount)], capture_output=True)
        if key.is_file():
            return key if "is not enrolled" in said("mokutil", "--test-key", str(key)) else None
    return None


def trust(key):
    """Asks the firmware to trust the key at the next start (the blue screen, which waits)."""
    said("mokutil", "--timeout", "-1")
    said("mokutil", "--import", str(key), input=f"{MOK_PASSWORD}\n{MOK_PASSWORD}\n")


def image_for(image, facts):
    """Monet for this PC's graphics: the NVIDIA image (as given) with a GTX 16 / RTX 20 or newer,
    otherwise the same name with -amd ("ghcr.io/x/monet:latest" → "ghcr.io/x/monet-amd:latest")."""
    if facts.get("newNvidia", True):
        return image
    name, _, tag = image.rpartition(":")
    if not name or "/" in tag:  # no tag: the colon was a registry's port
        name, tag = image, ""
    if name.endswith("-amd"):
        return image
    return f"{name}-amd" + (f":{tag}" if tag else "")
