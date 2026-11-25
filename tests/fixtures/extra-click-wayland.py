"""Exercise the native mouse filter and preferences in a private KWin compositor."""
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
from wayland_pointer import Pointer


def worker(helper, saved):
    import dbus
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtTest import QTest
    from extra_clicks import ExtraClicks
    from tests.test_resume import r
    assert os.environ["WAYLAND_DISPLAY"] == "extra-click-test"
    app = QApplication([])
    def pump(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            app.processEvents()
            time.sleep(.002)
    def until(check, why):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            app.processEvents()
            if check():
                return
            time.sleep(.005)
        raise AssertionError(why)

    class Target(QWidget):
        def __init__(self, title):
            super().__init__()
            self.setWindowTitle(title)
            self.setFixedSize(300, 210)
            self.events = []
            self.motions = []
            self.setMouseTracking(True)
        def mousePressEvent(self, e):
            self.events.append((e.button().value, True))
            e.accept()
        def mouseDoubleClickEvent(self, e):
            self.mousePressEvent(e)
        def mouseReleaseEvent(self, e):
            self.events.append((e.button().value, False))
            e.accept()
        def mouseMoveEvent(self, e):
            self.motions.append(e.buttons().value)

    bus = dbus.SessionBus()
    remote = dbus.Interface(bus.get_object("org.kde.KWin", "/org/kde/KWin/EIS/RemoteDesktop"), "org.kde.KWin.EIS.RemoteDesktop")
    drivers = []
    def connect(name):
        fd, cookie = remote.connectToEIS(dbus.Int32(2))
        fd = fd.take()
        try:
            driver = subprocess.Popen([helper, str(fd), name], pass_fds=(fd,), stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, text=True)
        finally:
            os.close(fd)
        drivers.append((driver, cookie))
        assert driver.stdout.readline().strip() == "ready"
        return driver
    def button(driver, code, down):
        driver.stdin.write(f"b {code} {int(down)}\n")
        driver.stdin.flush()
        assert driver.stdout.readline().strip() == "sent"
    left, right, middle, back = range(0x110, 0x114)
    def click(driver, code=left):
        button(driver, code, True)
        button(driver, code, False)
    def pairs(*buttons):
        return [(b.value, down) for b in buttons for down in (True, False)]
    def check(target, expected):
        until(lambda: len(target.events) >= len(expected), f"{target.windowTitle()} received {target.events}, expected {expected}")
        pump(.02)
        assert target.events == expected, (target.windowTitle(), target.events, expected)
        target.events.clear()
    try:
        one, two = connect("Monet mouse A"), connect("Monet mouse B")
        first, second = Target("Filter one"), Target("Filter two")
        panel = ExtraClicks()
        for widget in (first, second, panel):
            widget.show()
        until(lambda: panel.available and panel.model.count() >= 3, "Models unavailable")
        assert panel.enable.isChecked() == saved
        if not saved:
            assert not panel.config.allKeys(), panel.config.allKeys()
        QTest.mouseClick(panel.test_area, Qt.LeftButton)
        QTest.mouseClick(panel.test_area, Qt.RightButton)
        QTest.mouseClick(panel.test_area, Qt.MiddleButton)
        assert panel.test_area.counts == [1, 1, 1]
        panel.test_area.reset()
        assert panel.test_area.counts == [0, 0, 0]
        panel.hide()
        pump(.3)
        assert r.kwin_script("""for (const w of windows()) {
            if (!w.caption.startsWith("Filter ")) continue;
            w.frameGeometry={x:w.caption.endsWith("one") ? 40 : 440,y:70,width:w.frameGeometry.width,height:w.frameGeometry.height};
            if(w.caption.endsWith("one")) workspace.activeWindow=w;
        } reply(true)""")
        pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "extra-click-test", version=4)
        pointer.point(170, 160)
        pump(.18)
        L, R, M, B = Qt.LeftButton, Qt.RightButton, Qt.MiddleButton, Qt.BackButton
        click(one); click(one)
        check(first, pairs(L) if saved else pairs(L, L))
        if saved:
            print("Saved filter active at compositor startup.", flush=True)
            (Path.home() / "passed").touch()
            return
        panel.interval.setValue(100)
        panel.enable.setChecked(True)
        pump(.13)
        # The app sees the accepted press while the physical button is still down.
        button(one, left, True)
        until(lambda: first.events == [(L.value, True)], "First down missing")
        button(one, left, False)
        click(one)
        check(first, pairs(L))
        pump(.11)
        click(one); click(one, right); click(one, right); click(one, middle); click(one, back)
        check(first, pairs(L, R, R, M, B))
        panel.buttons["secondary"].setChecked(True)
        panel.buttons["middle"].setChecked(True)
        pump(.13)
        click(one, right); click(one, right); click(one, middle); click(one, middle)
        check(first, pairs(R, M))
        # Independent devices and button histories.
        click(one); click(two); click(one); click(two)
        check(first, pairs(L, L))
        pump(.13)
        click(one); button(one, left, True)  # rejected bounce
        button(two, left, True)              # accepted drag on the second mouse
        button(one, left, False)
        first.motions.clear()
        pointer.point(179, 162); pump(.03)
        assert L.value in first.motions, first.motions
        button(two, left, False)
        check(first, pairs(L, L))
        pump(.13)
        click(one)
        pointer.point(192, 160)
        pump(.01)
        click(one)
        pointer.point(550, 160)
        pump(.01)
        click(one)
        check(first, pairs(L, L))
        check(second, pairs(L))
        pump(.13)
        click(one)
        pointer.key(29, True); pump(.01)
        click(one)
        pointer.key(29, False)
        check(second, pairs(L, L))
        # A discarded down contributes neither a drag nor an orphaned up,
        # even when filtering is disabled before release.
        pump(.13)
        click(one); button(one, left, True); pump(.01)
        second.motions.clear()
        pointer.point(570, 170); pump(.02)
        assert second.motions and not any(second.motions), second.motions
        panel.enable.setChecked(False); pump(.02)
        button(one, left, False); click(one); click(one)
        check(second, pairs(L, L, L))
        panel.enable.setChecked(True)
        index = next(i for i in range(panel.model.count()) if "mouse A" in panel.model.itemText(i))
        model = panel.model.itemData(index)
        panel.model.setCurrentIndex(index); pump(.1)
        click(two); click(two); click(one); click(one)
        check(second, pairs(L, L, L))
        # Native drag keeps its button and release. The next click at the drop
        # point should reach the app straight away.
        pump(.13)
        button(one, left, True); pump(.01)
        pointer.point(600, 180); pump(.02)
        assert L.value in second.motions, second.motions
        pointer.point(570, 170); pump(.02)  # return the drag to its origin
        button(one, left, False); click(one)
        check(second, pairs(L, L))
        panel.show()
        one.stdin.close(); one.wait(timeout=3)
        remote.disconnect(dbus.Int32(drivers[0][1]))
        drivers.pop(0)
        until(lambda: "disconnected" in panel.model.currentText(), "Unplugged preference lost")
        one = connect("Monet mouse A")
        until(lambda: panel.model.currentData() == model and "disconnected" not in panel.model.currentText(), "Reconnected model")
        if os.environ.get("MONET_CLICK_INSTALLED") == "1":
            subprocess.run(["/usr/libexec/monet-quick","utilities","extra-clicks"], check=True, timeout=8)
            until(lambda: r.kwin_script("reply(windows().some(w=>w.caption==='Extra click filter'))"), "Installed Settings action")
            assert r.kwin_script("const w=windows().find(w=>w.caption==='Extra click filter'); w.closeWindow(); reply(true)")
        print("Verified", os.environ["QT_QPA_PLATFORM"], "button pairs, first clicks, focus switches, drags, hotplug and model selection.", flush=True)
        (Path.home() / "passed").touch()
    finally:
        for proc, cookie in drivers:
            if proc.poll() is None:
                proc.stdin.close()
                proc.wait(timeout=3)
            remote.disconnect(dbus.Int32(cookie))


