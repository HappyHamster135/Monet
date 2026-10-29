"""Durable, honest return feedback and the actual keyboard-operated recovery UI."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_resume import r
from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class ReturnSummary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trip.json"; self.off = self.path.with_name("off")
        self.state = {"version": 2, "id": "a" * 32, "time": 100, "boot": "old",
                      "apps": ["a.desktop", "b.desktop"], "windows": [], "done": []}
        for owner, name, value in ((r, "boot_id", "new"), (r, "window_snapshot", []),
                                  (r.time, "time", 110), (r.time, "sleep", None)):
            p = patch.object(owner, name, return_value=value); p.start(); self.addCleanup(p.stop)
        r.atomic_write(self.path, self.state)
        self.launch = Mock(); self.entry = Mock(return_value=True)

    def restore(self, **kwargs):
        return r.restore(self.path, self.off, lambda: [], self.entry, self.launch, **kwargs)

    def status(self):
        return r.return_status(self.path, self.off)

    def test_results_survive_completion_and_never_replay_a_finished_app(self):
        r.window_snapshot.side_effect = [[], [{"id": "a", "app": "a.desktop"}],
                                        [{"id": "b", "app": "b.desktop"}]]
        self.assertEqual(self.restore(), ["a.desktop", "b.desktop"])
        self.assertFalse(self.path.exists())
        state = self.status()
        self.assertEqual([i["status"] for i in state["items"]], ["opened", "opened"])
        self.assertFalse(state["retry"])
        self.assertEqual(r.return_path(self.path).stat().st_mode & 0o777, 0o600)
        self.restore(request=state["id"])
        self.assertEqual(self.launch.call_count, 2)

    def test_missing_app_can_be_reinstalled_and_only_that_app_retried(self):
        self.entry.side_effect = lambda app: app == "a.desktop"
        r.window_snapshot.side_effect = [[], [{"id": "a", "app": "a.desktop"}]]
        self.restore()
        state = self.status()
        self.assertEqual(state["items"][1]["status"], "missing-app")
        self.assertTrue(state["items"][1]["retry"])
        self.entry.side_effect = None
        r.window_snapshot.side_effect = [[], [{"id": "b", "app": "b.desktop"}]]
        self.assertEqual(self.restore(selected="b.desktop", request=state["id"]), ["b.desktop"])
        self.assertEqual([c.args[0] for c in self.launch.call_args_list], ["a.desktop", "b.desktop"])

    def test_interrupted_opening_is_not_a_success_or_a_permanent_busy_state(self):
        report = r.initial_return(self.state); report["items"]["a.desktop"]["status"] = "opening"
        r.save_return(self.path, self.state, report)
        with r.restore_lock(self.path):
            state = self.status()
            self.assertTrue(state["busy"]); self.assertFalse(state["retry"])
            self.assertFalse(r.clear_return(self.path, self.off, state["id"]))
        state = self.status()
        self.assertFalse(state["busy"]); self.assertTrue(state["retry"])
        self.assertEqual(state["items"][0]["status"], "unconfirmed")

    def test_stale_buttons_cannot_launch_or_dismiss_a_new_trip(self):
        before = self.path.read_bytes()
        self.assertEqual(self.restore(request="b" * 32), [])
        self.assertFalse(r.clear_return(self.path, self.off, "b" * 32))
        self.assertEqual(self.path.read_bytes(), before); self.launch.assert_not_called()

    def test_cancelled_same_boot_is_hidden_and_off_clears_summary(self):
        r.save_return(self.path, self.state, r.initial_return(self.state))
        r.boot_id.return_value = "old"
        self.assertFalse(self.status()["available"])
        self.restore(); self.assertTrue(self.path.exists())
        r.boot_id.return_value = "new"; self.off.touch(); self.restore()
        self.assertFalse(self.status()["available"])
        self.assertFalse(self.path.exists()); self.assertFalse(r.return_path(self.path).exists())

    def test_expired_checkpoint_still_explains_why_no_apps_opened(self):
        r.time.time.return_value = 100000
        self.restore()
        self.assertFalse(self.path.exists()); self.launch.assert_not_called()
        state = self.status()
        self.assertEqual([i["status"] for i in state["items"]], ["expired", "expired"])
        self.assertFalse(state["retry"])

    def test_dismiss_removes_only_recovery_metadata(self):
        personal = self.path.parent / "saved.txt"; personal.write_text("my work")
        r.save_return(self.path, self.state, r.initial_return(self.state))
        self.assertTrue(r.clear_return(self.path, self.off, self.state["id"]))
        self.assertFalse(self.status()["available"])
        self.assertEqual(personal.read_text(), "my work")

    def test_partial_document_result_does_not_claim_every_document_was_restored(self):
        present = self.path.parent / "saved.txt"; present.write_text("my work")
        absent = self.path.parent / "missing <work>.txt"
        app = "org.kde.kate.desktop"
        self.state.update(apps=[app], documents={app: [str(present), str(absent)]})
        r.atomic_write(self.path, self.state)
        r.window_snapshot.side_effect = [[], [{"id": "editor", "app": app}]]
        with patch.object(r.subprocess, "Popen") as start:
            self.restore()
        self.assertIn(str(present), start.call_args.args[0]); self.assertNotIn(str(absent), start.call_args.args[0])
        item = self.status()["items"][0]
        self.assertEqual(item["status"], "documents-missing")
        self.assertEqual(item["missing"], [absent.name]); self.assertEqual(item["documents"], 1)
        self.assertTrue(item["retry"])
        self.assertTrue(self.path.exists())
        self.assertFalse(absent.exists())

    def test_corrupt_summary_reports_an_error_without_discarding_checkpoint(self):
        for item in ({"status": []}, {"status": "opened", "missing": "bad"}, {"status": "invented"}):
            report = r.initial_return(self.state); report["items"]["a.desktop"] = item
            self.assertFalse(r.valid_return(report))
            r.atomic_write(r.return_path(self.path), report)
            with self.assertRaises(OSError): self.status()
            self.assertTrue(self.path.exists())
        report = r.initial_return(self.state)
        r.atomic_write(r.return_path(self.path), report)
        self.state["apps"] = None; self.state["done"] = None; r.atomic_write(self.path, self.state)
        self.assertFalse(self.status()["retry"])

    def test_checkpoint_receipt_wins_if_separate_summary_write_was_interrupted(self):
        report = r.initial_return(self.state)
        r.atomic_write(r.return_path(self.path), report)
        report["items"]["a.desktop"]["status"] = "opened"
        self.state["done"] = ["a.desktop"]; self.state["return"] = report
        r.atomic_write(self.path, self.state)
        self.assertEqual(self.status()["items"][0]["status"], "opened")
        self.assertFalse(self.status()["items"][0]["retry"])

    def test_notice_is_once_per_trip_and_a_failed_dispatch_is_retryable(self):
        self.q = quick_helper()
        r.save_return(self.path, self.state, r.initial_return(self.state))
        with patch.object(self.q, "resume_helper", return_value=r), patch.object(self.q, "TRIP_APPS", self.path), \
                patch.object(self.q, "TRIP_APPS_OFF", self.off), patch.object(self.q, "ok", return_value=False) as start:
            self.assertFalse(self.q.queue_return_notice())
            start.return_value = True
            self.assertTrue(self.q.queue_return_notice()); self.assertTrue(self.q.queue_return_notice())
            self.assertEqual(start.call_count, 2)
            self.assertIn("return-notice", start.call_args.args)
            self.assertIn("--unit=monet-return-notice-" + self.state["id"], start.call_args.args)


class ReturnActions(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.state = {"id": "a" * 32, "available": True, "busy": False, "items": [
            {"app": "a.desktop", "retry": True, "canOpen": True, "needsAttention": True}]}

    def test_worker_start_is_durable_and_does_not_accept_unlisted_apps_or_old_trips(self):
        with patch.object(self.q, "return_status", return_value=self.state), \
                patch.object(self.q, "return_worker_active", return_value=False) as busy, \
                patch.object(self.q, "ok", return_value=True) as start:
            self.assertFalse(self.q.retry_return("b" * 32))
            self.assertFalse(self.q.retry_return(self.state["id"], "unlisted.desktop"))
            self.assertTrue(self.q.retry_return(self.state["id"], "a.desktop"))
            self.assertIn("--unit=monet-return", start.call_args.args)
            self.assertIn("--setenv=XDG_STATE_HOME=" + str(self.q.TRIP_APPS.parent.parent.resolve()), start.call_args.args)
            self.assertEqual(start.call_args.args[-3:], ("return-run", self.state["id"], "a.desktop"))
            busy.return_value = True
            self.assertTrue(self.q.retry_return(self.state["id"], "a.desktop")); start.assert_called_once()

    def test_notice_reviews_the_matching_return_without_claiming_complete_recovery(self):
        with patch.object(self.q, "return_status", return_value=self.state), patch.object(self.q, "run", return_value="open") as send, \
                patch.object(self.q, "open_settings") as opened:
            self.q.show_return_notice("b" * 32); send.assert_not_called()
            self.q.show_return_notice(self.state["id"])
            self.assertIn("Some work needs attention", send.call_args.args[-1])
            opened.assert_called_once_with("windows#return")


try:
    from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl, Qt, QSettings, QStandardPaths, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class ReturnHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)
        def __init__(self):
            super().__init__(); self.ticket = 0; self.actions = []; self.fail = False; self.readFail = False
            self.delay = 30; self.readDelay = 5
            self.state = {"id": "a" * 32, "available": True, "busy": False, "retry": True, "items": [
                {"app": "a.desktop", "name": "A saved app", "detail": "Opening wasn't confirmed.",
                 "retry": True, "canOpen": True, "status": "unconfirmed"},
                {"app": "b.desktop", "name": "Editor", "detail": "Some documents are unavailable.",
                 "retry": True, "canOpen": True, "status": "documents-missing", "missingCount": 1,
                 "missing": ["notes <work>.txt"]}]}

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1; ticket = self.ticket; verb = command[1] if len(command) > 1 else ""; delay = 1; code = 0; result = {}
            if verb == "return-status":
                delay = self.readDelay; result = self.state
                if self.readFail: result = {}; code = 1
            elif verb in ("return-retry", "return-open", "return-dismiss"):
                self.actions.append(command[1:]); delay = self.delay
                if not self.fail:
                    if verb == "return-dismiss": self.state = {"available": False, "busy": False, "items": []}
                    elif verb == "return-retry": self.state = dict(self.state, busy=True, retry=False)
                result = {"ok": not self.fail, "state": self.state}; code = 1 if self.fail else 0
            elif verb == "pc": result = {"windows": "Ready"}
            elif verb == "library": result = []
            output = json.dumps(result)
            QTimer.singleShot(delay, lambda: self.done.emit(ticket, output, code, ""))
            return ticket


@unittest.skipUnless(QT, "Qt/Kirigami runtime")
class ReturnUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([]); cls.app.setQuitOnLastWindowClosed(False)
        cls.identity = (cls.app.organizationName(), cls.app.organizationDomain(), cls.app.applicationName())
        cls.config = tempfile.TemporaryDirectory()
        cls.app.setOrganizationName("monet-return-tests"); cls.app.setOrganizationDomain("tests.invalid")
        cls.app.setApplicationName("settings")
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, cls.config.name)
        loader = importlib.machinery.SourceFileLoader("return_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader)); loader.exec_module(cls.games)

    @classmethod
    def tearDownClass(cls):
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation))
        cls.app.setOrganizationName(cls.identity[0]); cls.app.setOrganizationDomain(cls.identity[1]); cls.app.setApplicationName(cls.identity[2])
        cls.config.cleanup()

    def setUp(self):
        self.engine = QQmlApplicationEngine(); self.helper = ReturnHelper(); self.words = self.games.Words(); self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "windows#return", "blurBehind": False,
            "pictures": (ROOT / "linux/share/monet/settings").as_uri() + "/",
            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]; QTest.qWait(120)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(10); self.assertEqual(self.errors, [])

    def item(self, name):
        todo = [self.window.contentItem()]
        while todo:
            item = todo.pop()
            if item.objectName() == name: return item
            todo.extend(item.childItems())
        self.fail(name + " missing")

    def press(self, name):
        self.item(name).forceActiveFocus(); QTest.keyClick(self.window, Qt.Key_Return)

    def test_repeat_keyboard_actions_are_ignored_while_retry_is_starting_and_running(self):
        self.helper.delay = 100
        self.press("returnRetry-a.desktop"); self.press("returnRetry-a.desktop")
        self.assertEqual(len(self.helper.actions), 1)
        self.assertTrue(self.window.property("returnBusy")); QTest.qWait(160)
        self.assertFalse(self.item("returnDismiss").property("enabledPill"))
        self.press("returnOpen-a.desktop"); self.assertEqual(len(self.helper.actions), 1)

    def test_tab_from_the_return_destination_reaches_its_actions_without_visiting_the_sidebar(self):
        self.assertTrue(self.item("search-return").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item("returnRetryAll").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item("returnDismiss").hasActiveFocus())

    def test_failed_action_remains_visible_across_successful_refresh_and_can_be_retried(self):
        self.helper.fail = True; self.press("returnRetryAll"); QTest.qWait(100)
        self.assertTrue(self.window.property("returnProblem"))
        QMetaObject.invokeMethod(self.window, "loadReturn"); QTest.qWait(50)
        self.assertTrue(self.window.property("returnProblem"))
        self.helper.fail = False; self.press("returnRetryAll"); QTest.qWait(100)
        self.assertFalse(self.window.property("returnProblem")); self.assertEqual(len(self.helper.actions), 2)

    def test_late_refresh_cannot_resurrect_a_dismissed_list_and_focus_is_retained(self):
        self.helper.readDelay = 200
        QMetaObject.invokeMethod(self.window, "loadReturn")
        self.press("returnDismiss"); QTest.qWait(350)
        self.assertFalse(self.window.property("returnInfo").toVariant()["available"])
        self.assertTrue(self.item("search-return").hasActiveFocus())
        self.assertFalse(self.window.property("returnLoading"))

    def test_failed_refresh_keeps_last_known_list_and_retry_restores_status(self):
        self.helper.readFail = True; QMetaObject.invokeMethod(self.window, "loadReturn"); QTest.qWait(60)
        self.assertTrue(self.window.property("returnReadProblem"))
        self.assertTrue(self.window.property("returnInfo").toVariant()["available"])
        self.helper.readFail = False; self.press("returnRefresh"); QTest.qWait(60)
        self.assertFalse(self.window.property("returnReadProblem"))

    def test_background_refresh_keeps_keyboard_focus_inside_the_recovery_card(self):
        self.item("returnOpen-a.desktop").forceActiveFocus()
        QMetaObject.invokeMethod(self.window, "loadReturn"); QTest.qWait(60)
        self.assertTrue(self.item("returnOpen-a.desktop").hasActiveFocus())
        self.helper.state = dict(self.helper.state, busy=True)
        QMetaObject.invokeMethod(self.window, "loadReturn"); QTest.qWait(60)
        self.assertTrue(self.item("search-return").hasActiveFocus())

    def test_controls_fit_a_narrow_window_and_missing_names_are_plain_text(self):
        self.window.setWidth(760); QTest.qWait(100)
        for app in ("a.desktop", "b.desktop"):
            button = self.item("returnOpen-" + app)
            row = button.parentItem().parentItem().parentItem()
            self.assertLessEqual(button.mapToItem(row, 0, 0).x() + button.width(), row.width())
            self.assertLessEqual(button.mapToItem(row, 0, 0).y() + button.height(), row.height())
        todo = [self.item("search-return")]; found = False
        while todo:
            item = todo.pop(); todo.extend(item.childItems())
            if "notes <work>.txt" in (item.property("text") or ""):
                expression = QQmlExpression(self.engine.contextForObject(item), item, "textFormat === Text.PlainText")
                found = True; self.assertTrue(expression.evaluate()[0])
        self.assertTrue(found)

    def test_missing_document_retry_uses_the_existing_recovery_worker(self):
        button = self.item("returnRetry-b.desktop")
        self.assertEqual(button.property("text"), "Retry documents")
        self.press("returnRetry-b.desktop"); QTest.qWait(60)
        self.assertEqual(self.helper.actions, [["return-retry", "a" * 32, "b.desktop"]])

    def test_games_restart_explanation_and_buttons_fit_a_small_window(self):
        engine = QQmlApplicationEngine(); errors = []
        engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
        context = engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "blurBehind": False,
            "art": (ROOT / "linux/share/monet/settings").as_uri() + "/",
            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/games/Games.qml")))
        self.assertTrue(engine.rootObjects(), errors)
        window = engine.rootObjects()[0]
        try:
            window.setWidth(760); window.setHeight(520)
            window.setProperty("asking", {"name": "A test game", "windows": "test-game", "store": "steam", "art": ""})
            window.setProperty("sheetOpen", True); QTest.qWait(150)
            todo = [window.contentItem()]; found = set()
            while todo:
                item = todo.pop(); todo.extend(item.childItems())
                text = item.property("text") or ""
                if item.isVisible() and (text.startswith("Unsaved changes") or text in ("Cancel", "Restart & Play")):
                    found.add("explanation" if text.startswith("Unsaved") else text)
                    point = item.mapToItem(window.contentItem(), 0, 0)
                    self.assertGreaterEqual(point.y(), 0)
                    self.assertLessEqual(point.y() + item.height(), window.height())
                    self.assertLessEqual(point.x() + item.width(), window.width())
            self.assertEqual(found, {"explanation", "Cancel", "Restart & Play"})
            self.assertEqual(errors, [])
        finally:
            window.close(); engine.deleteLater(); QTest.qWait(5)


if __name__ == "__main__":
    unittest.main()
