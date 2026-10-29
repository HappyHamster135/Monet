"""Unsaved work blocks switching; cancellation cannot authorize a later reboot."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r, ROOT


class CancelledDeparture(unittest.TestCase):
    def test_bad_window_inspection_fails_closed(self):
        for result in (None, {}, [{"id": "one"}], [{"id": 1, "closeable": True}]):
            with patch.object(r, "kwin_script", return_value=result):
                with self.assertRaises(RuntimeError):
                    r.departure_windows()

    @unittest.skipIf(os.name == "nt", "Linux restore lock")
    def test_cancel_reopens_closed_apps_only_on_the_departure_boot(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, "boot_id", return_value="same"), \
                patch.object(r, "window_snapshot", return_value=[]), patch.object(r.time, "sleep"):
            path = Path(tmp) / "apps.json"
            state = {"version": 3, "id": "a" * 32, "boot": "same", "time": 100,
                     "apps": ["closed.desktop", "unsaved.desktop"], "done": []}
            r.atomic_write(path, state)
            self.assertFalse(r.cancel_departure(path, "b" * 32))
            self.assertFalse(r.usable(state, 110, "same", 100))
            self.assertTrue(r.cancel_departure(path, state["id"]))
            saved = r.read_state(path)
            self.assertTrue(r.usable(saved, 110, "same", 100))
            self.assertFalse(r.usable(saved, 110, "unrelated-boot", 100))
            r.window_snapshot.side_effect = [[], [{"id": "reopened", "app": "closed.desktop"}]]
            launch = Mock()
            self.assertEqual(r.restore(path, path.with_name("off"), lambda: ["unsaved.desktop"],
                                       lambda _: True, launch, request=state["id"]), ["closed.desktop"])
            launch.assert_called_once_with("closed.desktop")
            self.assertFalse(path.exists())

    def test_helper_is_packaged_and_guard_precedes_every_boot_write(self):
        for name in ("install", "uninstall"):
            self.assertIn("monet-leave", (ROOT / f"linux/{name}.sh").read_text())
        main = (ROOT / "crates/monet/src/main.rs").read_text()
        helper = main[main.index("fn helper_switch("):main.index("fn await_saved_apps(")]
        self.assertLess(helper.index("await_saved_apps("), helper.index("request::write("))
        self.assertLess(helper.index("await_saved_apps("), helper.index("boot::set_boot_next("))
        self.assertIn('"--check-inhibitors=yes"', helper)
        self.assertNotIn('"--force"', helper)

    def test_ui_safety_paths_in_separate_qt_process(self):
        try:
            import PySide6
        except ImportError:
            self.skipTest("Qt runtime")
        result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_departure.DepartureUI"],
                                cwd=ROOT, capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen", MONET_DEPARTURE_UI_TEST="1"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if os.environ.get("MONET_DEPARTURE_UI_TEST") == "1":
    from PySide6.QtCore import QProcess, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    loader = importlib.machinery.SourceFileLoader("departure_ui", str(ROOT / "linux/libexec/monet-leave"))
    leave = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(leave)

    class DepartureUI(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.app = QApplication([])
            cls.app.setQuitOnLastWindowClosed(False)

        def setUp(self):
            self.quick = Mock()
            self.quick.tr.side_effect = lambda text: text
            self.resume = self.quick.resume_helper.return_value
            self.resume.EDITORS = r.EDITORS
            self.resume.PDF = r.PDF
            self.capture = patch.object(leave.Departure, "capture"); self.capture.start()
            self.addCleanup(self.capture.stop)
            self.window = leave.Departure(self.quick, "/test/monet")
            self.window.process = Mock()
            self.window.phase = "close"
            self.window.ident = "a" * 32
            self.window.show()
            QTest.qWait(5)

        def tearDown(self):
            self.window.timer.stop()
            self.window.background_timeout.stop()
            self.window.background.kill()
            self.window.phase = "done"
            self.window.close()
            self.window.deleteLater()
            QTest.qWait(5)

        def test_wayland_save_dialog_blocks_departure_without_becoming_an_editor_window(self):
            from PySide6.QtQml import QJSEngine
            with patch.object(r,"kwin_script",return_value=[]) as call:
                r.departure_windows()
            engine=QJSEngine()
            windows=[{"internalId":"main","pid":12,"normalWindow":True,"transient":False,"closeable":True},
                     {"internalId":"save-as","pid":12,"normalWindow":True,"transient":True,"closeable":True}]
            result=engine.evaluate("var result; function reply(value) { result=value; } "
                "function appId(w) { return 'org.kde.kate.desktop'; } "
                "var workspace={windowList:()=>" + json.dumps(windows) + "};\n" + call.call_args.args[0])
            self.assertFalse(result.isError(),result.toString())
            pending=json.loads(engine.evaluate("JSON.stringify(result)").toString())
            self.assertEqual([(w["id"],w["normal"]) for w in pending],[("main",True),("save-as",False)])

        def test_pdf_watch_precedes_close_requests(self):
            windows = [{"id": "pdf", "app": r.PDF, "pid": 12, "normal": True}]
            self.window.watch_editors(windows)
            self.resume.prepare_pdf_close.assert_called_once_with(self.quick.TRIP_APPS, self.window.ident, windows[0], windows)
            self.assertTrue(self.window.touched)

        def test_only_shutdown_blockers_wait_and_the_entire_reply_must_be_valid(self):
            def reply(rows):
                return json.dumps({"type": "a(ssssuu)", "data": [rows]}).encode()
            block = ["sleep:shutdown", "Store", "Installing", "block", 1000, 123]
            rows = [block, ["shutdown", "Other", "Saving", "block-weak", 1001, 124],
                    ["shutdown", "Session", "Flushing", "delay", 1000, 125],
                    ["sleep", "Music", "Playing", "block", 1000, 126]]
            self.assertEqual(leave.shutdown_blockers(reply(rows)), [("Store", "Installing"), ("Other", "Saving")])
            self.assertEqual(leave.shutdown_blockers(reply([])), [])
            for raw in (b"broken", b"{}", b"[]", reply([block, None]), reply([block[:-1]]),
                        reply([block[:4] + [True, 1]]), reply([block[:3] + ["unknown", 1, 2]]),
                        reply([block] * 1025), b" " * (256 * 1024 + 1)):
                with self.subTest(raw=raw[:150]), self.assertRaises(ValueError):
                    leave.shutdown_blockers(raw)

        def test_background_blocker_keeps_windows_open_and_names_are_plain_text(self):
            self.resume.departure_windows.return_value = [{"id": "open", "closeable": True}]
            for _ in range(3):
                self.window.close_windows([("<b>Store</b>", "Installing")])
            self.assertEqual(self.resume.departure_windows.call_args_list, [unittest.mock.call()] * 3)
            self.window.process.write.assert_not_called()
            self.assertTrue(self.window.button.isEnabled())
            self.assertEqual(self.window.detail.textFormat(), Qt.PlainText)
            self.assertIn("<b>Store</b>", self.window.detail.text())
            self.window.close_windows([])
            self.assertIn(unittest.mock.call("open"), self.resume.departure_windows.call_args_list)
            self.assertEqual(self.window.detail.text(), self.window.instructions)

        def test_headless_blocker_waits_even_when_all_windows_are_gone(self):
            self.resume.departure_windows.return_value = []
            self.window.close_windows([("Store", "Installing")])
            self.window.process.write.assert_not_called()
            self.window.close_windows([])
            self.window.process.write.assert_called_once_with(b"continue\n")

        def test_inhibitor_query_is_async_and_cancel_ignores_its_late_reply(self):
            self.window.background = Mock()
            self.window.background.state.return_value = QProcess.NotRunning
            self.window.check_windows()
            self.window.background.start.assert_called_once()
            self.resume.departure_windows.assert_not_called()
            self.window.reject()
            self.window.background.readAllStandardOutput.return_value = b'{"type":"a(ssssuu)","data":[[]]}'
            self.window.background_finished(0, QProcess.NormalExit)
            self.resume.departure_windows.assert_not_called()
            self.window.process.write.assert_not_called()
            self.window.background.kill.assert_called()

        def test_failed_inhibitor_query_cancels_without_closing_apps(self):
            self.window.background = Mock()
            self.window.background.readAllStandardOutput.return_value = b"{}"
            self.window.background_finished(0, QProcess.NormalExit)
            self.assertTrue(self.window.cancelled)
            self.resume.departure_windows.assert_not_called()
            self.window.process.write.assert_not_called()
            self.assertIn("background work", self.window.error)

        def test_stalled_inhibitor_query_times_out_without_acceptance(self):
            self.window.background.start(sys.executable, ["-c", "import time; time.sleep(30)"])
            self.window.background_timeout.start(30)
            QTest.qWait(150)
            self.assertTrue(self.window.cancelled)
            self.resume.departure_windows.assert_not_called()
            self.window.process.write.assert_not_called()
            self.assertIn("background work", self.window.error)

        def test_veto_and_dialog_closure_never_force_the_restart_or_repeat_close(self):
            window = {"id": "unsaved", "closeable": True}
            self.resume.departure_windows.return_value = [window]
            for _ in range(4):
                self.window.close_windows([])
            self.assertEqual([c.args for c in self.resume.departure_windows.call_args_list].count(("unsaved",)), 1)
            self.window.process.write.assert_not_called()
            self.assertTrue(self.window.button.isEnabled())

        def test_all_windows_must_close_before_one_acceptance(self):
            self.window.target = "already-closed"
            self.resume.departure_windows.return_value = [{"id": "new-window", "closeable": True}]
            self.window.close_windows([])
            self.window.process.write.assert_not_called()
            self.assertEqual(self.window.target, "new-window")
            self.resume.departure_windows.return_value = []
            self.window.close_windows([])
            self.window.close_windows([])
            self.window.process.write.assert_called_once_with(b"continue\n")
            self.assertFalse(self.window.button.isEnabled())
            self.window.reject()
            self.assertFalse(self.window.cancelled)

        def test_final_document_write_must_finish_before_acceptance(self):
            self.resume.departure_windows.return_value = []
            self.resume.refresh_departure.return_value = False
            self.window.close_windows([])
            self.window.process.write.assert_not_called()
            self.assertTrue(self.window.button.isEnabled())
            self.resume.refresh_departure.return_value = True
            self.window.close_windows([])
            self.window.process.write.assert_called_once_with(b"continue\n")

        def test_failed_final_read_cancels_and_retains_last_good_recovery(self):
            self.window.touched = True
            self.resume.departure_windows.return_value = []
            self.resume.refresh_departure.side_effect = RuntimeError("bad native session")
            self.window.close_windows([])
            self.window.process.write.assert_not_called()
            self.assertTrue(self.window.cancelled)
            self.window.process_finished(1, QProcess.NormalExit)
            self.resume.cancel_departure.assert_called_once()
            self.quick.trip_apps_again.assert_called_once()

        def test_cancel_during_editor_preparation_cannot_send_the_close_request(self):
            target = {"id":"editor", "pid":12, "app":"org.kde.kwrite.desktop", "closeable":True}
            self.resume.departure_windows.return_value = [target]
            self.resume.prepare_editor_close.side_effect = lambda *args: self.window.reject()
            self.window.close_windows([])
            self.assertEqual(self.resume.departure_windows.call_args_list, [unittest.mock.call()])
            self.window.process.write.assert_not_called()

        def test_all_editors_are_watched_before_the_first_window_is_closed(self):
            windows = [{"id":"blocking-app", "app":"other.desktop", "closeable":True},
                       {"id":"editor-one", "app":"org.kde.kate.desktop", "pid":12, "closeable":True},
                       {"id":"editor-two", "app":"org.kde.kwrite.desktop", "pid":13, "closeable":True}]
            watched=[]
            self.resume.prepare_editor_close.side_effect=lambda path,ident,target,frames:watched.append(target["id"])
            def inspect(close=None):
                if close:
                    self.assertEqual(watched,["editor-one","editor-two"])
                    self.assertEqual(close,"blocking-app")
                return windows
            self.resume.departure_windows.side_effect=inspect
            self.window.close_windows([])
            self.window.process.write.assert_not_called()

        def test_editor_watch_starts_before_privileged_preflight_and_cancel_stops_it(self):
            self.window.phase="capture"
            self.window.process.readAllStandardOutput.return_value=b"a"*32
            self.resume.departure_windows.return_value=[{"id":"editor", "app":"org.kde.kate.desktop", "pid":12}]
            self.resume.prepare_editor_close.side_effect=lambda *args:self.window.reject()
            self.window.process_finished(0,QProcess.NormalExit)
            self.assertTrue(self.window.cancelled)
            self.window.process.start.assert_not_called()
            self.window.process.write.assert_not_called()

        def test_multiple_browser_windows_wait_for_native_quit_without_closing_them_individually(self):
            self.resume.BROWSER = "browser.desktop"
            self.resume.departure_windows.return_value = [
                {"id": name, "pid": 42, "app": self.resume.BROWSER, "closeable": True} for name in ("one", "two")]
            self.window.close_windows([])
            self.resume.departure_windows.assert_called_once_with()
            self.window.process.write.assert_not_called()
            self.assertIn("Quit the browser", self.window.message.text())
            self.assertTrue(self.window.button.isEnabled())

        def test_inspection_error_cancels_without_accepting(self):
            self.resume.departure_windows.side_effect = RuntimeError("lost KWin")
            self.window.close_windows([])
            self.window.process.write.assert_not_called()
            self.window.process.closeWriteChannel.assert_called_once()
            self.assertTrue(self.window.cancelled)

        def test_cancel_during_nested_window_inspection_cannot_race_into_acceptance(self):
            def inspect():
                self.window.reject()
                return []
            self.resume.departure_windows.side_effect = inspect
            self.window.close_windows([])
            self.window.process.write.assert_not_called()

        def test_escape_cancels_then_restores_only_this_attempt(self):
            self.window.touched = True
            QTest.keyClick(self.window, Qt.Key_Escape)
            self.assertTrue(self.window.cancelled)
            self.window.process.closeWriteChannel.assert_called_once()
            self.window.process_finished(1, QProcess.NormalExit)
            self.resume.cancel_departure.assert_called_once_with(self.quick.TRIP_APPS, "a" * 32)
            self.quick.trip_apps_again.assert_called_once_with(request="a" * 32)
            self.assertEqual(self.window.button.text(), "Close")
            self.assertTrue(self.window.detail.isHidden())

        def test_restart_failure_restores_closed_apps_without_claiming_success(self):
            self.window.phase, self.window.touched = "restart", True
            self.window.process_finished(1, QProcess.NormalExit)
            self.assertIn("couldn't", self.window.message.text())
            self.quick.trip_apps_again.assert_called_once()


if __name__ == "__main__":
    unittest.main()
