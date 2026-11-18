"""Your work after a restart: kept fresh while you work, reopened once at the next sign-in,
never twice, on the same screens; trips to Windows keep their own checkpoint."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r
from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("monet_work_test", str(ROOT / "linux/libexec/monet-work"))
w = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(w)

KATE, FILES, ZEN = "org.kde.kate.desktop", r.FILES, r.BROWSER


def qt_app():
    """One Qt application for the whole module: the Settings window needs a GUI one."""
    from PySide6.QtCore import QCoreApplication
    try:
        from PySide6.QtGui import QGuiApplication
    except ImportError:
        return QCoreApplication.instance() or QCoreApplication([])
    return QCoreApplication.instance() or QGuiApplication([])


class WhenToLook(unittest.TestCase):
    """monet-work's timing, with a pretend clock: no busy polling, nothing while it shouldn't."""

    def setUp(self):
        self.watch = w.Watch(0)

    def due(self, now, **kwargs):
        return self.watch.due(now, kwargs.get("settled", True), kwargs.get("departing", False))

    def test_first_look_of_a_sign_in_waits_for_its_reopening(self):
        self.assertIsNone(self.due(1, settled=False))
        self.assertEqual(self.watch.wait(1), w.SETTLE - 1)  # One timer, not a poll.
        self.assertEqual(self.due(2, settled=True), "picture")
        self.assertEqual(w.Watch(0).due(w.SETTLE, False, False), "picture")  # Never forever.

    def test_changes_settle_before_a_picture_and_a_stream_of_them_is_bounded(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.changed(10)
        self.assertIsNone(self.due(11))
        self.assertAlmostEqual(self.watch.wait(11), w.QUIET - 1)
        self.assertEqual(self.due(10 + w.QUIET), "picture")
        self.watch.pictured(13, self.watch.taken(), [])
        for second in range(20, 20 + w.LONGEST):
            self.watch.changed(second)  # A window dragged around for half a minute.
            self.assertIsNone(self.due(second + 0.5))
        self.assertEqual(self.due(20 + w.LONGEST), "picture")

    def test_nothing_changes_nothing_is_written_except_documents_now_and_then(self):
        self.watch.pictured(0, self.watch.taken(), ["org.kde.konsole.desktop"])
        self.assertIsNone(self.due(10000))
        self.assertIsNone(self.watch.wait(10000))
        self.watch.pictured(0, self.watch.taken(), [KATE])
        self.assertIsNone(self.due(w.REFRESH - 1))
        self.assertEqual(self.due(w.REFRESH), "picture")

    def test_nothing_while_the_screen_is_locked(self):
        self.watch.pictured(0, self.watch.taken(), [KATE])
        self.watch.lock(True)
        self.watch.changed(5)
        self.assertIsNone(self.due(w.REFRESH * 3))
        self.assertIsNone(self.watch.wait(w.REFRESH * 3))
        self.watch.lock(False)
        self.assertEqual(self.due(w.REFRESH * 3), "picture")

    def test_closes_before_a_restart_are_taken_out_and_the_logouts_own_are_not(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.window_closed("{closed-by-you}", 10)
        self.watch.leave("logout")
        self.watch.window_closed("{closed-by-the-logout}", 10.5)
        self.assertEqual(self.watch.wait(10.5), 0.2)
        self.assertEqual(self.due(10.5), "trim")
        self.assertEqual(self.watch.closed, {"{closed-by-you}"})
        self.watch.trimmed({"{closed-by-you}"})
        for later in (11, 100, 10000):
            self.assertIsNone(self.due(later))
        self.assertIsNone(self.watch.wait(10000))

    def test_a_cancelled_sign_out_looks_again_after_a_while(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.leave("logout")
        self.watch.stay("logout", 50)
        self.assertIsNone(self.due(50 + w.THAW - 1))
        self.assertAlmostEqual(self.watch.wait(50 + w.THAW - 1), 1)
        self.assertIsNone(self.due(50 + w.THAW))  # Changed then, so a quiet moment first.
        self.assertEqual(self.due(50 + w.THAW + w.QUIET), "picture")

    def test_a_shutdown_and_a_logout_both_have_to_end(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.leave("logout")
        self.watch.leave("shutdown")
        self.watch.stay("logout", 10)
        self.watch.changed(11)
        self.assertIsNone(self.due(10 + w.THAW + w.QUIET))
        self.assertTrue(self.watch.leaving)

    def test_a_switch_to_windows_keeps_its_own_checkpoint(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.changed(5)
        self.assertIsNone(self.due(10, departing=True))
        self.assertEqual(self.watch.wait(10), 30)
        self.assertEqual(self.due(40, departing=False), "picture")

    def test_a_compositor_that_doesnt_answer_is_asked_less_and_less_often(self):
        self.watch.pictured(0, self.watch.taken(), [])
        self.watch.changed(10)
        delays, now = [], 10 + w.QUIET
        for _ in range(7):
            self.assertEqual(self.due(now), "picture")
            self.watch.failed(now)
            delay = self.watch.wait(now)
            self.assertIsNone(self.due(now + delay - 0.1))
            delays.append(round(delay))
            now += delay
        self.assertEqual(delays, [6, 12, 24, 48, 96, 96, 96])
        self.watch.pictured(now, self.watch.taken(), [])
        self.assertEqual(self.watch.failures, 0)

    def test_a_change_during_a_picture_is_not_lost(self):
        self.watch.changed(1)
        taken = self.watch.taken()
        self.watch.changed(2)  # Arrived while KWin was asked.
        self.watch.window_closed("{late}", 2)
        self.watch.pictured(3, taken, [])
        self.assertIsNotNone(self.watch.dirty_since)
        self.assertEqual(self.watch.closed, {"{late}"})
        self.assertEqual(self.due(2 + w.QUIET), "picture")


class WhileAGameRuns(unittest.TestCase):
    """A picture loads a script into KWin, on the thread that draws the game: none after every
    Alt+Tab, only once the game has quit, or now and then in a long session."""

    def setUp(self):
        self.watch = w.Watch(0)
        self.watch.pictured(0, self.watch.taken(), [])
        self.playing = True
        self.asked = 0

    def game(self):
        self.asked += 1
        return self.playing

    def due(self, now):
        return self.watch.due(now, True, False, self.game)

    def test_alt_tab_in_and_out_waits_for_the_game_to_quit(self):
        self.watch.changed(10)  # Out of the game,
        self.assertIsNone(self.due(10 + w.QUIET))
        self.assertEqual(self.watch.wait(10 + w.QUIET), w.GAME_LOOK)  # Not a busy poll.
        self.watch.changed(20)  # and back in.
        self.assertAlmostEqual(self.watch.wait(20), w.QUIET)
        self.assertIsNone(self.due(20 + w.QUIET))
        self.assertIsNone(self.due(20 + w.QUIET + w.GAME_LOOK))
        self.playing = False  # Quit (its window closing would also say so).
        self.assertEqual(self.due(20 + w.QUIET + 2 * w.GAME_LOOK), "picture")
        self.watch.pictured(60, self.watch.taken(), [])
        self.assertIsNone(self.watch.wait(60))
        self.assertFalse(self.watch.gaming)

    def test_the_game_is_asked_only_when_a_picture_would_be_taken(self):
        self.watch.changed(10)
        self.assertIsNone(self.due(11))  # Not quiet yet.
        self.watch.lock(True)
        self.assertIsNone(self.due(10 + w.QUIET))
        self.watch.lock(False)
        self.assertIsNone(self.watch.due(10 + w.QUIET, True, True, self.game))  # A switch to Windows.
        self.assertIsNone(self.watch.due(10 + w.QUIET, False, False, self.game))  # Still reopening.
        self.assertEqual(self.asked, 0)
        self.assertIsNone(self.due(10 + w.QUIET))
        self.assertEqual(self.asked, 1)
        # Nothing changed and no documents open: not asked at all.
        quiet = w.Watch(0)
        quiet.pictured(0, quiet.taken(), [])
        self.assertIsNone(quiet.due(10000, True, False, lambda: self.fail("asked")))

    def test_a_long_session_still_gets_a_picture_every_few_minutes(self):
        self.watch.changed(10)
        now = 10 + w.QUIET
        while self.due(now) is None:
            self.assertLessEqual(self.watch.wait(now), w.GAME_LOOK)
            now += self.watch.wait(now)
        self.assertEqual(now, w.GAMING)  # Exactly then, not a moment before.
        self.watch.pictured(now, self.watch.taken(), [])
        self.watch.changed(now + 1)
        self.assertIsNone(self.due(now + 1 + w.QUIET))  # The next one waits as long again.
        # Documents and tabs in Kate or Files change unseen: their five minutes stand.
        kate = w.Watch(0)
        kate.pictured(0, kate.taken(), [KATE])
        self.assertIsNone(kate.due(w.REFRESH - 1, True, False, self.game))
        self.assertEqual(kate.due(w.REFRESH, True, False, self.game), "picture")

    def test_a_window_closed_during_a_game_stays_closed(self):
        self.watch.window_closed("{kate}", 10)
        self.assertIsNone(self.due(11))
        # Taken out of the last picture (a file, not KWin) as soon as things settle,
        self.assertEqual(self.due(10 + w.QUIET), "trim")
        self.watch.trimmed({"{kate}"})
        self.assertIsNone(self.due(10 + w.QUIET + w.GAME_LOOK))
        self.assertEqual(self.watch.wait(10 + w.QUIET + w.GAME_LOOK), w.GAME_LOOK)
        # and still a picture once the game quits.
        self.playing = False
        self.assertEqual(self.due(10 + w.QUIET + 2 * w.GAME_LOOK), "picture")

    def test_a_close_right_before_a_restart_is_still_taken_out_at_once(self):
        self.watch.changed(10)
        self.assertIsNone(self.due(10 + w.QUIET))  # Holding for the game.
        self.watch.window_closed("{closed-by-you}", 20)
        self.watch.leave("logout")
        self.watch.window_closed("{closed-by-the-logout}", 20.5)
        self.assertEqual(self.watch.wait(20.5), 0.2)
        self.assertEqual(self.due(20.5), "trim")
        self.assertEqual(self.watch.closed, {"{closed-by-you}"})
        self.watch.trimmed({"{closed-by-you}"})
        self.playing = False
        for later in (21, 100, 10000):
            self.assertIsNone(self.due(later))  # Nothing more is written.

    def test_the_test_is_monet_rests(self):
        test = w.game_test()
        self.assertEqual((test.__module__, test.__name__), ("monet_rest", "game_running"))
        with tempfile.TemporaryDirectory() as folder:
            proc = Path(folder)
            (proc / "4242").mkdir()
            (proc / "4242/comm").write_text("wineserver\n")
            self.assertTrue(w.game_test()(proc=proc))
            (proc / "4242/comm").write_text("kate\n")
            (proc / "4242/environ").write_bytes(b"HOME=/home/me\0")
            self.assertFalse(w.game_test()(proc=proc))
        with patch.object(w, "load", side_effect=FileNotFoundError):
            self.assertFalse(w.game_test()())  # Not installed beside it: pictures as before.


def frame(app, ident, pid=7, **extra):
    return dict({"app": app, "id": ident, "pid": pid, "rect": {"x": 10, "y": 20, "width": 800, "height": 600},
                 "area": {"x": 0, "y": 0, "width": 1920, "height": 1080}, "screen": "DP-1"}, **extra)


class WorkCheckpoint(unittest.TestCase):
    def test_a_picture_never_waits_for_apps_and_names_its_sign_in(self):
        with patch.object(r.time, "sleep") as sleep, patch.object(r, "editor_documents", return_value=[]), \
                patch.object(r.editor_helper(), "capture", return_value=None):
            saved = r.work_checkpoint([KATE, "a.desktop"], [frame(KATE, "k"), frame("a.desktop", "a")],
                                      {"desktop": {"id": "d"}}, "boot:3")
        sleep.assert_not_called()
        self.assertEqual((saved["version"], saved["kind"], saved["session"]), (4, "work", "boot:3"))
        self.assertEqual([f["id"] for f in saved["windows"]], ["k", "a"])
        self.assertFalse(r.usable(saved, time.time(), "boot", 1))  # Not this sign-in's to reopen.

    def test_a_browser_without_its_own_session_yet_opens_as_from_the_menu(self):
        browser = r.browser_helper()
        with patch.object(browser, "capture", return_value={"mode": "skip"}), \
                patch.object(r, "browser_private", return_value=False):
            saved = r.work_checkpoint([ZEN], [frame(ZEN, "z")], None, "s")
        self.assertNotIn(ZEN, saved.get("groups", {}))
        self.assertNotIn("browser", saved)
        with patch.object(browser, "capture", return_value={"mode": "skip"}), \
                patch.object(r, "browser_private", return_value=True):
            saved = r.work_checkpoint([ZEN], [frame(ZEN, "z")], None, "s")
        self.assertEqual(saved["groups"][ZEN][0]["browser"], {"mode": "skip", "private": True})

    def test_windows_closed_just_before_a_restart_stay_closed(self):
        saved = {"version": 4, "apps": [KATE, FILES, "tray.desktop", "a.desktop"],
                 "windows": [frame(KATE, "k1"), frame(KATE, "k2"), frame(FILES, "f"), frame("a.desktop", "a")],
                 "documents": {"a.desktop": ["/x"]},
                 "groups": {KATE: [{"editor_windows": [{"id": "k1", "editor": None}, {"id": "k2", "editor": None}],
                                    "windows": [frame(KATE, "k1"), frame(KATE, "k2")]}],
                            FILES: [{"files": {"tabs": []}, "windows": [frame(FILES, "f")]}]}}
        self.assertFalse(r.trim_closed(saved, {"never-saved"}))
        self.assertTrue(r.trim_closed(saved, {"k2", "f", "a"}))
        self.assertEqual(saved["apps"], [KATE, "tray.desktop"])
        self.assertEqual([f["id"] for f in saved["windows"]], ["k1"])
        self.assertEqual(saved["groups"][KATE][0]["editor_windows"], [{"id": "k1", "editor": None}])
        self.assertNotIn(FILES, saved["groups"])
        self.assertEqual(saved["documents"], {})

    def test_the_off_switch_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            live, back, off = Path(tmp) / "work.json", Path(tmp) / "work-return.json", Path(tmp) / "off"
            off.touch()
            self.assertFalse(r.save_work(live, back, {"version": 4, "session": "s", "apps": []}, off))
            self.assertFalse(live.exists())

    def test_logout_updates_exact_windows_without_losing_missing_windows_or_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            live, off = Path(tmp) / "work.json", Path(tmp) / "off"
            one, two = frame(KATE, "1"), frame(KATE, "2")
            group = {"windows": [one, two], "editor": {"documents": ["/test.txt"]}}
            r.atomic_write(live, {"version": 4, "session": "s", "windows": [one, two],
                                  "groups": {KATE: [group]}})
            moved = dict(one, fullscreen=True, rect={"x": 0, "y": 0, "width": 1920, "height": 1080})
            r.refresh_work_frames(live, "s", [moved, frame(FILES, "3")], off)
            saved = r.read_state(live)
            self.assertEqual(saved["windows"], [moved, two])
            self.assertEqual(saved["groups"][KATE], [dict(group, windows=[moved, two])])


@unittest.skipIf(os.name == "nt", "Linux advisory lock")
class OncePerSignIn(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.live, self.back, self.off = folder / "work.json", folder / "work-return.json", folder / "off"
        self.saved = {"version": 4, "kind": "work", "id": "a" * 32, "time": 100, "boot": "old", "session": "old:2",
                      "apps": ["a.desktop", "b.desktop"], "windows": [frame("a.desktop", "old-a")], "done": []}
        for owner, name, value in ((r, "boot_id", "new"), (r, "window_snapshot", []),
                                   (r.time, "time", 200), (r.time, "sleep", None)):
            p = patch.object(owner, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_the_next_sign_in_takes_the_work_once(self):
        r.atomic_write(self.live, self.saved)
        self.assertFalse(r.hand_over(self.live, self.back, "old:2"))  # Still this sign-in's own.
        self.assertTrue(self.live.exists())
        self.assertTrue(r.hand_over(self.live, self.back, "new:3"))
        self.assertFalse(self.live.exists())
        handed = r.read_state(self.back)
        self.assertEqual(handed["handed"]["session"], "new:3")
        self.assertTrue(r.usable(handed, 300, "new", 1))
        self.assertFalse(r.hand_over(self.live, self.back, "new:3"))

    def test_a_sign_out_on_the_same_boot_also_hands_over(self):
        r.atomic_write(self.live, dict(self.saved, boot="new", session="new:2"))
        self.assertTrue(r.hand_over(self.live, self.back, "new:4"))
        status = r.return_status(self.back, self.off)
        self.assertTrue(status["available"])  # Not mistaken for a cancelled switch.

    def test_a_new_picture_never_replaces_unreopened_work(self):
        r.atomic_write(self.live, self.saved)
        mine = dict(self.saved, session="new:3", apps=["c.desktop"], id="b" * 32)
        self.assertTrue(r.save_work(self.live, self.back, mine, self.off))
        self.assertEqual(r.read_state(self.back)["apps"], ["a.desktop", "b.desktop"])
        self.assertEqual(r.read_state(self.live)["apps"], ["c.desktop"])
        self.assertFalse(r.save_work(self.live, self.back, dict(mine, id="c" * 32, time=999), self.off))  # Same picture.

    def test_reopens_once_and_not_an_app_that_started_anyway(self):
        r.atomic_write(self.back, dict(self.saved, handed={"session": "new:3"}))
        r.window_snapshot.side_effect = [[{"app": "b.desktop", "id": "b-already"}],
                                         [{"app": "b.desktop", "id": "b-already"}, frame("a.desktop", "new-a")],
                                         [{"app": "b.desktop", "id": "b-already"}, frame("a.desktop", "new-a")]] + [[]] * 200
        launch = Mock()
        with patch.object(r, "place_windows", return_value=[]) as place:
            started = r.restore(self.back, self.off, lambda: ["b.desktop"], lambda _: True, launch)
        self.assertEqual(started, ["a.desktop"])
        self.assertEqual([c.args[0] for c in launch.call_args_list], ["a.desktop"])
        place.assert_called()
        self.assertFalse(self.back.exists())
        r.window_snapshot.side_effect = None
        self.assertEqual(r.restore(self.back, self.off, lambda: [], lambda _: True, launch), [])
        launch.assert_called_once()

    def test_slow_apps_after_a_start_still_get_their_place(self):
        r.atomic_write(self.back, dict(self.saved, apps=["a.desktop"], handed={"session": "new:3"}))
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        def snapshot():
            return [frame("a.desktop", "new-a")] if clock[0] > 20 else []
        r.window_snapshot.side_effect = snapshot
        with patch.object(r.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(r.time, "sleep", side_effect=sleep), \
                patch.object(r, "place_windows", return_value=[]) as place:
            self.assertEqual(r.restore(self.back, self.off, lambda: [], lambda _: True, Mock()), ["a.desktop"])
        place.assert_called()

    def test_a_browser_whose_session_cant_be_confirmed_opens_normally(self):
        state = {"mode": "native", "profile": "work", "session": 1, "updated": 1, "windows": 2, "tabs": 4}
        r.atomic_write(self.back, dict(self.saved, apps=[ZEN], windows=[frame(ZEN, "z")], handed={"session": "new:3"},
                                       groups={ZEN: [{"browser": state, "windows": [frame(ZEN, "z")]}]}))
        browser = r.browser_helper()
        r.window_snapshot.side_effect = [[], [frame(ZEN, "new-z")], [frame(ZEN, "new-z")]] + [[]] * 200
        launch = Mock()
        with patch.object(browser, "valid", return_value=True), patch.object(browser, "prepare", return_value=None), \
                patch.object(r, "place_windows", return_value=[]):
            self.assertEqual(r.restore(self.back, self.off, lambda: [], lambda _: True, launch), [ZEN])
        launch.assert_called_once_with(ZEN)
        self.assertEqual(r.read_return(self.back)["items"][ZEN]["status"], "opened")

    def test_private_browsing_stays_closed(self):
        r.atomic_write(self.back, dict(self.saved, apps=[ZEN], windows=[frame(ZEN, "z")], handed={"session": "new:3"},
                                       groups={ZEN: [{"browser": {"mode": "skip", "private": True},
                                                      "windows": [frame(ZEN, "z")]}]}))
        launch = Mock()
        r.restore(self.back, self.off, lambda: [], lambda _: True, launch)
        launch.assert_not_called()
        self.assertEqual(r.read_return(self.back)["items"][ZEN]["status"], "browser-skipped")

    def test_a_trip_that_ended_the_session_owns_its_return(self):
        trip = {"version": 3, "boot": "old", "time": 100}
        self.assertTrue(r.trip_owns_return(trip, {"boot": "old", "time": 150}))
        for work, owner in (({"boot": "other", "time": 150}, trip), ({"boot": "old", "time": 1000}, trip),
                            ({"boot": "old", "time": 150}, dict(trip, cancelled_boot="old")),
                            ({"boot": "old", "time": 150}, dict(trip, version=2))):
            self.assertFalse(r.trip_owns_return(owner, work))


class ScreensAcrossChanges(unittest.TestCase):
    """A window goes back to its monitor even on another port, and stays reachable without it."""
    LEFT = {"x": 0, "y": 0, "width": 1920, "height": 1080}
    RIGHT = {"x": 1920, "y": 0, "width": 2560, "height": 1440}

    def output(self, port, model, serial, area):
        return {"name": port, "area": area, "display": {"name": port, "maker": "Dell", "model": model, "serial": serial}}

    def test_the_same_monitor_on_another_port_wins_over_the_old_port(self):
        saved = {"screen": "DP-1", "display": {"name": "DP-1", "maker": "Dell", "model": "U2723", "serial": "A1"}}
        outputs = [self.output("DP-1", "P2419", "B2", self.LEFT), self.output("HDMI-A-1", "U2723", "A1", self.RIGHT)]
        self.assertEqual(r.matching_output(saved, outputs)["name"], "HDMI-A-1")

    def test_two_identical_monitors_without_serials_go_by_port(self):
        saved = {"screen": "DP-2", "display": {"maker": "Dell", "model": "P2419", "serial": ""}}
        outputs = [self.output("DP-1", "P2419", "", self.LEFT), self.output("DP-2", "P2419", "", self.RIGHT)]
        self.assertEqual(r.matching_output(saved, outputs)["name"], "DP-2")
        self.assertEqual(r.matching_output(dict(saved, screen="DP-9"), outputs), {})

    def test_an_unplugged_monitor_leaves_the_window_where_it_opened(self):
        saved = {"screen": "DP-3", "display": {"maker": "LG", "model": "27GL", "serial": "Z"}}
        self.assertEqual(r.matching_output(saved, [self.output("DP-3", "U2723", "A1", self.LEFT)]), {})

    def test_checkpoints_from_before_monitor_names_still_go_by_port(self):
        self.assertEqual(r.matching_output({"screen": "DP-1"}, [self.output("DP-1", "U2723", "A1", self.RIGHT)])["area"],
                         self.RIGHT)

    def test_placement_uses_the_moved_monitors_area(self):
        saved = frame("a.desktop", "old", rect={"x": 2020, "y": 100, "width": 800, "height": 600}, area=self.RIGHT,
                      screen="DP-1", display={"maker": "Dell", "model": "U2723", "serial": "A1"})
        outputs = [self.output("DP-1", "P2419", "B2", self.LEFT),
                   self.output("HDMI-A-1", "U2723", "A1", {"x": 1920, "y": 40, "width": 2560, "height": 1400})]
        current = [{"app": "a.desktop", "id": "new", "area": self.LEFT, "outputs": outputs}]
        with patch.object(r, "kwin_script", return_value=["new"]) as script:
            r.place_windows([saved], current, set())
        places = json.loads(script.call_args.args[0].split(";", 1)[0].removeprefix("const places = "))
        self.assertEqual(places[0]["rect"], {"x": 2020, "y": 140, "width": 800, "height": 600})


class KWinScripts(unittest.TestCase):
    """The capture and placement JavaScript itself, in Qt's engine with a pretend KWin."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            raise unittest.SkipTest("Qt JavaScript engine required")
        cls.app = qt_app()
        cls.Engine = QJSEngine

    def setUp(self):
        self.engine = self.Engine()
        self.evaluate(r"""
        var KWin = {MaximizeArea: 2};
        var desks = [{id:"work", name:"Work"}, {id:"play", name:"Play"}];
        var screens = [
            {name:"DP-1", manufacturer:"Dell", model:"P2419", serialNumber:"B2", area:{x:0,y:0,width:1920,height:1080}},
            {name:"HDMI-A-1", manufacturer:"Dell", model:"U2723", serialNumber:"A1", area:{x:1920,y:0,width:2560,height:1440}}];
        var frames = [{internalId:"{one}", desktopFileName:"org.kde.kate", normalWindow:true, skipTaskbar:false,
            transient:false, pid:5, windowRole:"", output:screens[1], desktops:[desks[1]], onAllDesktops:false,
            keepAbove:false, keepBelow:false, minimized:false, fullScreen:false, active:true, stackingOrder:3,
            frameGeometry:{x:2000,y:50,width:900,height:700}, setMaximize:function(h,v){this.maximized=h&&v;}}];
        var workspace = {desktops:desks, currentDesktop:desks[0], currentActivity:"main", cursorPos:{x:1,y:2},
            screens:screens, windowList:()=>frames,
            clientArea:(kind, o) => (o.output || o).area};
        var result; function reply(v) { result = v; }
        """ + r.WINDOWS_JS)

    def evaluate(self, code):
        result = self.engine.evaluate(code)
        self.assertFalse(result.isError(), result.toString())
        return result

    def value(self, expression):
        return json.loads(self.evaluate("JSON.stringify(" + expression + ")").toString())

    def test_capture_names_the_monitor_and_nothing_a_window_shows(self):
        self.evaluate("reply(windows().map(capture));")
        captured = self.value("result")[0]
        self.assertEqual(captured["display"], {"name": "HDMI-A-1", "maker": "Dell", "model": "U2723", "serial": "A1"})
        self.assertEqual([o["display"]["model"] for o in captured["outputs"]], ["P2419", "U2723"])
        self.assertEqual(captured["desktops"], [{"id": "play", "name": "Play"}])
        for private in ("caption", "title", "resourceClass"):
            self.assertNotIn(private, json.dumps(captured))

    def test_the_captured_window_goes_back_to_its_monitor_on_a_new_port(self):
        self.evaluate("reply(windows().map(capture));")
        old = self.value("result")[0]
        # Next start: the monitors swapped ports; a new Kate window opened on the first screen.
        self.evaluate("""screens[0].name = "HDMI-A-1"; screens[1].name = "DP-1";
            frames[0] = Object.assign({}, frames[0], {internalId:"{two}", output:screens[0], desktops:[desks[0]],
                frameGeometry:{x:100,y:100,width:640,height:480}});""")
        self.evaluate("reply(windows().map(capture));")
        current = self.value("result")
        def script(body):
            self.evaluate(body)
            return self.value("result")
        with patch.object(r, "kwin_script", side_effect=script):
            mapped = r.place_windows([old], current, set())
        self.assertEqual(mapped, [{"old": "{one}", "new": "{two}", "app": KATE}])
        self.assertEqual(self.value("frames[0].frameGeometry"), {"x": 2000, "y": 50, "width": 900, "height": 700})
        self.assertEqual(self.value("frames[0].desktops.map(d => d.id)"), ["play"])


