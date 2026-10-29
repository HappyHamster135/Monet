"""Independent windows/profiles keep their own receipts through partial recovery."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r

b, f = r.browser_helper(), r.files_helper()
ONE = {"tabs": [{"folders": ["/one"], "active": 0}], "active": 0}
TWO = {"tabs": [{"folders": ["/two", "/three"], "active": 1}], "active": 0}


class GroupCapture(unittest.TestCase):
    def test_shared_process_windows_keep_exact_frames_and_fail_closed_without_identity(self):
        frames = [{"app": r.FILES, "pid": 42, "id": "{" + str(i) * 8 + "-1111-2222-3333-444444444444}"} for i in (1, 2)]
        states = [{"id": w["id"], "files": s} for w, s in zip(frames, (ONE, TWO))]
        with patch.object(f, "capture", return_value=list(reversed(states))) as capture:
            groups = r.checkpoint([r.FILES], frames)["groups"][r.FILES]
            self.assertEqual(groups, [{"files": s, "windows": [w]} for w, s in zip(frames, (ONE, TWO))])
            capture.assert_called_once_with(42, windows=True)
            capture.return_value = states[:1]
            self.assertEqual([g["files"] for g in r.checkpoint([r.FILES], frames)["groups"][r.FILES]], [None, None])

    def test_no_identified_browser_window_never_falls_back_to_default_profile(self):
        self.assertEqual(r.checkpoint([r.BROWSER], [])["browser"], {"mode": "skip"})

    def test_profiles_are_captured_independently_with_their_own_frames(self):
        frames = [{"app": r.BROWSER, "pid": pid, "id": str(i)} for i, pid in enumerate((1, 1, 2, 3))]
        def capture(own):
            return {"mode": "skip"} if own[0]["pid"] == 3 else {"mode": "native", "profile": str(own[0]["pid"])}
        with patch.object(b, "capture", side_effect=capture), patch.object(r.time, "sleep"):
            groups = r.checkpoint([r.BROWSER], frames)["groups"][r.BROWSER]
        self.assertEqual([g["browser"] for g in groups],
                         [{"mode": "native", "profile": "1"}, {"mode": "native", "profile": "2"}, {"mode": "skip"}])
        self.assertEqual([len(g["windows"]) for g in groups], [2, 1, 1])

    def test_fewer_native_windows_cannot_be_reported_as_full_recovery(self):
        with patch.object(b, "valid", return_value=True), patch.object(b, "profile_path", return_value=Path("/test")), \
                patch.object(b, "private_profile", return_value=False), patch.object(b, "native_enabled", return_value=True), \
                patch.object(b, "snapshot", return_value={"windows": 1, "tabs": 2, "session": 1, "updated": 3}):
            self.assertIsNone(b.prepare({"profile": "work", "session": 1, "updated": 2, "windows": 2}))


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class IndependentRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "trip.json"; self.off = self.path.with_name("off")
        self.live, self.launches = [], []
        for owner, name, value in ((r, "boot_id", "new"), (r.time, "time", 110), (r.time, "sleep", None),
                                   (r, "place_windows", []), (f, "cleanup", None)):
            patcher = patch.object(owner, name, return_value=value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(r, "window_snapshot", side_effect=lambda: list(self.live))
        patcher.start(); self.addCleanup(patcher.stop)

    def save(self, app, groups):
        r.atomic_write(self.path, {"version": 2, "time": 100, "boot": "old", "apps": [app],
                                   "done": [], "groups": {app: copy.deepcopy(groups)}})

    def restore(self):
        return r.restore(self.path, self.off, lambda: [w["app"] for w in self.live], lambda _: True,
                         lambda _: self.fail("Generic launch cannot pick a profile or window group"))

    def test_an_open_profile_does_not_suppress_a_missing_profile_or_reopen_private(self):
        self.live = [{"id": "work", "pid": 11, "app": r.BROWSER}]
        owners = {"work": 11}
        self.save(r.BROWSER, [{"browser": {"mode": "native", "profile": name}} for name in ("work", "home")]
                  + [{"browser": {"mode": "skip"}}])
        def launch(state):
            self.launches.append(state["profile"]); owners[state["profile"]] = 22
            self.live.append({"id": "home", "pid": 22, "app": r.BROWSER})
            return 22
        with patch.object(b, "valid", side_effect=lambda s: s.get("mode") == "native"), \
                patch.object(b, "owner", side_effect=lambda name: owners.get(name)), \
                patch.object(b, "prepare", return_value={"restore": False}), patch.object(b, "process_start", return_value=1), \
                patch.object(b, "launch", side_effect=launch), patch.object(b, "ready", return_value=22), \
                patch.object(b, "profile_path", return_value=None):
            self.assertEqual(self.restore(), [r.BROWSER])
        self.assertEqual(self.launches, ["home"])
        self.assertEqual(self.live[0], {"id": "work", "pid": 11, "app": r.BROWSER})
        self.assertFalse(self.path.exists())
        self.assertEqual(r.read_state(r.return_path(self.path))["items"][r.BROWSER]["status"], "partly-restored")

    def test_browser_partial_return_reuses_pending_launch_without_replaying_completed_profile(self):
        self.save(r.BROWSER, [{"browser": {"mode": "native", "profile": n}} for n in ("work", "home")])
        owners, ready = {}, {"work"}
        def launch(state):
            name = state["profile"]; pid = 10 + len(owners); owners[name] = pid; self.launches.append(name)
            self.live.append({"id": name, "pid": pid, "app": r.BROWSER}); return pid
        with patch.object(b, "valid", return_value=True), patch.object(b, "owner", side_effect=lambda n: owners.get(n)), \
                patch.object(b, "launching", return_value=True), patch.object(b, "prepare", return_value={"restore": False}), \
                patch.object(b, "process_start", return_value=1), patch.object(b, "launch", side_effect=launch), \
                patch.object(b, "ready", side_effect=lambda s, _: owners[s["profile"]] if s["profile"] in ready else None), \
                patch.object(b, "profile_path", return_value=None):
            self.assertEqual(self.restore(), [])
            groups = r.read_state(self.path)["groups"][r.BROWSER]
            self.assertEqual([g["status"] for g in groups], ["browser-opened", "unconfirmed"])
            self.assertIn("browser_launch", groups[1])
            ready.add("home")
            self.assertEqual(self.restore(), [r.BROWSER])
        self.assertEqual(self.launches, ["work", "home"])
        self.assertFalse(self.path.exists())

    def test_files_partial_return_keeps_success_and_retries_only_missing_folders(self):
        self.save(r.FILES, [{"files": ONE}, {"files": TWO}])
        states, available = {}, [False]
        def start(state):
            if state == TWO and not available[0]:
                raise OSError("drive disconnected")
            pid = 20 + len(states); states[pid] = state; self.launches.append(state)
            self.live.append({"id": str(pid), "pid": pid, "app": r.FILES})
            return Path("dolphin_monet-" + "a" * 32 + "_"), pid
        with patch.object(f, "start", side_effect=start), patch.object(f, "capture", side_effect=lambda pid: states.get(pid)), \
                patch.object(f, "alive", return_value=True):
            self.assertEqual(self.restore(), [])
            self.assertEqual(r.read_state(self.path)["groups"][r.FILES][0]["status"], "folders-restored")
            available[0] = True
            self.assertEqual(self.restore(), [r.FILES])
        self.assertEqual(self.launches, [ONE, TWO])
        self.assertEqual(len(self.live), 2)

    def test_cancelled_switch_reopens_only_the_files_window_that_closed(self):
        self.save(r.FILES, [{"files": ONE}, {"files": TWO}])
        self.live = [{"id": "survived", "pid": 10, "app": r.FILES}]
        def start(state):
            self.assertEqual(state, TWO)
            self.live.append({"id": "restored", "pid": 20, "app": r.FILES})
            return Path("dolphin_monet-" + "a" * 32 + "_"), 20
        with patch.object(f, "start", side_effect=start) as launch, \
                patch.object(f, "capture", side_effect=lambda pid: ONE if pid == 10 else TWO), \
                patch.object(f, "alive", return_value=True):
            self.assertEqual(self.restore(), [r.FILES])
            launch.assert_called_once()
        self.assertEqual([w["id"] for w in r.place_windows.call_args.args[1]], ["restored"])
        self.assertEqual(self.live[0]["id"], "survived")

    def test_identical_saved_files_windows_count_separately(self):
        self.save(r.FILES, [{"files": ONE}, {"files": ONE}])
        self.live = [{"id": "existing", "pid": 10, "app": r.FILES}]
        def start(state):
            self.live.append({"id": "second", "pid": 20, "app": r.FILES})
            return Path("dolphin_monet-" + "a" * 32 + "_"), 20
        with patch.object(f, "start", side_effect=start) as launch, patch.object(f, "capture", return_value=ONE), \
                patch.object(f, "alive", return_value=True):
            self.assertEqual(self.restore(), [r.FILES])
            launch.assert_called_once()

    def test_existing_shared_process_windows_each_satisfy_one_group(self):
        self.save(r.FILES, [{"files": ONE}, {"files": ONE}])
        self.live = [{"id": name, "pid": 10, "app": r.FILES} for name in ("first", "second")]
        with patch.object(f, "capture", return_value=[{"id": w["id"], "files": ONE} for w in self.live]), \
                patch.object(f, "start") as start:
            self.assertEqual(self.restore(), [])
            self.assertFalse(self.path.exists())
            start.assert_not_called()
            r.place_windows.assert_not_called()

    def test_pending_receipt_reserves_its_window_before_identical_sibling_can_match(self):
        receipt = {"boot": "new", "pid": 20, "session": "dolphin_monet-" + "a" * 32 + "_"}
        self.save(r.FILES, [{"files": ONE}, {"files": ONE, "files_launch": receipt}])
        self.live = [{"id": "pending", "pid": 20, "app": r.FILES}]
        def start(state):
            self.live.append({"id": "new", "pid": 30, "app": r.FILES})
            return Path("dolphin_monet-" + "b" * 32 + "_"), 30
        with patch.object(f, "capture", return_value=ONE), patch.object(f, "alive", return_value=True), \
                patch.object(f, "start", side_effect=start) as launch:
            self.assertEqual(self.restore(), [r.FILES])
            launch.assert_called_once()
        self.assertEqual(len(self.live), 2)

    def test_same_process_survivors_keep_changed_tabs_and_closed_sibling_reopens(self):
        frames = [{"id": name, "app": r.FILES, "pid": 10} for name in ("closed", "first", "second")]
        self.save(r.FILES, [{"files": ONE, "windows": [w]} for w in frames])
        state = r.read_state(self.path)
        state.update(version=3, boot="new", cancelled_boot="new", id="a" * 32)
        r.atomic_write(self.path, state)
        self.live = frames[1:]
        def capture(pid, **kwargs):
            return [{"id": w["id"], "files": TWO} for w in frames[1:]] if kwargs else ONE
        def start(state):
            self.live.append({"id": "restored", "pid": 20, "app": r.FILES})
            return Path("dolphin_monet-" + "a" * 32 + "_"), 20
        with patch.object(f, "capture", side_effect=capture), patch.object(f, "alive", return_value=True), \
                patch.object(f, "start", side_effect=start) as launch:
            self.assertEqual(self.restore(), [r.FILES])
            launch.assert_called_once()
        self.assertEqual([w["id"] for w in r.place_windows.call_args.args[0]], ["closed"])

    def test_cancelled_identical_folders_keep_the_survivors_identity_and_the_closed_windows_position(self):
        self.save(r.FILES, [{"files": ONE, "windows": [{"id": "closed", "app": r.FILES}]},
                            {"files": ONE, "windows": [{"id": "survived", "app": r.FILES}]}])
        state = r.read_state(self.path)
        state.update(version=3, boot="new", cancelled_boot="new", id="a" * 32)
        r.atomic_write(self.path, state)
        self.live = [{"id": "survived", "pid": 10, "app": r.FILES}]
        def start(state):
            self.live.append({"id": "restored", "pid": 20, "app": r.FILES})
            return Path("dolphin_monet-" + "a" * 32 + "_"), 20
        with patch.object(f, "start", side_effect=start) as launch, patch.object(f, "capture", return_value=ONE), \
                patch.object(f, "alive", return_value=True):
            self.assertEqual(self.restore(), [r.FILES]); launch.assert_called_once()
        self.assertEqual([w["id"] for w in r.place_windows.call_args.args[0]], ["closed"])

    def test_malformed_group_cannot_fall_back_to_a_default_profile(self):
        for groups in (None, [], [None], [{}] * (r.MAX_APPS + 1)):
            self.save(r.BROWSER, groups)
            with patch.object(b, "launch") as launch:
                self.assertEqual(self.restore(), [])
                launch.assert_not_called()

    def test_off_can_discard_malformed_files_groups(self):
        self.save(r.FILES, None)
        self.off.touch()
        self.assertEqual(self.restore(), [])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
