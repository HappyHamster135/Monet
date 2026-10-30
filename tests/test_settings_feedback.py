"""The appearance repair reports real failures and keeps its result visible."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl, Signal, Slot, Q_ARG
    from PySide6.QtGui import QGuiApplication, QWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


class LookRepair(unittest.TestCase):
    def test_failed_commands_cannot_report_success(self):
        q = quick_helper()
        with patch.object(q, "run", return_value="") as run, patch.object(q, "set_dodge", return_value=True) as dodge, \
                patch.object(q, "set_snap", return_value=True), patch.object(q, "prefs", return_value={"dodge": True, "snap": True}):
            self.assertEqual(q.look_reset(), {"done": True})
            run.side_effect = [None, ""]
            self.assertEqual(q.look_reset(), {"done": False})
            run.side_effect = ["", None]
            self.assertEqual(q.look_reset(), {"done": False})
            run.side_effect = None; dodge.return_value = False
            self.assertEqual(q.look_reset(), {"done": False})

    def test_snap_reports_a_failed_write_or_reconfigure(self):
        q = quick_helper()
        with patch.object(q, "kwrite", side_effect=[True, False, True]), patch.object(q, "busctl", return_value=""):
            self.assertFalse(q.set_snap(True))
        with patch.object(q, "kwrite", return_value=True), patch.object(q, "busctl", return_value=None):
            self.assertFalse(q.set_snap(True))


if QT:
    class FakeHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)
        def __init__(self):
            super().__init__(); self.ticket = 0; self.reply = ('{"done":true}', 0); self.resets = 0
            self.commands = []; self.hold_status = False; self.pending_status = []; self.scale_ticket = None

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket = self.ticket
            self.commands.append(list(command))
            if command[1] == "access-scale":
                self.scale_ticket = ticket
                return ticket
            if command[1] == "status" and self.hold_status:
                self.pending_status.append(ticket)
                return ticket
            if len(command) > 1 and command[1] == "look-reset":
                self.resets += 1
                out, code = self.reply
                QTimer.singleShot(60, lambda: self.done.emit(ticket, out, code, ""))
            else:
                QTimer.singleShot(1, lambda: self.done.emit(ticket, "{}", 0, ""))
            return ticket


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class LookFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        loader = importlib.machinery.SourceFileLoader("feedback_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    def setUp(self):
        self.engine = QQmlApplicationEngine(); self.words = self.games.Words(); self.helper = FakeHelper()
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "light", "blurBehind": False,
                            "pictures": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings") + "/").toString(),
                            "brush": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/textures/brush.png")).toString()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]; QTest.qWait(100)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(1)

    def test_scale_selection_waits_for_feedback_and_keeps_other_monitor_unchanged(self):
        screens = [dict(name="eDP-1",scale=200,width=3840,height=2400,highDensity=True),
                   dict(name="DP-1",scale=100,width=1920,height=1080,highDensity=False)]
        self.window.setProperty("displaySizes", screens)
        def change():
            QMetaObject.invokeMethod(self.window, "changeScreenSize", Q_ARG("QVariant", "DP-1"), Q_ARG("QVariant", 125))
        change();change()
        commands = [c for c in self.helper.commands if c[1] == "access-scale"]
        self.assertEqual(commands, [["helper", "access-scale", "125", "DP-1".encode().hex()]])
        self.assertTrue(self.window.property("scaleBusy"))
        self.helper.done.emit(self.helper.scale_ticket, json.dumps({"ok":False,"displays":screens,"error":"Display disconnected"}), 0, "")
        QTest.qWait(10)
        self.assertFalse(self.window.property("scaleBusy"));self.assertEqual(self.window.property("scaleProblem"), "Display disconnected")
        change();screens[1]["scale"] = 125
        self.helper.done.emit(self.helper.scale_ticket, json.dumps({"ok":True,"displays":screens}), 0, "")
        QTest.qWait(10)
        self.assertEqual(self.window.property("scaleProblem"), "")
        state=self.window.property("displaySizes").toVariant()
        self.assertEqual([screen["scale"] for screen in state], [200,125])

    def button(self):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == "restoreLookButton": return item
            pending.extend(item.childItems())
        self.fail("Appearance repair button missing")

    def test_success_stays_visible_and_double_click_does_not_repeat(self):
        QMetaObject.invokeMethod(self.window, "restoreLook")
        self.assertTrue(self.window.property("restoring"))
        self.assertEqual(self.button().property("text"), "Putting it back…")
        QMetaObject.invokeMethod(self.window, "restoreLook")
        self.assertEqual(self.helper.resets, 1)
        QTest.qWait(4300)
        self.assertTrue(self.window.property("restored"))
        self.assertEqual(self.button().property("text"), "Put back again")

    def test_failure_and_malformed_success_remain_retryable(self):
        for reply in (('{"done":false}', 1), ('{}', 0), ('{"done":true}', 1)):
            self.helper.reply = reply
            QMetaObject.invokeMethod(self.window, "restoreLook"); QTest.qWait(100)
            self.assertFalse(self.window.property("restored"))
            self.assertTrue(self.window.property("restoreFailed"))
            self.assertEqual(self.button().property("text"), "Try again")
        self.helper.reply = ('{"done":true}', 0)
        QMetaObject.invokeMethod(self.window, "restoreLook"); QTest.qWait(100)
        self.assertTrue(self.window.property("restored"))
        self.assertFalse(self.window.property("restoreFailed"))

    def test_polling_is_scoped_coalesced_and_stops_when_minimized(self):
        self.window.setProperty("page", "about"); QTest.qWait(20)
        self.helper.commands.clear()
        QMetaObject.invokeMethod(self.window, "refresh")
        self.assertEqual(self.helper.commands, [])
        self.helper.hold_status = True
        self.window.setProperty("page", "sound"); QTest.qWait(20)
        for _ in range(8): QMetaObject.invokeMethod(self.window, "refresh")
        self.window.setProperty("page", "power"); QTest.qWait(20)
        status = [cmd for cmd in self.helper.commands if cmd[1] == "status"]
        self.assertEqual(status, [["helper", "status", "sound"]])
        self.helper.hold_status = False
        self.helper.done.emit(self.helper.pending_status.pop(), '{"volume":42}', 0, "")
        QTest.qWait(20)
        status = [cmd for cmd in self.helper.commands if cmd[1] == "status"]
        self.assertEqual(status[-1], ["helper", "status", "power"])
        self.window.setVisibility(QWindow.Minimized); QTest.qWait(20)
        self.helper.commands.clear()
        QMetaObject.invokeMethod(self.window, "refresh")
        self.assertEqual(self.helper.commands, [])
        self.window.showNormal(); QTest.qWait(20)
        self.assertIn(["helper", "status", "power"], self.helper.commands)

    def test_storage_capacity_loads_without_starting_a_folder_scan(self):
        self.helper.commands.clear()
        self.window.setProperty("page", "storage"); QTest.qWait(30)
        self.assertIn(["helper", "storage-capacity"], self.helper.commands)
        self.assertNotIn(["helper", "storage"], self.helper.commands)
        QMetaObject.invokeMethod(self.window, "measureStorage")
        QMetaObject.invokeMethod(self.window, "measureStorage")
        self.assertEqual(self.helper.commands.count(["helper", "storage"]), 1)
        QTest.qWait(20)
        self.assertFalse(self.window.property("storageBusy"))
        self.assertTrue(self.window.property("storageProblem"))  # malformed worker response is retryable
