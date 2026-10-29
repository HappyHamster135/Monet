"""Notification deadlines, verified writes, and the real Settings controls."""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Linux notification settings and file locking")
class Notifications(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.q.FOCUS_QUIET = Path(self.temp.name) / "focus-quiet.json"

    def test_kconfig_dates_and_expired_deadlines(self):
        q = self.q
        expected = datetime.datetime(2026, 10, 27, 22, 30, 12, 250000, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual(q.quiet_until("2026,10,27,22,30,12.25,UTC"), expected)
        self.assertEqual(q.quiet_until("2026,10,27,23,30,12.25,Europe/Stockholm"), expected)
        self.assertEqual(q.quiet_until("2026,10,28,0,30,12.25,UTC+02:00"), expected)
        self.assertTrue(q.quiet_state("2026,10,27,22,30,12.25,UTC", now=expected-1)["quiet"])
        self.assertFalse(q.quiet_state("2026,10,27,22,30,12.25,UTC", now=expected)["quiet"])
        for text in ("", "broken", "2026,2,30,12,0,0", "2026,10,27,24,0,0", "2026,10,27,12,0,nan",
                     "2026,10,27,12,0,0,Not/AZone", "2026,10,27,12,0,0,UTC+01:99"):
            with self.subTest(text=text):
                self.assertFalse(q.quiet_state(text, now=0)["quiet"])
                self.assertIsNone(q.quiet_until(text))

    def quiet_run(self, config, writes=True):
        def run(*args, **kwargs):
            key = args[args.index("--key") + 1]
            if args[0] == "kwriteconfig6":
                if writes:
                    if args[-1] == "--delete": config.pop(key, None)
                    else: config[key] = args[-1]
                return ""  # Also exercises an immutable key whose tool exits successfully.
            return config.get(key, "")
        return run

    def test_duration_indefinite_off_and_write_readback(self):
        q = self.q
        config = {"NotificationSoundsMuted": "true", "WhenFullscreen": "false"}
        now = 1793136637
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            for mode, length in (("hour", 3600), ("four-hours", 14400)):
                result = q.set_quiet(mode)
                self.assertTrue(result["ok"])
                self.assertEqual(result["quietUntil"], ((now + length) // 60) * 60)
                self.assertFalse(result["quietIndefinite"])
            self.assertTrue(q.set_quiet("on")["quietIndefinite"])
            self.assertFalse(q.set_quiet("off")["quiet"])
        self.assertEqual(config, {"NotificationSoundsMuted": "true", "WhenFullscreen": "false"})
        with patch.object(q, "run", side_effect=self.quiet_run(config, writes=False)):
            self.assertFalse(q.set_quiet("hour")["ok"])
        with patch.object(q, "run", return_value=None):
            self.assertFalse(q.set_quiet("off")["ok"])

    @unittest.skipUnless(hasattr(time, "tzset"), "POSIX time-zone switching")
    def test_duration_and_tomorrow_across_daylight_saving(self):
        q = self.q
        original = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Stockholm"; time.tzset()
        try:
            # The clocks go back the following morning. Tomorrow still means 08:00 local.
            now = datetime.datetime(2026, 10, 24, 23, 30).timestamp()
            config = {}
            with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
                result = q.set_quiet("tomorrow")
                self.assertTrue(result["ok"])
                self.assertEqual(datetime.datetime.fromtimestamp(result["quietUntil"]), datetime.datetime(2026, 10, 25, 8))
                self.assertEqual(q.set_quiet("four-hours")["quietUntil"], now + 14400)
                self.assertEqual(q.quiet_until("2026,10,24,23,30,0"), now)
        finally:
            if original is None: os.environ.pop("TZ", None)
            else: os.environ["TZ"] = original
            time.tzset()

    def test_notification_actions_require_matching_readback_and_keep_history(self):
        q = self.q
        written = {}
        def write(file, group, key, value):
            written[str(group), key] = str(value)
            return True
        def read(file, group, key, default=""):
            return written.get((str(group), key), default)
        with patch.object(q, "kwrite", side_effect=write), patch.object(q, "kread", side_effect=read), \
                patch.object(q, "notify_state", return_value={"apps": [], "quiet": False}):
            for command, args in (("notify-rule", ["mirrored", "off"]), ("notify-rule", ["urgent", "on"]),
                                  ("notify-place", ["topright"]), ("notify-time", ["10"]),
                                  ("notify-app", ["org.kde.dolphin".encode().hex(), "off"])):
                self.assertTrue(q.change_notifications(command, args)["ok"])
            self.assertEqual(written["DoNotDisturb", "WhenScreenSharing"], "false")
            self.assertEqual(written["('Applications', 'org.kde.dolphin')", "ShowPopups"], "false")
            self.assertFalse(any(key in ("ShowInHistory", "NotificationSoundsMuted") for group, key in written))
            with patch.object(q, "kread", return_value="unchanged"):
                self.assertFalse(q.change_notifications("notify-time", ["5"])["ok"])
            with patch.object(q, "kwrite", return_value=False):
                self.assertFalse(q.change_notifications("notify-time", ["10"])["ok"])
            count = len(written)
            for command, args in (("notify-time", ["999"]), ("notify-rule", ["sounds", "off"]),
                                  ("notify-app", ["[Global]".encode().hex(), "off"]), ("notify-place", ["bad"])):
                self.assertFalse(q.change_notifications(command, args)["ok"])
            self.assertEqual(len(written), count)

    def test_focus_keeps_existing_quiet_deadline_and_unrelated_preferences(self):
        q = self.q
        now = 1793136600
        for previous in ("", "2099,12,31,23,59,0,UTC", "2026,10,27,23,45,0,UTC",
                         "2026,10,27,21,40,0,UTC"):
            with self.subTest(previous=previous):
                config = {"Until": previous, "WhenFullscreen": "false"} if previous else {"WhenFullscreen": "false"}
                original = config.copy()
                with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
                    self.assertTrue(q.focus_quiet(now + 1800, "41")["ok"])
                    self.assertEqual(q.quiet_until(config["Until"]), max(now + 1800, q.quiet_until(previous) or 0))
                    self.assertTrue(q.focus_quiet(None, "41")["ok"])
                self.assertEqual(config, original)
                self.assertFalse(q.FOCUS_QUIET.exists())

    def test_focus_respects_new_manual_choices_in_monet_and_other_settings(self):
        q = self.q
        now = 1793136600
        config = {}
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            for mode in ("on", "off", "hour"):
                self.assertTrue(q.focus_quiet(now + 1200, "42")["ok"])
                self.assertTrue(q.set_quiet(mode)["ok"])
                chosen = config.copy()
                self.assertTrue(q.focus_quiet(None, "42")["ok"])
                self.assertEqual(config, chosen)
            self.assertTrue(q.focus_quiet(now + 7200, "42")["ok"])
            config["Until"] = "2026,10,28,8,0,0,Europe/Stockholm"
            chosen = config.copy()
            self.assertTrue(q.focus_quiet(None, "42")["ok"])
            self.assertEqual(config, chosen)

    def test_overlapping_timers_and_helper_restart_preserve_the_remaining_timer(self):
        q = self.q
        now = 1793136600
        config = {}
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            self.assertTrue(q.focus_quiet(now + 600, "43")["ok"])
            self.assertTrue(q.focus_quiet(now + 1800, "44")["ok"])
        restarted = quick_helper()
        restarted.FOCUS_QUIET = q.FOCUS_QUIET
        with patch.object(restarted, "run", side_effect=self.quiet_run(config)), patch.object(restarted.time, "time", return_value=now):
            result = restarted.focus_quiet(None, "44")
            self.assertEqual(result, {"ok": True, "remaining": 1})
            self.assertEqual(q.quiet_until(config["Until"]), now + 600)
            restarted.focus_quiet(None, "43")
            self.assertEqual(config, {})

    def test_expired_timer_restores_previous_value_without_starting_another_period(self):
        q = self.q
        now = 1793136600
        config = {}
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            q.focus_quiet(now + 60, "45")
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now + 120):
            self.assertTrue(q.focus_quiet(None, "45")["ok"])
            self.assertEqual(config, {})
            self.assertFalse(q.focus_quiet(now + 60, "45")["ok"])

    def test_focus_failures_never_erase_a_manual_preference(self):
        q = self.q
        now = 1793136600
        config = {"Until": "2026,10,27,21,40,0,UTC"}
        original = config.copy()
        with patch.object(q, "run", side_effect=self.quiet_run(config, writes=False)), patch.object(q.time, "time", return_value=now):
            self.assertFalse(q.focus_quiet(now + 1800, "46")["ok"])
            self.assertEqual(config, original)
            q.focus_quiet(None, "46")
            self.assertEqual(config, original)
        q.FOCUS_QUIET.write_text("not json")
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            self.assertTrue(q.focus_quiet(None, "46")["ok"])
            self.assertEqual(config, original)
            with patch.object(q, "save_focus_quiet", side_effect=OSError("disk full")):
                self.assertFalse(q.focus_quiet(now + 1800, "46")["ok"])
                self.assertEqual(config, original)
        with patch.object(q, "run", return_value=None):
            self.assertFalse(q.focus_quiet(None, "46")["ok"])

    def test_failed_manual_write_keeps_timer_ownership_for_cleanup(self):
        q = self.q
        now = 1793136600
        config = {}
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            q.focus_quiet(now + 1800, "47")
            record = q.FOCUS_QUIET.read_bytes()
            with patch.object(q, "run", side_effect=self.quiet_run(config, writes=False)):
                self.assertFalse(q.set_quiet("off")["ok"])
            self.assertEqual(q.FOCUS_QUIET.read_bytes(), record)
            q.focus_quiet(None, "47")
            self.assertEqual(config, {})

    def test_failed_second_timer_keeps_first_timer_ownership(self):
        q = self.q
        now = 1793136600
        config = {}
        with patch.object(q, "run", side_effect=self.quiet_run(config)), patch.object(q.time, "time", return_value=now):
            q.focus_quiet(now + 600, "48")
            self.assertEqual(q.FOCUS_QUIET.stat().st_mode & 0o777, 0o600)
            first = q.FOCUS_QUIET.read_bytes()
            with patch.object(q, "run", side_effect=self.quiet_run(config, writes=False)):
                self.assertFalse(q.focus_quiet(now + 1800, "49")["ok"])
            self.assertEqual(q.FOCUS_QUIET.read_bytes(), first)
            self.assertEqual(q.focus_quiet(None, "49")["remaining"], 1)
            self.assertEqual(q.quiet_until(config["Until"]), now + 600)
            self.assertTrue(q.focus_quiet(None, "48")["ok"])
            self.assertEqual(config, {})


try:
    from PySide6.QtCore import QObject, QMetaObject, QSettings, QStandardPaths, QTimer, QUrl, Signal, Slot, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine, QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "Qt runtime")
class TimerRequests(unittest.TestCase):
    def test_rapid_pause_and_resume_send_only_the_latest_intent_in_order(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        js = QJSEngine()
        source = (ROOT / "linux/share/plasma/plasmoids/org.monet.timer/contents/ui/main.qml").read_text()
        js.evaluate("""var root=this, focusActive='', focusPending='', helper='/helper',
            Plasmoid={id:52}, sent=[], disconnected=[],
            runner={connectSource:function(s){sent.push(s)}};
            function disconnectSource(s){disconnected.push(s)};""")
        for name in ("requestFocus", "sendFocus"):
            result = js.evaluate(re.search(r"    (function " + name + r"\(.*?\n    })", source, re.S).group(1))
            self.assertFalse(result.isError(), result.toString())
        handler = re.search(r"onNewData: (source => \{.*?\n        })", source, re.S).group(1)
        self.assertFalse(js.evaluate("var completed = " + handler).isError())
        js.evaluate("requestFocus('100'); requestFocus('off'); requestFocus('200')")
        self.assertEqual(js.evaluate("sent").toVariant(), ["/helper focus 100 52"])
        js.evaluate("completed('/helper ring alarm')")
        self.assertEqual(js.evaluate("focusActive").toString(), "/helper focus 100 52")
        js.evaluate("completed('/helper focus 100 52')")
        self.assertEqual(js.evaluate("sent").toVariant(), ["/helper focus 100 52", "/helper focus 200 52"])
        js.evaluate("completed('/helper focus 200 52'); requestFocus('off'); completed('/helper focus off 52')")
        self.assertEqual(js.evaluate("sent").toVariant()[-1], "/helper focus off 52")
        self.assertEqual(js.evaluate("focusActive + focusPending").toString(), "")

if QT:
    class FakeHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)
        def __init__(self):
            super().__init__(); self.ticket = 0; self.actions = []; self.fail = False; self.malformed = False
            self.state = {"quiet": False, "quietUntil": None, "quietIndefinite": False, "apps": [],
                          "fullscreen": True, "mirrored": True, "urgent": True, "place": "clock", "time": 5}

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1; ticket = self.ticket
            if command[1] == "notify":
                out = json.dumps(self.state)
                QTimer.singleShot(1, lambda: self.done.emit(ticket, out, 0, ""))
            elif command[1] == "quiet":
                self.actions.append(command)
                if not self.fail:
                    self.state.update(quiet=True, quietUntil=time.time()+3600)
                out = "{}" if self.malformed else json.dumps({"ok": not self.fail, "state": self.state})
                QTimer.singleShot(90, lambda: self.done.emit(ticket, out, 0, ""))
            else:
                QTimer.singleShot(1, lambda: self.done.emit(ticket, "{}", 0, ""))
            return ticket


@unittest.skipUnless(QT, "Qt runtime")
class NotificationUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.config = tempfile.TemporaryDirectory()
        cls.identity = (cls.app.organizationName(), cls.app.organizationDomain(), cls.app.applicationName())
        cls.app.setOrganizationName("monet-notification-tests")
        cls.app.setOrganizationDomain("tests.invalid")
        cls.app.setApplicationName("settings")
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, cls.config.name)
        loader = importlib.machinery.SourceFileLoader("notification_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    @classmethod
    def tearDownClass(cls):
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation))
        cls.app.setOrganizationName(cls.identity[0]); cls.app.setOrganizationDomain(cls.identity[1]); cls.app.setApplicationName(cls.identity[2])
        cls.config.cleanup()

    def setUp(self):
        self.engine = QQmlApplicationEngine(); self.words = self.games.Words(); self.helper = FakeHelper()
        self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "notifications", "blurBehind": False,
                            "pictures": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings") + "/").toString(),
                            "brush": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/textures/brush.png")).toString()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]; QTest.qWait(100)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(1)
        self.assertFalse(self.errors, "\n".join(self.errors))

    def item(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name: return item
            pending.extend(item.childItems())
        self.fail(name + " missing")

    def test_keyboard_duration_waits_for_result_and_repeated_click_is_ignored(self):
        button = self.item("quiet-hour")
        QMetaObject.invokeMethod(button, "forceActiveFocus")
        QTest.keyClick(self.window, Qt.Key_Space)
        self.assertEqual(self.window.property("notifyBusy"), "quiet hour")
        self.assertFalse(self.item("doNotDisturb").property("checked"))
        QMetaObject.invokeMethod(button, "clicked")
        self.assertEqual(len(self.helper.actions), 1)
        QTest.qWait(130)
        self.assertTrue(self.item("doNotDisturb").property("checked"))
        self.assertIn("Quiet until", self.item("doNotDisturb").property("detail"))
        self.assertEqual(self.window.property("notifyMessage"), "Saved")

    def test_failed_or_malformed_response_keeps_feedback_and_retry(self):
        self.helper.fail = True
        QMetaObject.invokeMethod(self.item("quiet-hour"), "clicked"); QTest.qWait(130)
        self.assertTrue(self.window.property("notifyFailed"))
        self.assertFalse(self.item("doNotDisturb").property("checked"))
        self.assertEqual(self.window.property("notifyRetry"), "quiet hour")
        QMetaObject.invokeMethod(self.item("notificationRetry"), "forceActiveFocus")
        self.assertTrue(self.item("notificationRetry").property("activeFocus"))
        self.helper.fail = False; self.helper.malformed = True
        QMetaObject.invokeMethod(self.item("quiet-hour"), "clicked"); QTest.qWait(130)
        self.assertTrue(self.window.property("notifyFailed"))
        self.helper.malformed = False
        QMetaObject.invokeMethod(self.item("quiet-hour"), "clicked"); QTest.qWait(130)
        self.assertFalse(self.window.property("notifyFailed"))
        self.assertTrue(self.item("doNotDisturb").property("checked"))

    def test_expiry_and_changes_elsewhere_are_refreshed(self):
        QMetaObject.invokeMethod(self.item("quiet-hour"), "clicked"); QTest.qWait(130)
        self.helper.state.update(quiet=False, quietUntil=None)
        QMetaObject.invokeMethod(self.window, "loadNotifications"); QTest.qWait(30)
        self.assertFalse(self.item("doNotDisturb").property("checked"))
        self.assertEqual(self.item("doNotDisturb").property("detail"), "Notifications pop up as they come")

    def test_tab_focus_reveals_controls_below_the_viewport(self):
        self.window.setHeight(540)
        scroller = self.item("settingsScroller")
        seen_below_fold = False
        QMetaObject.invokeMethod(self.item("quiet-hour"), "forceActiveFocus")
        for _ in range(18):
            QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(10)
            focus = self.window.activeFocusItem()
            if focus and scroller.property("contentY") > 0:
                point = focus.mapToItem(scroller, 0, 0)
                if point.y() >= 0:
                    self.assertLessEqual(point.y() + focus.height(), scroller.height())
                    seen_below_fold = True
        self.assertTrue(seen_below_fold)
