"""Check the Claude Code control protocol and independent account view settings."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
import claude_limits
try:
    from PySide6.QtCore import QSettings
    import codex_limits as accounts
except ImportError:
    accounts = None


class ClaudeProtocol(unittest.TestCase):
    def test_windows_require_a_reported_percentage_and_a_current_reset(self):
        now = datetime.now(timezone.utc)
        future = (now + timedelta(hours=2)).isoformat()
        recent = (now - timedelta(seconds=1)).isoformat()
        data = {"five_hour": {"utilization": 12.5, "resets_at": future},
                "seven_day": {"utilization": 0, "resets_at": None},
                "seven_day_opus": {"utilization": 27, "resets_at": recent},
                "seven_day_sonnet": {"utilization": True},
                "model_scoped": [{"display_name":"Opus","utilization":10},
                                 {"display_name":"Opus","utilization":20},
                                 {"display_name":"Invalid\nlabel","utilization":5},
                                 {"display_name":"Unknown reset","utilization":5,"resets_at":"tomorrow"},
                                 {"display_name":"Invalid count","utilization":float("nan")}]}
        rows = claude_limits.windows({"rate_limits": data}, now.timestamp())
        self.assertEqual([r["left"] for r in rows], [87.5, 100, 90])
        self.assertEqual(rows[0]["reset"], int(datetime.fromisoformat(future).timestamp()))
        self.assertEqual(rows[-1]["scope"], "Opus")

    def test_control_requests_and_plain_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cli = folder / "claude"
            cli.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
root = Path(__file__).parent
assert os.getcwd() == "/"
assert "--safe-mode" in sys.argv and "--no-session-persistence" in sys.argv
assert sys.argv[sys.argv.index("--tools")+1] == ""
assert os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
for step in ("initialize","get_usage"):
    command=json.loads(input())
    assert command["type"] == "control_request"
    assert command["request"] == ({"subtype":step} if step == "initialize" else {"subtype":step,"skip_behaviors":True})
    reply = {"subtype":"success", "response":{}} if step == "initialize" else json.loads((root/"response").read_text())
    print(json.dumps({"type":"control_response","response":{"request_id":"unrelated",**reply}}),flush=True)
    print(json.dumps({"type":"control_response","response":{"request_id":command["request_id"],**reply}}),flush=True)
''')
            cli.chmod(0o700)
            for response, state in [
                ({"subtype":"success","response":{"rate_limits_available":False}}, "no-plan"),
                ({"subtype":"success","response":{"rate_limits_available":True,"rate_limits":{}}}, "empty"),
                ({"subtype":"error","error":"Unsupported control request subtype"}, "outdated"),
                ({"subtype":"error","error":"Authentication required"}, "sign-in")]:
                with self.subTest(state=state):
                    (folder / "response").write_text(json.dumps(response))
                    self.assertEqual(asyncio.run(claude_limits.fetch(str(cli))), (state, []))


@unittest.skipUnless(accounts, "requires Qt preferences")
class AccountPreferences(unittest.TestCase):
    def test_provider_consent_and_hidden_tools_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = QSettings(str(Path(tmp)/"settings.ini"), QSettings.IniFormat)
            with patch.object(accounts, "cache_file", side_effect=lambda k,p: Path(tmp)/(p+k)), \
                 patch.object(accounts, "executable", return_value="/fixture/claude"), \
                 patch.object(claude_limits, "fetch") as query:
                rows = [{"window":"five_hour","minutes":300,"scope":"","left":62.5,"reset":0}]
                query.return_value = ("ready", rows)
                accounts.enable(settings, True)
                self.assertEqual(accounts.snapshot(settings, provider="claude")["state"], "off")
                query.assert_not_called()
                accounts.enable(settings, True, "claude")
                reading = accounts.snapshot(settings, provider="claude")
                rendered = accounts.display(reading, "claude")
                self.assertTrue(rendered["summary"].startswith("Claude Code · "))
                self.assertEqual(rendered["rows"][0]["value"], 62.5)
                self.assertEqual(accounts.snapshot(settings, provider="claude"), reading)
                query.assert_awaited_once()
                settings.setValue("hidden", '["agents"]')
                self.assertEqual(accounts.snapshot(settings, True, "claude")["state"], "off")
                query.assert_awaited_once()
                settings.setValue("hidden", "[]")
                accounts.enable(settings, False, "claude")
                self.assertTrue(accounts.generation(settings, "codex"))
                self.assertFalse(accounts.generation(settings, "claude"))
                self.assertFalse((Path(tmp)/("claude"+reading["generation"])).exists())
