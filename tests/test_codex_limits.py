"""Codex limits are opt-in, shared across readers, and restricted to reported windows."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
import tempfile
import sys
import time
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULE))

try:
    import codex_limits as limits
    from PySide6.QtCore import QSettings
except ModuleNotFoundError:
    limits = None


@unittest.skipUnless(limits, "requires Qt preferences")
class AccountLimits(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.settings = QSettings(str(self.folder / "prefs.ini"), QSettings.IniFormat)
        self.cli = self.folder / "codex"
        self.settings.setValue("codexExecutable", str(self.cli))
        self.marker = self.folder / "requests"
        self.cache = self.folder / "snapshot"
        location = patch.object(limits, "cache_file", return_value=self.cache)
        location.start()
        self.addCleanup(location.stop)
        self.cli.write_text('''#!/usr/bin/python3
import json, sys
from pathlib import Path
root = Path(__file__).parent
def read(): return json.loads(sys.stdin.readline())
def send(msg): print(json.dumps(msg), flush=True)
assert read()["method"] == "initialize"
send({"id": 1, "result": {}})
assert read()["method"] == "initialized"
assert read() == {"id": 2, "method": "account/rateLimits/read"}
with (root / "requests").open("a") as f: f.write("checked\\n")
send({"method":"account/rateLimits/updated", "params":{}})
send({"id": 2, **json.loads((root / "reply").read_text())})
''')
        self.cli.chmod(0o700)
        self.bucket = {"primary": {"usedPercent": 13.5, "windowDurationMins": 300,
                                   "resetsAt": int(time.time()) + 100},
                       "secondary": {"usedPercent": 97, "windowDurationMins": 10080}}

    def reply(self, data):
        (self.folder / "reply").write_text(json.dumps(data))

    def test_consent_cache_refresh_and_forget(self):
        self.reply({"result": {"rateLimitsByLimitId": {"codex": self.bucket}, "rateLimits": {},
                               "credits": "private extra details", "accountId": "private account"}})
        self.assertEqual(limits.snapshot(self.settings)["state"], "off")
        self.assertFalse(self.marker.exists())
        limits.enable(self.settings, True)
        first = limits.snapshot(self.settings)
        self.assertEqual(first["state"], "ready")
        self.assertEqual(first["expires"], self.bucket["primary"]["resetsAt"])
        rendered = limits.display(first)
        self.assertEqual([r["value"] for r in rendered["rows"]], [86.5, 3])
        self.assertTrue(rendered["rows"][0]["reset"])
        self.assertFalse(rendered["rows"][1]["reset"])
        self.assertNotIn("private", self.cache.read_text())
        self.assertEqual(limits.snapshot(self.settings), first)
        self.assertEqual(self.marker.read_text().splitlines(), ["checked"])
        self.reply({"error": {"message": "ChatGPT authentication required", "data": "private detail"}})
        state = limits.snapshot(self.settings, True)
        self.assertEqual(state["state"], "sign-in")
        self.assertEqual(limits.display(state)["rows"], [])
        self.assertNotIn("private", self.cache.read_text())
        self.assertEqual(len(self.marker.read_text().splitlines()), 2)
        limits.enable(self.settings, False)
        self.assertFalse(self.cache.exists())
        self.assertEqual(limits.snapshot(self.settings, True)["state"], "off")

    def test_invalid_and_non_default_buckets(self):
        self.assertEqual(limits.windows({"rateLimits": {"limitId": "another", **self.bucket}}), [])
        self.assertEqual(limits.windows({"rateLimits": {"primary": {"usedPercent": True}, "secondary": []}}), [])
        self.assertEqual(limits.windows({"rateLimits": {"primary": {"usedPercent": float("nan")}}}), [])
        self.assertEqual(limits.windows({"rateLimits": self.bucket})[0]["left"], 86.5)

    def test_simultaneous_readers_share_one_cli_request(self):
        limits.enable(self.settings, True)
        self.reply({"result": {"rateLimits": self.bucket}})
        code = ("import json, sys; from pathlib import Path; from PySide6.QtCore import QSettings; "
                "sys.path.insert(0,sys.argv[1]); import codex_limits as m; "
                "m.cache_file=lambda *_:Path(sys.argv[3]); "
                "print(json.dumps(m.snapshot(QSettings(sys.argv[2],QSettings.IniFormat))))")
        args = [sys.executable, "-B", "-c", code, str(MODULE), self.settings.fileName(), str(self.cache)]
        procs = [subprocess.Popen(args, stdout=subprocess.PIPE, text=True) for _ in range(2)]
        try:
            for child in procs:
                out, _ = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0)
                self.assertEqual(json.loads(out)["state"], "ready")
        finally:
            for child in procs:
                if child.poll() is None:
                    child.kill()
                    child.wait()
        self.assertEqual(self.marker.read_text().splitlines(), ["checked"])

    def test_unresponsive_cli_is_reaped(self):
        self.cli.write_text("#!/usr/bin/python3\nimport os,time\nfrom pathlib import Path\n"
                            "Path(__file__).with_name('pid').write_text(str(os.getpid()))\ntime.sleep(10)\n")
        with patch.object(limits, "REPLY_TIMEOUT", .4), self.assertRaises(TimeoutError):
            asyncio.run(limits.fetch(str(self.cli)))
        pid = int((self.folder / "pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_disable_during_request_discards_data(self):
        limits.enable(self.settings, True)
        async def disconnect(_):
            limits.enable(self.settings, False)
            return "ready", limits.windows({"rateLimits":self.bucket})
        with patch.object(limits, "fetch", disconnect):
            self.assertEqual(limits.snapshot(self.settings)["state"], "off")
        self.assertFalse(self.cache.exists())

    def test_cli_discovery_with_no_installed_app(self):
        from gi.repository import GioUnix
        with patch("shutil.which", return_value=None), patch.object(GioUnix.DesktopAppInfo, "new", side_effect=TypeError("constructor returned NULL")):
            self.settings.remove("codexExecutable")
            self.assertIsNone(limits.executable(self.settings))

    def test_missing_executable_and_invalid_replies(self):
        limits.enable(self.settings, True)
        self.settings.setValue("codexExecutable", str(self.folder / "absent"))
        self.assertEqual(limits.snapshot(self.settings)["state"], "missing")
        self.settings.setValue("codexExecutable", str(self.cli))
        self.reply({"result": {}})
        self.assertEqual(limits.snapshot(self.settings, True)["state"], "empty")
        self.cli.write_text('#!/bin/sh\necho broken\n')
        self.assertEqual(limits.snapshot(self.settings, True)["state"], "unavailable")
