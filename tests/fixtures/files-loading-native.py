#!/usr/bin/python3
"""Exercise an actual paired Dolphin against a deliberately delayed WebDAV server.

Run only in a disposable desktop container, with the matching bundle as argv[1].
No desktop session or external network service is used.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from gi.repository import Gio, GLib


def wait(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.025)
    raise AssertionError("Native Files fixture timed out")


class WebDav(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    entered = threading.Event()
    release = threading.Event()
    cancelled = threading.Event()
    requests = []

    def log_message(self, *_):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("DAV", "1, 2")
        self.send_header("Allow", "OPTIONS, PROPFIND, GET, HEAD")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PROPFIND(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.requests.append((self.command, self.path, self.headers.get("Depth")))
        if self.path.startswith("/blocked"):
            self.entered.set()
            deadline = time.monotonic() + 25
            while not self.release.is_set() and time.monotonic() < deadline:
                if select.select([self.connection], [], [], .05)[0]:
                    if not self.connection.recv(1, socket.MSG_PEEK):
                        self.cancelled.set()
                        return
                self.release.wait(.05)
        body = ("<?xml version='1.0'?><d:multistatus xmlns:d='DAV:'>"
                "<d:response><d:href>" + self.path + "</d:href><d:propstat><d:prop>"
                "<d:resourcetype><d:collection/></d:resourcetype>"
                "<d:getlastmodified>Thu, 05 Nov 2026 10:00:00 GMT</d:getlastmodified>"
                "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
                "</d:response></d:multistatus>").encode()
        try:
            self.send_response(207)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Cancellation is expected to close the worker's connection.


def main(bundle, artifacts, mode='navigate'):
    assert mode in {'navigate', 'cancel'}
    bundle = Path(bundle).resolve()
    artifacts = Path(artifacts).resolve(); artifacts.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        env.update(QT_QPA_PLATFORM="xcb", LD_LIBRARY_PATH=str(bundle), QT_FORCE_STDERR_LOGGING="1")
        # QLocalServer sockets must also remain private to this fixture.
        env["TMPDIR"] = env["XDG_RUNTIME_DIR"]
        library = next(bundle.glob("libdolphinprivate.so.*.*.*"))
        link = bundle / "libdolphinprivate.so.6"
        if not link.exists(): link.symlink_to(library.name)
        linked = subprocess.check_output(['ldd', str(bundle / 'dolphin')], env=env, text=True)
        assert 'not found' not in linked, ('Incomplete native Files test runtime', linked)
        local = Path(env["HOME"]) / "Local-folder"; local.mkdir()
        (local / "still-here.txt").write_text("fixture")
        log = (artifacts / "dolphin.log").open("w")
        xvfb = subprocess.Popen(["Xvfb", "-displayfd", "1", "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
            env=env, stdout=subprocess.PIPE, stderr=log, text=True, start_new_session=True)
        app = None
        server = ThreadingHTTPServer(("127.0.0.1", 0), WebDav)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            assert select.select([xvfb.stdout], [], [], 10)[0], "Xvfb did not start"
            env["DISPLAY"] = ":" + xvfb.stdout.readline().strip()
            app = subprocess.Popen([str(bundle / "dolphin"), "--new-window", str(local)], env=env,
                stdout=log, stderr=log, start_new_session=True)
            bus = Gio.DBusConnection.new_for_address_sync(env["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            def call(name, path, interface, method, value=None, timeout=1500):
                return bus.call_sync(name, path, interface, method, value, None,
                    Gio.DBusCallFlags.NONE, timeout, None).unpack()
            def service():
                return next((name for name in call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                    "org.freedesktop.DBus", "ListNames")[0] if name.startswith("org.kde.dolphin-")), None)
            name = wait(service)
            path = "/dolphin/Dolphin_1"
            def find_window(parent="/dolphin"):
                raw = call(name, parent, "org.freedesktop.DBus.Introspectable", "Introspect")[0]
                if "monetFilesState" in raw: return parent
                for node in ET.fromstring(raw).findall("node"):
                    found = find_window(parent + "/" + node.attrib["name"])
                    if found: return found
            path = wait(find_window)
            def state():
                return json.loads(call(name, path, "org.kde.dolphin.MainWindow", "monetFilesState")[0])
            def ready():
                result = state()
                return result if result and result["tabs"][result["active"]]["folders"] == [str(local)] else None
            wait(ready)
            window = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)], env=env, text=True).splitlines()[0]
            def navigate(url):
                subprocess.run(["xdotool", "windowfocus", "--sync", window, "key", "--clearmodifiers", "ctrl+l"], env=env, check=True)
                subprocess.run(["xdotool", "key", "ctrl+a"], env=env, check=True)
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "1", "--", str(url)], env=env, check=True)
                subprocess.run(["xdotool", "key", "Return"], env=env, check=True)
            remote = "webdav://127.0.0.1:" + str(server.server_port) + "/blocked/"
            navigate(remote)
            wait(WebDav.entered.is_set)
            wait(lambda: call(name, path, "org.kde.KMainWindow", "actionIsEnabled", GLib.Variant('(s)', ('stop',)))[0])
            assert state() is None, "Remote/loading metadata must remain refused"
            latencies = []
            for _ in range(20):
                started = time.monotonic(); state(); latencies.append((time.monotonic() - started) * 1000)
            if mode == 'cancel':
                assert call(name, path, "org.kde.KMainWindow", "activateAction", GLib.Variant('(s)', ('stop',)))[0]
                wait(lambda: not call(name, path, "org.kde.KMainWindow", "actionIsEnabled", GLib.Variant('(s)', ('stop',)))[0])
            # A slash-leading path in a remote navigator belongs to that remote
            # host. Use an explicit file URI when returning to the local drive.
            navigate(local.as_uri())
            wait(ready)
            before = ready()
            WebDav.release.set()
            time.sleep(1)
            assert ready() == before, "A stale remote reply replaced the new local view"
            (artifacts / "result.json").write_text(json.dumps({"requests": WebDav.requests,
                "rpc_ms": latencies, "maximum_rpc_ms": max(latencies),
                "navigation_while_waiting": True, "stale_reply_ignored": True,
                "cancelled": mode == 'cancel'}, indent=2))
        finally:
            try:
                if app is not None and app.poll() is None and 'window' in locals():
                    (artifacts / "last-state.json").write_text(json.dumps(state(), indent=2))
                    (artifacts / "window.xml").write_text(call(name, path, "org.freedesktop.DBus.Introspectable", "Introspect")[0])
                    subprocess.run([sys.executable, "-c", "from PySide6.QtGui import QGuiApplication; import sys; app=QGuiApplication([]); app.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])", window, str(artifacts / "window.png")], env=env, check=True)
            finally:
                WebDav.release.set(); server.shutdown(); server.server_close()
                if app is not None: stop(app)
                stop(xvfb); xvfb.stdout.close(); log.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
