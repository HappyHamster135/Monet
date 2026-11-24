"""Exercise mouse wheel profiles and clicks in a private compositor and real Qt scroll areas."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "linux/share/monet/utilities")]
from tools.test import private_session, stop
from wayland_pointer import Pointer


def worker(helper):
    import dbus
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtWidgets import QApplication, QLabel, QScrollArea
    from wheel_scrolling import WheelScrolling

    app = QApplication([])
    class Area(QScrollArea):
        def __init__(self, title):
            super().__init__()
            self.events = []
            self.clicks = 0
            label = QLabel(title)
            label.setFixedSize(2000, 2000)
            self.setWidget(label)
            self.setWindowTitle(title)
            self.setFixedSize(320, 240)

        def wheelEvent(self, event):
            self.events.append((event.angleDelta().x(), event.angleDelta().y(),
                                event.pixelDelta().x(), event.pixelDelta().y(), event.modifiers().value))
            super().wheelEvent(event)

        def viewportEvent(self, event):
            if event.type() == QEvent.MouseButtonPress:
                self.clicks += 1
            return super().viewportEvent(event)

    def pump(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            app.processEvents()
            time.sleep(.003)

    def totals(events):
        return tuple(map(sum, zip(*events))) if events else (0,) * 5

    assert os.environ["WAYLAND_DISPLAY"] == "monet-wheel-test"
    bus = dbus.SessionBus()
    obj = bus.get_object("org.kde.KWin", "/org/kde/KWin/EIS/RemoteDesktop")
    remote = dbus.Interface(obj, "org.kde.KWin.EIS.RemoteDesktop")
    fd, cookie = remote.connectToEIS(dbus.Int32(2))
    fd = fd.take()
    try:
        driver = subprocess.Popen([helper, str(fd)], pass_fds=(fd,), stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True)
    finally:
        os.close(fd)
    try:
        assert driver.stdout.readline().strip() == "ready", "EIS wheel unavailable"
        pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-wheel-test", version=4)
        first, second = Area("Wheel One"), Area("Wheel Two")
        first.show()
        second.show()
        pump(.3)
        from tests.test_resume import r
        assert r.kwin_script("""for (const w of windows()) {
            if (!w.caption.startsWith("Wheel ")) continue;
            w.frameGeometry={x:w.caption.endsWith("One") ? 20 : 500,y:100,width:w.frameGeometry.width,height:w.frameGeometry.height};
            if (w.caption.endsWith("One")) workspace.activeWindow=w;
        } reply(true)""")
        pump(.35)
        pointer.point(180, 230)
        pump(.1)
        # First click on the other window must focus it and reach its content.
        pointer.point(630, 230)
        pump(.05)
        pointer.click()
        pump(.08)
        pointer.point(180, 230)
        pointer.click()
        pump(.08)
        assert (first.clicks, second.clicks) == (1, 1), (first.clicks, second.clicks)
        panel = WheelScrolling()
        pump(.1)
        assert panel.check.isFinished() and panel.available, panel.status.text()
        assert not panel.config.allKeys(), panel.config.allKeys()
        assert panel.profile.currentData() == "system"
        def choose(combo, value):
            combo.setCurrentIndex(combo.findData(value))
            pump(.06)

        def scroll(y, kind="d", x=0, settle=.12):
            first.events.clear()
            driver.stdin.write(f"{kind} {x} {y}\n")
            driver.stdin.flush()
            assert driver.stdout.readline().strip() == "sent"
            pump(settle)
            return first.events.copy()

        baseline = scroll(120)
        assert totals(baseline)[1] == -120, baseline
        raw = scroll(7, "p")
        choose(panel.profile, "linear")
        linear = scroll(120)
        assert totals(linear)[1] == -120, linear
        if os.environ["QT_QPA_PLATFORM"] == "wayland":
            assert totals(linear)[3] == -40, linear
        assert scroll(7, "p") == raw, raw
        # Four quarter-detents must add up to a full turn of one notch.
        panel.step.setValue(200)
        pump(.05)
        small = [event for _ in range(4) for event in scroll(30, settle=.04)]
        assert abs(totals(small)[1] + 240) <= 2, small
        choose(panel.profile, "smooth")
        panel.step.setValue(100)
        panel.duration.setValue(240)
        pump(.05)
        before = first.verticalScrollBar().value()
        smooth = scroll(120, settle=.37)
        assert len(smooth) > 1 and abs(totals(smooth)[1] + 120) <= 2, smooth
        assert first.verticalScrollBar().value() > before, (before, first.verticalScrollBar().value())
        count = len(first.events)
        pump(.25)
        assert len(first.events) == count
        # Reversing removes the pending tail of the first direction.
        scroll(120, settle=.06)
        reverse = scroll(-120, settle=.35)
        assert totals(reverse)[1] >= 118 and all(ev[1] >= 0 for ev in reverse), reverse
        for mode in ("system", "linear"):
            choose(panel.profile, mode)
            for name, key in (("shift", 42), ("alt", 56), ("meta", 125), ("ctrl", 29)):
                choose(panel.sideways, name)
                pointer.key(key, True)
                pump(.05)
                sideways = scroll(120)
                pointer.key(key, False)
                pump(.05)
                assert totals(sideways)[:2] == (-120, 0), (mode, name, sideways)
                assert all(e[4] == 0 for e in sideways), (mode, name, sideways)

        pointer.key(29, True)
        pump(.06)
        pointer.key(42, True)
        pump(.04)
        chord = scroll(120)
        assert totals(chord)[1] == -120 and chord[-1][4] != 0, chord
        pointer.key(42, False)
        pointer.key(29, False)
        pump(.04)
        choose(panel.profile, "smooth")
        scroll(120, settle=.03)
        pointer.click()
        pump(.04)
        count = len(first.events)
        pump(.3)
        assert first.clicks == 2 and count == len(first.events), (first.clicks, count, first.events)
        scroll(120, settle=.03)
        pointer.point(630, 230)
        pump(.04)
        count = len(first.events)
        pump(.3)
        assert count == len(first.events) and second.events == [], (first.events, second.events)
        assert QSettings("Monet", "WheelScrolling").value("profile") == "smooth"
        reopened = WheelScrolling()
        assert reopened.duration.value() == 240 and reopened.sideways.currentData() == "ctrl"
        choose(panel.profile, "system")
        choose(panel.sideways, "off")
        pointer.point(180, 230)
        pump(.06)
        assert scroll(120) == baseline
        Path.home().joinpath("passed").touch()
        print("Passed", os.environ["QT_QPA_PLATFORM"], "wheel profiles, widget scrolling, first clicks, cancellation and modifier routing")
    finally:
        driver.stdin.close()
        stop(driver)
        remote.disconnect(cookie)


def run(opts):
    with private_session() as env:
        home = Path(env["HOME"])
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(WAYLAND_DISPLAY="monet-wheel-test", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", QT_QPA_PLATFORM="wayland",
                   LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1")
        if opts.plugin:
            dest = home / "plugins/kwin/plugins"
            dest.mkdir(parents=True)
            shutil.copyfile(opts.plugin, dest / "monet_wheel_scroll.so")
            env["QT_PLUGIN_PATH"] = str(dest.parents[1])
        session = home / "session.sh"
        session.write_text("#!/bin/sh\nexport QT_QPA_PLATFORM=" + opts.platform + "\nexec " +
                           shlex.join([sys.executable, __file__, "--worker", str(opts.driver.resolve())]) + "\n")
        session.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--width", "900", "--height", "600", "--xwayland",
                                   "--no-lockscreen", "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"],
                                   "--exit-with-session", session], env=env, start_new_session=True)
        try:
            server.wait(timeout=50)
            assert (home / "passed").is_file(), "Private wheel test failed"
        finally:
            stop(server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["wayland", "xcb"], default="wayland")
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--driver", type=Path, help="wheel-input built with pkg-config libei-1.0")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.driver:
        run(args)
    else:
        parser.error("--driver is required")
