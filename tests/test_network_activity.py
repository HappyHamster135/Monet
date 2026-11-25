"""Exercise the network monitor and its cancellable Qt HTTP transfers on loopback."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from network_activity import Connection, SessionTotals, Traffic, counters, default_routes, rate_text
    from speed_test import SpeedTest
except ImportError:
    SpeedTest = None


def link(rx, tx, index=2, name="eth0"):
    return Connection(name, index, name, ("192.0.2.23",), rx, tx)


@unittest.skipUnless(SpeedTest, "requires Qt Network")
class NetworkTraffic(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def test_proc_counters_and_route_preference(self):
        (self.folder / "dev").write_text("header\nheader\n eth0: 42 0 0 0 0 0 0 0 142\n bad: -1 0\n")
        self.assertEqual(counters(self.folder / "dev"), {"eth0": (42, 142)})
        self.assertEqual(counters(self.folder / "missing"), {})
        rows = [f"{name} 00000000 00000000 {flags} 0 0 {metric} 00000000"
                for name, flags, metric in (("eth0", "3", 100), ("vpn", "1", 10), ("bad", "201", 1))]
        (self.folder / "route").write_text("\n".join(["header", *rows, "corrupt\n"]))
        v6 = "0"*32
        (self.folder / "ipv6_route").write_text(f"{v6} 00 {v6} 00 {v6} 0000000f 0 0 00000001 wifi\n")
        self.assertEqual(default_routes(self.folder), ["vpn", "wifi", "eth0"])

    def test_rate_gaps_device_replacement_and_independent_interfaces(self):
        traffic = Traffic()
        self.assertEqual(traffic.sample([link(10, 20)], 1), {})
        self.assertEqual(traffic.sample([link(20, 60), link(450, 1, 9, "vpn")], 3), {"eth0": (5, 20)})
        self.assertEqual(traffic.sample([link(1, 0), link(460, 5, 9, "vpn")], 4), {"vpn": (10, 4)})
        self.assertEqual(traffic.sample([link(400, 200, 3)], 5), {})
        self.assertEqual(traffic.sample([link(401, 200, 3)], 12), {})
        traffic.sample([], 13)
        self.assertEqual(traffic.sample([link(403, 202, 3)], 14), {})
        self.assertTrue(rate_text(125000, True).endswith(" Mbit/s"))

    def test_session_checkpoint_reset_and_relogin(self):
        settings = QSettings(str(self.folder / "totals.ini"), QSettings.IniFormat)
        def ledger():
            return SessionTotals(settings, "a")
        s = ledger()
        s.sample([link(10, 5), link(120, 25, 9, "vpn")])
        s.sample([link(100, 40), link(150, 50, 9, "vpn")])
        s.save()
        s = ledger()
        s.sample([link(140, 60)])
        self.assertEqual(s.devices["eth0"][-2:], [130, 55])
        s.sample([link(2, 4)])
        self.assertEqual(ledger().devices["eth0"][-2:], [132, 59])
        s.reset(link(2, 4))
        self.assertEqual(ledger().devices["eth0"][-2:], [0, 0])
        self.assertEqual(ledger().devices["vpn"][-2:], [30, 25])
        s.sample([link(500, 300, 5)])
        self.assertEqual(s.devices["eth0"][-2:], [0, 0])
        self.assertFalse(SessionTotals(settings, "next login").devices)
        settings.setValue("devices", '{"wrong":[1,-4],"bad":["2",1,2,3,4]}')
        self.assertFalse(ledger().devices)

    def test_concurrent_logins_keep_independent_counters(self):
        with patch("network_activity.QStandardPaths.writableLocation", return_value=str(self.folder)):
            first = SessionTotals(session="login A")
            first.sample([link(10, 15)])
            second = SessionTotals(session="login B")
            second.sample([link(50, 55)])
            first.sample([link(100, 200)])
            second.sample([link(100, 200)])
            second.save()
            first.save()
            self.assertEqual(SessionTotals(session="login A").devices["eth0"][-2:], [90, 185])
            self.assertEqual(SessionTotals(session="login B").devices["eth0"][-2:], [50, 145])


@contextmanager
def endpoint(mode="ok"):
    """A server that can emulate portals, partial transfers and slow replies."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body=b"", mime="application/octet-stream"):
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Type", mime)
            if status == 302:
                self.send_header("Location", "/portal")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path != "/__down":
                self.respond(404)
                return
            size = int(parse_qs(url.query)["bytes"][0])
            server.downloads.append(size)
            if server.mode == "wait":
                server.entered.set()
                server.release.wait(4)
            if server.mode == "redirect":
                self.respond(302)
            elif server.mode == "portal":
                self.respond(200, b"", "text/html")
            elif size and server.mode == "short":
                self.respond(200, bytes(size - 1))
            elif size and server.mode == "long":
                self.respond(200, bytes(size + 1))
            else:
                self.respond(200, bytes(size))

        def do_POST(self):
            size = int(self.headers["Content-Length"])
            body = self.rfile.read(size)
            server.uploads.append(len(body))
            self.respond(503 if server.mode == "upload error" else 204)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.mode = mode
    server.downloads, server.uploads = [], []
    server.entered, server.release = threading.Event(), threading.Event()
    server.origin = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .025}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join()


@unittest.skipUnless(SpeedTest, "requires Qt Network")
class SpeedTransfers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, condition):
        end = time.monotonic() + 6
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.002)
        self.assertTrue(condition(), "Qt transfer timed out")

    def engine(self, server):
        engine = SpeedTest(origin=server.origin)
        engine.first_chunk = 16000
        engine.max_bytes = 48000
        self.addCleanup(engine.cancel)
        return engine

    def test_transfers_only_after_start_and_within_budget(self):
        with endpoint() as server:
            engine = self.engine(server)
            self.app.processEvents()
            self.assertEqual(server.downloads, [])
            engine.start()
            self.wait(lambda: not engine.running)
            self.assertEqual(engine.phase, "done", engine.error)
            self.assertEqual(set(engine.results), {"latency", "download", "upload"})
            self.assertTrue(all(n > 0 for n in engine.results.values()))
            self.assertEqual(server.downloads[:5], [0]*5)
            self.assertEqual(sum(server.downloads), engine.max_bytes)
            self.assertEqual(sum(server.uploads), engine.max_bytes)

    def test_rejects_portal_redirect_wrong_size_and_failed_upload(self):
        for mode in ("portal", "redirect", "short", "long", "upload error"):
            with self.subTest(mode=mode), endpoint(mode) as server:
                engine = self.engine(server)
                engine.start()
                self.wait(lambda: not engine.running)
                self.assertEqual(engine.phase, "failed")
                self.assertTrue(engine.error)
                self.assertNotIn("upload", engine.results)
                self.assertEqual(bool(server.uploads), mode == "upload error")

    def test_abort_and_retry_ignores_old_replies(self):
        with endpoint("wait") as server:
            engine = self.engine(server)
            engine.start()
            self.wait(server.entered.is_set)
            engine.cancel()
            self.assertEqual(engine.phase, "cancelled")
            server.mode = "ok"
            engine.start()
            server.release.set()
            self.wait(lambda: not engine.running)
            self.assertEqual(engine.phase, "done", engine.error)

    def test_timeout_stops_requests_and_offers_retry(self):
        with endpoint("wait") as server:
            engine = self.engine(server)
            engine.start()
            self.wait(server.entered.is_set)
            engine.timeout.start(1)
            self.wait(lambda: not engine.running)
            self.assertEqual(engine.phase, "failed")
            self.assertIsNone(engine.reply)
            self.assertFalse(engine.results)
