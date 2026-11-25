"""Click the wheel without moving the pointer after its first Wayland frame."""
import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from screen_selection_session import run_selection_test
from wayland_pointer import Pointer


def exercise(installed):
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMenu, QPushButton
    from tests.test_resume import r
    base = Path("/usr/share") if installed else ROOT / "linux/share"
    sys.path.insert(0, str(base / "monet/utilities"))
    from favorites_wheel import FavoritesWheel

    assert Path.home().parent.name.startswith("monet-tests-") and os.environ["WAYLAND_DISPLAY"] == "monet-wheel-click"
    app = QApplication([])
    app.setDesktopFileName("monet-utilities")
    outside = QPushButton("Other window")
    outside.show()
    pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / os.environ["WAYLAND_DISPLAY"])
    wheel = FavoritesWheel()
    wheel.profile_names = {"": "Quick Panel favorites"}
    positions = [(245, 260), (650, 300), (330, 225), (610, 245)]
    for index, (x, y) in enumerate(positions * 2):
        pointer.point(x, y)
        QTest.qWait(45)
        wheel.present(["shelf", "notes", "snippets", "ports"], 560)
        assert app.desktopFileName() == "monet-utilities"

        def placed():
            return r.kwin_script("""
const w = workspace.windowList().find(w => w.resourceClass === "org.monet.FavoritesWheel");
reply(w ? {x:w.frameGeometry.x+w.width/2, y:w.frameGeometry.y+w.height/2,
           task:w.skipTaskbar, switcher:w.skipSwitcher, active:w.active} : null);
""")

        deadline = time.monotonic() + 4
        frame = placed()
        while (not frame or not frame["active"]) and time.monotonic() < deadline:
            QTest.qWait(15)
            frame = placed()
        assert frame and frame["task"] and frame["switcher"], frame
        assert abs(frame["x"]-x) <= 1 and abs(frame["y"]-y) <= 1, frame
        if index >= len(positions):
            QTest.qWait(350)
            assert placed() == frame, (frame, placed())
        menus = []
        # The click enters the native QMenu event loop.
        def close_menu():
            if isinstance(app.activePopupWidget(), QMenu):
                menus.append(app.activePopupWidget().actions()[0].text())
                app.activePopupWidget().close()
        timer = QTimer(interval=20)
        timer.timeout.connect(close_menu)
        timer.start()
        pointer.click()
        QTest.qWait(150)
        timer.stop()
        assert menus == ["Quick Panel favorites"], (x, y, menus)
        wheel.hide()
        QTest.qWait(70)
    print("Verified eight first clicks at alternating pointer positions, stable placement and the original app identity.", flush=True)
    (Path.home() / "passed").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.worker:
        exercise(args.installed)
    else:
        rules = ROOT / "linux/share/monet/wheel-placement/kwinrulesrc"
        if args.installed:
            rules = next(p for d in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":")
                         if (p := Path(d) / "kwinrulesrc").is_file() and
                         "[org.monet.FavoritesWheel]" in p.read_text())
        run_selection_test(Path(__file__), args.installed, "monet-wheel-click", kwin_rules=rules)
