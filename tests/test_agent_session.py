"""Regression checks for a selected live session and its on-demand reader."""
from contextlib import closing, contextmanager
from importlib.util import find_spec
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import unittest

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
from agents import MAX_READ, display, snapshot


@contextmanager
def reader(path):
    with subprocess.Popen([sys.executable, "-u", str(MODULES / "session_watch.py")],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                          env={**os.environ, "LANGUAGE": "C", "LC_ALL": "C"}) as child:
        child.stdin.write(json.dumps(str(path)) + "\n")
        child.stdin.flush()
        try:
            yield child
        finally:
            child.stdin.close()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                raise


class Session(unittest.TestCase):
    def reading(self, child):
        self.assertTrue(select.select([child.stdout], [], [], 4)[0], "reader did not publish a change")
        return json.loads(child.stdout.readline())

    def test_lifecycle_partial_events_and_numeric_scope(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "chosen.jsonl"
            events = [{"type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"cached_input_tokens": 25, "input_tokens": 40, "total_tokens": 45}}}},
                {"type": "event_msg", "payload": {"type": "turn_aborted", "reason": "PRIVATE"}},
                {"type": ["unexpected"], "message": {"content": "PRIVATE"}},
                {"type": "event_msg", "payload": {"type": []}}]
            path.write_bytes(b"x" * MAX_READ + b"\n" + b"\n".join(json.dumps(x).encode() for x in events) + b'\n{"broken"')
            self.assertEqual(snapshot(path), ({"Input": 40, "Cached input": 25, "Total": 45}, "session", "interrupted"))
            self.assertNotIn("PRIVATE", display(path))
            path.write_text(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                "total_cost_usd": 0.175, "usage": {"output_tokens": 58, "input_tokens": True}}))
            self.assertEqual(snapshot(path), ({"Output": 58, "Reported cost (USD)": 0.175}, "run", "finished"))
            path.write_text('{"type":"assistant.usage","data":{"inputTokens":8,"outputTokens":3}}\n'
                            '{"type":"session.idle","data":{"private":"PRIVATE"}}\n')
            self.assertEqual(snapshot(path), ({"Input": 8, "Output": 3}, "request", "idle"))

    def test_copilot_persisted_usage_is_summed_only_for_complete_fields(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.jsonl"
            path.write_text(json.dumps({"type": "session.shutdown", "data": {"modelMetrics": {
                "private-a": {"usage": {"inputTokens": 7, "outputTokens": 4, "cacheReadTokens": 1}},
                "private-b": {"usage": {"inputTokens": 13, "outputTokens": 2}}},
                "totalAiCredits": 0.45, "totalPremiumRequests": True}}))
            self.assertEqual(snapshot(path), ({"Input": 20, "Output": 6, "AI credits": 0.45}, "session", "ended"))
            self.assertNotIn("private-", display(path))

    @unittest.skipUnless(sys.platform == "linux" and find_spec("PySide6"), "requires Linux Qt file watching")
    def test_replace_remove_recreate_and_exit_when_parent_closes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "folder" / "session.jsonl"
            with reader(path) as child:
                self.assertIn("Could not read", self.reading(child))
                path.parent.mkdir()
                path.write_text('{"type":"event_msg","payload":{"type":"task_started"}}\n')
                self.assertIn("Turn started", self.reading(child))
                replacement = path.with_suffix(".temp")
                replacement.write_text('{"type":"event_msg","payload":{"type":"task_complete"}}\n')
                replacement.replace(path)
                self.assertIn("Turn finished", self.reading(child))
                with path.open("a") as stream:
                    stream.write('{"message":{"usage":{"input_tokens":74}}}\n')
                self.assertIn("Input 74", self.reading(child))
                path.unlink()
                os.mkfifo(path)
                self.assertIn("Could not read", self.reading(child))
                path.unlink()
                path.write_text('{"type":"session.idle"}\n')
                self.assertIn("Session idle", self.reading(child))
            self.assertEqual(child.returncode, 0)

    @unittest.skipUnless(sys.platform == "linux" and find_spec("PySide6"), "requires Linux Qt file watching")
    def test_committed_wal_and_newest_assistant_scope(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "chosen.sqlite"
            with closing(sqlite3.connect(path)) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA wal_autocheckpoint=0")
                db.execute("CREATE TABLE message(time_created INTEGER, data TEXT)")
                db.commit()
                with reader(path) as child:
                    self.assertIn("No usage figures", self.reading(child))
                    for index, data in enumerate([{"role": "assistant", "tokens": {"input": 46}, "cost": 0.002},
                                                  {"role": "user", "text": "PRIVATE"}]):
                        db.execute("INSERT INTO message VALUES(?,?)", (index, json.dumps(data)))
                    db.commit()
                    value = self.reading(child)
                    self.assertIn("Latest assistant message in this database", value)
                    self.assertIn("Input 46", value)
                    self.assertIn("Reported cost (USD) 0.002", value)
                    self.assertNotIn("PRIVATE", value)
                    (path.parent / "other").touch()
                    self.assertFalse(select.select([child.stdout], [], [], 1)[0])
