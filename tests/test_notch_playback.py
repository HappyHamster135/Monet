"""Exercise track-specific notch controls against an MPRIS player with same-titled tracks."""
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
    def run_fixture(self, mode):
        with private_session() as env:
            probe = subprocess.run([sys.executable, "-m", "tests.test_notch_playback", mode],
                                   env=env, cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)

    def test_scrub_belongs_to_the_track_that_was_pressed(self):
        self.run_fixture("--fixture")

    def test_queued_play_waits_for_the_chosen_track_and_service(self):
        self.run_fixture("--queue")


def fixture(queue):
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
    id: root
    property string queueOwner: ""
    width: 400; height: 290
    function i18n(text) { return text }
    Mpris.Mpris2Model { id: players }
    Monet.QueuePlayback { id: action; objectName: "queuePlayback" }
    function choose(owner, track) { action.choose(owner, musicPage.trackId, track, players.currentPlayer) }
    Monet.Music {
        id: musicPage
        objectName: "music"; anchors.fill: parent; visible: !root.queueOwner
        sources: players; player: players.currentPlayer
        playing: false; view: 0; formatDuration: ms => String(ms)
    }
    Loader {
        anchors.fill: parent; active: !!root.queueOwner
        sourceComponent: Monet.NotchQueue {
            player: players.currentPlayer
            playback: action; service: "org.mpris.MediaPlayer2.Music"; track: musicPage.trackId; fresh: true
            snapshot: ({owner: root.queueOwner, service: service, trackId: track,
                        queue: [{id:"/missing",title:"First",artist:"",art:""}, {id:"/other",title:"Second",artist:"",art:""}]})
        }
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
        if queue:
            root = view.rootObject()
            controller = root.findChild(QQuickItem, "queuePlayback")
            bus = dbus.SessionBus()
            name = "org.mpris.MediaPlayer2.Music"
            owner = str(bus.get_name_owner(name))
            player = bus.get_object(name, "/org/mpris/MediaPlayer2")
            def calls():
                return events.read_text().splitlines() if events.exists() else []
            root.setProperty("queueOwner", owner)
            queue_list = root.findChild(QQuickItem, "notchQueue")
            assert queue_list and queue_list.activeFocusOnTab()
            queue_list.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(view, Qt.Key_Down)
            assert queue_list.property("currentIndex") == 1
            QTest.keyClick(view, Qt.Key_Return)
            wait(lambda: calls() == ["Music GoTo /other"], "skip requested without resuming the old song")
            root.choose(owner, "/missing")
            player.Next(dbus_interface="org.mpris.MediaPlayer2.Player")
            wait(lambda: calls() == ["Music GoTo /other", "Music Next", "Music Play"], "resume the chosen track once")
            wait(lambda: not controller.property("busy"), "finished")
            root.choose(owner, "/missing")
            wait(lambda: controller.property("failedOwner") == owner, "unsupported action reported")
            assert calls()[-1] == "Music GoTo /missing"
            # A new process can publish precisely the same service name and track IDs.
            stop(proc)
            wait(lambda: not music.property("trackId"), "old player exited")
            proc = subprocess.Popen([sys.executable, str(ROOT / "tests/fixtures/media-keys-wayland.py"),
                                     "--player", "Music"], start_new_session=True)
            wait(lambda: music.property("trackId") == "/sample", "replacement player")
            assert str(bus.get_name_owner(name)) != owner
            before = calls()
            root.choose(owner, "/other")
            wait(lambda: not controller.property("busy"), "stale queue rejected")
            assert controller.property("failedOwner") == owner and calls() == before
            return
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


if __name__ == "__main__" and sys.argv[1:] in (["--fixture"], ["--queue"]):
    fixture(sys.argv[1] == "--queue")
