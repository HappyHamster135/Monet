"""Record real videos on a private Wayland display. Pass --module to test a build."""
import argparse
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


def launch(args):
    with private_session() as env:
        env.update(WAYLAND_DISPLAY="monet-click-zoom-test", QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", LANGUAGE="en", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1",
                   QT_FFMPEG_DECODING_HW_DEVICE_TYPES=",", PIPEWIRE_REMOTE="pipewire-0")
        home = Path(env["HOME"])
        if args.module:
            plugin = home/"plugins/kwin/plugins/screencast.so"
            plugin.parent.mkdir(parents=True)
            shutil.copy2(args.module, plugin)
            env["QT_PLUGIN_PATH"] = str(home/"plugins")
        kwin = home/"kwin_wayland"
        shutil.copy2(shutil.which("kwin_wayland"), kwin)
        cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "--private"]
        if args.installed:
            cmd.append("--installed")
        script = home/"worker"
        script.write_text("#!/bin/sh\nexec " + shlex.join(cmd))
        script.chmod(0o700)
        processes = []
        try:
            for command in (["pipewire"], ["wireplumber", "--profile", "policy"]):
                processes.append(subprocess.Popen(command, env=env, start_new_session=True))
                if command == ["pipewire"]:
                    deadline = time.monotonic()+4
                    while not (Path(env["XDG_RUNTIME_DIR"])/"pipewire-0").is_socket():
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Private PipeWire did not start")
                        time.sleep(.04)
            desktop = subprocess.Popen([kwin, "--virtual", "--width", "1024", "--height", "768",
                "--socket", env["WAYLAND_DISPLAY"], "--no-lockscreen", "--no-global-shortcuts",
                "--no-kactivities", "--exit-with-session", script], env=env, start_new_session=True)
            processes.append(desktop)
            desktop.wait(timeout=100)
            assert (home/"passed").exists(), "Recording worker failed"
        finally:
            for process in reversed(processes):
                stop(process)


def exercise(args):
    assert os.environ["WAYLAND_DISPLAY"] == "monet-click-zoom-test"
    assert str(Path.home()).startswith("/tmp/monet-tests-")
    import dbus
    sys.path.insert(0, str(Path("/usr/share/monet/utilities") if args.installed else ROOT/"linux/share/monet/utilities"))
    from window import Window
    from tests.fixtures.wayland_pointer import Pointer
    from tests.test_resume import r
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])
    bus = dbus.SessionBus()
    class Target(QWidget):
        tick = 0
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#177831"))
            painter.fillRect(self.tick % 400, 50, 50, 50, QColor("#fff500"))
            painter.end()

        def advance(self):
            self.tick += 7
            self.update()

    target = Target()
    target.setWindowTitle("Monet recording fixture")
    target.resize(640, 480)
    target.show()
    timer = QTimer(target)
    timer.timeout.connect(target.advance)
    timer.start(70)
    home = Window("/usr/libexec")
    home.Open(["recordings"])
    page = home.pages["recordings"]
    takes = Path.home()/"captures"
    config = page.capture_settings()
    config.setValue("VideoSave/videoSaveLocation", takes.as_uri())
    config.sync()
    ptr = Pointer(Path(os.environ["XDG_RUNTIME_DIR"])/os.environ["WAYLAND_DISPLAY"])
    def wait(check, label):
        deadline = time.monotonic()+12
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            QTest.qWait(50)
        raise AssertionError((label, page.message.text()))

    window = 'const w=windows().find(w=>w.caption==="Monet recording fixture");'
    wait(lambda: r.kwin_script(window+'reply(!!w)'), "test window")
    r.kwin_script(window+'w.frameGeometry={x:110,y:105,width:640,height:480};reply(true)')
    bus_api = dbus.Interface(bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"), "org.freedesktop.DBus")
    def indicator():
        if not page.recorder:
            return None
        for name in bus.list_names():
            if not name.startswith(":") or bus_api.GetConnectionUnixProcessID(name) != page.recorder.processId():
                continue
            obj = bus.get_object(name, "/StatusNotifierItem", introspect=False)
            try:
                if "org.kde.StatusNotifierItem" in obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable"):
                    return dbus.Interface(obj, "org.kde.StatusNotifierItem")
            except dbus.DBusException:
                pass
        return None

    for mode, enabled, auto_edit in (("s", False, True), ("w", True, True), ("s", True, True), ("r", True, False)):
        previous = set(takes.glob("*"))
        page.auto_edit.setChecked(auto_edit)
        page.click_zoom.setChecked(enabled)
        page.capture(mode)
        QTest.qWait(1200)
        if mode == "r":
            wait(lambda: r.kwin_script('reply(windows().some(w=>w.resourceClass==="org.kde.spectacle" && w.active))'), "region picker")
            QTest.qWait(300)
            ptr.point(185, 175)
            QTest.qWait(100)
            ptr.button(True)
            for i in range(1, 11):
                ptr.point(185+28.5*i, 175+18*i)
                QTest.qWait(35)
            ptr.button(False)
            QTest.qWait(500)
            if not indicator():
                ptr.point(300, 250)
                ptr.click()
                QTest.qWait(85)
                ptr.click()
        else:
            ptr.point(330, 260)
            ptr.click()
        tray = wait(indicator, "recording indicator")
        QTest.qWait(850)
        if mode != "s":
            ptr.point(950, 670)
            ptr.click()
            QTest.qWait(650)
        ptr.point(350, 263)
        ptr.click()
        QTest.qWait(180)
        ptr.click()
        QTest.qWait(1200)
        tray.Activate(0, 0)
        wait(lambda: page.recorder is None, "saved recording")
        take, = set(takes.glob("*")) - previous
        assert take.stat().st_size > 0
        if not auto_edit:
            assert page.file != take
            home.Open(["recordings"])
            page.open_file(take)
        wait(lambda: page.file == take and page.duration > 0, "loaded video")
        if not enabled:
            assert page.take_zooms is None and not page.picture.zooms
            continue
        group, = page.take_zooms.groups
        zoom, = page.picture.zooms
        expected = {"s": (350/1024, 263/768), "w": (240/640, 158/480), "r": (165/286, 88/181)}[mode]
        assert abs(group[2]-expected[0]) < .012 and abs(group[3]-expected[1]) < .012, (mode, group)
        assert 650 < group[0] < page.duration-750 and 80 <= group[1]-group[0] < 550, (mode, group)
        page.list_zooms()
        next(a for a in page.zoom_menu.actions() if a.text() == "Clear zooms").trigger()
        page.open_file(take)
        wait(lambda: page.duration > 0, "reopened take")
        assert not page.picture.zooms
        page.list_zooms()
        next(a for a in page.zoom_menu.actions() if a.text() == "Restore zooms from clicks").trigger()
        assert page.picture.zooms == [zoom]
        page.zoom_history.undo()
        assert not page.picture.zooms
        print("Verified click zooms", mode, take.name, group, flush=True)
    (Path.home()/"passed").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    (exercise if args.private else launch)(args)
