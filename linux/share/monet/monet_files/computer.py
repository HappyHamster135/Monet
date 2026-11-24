"""Files' This PC view. Dolphin follows these non-executable links in the current tab."""
import fcntl
import gettext
import os
from pathlib import Path
import stat
import tempfile

from gi.repository import Gio, GioUnix, GLib

WORDS = gettext.translation("monet", localedir=str(Path(__file__).resolve().parents[2] / "locale"), fallback=True)
tr = WORDS.gettext
FOLDERS = (("DESKTOP", "user-desktop"), ("DOCUMENTS", "folder-documents"),
           ("DOWNLOAD", "folder-download"), ("MUSIC", "folder-music"),
           ("PICTURES", "folder-pictures"), ("VIDEOS", "folder-videos"))
OWNED = b"[Desktop Entry]\nType=Link\nX-Monet-ThisPC=1\n"


def location():
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "monet" / "This PC"


def devices():
    # GLib applies the desktop's display rules (including x-gvfs-hide/show).
    # Also include local data disks conventionally mounted by an administrator in /mnt.
    mounts, _ = GioUnix.mount_entries_get()
    result = []
    for mount in mounts:
        path = Path(mount.get_mount_path())
        if path == Path("/") or "x-gvfs-hide" in (mount.get_options() or "").split(","):
            continue
        under_mnt = Path("/mnt") in path.parents and mount.get_device_path().startswith("/dev/")
        if not under_mnt and not mount.guess_should_display():
            continue
        icon = mount.guess_icon()
        names = icon.get_names() if isinstance(icon, Gio.ThemedIcon) else ()
        result.append((mount.guess_name() or path.name, path, next(iter(names), "drive-harddisk")))
    return sorted(result, key=lambda item: str(item[1]))


def entries():
    seen = {Path.home()}
    for kind, icon in FOLDERS:
        folder = GLib.get_user_special_dir(getattr(GLib.UserDirectory, "DIRECTORY_" + kind))
        if folder:
            path = Path(folder)
            if path.is_absolute() and path not in seen and path.is_dir():
                seen.add(path)
                yield path.name, path, icon

    yield tr("System drive"), Path("/"), "drive-harddisk-system"
    yield from devices()


def existing(path):
    """Inspect only our small generated regular files. Never follow a user's link."""
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return b""
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        return b""
    try:
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode) and info.st_size <= 32768:
            content = os.read(fd, 32768)
            if content.startswith(OWNED):
                return content
    finally:
        os.close(fd)
    return b""


def refresh(folder=None, items=None):
    folder = folder or location()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink():
        raise OSError("This PC is a symbolic link")
    with (folder.parent / ".this-pc.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        wanted = set()
        for name, target, icon in entries() if items is None else items:
            # The filename is also the label in Dolphin's local file view.
            label = "".join(" " if ord(c) < 32 or c in "/\\" else c for c in name).strip(" .")
            label = label.encode("utf-8", "replace")[:200].decode("utf-8", "ignore") or tr("Drive")
            dest = folder / label
            suffix = 1
            while dest in wanted or existing(dest) == b"":
                suffix += 1
                dest = folder / f"{label} ({suffix})"
            wanted.add(dest)
            data = OWNED + f"Name={dest.name}\nIcon={icon}\nURL={target.as_uri()}\n".encode()
            old = existing(dest)
            if old == data:
                continue
            with tempfile.NamedTemporaryFile(dir=folder, prefix=".link-", delete=False) as stream:
                stream.write(data)
                temp = Path(stream.name)
            try:
                if old is None:
                    try:
                        os.link(temp, dest)
                    except FileExistsError:
                        pass  # An item placed by the user takes precedence.
                elif old and existing(dest) == old:
                    temp.replace(dest)
            finally:
                temp.unlink(missing_ok=True)
        for path in folder.iterdir():
            if path not in wanted and not path.name.startswith(".") and existing(path):
                path.unlink()
    return folder


def watch():
    # No periodic scan. GLib's Unix mount monitor observes the kernel mount table.
    loop = GLib.MainLoop()
    timer = 0

    def update():
        nonlocal timer
        timer = 0
        GLib.reload_user_special_dirs_cache()
        refresh()
        return GLib.SOURCE_REMOVE

    def changed(*_):
        nonlocal timer
        if not timer:
            timer = GLib.timeout_add(250, update)

    mounts = GioUnix.MountMonitor.get()
    mounts.connect("mounts-changed", changed)
    mounts.connect("mountpoints-changed", changed)
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    settings = Gio.File.new_for_path(str(config / "user-dirs.dirs")).monitor_file(Gio.FileMonitorFlags.NONE, None)
    settings.connect("changed", changed)
    update()
    loop.run()
