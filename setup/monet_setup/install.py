"""Installs Monet on the disk:  python3 -m monet_setup.install PLAN.json

PLAN.json comes from the window (app.py): the disk, "erase" or "keep", the
sizes from disks.py, the person, language, keyboard, time zone and Wi-Fi.
Progress goes to stdout, one JSON object per line:

    {"phase": "download", "fraction": 0.4, "got": ..., "total": ..., "eta": ...}
    {"log": "..."}                      for the Details box
    {"error": "...", "phase": ...}      what went wrong, in plain words
    {"done": true}

1. disk       erase: a new partition table, EFI | boot | Monet (btrfs).
              keep: boot | Monet in the largest free area, Windows' EFI.
              Monet's btrfs gets two subvolumes: root (the system) and
              download (the image, removed at the end).
2. download   skopeo copies Monet into download/ as an OCI layout. Pieces
              already there are kept, so "Try again" and restarts after a
              stall pick up where they stopped.
3. install    bootc install to-filesystem from that copy; updates come from
              the registry afterwards (--target-imgref).
4. configure  the person (an administrator), language, keyboard, time zone,
              Wi-Fi (also kept for Windows), Windows' "waiting" state, and
              Universal Blue's driver key for Secure Boot.
5. finish     unmount, delete the download, done.

A retry in the same session skips the disk step when it already finished
(STATE remembers), so a dropped download doesn't cost the downloaded part.
"""

import glob
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from . import disks, system, words
from .words import _

TOP = "/mnt/monet-top"          # Monet's btrfs, all subvolumes
TARGET = "/mnt/monet"           # the root subvolume, where bootc installs
DOWNLOAD = f"{TOP}/download"
STATE = Path(os.environ.get("MONET_INSTALL_STATE", "/run/monet-setup/install.json"))
STALL = 240                     # seconds with no bytes before a download restarts
MOK_PASSWORD = "monetsetup"
SHIM = "\\EFI\\fedora\\shimx64.efi"
LOG = Path("/run/monet-setup/install.log")


class Stop(Exception):
    """A step failed; the message is what the person reads."""


def emit(**event):
    print(json.dumps(event), flush=True)


def log(text):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(text + "\n")
    except OSError:
        pass
    emit(log=text)


