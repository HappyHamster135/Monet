"""The required desktop job must fail on lost coverage and contain its processes."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("monet_test_runner", ROOT / "tools/test.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Coverage(unittest.TestCase):
    def test_only_documented_skips_are_allowed(self):
        self.assertTrue(runner.expected_skip({"test": "tests.test_notification_policy.NativePolicy.test_one",
                                              "reason": "only run on the isolated test bus"}))
        for name, reason in (("tests.test_phone_window.PhoneWindow.test_one", "Qt runtime"),
                             ("tests.test_passwords_bus.PasswordsBus.test_one", "requires isolated dbus-run-session"),
                             ("tests.test_notification_policy.NativePolicy.test_one", "Qt runtime")):
            self.assertFalse(runner.expected_skip({"test": name, "reason": reason}))

    def test_skipped_required_checks_and_missing_worker_results_fail_the_job(self):
        @contextmanager
        def session(): yield {}
        for reported in (True, False):
            def execute(command, env, timeout):
                if "--worker" in command and reported:
                    Path(command[-1]).write_text(json.dumps({"module": "tests.fixture", "tests": 1,
                        "failures": 0, "errors": 0, "skipped": [{"test": "tests.fixture.test_one", "reason": "Qt runtime"}]}))
                return 0
            with patch.object(runner, "private_session", session), patch.object(runner, "run", side_effect=execute), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(["--require-desktop", "tests.fixture"]), 1)


@unittest.skipUnless(sys.platform == "linux", "Linux process and bus isolation")
class Isolation(unittest.TestCase):
    def test_private_bus_cannot_activate_the_desktop_vault_or_portal(self):
        with runner.private_session() as env:
            folder = Path(env["MONET_PHONE_WINDOW_ROOT"])
            self.assertTrue(Path(env["HOME"]).is_relative_to(folder))
            self.assertNotEqual(env["DBUS_SESSION_BUS_ADDRESS"], os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
            result = subprocess.run(["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.DBus",
                                     "/org/freedesktop/DBus", "org.freedesktop.DBus.ListActivatableNames"],
                                    env=env, text=True, capture_output=True, check=True, timeout=5)
            self.assertNotIn("kwallet", result.stdout)
            self.assertNotIn("portal", result.stdout)
            self.assertNotIn("secrets", result.stdout)
        self.assertFalse(folder.exists())

    def test_timeout_terminates_the_whole_child_process_group(self):
        with tempfile.TemporaryDirectory() as temp:
            pidfile = Path(temp) / "child"
            code = ("import subprocess,sys,time; from pathlib import Path; "
                    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)")
            self.assertEqual(runner.run([sys.executable, "-c", code, str(pidfile)], dict(os.environ), 1), 124)
            child = int(pidfile.read_text())
            for _ in range(100):
                path = Path(f"/proc/{child}/stat")
                try:
                    if path.read_text().split()[2] == "Z": break
                except (FileNotFoundError, ProcessLookupError):
                    break  # Reaped between the timeout and this observation.
                time.sleep(.01)
            else: self.fail("Timed-out module left its child running")


if __name__ == "__main__": unittest.main()
