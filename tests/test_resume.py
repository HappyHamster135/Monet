"""Checkpoints contain saved work, survive interruption, and never duplicate live apps."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("resume_test", str(ROOT / "linux/libexec/monet-resume"))
r = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(r)


class WorkCheckpoint(unittest.TestCase):
    def test_unavailable_compositor_is_not_an_empty_desktop(self):
        for reader, empty in ((r.window_snapshot, []), (r.desktop_snapshot, {"windows": []})):
            with patch.object(r, "kwin_script", return_value=empty):
                self.assertEqual(reader(), empty)
            for response in (None, "broken"):
                with patch.object(r, "kwin_script", return_value=response), self.assertRaises(OSError):
                    reader()
            with patch.object(r, "kwin_script", side_effect=RuntimeError("KWin checkpoint timed out")), self.assertRaises(OSError):
                reader()

    def test_only_saved_local_editor_documents_not_recent_or_private_urls(self):
        self.assertEqual(r.documents("""[Open Documents]
Count=6
[Document 0]
URL=file:///home/j/Hello%20world.txt
[Document 1]
URL=
[Document 2]
URL=https://example.test/private
[Document 3]
URL=file:///home/j/Hello%20world.txt
[Recent Files]
URL=file:///home/j/closed.txt
[Document 4]
URL=file://another-host/share.txt
[Document 5]
URL=file:///home/j/bad%00name.txt
[Document 6]
URL=file:///home/j/already-closed.txt
"""), ["/home/j/Hello world.txt"])
        self.assertEqual(r.documents("broken = ["), [])

    def test_atomic_checkpoint_is_private_and_bad_input_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "monet/trip-apps.json"
            r.atomic_write(path, {"apps": ["a.desktop"]})
            self.assertEqual(r.read_state(path)["apps"], ["a.desktop"])
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.object(r.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    r.atomic_write(path, {"apps": []})
            self.assertEqual(r.read_state(path)["apps"], ["a.desktop"])
            self.assertFalse(list(path.parent.glob(".trip-*")))
            path.write_text("not json")
            self.assertEqual(r.read_state(path), {})

    def test_only_next_boot_and_recent_checkpoint_is_eligible(self):
        state = {"version": 2, "time": 100, "boot": "old", "apps": []}
        self.assertTrue(r.usable(state, 110, "new", 50))
        for now, boot in ((110, "old"), (151, "new"), (99, "new")):
            self.assertFalse(r.usable(state, now, boot, 50))
        for stamp in ("100", None, float("nan"), float("inf")):
            self.assertFalse(r.usable(dict(state, time=stamp), 110, "new", 50))

    def test_oversized_checkpoint_preserves_the_previous_readable_copy(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, "LIMIT", 100):
            path = Path(tmp) / "trip.json"
            original = {"apps": ["a.desktop"]}
            r.atomic_write(path, original)
            with self.assertRaises(OSError):
                r.atomic_write(path, {"metadata": "x" * 100})
            self.assertEqual(r.read_state(path), original)
            self.assertFalse(list(path.parent.glob(".trip-*")))

    def test_unplugged_or_scaled_display_keeps_window_reachable(self):
        saved = {"area": {"x": 1920, "y": 0, "width": 1920, "height": 1080},
                 "rect": {"x": 2800, "y": 700, "width": 1000, "height": 800}}
        area = {"x": 0, "y": 36, "width": 1280, "height": 684}
        self.assertEqual(r.placed_rect(saved, area), {"x": 280, "y": 36, "width": 1000, "height": 684})
        saved["rect"]["x"] = float("nan")
        self.assertIsNone(r.placed_rect(saved, area))

    def test_geometry_never_applies_to_preexisting_windows(self):
        old = {"app": "a.desktop", "role": "", "rect": {}}
        current = [{"app": "a.desktop", "role": "", "id": "already-open"}]
        with patch.object(r, "kwin_script") as script:
            r.place_windows([old], current, {"already-open"})
            script.assert_not_called()

    def test_documents_are_arguments_not_a_shell_and_missing_files_are_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "some notes; do not execute.txt"
            doc.write_text("saved work")
            app = "org.kde.kate.desktop"
            saved = {"documents": {app: [str(doc), str(doc) + "-missing", "--eval=bad"]}}
            # Linux paths only; Windows still exercises parser/state tests above.
            with patch.object(r.Path, "is_file", return_value=True), patch.object(r.subprocess, "Popen") as start:
                r.start_app(app, {"documents": {app: ["/tmp/some notes; do not execute.txt", "--eval=bad"]}}, lambda _: None)
                self.assertEqual(start.call_args.args[0], ["kate", "--new", "--startanon", "--", "/tmp/some notes; do not execute.txt"])
                r.start_app("org.kde.kwrite.desktop", {"documents": {"org.kde.kwrite.desktop": ["/home/j/notes.txt"]}}, lambda _: None)
                self.assertEqual(start.call_args.args[0], ["kwrite", "--", "/home/j/notes.txt"])
            with patch.object(r.subprocess, "Popen") as start:
                launched = []
                r.start_app(app, {"documents": {app: ["/definitely-missing-monet-document"]}}, launched.append)
                start.assert_not_called()
                self.assertEqual(launched, [app])


@unittest.skipIf(os.name == "nt", "Linux advisory lock")
class RestoreReceipt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trip.json"
        self.off = self.path.with_name("off")
        self.state = {"version": 2, "time": 100, "boot": "old", "apps": ["a.desktop", "b.desktop"], "windows": [], "done": []}
        r.atomic_write(self.path, self.state)
        for target, value in (("boot_id", "new"), ("window_snapshot", [])):
            p = patch.object(r, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        for target, value in (("time", 110), ("sleep", None)):
            p = patch.object(r.time, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def restore(self, launch, running=()):
        return r.restore(self.path, self.off, lambda: running, lambda _: True, launch)

    def test_failed_launch_keeps_snapshot_and_success_receipt_is_not_replayed(self):
        r.window_snapshot.side_effect = [[], [{"app": "a.desktop", "id": "new"}]] + [[]] * 20
        started = []
        self.assertEqual(self.restore(started.append), ["a.desktop"])
        self.assertEqual(r.read_state(self.path)["done"], ["a.desktop"])
        r.window_snapshot.side_effect = [[], [{"app": "b.desktop", "id": "new-b"}]]
        self.assertEqual(self.restore(started.append), ["b.desktop"])
        self.assertEqual(started, ["a.desktop", "b.desktop", "b.desktop"])
        self.assertFalse(self.path.exists())

    def test_already_running_apps_are_not_reopened(self):
        started = []
        self.assertEqual(self.restore(started.append, ("a.desktop", "b.desktop")), [])
        self.assertEqual(started, [])
        self.assertFalse(self.path.exists())

    def test_failed_initial_snapshot_preserves_work_and_retry_reuses_live_apps(self):
        r.window_snapshot.side_effect = OSError("compositor unavailable")
        started = []
        self.assertEqual(self.restore(started.append), [])
        self.assertEqual(started, [])
        self.assertEqual(r.read_state(self.path)["done"], [])
        self.assertTrue(all(item["status"] == "unconfirmed" for item in r.read_return(self.path)["items"].values()))
        r.window_snapshot.side_effect = None
        r.window_snapshot.return_value = [{"id": app, "app": app} for app in self.state["apps"]]
        self.assertEqual(self.restore(started.append), [])
        self.assertEqual(started, [])
        self.assertFalse(self.path.exists())

    def test_off_switch_clears_checkpoint_without_launching(self):
        self.off.touch()
        started = []
        self.assertEqual(self.restore(started.append), [])
        self.assertFalse(self.path.exists())
        self.assertEqual(started, [])

    def test_same_boot_keeps_checkpoint_and_does_not_launch(self):
        r.boot_id.return_value = "old"
        started = []
        self.assertEqual(self.restore(started.append), [])
        self.assertTrue(self.path.exists())
        self.assertEqual(started, [])

    def test_concurrent_restore_does_not_start_duplicates(self):
        import fcntl
        with self.path.with_suffix(".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = []
            self.assertEqual(self.restore(started.append), [])
            self.assertEqual(started, [])


if __name__ == "__main__":
    unittest.main()
