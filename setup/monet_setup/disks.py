"""Which disk Monet goes on, and how it's split.

"Monet and Windows" (erase): the disk is wiped and gets
    EFI (1 GiB) | boot (2 GiB) | Monet (btrfs) | free space for Windows
with Windows' share left free: after the first sign-in, Monet downloads
Windows and monet-prepare-windows puts it there (it needs 64 GiB plus 8 GiB
for its setup files). The same sizes as the old kickstart.

"Monet next to my Windows" (keep): Windows and its files stay. Monet uses the
largest free area of the disk and Windows' own EFI partition:
    ... Windows ... | boot (2 GiB) | Monet (btrfs)
Without enough free space, Monet makes room by shrinking Windows' drive (C:)
with ntfsresize: Windows keeps what it uses and half its free space, at least
30 GiB. Its files can come along too (your_files): copied while installing.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from .words import _, tr

MIB = 1024 * 1024
GIB = 1024 * MIB
EFI_MIB = 1024
BOOT_MIB = 2048
MIN_MONET_MIB = 64 * 1024
WINDOWS_SETUP_MIB = 8 * 1024
WINDOWS_ROOM_MIB = 30 * 1024
# Monet's own system and apps, besides the files brought from Windows.
MONET_OWN_MIB = 40 * 1024
EFI_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
# The folders brought from Windows: named the same on every Windows, whatever its language.
FOLDERS = ("Desktop", "Documents", "Pictures", "Music", "Videos", "Downloads")
NOT_PEOPLE = {"public", "default", "default user", "all users", "defaultuser0", "defaultuser100000",
              "wdagutilityaccount"}
WINDOWS_MOUNT = "/run/monet-setup/windows"


def run(*args, timeout=60):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout if done.returncode == 0 else ""


def said(*args, timeout=120):
    """Everything a tool printed, whether it worked or not ("" if it couldn't run)."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "") + (done.stderr or "")


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


def windows_partition(disk):
    """Windows' drive (C:): the biggest NTFS partition, or a BitLocker one."""
    found = [p for p in disk.get("children", []) if (p.get("fstype") or "").lower() in ("ntfs", "bitlocker")]
    return max(found, key=lambda p: int(p.get("size") or 0), default=None)


def smallest_size(report):
    """(the smallest Windows' drive can become in bytes, "") from `ntfsresize --info`, or (None, why not)."""
    lowered = report.lower()
    if "hibernat" in lowered or "fast restart" in lowered:
        return None, _("Windows is asleep, not shut down, so Monet can't make room on its drive. In Windows, hold Shift while you choose Shut down, then start Monet Setup again.")  # noqa: E501
    if "chkdsk" in lowered or "unclean" in lowered or "inconsistent" in lowered:
        return None, _("Windows' drive needs a check first. Start Windows, restart it once, then shut it down and start Monet Setup again.")  # noqa: E501
    found = re.search(r"resize at (\d+) bytes", report)
    return (int(found.group(1)), "") if found else (None, "")


def shrink_info(path):
    return smallest_size(said("ntfsresize", "--info", "--force", "--no-progress-bar", path))


def plan_keep(disk, free_bytes, shrink=None):
    """Monet next to what's there: the free space, or room made by shrinking Windows'
    drive; Windows' EFI partition. shrink(path) says how small the drive can get."""
    if not efi_partition(disk):
        return None, _("This disk has no EFI partition, so Windows doesn't start from it.")
    monet = free_bytes // MIB - BOOT_MIB - 16
    if monet >= MIN_MONET_MIB:
        return {"boot": BOOT_MIB, "monet": monet}, ""
    need = (MIN_MONET_MIB + BOOT_MIB + 16) * MIB
    no_room = tr("Needs %1 of free space; this disk has %2. Shrink Windows' drive in Disk Management first.",
                 size_text(need), size_text(free_bytes))
    windows = windows_partition(disk)
    if windows is None or shrink is None:
        return None, no_room
    if (windows.get("fstype") or "").lower() == "bitlocker":
        return None, _("Windows' drive is encrypted with BitLocker, so Monet can't make room on it. Turn BitLocker off in Windows first, or choose Monet and Windows.")  # noqa: E501
    smallest, why = shrink(windows["path"])
    if smallest is None:
        return None, why or no_room
    size, room = int(windows.get("size") or 0), WINDOWS_ROOM_MIB * MIB
    # Windows keeps what it uses and half its free space (at least 30 GiB) to grow into,
    # unless Monet needs more of it.
    keeps = min(smallest + max(room, (size - smallest) // 2), size - need)
    keeps = keeps // MIB * MIB
    if keeps < smallest + room:
        return None, tr("Windows' drive is too full to make room for Monet. Free up %1 in Windows, then try again.",
                        size_text(smallest + room + need - size))
    return {"boot": BOOT_MIB, "monet": (size - keeps) // MIB - BOOT_MIB - 16,
            "shrink": {"partition": windows["path"], "from": size, "to": keeps}}, ""


def mount_windows(path):
    """Windows' drive, read-only, at WINDOWS_MOUNT: True if it's there."""
    try:
        os.makedirs(WINDOWS_MOUNT, exist_ok=True)
        if os.path.ismount(WINDOWS_MOUNT):
            return True
        # ntfs-3g reads a drive Windows left asleep too.
        for kind in ("ntfs-3g", "ntfs3"):
            if subprocess.run(["mount", "-t", kind, "-o", "ro", path, WINDOWS_MOUNT],
                              capture_output=True, timeout=60).returncode == 0:
                return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def unmount_windows():
    try:
        subprocess.run(["umount", WINDOWS_MOUNT], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        pass


def size_of(folder):
    """Bytes in a folder, without following links (Documents' "My Music" and the like)."""
    total = 0
    for top, _dirs, files in os.walk(folder):
        for name in files:
            try:
                st = os.lstat(os.path.join(top, name))
            except OSError:
                continue
            if not os.path.islink(os.path.join(top, name)):
                total += st.st_size
    return total


def your_files(root):
    """The files to bring from the Windows mounted at root: the account used last,
    {"person", "folders": {Documents: "Users/Ann/Documents", ...}, "sizes", "total"},
    or None. Folders OneDrive keeps (its Documents, Desktop, Pictures) count too."""
    users = Path(root) / "Users"
    people = []
    try:
        for home in users.iterdir():
            if home.is_dir() and not home.is_symlink() and home.name.lower() not in NOT_PEOPLE:
                try:
                    used = (home / "NTUSER.DAT").stat().st_mtime
                except OSError:
                    used = 0
                people.append((used, home))
    except OSError:
        return None
    if not people:
        return None
    # shortcut: only the account used last comes along; bring the others from Files later.
    home = max(people)[1]
    folders, sizes = {}, {}
    for name in FOLDERS:
        for place in (home / name, home / "OneDrive" / name):
            size = size_of(place) if place.is_dir() and not place.is_symlink() else 0
            if size:
                folders[name], sizes[name] = str(place.relative_to(root)).replace(os.sep, "/"), size
                break
    if not folders:
        return None
    return {"person": home.name, "folders": folders, "sizes": sizes, "total": sum(sizes.values())}


def windows_files(disk):
    """your_files() of the disk's Windows, mounted for a moment."""
    windows = windows_partition(disk)
    if windows is None or (windows.get("fstype") or "").lower() != "ntfs" or not mount_windows(windows["path"]):
        return None
    try:
        found = your_files(WINDOWS_MOUNT)
    finally:
        unmount_windows()
    if found:
        found["partition"] = windows["path"]
    return found


def offer(devices=None, free=None, shrink=None, files=None):
    """What the Ready page shows: each disk, whether "next to my Windows" fits on it
    (and why not), and the files Windows has to bring along."""
    free = free or (lambda path: largest_free(path))
    shrink = shrink or shrink_info
    files = files or windows_files
    out = []
    for disk in disks(devices):
        start, sectors, sector = free(disk["path"])
        keep, why = plan_keep(disk, sectors * sector, shrink)
        has_windows = windows_partition(disk) is not None
        found = files(disk) if has_windows else None
        # They're copied: room for them, and Monet's own besides.
        if found and keep:
            found["fits"] = found["total"] // MIB <= keep["monet"] - MONET_OWN_MIB
        out.append({"path": disk["path"], "label": describe(disk), "size": int(disk["size"]),
                    "erase": plan_erase(int(disk["size"])), "keep": keep, "keepWhy": why,
                    "hasWindows": has_windows, "files": found})
    return out
