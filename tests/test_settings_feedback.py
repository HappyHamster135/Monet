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
            self.hold_history = False; self.pending_history = []
            self.replies = {}; self.held_commands = set(); self.pending_commands = []

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket = self.ticket
            self.commands.append(list(command))
            if command[1] in self.held_commands:
                self.pending_commands.append(ticket)
                return ticket
            if command[1] == "update-history" and self.hold_history:
                self.pending_history.append(ticket)
                return ticket
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
                out = self.replies.get(command[1], "{}")
                QTimer.singleShot(1, lambda: self.done.emit(ticket, out, 0, ""))
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
        self.activity = self.games.WindowActivity()
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "windowActivity": self.activity, "firstPage": "light", "blurBehind": False,
                            "pictures": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings") + "/").toString(),
                            "brush": QUrl.fromLocalFile(str(ROOT / "linux/share/monet/textures/brush.png")).toString()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]
        self.activity.watch(self.window); QTest.qWait(100)

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

    def test_wallet_policy_waits_for_confirmation_and_does_not_poll(self):
        state = dict(enabled=True, policy="session", unlocked=True, manager=True, automaticLogin=True)
        self.helper.replies['wallet-status'] = json.dumps(state)
        self.window.setProperty('page', 'privacy'); QTest.qWait(40)
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'privacy#passwords'))
        QTest.qWait(200)
        self.assertEqual(self.window.property('pendingAnchor'), '')
        self.assertEqual(self.window.property('walletInfo').toVariant()['policy'], 'session')
        self.helper.held_commands.add('wallet-policy')
        QMetaObject.invokeMethod(self.window, 'walletAction', Q_ARG('QVariant', 'policy'), Q_ARG('QVariant', '10'))
        QMetaObject.invokeMethod(self.window, 'walletAction', Q_ARG('QVariant', 'policy'), Q_ARG('QVariant', '30'))
        self.assertTrue(self.window.property('walletBusy'))
        self.assertEqual(self.window.property('walletInfo').toVariant()['policy'], 'session')
        self.assertEqual(sum(c[1] == 'wallet-policy' for c in self.helper.commands), 1)
        ticket = self.helper.pending_commands.pop()
        self.helper.done.emit(ticket, '{"ok":false}', 0, ''); QTest.qWait(10)
        self.assertFalse(self.window.property('walletBusy'))
        self.assertTrue(self.window.property('walletProblem'))
        self.assertFalse(self.window.property('walletChanged'))
        self.helper.held_commands.clear()
        self.helper.replies['wallet-policy'] = json.dumps(dict(ok=True, state=dict(state, policy='10')))
        QMetaObject.invokeMethod(self.window, 'walletAction', Q_ARG('QVariant', 'policy'), Q_ARG('QVariant', '10'))
        QTest.qWait(40)
        self.assertEqual(self.window.property('walletInfo').toVariant()['policy'], '10')
        self.assertTrue(self.window.property('walletChanged'))
        self.helper.commands.clear(); QTest.qWait(2200)
        self.assertFalse(any(c[1].startswith('wallet-') for c in self.helper.commands))

    def test_update_history_loads_on_demand_coalesces_and_recovers(self):
        self.helper.hold_history = True
        self.window.setProperty("page", "updates"); QTest.qWait(30)
        for _ in range(6):
            QMetaObject.invokeMethod(self.window, "loadUpdateHistory")
            QMetaObject.invokeMethod(self.window, "refresh")
        self.assertEqual(self.helper.commands.count(["helper", "update-history"]), 1)
        self.assertNotIn(["helper", "status", "updates"], self.helper.commands)
        self.assertTrue(self.window.property("updateHistoryBusy"))
        ticket = self.helper.pending_history.pop()
        self.helper.done.emit(ticket, '{"ok":true,"items":[{"time":1793352638000,"result":"failed"}],"state":"idle"}', 0, "")
        QTest.qWait(30)
        state = self.window.property("updateHistory").toVariant()
        self.assertEqual(state["items"][0]["result"], "failed")
        self.assertFalse(self.window.property("updateHistoryBusy"))
        QTest.qWait(2100)
        self.assertEqual(self.helper.commands.count(["helper", "update-history"]), 1)
        for response, code, expected in (("{}", 0, False),
                                          ('{"ok":true,"items":[null],"state":"idle"}', 0, False),
                                          ('{"ok":true,"items":[{"time":1,"result":"unknown"}],"state":"idle"}', 0, False),
                                          ('{"ok":true,"items":[{"time":"today","result":"done"}],"state":"idle"}', 0, False),
                                          ('{"ok":true,"items":[],"state":"idle"}', 1, False),
                                          ('{"ok":true,"items":[],"state":"idle"}', 0, True)):
            QMetaObject.invokeMethod(self.window, "loadUpdateHistory")
            self.helper.done.emit(self.helper.pending_history.pop(), response, code, "")
            QTest.qWait(20)
            self.assertEqual(self.window.property("updateHistory").toVariant()["ok"], expected)

    def test_detail_reads_coalesce_until_the_previous_reply_finishes(self):
        self.window.setProperty("page", "about"); QTest.qWait(20)
        for method, command, response in (("loadAppsSound", "apps-sound", "[]"),
                                           ("loadBackup", "backup", "{}"),
                                           ("loadPhotoState", "paint-state", '{"state":"ready"}')):
            with self.subTest(command=command):
                self.helper.commands.clear(); self.helper.held_commands = {command}
                for _ in range(8): QMetaObject.invokeMethod(self.window, method)
                self.assertEqual(self.helper.commands, [["helper", command]])
                self.helper.done.emit(self.helper.pending_commands.pop(), response, 0, "")
                QTest.qWait(10)
                QMetaObject.invokeMethod(self.window, method)
                self.assertEqual(self.helper.commands, [["helper", command]] * 2)
                self.helper.done.emit(self.helper.pending_commands.pop(), response, 0, "")
                self.helper.held_commands.clear(); QTest.qWait(10)

    def test_detail_timers_pause_when_minimized_and_refresh_on_restore(self):
        self.helper.replies.update({"phones": "[]", "apps-sound": "[]",
            "backup": '{"copying":true,"drives":[]}', "paint-state": '{"state":"painting"}',
            "return-status": '{"items":[],"busy":false,"available":false}'})
        for page, command in (("sound", "apps-sound"), ("phone", "phones"),
                               ("windows", "return-status"), ("light", "paint-state"), ("backups", "backup")):
            with self.subTest(page=page):
                self.window.setProperty("page", page); QTest.qWait(100)
                self.assertIn(["helper", command], self.helper.commands)
                self.window.setVisibility(QWindow.Minimized); QTest.qWait(20)
                self.helper.commands.clear()
                QTest.qWait(4200)  # Beyond the longest detail refresh interval.
                self.assertEqual(self.helper.commands, [])
                self.window.showNormal(); QTest.qWait(100)
                self.assertIn(["helper", command], self.helper.commands)
        # A painting can continue in the background without polling its progress
        # from unrelated Settings pages.
        self.window.setProperty("page", "about"); QTest.qWait(50)
        self.helper.commands.clear(); QTest.qWait(1600)
        self.assertEqual(self.helper.commands, [])