def run(*args, check=True, input=None, timeout=1800, quiet=False):
    """Runs a command; its output goes to the log. Returns stdout."""
    if not quiet:
        log("$ " + " ".join(shlex.quote(str(a)) for a in args))
    try:
        done = subprocess.run([str(a) for a in args], input=input, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Stop(f"{args[0]} took too long.") from None
    except OSError as e:
        raise Stop(f"{args[0]} isn't available ({e.strerror}).") from None
    out = (done.stdout or "") + (done.stderr or "")
    for line in out.strip().splitlines()[-30:]:
        if line.strip():
            log("  " + line)
    if check and done.returncode != 0:
        raise Stop(f"{args[0]} failed (exit {done.returncode}).")
    return done.stdout or ""


# -- 1. the disk --------------------------------------------------------------

def partition_path(disk, number):
    """/dev/nvme0n1 + 3 -> /dev/nvme0n1p3; /dev/sda + 3 -> /dev/sda3."""
    return f"{disk}p{number}" if disk[-1].isdigit() else f"{disk}{number}"


def settle(disk):
    run("partx", "-u", disk, check=False, quiet=True)
    run("udevadm", "settle", "--timeout=30", check=False, quiet=True)
    time.sleep(1)


def prepare_erase(plan):
    disk, sizes = plan["disk"], plan["sizes"]
    run("wipefs", "-a", "-f", disk, check=False)
    run("sgdisk", "--zap-all", disk)
    run("sgdisk",
        "-n", f"1:0:+{sizes['efi']}M", "-t", "1:EF00", "-c", "1:EFI System",
        "-n", f"2:0:+{sizes['boot']}M", "-t", "2:8300", "-c", "2:boot",
        "-n", f"3:0:+{sizes['monet']}M", "-t", "3:8300", "-c", "3:monet",
        disk)
    settle(disk)
    efi, boot, monet = (partition_path(disk, n) for n in (1, 2, 3))
    run("mkfs.fat", "-F", "32", "-n", "EFI", efi)
    return {"efi": efi, "boot": boot, "monet": monet}


def prepare_keep(plan):
    disk, sizes = plan["disk"], plan["sizes"]
    start, sectors, sector = disks.largest_free(disk)
    mib = 1024 * 1024 // sector
    first = -(-start // mib) * mib
    boot_end = first + sizes["boot"] * mib - 1
    monet_end = boot_end + sizes["monet"] * mib
    if monet_end >= start + sectors:
        raise Stop(_("The free space on the disk changed. Go back and choose again."))
    before = set(numbers(disk))
    run("sgdisk",
        "-n", f"0:{first}:{boot_end}", "-t", "0:8300", "-c", "0:boot",
        "-n", f"0:{boot_end + 1}:{monet_end}", "-t", "0:8300", "-c", "0:monet",
        disk)
    settle(disk)
    new = sorted(set(numbers(disk)) - before)
    if len(new) != 2:
        raise Stop(_("The new partitions didn't show up."))
    found = next((p for p in disks.lsblk() if p["path"] == disk), {})
    efi = disks.efi_partition(found)
    if not efi:
        raise Stop(_("Windows' EFI partition wasn't found."))
    return {"efi": efi["path"], "boot": partition_path(disk, new[0]), "monet": partition_path(disk, new[1])}


def numbers(disk):
    """Partition numbers on the disk."""
    out = run("sgdisk", "-p", disk, quiet=True)
    return [int(line.split()[0]) for line in out.splitlines() if line.strip()[:1].isdigit()]


def prepare_disk(plan):
    emit(phase="disk", fraction=0.1)
    parts = prepare_erase(plan) if plan["mode"] == "erase" else prepare_keep(plan)
    emit(phase="disk", fraction=0.5)
    run("mkfs.ext4", "-F", "-q", "-L", "boot", parts["boot"])
    run("mkfs.btrfs", "-f", "-q", "-L", "monet", parts["monet"])
    os.makedirs(TOP, exist_ok=True)
    run("mount", parts["monet"], TOP)
    run("btrfs", "subvolume", "create", f"{TOP}/root")
    run("btrfs", "subvolume", "create", DOWNLOAD)
    emit(phase="disk", fraction=1.0)
    return parts


# -- 2. the download ------------------------------------------------------------

def received():
    """Bytes received on every network connection so far."""
    total = 0
    try:
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            name, data = line.split(":", 1)
            if name.strip() != "lo":
                total += int(data.split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return total


def image_size(image):
    """The compressed size of Monet's layers, from its manifest; 0 if unknown."""
    try:
        raw = json.loads(run("skopeo", "inspect", "--raw", f"docker://{image}", quiet=True, timeout=120))
        if "manifests" in raw:
            digest = next(m["digest"] for m in raw["manifests"]
                          if m.get("platform", {}).get("architecture") == "amd64")
            repo = image.rsplit(":", 1)[0] if ":" in image.split("/")[-1] else image
            raw = json.loads(run("skopeo", "inspect", "--raw", f"docker://{repo}@{digest}", quiet=True, timeout=120))
        return sum(layer["size"] for layer in raw["layers"])
    except (Stop, ValueError, KeyError, StopIteration):
        return 0


def copy_once(image, total, start, popen=subprocess.Popen, clock=time):
    """One skopeo copy. True when it finished; False when it failed or stopped
    moving for STALL seconds (then it's stopped, to be started again)."""
    log(f"$ skopeo copy docker://{image} oci:{DOWNLOAD}/oci:latest")
    with open(LOG, "a") if LOG.parent.exists() else open(os.devnull, "w") as out:
        proc = popen(["skopeo", "copy", "--retry-times", "3", f"docker://{image}", f"oci:{DOWNLOAD}/oci:latest"],
                     stdout=out, stderr=subprocess.STDOUT)
        seen, moved, rates = received(), clock.time(), []
        while proc.poll() is None:
            clock.sleep(2)
            now = received()
            if now - seen > 256 * 1024:
                seen, moved = now, clock.time()
            elif clock.time() - moved > STALL:
                log(f"no data for {STALL // 60} minutes; starting the download again")
                proc.kill()
                proc.wait()
                return False
            got = max(0, now - start)
            rates = (rates + [(clock.time(), got)])[-30:]
            speed = (rates[-1][1] - rates[0][1]) / max(1, rates[-1][0] - rates[0][0])
            eta = (total - got) / speed if total and speed > 0 and got < total else None
            emit(phase="download", fraction=min(got / total, 0.99) if total else 0.0,
                 got=min(got, total) if total else got, total=total, eta=eta)
    return proc.returncode == 0


def download(plan, tries=8):
    image = plan["image"]
    run("nm-online", "-s", "-q", "-t", "60", check=False, timeout=90)
    total = image_size(image)
    log(f"Monet's download: {total / 1e9:.1f} GB" if total else "Monet's download size isn't known")
    start = received()
    for attempt in range(tries):
        if copy_once(image, total, start):
            emit(phase="download", fraction=1.0, got=total, total=total)
            return
        emit(phase="download", note="the connection dropped, picking up where it stopped")
        time.sleep(min(10 * (attempt + 1), 60))
    raise Stop(_("The connection dropped and didn't come back. Check the Wi-Fi, then try again."))


# -- 3. installing ----------------------------------------------------------------

def mount_target(parts):
    os.makedirs(TARGET, exist_ok=True)
    run("mount", "-o", "subvol=root,compress=zstd:1", parts["monet"], TARGET)
    os.makedirs(f"{TARGET}/boot", exist_ok=True)
    run("mount", parts["boot"], f"{TARGET}/boot")
    os.makedirs(f"{TARGET}/boot/efi", exist_ok=True)
    run("mount", parts["efi"], f"{TARGET}/boot/efi")


def install(plan, parts):
    emit(phase="install", fraction=0.05)
    # bootc wants an empty root: a try that stopped halfway left things there.
    unmount_target()
    root = Path(f"{TOP}/root")
    if root.exists() and any(root.iterdir()):
        run("btrfs", "subvolume", "delete", root)
    if not root.exists():
        run("btrfs", "subvolume", "create", root)
    mount_target(parts)
    emit(phase="install", fraction=0.15)
    run("bootc", "install", "to-filesystem",
        "--source-imgref", f"oci:{DOWNLOAD}/oci:latest",
        "--target-imgref", plan["image"],
        "--skip-fetch-check",
        "--karg", "rootflags=subvol=root",
        TARGET, timeout=3600)
    emit(phase="install", fraction=0.9)
    boot_entry(plan, parts)
    emit(phase="install", fraction=1.0)


def boot_entry(plan, parts):
    """The PC's firmware lists Monet as "Monet", first in line. bootupd may
    have added one for this disk called "Fedora": that one makes way."""
    uuid = run("blkid", "-s", "PARTUUID", "-o", "value", parts["efi"], check=False, quiet=True).strip().lower()
    for number, name, path in entries(run("efibootmgr", "-v", check=False, quiet=True)):
        if uuid and uuid in path.lower() and SHIM.lower() in path.lower():
            if name == "Monet":
                return
            run("efibootmgr", "-b", number, "-B", check=False)
    partition = parts["efi"][len(plan["disk"]):].lstrip("p")
    run("efibootmgr", "--create", "--disk", plan["disk"], "--part", partition, "--label", "Monet",
        "--loader", SHIM, check=False)


def entries(listing):
    """(number, name, device path) for each line of `efibootmgr -v`."""
    for line in listing.splitlines():
        match = re.match(r"Boot([0-9A-Fa-f]{4})\*?\s+([^\t]*)\t?(.*)", line)
        if match:
            yield match.group(1), match.group(2).strip(), match.group(3)


# -- 4. setting it up ------------------------------------------------------------

def deployment():
    found = [d for d in glob.glob(f"{TARGET}/ostree/deploy/*/deploy/*.0") if os.path.isdir(d)]
    if not found:
        raise Stop(_("Monet's system wasn't found after installing."))
    root = Path(sorted(found)[-1])
    return root, root.parent.parent / "var"


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chmod(path, mode)


def configure(plan):
    emit(phase="configure", fraction=0.1)
    # bootc may leave the new system mounted read-only when it's done.
    for path in (TARGET, f"{TARGET}/boot"):
        run("mount", "-o", "remount,rw", path, check=False, quiet=True)
    root, var = deployment()
    mounts = []
    try:
        for source, target, opts in ((str(var), root / "var", ["--bind"]), ("/proc", root / "proc", ["-t", "proc"]),
                                     ("/sys", root / "sys", ["--rbind"]), ("/dev", root / "dev", ["--rbind"])):
            target.mkdir(parents=True, exist_ok=True)
            run("mount", *opts, source, target)
            mounts.append(target)
        account, name = plan["account"], plan["name"]
        run("chroot", root, "useradd", "-m", "-U", "-G", "wheel", "-c", name, account)
        run("chroot", root, "chpasswd", input=f"{account}:{plan['password']}\n", quiet=True)
        log(f"made {account} ({name}), an administrator")
        emit(phase="configure", fraction=0.4)

        etc = root / "etc"
        write(etc / "locale.conf", f"LANG={plan['language']}\n")
        write(etc / "vconsole.conf", f"KEYMAP={plan['keyboard']}{'-' + plan['variant'] if plan['variant'] else ''}\n")
        layouts, variants, options = system.xkb(plan["keyboard"], plan["variant"])
        write(etc / "X11/xorg.conf.d/00-keyboard.conf",
              'Section "InputClass"\n    Identifier "system-keyboard"\n    MatchIsKeyboard "on"\n'
              f'    Option "XkbLayout" "{layouts}"\n'
              + (f'    Option "XkbVariant" "{variants}"\n' if variants else "")
              + (f'    Option "XkbOptions" "{options}"\n' if options else "")
              + "EndSection\n")
        zone = system.guess_time_zone(plan["timezone"])
        if (root / "usr/share/zoneinfo" / zone).exists():
            (etc / "localtime").unlink(missing_ok=True)
            (etc / "localtime").symlink_to(f"../usr/share/zoneinfo/{zone}")
        write(etc / "hostname", "monet\n")
        emit(phase="configure", fraction=0.6)

        # The Wi-Fi used here: for Monet, and for Windows (monet-prepare-windows
        # turns var/lib/monet/wifi into Windows profiles).
        for conn in glob.glob("/etc/NetworkManager/system-connections/*.nmconnection"):
            data = Path(conn).read_text(errors="replace")
            if plan.get("wifi") and f"ssid={plan['wifi']}" not in data:
                continue
            for folder in (etc / "NetworkManager/system-connections", var / "lib/monet/wifi"):
                write(folder / Path(conn).name, data, 0o600)
        if plan["mode"] == "erase":
            write(var / "lib/monet/windows-setup", "waiting\n")
        # The apps picked on "Your apps": monet-apps installs them once Monet is
        # online (an empty list is a choice too: none).
        write(var / "lib/monet/apps", "".join(f"{app}\n" for app in plan.get("apps", [])))

        # NVIDIA's driver is signed with Universal Blue's key: ask the firmware
        # to trust it (confirmed once, on a blue screen, with "monetsetup").
        key = etc / "pki/akmods/certs/akmods-ublue.der"
        if key.exists():
            run("mokutil", "--timeout", "-1", check=False)
            run("mokutil", "--import", key, input=f"{MOK_PASSWORD}\n{MOK_PASSWORD}\n", check=False)
        emit(phase="configure", fraction=0.8)

        # Labels for what was written here, from Monet's own SELinux policy.
        contexts = "/etc/selinux/targeted/contexts/files/file_contexts"
        if (root / contexts.lstrip("/")).exists():
            run("chroot", root, "setfiles", "-F", "-T", "0", contexts, "/etc", f"/var/home/{account}", "/var/lib/monet",
                check=False)
        emit(phase="configure", fraction=1.0)
    finally:
        for target in reversed(mounts):
            run("umount", "-R", target, check=False, quiet=True)


# -- 5. tidying up -----------------------------------------------------------------

def unmount_target():
    for path in (f"{TARGET}/boot/efi", f"{TARGET}/boot", TARGET):
        if os.path.ismount(path):
            run("umount", "-R", path, check=False, quiet=True)


def finish():
    emit(phase="finish", fraction=0.2)
    unmount_target()
    run("btrfs", "subvolume", "delete", DOWNLOAD, check=False)
    run("umount", TOP, check=False, quiet=True)
    run("sync", check=False, quiet=True)
    emit(phase="finish", fraction=1.0)


def remembered(plan):
    """The partitions from an earlier try in this session, if it was this disk."""
    try:
        saved = json.loads(STATE.read_text())
    except (OSError, ValueError):
        return None
    if saved.get("disk") != plan["disk"] or saved.get("mode") != plan["mode"]:
        return None
    return saved.get("parts")


def remember(plan, parts):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"disk": plan["disk"], "mode": plan["mode"], "parts": parts}))
    except OSError:
        pass


def main(path):
    plan = json.loads(Path(path).read_text())
    words.use(plan.get("language", ""))
    phase = "disk"
    try:
        parts = remembered(plan)
        if parts and os.path.exists(parts["monet"]):
            log("using the disk prepared by the last try")
            if not os.path.ismount(TOP):
                os.makedirs(TOP, exist_ok=True)
                run("mount", parts["monet"], TOP)
        else:
            parts = prepare_disk(plan)
            remember(plan, parts)
        phase = "download"
        download(plan)
        phase = "install"
        install(plan, parts)
        phase = "configure"
        configure(plan)
        phase = "finish"
        finish()
        STATE.unlink(missing_ok=True)
        emit(done=True)
    except Stop as e:
        emit(phase=phase, error=str(e))
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 - shown to the person, details in the log
        log(f"{type(e).__name__}: {e}")
        emit(phase=phase, error=_("Something unexpected went wrong. The details say what."))
        sys.exit(1)
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
