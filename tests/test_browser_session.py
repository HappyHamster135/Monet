"""Native browser recovery must never switch profiles or resurrect private data."""
import copy
import ctypes
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tests.test_resume import r

b = r.browser_helper()


def fixture():
    return {"session": {"startTime": 1000, "lastUpdate": 5000},
            "windows": [{"tabs": [{"entries": [{"url": "https://example.test/one"}], "index": 1, "pinned": True},
                                  {"entries": [{"url": "https://example.test/two"}], "index": 1}]}],
            "cookies": [{"value": "secret-cookie"}], "_closedWindows": [{"url": "closed-private-data"}]}


class BrowserSession(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "zen"
        self.profile = self.root / "work profile"
        self.profile.mkdir(parents=True)
        p = patch.object(b, "root", return_value=self.root)
        p.start(); self.addCleanup(p.stop)
        self.saved = {"mode": "native", "profile": "work profile", "session": 1000, "updated": 5000, "windows": 1, "tabs": 2, "restore": True}

    def test_metadata_has_no_urls_cookies_titles_or_closed_tabs(self):
        state = b.summary(fixture())
        encoded = json.dumps(state)
        self.assertEqual(state["tabs"], 2)
        for secret in ("example.test", "secret-cookie", "closed-private-data"):
            self.assertNotIn(secret, encoded)
        changed = fixture()
        changed["windows"][0]["tabs"].reverse()
        self.assertNotEqual(state["digest"], b.summary(changed)["digest"])

    def test_zen_placeholder_is_not_a_user_blank_tab(self):
        state = fixture()
        expected = b.summary(state)
        state["windows"][0]["tabs"].insert(1, {"entries": [{"url": "about:blank"}], "zenIsEmpty": True})
        self.assertEqual(b.summary(state), expected)
        state["windows"][0]["tabs"][1]["zenIsEmpty"] = False
        self.assertEqual(b.summary(state)["tabs"], expected["tabs"] + 1)
        state["windows"][0]["tabs"][1].update(zenIsEmpty=True, groupId="saved-split")
        self.assertEqual(b.summary(state)["tabs"], expected["tabs"] + 1)

    def test_private_or_unsupported_payload_never_enters_native_restore(self):
        for flag in ("isPrivate", "isZenUnsynced"):
            state = fixture(); state["windows"][0][flag] = True
            self.assertIsNone(b.summary(state))
        state = fixture(); state["windows"][0]["tabs"][0]["isPrivate"] = True
        self.assertIsNone(b.summary(state))
        for malformed in ({}, {"windows": None}, dict(fixture(), session={"startTime": float("nan"), "lastUpdate": 1})):
            self.assertIsNone(b.summary(malformed))

    def test_profiles_are_confined_and_missing_profiles_are_not_created(self):
        for name in ("../elsewhere", str(self.root), "", None, "missing", "bad\nprofile"):
            self.assertIsNone(b.profile_path(name))
        self.assertEqual(b.profile_path("work profile"), self.profile.resolve())
        if os.name != "nt":
            (self.root / "escape").symlink_to(self.root.parent, target_is_directory=True)
            self.assertIsNone(b.profile_path("escape"))

    def test_capture_rejects_previous_run_or_multiple_profiles(self):
        frames = [{"app": b.APP, "pid": 42}]
        state = dict(b.summary(fixture()), written=500)
        with patch.object(b, "profile_for_pid", return_value="work profile"), \
                patch.object(b, "private_start", return_value=False), \
                patch.object(b, "snapshot", return_value=state), patch.object(b, "process_start", return_value=400):
            self.assertEqual(b.capture(frames), self.saved)
            state["written"] = 300
            self.assertEqual(b.capture(frames), {"mode": "skip"})
            self.assertEqual(b.capture(frames + [{"app": b.APP, "pid": 43}]), {"mode": "skip"})

    def test_deleted_or_replaced_native_session_is_not_resurrected(self):
        with patch.object(b, "snapshot", return_value=None):
            self.assertIsNone(b.prepare(self.saved))
        state = b.summary(fixture())
        with patch.object(b, "snapshot", return_value=dict(state, session=2000)):
            self.assertIsNone(b.prepare(self.saved))
        with patch.object(b, "snapshot", return_value=state):
            self.assertEqual(b.prepare(self.saved)["digest"], state["digest"])

    def test_multiple_synced_windows_verify_what_zen_will_actually_restore(self):
        state = fixture(); state["windows"].append(copy.deepcopy(state["windows"][0]))
        state["windows"][1]["tabs"][1]["entries"][0]["url"] = "https://example.test/newer"
        sidebar = {"lastCollected": 6000, "tabs": state["windows"][1]["tabs"]}
        expected = copy.deepcopy(state)
        expected["windows"][0]["tabs"] = copy.deepcopy(sidebar["tabs"])
        with patch.object(b, "read_session", return_value=sidebar):
            self.assertEqual(b.restored_summary(self.profile, state)["digest"], b.summary(expected)["digest"])
            (self.profile / "user.js").write_text('user_pref("zen.window-sync.enabled", false);\n')
            self.assertEqual(b.restored_summary(self.profile, state), b.summary(state))
            (self.profile / "user.js").write_text('user_pref("zen.window-sync.sync-only-pinned-tabs", true);\n')
            self.assertEqual(b.restored_summary(self.profile, state), b.summary(state))
        for bad in (None, {"lastCollected": float("nan"), "tabs": []}, {"lastCollected": 1, "tabs": []},
                    {"lastCollected": 6000, "tabs": [{"isPrivate": True}]}):
            with patch.object(b, "read_session", return_value=bad):
                self.assertIsNone(b.restored_summary(self.profile, state))

    def test_start_preserves_browser_preferences_and_uses_original_profile(self):
        prefs = self.profile / "prefs.js"
        prefs.write_text('user_pref("browser.startup.page", 0);\n')
        original = prefs.read_bytes()
        self.assertEqual(b.prepare(self.saved), {"restore": False})
        with patch.object(b, "owner", return_value=None), patch.object(b.subprocess, "Popen") as start:
            start.return_value.pid = 42
            self.assertEqual(b.launch(self.saved), 42)
            self.assertEqual(start.call_args.args[0], ["flatpak", "run", b.FLATPAK, "--new-instance", "--profile", str(self.profile.resolve())])
            self.assertEqual(prefs.read_bytes(), original)
        with patch.object(b, "owner", return_value=42), patch.object(b.subprocess, "Popen") as start:
            with self.assertRaises(OSError): b.launch(self.saved)
            start.assert_not_called()

    def test_private_preference_and_startup_preference_override_are_respected(self):
        (self.profile / "prefs.js").write_text('user_pref("browser.startup.page", 0);\n')
        self.assertFalse(b.native_enabled(self.profile))
        (self.profile / "user.js").write_text('user_pref("browser.startup.page", 3);\n')
        self.assertTrue(b.native_enabled(self.profile))
        (self.profile / "user.js").write_text('user_pref("browser.privatebrowsing.autostart", true);\n')
        self.assertIsNone(b.prepare(self.saved))

    def test_ready_requires_new_native_write_and_matching_tabs(self):
        state = dict(b.summary(fixture()), written=600)
        receipt = {"started": 500, "expected": state}
        with patch.object(b, "owner", return_value=42), patch.object(b, "snapshot", return_value=state):
            self.assertEqual(b.ready(self.saved, receipt), 42)
            self.assertIsNone(b.ready(self.saved, dict(receipt, started=700)))
            self.assertIsNone(b.ready(self.saved, dict(receipt, expected={"digest": "wrong"})))

    def test_jsonlz4_limits_corruption_and_real_round_trip(self):
        path = self.profile / "sessionstore.jsonlz4"
        for data in (b"not lz4", b"mozLz40\0" + struct.pack("<I", b.LIMIT + 1),
                     b"mozLz40\0" + struct.pack("<I", 10) + b"invalid"):
            path.write_bytes(data); self.assertIsNone(b.read_session(path))
        try: library = ctypes.CDLL("liblz4.so.1")
        except OSError: self.skipTest("Linux LZ4 runtime")
        source = json.dumps(fixture()).encode()
        output = ctypes.create_string_buffer(len(source) * 2)
        compress = library.LZ4_compress_default
        compress.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        size = compress(source, output, len(source), len(output))
        self.assertGreater(size, 0)
        path.write_bytes(b"mozLz40\0" + struct.pack("<I", len(source)) + output.raw[:size])
        self.assertEqual(b.read_session(path), fixture())


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class BrowserReceipt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trip.json"; self.off = self.path.with_name("off")
        self.state = {"version": 2, "time": 100, "boot": "old", "apps": [b.APP], "done": [],
                      "browser": {"mode": "native", "profile": "work"}}
        for owner, name, value in ((r, "boot_id", "new"), (r.time, "time", 110), (r.time, "sleep", None),
                                   (r, "window_snapshot", []), (b, "valid", True), (b, "launching", False),
                                   (b, "process_start", 110), (b, "prepare", {"digest": "expected"}),
                                   (b, "launch", 42)):
            p = patch.object(owner, name, return_value=value); p.start(); self.addCleanup(p.stop)
        r.atomic_write(self.path, self.state)

    def restore(self):
        return r.restore(self.path, self.off, lambda: [], lambda _: True, lambda _: self.fail("generic browser launch"))

    def test_slow_launch_keeps_receipt_and_retry_does_not_launch_twice(self):
        with patch.object(b, "ready", return_value=None):
            self.assertEqual(self.restore(), [])
        self.assertTrue(self.path.exists()); b.launch.assert_called_once()
        b.launching.return_value = True
        r.window_snapshot.return_value = [{"id": "new", "app": b.APP, "pid": 42}]
        with patch.object(b, "ready", return_value=42):
            self.assertEqual(self.restore(), [b.APP])
        b.launch.assert_called_once(); self.assertFalse(self.path.exists())

    def test_private_only_checkpoint_does_not_open_default_profile(self):
        self.state["browser"] = {"mode": "skip"}; r.atomic_write(self.path, self.state)
        self.assertEqual(self.restore(), []); b.launch.assert_not_called()
        self.assertFalse(self.path.exists())
        self.assertEqual(r.return_status(self.path, self.off)["items"][0]["status"], "browser-skipped")

    def test_summary_distinguishes_verified_tabs_from_normal_browser_startup(self):
        with patch.object(b, "ready", return_value=42), patch.object(b, "profile_path", return_value=Path("/test-profile")), \
                patch.object(b, "native_enabled", return_value=True) as enabled:
            for preference, expected, status in ((True, {"digest": "expected"}, "browser-restored"),
                                                (False, {"digest": "expected"}, "browser-opened"),
                                                (True, {"restore": False}, "browser-opened")):
                enabled.return_value = preference; b.prepare.return_value = expected
                r.window_snapshot.side_effect = [[], [{"id": "browser", "app": b.APP, "pid": 42}]]
                r.atomic_write(self.path, self.state)
                self.assertEqual(self.restore(), [b.APP])
                self.assertEqual(r.return_status(self.path, self.off)["items"][0]["status"], status)

    def test_user_opened_browser_is_not_restarted(self):
        r.window_snapshot.return_value = [{"id": "existing", "app": b.APP, "pid": 12}]
        with patch.object(b, "owner", return_value=12):
            self.assertEqual(self.restore(), [])
        b.launch.assert_not_called()

    def test_off_stops_restore_without_launch(self):
        self.off.touch(); self.assertEqual(self.restore(), []); b.launch.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_browser_deleted_its_session_and_launcher_failure(self):
        b.prepare.return_value = None
        self.assertEqual(self.restore(), []); b.launch.assert_not_called()
        self.assertFalse(self.path.exists())
        r.atomic_write(self.path, self.state); b.prepare.return_value = {"digest": "expected"}
        b.launch.side_effect = OSError("unavailable")
        self.assertEqual(self.restore(), []); self.assertTrue(self.path.exists())
