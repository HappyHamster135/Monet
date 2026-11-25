"""Exercise visible cleaning on two private outputs with actual pointer and key events."""
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


def run(args):
    with private_session() as env:
        env.update(WAYLAND_DISPLAY="monet-cleaning-test", QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", LANGUAGE="en", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1")
        home = Path(env["HOME"])
        if args.plugin:
            plugin = home/"plugins/kwin/plugins/monet_cleaning.so"
            plugin.parent.mkdir(parents=True)
            shutil.copy2(args.plugin, plugin)
            env["QT_PLUGIN_PATH"] = str(home/"plugins")
        kwin = home/"kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), kwin)
        kwin.chmod(0o700)
        cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "--private"]
        if args.installed:
            cmd.append("--installed")
        script = home/"session"
        script.write_text("#!/bin/sh\nexec " + shlex.join(cmd))
        script.chmod(0o700)
        proc = subprocess.Popen([kwin, "--virtual", "--width", "960", "--height", "660", "--output-count", "2",
            "--socket", env["WAYLAND_DISPLAY"], "--no-kactivities", "--exit-with-session", script],
            env=env, start_new_session=True)
        try:
            proc.wait(timeout=115)
            assert (home/"passed").exists(), "Cleaning session check failed"
        finally:
            stop(proc)


