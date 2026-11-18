"""Check the compositor's actual states on a private virtual Wayland output."""
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


def worker(output, kind):
    from PySide6.QtCore import QPoint, QPointF, QUrl, Qt
    from PySide6.QtGui import QGuiApplication, QWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from tests.test_settings_navigation import SettingsNavigation

    def until(condition, label):
        deadline = time.monotonic() + 8
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(20)
        assert condition(), label

    from tests.test_store_navigation import StoreNavigation
    Case = StoreNavigation if kind == "store" else SettingsNavigation
    Case.setUpClass()
    app_id = "monet-controls-fixture-" + kind
    QGuiApplication.instance().setDesktopFileName(app_id)
    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / (app_id + ".desktop")).write_text("[Desktop Entry]\nType=Application\nName=Controls fixture\nExec=/usr/bin/false\n")
    case = Case("test_opening_again_restores_maximized_and_preserves_the_requested_page" if kind == "store"
                else "test_reopening_settings_restores_its_maximized_state")
    records = []
    restoration_sizes = []
    restoring = False
    try:
        case.setUp()
        window = case.window
        def resized(*args):
            if restoring:
                restoration_sizes.append([window.width(), window.height()])
        window.widthChanged.connect(resized)
        window.heightChanged.connect(resized)
        observer = QQmlApplicationEngine()
        observer.loadData(b'''import QtQuick
import org.kde.taskmanager as TaskManager
Window {
    visible: false
    property TaskManager.TasksModel tasks: TaskManager.TasksModel { groupMode: TaskManager.TasksModel.GroupDisabled }
    function snapshot() {
        let result = [];
        for (let row = 0; row < tasks.rowCount(); row++) {
            const index = tasks.index(row, 0);
            const frame = tasks.data(index, TaskManager.AbstractTasksModel.Geometry);
            if (tasks.data(index, TaskManager.AbstractTasksModel.IsWindow)) result.push({
                id: tasks.data(index, TaskManager.AbstractTasksModel.StorageId),
                frame: [frame.x, frame.y, frame.width, frame.height],
                minimized: tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized),
                maximized: tasks.data(index, TaskManager.AbstractTasksModel.IsMaximized),
                fullscreen: tasks.data(index, TaskManager.AbstractTasksModel.IsFullScreen)});
        }
        return result;
    }
}''', QUrl.fromLocalFile(str(output / "observer.qml")))
        assert observer.rootObjects(), "The native observer did not load"
        model = observer.rootObjects()[0]

        def state():
            matches = [item for item in model.snapshot().toVariant() if item["id"] == app_id + ".desktop"]
            return matches[0] if len(matches) == 1 else {}

        until(lambda: state() and window.isExposed(), kind + " did not map")
        def maximize():
            button = case.item("windowMaximize")
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                             button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint())
        screen = window.screen().availableGeometry()
        for name, show, expected in (("windowed", window.showNormal, QWindow.Windowed),
                                     ("maximized", maximize, QWindow.Maximized),
                                     ("fullscreen", window.showFullScreen, QWindow.FullScreen)):
            def restored():
                found = state()
                return (found and not found["minimized"] and found["maximized"] == (name == "maximized")
                        and found["fullscreen"] == (name == "fullscreen") and window.visibility() == expected)
            show()
            until(restored, "Initial " + name + ": " + str(state()))
            if name == "maximized":
                until(lambda: state().get("frame") == [screen.x(), screen.y(), screen.width(), screen.height()],
                      "Maximized frame did not fill the available screen: " + str(state()))
            window.showMinimized()
            until(lambda: state().get("minimized") and not window.isExposed(), "Minimize " + name)
            restoration_sizes.clear()
            before_size = [window.width(), window.height()]
            restoring = True
            if kind == "store": case.shop.wanted.emit("games")
            else: case.helper.wanted.emit("sound")
            until(restored, "Restore " + name + ": " + str(state()))
            QTest.qWait(150)
            restoring = False
            assert restored(), "Late configure changed " + name
            if name != "windowed":
                assert all(size == before_size for size in restoration_sizes), "Restore briefly shrank " + name + ": " + str(restoration_sizes)
            records.append(dict(mode=name, compositor=state(), page=window.property("section" if kind == "store" else "page"),
                                available=[window.screen().availableGeometry().width(), window.screen().availableGeometry().height()],
                                size=[window.width(), window.height()]))
            assert window.property("section" if kind == "store" else "page") == ("games" if kind == "store" else "sound")
            if name == "maximized":
                assert state()["frame"] == [screen.x(), screen.y(), screen.width(), screen.height()], str(state())
        window.showNormal()
        until(lambda: state() and not state().get("maximized") and not state().get("fullscreen"), "Leave fullscreen before corner click")
        window.showMaximized()
        screen = window.screen().availableGeometry()
        until(lambda: state().get("maximized") and not state().get("fullscreen")
              and state().get("frame", [])[2:] == [screen.width(), screen.height()]
              and window.width() == screen.width() and window.height() == screen.height(), "Maximize before corner click")
        close = case.item("windowClose")
        until(lambda: abs(close.mapToScene(QPointF(close.width(), 0)).x() - window.width()) < 0.5
              and abs(close.mapToScene(QPointF(0, 0)).y()) < 0.5, "Lay out the screen-edge control")
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(window.width() - 1, 0))
        until(lambda: not window.isVisible() and not state(), "Close at the top-right corner")
        result = dict(ok=True, records=records, corner_close=True,
                      scope="Actual KWin states on a private virtual output, CPU rendering; no host session or physical input")
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        if hasattr(case, "window"):
            case.tearDown()
        case.doCleanups()
        Case.tearDownClass()
    return 0


def parent(output, kind):
    from tools.test import private_session, stop
    output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        folder = Path(env["HOME"]).parent
        binary = folder / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE",
                   WAYLAND_DISPLAY="monet-controls-fixture", KWIN_COMPOSE="O2", LIBGL_ALWAYS_SOFTWARE="1",
                   QT_FORCE_STDERR_LOGGING="1")
        for key in ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_AUTO_SCREEN_SCALE_FACTOR"):
            env.pop(key, None)
        script = folder / "session.sh"
        script.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, str(Path(__file__).resolve()), "worker", str(output), kind]) + "\n")
        script.chmod(0o700)
        with (output / "kwin.log").open("w") as log:
            server = subprocess.Popen([str(binary), "--virtual", "--output-count", "1", "--width", "1280", "--height", "1600" if kind == "store" else "800",
                                       "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities", "--socket", "monet-controls-fixture",
                                       "--exit-with-session", str(script)], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = server.wait(timeout=90)
            finally:
                stop(server)
        assert code == 0, "KWin/fixture exited " + str(code)
        assert json.loads((output / "result.json").read_text())["ok"]


if __name__ == "__main__":
    if sys.argv[1] == "worker":
        sys.exit(worker(Path(sys.argv[2]), sys.argv[3]))
    parent(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "settings")
