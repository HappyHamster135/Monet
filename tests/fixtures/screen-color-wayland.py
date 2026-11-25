"""Sample a known rendered pixel and paste in a private KWin session with wl-clipboard."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import stop
from screen_selection_session import run_selection_test
from wayland_pointer import Pointer


def exercise(installed):
    import dbus
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QWidget
    from tests.test_resume import r

    assert os.environ["WAYLAND_DISPLAY"] == "monet-screen-colors"
    data = Path("/usr/share") if installed else ROOT / "linux/share"
    sys.path.insert(0, str(data / "monet/utilities"))
    from window import Window
    executable = Path("/usr/libexec/monet-utilities") if installed else ROOT / "linux/libexec/monet-utilities"
    app = QApplication([])
    def wait(check, why):
        deadline = time.monotonic() + 6
        while not check() and time.monotonic() < deadline:
            QTest.qWait(12)
        assert check(), why

    target = QWidget()
    target.setWindowTitle("Monet sample")
    target.setFixedSize(720, 450)
    target.setAutoFillBackground(True)
    palette = target.palette()
    palette.setColor(QPalette.Window, QColor("#336699"))
    target.setPalette(palette)
    editor = QLineEdit(target)
    editor.setGeometry(10, 10, 350, 50)
    target.show()
    QTest.qWait(400)
    geometry = r.kwin_script("reply(rect(windows().find(w=>w.caption==='Monet sample').clientGeometry))")
    pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-screen-colors", version=4)
    bus = dbus.SessionBus()
    effects = bus.get_object("org.kde.KWin", "/Effects")
    def picking():
        return "colorpicker" in effects.Get("org.kde.kwin.Effects", "activeEffects", dbus_interface=dbus.PROPERTIES_IFACE)

    def sample():
        wait(picking, "KWin did not start sampling")
        pointer.point(geometry["x"] + 100, geometry["y"] + 180)
        QTest.qWait(40)
        pointer.click()
        wait(lambda: not picking(), "KWin did not finish sampling")

    def paste(text):
        editor.setFocus()
        editor.clear()
        pointer.key(29, True)
        pointer.key(47, True)
        pointer.key(47, False)
        pointer.key(29, False)
        wait(lambda: editor.text() == text, f"Expected the client to paste {text}")

    def clipboard():
        return subprocess.check_output(["wl-paste", "--no-newline"], text=True, timeout=2)

    external = subprocess.Popen([sys.executable, executable, "color"], start_new_session=True)
    try:
        wait(picking, "Desktop action did not start")
        assert r.kwin_script("reply(windows().map(w=>w.caption))") == ["Monet sample"]
        sample()
        wait(lambda: app.clipboard().text() == "#336699", "First sample missing")
        paste("#336699")
        receiver = bus.get_object("org.monet.Utilities", "/Utilities")
        receiver.OpenTool("color", "", dbus_interface="org.monet.Utilities")
        wait(picking, "Tool search did not start the picker")
        pointer.key(1, True)
        pointer.key(1, False)
        wait(lambda: not picking(), "Escape did not cancel")
        paste("#336699")
        external.terminate()
        external.wait(timeout=3)
        paste("#336699")
    finally:
        if external.poll() is None:
            stop(external)

    catalog = Window("/usr/libexec")
    catalog.Open(["tools"])
    QTest.qWait(280)
    catalog.run_tool("color")
    assert not catalog.isVisible()
    sample()
    page = catalog.pages["color"]
    wait(lambda: catalog.isVisible() and not page.busy, "Catalog did not restore after sampling")
    assert catalog.stack.currentWidget() is page and page.value.text() == "#336699"
    for form, value in (("rgb", "rgb(51, 102, 153)"), ("hsl", "hsl(210, 50%, 40%)"),
                        ("bare", "336699"), ("swiftui", "Color(red: 0.2, green: 0.4, blue: 0.6)")):
        page.format.setCurrentIndex(page.format.findData(form))
        page.copy_button.click()
        wait(lambda: not page.busy, "Copy did not complete")
        assert page.value.text() == clipboard() == value

    catalog.hide()
    catalog.Open(["quick-panel"])
    panel = catalog.quick_panel
    panel.grid.setCurrentRow(panel.keys.index("color"))
    QTest.keyClick(panel.grid, Qt.Key_Return)
    sample()
    wait(lambda: not page.busy, "Favorite did not complete")
    assert not panel.isVisible() and not catalog.isVisible()
    assert clipboard() == value

    palette.setColor(QPalette.Window, QColor("#cc6633"))
    target.setPalette(palette)
    QTest.qWait(100)
    restarted = subprocess.Popen([sys.executable, executable, "color"], start_new_session=True)
    try:
        sample()
        wait(lambda: clipboard() == "Color(red: 0.8, green: 0.4, blue: 0.2)", "Format did not persist")
    finally:
        stop(restarted)
    (Path.home() / "passed").touch()
    print("Verified screenshot sampling, paste after exit, Escape, catalog, favorites and saved formats.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        exercise(args.installed)
    else:
        run_selection_test(Path(__file__), args.installed, "monet-screen-colors")
