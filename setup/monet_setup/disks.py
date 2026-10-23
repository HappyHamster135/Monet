"""Which disk Monet goes on, and how it's split.

"Monet and Windows" (erase): the disk is wiped and gets
    EFI (1 GiB) | boot (2 GiB) | Monet (btrfs) | free space for Windows
with Windows' share left free: after the first sign-in, Monet downloads
Windows and monet-prepare-windows puts it there (it needs 64 GiB plus 8 GiB
for its setup files). The same sizes as the old kickstart.

"Monet next to my Windows" (keep): nothing existing is touched. Monet uses the
largest free area of the disk and Windows' own EFI partition:
    ... Windows ... | boot (2 GiB) | Monet (btrfs)
"""

import json
import subprocess

from .words import _, tr

MIB = 1024 * 1024
GIB = 1024 * MIB
EFI_MIB = 1024
BOOT_MIB = 2048
MIN_MONET_MIB = 64 * 1024
WINDOWS_SETUP_MIB = 8 * 1024
EFI_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"


def run(*args, timeout=60):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout if done.returncode == 0 else ""


def flag(value):
    return value in (True, 1, "1", "true")


def lsblk():
    out = run("lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,RO,TRAN,MODEL,VENDOR,PARTTYPE,FSTYPE,LABEL,"
              "PARTLABEL,MOUNTPOINTS")
    try:
        return json.loads(out or "{}").get("blockdevices", [])
    except ValueError:
        return []


def live_media(devices):
    """Disks that hold the running USB stick: anything mounted under
    /run/initramfs/live, or carrying the stick's labels ("Monet-0.7.0" and
    its EFI partition's MONETEFI). Not Monet's own partitions on a PC that
    already has Monet (monet, MONETWIN, MONETSETUP): that disk can be used."""
    found = set()
    for disk in devices:
        for part in [disk] + disk.get("children", []):
            points = [p for p in (part.get("mountpoints") or []) if p]
            label = part.get("label") or ""
            if any(p.startswith("/run/initramfs/live") for p in points) or label.startswith("Monet-") \
                    or label == "MONETEFI":
                found.add(disk["name"])
    return found


def describe(disk):
    """"Samsung SSD 990 PRO · 1 TB": what people see on the box."""
    model = " ".join((disk.get("model") or disk.get("vendor") or _("Disk")).split())
    return f"{model} · {size_text(int(disk['size']))}"


def size_text(size):
    tb = size / 1e12
    if tb >= 1:
        return f"{tb:.1f} TB".replace(".0 ", " ")
    return f"{round(size / 1e9)} GB"


def disks(devices=None):
    """Disks Monet could go on, biggest first. Never the USB stick it's running
    from; USB and removable disks only when there's nothing else."""
    devices = lsblk() if devices is None else devices
    media = live_media(devices)
    usable = [d for d in devices if d.get("type") == "disk" and d["name"] not in media and not flag(d.get("ro"))
              and not d["name"].startswith(("zram", "loop", "sr", "nbd", "ram")) and int(d.get("size") or 0) > 0]
    internal = [d for d in usable if not flag(d.get("rm")) and d.get("tran") != "usb"]
    chosen = internal or usable
    return sorted(chosen, key=lambda d: -int(d["size"]))


def windows_mib(size_mib):
    """Windows' share of an erased disk: about a third, 100-500 GiB."""
    return min(max(size_mib * 35 // 100, 100 * 1024), 500 * 1024)


def plan_erase(size):
    """{efi, boot, monet, windows} in MiB for a disk of `size` bytes."""
    size_mib = size // MIB
    win = windows_mib(size_mib)
    monet = size_mib - win - WINDOWS_SETUP_MIB - 4 * 1024
    if monet < MIN_MONET_MIB:
        # Too small to share: Monet takes the whole disk.
        monet, win = size_mib - EFI_MIB - BOOT_MIB - 16, 0
    if monet < MIN_MONET_MIB:
        return None
    return {"efi": EFI_MIB, "boot": BOOT_MIB, "monet": monet, "windows": win}


def largest_free(path):
    """(start sector, sectors, sector size) of the disk's largest free area."""
    sector = int(run("blockdev", "--getss", path).strip() or 512)
    best = (0, 0)
    for line in run("sfdisk", "-F", "-q", path).splitlines():
        f = line.split()
        if len(f) >= 3 and f[0].isdigit() and f[1].isdigit():
            start, end = int(f[0]), int(f[1])
            if end - start + 1 > best[1]:
                best = (start, end - start + 1)
    return best[0], best[1], sector


def efi_partition(disk):
    return next((p for p in disk.get("children", []) if (p.get("parttype") or "").lower() == EFI_TYPE), None)


def plan_keep(disk, free_bytes):
    """Monet next to what's there: the free space, Windows' EFI partition."""
    if not efi_partition(disk):
        return None, _("This disk has no EFI partition, so Windows doesn't start from it.")
    monet = free_bytes // MIB - BOOT_MIB - 16
    if monet < MIN_MONET_MIB:
        need = (MIN_MONET_MIB + BOOT_MIB) * MIB
        return None, tr("Needs %1 of free space; this disk has %2. Shrink Windows' drive in Disk Management first.",
                        size_text(need), size_text(free_bytes))
    return {"boot": BOOT_MIB, "monet": monet}, ""


def offer(devices=None, free=None):
    """What the Ready page shows: each disk, and whether "next to my Windows"
    fits on it (and why not)."""
    free = free or (lambda path: largest_free(path))
    out = []
    for disk in disks(devices):
        start, sectors, sector = free(disk["path"])
        keep, why = plan_keep(disk, sectors * sector)
        has_windows = any((p.get("fstype") or "") == "ntfs" for p in disk.get("children", []))
        out.append({"path": disk["path"], "label": describe(disk), "size": int(disk["size"]),
                    "erase": plan_erase(int(disk["size"])), "keep": keep, "keepWhy": why,
                    "hasWindows": has_windows})
    return out
