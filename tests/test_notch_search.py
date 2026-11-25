"""The notch creates runners on demand and delivers one keyboard activation."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
NATIVE = importlib.util.find_spec("PySide6") and shutil.which("kbuildsycoca6") and any(
    Path("/usr").glob("lib*/qt6/qml/org/kde/milou/qmldir")) and any(
    Path("/usr").glob("lib*/qt6/plugins/kf6/krunner/krunner_services.so"))


@unittest.skipUnless(NATIVE, "requires Qt, Milou and the Plasma application runner")
class NotchSearch(unittest.TestCase):
    def test_query_navigation_and_keyboard_activation(self):
        with private_session() as env:
            result = subprocess.run([sys.executable, "-m", "tests.test_notch_search", "--fixture"],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def fixture():
    from PySide6.QtCore import QObject, Qt, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QSignalSpy, QTest

    class Words(QObject):
        @Slot(str, result=str)
        def i18n(self, message):
            return message

    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir()
    for n in (1, 2):
        (apps / f"monet-search-fixture-{n}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=MonetSearchFixture {n}\nExec=/usr/bin/true {n}\n")
    subprocess.run(["kbuildsycoca6", "--noincremental"], check=True)
    app = QGuiApplication([])
    words = Words()
    window = QQuickView()
    window.rootContext().setContextObject(words)
    window.setResizeMode(QQuickView.SizeRootObjectToView)
    window.setSource(QUrl.fromLocalFile(str(UI / "NotchSearch.qml")))
    assert window.rootObject(), window.errors()
    window.resize(420, 360)
    window.show()
    window.requestActivate()
    page = window.rootObject()
    page.focusSearch()
    runs = QSignalSpy(page.activated)
    field = window.activeFocusItem()
    assert field and field.property("placeholderText") == "Search apps, files and commands"
    QTest.keyClick(window, Qt.Key_Return)
    assert runs.count() == 0

    def populated():
        for _ in range(140):
            QTest.qWait(35)
            listing = page.findChild(QObject, "notchCommandResults")
            if listing and listing.property("count") >= 2 and not listing.property("querying"):
                return listing
        found = listing.property("count") if listing else 0
        raise AssertionError(f"Expected both temporary applications, found {found} results")

    field.setProperty("text", "MonetSearchFixture")
    listing = populated()
    QTest.keyClick(window, Qt.Key_Down)
    assert listing.property("currentIndex") == 1
    QTest.keyClick(window, Qt.Key_Return)
    assert runs.count() == 1
    page.focusSearch()
    field.setProperty("text", "")
    QTest.qWait(50)
    assert page.findChild(QObject, "notchCommandResults") is None
    field.setProperty("text", "MonetSearchFixture")
    QTest.keyClick(window, Qt.Key_Return)
    for _ in range(140):
        if runs.count() == 2:
            break
        QTest.qWait(35)
    assert runs.count() == 2
    window.close()


if __name__ == "__main__":
    fixture() if "--fixture" in sys.argv else unittest.main()
