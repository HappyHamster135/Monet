"""Can this PC run Monet, and which Monet? What Setup looks at before anything is
erased: the graphics, which choose the image (NVIDIA's open driver, for GTX 16 and
RTX 20 and newer, or AMD's and Intel's, Mesa, which also drives older NVIDIA cards
with the open nouveau driver), and the memory. UEFI needs no check: the stick only
starts that way.
"""

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
