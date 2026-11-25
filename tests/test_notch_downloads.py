"""Exercise the native folder watcher and Utilities' choice of download folder."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
NATIVE = importlib.util.find_spec("PySide6") and any(
    Path("/usr").glob("lib*/qt6/qml/org/kde/private/desktopcontainment/folder/qmldir"))


@unittest.skipUnless(NATIVE, "requires the Plasma directory model and Qt")
class NotchDownloads(unittest.TestCase):
    def test_arrivals_replacements_and_removable_folders(self):
        with private_session() as env:
            child = subprocess.run([sys.executable, "-m", "tests.test_notch_downloads", "--fixture"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=40)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


def fixture():
    from PySide6.QtCore import QSettings, QStandardPaths, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
    from pages import Downloads
    from window import Receiver, Window

    app = QApplication([])
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))

    def until(test):
        end = time.monotonic() + 6
        while not test() and time.monotonic() < end:
            QTest.qWait(25)
        assert test(), warnings

    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        folder = base / "Special %20 & # å"
        folder.mkdir()
        for i in range(20):
            path = folder / f"document {i}.txt"
            path.write_text("Saved")
            os.utime(path, (10 + i, 10 + i))
        (folder / "Empty.txt").touch()
        (folder / "Movie.mkv").touch()
        partial = folder / "Movie.abcd1234.mkv.part"
        partial.write_bytes(b"piece")
        (folder / "New folder").mkdir()
        (folder / ".hidden").touch()

        ui = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
        component = base / "Test.qml"
        component.write_text('import QtQuick\nimport "' + ui.as_uri() + '''" as Monet
Item {
    id: viewer
    property url directory
    property var rows: feed.recent
    property int completions: 0
    property bool observe: true
    Monet.DownloadFeed {
        id: feed
        directory: viewer.directory
        watchCompletions: viewer.observe
        onDownloadCompleted: viewer.completions++
    }
}''')
        engine.setInitialProperties({"directory": QUrl.fromLocalFile(str(folder))})
        engine.load(QUrl.fromLocalFile(str(component)))
        assert engine.rootObjects(), warnings
        root = engine.rootObjects()[0]

        def rows():
            return root.property("rows").toVariant()

        until(lambda: len(rows()) == 12)
        names = [r["name"] for r in rows()]
        assert "Empty.txt" in names and "Movie.mkv" not in names, names
        assert [r["name"] for r in rows() if r["partial"]] == [partial.name]
        assert names[-1] == "document 10.txt" and "New folder" not in names, names
        assert root.property("completions") == 0
        partial.replace(folder / "Movie.mkv")
        until(lambda: any(r["name"] == "Movie.mkv" and not r["partial"] for r in rows()))
        assert not any(r["partial"] for r in rows())
        assert root.property("completions") == 1
        (folder / "unrelated.txt").write_text("New file")
        until(lambda: any(r["name"] == "unrelated.txt" for r in rows()))
        assert root.property("completions") == 1
        root.setProperty("observe", False)
        archive = folder / "archive.zip.crdownload"
        archive.write_text("Archive")
        until(lambda: any(r["partial"] for r in rows()))
        archive.rename(folder / "archive.zip")
        until(lambda: any(r["name"] == "archive.zip" for r in rows()))
        assert root.property("completions") == 1
        other = base / "Reconnected #2"
        other.mkdir()
        file = other / "Photo #12 %2F.png"
        file.touch()
        root.setProperty("directory", QUrl.fromLocalFile(str(other)))
        until(lambda: [r["name"] for r in rows()] == [file.name])
        assert QUrl(rows()[0]["url"]).toLocalFile() == str(file)
        assert not warnings, warnings

        # A running Utilities window keeps its current page and focus. Adding
        # again is idempotent and the shelf stores the exact local path.
        window = Window("/usr/libexec")
        receiver = Receiver(window)
        previous = window.stack.currentWidget()
        address = file.as_uri()
        assert receiver.AddToShelf(address) and receiver.AddToShelf(address)
        assert window.pages["shelf"].files.paths() == [str(file)]
        assert window.stack.currentWidget() == previous and not window.isVisible()
        for invalid in ("https://example.org/file", "file://host/tmp/remote", (base / "missing").as_uri()):
            assert not receiver.AddToShelf(invalid)
        receiver.idle.stop()

        conf = QSettings(str(base / "prefs.ini"), QSettings.IniFormat)
        conf.setValue("downloads", str(other))
        page = Downloads(conf)
        page.show()
        until(lambda: page.view.isVisible())
        assert page.model.filePath(page.view.rootIndex()) == str(other)
        file.unlink()
        other.rmdir()
        until(lambda: page.view.isHidden() and page.unavailable.isVisible())
        assert conf.value("downloads") == str(other)
        other.mkdir()
        until(lambda: page.view.isVisible() and page.model.filePath(page.view.rootIndex()) == str(other))
        page.reset_folder()
        assert not conf.contains("downloads")
        assert page.path.text() == QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        page.close()
        assert not page.folder_watch.directories()


if __name__ == "__main__":
    if "--fixture" in sys.argv:
        fixture()
    else:
        unittest.main()