def exercise(args):
    import dbus
    from PySide6.QtCore import QObject, QTimer, Slot
    from PySide6.QtDBus import QDBusConnection
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox, QWidget
    from tests.test_resume import r
    sys.path.insert(0, str(Path("/usr/share/monet/utilities") if args.installed else ROOT/"linux/share/monet/utilities"))
    from window import Window

    assert os.environ["WAYLAND_DISPLAY"] == "monet-cleaning-test" and str(Path.home()).startswith("/tmp/monet-tests-")
    app = QApplication([])
    qtbus = QDBusConnection.sessionBus()
    assert qtbus.registerService("org.monet.Utilities")
    bus = dbus.SessionBus()
    name, path, interface = "org.kde.KWin", "/org/monet/Cleaning", "org.monet.Cleaning"
    plugins = bus.get_object(name, "/Plugins")
    loaded = dbus.Interface(plugins, "org.freedesktop.DBus.Properties").Get("org.kde.KWin.Plugins", "LoadedPlugins")
    assert "monet_cleaning" not in loaded, "Cleaning must stay off the desktop startup path"
    class Counter(QObject):
        value = 0
        @Slot()
        def hit(self):
            self.value += 1
    counter = Counter()
    assert qtbus.registerObject("/CleaningProbe", "org.monet.CleaningProbe", counter, QDBusConnection.ExportAllSlots)
    shortcut = Path.home()/"cleaning-shortcut.js"
    shortcut.write_text('registerShortcut("MonetCleaningTest", "Cleaning fixture", "Ctrl+Alt+J", '
                        '() => callDBus("org.monet.Utilities","/CleaningProbe","org.monet.CleaningProbe","hit"));')
    ident = bus.call_blocking(name, "/Scripting", "org.kde.kwin.Scripting", "loadScript", "ss",
                              (str(shortcut), "monet-cleaning-probe"))
    assert ident >= 0
    dbus.Interface(bus.get_object(name, f"/Scripting/Script{ident}"), "org.kde.kwin.Script").run()
    window = Window("/usr/libexec")

    class Target(QWidget):
        color = "#e5ae21"
        keys = ""
        clicks = 0
        def keyPressEvent(self, event):
            self.keys += event.text()
        def mousePressEvent(self, event):
            self.clicks += 1
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(self.color))
            painter.end()

    target = Target()
    target.setWindowTitle("Monet private cleaning target")
    target.resize(460, 330)
    target.show()
    def wait(check, label, timeout=5):
        until = time.monotonic()+timeout
        while time.monotonic() < until:
            value = check()
            if value:
                return value
            QTest.qWait(35)
        raise AssertionError((label, window.status.currentMessage(), target.keys, target.clicks))
    target_script = 'const w=workspace.stackingOrder.find(w=>w.caption==="Monet private cleaning target");'
    wait(lambda: r.kwin_script(target_script+'reply(!!w)'), "target mapped")
    r.kwin_script(target_script+'w.frameGeometry={x:20,y:60,width:460,height:330};workspace.activeWindow=w;reply(true)')
    wait(lambda: r.kwin_script(target_script+'reply(w.active)'), "target focused")
    QTest.qWait(350)
    ptr = Pointer(Path(os.environ["XDG_RUNTIME_DIR"])/os.environ["WAYLAND_DISPLAY"], version=4)
    def key(code):
        ptr.key(code, True)
        QTest.qWait(25)
        ptr.key(code, False)
        QTest.qWait(30)
    def chord():
        ptr.key(29, True)
        ptr.key(56, True)
        key(36)
        ptr.key(56, False)
        ptr.key(29, False)
        QTest.qWait(100)
    def cards():
        return r.kwin_script('reply(workspace.stackingOrder.filter(w=>w.caption==="Cleaning mode" && !w.deleted).map(w=>rect(w.frameGeometry)))')

    def start(mode="visible"):
        def choose():
            dialog = app.activeModalWidget()
            display = dialog.findChild(QComboBox, "cleaningDisplay")
            display.setCurrentIndex(display.findData(mode))
            times = dialog.findChild(QComboBox)
            times.setCurrentIndex(times.findData(30))
            box = dialog.findChild(QDialogButtonBox)
            next(b for b in box.buttons() if box.buttonRole(b) == QDialogButtonBox.AcceptRole).click()
        QTimer.singleShot(0, choose)
        window.run_tool("lock")
        wait(lambda: len(cards()) == 2, "cleaning cards on both outputs")
        QTest.qWait(140)

    ptr.point(220, 215)
    QTest.qWait(140)
    ptr.click()
    key(30)  # A
    wait(lambda: target.keys == "a" and target.clicks == 1, "ordinary input")
    chord()
    wait(lambda: counter.value == 1, "real desktop shortcut works before cleaning")
    start()
    other = dbus.Interface(bus.get_object(name, path), interface)
    ptr.point(200, 210)
    ptr.click()
    chord()
    assert counter.value == 1
    key(48)  # B
    assert target.keys == "a" and target.clicks == 1
    key(58)  # Wiping Caps Lock must not change typing after the timer.
    target.color = "#16834b"
    target.update()
    QTest.qWait(180)
    # Screenshot the private outputs just as a normal screen capture would.
    path_png = Path.home()/"visible.png"
    subprocess.run(["spectacle", "--new-instance", "-b", "-n", "-f", "-o", str(path_png)], check=True, timeout=12)
    image = QImage(str(path_png))
    assert not image.isNull() and image.pixelColor(220, 215).name() == "#16834b"
    xs, ys = [], []
    for rect in cards():
        if rect["x"] < 960:
            continue
        for y in range(rect["y"], rect["y"]+rect["height"], 2):
            for x in range(rect["x"], rect["x"]+rect["width"], 2):
                if image.pixelColor(x, y).name() == "#30685b":
                    xs.append(x)
                    ys.append(y)
    assert xs, ("visible button on second display", cards(), image.size())
    pos = ((min(xs)+max(xs))//2, (min(ys)+max(ys))//2)
    if os.getenv("MONET_CLEANING_QA_DIR"):
        image.save(str(Path(os.environ["MONET_CLEANING_QA_DIR"])/"visible.png"))
    ptr.point(*pos)
    ptr.button(True)
    ptr.point(200, 210)
    ptr.button(False)
    QTest.qWait(150)
    assert len(cards()) == 2 and target.clicks == 1
    ptr.point(*pos)
    QTest.qWait(100)
    ptr.click()
    wait(lambda: not cards(), "finish button")
    ptr.point(220, 215)
    QTest.qWait(140)
    ptr.click()
    assert not other.Begin(dbus.Int32(30), False), "Only the Utilities owner can start a cleaning session"
    chord()
    wait(lambda: counter.value == 2, "desktop shortcut restored")
    key(46)  # C
    wait(lambda: target.keys == "ac" and target.clicks == 2, "pointer exit restores input")

    start()
    outputs = json.loads(subprocess.check_output(["kscreen-doctor", "-j"], timeout=5))["outputs"]
    second = max(outputs, key=lambda o: o["pos"]["x"])
    output = "output." + str(second["id"])
    subprocess.run(["kscreen-doctor", output+".disable"], check=True, timeout=5)
    wait(lambda: len(cards()) == 1, "cleaning follows display removal")
    subprocess.run(["kscreen-doctor", output+".enable"], check=True, timeout=5)
    wait(lambda: len(cards()) == 2, "cleaning follows display reconnection")
    for _ in range(3):
        key(1)
    key(30)
    for _ in range(4):
        key(1)
    assert len(cards()) == 2 and target.keys == "ac"
    key(1)
    wait(lambda: not cards(), "five deliberate Esc presses")
    key(32)
    wait(lambda: target.keys == "acd", "keyboard exit restores input")

    start()
    ptr.point(220, 215)
    ptr.button(True)
    start_time = time.monotonic()
    while time.monotonic()-start_time < 29:
        QTest.qWait(400)
    wait(lambda: not cards(), "timed exit even when a button is held", 4)
    ptr.button(False)
    ptr.click()
    key(18)
    wait(lambda: target.keys == "acde" and target.clicks == 3, "normal input after timeout")

    start("dark")
    path_png = Path.home()/"blackout.png"
    subprocess.run(["spectacle", "--new-instance", "-b", "-n", "-f", "-o", str(path_png)], check=True, timeout=12)
    dark = QImage(str(path_png))
    assert all(dark.pixelColor(x, 215).name() == "#000000" for x in (220, 1200))
    assert not dbus.Interface(bus.get_object("org.freedesktop.ScreenSaver", "/ScreenSaver"),
                              "org.freedesktop.ScreenSaver").GetActive()
    assert qtbus.unregisterService("org.monet.Utilities")
    wait(lambda: not cards(), "owner disappearance")
    key(33)
    wait(lambda: target.keys == "acdef", "input when Utilities exits")
    assert qtbus.registerService("org.monet.Utilities")
    start()
    locker = dbus.Interface(bus.get_object("org.freedesktop.ScreenSaver", "/ScreenSaver"), "org.freedesktop.ScreenSaver")
    ptr.key(48, True)
    ptr.button(True)
    QTest.qWait(100)
    locker.Lock(timeout=8)
    wait(lambda: locker.GetActive() and not cards(), "real lock replaces visible cleaning")
    ptr.key(48, False)
    ptr.button(False)
    for _ in range(5):
        key(1)
    assert locker.GetActive() and target.keys == "acdef", "the cleaning exit cannot unlock Plasma"
    (Path.home()/"passed").touch()
    print("Verified two visible outputs, input isolation, UI and keyboard exits, timed recovery and owner loss.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    (exercise if args.private else run)(args)