# A stand-in for the parts of KWin's scripting API the Monet Work script uses, as KWin 6.8 has them.
FAKE_KWIN = {
    "qmldir": "module org.kde.kwin\nsingleton Workspace 1.0 Workspace.qml\nDBusCall 1.0 DBusCall.qml\n",
    "Workspace.qml": """pragma Singleton
import QtQml
QtObject {
    property var stackingOrder: []
    property var activeWindow: null
    property var currentDesktop: "one"
    property var calls: []
    property bool listening: true
    signal windowAdded(var window)
    signal windowRemoved(var window)
    signal windowActivated(var window)
    signal screensChanged()
}
""",
    "DBusCall.qml": """import QtQml
QtObject {
    id: dbus
    property string service
    property string path
    property string dbusInterface
    property string method
    property var arguments: []
    signal finished(var returnValue)
    signal failed()
    function call() {
        if (!Workspace.listening && service === "org.monet.Priority") failed()
        else Workspace.calls = Workspace.calls.concat([[service, method].concat(dbus.arguments)])
    }
}
""",
}

SCENE = """import QtQuick
import org.kde.kwin

Item {
    id: scene
    property var work: workLoader.item
    property var dp1: ({name: "DP-1"})
    property var dp2: ({name: "DP-2"})
    component FakeWindow: QtObject {
        property int pid: 0
        property string internalId: "{" + pid + "}"
        property string desktopFileName: ""
        property bool normalWindow: true
        property bool skipTaskbar: false
        property bool deleted: false
        property bool minimized: false
        property bool fullScreen: false
        property bool keepAbove: false
        property bool keepBelow: false
        property bool onAllDesktops: true
        property var desktops: []
        property var output: scene.dp1
        property rect frameGeometry: Qt.rect(0, 0, 800, 600)
        signal maximizedChanged()
    }
    property var zen: FakeWindow { pid: 30; desktopFileName: "app.zen_browser.zen" }
    property var game: FakeWindow { pid: 42; fullScreen: true }
    property var panel: FakeWindow { pid: 7; normalWindow: false }
    Loader {
        id: workLoader
        source: "WORK"
    }
}
"""


