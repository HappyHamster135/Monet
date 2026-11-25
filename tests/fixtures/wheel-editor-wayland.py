"""Build a named wheel through its native editor and move a sector with the pointer."""
import argparse
import os
from pathlib import Path
import sys
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from screen_selection_session import run_selection_test
from wayland_pointer import Pointer


def exercise(installed):
    from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Slot
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QLineEdit, QListWidget
    from tests.test_resume import r
    base = Path("/usr/share") if installed else ROOT / "linux/share"
    sys.path.insert(0, str(base / "monet/utilities"))
    from window import Window
    from wheel_profiles import Entry, open_target, profiles

    home = Path.home()
    assert home.parent.name.startswith("monet-tests-") and os.environ["WAYLAND_DISPLAY"] == "monet-wheel-editor"
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
    app = QApplication([])
    window = Window("/usr/libexec")
    window.Open(["wheel-settings"])
    editor = window.pages["wheel-settings"]

    def wait(check, why):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if check():
                return
            QTest.qWait(25)
        raise AssertionError(why)

    wait(window.isActiveWindow, "active editor")
    errors = []
    def dialog_input(callback, kind):
        def enter():
            dialog = app.activeModalWidget()
            try:
                assert isinstance(dialog, kind), dialog
                QTimer.singleShot(4000, dialog, dialog.reject)
                callback(dialog)
            except BaseException as error:
                errors.append(error)
                if dialog:
                    dialog.reject()
        QTimer.singleShot(100, enter)

    def text(value):
        def enter(dialog):
            dialog.setTextValue(value)
            dialog.accept()
        dialog_input(enter, QInputDialog)

    text("Studio")
    editor.new_profile()
    ident = editor.selector.currentData()
    assert ident
    print("Created a named wheel.", flush=True)
    text("Reading")
    editor.add_item("menu")
    editor.tree.setCurrentItem(editor.root)
    file = home / "A plan & notes.txt"
    file.write_text("Local file fixture.")
    def select_file(dialog):
        line = dialog.findChild(QLineEdit, "fileNameEdit")
        line.setText(str(file))
        QTest.keyClick(line, Qt.Key_Return)
    dialog_input(select_file, QFileDialog)
    editor.add_item("file")
    assert not errors, errors
    assert editor.root.childCount() == 2
    print("Added a submenu and a file.", flush=True)

    coords = r.kwin_script("const w=workspace.activeWindow;reply([w.clientGeometry.x,w.clientGeometry.y]);")
    def row_pos(row):
        pt = editor.tree.viewport().mapTo(window, editor.tree.visualItemRect(row).center())
        return coords[0]+pt.x(), coords[1]+pt.y()
    def move_pointer(source, destination):
        start, end = row_pos(source), row_pos(destination)
        sender = subprocess.Popen([sys.executable, __file__, "--drag", *map(str, (*start, *end))])
        try:
            wait(lambda: sender.poll() is not None, "pointer release")
            assert sender.returncode == 0
        finally:
            if sender.poll() is None:
                sender.kill()
                sender.wait()
    move_pointer(editor.root.child(1), editor.root.child(0))
    wait(lambda: editor.root.childCount() == 1 and editor.root.child(0).childCount() == 1,
         "dragged item moved into submenu exactly once")
    folder = editor.root.child(0)
    editor.tree.setCurrentItem(folder)
    text("https://example.org/watch?start=7&lang=sv")
    editor.add_item("url")
    editor.tree.setCurrentItem(editor.root)
    def choose_tool(dialog):
        query = dialog.findChild(QLineEdit)
        query.setText("Scratchpad")
        result = dialog.findChild(QListWidget).currentItem()
        assert result.data(Qt.UserRole).kind == "tool"
        dialog.accept()
    dialog_input(choose_tool, QDialog)
    editor.add_item("tool")
    apps = Path(os.environ["XDG_DATA_HOME"]) / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "org.monet.TestWheel.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Wheel Fixture App\nExec=/usr/bin/true\n")
    def choose_app(dialog):
        dialog.findChild(QLineEdit).setText("Wheel Fixture App")
        assert dialog.findChild(QListWidget).currentItem().data(Qt.UserRole).value == "org.monet.TestWheel.desktop"
        dialog.accept()
    dialog_input(choose_app, QDialog)
    editor.add_item("app")

    def choose_shortcut(dialog):
        dialog.findChild(QLineEdit).setText("Window Maximize")
        assert dialog.findChild(QListWidget).currentItem().data(Qt.UserRole).component == "kwin"
        dialog.accept()
    def choose_component(dialog):
        dialog.findChild(QLineEdit).setText("kwin")
        assert dialog.findChild(QListWidget).currentItem().data(Qt.UserRole).value == "kwin"
        dialog.accept()
        dialog_input(choose_shortcut, QDialog)
    dialog_input(choose_component, QDialog)
    editor.add_item("shortcut")
    assert not errors, errors
    selected = profiles(window.settings)[ident]
    assert len(selected.items) == 4 and len(selected.items[0].children) == 2
    file_entry, link_entry = selected.items[0].children
    assert file_entry.value == str(file) and link_entry.value.endswith("start=7&lang=sv")
    class Handler(QObject):
        @Slot(QUrl)
        def opened(self, url):
            received.append(url)
    handler = Handler()
    received = []
    for scheme in ("file", "https"):
        QDesktopServices.setUrlHandler(scheme, handler, "opened")
    try:
        assert open_target(file_entry) and open_target(link_entry)
        assert [received[0].toLocalFile(), received[1].toString()] == [str(file), link_entry.value]
    finally:
        for scheme in ("file", "https"):
            QDesktopServices.unsetUrlHandler(scheme)
    window.home()
    window.Open(["wheel-settings"])
    assert editor.selector.currentData() == ident and editor.root.child(0).childCount() == 2
    if capture := os.getenv("MONET_WHEEL_EDITOR_CAPTURE"):
        window.grab().save(capture)
    folder = editor.root.child(0)
    for index in range(6):
        editor.add_row(folder, Entry("tool", "notes", f"Note {index}"))
    editor.save_items()
    before = profiles(window.settings)[ident]
    move_pointer(editor.root.child(1), folder)
    QTest.qWait(150)
    assert folder.childCount() == 8 and editor.root.childCount() == 4
    assert profiles(window.settings)[ident] == before
    (home / "passed").touch()
    print("Verified the native chooser, file and link handlers, pointer drag into a submenu and saved ordering.", flush=True)


def drag(coords):
    assert Path.home().parent.name.startswith("monet-tests-") and os.environ["WAYLAND_DISPLAY"] == "monet-wheel-editor"
    point = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / os.environ["WAYLAND_DISPLAY"], version=4)
    x, y, end_x, end_y = coords
    point.point(x, y)
    time.sleep(.15)
    point.button(True)
    try:
        time.sleep(.12)
        point.point(x-21, y)
        time.sleep(.12)
        for i in range(1, 9):
            point.point(x-21, round(y+(end_y-y)*i/8))
            time.sleep(.035)
        point.point(end_x, end_y)
        time.sleep(.18)
    finally:
        point.button(False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--drag", nargs=4, type=int)
    args = parser.parse_args()
    if args.drag:
        drag(args.drag)
    elif args.worker:
        exercise(args.installed)
    else:
        run_selection_test(Path(__file__), args.installed, "monet-wheel-editor")
