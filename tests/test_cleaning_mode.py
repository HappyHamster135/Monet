"""Exercise the Utilities dialog and helper on a disposable session bus."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "linux/share/monet/utilities"


@unittest.skipUnless(importlib.util.find_spec("PySide6") and importlib.util.find_spec("dbus"), "Qt and D-Bus")
class CleaningMode(unittest.TestCase):
    def test_dialog_starts_locker_with_selected_time_and_recovers_from_failure(self):
        with private_session() as env:
            child = subprocess.run([sys.executable, "-m", "tests.test_cleaning_mode", "--fixture"],
                                   env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


def fixture():
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtDBus import QDBusConnection, QDBusVirtualObject
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox
    sys.path.insert(0, str(MODULES))
    from window import Window

    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    assert runtime.parent.name.startswith("monet-tests-")
    page = Path(os.environ["XDG_DATA_HOME"]) / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/CleaningScreen.qml"
    page.parent.mkdir(parents=True)
    page.write_bytes((MODULES.parent / "lockscreen/CleaningScreen.qml").read_bytes())
    app = QApplication([])
    bus = QDBusConnection.sessionBus()
    service = "org.freedesktop.ScreenSaver"
    settings = QSettings(str(runtime / "monet-cleaning.ini"), QSettings.IniFormat)

    class Locker(QDBusVirtualObject):
        active = False
        reject = False
        calls = 0

        def introspect(self, path):
            return ('<interface name="org.freedesktop.ScreenSaver"><method name="GetActive">'
                    '<arg type="b" direction="out"/></method><method name="Lock"/></interface>')

        def handleMessage(self, message, connection):
            if message.interface() != service:
                return False
            if message.member() == "GetActive":
                reply = message.createReply(self.active)
            elif message.member() == "Lock":
                self.calls += 1
                settings.sync()
                self.seconds = (int(settings.value("Cleaning/deadline")) - time.time_ns() // 1_000_000) / 1000
                reply = (message.createErrorReply("org.freedesktop.DBus.Error.Failed", "Fixture failure")
                         if self.reject else message.createReply())
            else:
                return False
            connection.send(reply)
            return True

    locker = Locker()
    assert bus.registerVirtualObject("/ScreenSaver", locker) and bus.registerService(service)
    window = Window(ROOT / "linux/libexec")

    def choose(seconds=None):
        shown = []
        def select():
            dialog = app.activeModalWidget()
            times = dialog.findChild(QComboBox)
            shown.append(times.currentData())
            if seconds is None:
                dialog.reject()
            else:
                times.setCurrentIndex(times.findData(seconds))
                buttons = dialog.findChild(QDialogButtonBox)
                next(b for b in buttons.buttons() if buttons.buttonRole(b) == QDialogButtonBox.AcceptRole).click()
        QTimer.singleShot(0, select)
        window.run_tool("lock")
        end = time.monotonic() + 4
        while window.running and time.monotonic() < end:
            QTest.qWait(15)
        assert not window.running
        settings.sync()
        return shown

    assert choose() == [60] and locker.calls == 0 and not settings.contains("Cleaning/deadline")
    shown = choose(120)
    assert shown == [60] and locker.calls == 1, (shown, locker.calls, window.status.currentMessage())
    assert 118 < locker.seconds <= 120
    assert choose() == [120]
    locker.active = True
    deadline = settings.value("Cleaning/deadline")
    choose(30)
    assert locker.calls == 1 and settings.value("Cleaning/deadline") == deadline
    assert "already locked" in window.status.currentMessage()
    locker.active = False
    locker.reject = True
    choose(30)
    assert locker.calls == 2 and not settings.contains("Cleaning/deadline")
    assert "could not lock" in window.status.currentMessage()
    window.close()


if __name__ == "__main__":
    if "--fixture" in sys.argv:
        fixture()
    else:
        unittest.main()