@unittest.skipUnless(os.name != "nt", "Qt Quick")
class FrontInKWin(unittest.TestCase):
    """The Monet Work script says which windows are in front (for games first, monet-priority),
    as it changes and only when it has: run as it is, against a stand-in for KWin."""

    def setUp(self):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtQml import QQmlApplicationEngine
        except ImportError:
            self.skipTest("Qt Quick required")
        qt_app()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        kwin = folder / "imports/org/kde/kwin"
        kwin.mkdir(parents=True)
        for name, text in FAKE_KWIN.items():
            (kwin / name).write_text(text, encoding="utf-8")
        script = ROOT / "linux/share/kwin/scripts/monet-work/contents/ui/main.qml"
        scene = folder / "scene.qml"
        scene.write_text(SCENE.replace("WORK", QUrl.fromLocalFile(str(script)).toString()), encoding="utf-8")
        self.engine = QQmlApplicationEngine()
        self.addCleanup(self.engine.deleteLater)
        self.engine.addImportPath(str(folder / "imports"))
        errors = []
        self.engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
        self.engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(self.engine.rootObjects(), "\n".join(errors))
        self.scene = self.engine.rootObjects()[0]
        self.assertIsNotNone(self.scene.property("work"), "\n".join(errors))
        self.errors = errors

    def js(self, expression):
        from PySide6.QtQml import QJSValue, QQmlExpression
        expr = QQmlExpression(self.engine.contextForObject(self.scene), self.scene, expression)
        value, _ = expr.evaluate()
        self.assertFalse(expr.hasError(), expr.error().toString())
        return value.toVariant() if isinstance(value, QJSValue) else value

    def said(self, wait=400):
        from PySide6.QtTest import QTest
        QTest.qWait(wait)
        calls = self.js("Workspace.calls")
        self.js("Workspace.calls = []")
        return [json.loads(c[2]) for c in calls if c[:2] == ["org.monet.Priority", "Front"]]

    def test_window_placement_can_use_chatgpts_class_without_a_desktop_id(self):
        self.assertEqual(self.js('scene.work.children[0].key({normalWindow: true, managed: true,'
                                 ' desktopFileName: "", resourceClass: "Chatgpt"})'),
                         "classes/chatgpt")

    def test_whats_in_front_as_it_changes(self):
        self.assertEqual(self.said(), [{"active": 0, "full": []}])  # As it starts.
        self.js("Workspace.windowAdded(scene.panel)")
        self.assertEqual(self.said(), [])  # Nothing changed in front: not said again.
        # The game, full screen, in front.
        self.js("Workspace.stackingOrder = [scene.panel, scene.zen, scene.game]")
        self.js("Workspace.activeWindow = scene.game; Workspace.windowActivated(scene.game)")
        self.assertEqual(self.said(), [{"active": 42, "full": []}])
        # Alt+Tab: the game minimizes itself, Zen in front.
        self.js("Workspace.windowAdded(scene.game); Workspace.windowAdded(scene.zen)")
        self.said()
        self.js("scene.game.minimized = true; Workspace.activeWindow = scene.zen; Workspace.windowActivated(scene.zen)")
        self.assertEqual(self.said(), [{"active": 30, "full": []}])
        # Back, then the game on a screen of its own while Zen is used on the other one.
        self.js("scene.game.minimized = false; scene.game.output = scene.dp2")
        self.assertEqual(self.said(), [{"active": 30, "full": [42]}])
        # Behind Zen on the same screen, it isn't in front.
        self.js("scene.game.output = scene.dp1")
        self.assertEqual(self.said(), [{"active": 30, "full": []}])
        # On another desktop it isn't either; the panel never is.
        self.js("scene.game.output = scene.dp2; scene.game.onAllDesktops = false; scene.game.desktops = ['two']")
        self.assertEqual(self.said(), [])
        self.js("Workspace.activeWindow = scene.panel; Workspace.windowActivated(scene.panel)")
        self.assertEqual(self.said(), [{"active": 0, "full": []}])
        self.assertEqual(self.errors, [])

    def test_said_again_when_games_first_wasnt_listening(self):
        self.said()
        self.js("Workspace.listening = false")  # monet-priority not started yet: KWin's call fails.
        self.js("Workspace.stackingOrder = [scene.game]; Workspace.activeWindow = scene.game; Workspace.windowActivated(scene.game)")
        self.assertEqual(self.said(), [])
        self.js("Workspace.listening = true; Workspace.windowActivated(scene.game)")
        self.assertEqual(self.said(), [{"active": 42, "full": []}])
        self.js("Workspace.windowActivated(scene.game)")
        self.assertEqual(self.said(), [])


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class DesktopReady(unittest.TestCase):
    def test_an_already_ready_desktop_has_no_extra_sleep(self):
        q = quick_helper(); resume = Mock()
        with patch.object(q, "run", return_value="b true\n"), patch.object(q.time, "sleep") as sleep:
            self.assertTrue(q.wait_for_desktop(resume))
        resume.window_snapshot.assert_called_once_with()
        sleep.assert_not_called()

    def test_shell_registration_and_compositor_readiness_both_matter(self):
        q = quick_helper(); resume = Mock()
        resume.window_snapshot.side_effect = [OSError("KWin is starting"), []]
        with patch.object(q, "run", side_effect=["b false", "b true", "b true"]), patch.object(q.time, "sleep") as sleep:
            self.assertTrue(q.wait_for_desktop(resume, tries=3))
        self.assertEqual(resume.window_snapshot.call_count, 2)
        self.assertEqual(sleep.call_count, 2)

    def test_missing_shell_never_starts_compositor_queries_or_reports_ready(self):
        q = quick_helper(); resume = Mock()
        with patch.object(q, "run", return_value=None), patch.object(q.time, "sleep"):
            self.assertFalse(q.wait_for_desktop(resume, tries=2))
        resume.window_snapshot.assert_not_called()


