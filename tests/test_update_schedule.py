"""Automatic retries obey the network gate; no real updater is invoked."""
import os
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
UNIT = (ROOT / "linux/systemd/monet-update.service").read_text()
GATE = next(line.split("=", 1)[1] for line in UNIT.splitlines() if line.startswith("ExecCondition=/bin/sh"))


class UpdateFeedback(unittest.TestCase):
    def test_only_a_successful_complete_report_is_accepted(self):
        helper = quick_helper()
        for output, code, ok in (('{"system": false, "apps": 0}', 0, True),
                                 ('Progress\n{"system": true, "apps": 2, "version": "0.9.5"}', 0, True),
                                 ('{"system": false, "apps": 0}', 1, False),
                                 ('{}', 0, False), ('{"system": false, "apps": -1}', 0, False),
                                 ('{"system": false, "apps": true}', 0, False), ('not json', 0, False)):
            with self.subTest(output=output, code=code), patch.object(helper.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], code, output, "App check failed" if code else "")):
                result = helper.update_check()
                self.assertEqual(result["ok"], ok)
                if not ok:
                    self.assertTrue(result["message"])

    def test_timeout_or_unavailable_helper_returns_a_retryable_error(self):
        helper = quick_helper()
        for error in (OSError("fixture: unavailable"), subprocess.TimeoutExpired("fixture", 300)):
            with patch.object(helper.subprocess, "run", side_effect=error):
                result = helper.update_check()
                self.assertFalse(result["ok"])
                self.assertTrue(result["message"])


class UpdateHistory(unittest.TestCase):
    def setUp(self):
        self.helper = quick_helper()

    def entry(self, outcome, invocation=1, seconds=1000):
        return {"MESSAGE_ID": getattr(self.helper, "UPDATE_" + outcome),
                "INVOCATION_ID": f"{invocation:032x}", "__REALTIME_TIMESTAMP": str(seconds * 1000000)}

    def parse(self, *entries):
        return self.helper.recent_update_results("\n".join(json.dumps(entry) for entry in entries))

    def test_recovery_is_newest_and_each_attempt_is_shown_once(self):
        entries = [self.entry("FAILED", 1, 1000), self.entry("FAILED", 1, 1001),
                   self.entry("FINISHED", 2, 1100)]
        self.assertEqual(self.parse(*entries), [{"time": 1100000, "result": "done"},
                                               {"time": 1001000, "result": "failed"}])

    def test_a_successful_job_message_after_a_skip_is_not_an_update(self):
        self.assertEqual(self.parse(self.entry("SKIPPED"), self.entry("FINISHED")),
                         [{"time": 1000000, "result": "skipped"}])
        self.assertEqual(self.parse(self.entry("FINISHED"), self.entry("SKIPPED")),
                         [{"time": 1000000, "result": "skipped"}])

    def test_history_is_bounded_and_ignores_runs_that_never_started(self):
        entries = [self.entry("FINISHED", i, 1000 + i) for i in range(30)]
        items = self.parse(*entries)
        self.assertEqual(len(items), 10)
        self.assertEqual(items[0]["time"], 1029000)
        self.assertEqual(items[-1]["time"], 1020000)
        entry = self.entry("FINISHED")
        del entry["INVOCATION_ID"]
        self.assertEqual(self.parse(entry), [])

    def test_dates_and_malformed_entries_cannot_turn_into_success(self):
        for value in (None, [], "bad", "-1", "0", "9" * 25):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(dict(self.entry("FINISHED"), __REALTIME_TIMESTAMP=value))
        with self.assertRaises(ValueError):
            self.helper.recent_update_results("not json")
        with self.assertRaises(ValueError):
            self.parse([])

    def test_unavailable_history_is_distinct_from_no_saved_history(self):
        for output, code, expected in (("", 0, True), ("", 1, False), ("bad", 0, False)):
            with patch.object(self.helper, "run", return_value="LoadState=loaded\nActiveState=failed\nSubState=failed"), \
                    patch.object(self.helper.subprocess, "run", return_value=subprocess.CompletedProcess([], code, output, "")):
                self.assertEqual(self.helper.update_history(), {"ok": expected, "items": [], "state": "idle"})
        for error in (OSError("missing"), subprocess.TimeoutExpired("journalctl", 5)):
            with patch.object(self.helper, "run", return_value=None), \
                    patch.object(self.helper.subprocess, "run", side_effect=error):
                self.assertEqual(self.helper.update_history(), {"ok": False, "items": [], "state": "unknown"})

    def test_active_and_retry_state_does_not_hide_the_previous_failure(self):
        for active, sub, state in (("activating", "start", "running"),
                                   ("activating", "auto-restart", "retry"),
                                   ("activating", "auto-restart-queued", "retry")):
            with patch.object(self.helper, "run", return_value=f"LoadState=loaded\nActiveState={active}\nSubState={sub}"), \
                    patch.object(self.helper.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], 0, json.dumps(self.entry("FAILED")), "")) as read:
                result = self.helper.update_history()
                self.assertEqual(result["state"], state)
                self.assertEqual(result["items"][0]["result"], "failed")
                args = read.call_args.args[0]
                self.assertIn("_PID=1", args)
                self.assertIn("UNIT=monet-update.service", args)


