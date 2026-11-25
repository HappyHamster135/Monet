"""Check desktop media shortcuts against real MPRIS services in a private KWin session."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from wayland_pointer import Pointer

MPRIS = "org.mpris.MediaPlayer2"
PLAYER = MPRIS + ".Player"
OBJECT = "/org/mpris/MediaPlayer2"


def player(name):
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    def record(action):
        with (Path.home() / "events").open("a") as f:
            f.write(f"{name} {action}\n")
    class Service(dbus.service.Object):
        track_id = "/sample"
        state = "Playing" if name in ("Video", "Monitor") else "Paused"

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
            if interface == MPRIS:
                return {"Identity": name, "DesktopEntry": "legacy.music" if name == "Fallback" else "fixture." + name, "CanRaise": False, "CanQuit": True,
                        "HasTrackList": False, "SupportedUriSchemes": dbus.Array([], signature="s"),
                        "SupportedMimeTypes": dbus.Array([], signature="s")}
            return {"PlaybackStatus": self.state, "CanControl": name != "Monitor", "CanPlay": name != "Monitor", "CanPause": name != "Monitor",
                    "CanSeek": True, "CanGoNext": True, "CanGoPrevious": True, "Volume": .5, "Rate": 1.,
                    "MinimumRate": 1., "MaximumRate": 1., "Position": dbus.Int64(0),
                    "Metadata": dbus.Dictionary({"xesam:title": "Fixture", "mpris:trackid": dbus.ObjectPath(self.track_id),
                                                 "mpris:length": dbus.Int64(120_000_000)}, signature="sv")}

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
        def Get(self, interface, key):
            return self.GetAll(interface)[key]

        @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
        def PropertiesChanged(self, interface, props, invalid):
            pass

        def change(self, action, state):
            record(action)
            self.state = state
            self.PropertiesChanged(PLAYER, {"PlaybackStatus": state}, [])

        @dbus.service.method(MPRIS)
        def Quit(self):
            GLib.idle_add(loop.quit)

        @dbus.service.method(PLAYER)
        def Next(self):
            record("Next")
            self.track_id = "/other" if self.track_id == "/sample" else "/sample"
            self.PropertiesChanged(PLAYER, {"Metadata": self.GetAll(PLAYER)["Metadata"]}, [])

        @dbus.service.method(PLAYER, in_signature="ox")
        def SetPosition(self, track, position):
            record(f"SetPosition {track} {position}")

        @dbus.service.method(PLAYER)
        def Play(self):
            self.change("Play", "Playing")

        @dbus.service.method(PLAYER)
        def Pause(self):
            self.change("Pause", "Paused")

        @dbus.service.method(PLAYER)
        def Stop(self):
            self.change("Stop", "Stopped")

        @dbus.service.method(PLAYER)
        def Previous(self):
            record("Previous")

        @dbus.service.method(PLAYER, in_signature="x")
        def Seek(self, delta):
            record(str(delta))

    if name == "Fallback":
        record("Started")
        time.sleep(.7)
    obj = Service(bus, OBJECT)
    service = dbus.service.BusName(MPRIS + "." + name, bus)
    loop = GLib.MainLoop()
    bus.call_on_disconnection(lambda _: loop.quit())
    loop.run()


def worker():
    import dbus
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from media_keys import MediaKeys
    assert os.environ["WAYLAND_DISPLAY"] == "media-key-test"
    bus = dbus.SessionBus()
    home = Path.home()
    log = home / "events"
    app = QApplication([])
    procs = []
    def spawn(*args):
        p = subprocess.Popen(args, start_new_session=True)
        procs.append(p)
        return p
    def wait(check, why):
        until = time.monotonic() + 8
        while time.monotonic() < until:
            app.processEvents()
            if check():
                return
            time.sleep(.025)
        raise AssertionError(why)
    def records():
        return log.read_text().splitlines() if log.exists() else []
    def key(code, expected=None):
        n = len(records())
        pointer.key(code, True)
        time.sleep(.03)
        pointer.key(code, False)
        if expected:
            wait(lambda: records()[n:] == [expected], (expected, records()))
        else:
            time.sleep(.15)
            assert len(records()) == n, records()
    try:
        if not bus.name_has_owner("org.kde.kded6"):
            spawn("kded6")
        wait(lambda: bus.name_has_owner("org.kde.kded6"), "KDED startup")
        kded = bus.get_object("org.kde.kded6", "/kded", introspect=False)
        assert kded.loadModule("mprisservice", dbus_interface="org.kde.kded6")
        rules = dbus.Interface(bus.get_object("org.kde.kded6", "/org/monet/MediaKeys", introspect=False), "org.monet.MediaKeys1")
        assert json.loads(rules.Players()) == {}
        video = spawn(sys.executable, __file__, "--player", "Video")
        music = spawn(sys.executable, __file__, "--player", "Music")
        wait(lambda: len(json.loads(rules.Players())) == 2, "Two active players")
        pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "media-key-test", version=4)
        panel = MediaKeys()
        panel.show()
        wait(lambda: len(panel.running) == 2, "Settings did not list both players")
        def permit(name, allowed):
            for i in range(panel.list.count()):
                item = panel.list.item(i)
                if item.data(Qt.UserRole) == "app:fixture." + name:
                    item.setCheckState(Qt.Checked if allowed else Qt.Unchecked)
                    app.processEvents()
                    time.sleep(.06)
                    return
            raise AssertionError(name)
        assert not panel.config.contains("blocked") and not panel.config.contains("fallback")
        key(163, "Video Next")
        permit("Video", False)
        key(163, "Music Next")
        # The stock KDE action keeps a user's customized shortcut and seek distance.
        n = len(records())
        for code in (29, 42, 67):
            pointer.key(code, True)
        for code in (67, 42, 29):
            pointer.key(code, False)
        wait(lambda: records()[n:] == ["Music 30000000"], "Custom seek shortcut")
        key(164, "Music Play")
        key(164, "Music Pause")
        # A blocked application still receives its own explicit playback commands.
        video_player = dbus.Interface(bus.get_object(MPRIS + ".Video", OBJECT), PLAYER)
        video_player.Next()
        assert records()[-1] == "Video Next"
        permit("Music", False)
        key(163)
        key(164)
        idx = panel.fallback.findData("fixture.Fallback")
        assert idx > 0
        panel.fallback.setCurrentIndex(idx)
        time.sleep(.08)
        key(163)
        n = len(records())
        for _ in range(2):
            pointer.key(164, True)
            time.sleep(.025)
            pointer.key(164, False)
            time.sleep(.07)
        wait(lambda: records()[n:] == ["Fallback Started", "Fallback Play"], ("launch once", records()))
        key(164, "Fallback Pause")
        assert panel.config.value("fallback") == "fixture.Fallback"
        permit("Fallback", False)
        assert panel.fallback.currentIndex() == 0 and not panel.config.contains("fallback")
        panel.fallback.setCurrentIndex(idx)
        assert "app:fixture.Fallback" not in panel.blocked()
        restored = MediaKeys()
        assert restored.fallback.currentData() == "fixture.Fallback"
        assert restored.blocked() == {"app:fixture.Video", "app:fixture.Music"}
        restored.close()
        # Filtering survives a player exiting, including reopening under a new D-Bus owner.
        stop(video)
        procs.remove(video)
        wait(lambda: "app:fixture.Video" not in panel.running, "Old video owner still listed")
        spawn(sys.executable, __file__, "--player", "Video")
        wait(lambda: "app:fixture.Video" in panel.running, "New video owner missing")
        key(165, "Fallback Previous")
        fallback = dbus.Interface(bus.get_object(MPRIS + ".Fallback", OBJECT), MPRIS)
        fallback.Quit()
        wait(lambda: "app:fixture.Fallback" not in panel.running, "Fallback still open")
        pointer.key(164, True)
        pointer.key(164, False)
        wait(lambda: records()[-1:] == ["Fallback Started"], "Second launch")
        key(166)
        wait(lambda: "app:fixture.Fallback" in panel.running, "Fallback did not register")
        assert records()[-1] == "Fallback Started", records()
        key(164, "Fallback Play")
        permit("Video", True)
        # Either eligible, playing app may now be Plasma's active player.
        dbus.Interface(bus.get_object(MPRIS + ".Fallback", OBJECT), PLAYER).Pause()
        key(163, "Video Next")
        for name in ("Video", "Music", "Fallback"):
            dbus.Interface(bus.get_object(MPRIS + "." + name, OBJECT), MPRIS).Quit()
        wait(lambda: json.loads(rules.Players()) == {}, "Closed players still registered")
        spawn(sys.executable, __file__, "--player", "Monitor")
        wait(lambda: list(json.loads(rules.Players())) == ["app:fixture.Monitor"], "Read-only session")
        n = len(records())
        pointer.key(164, True)
        pointer.key(164, False)
        wait(lambda: records()[n:] == ["Fallback Started", "Fallback Play"], "Read-only player swallowed Play")
        if os.environ.get("MONET_TEST_INSTALLED_MEDIA_KEYS") == "1":
            from tests.test_resume import r
            subprocess.run(["/usr/libexec/monet-quick", "utilities", "media-keys"], check=True, timeout=8)
            wait(lambda: r.kwin_script("reply(windows().some(w=>w.caption==='Media keys'))"), "Installed Settings action")
            assert r.kwin_script("const w=windows().find(w=>w.caption==='Media keys'); w.closeWindow(); reply(true)")
        print("Verified physical media-key routing, unchanged direct playback, saved exclusions and exactly one fallback launch.", flush=True)
        (home / "passed").touch()
    finally:
        for p in reversed(procs):
            stop(p)


def run(plugin):
    with private_session() as env:
        home = Path(env["HOME"])
        env.update(WAYLAND_DISPLAY="media-key-test", QT_QPA_PLATFORM="wayland", XDG_CURRENT_DESKTOP="KDE",
                   XDG_SESSION_TYPE="wayland", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1",
                   GSETTINGS_BACKEND="memory", PYTHONPATH=str(ROOT / "linux/share/monet/utilities") if plugin else "/usr/share/monet/utilities")
        if plugin:
            dest = home / "plugins/kf6/kded"
            dest.mkdir(parents=True)
            shutil.copyfile(plugin, dest / "mprisservice.so")
            env["QT_PLUGIN_PATH"] = str(dest.parents[1])
        (Path(env["XDG_CONFIG_HOME"]) / "kglobalshortcutsrc").write_text(
            "[mediacontrol]\nseekforwardmedialong=Ctrl+Shift+F9,none,Media playback seek forward 30s\n")
        applications = Path(env["XDG_DATA_HOME"]) / "applications"
        applications.mkdir()
        for name in ("Video", "Music", "Fallback"):
            (applications / ("fixture." + name + ".desktop")).write_text(
                "[Desktop Entry]\nType=Application\nName=" + name + "\nCategories=AudioVideo;Player;\n" +
                ("StartupWMClass=legacy.music\n" if name == "Fallback" else "") + "Exec=" +
                shlex.join([sys.executable, __file__, "--player", name]) + "\n")
        subprocess.run(["kbuildsycoca6", "--noincremental"], env=env, check=True)
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        script = home / "session.sh"
        script.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "--worker"]) + "\n")
        script.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--no-lockscreen", "--no-kactivities", "--socket",
                                   env["WAYLAND_DISPLAY"], "--exit-with-session", script], env=env, start_new_session=True)
        try:
            server.wait(timeout=70)
            assert (home / "passed").exists(), "Private media-key test failed"
        finally:
            stop(server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--player", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.player:
        player(args.player)
    elif args.worker:
        worker()
    else:
        run(args.plugin)
