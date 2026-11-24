"""Run on an installed Monet image. All shortcuts and copies use a private KWin session."""
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

TEXT = "Test Ångström 🦊"


def wait(check, message):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.035)
    raise AssertionError(message)


def donor(home):
    from PySide6.QtCore import QMimeData, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    class DelayedCopy(QMimeData):
        def retrieveData(self, mime, kind):
            if mime.startswith("text/plain") and (home / "arm").exists() and not (home / "reading").exists():
                (home / "reading").touch()
                time.sleep(.65)
            return super().retrieveData(mime, kind)

    app = QApplication([])
    window = QWidget()
    window.show()

    def copy():
        mime = DelayedCopy()
        mime.setText(TEXT)
        mime.setHtml(f"<strong>{TEXT}</strong>")
        app.clipboard().setMimeData(mime)
        (home / "copied").touch()

    QTimer.singleShot(200, copy)
    app.exec()


def editor(home):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget

    app = QApplication([])
    app.setDesktopFileName("org.monet.PasteTest")
    window = QWidget()
    layout = QVBoxLayout(window)
    first, second = QTextEdit("First"), QTextEdit("Second")
    for field in (first, second):
        layout.addWidget(field)
        field.selectAll()
    window.show()
    first.setFocus()

    def update():
        if (home / "reading").exists() and not (home / "switched").exists():
            second.setFocus()
            second.selectAll()
            (home / "switched").touch()
        snapshot = [first.toPlainText(), second.toPlainText(), first.hasFocus(), second.hasFocus()]
        temporary = home / "fields.tmp"
        temporary.write_text(json.dumps(snapshot))
        temporary.replace(home / "fields")

    timer = QTimer()
    timer.timeout.connect(update)
    timer.start(20)
    app.exec()


def worker(home):
    import dbus
    from wayland_pointer import Pointer

    processes = []
    def start(*args):
        processes.append(subprocess.Popen(args, start_new_session=True))

    def fields():
        path = home / "fields"
        return json.loads(path.read_text()) if path.exists() else []

    try:
        bus = dbus.SessionBus()
        start("/usr/libexec/at-spi-bus-launcher", "--launch-immediately")
        wait(lambda: bus.name_has_owner("org.a11y.Bus"), "Accessibility bus did not start")
        address = bus.get_object("org.a11y.Bus", "/org/a11y/bus").GetAddress(dbus_interface="org.a11y.Bus")
        os.environ["AT_SPI_BUS_ADDRESS"] = str(address)
        start("/usr/libexec/at-spi2-registryd")
        accessibility = dbus.bus.BusConnection(str(address))
        wait(lambda: accessibility.name_has_owner("org.a11y.atspi.Registry"), "Registry did not start")
        start(sys.executable, __file__, "donor")
        wait(lambda: (home / "copied").exists(), "Clipboard donor did not start")
        start(sys.executable, __file__, "editor")
        wait(lambda: fields() == ["First", "Second", True, False], "Editor did not acquire focus")

        device = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-paste-test", version=4)
        def press():
            keys = (125, 29, 47)  # Left Meta, Left Ctrl, V (Linux input event codes).
            for down, codes in ((True, keys), (False, reversed(keys))):
                for code in codes:
                    device.key(code, down)
                    time.sleep(.022)

        (home / "arm").touch()
        press()
        wait(lambda: (home / "switched").exists(), "Clipboard conversion did not start")
        time.sleep(.95)
        assert fields() == ["First", "Second", False, True], fields()
        press()
        press()
        wait(lambda: fields() == ["First", TEXT * 2, False, True], "Editor lost a deliberate paste")
        html = subprocess.check_output(["wl-paste", "--no-newline", "--type", "text/html"])
        assert html.decode() == f"<strong>{TEXT}</strong>"
        (home / "passed").touch()
    finally:
        for process in reversed(processes):
            stop(process)


def run():
    with private_session() as env:
        home = Path(env["HOME"])
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(WAYLAND_DISPLAY="monet-paste-test", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE",
                   QT_QPA_PLATFORM="wayland", QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1", QT_ACCESSIBILITY="1",
                   NO_AT_BRIDGE="0", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1")
        session = home / "session.sh"
        session.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "worker"]) + "\n")
        session.chmod(0o700)
        command = [binary, "--virtual", "--width", "900", "--height", "600", "--no-lockscreen",
                   "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"], "--exit-with-session", session]
        server = subprocess.Popen(command, env=env, start_new_session=True)
        try:
            server.wait(timeout=40)
            assert (home / "passed").exists(), "Private paste session failed"
        finally:
            stop(server)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run()
    else:
        {"worker": worker, "donor": donor, "editor": editor}[sys.argv[1]](Path.home())
