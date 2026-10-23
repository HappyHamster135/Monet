"""Can this PC run Monet? What Setup looks at before anything is erased: the
graphics (Monet's NVIDIA driver needs an RTX 20-series or newer, and nouveau
stays off) and the memory. UEFI needs no check: the stick only starts that way.
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


def check(cards=None, gb=None):
    """{"oldNvidia": "only" (nothing else to draw with), "beside" (built-in graphics too) or "",
    "memory": GB or None}."""
    cards = graphics() if cards is None else cards
    gb = memory() if gb is None else gb
    old = [c for c in cards if c[0] == NVIDIA and int(c[1], 16) < TURING]
    rest = [c for c in cards if c not in old]
    return {"oldNvidia": "only" if old and not rest else "beside" if old else "", "memory": gb}
