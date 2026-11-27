"""Shared tool choices survive login and reach an already running notch."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
NATIVE = importlib.util.find_spec("PySide6") and any(
    Path("/usr").glob("lib*/qt6/qml/org/kde/plasma/workspace/dbus/qmldir"))


@unittest.skipUnless(NATIVE, "requires the Plasma session bus module and Qt")
class ToolVisibility(unittest.TestCase):
    def test_catalog_changes_and_last_pending_pad_save(self):
        with private_session() as env:
            child = subprocess.run([sys.executable, "-m", "tests.test_notch_tool_visibility", "--fixture"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=25)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


def fixture():
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer, QUrl
    from PySide6.QtDBus import QDBusConnection
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QTreeWidget

    sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
    from window import Receiver, SERVICE, Window

    app = QApplication([])
    settings = QSettings("Monet", "Utilities")
    settings.setValue("hidden", '["downloads"]')
    settings.sync()
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    engine.load(QUrl.fromLocalFile(str(UI / "ToolVisibility.qml")))
    (tools,) = engine.rootObjects()
    from actions import DEFAULT_FAVORITES
    assert len(DEFAULT_FAVORITES) == 12
    assert not set(DEFAULT_FAVORITES) & {"notes", "calendars", "shelf", "clipboard", "downloads", "camera", "mixer", "agents"}
    assert tools.property("favorites").toVariant() == DEFAULT_FAVORITES
    assert not settings.contains("favorites")
    from actions import preferences
    for chosen in (["camera", "notes"], []):
        settings.setValue("favorites", json.dumps(chosen)); settings.sync()
        tools.reload()
        assert tools.property("favorites").toVariant() == chosen
        assert preferences(settings)[0] == chosen
    settings.remove("favorites"); settings.sync(); tools.reload()
    from notch_preferences import RADIAL_DEFAULT, save_radial
    assert tools.property("radial").toVariant() == RADIAL_DEFAULT
    chosen = ["emoji", "", "record", "downloads", "", "", "", ""]
    save_radial(settings, chosen);tools.reload()
    assert tools.property("radial").toVariant() == ["emoji", "", "record", "", "", "", "", ""]
    assert tools.property("hidden").toVariant() == ["downloads"], warnings
    bus = QDBusConnection.sessionBus()
    assert not bus.interface().isServiceRegistered(SERVICE).value()
    window = Window("/usr/libexec")
    receiver = Receiver(window)
    assert bus.registerService(SERVICE)
    QTest.qWait(50)

    def apply(hidden):
        def choose():
            dialog = app.activeModalWidget()
            tree = dialog.findChild(QTreeWidget)
            for row in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(row)
                item.setCheckState(1, Qt.Unchecked if item.data(0, Qt.UserRole) in hidden else Qt.Checked)
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
        QTimer.singleShot(0, choose)
        window.customize()
        for _ in range(60):
            if set(tools.property("hidden").toVariant()) == hidden:
                return
            QTest.qWait(20)
        raise AssertionError((tools.property("hidden").toVariant(), warnings))

    apply(set())
    assert tools.property("radial").toVariant() == chosen
    window.Open(["downloads"])
    assert "downloads" in window.pages
    window.hide()
    test_file = Path.home() / "kept file"
    test_file.touch()
    assert receiver.AddToShelf(test_file.as_uri())
    pad = json.loads(receiver.pad_request('{"action":"view"}'))["pad"]
    apply({"downloads", "shelf", "notes", "watch", "agents"})
    receiver.Present(json.dumps(["watch", "3"]))
    receiver.Present(json.dumps(["floating-pad", pad["id"]]))
    receiver.Present(json.dumps(["downloads"]))
    assert not window.isVisible() and not window.notch_previews and not window.floating_pads
    assert "downloads" not in window.pages
    assert not receiver.AddToShelf(test_file.as_uri())
    assert receiver.shelf_request('{"action":"remove","urls":[]}') == "{}"
    assert not json.loads(receiver.pad_request('{"action":"new"}'))["ok"]
    data = json.dumps(dict(action="save", id=pad["id"], revision=pad["revision"], value="Final keystroke"))
    assert json.loads(receiver.pad_request(data))["ok"]
    apply(set())
    (row,) = json.loads(receiver.shelf_request('{"action":"view"}'))["rows"]
    assert row["path"] == str(test_file)
    assert json.loads(receiver.pad_request('{"action":"view"}'))["pad"]["body"] == "Final keystroke"
    assert not warnings, warnings
    bus.unregisterService(SERVICE)
    receiver.idle.stop()
    receiver.deleteLater()
    window.close()
    window.deleteLater()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    fixture() if "--fixture" in sys.argv else unittest.main()
