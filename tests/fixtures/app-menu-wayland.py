"""Check native accessibility actions in overlapping documents in a disposable compositor."""
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


def wait(check):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError("Timed out waiting for " + check.__name__)


def client():
    from PySide6.QtWidgets import QApplication, QMainWindow
    app = QApplication([])
    windows = []
    for name in ("First", "Second"):
        window = QMainWindow()
        windows.append(window)
        window.setWindowTitle("Document  " + name)
        bar = window.menuBar()
        bar.setNativeMenuBar(False)
        for group in ("File", "Edit"):
            action = bar.addMenu(group).addMenu("Selection").addAction("Mark")
            def select(checked, label=(name, group), item=action):
                with (Path.home()/"events").open("a") as f:
                    print(*label, file=f)
                item.setEnabled(False)
            action.triggered.connect(select)
        window.resize(320, 240)
        window.show()
    app.exec()


def exercise():
    import dbus
    from menu_commands import MenuSearch, target_window
    from tests.test_resume import r
    bus = dbus.SessionBus()
    processes = []
    def start(*cmd):
        processes.append(subprocess.Popen(cmd, start_new_session=True))
    try:
        start("/usr/libexec/at-spi-bus-launcher", "--launch-immediately")
        wait(lambda: bus.name_has_owner("org.a11y.Bus"))
        os.environ["AT_SPI_BUS_ADDRESS"] = str(bus.get_object("org.a11y.Bus", "/org/a11y/bus").GetAddress(dbus_interface="org.a11y.Bus"))
        start("/usr/libexec/at-spi2-registryd")
        registry = dbus.bus.BusConnection(os.environ["AT_SPI_BUS_ADDRESS"])
        wait(lambda: registry.name_has_owner("org.a11y.atspi.Registry"))
        assert bus.request_name("org.monet.ToolSearch") == 1
        start(sys.executable, __file__, "--client")
        wait(lambda: target_window(bus).get("title") == "Document Second")
        search = MenuSearch(bus)
        rows = wait(lambda: search.matches("mark"))
        assert len(rows) == 2 and rows[0][0] != rows[1][0]
        assert not target_window(dbus.SessionBus(private=True))
        assert search.run(rows[0][0])
        events = Path.home()/"events"
        wait(lambda: events.exists() and events.read_text().splitlines() == ["Second File"])
        assert not search.run(rows[0][0]), "The selected action was disabled"
        assert r.kwin_script('workspace.activeWindow=workspace.windowList().find(w=>w.caption==="Document First");reply(true)')
        assert not search.run(rows[1][0]), "The original document lost focus"
        other, = search.matches("edit mark")
        assert search.run(other[0])
        wait(lambda: events.read_text().splitlines() == ["Second File", "First Edit"])
        (Path.home()/"passed").touch()
    finally:
        for process in reversed(processes):
            stop(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--client", action="store_true")
    args = parser.parse_args()
    if args.worker or args.client:
        assert os.environ["WAYLAND_DISPLAY"] == "menu-test" and Path.home().parent.name.startswith("monet-tests-")
        return client() if args.client else exercise()
    with private_session() as env:
        home = Path(env["HOME"])
        env.update(WAYLAND_DISPLAY="menu-test", QT_QPA_PLATFORM="wayland", XDG_CURRENT_DESKTOP="KDE",
                   XDG_SESSION_TYPE="wayland", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1", QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")
        if args.plugin:
            plugin = home/"plugins/kwin/plugins/monet_app_menu.so"
            plugin.parent.mkdir(parents=True)
            shutil.copy(args.plugin, plugin)
            env["QT_PLUGIN_PATH"] = str(home/"plugins")
        kwin = home/"kwin_wayland"
        shutil.copy(shutil.which("kwin_wayland"), kwin)
        worker = home/"exercise"
        worker.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "--worker"]) + "\n")
        worker.chmod(0o700)
        process = subprocess.Popen([kwin, "--virtual", "--socket", "menu-test", "--no-lockscreen",
                                    "--no-kactivities", "--exit-with-session", worker], env=env, start_new_session=True)
        try:
            assert process.wait(timeout=45) == 0 and (home/"passed").exists()
        finally:
            stop(process)


if __name__ == "__main__":
    main()
