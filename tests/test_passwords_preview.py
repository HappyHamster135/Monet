"""The preview only patches presentation/defaults and refuses an unexpected upstream tree."""
import importlib.util
import http.client
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("passwords_patch", ROOT / "prototypes/passwords/apply.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class PasswordsPreview(unittest.TestCase):
    def fixture(self, root):
        for name, edits in PATCH.changes().items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(before for before, _ in edits), encoding="utf-8")

    def test_unexpected_source_fails_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            bad = root / "src/core/Config.cpp"
            bad.write_text("Upstream changed", encoding="utf-8")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with self.assertRaises(ValueError):
                PATCH.apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_duplicate_anchor_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            path = root / "src/main.cpp"
            path.write_text(path.read_text() * 2, encoding="utf-8")
            with self.assertRaises(ValueError):
                PATCH.apply(root)

    def test_patch_keeps_security_engine_and_protocol_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            PATCH.apply(root)
            self.assertIn('"MonetWindow.inc"', (root / "src/gui/MainWindow.cpp").read_text())
            self.assertTrue((root / "tests/TestMonetPasswords.cpp").is_file())
            self.assertFalse((root / "src/crypto").exists())
            self.assertFalse((root / "src/browser").exists())
            with self.assertRaises(ValueError):
                PATCH.apply(root)


class PasswordsTestSite(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("passwords_test_site", ROOT / "prototypes/passwords/test_zen.py")
        self.fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.fixture)
        self.server = self.fixture.HTTPServer(("127.0.0.1", 0), self.fixture.TestSite)
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        def close():
            self.server.shutdown()
            worker.join(timeout=2)
            self.server.server_close()
        self.addCleanup(close)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_only_form_pages_are_served_never_vaults_or_directory_listings(self):
        for path in ("/Passwords.kdbx", "/../Passwords.kdbx", "/browser.log", "/fixtures/"):
            self.assertEqual(self.request("GET", path)[0], 404)
        for path, purpose in (("/", "current-password"), ("/signup", "new-password"), ("/change", "new-password")):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn(purpose.encode(), body)

    def test_submission_redirects_without_echoing_or_persisting_credentials(self):
        secret = "username=fixture&password=never-echo-this"
        status, headers, body = self.request("POST", "/submitted", secret)
        self.assertEqual((status, headers["Location"], body), (303, "/submitted", b""))
        status, _, body = self.request("GET", "/submitted")
        self.assertEqual(status, 200)
        self.assertNotIn(b"never-echo-this", body)
        self.assertEqual(self.request("POST", "/submitted", "x" * 4097)[0], 400)
        self.assertEqual(self.request("POST", "/elsewhere", secret)[0], 400)

    def test_frame_and_two_step_fixtures_keep_the_boundaries_distinct(self):
        self.assertIn(b'src="/"', self.request("GET", "/same-frame")[2])
        self.assertIn(b'src="http://localhost:8765/"', self.request("GET", "/cross-frame")[2])
        self.assertIn(b'src="http://127.0.0.1:8765/"', self.request("GET", "/trusted-frame")[2])
        first = self.request("GET", "/multi-user")[2]
        second = self.request("GET", "/multi-password")[2]
        self.assertIn(b'name="username"', first)
        self.assertNotIn(b'name="password"', first)
        self.assertIn(b'name="password"', second)
        self.assertNotIn(b'name="username"', second)


if __name__ == "__main__":
    unittest.main()
