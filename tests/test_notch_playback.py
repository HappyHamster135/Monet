"""Exercise notch seeking against a player that advances to a same-titled track."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
import unittest

from tools.test import private_session, stop

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
NATIVE = importlib.util.find_spec("PySide6") and any(
    Path("/usr").glob("lib*/qt6/qml/org/kde/plasma/private/mpris/qmldir"))


@unittest.skipUnless(NATIVE, "requires Qt and Plasma media controls")
class NotchPlayback(unittest.TestCase):
    def test_scrub_belongs_to_the_track_that_was_pressed(self):
        with private_session() as env:
            probe = subprocess.run([sys.executable, "-m", "tests.test_notch_playback", "--fixture"],
                                   env=env, cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)


def fixture():
    import dbus
    from PySide6.QtCore import QPointF, Qt, QUrl
    from PySide6.QtQuick import QQuickItem, QQuickView
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    scene = Path.home() / "MusicTest.qml"
    scene.write_text('''import QtQuick
import org.kde.plasma.private.mpris as Mpris
import "''' + UI.as_uri() + '''" as Monet
Item {
    width: 400; height: 290
    function i18n(text) { return text }
    Mpris.Mpris2Model { id: players }
    Monet.Music {
        objectName: "music"; anchors.fill: parent
        sources: players; player: players.currentPlayer
        playing: false; view: 0; formatDuration: ms => String(ms)
    }
}''')
    view = QQuickView()
    view.setSource(QUrl.fromLocalFile(str(scene)))
    assert view.status() == QQuickView.Ready, [e.toString() for e in view.errors()]
    view.show()
    music = view.rootObject().findChild(QQuickItem, "music")
    slider = music.findChild(QQuickItem, "notchPlaybackPosition")
    events = Path.home() / "events"

    def wait(check, label):
        until = time.monotonic() + 4
        while time.monotonic() < until:
            if check():
                return
            QTest.qWait(20)
        raise AssertionError(label)

    def at(fraction):
        return slider.mapToScene(QPointF(slider.width() * fraction, slider.height() / 2)).toPoint()

    proc = subprocess.Popen([sys.executable, str(ROOT / "tests/fixtures/media-keys-wayland.py"), "--player", "Music"],
                            start_new_session=True)
    try:
        wait(lambda: music.property("trackId") == "/sample" and slider.isEnabled(), "first track")
        QTest.mousePress(view, Qt.LeftButton, pos=at(.2))
        QTest.mouseMove(view, at(.6))
        player = dbus.SessionBus().get_object("org.mpris.MediaPlayer2.Music", "/org/mpris/MediaPlayer2")
        player.Next(dbus_interface="org.mpris.MediaPlayer2.Player")
        wait(lambda: music.property("trackId") == "/other", "new track with identical title")
        QTest.mouseRelease(view, Qt.LeftButton, pos=at(.6))
        QTest.qWait(60)
        assert events.read_text().splitlines() == ["Music Next"]
        QTest.mouseClick(view, Qt.LeftButton, pos=at(.6))
        wait(lambda: "Music SetPosition /other " in events.read_text(), "seek current track")
        QTest.keyClick(view, Qt.Key_Home)
        wait(lambda: events.read_text().endswith("Music SetPosition /other 0\n"), "seek to start")
        assert len(events.read_text().splitlines()) == 3
    finally:
        stop(proc)
        view.close()
        app.processEvents()


if __name__ == "__main__" and sys.argv[1:] == ["--fixture"]:
    fixture()