def run(args):
    from PySide6.QtCore import QSettings
    with private_session() as env:
        home = Path(env["HOME"])
        env.update(WAYLAND_DISPLAY="extra-click-test", QT_QPA_PLATFORM="wayland", XDG_CURRENT_DESKTOP="KDE",
                   XDG_SESSION_TYPE="wayland", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1",
                   PYTHONPATH=str(ROOT/"linux/share/monet/utilities") if args.plugin else "/usr/share/monet/utilities")
        Path(env["XDG_CONFIG_HOME"], "kwinrc").write_text("[MouseBindings]\nCommandWindow1=Activate, raise and pass click\n")
        if args.plugin:
            dest = home / "plugins/kwin/plugins"
            dest.mkdir(parents=True)
            shutil.copyfile(args.plugin, dest/"monet_click_filter.so")
            env["QT_PLUGIN_PATH"] = str(dest.parents[1])
        else:
            env["MONET_CLICK_INSTALLED"] = "1"
        if args.saved:
            s = QSettings(str(Path(env["XDG_CONFIG_HOME"]) / "Monet/ExtraClicks.conf"), QSettings.IniFormat)
            s.setValue("enabled", True)
            s.setValue("interval", 100)
            s.sync()
        runner = home/"kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), runner)
        runner.chmod(0o700)
        session = home/"session.sh"
        cmd = [sys.executable, __file__, "--worker", str(args.driver.resolve())]
        if args.saved:
            cmd.append("--saved")
        session.write_text("#!/bin/sh\nexport QT_QPA_PLATFORM=" + args.platform + "\nexec " + shlex.join(cmd) + "\n")
        session.chmod(0o700)
        server = subprocess.Popen([runner, "--virtual", "--width", "1000", "--height", "620", "--xwayland",
                                   "--no-lockscreen", "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"],
                                   "--exit-with-session", session], env=env, start_new_session=True)
        try:
            server.wait(timeout=65)
            assert (home/"passed").exists(), "Private mouse test failed"
        finally:
            stop(server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--platform", choices=["wayland", "xcb"], default="wayland")
    parser.add_argument("--saved", action="store_true")
    parser.add_argument("--driver", type=Path, help="wheel-input.c built with libei")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.saved)
    elif args.driver:
        run(args)
    else:
        parser.error("--driver is required")
