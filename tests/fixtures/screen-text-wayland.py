"""Select actual text, a QR code and an empty region in a private Spectacle session."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from screen_selection_session import run_selection_test
from tools.test import stop
from wayland_pointer import Pointer


def exercise(installed):
    import dbus
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QWidget
    from tests.test_resume import r

    assert os.environ["WAYLAND_DISPLAY"] == "monet-screen-text"
    data = Path("/usr/share") if installed else ROOT / "linux/share"
    sys.path.insert(0, str(data / "monet/utilities"))
    from window import Window
    executable = Path("/usr/libexec/monet-utilities") if installed else ROOT / "linux/libexec/monet-utilities"
    app = QApplication([])
    def wait(check, why):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if check():
                return
            QTest.qWait(25)
        raise AssertionError(why)

    target = QWidget()
    target.setStyleSheet("QWidget { background: white; color: black; }")
    target.setWindowTitle("Monet reading sample")
    target.setFixedSize(740, 450)
    paragraph = QLabel("Meet at noon on Friday", target)
    paragraph.setStyleSheet("font: 30px 'DejaVu Sans'")
    paragraph.setGeometry(30, 40, 620, 60)
    code = QLabel(target)
    code.setGeometry(25, 135, 210, 210)
    code.setPixmap(QPixmap(str(Path(__file__).with_name("screen-text-qr.png"))).scaled(200, 200))
    editor = QPlainTextEdit(target)
    editor.setGeometry(260, 180, 330, 80)
    target.show()
    editor.setFocus()
    QTest.qWait(350)
    origin = r.kwin_script("reply(rect(windows().find(w=>w.caption==='Monet reading sample').clientGeometry))")
    pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-screen-text", version=4)
    def overlay():
        return r.kwin_script("reply(workspace.windowList().some(w=>String(w.resourceClass).toLowerCase().includes('spectacle') && !w.deleted))")

    def select(region=None):
        wait(overlay, "Spectacle selection did not appear")
        QTest.qWait(220)
        if region:
            x, y, right, bottom = region
            pointer.point(origin["x"]+x, origin["y"]+y)
            QTest.qWait(45)
            pointer.button(True)
            pointer.point(origin["x"]+right, origin["y"]+bottom)
            QTest.qWait(70)
            pointer.button(False)
        else:
            pointer.key(1, True)
            pointer.key(1, False)
        wait(lambda: not overlay(), "Spectacle did not dismiss the selection")

    def paste(expected):
        editor.clear()
        pointer.key(29, True)
        pointer.key(47, True)
        pointer.key(47, False)
        pointer.key(29, False)
        wait(lambda: editor.toPlainText() == expected, "Pasted content did not match")

    text_area = (12, 20, 620, 114)
    qr_area = (10, 123, 244, 365)
    blank_area = (460, 285, 680, 390)
    qr_value = "  Friday\n12:30  "
    # Use the same automatic file/clipboard preferences as the Monet profile.
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "spectaclerc"
    config.write_text("[General]\nclipboardGroup=PostScreenshotCopyImage\nautoSaveImage=true\n")
    copied_images = []
    def clipboard_changed():
        mime = app.clipboard().mimeData()
        if mime and mime.hasImage():
            copied_images.append(True)
    app.clipboard().dataChanged.connect(clipboard_changed)
    bus = dbus.SessionBus()
    warm = subprocess.Popen(["spectacle", "--dbus"])
    wait(lambda: bus.name_has_owner("org.kde.Spectacle"), "Prewarmed screenshot service did not start")
    warm_owner = bus.get_name_owner("org.kde.Spectacle")
    external = subprocess.Popen([sys.executable, executable, "ocr"], start_new_session=True)
    try:
        select(text_area)
        wait(lambda: app.clipboard().text() == paragraph.text(), "Global selection did not copy the sentence")
        paste(paragraph.text())
        receiver = bus.get_object("org.monet.Utilities", "/Utilities")
        receiver.OpenTool("ocr", "", dbus_interface="org.monet.Utilities")
        select(qr_area)
        wait(lambda: app.clipboard().text() == qr_value, "QR whitespace was lost")
        paste(qr_value)
        receiver.OpenTool("ocr", "", dbus_interface="org.monet.Utilities")
        select()
        paste(qr_value)
        external.terminate()
        external.wait(timeout=3)
    finally:
        if external.poll() is None:
            stop(external)
    paste(qr_value)

    catalog = Window("/usr/libexec")
    catalog.Open(["tools"])
    QTest.qWait(250)
    catalog.run_tool("ocr")
    page = catalog.pages["ocr"]
    assert not catalog.isVisible()
    select(text_area)
    wait(lambda: catalog.isVisible() and not page.busy, "Catalog did not return")
    assert page.editor.toPlainText() == paragraph.text()
    page.editor.setPlainText("Edited\ntext")
    page.copy_button.click()
    wait(lambda: app.clipboard().text() == "Edited\ntext" and not page.busy, "Edits did not copy")
    page.pick(True)
    select(blank_area)
    wait(lambda: not page.busy, "Recognition did not finish")
    assert page.editor.toPlainText() == app.clipboard().text() == "Edited\ntext"
    assert catalog.isVisible()
    page.pick(True)
    select()
    wait(lambda: catalog.isVisible() and not page.busy, "Cancel did not restore Utilities")
    assert page.editor.toPlainText() == app.clipboard().text() == "Edited\ntext"
    from actions import tr
    assert catalog.status.currentMessage() != tr("Couldn’t read the selected area.")
    catalog.save_favorites(["ocr"])
    catalog.hide()
    catalog.Open(["quick-panel"])
    panel = catalog.quick_panel
    panel.grid.setCurrentRow(panel.keys.index("ocr"))
    QTest.keyClick(panel.grid, Qt.Key_Return)
    select(qr_area)
    wait(lambda: not page.busy and app.clipboard().text() == qr_value, "Quick Panel did not copy the code")
    assert not catalog.isVisible() and not panel.isVisible()
    assert bus.get_name_owner("org.kde.Spectacle") == warm_owner
    assert not copied_images, "Text capture wrote an intermediate screenshot to the clipboard"
    assert not list((Path.home() / "Pictures").rglob("*.png"))
    warm.terminate()
    warm.wait(timeout=3)
    (Path.home() / "passed").touch()
    print("Verified typed text, QR whitespace, region selection, paste into the original app, editing, blank results and Escape.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        exercise(args.installed)
    else:
        run_selection_test(Path(__file__), args.installed, "monet-screen-text")
