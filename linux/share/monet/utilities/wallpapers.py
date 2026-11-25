"""The desktop's installed wallpapers and the user's linked picture collection."""
import json
import os
import re
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLocale, QSize, Qt
from PySide6.QtGui import QImageReader

from actions import stored, tr


@dataclass(frozen=True)
class Wallpaper:
    name: str
    target: Path
    preview: Path
    personal: bool = False


class Collection:
    def __init__(self, settings):
        self.settings = settings
        data = stored(settings, "wallpaper/collection", {})
        for key in ("files", "folders", "hidden"):
            paths = data.get(key, [])
            setattr(self, key, {Path(p) for p in paths if isinstance(p, str) and Path(p).is_absolute()}
                    if isinstance(paths, list) else set())

    def save(self):
        data = {k: sorted(map(str, getattr(self, k))) for k in ("files", "folders", "hidden")}
        self.settings.setValue("wallpaper/collection", json.dumps(data))
        self.settings.sync()

    def add(self, paths, folder=False):
        paths = {Path(p).absolute() for p in paths}
        (self.folders if folder else self.files).update(paths)
        if not folder:
            self.hidden.difference_update(paths)
        self.save()

    def forget(self, path, folder=False):
        (self.folders if folder else self.files).discard(path)
        if not folder and any(path.is_relative_to(root) for root in self.folders):
            self.hidden.add(path)
        self.hidden = {p for p in self.hidden if any(p.is_relative_to(root) for root in self.folders)}
        self.save()


def formats():
    stills = set("jpeg jpg png webp avif jxl heif heic gif bmp tif tiff".split())
    return stills.intersection(bytes(f).decode() for f in QImageReader.supportedImageFormats())


def resolution_score(path):
    # Prefer a small landscape variant for the thumbnail. Plasma chooses the
    # full-resolution file for each monitor from the package at apply time.
    match = re.fullmatch(r"(\d+)x(\d+)", path.stem)
    if match:
        width, height = map(int, match.groups())
        return (width < height, abs(width / max(1, height) - 16/9), width)
    return (True, 10, 0)


def catalog(roots, files, folders, hidden, stopped):
    suffixes = {"." + f for f in formats()}
    entries = {}
    package_ids = set()
    series = {"hours": tr("The Hours"), "lilies": tr("Water Lilies"),
              "haystacks": tr("Haystacks"), "magpie": tr("The Magpie")}
    lights = {"dawn": tr("Dawn"), "day": tr("Day"), "dusk": tr("Dusk"), "night": tr("Night")}

    def picture(p, personal=False, name=None):
        if p.suffix.lower() in suffixes and p.is_file():
            entries[p] = Wallpaper(name or p.stem, p, p, personal)

    for root in roots:
        try:
            for candidate in root.iterdir():
                if stopped.is_set():
                    return []
                if candidate.name.startswith("."):
                    continue
                try:
                    p = candidate.resolve(strict=True)
                    if p.is_file():
                        picture(p)
                        continue
                    if p in entries or not (p / "metadata.json").is_file():
                        continue
                    info = json.loads((p / "metadata.json").read_bytes())["KPlugin"]
                    package_id = info.get("Id", p.name)
                    if package_id in package_ids:
                        continue
                    previews = [img for img in (p / "contents/images").iterdir()
                                if img.suffix.lower() in suffixes and img.is_file()]
                    if not previews:
                        continue
                    locale = QLocale().name()
                    name = info.get("Name[" + locale + "]") or info.get("Name[" + locale.split("_")[0] + "]") or info.get("Name", p.name)
                    entries[p] = Wallpaper(name, p, min(previews, key=resolution_score))
                    package_ids.add(package_id)
                    if package_id == "Monet":
                        for directory, title in series.items():
                            for phase, label in lights.items():
                                picture(p / "contents" / directory / (phase + ".jpg"), name=tr("{series} · {light}").format(series=title, light=label))
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError):
                    continue
        except OSError:
            continue

    for folder in sorted(folders):
        for base, dirs, names in os.walk(folder):
            if stopped.is_set():
                return []
            dirs[:] = [name for name in dirs if not name.startswith(".") and not (Path(base) / name).is_symlink()]
            for name in names:
                if stopped.is_set():
                    return []
                path = Path(base) / name
                if not name.startswith(".") and path not in hidden and not path.is_symlink():
                    picture(path, True)
    for p in files:
        if stopped.is_set():
            return []
        if p not in hidden:
            picture(p, True)
    return sorted(entries.values(), key=lambda e: (not e.personal, e.name.casefold(), str(e.target)))


def thumbnail(path):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    target = QSize(256, 148)
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(size.scaled(target, Qt.KeepAspectRatio))
    image = reader.read()
    if not image.isNull():
        image = image.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return image


def apply(entry, connector=None):
    if not entry.target.exists() or thumbnail(entry.preview).isNull():
        raise ValueError(tr("This wallpaper is unavailable or could not be read."))
    # Follow Plasma's own wallpaper command across activity containments.
    # Encode the file as a URL, then quote both data values for the script.
    uri = entry.target.as_uri() + ("/" if entry.target.is_dir() else "")
    script = """
        const connector = %s;
        const screenId = connector === null ? null : screenForConnector(connector);
        const targets = desktops().filter(d => screenId === null || (screenId >= 0 && d.screen === screenId));
        const url = %s;
        let applied = 0;
        for (const d of targets) {
            d.wallpaperPlugin = 'org.kde.image';
            d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];
            d.writeConfig('Image', url);
            if (d.readConfig('Image') === url) ++applied;
        }
        print(applied > 0 && applied === targets.length);
    """ % (json.dumps(connector), json.dumps(uri))
    import dbus
    with closing(dbus.SessionBus(private=True)) as bus:
        shell = dbus.Interface(bus.get_object("org.kde.plasmashell", "/PlasmaShell"), "org.kde.PlasmaShell")
        result = str(shell.evaluateScript(script, timeout=8)).strip()
    if result != "true":
        raise ValueError(tr("The desktop could not apply this wallpaper to the selected display."))
