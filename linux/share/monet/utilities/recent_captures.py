"""Recent images and videos in the save locations used by Spectacle."""
from heapq import nlargest
import os
from pathlib import Path
from PySide6.QtCore import QSettings, QStandardPaths, QUrl

from actions import tr


def capture_folders(include_images, include_video):
    config = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "spectaclerc"
    settings = QSettings(str(config), QSettings.IniFormat)
    formats = []
    if include_images:
        formats.append(("ImageSave", "imageSaveLocation", "translatedScreenshotsFolder", tr("Screenshots"),
                        QStandardPaths.PicturesLocation, {".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp", ".tiff"}))
    if include_video:
        formats.append(("VideoSave", "videoSaveLocation", "translatedScreencastsFolder", tr("Screencasts"),
                        QStandardPaths.MoviesLocation, {".mp4", ".webm", ".mkv", ".mov", ".gif"}))
    folders = {}
    for group, key, translated, default, location, extensions in formats:
        value = settings.value(f"{group}/{key}", "")
        if value:
            url = QUrl(value) if isinstance(value, QUrl) else QUrl.fromUserInput(str(value))
            if not url.isLocalFile():
                continue
            folder = Path(url.toLocalFile())
        else:
            folder = Path(QStandardPaths.writableLocation(location)) / str(settings.value(f"{group}/{translated}", default))
        folders.setdefault(folder, set()).update(extensions)
    return folders


def recent_files(folders):
    def files():
        for folder, extensions in folders.items():
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if entry.name.startswith(".") or Path(entry.name).suffix.lower() not in extensions:
                            continue
                        try:
                            if entry.is_file(follow_symlinks=False):
                                yield entry.stat(follow_symlinks=False).st_mtime_ns, entry.path
                        except OSError:
                            continue
            except OSError:
                continue
    return [{"name": Path(path).name, "url": QUrl.fromLocalFile(path).toString(QUrl.FullyEncoded),
             "video": Path(path).suffix.lower() in {".mp4", ".webm", ".mkv", ".mov", ".gif"}}
            for _, path in nlargest(12, files())]