class SignIn(unittest.TestCase):
    """monet-quick trip-apps-again at every sign-in: the trip first, then the last session's work."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.q = q = quick_helper()
        state = folder / "state/monet"
        q.TRIP_APPS, q.WORK, q.WORK_RETURN, q.WORK_AGAIN = (state / name for name in (
            "trip-apps.json", "work.json", "work-return.json", "work-again.json"))
        q.TRIP_APPS_OFF, q.CONFIG = folder / "config/monet/trip-apps-off", folder / "config"
        self.launched = []
        for owner, name, value in ((q, "resume_helper", r), (q, "session_key", "new:3"), (q, "running_apps", []),
                                   (q, "entry_by_id", {"Type": "Application"}), (q, "starts_anyway", False),
                                   (q, "run", None), (q, "ok", True), (q, "wait_for_desktop", True),
                                   (r, "boot_id", "new"), (r, "kwin_script", None), (r.time, "sleep", None)):
            p = patch.object(owner, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(q, "launch", side_effect=self.launched.append)
        p.start()
        self.addCleanup(p.stop)
        self.windows = []
        p = patch.object(r, "window_snapshot", side_effect=lambda: [frame(app, "new-" + app) for app in self.launched])
        p.start()
        self.addCleanup(p.stop)
        self.work = {"version": 4, "kind": "work", "id": "a" * 32, "time": int(time.time()), "boot": "old",
                     "session": "old:2", "apps": ["a.desktop", "b.desktop"], "windows": [], "done": []}

    def test_after_a_restart_the_last_sessions_apps_reopen_once(self):
        r.atomic_write(self.q.WORK, self.work)
        self.assertEqual(self.q.reopen_work(), ["a.desktop", "b.desktop"])
        self.assertEqual(self.q.reopen_work(), [])
        self.assertEqual(self.launched, ["a.desktop", "b.desktop"])
        self.assertTrue(self.q.work_settled("new:3"))
        # Everything back: no summary left behind, no notice.
        self.assertFalse(self.q.WORK_RETURN.exists())
        self.assertFalse(r.return_path(self.q.WORK_RETURN).exists())
        self.q.ok.assert_not_called()

    def test_late_desktop_keeps_work_retryable_before_any_launch(self):
        r.atomic_write(self.q.WORK, self.work)
        self.q.wait_for_desktop.return_value = False
        self.assertEqual(self.q.reopen_work(), [])
        self.assertEqual(self.launched, [])
        pending = r.read_state(self.q.WORK_RETURN)
        self.assertEqual(pending["apps"], self.work["apps"])
        self.assertFalse(pending.get("automatic", False))
        self.q.wait_for_desktop.return_value = True
        self.assertEqual(self.q.reopen_work(), ["a.desktop", "b.desktop"])

    def test_trip_waits_for_the_desktop_before_launching(self):
        trip = {"version": 2, "id": "b" * 32, "time": int(time.time()), "boot": "old", "apps": ["t.desktop"], "done": []}
        r.atomic_write(self.q.TRIP_APPS, trip)
        self.q.wait_for_desktop.return_value = False
        self.assertEqual(self.q.reopen_work(), [])
        self.assertEqual(self.launched, [])
        self.assertTrue(self.q.TRIP_APPS.exists())
        self.q.wait_for_desktop.return_value = True
        self.assertEqual(self.q.reopen_work(), ["t.desktop"])

    def test_an_app_that_now_starts_by_itself_is_not_opened_twice(self):
        r.atomic_write(self.q.WORK, self.work)
        self.q.starts_anyway.side_effect = lambda app: app == "b.desktop"
        self.assertEqual(self.q.reopen_work(), ["a.desktop"])
        self.assertEqual(self.launched, ["a.desktop"])

    def test_off_means_starting_fresh(self):
        r.atomic_write(self.q.WORK, self.work)
        self.q.set_trip_apps(False)
        self.assertFalse(self.q.WORK.exists())
        self.assertEqual(self.q.reopen_work(), [])
        self.assertEqual(self.launched, [])
        self.assertIsNone(self.q.capture_work("new:3"))
        self.q.set_trip_apps(True)
        self.assertTrue(self.q.ready_state()["apps"])

    def test_kdes_own_restore_chosen_in_kdes_settings_keeps_restarts(self):
        r.atomic_write(self.q.WORK, self.work)
        rc = self.q.CONFIG / "ksmserverrc"
        rc.parent.mkdir(parents=True, exist_ok=True)
        rc.write_text("[General]\nconfirmLogout=false\nloginMode=restorePreviousLogout\n")
        self.assertTrue(self.q.kde_restores())
        self.assertEqual(self.q.reopen_work(), [])
        self.assertEqual(self.launched, [])
        rc.write_text("[General]\nloginMode=emptySession\n")
        self.assertFalse(self.q.kde_restores())

    def test_a_trip_reopens_its_own_apps_and_the_sessions_checkpoint_steps_aside(self):
        r.atomic_write(self.q.WORK, dict(self.work, time=105))
        r.atomic_write(self.q.TRIP_APPS, {"version": 3, "id": "b" * 32, "time": 100, "boot": "old",
                                          "apps": ["a.desktop"], "windows": [], "done": []})
        receipt = Path(self.temp.name) / "trip-return.json"
        r.atomic_write(receipt, {"id": "b" * 32, "boot": "old", "returned_boot": "new"})
        with patch.object(r, "TRIP_RETURN", receipt):
            self.assertEqual(self.q.reopen_work(), ["a.desktop"])
        self.assertEqual(self.launched, ["a.desktop"])
        self.assertFalse(self.q.WORK_RETURN.exists())

    def test_what_couldnt_reopen_is_summarized_with_retry_and_a_word(self):
        r.atomic_write(self.q.WORK, self.work)
        self.q.entry_by_id.side_effect = lambda app: None if app == "b.desktop" else {"Type": "Application"}
        self.q.reopen_work()
        state = self.q.return_status()
        self.assertEqual(state["kind"], "restart")
        items = {item["app"]: item for item in state["items"]}
        self.assertEqual(items["b.desktop"]["status"], "missing-app")
        self.assertTrue(items["b.desktop"]["needsAttention"] and items["b.desktop"]["retry"])
        self.assertFalse(items["a.desktop"]["needsAttention"])
        self.q.ok.assert_called_once()
        self.assertIn("return-notice", self.q.ok.call_args.args)
        # Retry and dismiss find the restart's own checkpoint by its id.
        self.assertEqual(self.q.return_source(state["id"]), self.q.WORK_RETURN)
        self.q.entry_by_id.side_effect = None
        with patch.object(self.q, "return_worker_active", return_value=False):
            self.assertTrue(self.q.retry_return(state["id"], "b.desktop"))
        self.assertTrue(r.clear_return(self.q.return_source(state["id"]), self.q.TRIP_APPS_OFF, state["id"]))

    def test_the_restart_notice_opens_power_and_sleep(self):
        state = {"id": "a" * 32, "available": True, "kind": "restart", "items": [{"needsAttention": True}]}
        with patch.object(self.q, "return_status", return_value=state), \
                patch.object(self.q, "open_settings") as opened:
            self.q.run.return_value = "open"
            self.q.show_return_notice("a" * 32)
        self.assertIn("Some apps didn't reopen", self.q.run.call_args.args)
        opened.assert_called_once_with("power#return")

    def test_the_latest_return_is_shown_and_a_trips_id_still_finds_the_trip(self):
        trip = {"version": 3, "id": "b" * 32, "time": 100, "boot": "old", "apps": ["t.desktop"], "done": []}
        r.save_return(self.q.TRIP_APPS, trip, r.initial_return(trip))
        work = dict(self.work, handed={"session": "new:3"})
        later = r.initial_return(work)
        r.save_return(self.q.WORK_RETURN, work, later)
        with patch.object(self.q, "return_worker_active", return_value=False):
            self.assertEqual(self.q.return_status()["id"], "a" * 32)
            self.assertEqual(self.q.return_status("b" * 32)["kind"], "trip")

    def test_the_first_sign_in_with_monets_reopening_brings_back_what_kde_saved(self):
        kde = self.q.TRIP_APPS.parent.parent / "plasmasessionrestorerc"
        kde.parent.mkdir(parents=True, exist_ok=True)
        kde.write_text("[1]\nappId=org.kde.dolphin.desktop\n\n[2]\nappId=steam.desktop\n\n[3]\nappId=bad;id\n")
        self.assertEqual(self.q.reopen_work(), ["org.kde.dolphin.desktop"])
        self.assertEqual(self.q.reopen_work(), [])  # Once only.
        self.assertEqual(self.launched, ["org.kde.dolphin.desktop"])

    def test_a_picture_keeps_monets_rules_for_which_apps_reopen(self):
        snapshot = {"windows": [frame("steam.desktop", "s"), frame("a.desktop", "a"), frame("auto.desktop", "x")],
                    "scene": {"desktop": {"id": "d"}}}
        self.q.starts_anyway.side_effect = lambda app: app == "auto.desktop"
        with patch.object(r, "desktop_snapshot", return_value=snapshot):
            saved = self.q.capture_work("new:3")
        self.assertEqual(saved["apps"], ["a.desktop"])
        self.assertEqual(saved["session"], "new:3")
        self.assertTrue(self.q.save_work(saved))
        self.assertEqual(r.read_state(self.q.WORK)["apps"], ["a.desktop"])
        saved["windows"] = saved["windows"] + [frame("a.desktop", "a2")]
        self.assertTrue(self.q.save_work(saved))
        self.assertTrue(self.q.trim_work({"a2"}, "new:3"))
        self.assertEqual([f["id"] for f in r.read_state(self.q.WORK)["windows"]], ["a"])
        self.assertFalse(self.q.trim_work({"a"}, "another:9"))

    def test_departing_is_only_a_live_switch_on_this_boot(self):
        trip = {"version": 3, "time": time.time(), "boot": "new", "apps": []}
        r.atomic_write(self.q.TRIP_APPS, trip)
        self.assertTrue(self.q.departing())
        for other in (dict(trip, cancelled_boot="new"), dict(trip, boot="old"), dict(trip, time=time.time() - 7200)):
            r.atomic_write(self.q.TRIP_APPS, other)
            self.assertFalse(self.q.departing())


class Packaging(unittest.TestCase):
    def test_the_kwin_script_service_and_switch_are_installed_and_on(self):
        meta = json.loads((ROOT / "linux/share/kwin/scripts/monet-work/metadata.json").read_text())
        self.assertEqual((meta["KPlugin"]["Id"], meta["X-Plasma-API"], meta["X-Plasma-MainScript"], meta["KPlugin"]["EnabledByDefault"]),
                         ("monet-work", "declarativescript", "ui/main.qml", True))
        script = (ROOT / "linux/share/kwin/scripts/monet-work/contents/ui/main.qml").read_text()
        for word in ('service: "org.monet.Work"', 'method: "Changed"', 'method: "Closed"', "windowRemoved"):
            self.assertIn(word, script)
        for private in ("caption", ".title"):
            self.assertNotIn(private, script)
        install, uninstall = (ROOT / "linux/install.sh").read_text(), (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('tree "$SRC/share/kwin/scripts/monet-work" "$DATADIR/kwin/scripts/monet-work"', install)
        self.assertIn('put 644 "$SRC/systemd/user/monet-work.service"', install)
        self.assertEqual(install.count("systemctl --global enable monet-work.service"), 2)
        self.assertIn("monet-resume monet-work monet-leave", install)
        self.assertIn("--file /etc/xdg/ksmserverrc --group General --key loginMode emptySession", install)
        self.assertIn('"$PREFIX/share/kwin/scripts/monet-work"', uninstall)
        self.assertIn("/etc/systemd/user/monet-work.service", uninstall)
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn("look --file kwinrc --group Plugins --key monet-workEnabled true", look)
        self.assertIn("kw_default ksmserverrc General loginMode emptySession", look)
        unit = (ROOT / "linux/systemd/user/monet-work.service").read_text()
        for line in ("PartOf=graphical-session.target", "ExecStart=@LIBEXECDIR@/monet-work", "WantedBy=graphical-session.target"):
            self.assertIn(line, unit)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        restore = '[ -z "$GUEST" ] && "$LIBEXECDIR/monet-quick" trip-apps-again'
        self.assertIn(restore, session)
        self.assertLess(session.index(restore), session.index('"$LIBEXECDIR/monet-quick" steam-share'))

    def test_settings_offers_one_switch_on_power_and_windows_and_a_restart_summary(self):
        qml = (ROOT / "linux/share/monet/settings-app/MonetSettings.qml").read_text()
        self.assertEqual(qml.count('title: i18n("Reopen your work")'), 2)
        self.assertEqual(qml.count("onTapped: sheet.setReopenWork(sheet.ready.apps === false)"), 2)
        self.assertIn('objectName: "search-reopen"', qml)
        self.assertEqual(qml.count("sourceComponent: returnSummary"), 2)
        self.assertIn('i18n("After your last restart")', qml)
        q = quick_helper()
        self.assertEqual(q.everyday_search("reopen apps after restart")[0]["target"], "power#reopen")


from tests import test_return_summary as summary_tests


@unittest.skipUnless(summary_tests.QT, "Qt/Kirigami runtime")
class PowerAndSleep(summary_tests.ReturnUI):
    """The switch and what didn't reopen after a restart, on Power & Sleep, by keyboard."""

    def setUp(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        self.engine = QQmlApplicationEngine()
        self.helper = Helper()
        self.words = self.games.Words()
        self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        context = self.engine.rootContext()
        context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "power#reopen", "blurBehind": False,
                            "pictures": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.wait_for(lambda: not self.window.property("pendingAnchor") and not self.window.property("returnLoading")
                      and self.window.property("returnInfo").toVariant()["available"])

    def test_the_switch_is_reached_and_turned_off_from_the_keyboard(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.assertTrue(self.item("search-reopen").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Space)
        self.wait_for(lambda: ["trip-apps", "off"] in self.helper.asked)
        self.assertFalse(self.window.property("ready").toVariant()["apps"])

    def test_what_didnt_reopen_after_a_restart_is_listed_with_retry(self):
        card = self.item("search-return")
        found = []
        todo = [card]
        while todo:
            item = todo.pop()
            todo.extend(item.childItems())
            found.append(item.property("text") or item.property("title") or "")
        self.assertIn("After your last restart", found)
        self.press("returnRetry-a.desktop")
        self.wait_for(lambda: ["return-retry", "a" * 32, "a.desktop"] in self.helper.asked)

    # The Windows page's own checks, inherited from ReturnUI, don't apply here.
    test_repeat_keyboard_actions_are_ignored_while_retry_is_starting_and_running = None
    test_tab_from_the_return_destination_reaches_its_actions_without_visiting_the_sidebar = None
    test_failed_action_remains_visible_across_successful_refresh_and_can_be_retried = None
    test_late_refresh_cannot_resurrect_a_dismissed_list_and_focus_is_retained = None
    test_failed_refresh_keeps_last_known_list_and_retry_restores_status = None
    test_background_refresh_keeps_keyboard_focus_inside_the_recovery_card = None
    test_controls_fit_a_narrow_window_and_missing_names_are_plain_text = None
    test_missing_document_retry_uses_the_existing_recovery_worker = None
    test_games_restart_explanation_and_buttons_fit_a_small_window = None


if summary_tests.QT:
    from PySide6.QtCore import Slot

    class Helper(summary_tests.ReturnHelper):
        def __init__(self):
            super().__init__()
            self.asked = []
            self.state = dict(self.state, kind="restart")
            for item in self.state["items"]:
                item["needsAttention"] = True

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.asked.append(list(command[1:]))
            if command[1:2] == ["trip-apps"]:
                self.ticket += 1
                ticket, out = self.ticket, json.dumps({"on": False, "apps": command[2:] != ["off"]})
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1, lambda: self.done.emit(ticket, out, 0, ""))
                return ticket
            return super().run(command)


@unittest.skipIf(os.name == "nt" or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"), "a private session bus")
class OnTheBus(unittest.TestCase):
    """monet-work's own loop on the private test bus: KWin's words in, pictures out, and a
    sign-out (org.kde.Shutdown appearing) stopping them."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtDBus import QDBusConnection
        except ImportError:
            raise unittest.SkipTest("Qt D-Bus required")
        cls.app = qt_app()
        cls.Bus = QDBusConnection

    def wait(self, condition, seconds=5):
        from PySide6.QtCore import QCoreApplication, QEventLoop
        deadline = time.monotonic() + seconds
        while not condition() and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
            time.sleep(0.01)
        return condition()

    def quick(self, session):
        quick = Mock()
        quick.session_key.return_value = session
        quick.work_settled.return_value = True
        quick.departing.return_value = False
        quick.capture_work.side_effect = lambda session: {"version": 4, "session": session, "apps": ["a.desktop"]}
        return quick

    def connect(self, *names):
        buses = [self.Bus.connectToBus(os.environ["DBUS_SESSION_BUS_ADDRESS"], name) for name in names]
        self.addCleanup(lambda: [self.Bus.disconnectFromBus(name) for name in names])
        return buses

    def tell(self, kwin, method, *args):
        from PySide6.QtDBus import QDBusMessage
        message = QDBusMessage.createMethodCall(w.NAME, w.PATH, w.NAME, method)
        message.setArguments(list(args))
        pending = kwin.asyncCall(message, 2000)  # Answered by this same process's loop.
        self.assertTrue(self.wait(pending.isFinished))
        self.assertFalse(pending.isError(), pending.error().message())

    def test_kwins_words_become_pictures_until_a_sign_out_begins(self):
        quick = self.quick("boot:1")
        bus, kwin = self.connect("monet-work-under-test", "pretend-kwin")
        with patch.object(w, "QUIET", 0.5), patch.object(w, "THAW", 0.5):
            alive = w.serve(quick, bus=bus, system=bus, game=lambda: False)
            self.assertIsNotNone(alive)
            self.assertTrue(self.wait(lambda: quick.save_work.call_count == 1))  # The sign-in's first look.
            say = lambda *words: self.tell(kwin, *words)
            say("Changed")
            self.assertTrue(self.wait(lambda: quick.save_work.call_count == 2))
            say("Closed", "{closed-by-you}")
            self.assertTrue(kwin.registerService("org.kde.Shutdown"))  # A restart begins.
            self.assertTrue(self.wait(lambda: quick.trim_work.called))
            self.assertEqual(quick.trim_work.call_args.args, ({"{closed-by-you}"}, "boot:1"))
            quick.refresh_work_frames.assert_called_once_with("boot:1")
            say("Closed", "{closed-by-the-logout}")
            say("Changed")
            self.wait(lambda: False, 0.8)
            self.assertEqual(quick.save_work.call_count, 2)
            self.assertEqual(quick.trim_work.call_count, 1)
            kwin.unregisterService("org.kde.Shutdown")  # Cancelled after all.
            self.assertTrue(self.wait(lambda: quick.save_work.call_count == 3))
            again, = self.connect("second-monet-work")
            self.assertIsNone(w.serve(quick, bus=again, system=again))  # One per sign-in.

    def test_a_game_holds_pictures_until_it_quits(self):
        quick = self.quick("boot:2")
        game = Mock(return_value=False)
        bus, kwin = self.connect("monet-work-gaming", "pretend-kwin-gaming")
        with patch.object(w, "QUIET", 0.3), patch.object(w, "GAME_LOOK", 0.5):
            alive = w.serve(quick, bus=bus, system=bus, game=game)
            self.assertIsNotNone(alive)
            self.assertTrue(self.wait(lambda: quick.save_work.call_count == 1))
            game.return_value = True
            self.tell(kwin, "Changed")  # Alt+Tab, in and out of the game.
            self.tell(kwin, "Changed")
            self.assertTrue(self.wait(lambda: game.called))
            self.tell(kwin, "Closed", "{kate}")
            self.assertTrue(self.wait(lambda: quick.trim_work.called))  # Stays closed meanwhile.
            self.assertEqual(quick.trim_work.call_args.args, ({"{kate}"}, "boot:2"))
            self.wait(lambda: False, 1.2)  # Two looks for the game.
            self.assertEqual(quick.save_work.call_count, 1)
            self.assertEqual(quick.capture_work.call_count, 1)  # KWin never asked.
            game.return_value = False  # Quit.
            self.assertTrue(self.wait(lambda: quick.save_work.call_count == 2, 2))
            self.assertEqual(quick.trim_work.call_count, 1)


if __name__ == "__main__":
    unittest.main()
