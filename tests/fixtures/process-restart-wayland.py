"""Restart a fixture application through the Utilities UI on an isolated KWin display."""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop

APP_ID = "org.monet.ProcessRestartFixture"
DISPLAY = "monet-process-restart-test"


def log(event):
    with (Path(os.environ["HOME"]) / "events").open("a") as output:
        print(json.dumps([event, os.getpid(), time.monotonic()]), file=output)


def fixture_app():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication([])
    app.setDesktopFileName(APP_ID)
    window = QWidget()
    window.setWindowTitle("Disposable restart target")
    window.show()
    clock = QTimer()
    clock.timeout.connect(lambda: None)
    clock.start(40)
    def quit_later(*_):
        log("quitting")
        QTimer.singleShot(450, app.quit)
    signal.signal(signal.SIGTERM, quit_later)
    QTimer.singleShot(30000, app.quit)
    app.aboutToQuit.connect(lambda: log("exited"))
    log("started")
    return app.exec()


def exercise():
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    modules = os.getenv("MONET_UTILITIES_MODULES", str(ROOT / "linux/share/monet/utilities"))
    sys.path.insert(0, modules)
    from window import Window
    from local_ports import process

    app = QApplication([])
    helpers = Path("/usr/libexec") if os.getenv("MONET_UTILITIES_MODULES") else ROOT / "linux/libexec"
    window = Window(helpers)
    window.show()
    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    binary = Path(sys.executable)
    apps.joinpath(APP_ID + ".desktop").write_text("[Desktop Entry]\nType=Application\nName=Restart fixture\n"
        f'Exec="{binary}" "{Path(__file__).resolve()}" app\nTerminal=false\n')
    first = subprocess.Popen([binary, __file__, "app"])
    events = Path(os.environ["HOME"]) / "events"
    def records():
        return [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    def wait(test, why):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = test()
            if result:
                return result
            QTest.qWait(30)
        raise AssertionError((why, records(), window.status.currentMessage()))
    try:
        wait(records, "first start")
        QTest.qWait(450)
        window.search.setText("End or restart a process")
        assert window.catalog.count() == 1
        window.open_selected()
        page = window.pages["process-control"]
        wait(lambda: not page.loading, "process list")
        page.filter.setText(str(first.pid))
        row, = [i for i in range(page.model.rowCount()) if page.model.index(i, 1).data(Qt.DisplayRole) == first.pid]
        page.rows.selectRow(row)
        page.manage.click()
        wait(lambda: page.detail and page.detail.restart.isEnabled(), "matching desktop entry")
        def approve():
            box = QApplication.activeModalWidget()
            assert isinstance(box, QMessageBox) and box.defaultButton() is box.button(QMessageBox.Cancel)
            next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.DestructiveRole).click()
        QTimer.singleShot(25, approve)
        page.detail.restart.click()
        wait(lambda: any(x[0] == "quitting" for x in records()), "quit requested")
        window.close()
        assert not window.isVisible() and page.applying_action
        wait(lambda: not page.applying_action, "request completed after closing Utilities")
        wait(lambda: len([r for r in records() if r[0] == "started"]) == 2, "app relaunched")
        assert first.wait(timeout=2) == 0
        started, quitting, exited, second = records()
        assert [started[0], quitting[0], exited[0], second[0]] == ["started", "quitting", "exited", "started"]
        assert started[1] == exited[1] == first.pid and second[1] != first.pid and second[2] >= exited[2]
        assert process(second[1]) is not None
        print("Verified exact app identity, confirmation, real exit before relaunch, and closing Utilities during restart.", flush=True)
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=4)
        window.close()


def private_display():
    if not Path("/run/.containerenv").exists() or set(os.listdir("/sys/class/net")) != {"lo"}:
        sys.exit("Run this fixture with Podman --network=none and its own PID namespace.")
    with private_session() as env:
        env.update(WAYLAND_DISPLAY=DISPLAY, QT_QPA_PLATFORM="wayland", XDG_CURRENT_DESKTOP="KDE",
                   XDG_SESSION_TYPE="wayland", LANGUAGE="en", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="2")
        home = Path(env["HOME"])
        compositor = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), compositor)
        compositor.chmod(0o700)
        runner = home / "run"
        runner.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "exercise"]))
        runner.chmod(0o700)
        kwin = subprocess.Popen([compositor, "--virtual", "--socket", DISPLAY, "--width", "1024", "--height", "768",
                                 "--no-global-shortcuts", "--no-lockscreen", "--no-kactivities", "--exit-with-session", runner],
                                env=env, start_new_session=True)
        try:
            kwin.wait(timeout=55)
            assert (home / "passed").exists()
        finally:
            stop(kwin)


if __name__ == "__main__":
    if sys.argv[1:] in (["app"], ["exercise"]):
        assert os.environ["WAYLAND_DISPLAY"] == DISPLAY and os.environ["HOME"].startswith("/tmp/monet-tests-")
        if sys.argv[1] == "app":
            sys.exit(fixture_app())
        exercise()
        (Path(os.environ["HOME"]) / "passed").touch()
    else:
        private_display()
