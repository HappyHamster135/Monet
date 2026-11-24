"""Exercise the installed port manager against disposable listeners in an isolated container."""
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def name(value):
    ctypes.CDLL(None).prctl(15, value.encode(), 0, 0, 0)


def serve(directory):
    name("Port fixture")
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen()
    port = tcp.getsockname()[1]
    udp = socket.socket(type=socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", port))
    subprocess.Popen([sys.executable, __file__, "idle", directory, "Shared owner"],
                     pass_fds=(tcp.fileno(), udp.fileno()))
    subprocess.Popen([sys.executable, __file__, "idle", directory, "Worker parent"])
    def rebind(*_):
        nonlocal tcp
        tcp.close()
        tcp = socket.socket()
        tcp.bind(("127.0.0.1", 0))
        tcp.listen()
        (directory / "new-port").write_text(str(tcp.getsockname()[1]))
    def connect_udp(*_):
        udp.connect(("127.0.0.1", 9))
        (directory / "connected").touch()
    signal.signal(signal.SIGUSR1, rebind)
    signal.signal(signal.SIGUSR2, connect_udp)
    (directory / "port").write_text(str(port))
    while True:
        signal.pause()


def idle(directory, label):
    name(label)
    if label == "Worker parent":
        subprocess.Popen([sys.executable, __file__, "idle", directory, "Nested child"])
    if label != "Shared owner":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (directory / label).write_text(str(os.getpid()))
    while True:
        signal.pause()


def exercise():
    assert os.environ["HOME"].startswith("/tmp/monet-tests-") and os.environ["QT_QPA_PLATFORM"] == "offscreen"
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    sys.path.insert(0, os.getenv("MONET_UTILITIES_MODULES", str(ROOT / "linux/share/monet/utilities")))
    from window import Window
    from local_ports import process

    app = QApplication([])
    window = Window(ROOT / "linux/libexec")
    directory = Path(os.environ["HOME"])
    server = subprocess.Popen([sys.executable, __file__, "serve", directory], start_new_session=True)
    try:
        def wait(check):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                value = check()
                if value:
                    return value
                QTest.qWait(25)
            raise AssertionError("Timed out waiting for " + str(check))
        wait(lambda: all((directory / key).exists() for key in ("port", "Shared owner", "Nested child", "Worker parent")))
        port = (directory / "port").read_text()
        shared, worker, nested = [int((directory / key).read_text()) for key in ("Shared owner", "Worker parent", "Nested child")]
        window.show()
        window.search.setText("Listening ports")
        assert window.catalog.count() == 1
        window.open_selected()
        page = window.pages["ports"]
        wait(lambda: not page.loading)
        page.filter.setText("TCP " + port)
        def visible():
            return [page.model.index(i, 0) for i in range(page.model.rowCount())]
        assert {i.data(Qt.UserRole).owner.pid for i in visible()} == {server.pid, shared}
        page.filter.setText("UDP " + port)
        assert {i.data(Qt.UserRole).owner.pid for i in visible()} == {server.pid, shared}
        page.filter.setText("no-matching-endpoint")
        assert not visible() and not page.manage.isEnabled()
        def inspect(protocol="TCP"):
            page.filter.setText(protocol + " " + port)
            row = next(i for i in visible() if i.data(Qt.UserRole).owner.pid == server.pid)
            page.rows.selectRow(row.row())
            assert page.manage.isEnabled()
            page.manage.click()
            wait(lambda: page.detail)
            return page.detail
        def answer(button, yes):
            def press():
                box = QApplication.activeModalWidget()
                assert isinstance(box, QMessageBox)
                assert box.defaultButton() is box.button(QMessageBox.Cancel)
                if yes:
                    next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.DestructiveRole).click()
                else:
                    box.button(QMessageBox.Cancel).click()
            QTimer.singleShot(20, press)
            button.click()
        def select(dialog, pid):
            item, = dialog.tree.findItems(str(pid), Qt.MatchExactly | Qt.MatchRecursive, 1)
            dialog.tree.setCurrentItem(item)
        dialog = inspect()
        select(dialog, shared)
        answer(dialog.end, False)
        assert process(shared) and page.detail is dialog
        answer(dialog.end, True)
        wait(lambda: not page.loading and process(shared) is None)
        assert server.poll() is None and process(worker) and process(nested)
        dialog = inspect()
        select(dialog, worker)
        assert dialog.children.isEnabled()
        dialog.children.setChecked(True)
        answer(dialog.force, True)
        wait(lambda: not page.loading and process(worker) is None and process(nested) is None)
        assert server.poll() is None
        dialog = inspect("UDP")
        server.send_signal(signal.SIGUSR2)
        wait(lambda: (directory / "connected").exists())
        answer(dialog.end, True)
        wait(lambda: not page.loading)
        assert server.poll() is None and not visible()
        dialog = inspect()
        server.send_signal(signal.SIGUSR1)
        wait(lambda: (directory / "new-port").exists())
        answer(dialog.end, True)
        wait(lambda: not page.loading)
        assert server.poll() is None and not visible()
        port = (directory / "new-port").read_text()
        dialog = inspect()
        answer(dialog.end, True)
        wait(lambda: not page.loading and server.poll() == -signal.SIGTERM)
        page.refresh()
        wait(lambda: not page.loading)
        assert not visible()
        window.close()
        print("Verified shared TCP/UDP ownership, filtering, cancellation, single and subtree signals, and stale-port rejection.")
    finally:
        stop(server)


if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        serve(Path(sys.argv[2]))
    elif sys.argv[1:2] == ["idle"]:
        idle(Path(sys.argv[2]), sys.argv[3])
    elif sys.argv[1:] == ["--private"]:
        exercise()
    else:
        # This integration test inspects the namespace's actual listening sockets.
        if not Path("/run/.containerenv").exists() or set(os.listdir("/sys/class/net")) != {"lo"}:
            sys.exit("Run this fixture with Podman --network=none and its own PID namespace.")
        with private_session() as env:
            env.update(LANGUAGE="en", LC_ALL="C.UTF-8")
            subprocess.run([sys.executable, __file__, "--private"], env=env, check=True, timeout=60)