class NetworkGate(unittest.TestCase):
    def test_metered_unknown_missing_and_invalid_network_states_skip_automatic_work(self):
        with tempfile.TemporaryDirectory(prefix="monet-network-fixture-") as tmp:
            bus = Path(tmp) / "busctl"
            bus.write_text('#!/bin/sh\nprintf "%s\\n" "$FIXTURE_METERED"\nexit "$FIXTURE_EXIT"\n')
            bus.chmod(0o700)
            for response, code, allowed in (("u 0", "0", False), ("u 1", "0", False), ("u 2", "0", True),
                                             ("u 3", "0", False), ("u 4", "0", True), ("", "1", False),
                                             ("u 2", "1", False), ("garbage", "0", False)):
                with self.subTest(response=response, code=code):
                    gate = GATE.replace("$$", "$").replace("/var/lib/monet/auto-updates-off", str(Path(tmp) / "off"))
                    done = subprocess.run(shlex.split(gate),
                                          env=dict(os.environ, PATH=tmp, FIXTURE_METERED=response, FIXTURE_EXIT=code),
                                          capture_output=True, timeout=5)
                    self.assertEqual(done.returncode == 0, allowed)


@unittest.skipUnless(os.environ.get("MONET_NATIVE_SYSTEMD_TESTS") == "1", "opt-in transient user-service fixture")
class NativeRetry(unittest.TestCase):
    def test_native_success_failure_and_skip_events_keep_their_meaning(self):
        helper = quick_helper()
        for mode, expected in (("success", "done"), ("failure", "failed"), ("skip", "skipped")):
            name = "monet-history-fixture-" + uuid.uuid4().hex + ".service"
            args = ["systemd-run", "--user", "--quiet", "--wait", "--unit=" + name, "--property=Type=oneshot"]
            if mode == "skip":
                args.append("--property=ExecCondition=/bin/false")
            args.append("/bin/false" if mode == "failure" else "/bin/true")
            try:
                subprocess.run(args, capture_output=True, timeout=10)
                journal = subprocess.run(["journalctl", "--user", "-u", name, "--no-pager", "-o", "json"],
                                         capture_output=True, text=True, timeout=5, check=True)
                entries = [json.loads(line) for line in journal.stdout.splitlines()]
                # A disposable user unit exercises the same native events without
                # starting the laptop's real privileged updater.
                for entry in entries:
                    entry["INVOCATION_ID"] = entry.get("USER_INVOCATION_ID")
                items = helper.recent_update_results("\n".join(json.dumps(entry) for entry in entries))
                self.assertEqual([item["result"] for item in items], [expected])
            finally:
                subprocess.run(["systemctl", "--user", "stop", name], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "--user", "reset-failed", name], capture_output=True, timeout=10)

    def scenario(self, behavior, expected, final_state):
        with tempfile.TemporaryDirectory(prefix="monet-retry-fixture-") as tmp:
            root = Path(tmp)
            count, mode, script, bus, off = [root / name for name in ("count", "metered", "run", "busctl", "off")]
            mode.write_text("u 4")
            bus.write_text(f'#!/bin/sh\nIFS= read -r value < "{mode}" || :\nprintf "%s\\n" "$value"\n')
            bus.chmod(0o700)
            script.write_text(f'''#!/bin/sh
n=0
if [ -f "{count}" ]; then read -r n < "{count}"; fi
n=$((n + 1))
printf '%s\\n' "$n" > "{count}"
case {behavior} in
 recover) [ "$n" -ge 2 ] ;;
 metered) printf 'u 1\\n' > "{mode}"; exit 1 ;;
 off) printf 'off\\n' > "{off}"; exit 1 ;;
 *) exit 1 ;;
esac
''')
            script.chmod(0o700)
            name = "monet-update-fixture-" + uuid.uuid4().hex + ".service"
            policy = dict(line.split("=", 1) for line in UNIT.splitlines()
                          if line.startswith(("Type=", "Restart=", "StartLimitBurst=")))
            args = ["systemd-run", "--user", "--no-block", "--quiet", "--unit=" + name,
                    "--property=RestartSec=200ms", "--property=StartLimitIntervalSec=10s",
                    "--property=ConditionPathExists=!" + str(off),
                    "--property=ExecCondition=" + GATE.replace("/var/lib/monet/auto-updates-off", str(off)),
                    "--setenv=PATH=" + tmp]
            args += ["--property=" + key + "=" + value for key, value in policy.items()]
            try:
                started = subprocess.run([*args, str(script)], capture_output=True, text=True, timeout=10)
                self.assertEqual(started.returncode, 0, started.stderr)
                state = {}
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    shown = subprocess.run(["systemctl", "--user", "show", name, "--property=ActiveState,SubState,Result"],
                                           capture_output=True, text=True, timeout=5)
                    state = dict(line.split("=", 1) for line in shown.stdout.splitlines() if "=" in line)
                    if count.exists() and state.get("ActiveState") in ("failed", "inactive"):
                        break
                    time.sleep(.05)
                self.assertEqual(int(count.read_text()), expected, str(state))
                self.assertEqual(state.get("ActiveState"), final_state, str(state))
                # A terminal state must stay terminal beyond several retry intervals.
                time.sleep(1)
                self.assertEqual(int(count.read_text()), expected)
            finally:
                subprocess.run(["systemctl", "--user", "stop", name], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "--user", "reset-failed", name], capture_output=True, timeout=10)

    def test_a_temporary_failure_recovers_on_the_next_attempt(self):
        self.scenario("recover", 2, "inactive")

    def test_a_persistent_failure_stops_after_three_attempts(self):
        self.scenario("fail", 3, "failed")

    def test_switching_to_a_metered_network_cancels_the_retry(self):
        self.scenario("metered", 1, "inactive")

    def test_turning_automatic_updates_off_cancels_the_retry(self):
        self.scenario("off", 1, "inactive")
