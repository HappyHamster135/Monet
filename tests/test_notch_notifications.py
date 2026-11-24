"""Test notch actions and shared history against KDE's actual notification server."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (importlib.util.find_spec("PySide6") and importlib.util.find_spec("dbus")
          and any(Path("/usr").glob("lib*/qt6/qml/org/kde/notificationmanager/qmldir")))


@unittest.skipUnless(NATIVE, "Qt, KDE notifications and D-Bus")
class NotchNotifications(unittest.TestCase):
    def test_preview_replacement_per_app_settings_and_shared_history(self):
        with private_session() as env:
            child = subprocess.run([sys.executable, "-m", "tests.test_notch_notifications", "--fixture"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


def fixture():
    import dbus
    from importlib.machinery import SourceFileLoader
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest

    home = Path(os.environ["HOME"])
    assert home.parent.name.startswith("monet-tests-")
    config = Path(os.environ["XDG_CONFIG_HOME"])
    (config / "plasmanotifyrc").write_text("[Applications][org.monet.SilentTest]\nShowPopups=false\n"
                                         "[Applications][org.monet.PopupTest]\nShowInHistory=false\n")
    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir(parents=True)
    for name in ("MailTest", "SilentTest", "PopupTest"):
        (apps / f"org.monet.{name}.desktop").write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\n")
    app = QGuiApplication([])
    app.setApplicationName("Notch notification test")
    loader = SourceFileLoader("notice_words", str(ROOT / "linux/libexec/monet-games"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    words = module.Words()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextObject(words)
    errors = []
    engine.warnings.connect(lambda values: errors.extend(e.toString() for e in values))
    ui = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
    page = home / "Notifications.qml"
    page.write_text('import QtQuick\nimport QtQuick.Controls\nimport "' + ui.as_uri() + '''" as Monet
ApplicationWindow {
    visible: true; width: 400; height: 340
    property alias previewId: preview.noticeId
    property alias heading: preview.title
    property alias selected: inbox.inDetail
    property alias subject: inbox.detail
    property int requestId: 0
    Monet.NoticePreview { id: preview }
    Monet.NoticeInbox {
        id: inbox; anchors.fill: parent
        liveSource: preview; requestedNotice: requestId; onPreviewFinished: requestId = 0
    }
    function read(id) { inbox.show({id: id, kind: 1}) }
    function confirmClear() { inbox.askClear() }
    function clearListed() { inbox.clearListed() }
}''')
    engine.load(QUrl.fromLocalFile(str(page)))
    assert engine.rootObjects(), errors
    win = engine.rootObjects()[0]

    def wait(test, description):
        end = time.monotonic() + 6
        while not test():
            if time.monotonic() >= end:
                raise AssertionError((description, errors))
            QTest.qWait(15)

    with ThreadPoolExecutor(max_workers=1) as worker:
        # The Qt main thread runs the server. A separate connection acts as a real sending app.
        def send(title, sender="MailTest", ident=0):
            def notify():
                bus = dbus.SessionBus(private=True)
                try:
                    return int(bus.call_blocking("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                               "org.freedesktop.Notifications", "Notify", "susssasa{sv}i",
                               ("Mail", ident, "mail-unread", title, "body", [],
                                {"desktop-entry": "org.monet." + sender}, 0), timeout=4))
                finally:
                    bus.close()
            task = worker.submit(notify)
            wait(task.done, "notification delivery")
            return task.result()

        first = send("First")
        wait(lambda: win.property("previewId") == first, "first preview")
        silent = send("Silent", "SilentTest")
        QTest.qWait(120)
        assert win.property("previewId") == first
        win.read(silent)
        wait(lambda: win.property("selected"), "silent app is still in history")
        popup = send("Popup only", "PopupTest")
        wait(lambda: win.property("previewId") == popup, "popup-only sender")
        win.read(popup)
        assert not win.property("selected")
        win.setProperty("requestId", popup)
        wait(lambda: win.property("selected"), "popup-only details")
        send("Replacement", "PopupTest", popup)
        wait(lambda: win.property("heading") == "Replacement", "updated preview")
        wait(lambda: win.property("subject").toVariant().get("summary") == "Replacement", "updated open detail")

        win.confirmClear()
        new = send("Arrived during confirmation")
        send("Replaced during confirmation", ident=first)
        QTest.qWait(80)
        win.clearListed()
        QTest.qWait(120)
        win.read(silent)
        assert not win.property("selected"), "confirmed existing notification survived"
        for ident in (new, first):
            win.read(ident)
            assert win.property("selected"), "an arriving or replaced notification was cleared"
    assert not errors, errors
    win.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--fixture"]:
        fixture()
    else:
        unittest.main()
