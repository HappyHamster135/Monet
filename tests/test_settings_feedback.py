"""The appearance repair reports real failures and keeps its result visible."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl, Signal, Slot, Q_ARG, Qt
    from PySide6.QtGui import QGuiApplication, QWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


class LookRepair(unittest.TestCase):
    def test_profile_transport_rejects_invalid_requests_and_failed_responses(self):
        import subprocess
        q = quick_helper()
        with patch.object(q.subprocess, 'run') as run:
            self.assertFalse(q.profile_recovery(['../../file', 'x'])['ok'])
            run.assert_not_called()
        for response, code in (('{}', 0), ('{"ok":true}', 1), ('bad', 0)):
            with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, response, '')):
                self.assertFalse(q.profile_recovery([])['ok'])
        with patch.object(q.subprocess, 'run', side_effect=subprocess.TimeoutExpired('profile', 120)):
            self.assertEqual(q.profile_recovery([])['state'], 'unavailable')

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

    def wait_for(self, condition):
        """Wait for a reply, without assuming a loaded renderer meets a short sleep."""
        deadline = time.monotonic() + 2
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), 'The asynchronous reply did not arrive')

    def test_retained_install_review_consent_busy_and_failed_cleanup(self):
        item = dict(id='previous-install-'+'a'*16, token='b'*64, time=1793782800000, homes=1, bytes=None)
        self.window.setProperty('page', 'storage'); QTest.qWait(80)
        self.assertFalse(any(c[1] == 'storage-recovery' for c in self.helper.commands))
        self.helper.replies['storage-recovery'] = json.dumps(dict(ok=True, items=[item]))
        QMetaObject.invokeMethod(self.item('scanRetained'), 'clicked'); QTest.qWait(60)
        self.helper.replies['storage-recovery'] = json.dumps(dict(ok=True, item=item))
        QMetaObject.invokeMethod(self.item('reviewRetained-'+item['id']), 'clicked'); QTest.qWait(80)
        self.assertFalse(self.item('deleteRetained').property('enabledPill'))
        # The function itself also checks consent; invoking a signal cannot bypass it.
        QMetaObject.invokeMethod(self.item('deleteRetained'), 'clicked'); QTest.qWait(20)
        self.assertFalse(any(c[1:3] == ['storage-recovery', 'delete'] for c in self.helper.commands))
        self.window.setProperty('retainedConsent', True)
        self.helper.held_commands.add('storage-recovery')
        QMetaObject.invokeMethod(self.item('deleteRetained'), 'clicked')
        QMetaObject.invokeMethod(self.item('deleteRetained'), 'clicked')
        self.assertEqual(sum(c[1:3] == ['storage-recovery', 'delete'] for c in self.helper.commands), 1)
        self.assertTrue(self.window.property('retainedBusy'))
        self.helper.done.emit(self.helper.pending_commands[-1], '{"ok":false,"state":"changed"}', 1, '')
        QTest.qWait(40)
        self.assertFalse(self.window.property('retainedBusy'))
        self.assertIsNone(self.window.property('retainedReview'))
        self.assertIn('changed or is in use', self.window.property('retainedMessage'))

    def test_recovery_diagnostics_are_explicit_coalesced_and_previewed(self):
        self.window.setProperty('page', 'recovery'); QTest.qWait(80)
        self.assertFalse(any(c[1] == 'troubleshooting' for c in self.helper.commands))
        self.helper.held_commands.add('troubleshooting')
        for _ in range(3): QMetaObject.invokeMethod(self.item('checkRecoveryHealth'), 'clicked')
        self.assertEqual(sum(c[1] == 'troubleshooting' for c in self.helper.commands), 1)
        data = dict(ok=True, low=True, rollback=True, services=[], report='Monet recovery check\nLow disk space: yes')
        self.helper.done.emit(self.helper.pending_commands[-1], json.dumps(data), 0, '')
        QTest.qWait(60)
        self.assertEqual(self.item('recoveryReport').property('text'), data['report'])
        self.assertFalse(self.window.property('healthBusy'))
        self.assertFalse(any(c[1] in ('rollback', 'restart', 'update') for c in self.helper.commands))

    def test_earlier_copy_keeps_selection_coalesces_clicks_and_reports_failure(self):
        item = dict(name='2026-11-04 09.00', time=1793782800000, size=12, folder=False)
        self.window.setProperty('earlier', dict(file='/home/test/letter.txt', name='letter.txt', versions=[item]))
        self.helper.held_commands.add('put-back')
        for _ in range(2):
            self.assertTrue(QMetaObject.invokeMethod(self.window, 'useEarlier',
                            Q_ARG('QVariant', 'put-back'), Q_ARG('QVariant', item)))
        actions = [c for c in self.helper.commands if c[1] == 'put-back']
        self.assertEqual(actions, [['helper', 'put-back', '/home/test/letter.txt'.encode().hex(), item['name'].encode().hex()]])
        self.assertTrue(self.window.property('earlierBusy'))
        self.helper.done.emit(self.helper.pending_commands[-1], '{"ok":false,"state":"failed"}', 0, '')
        QTest.qWait(30)
        self.assertFalse(self.window.property('earlierBusy'))
        self.assertIn('free space', self.window.property('earlierMessage'))
        self.helper.held_commands.clear()
        self.helper.replies['put-back'] = '{"ok":true,"state":"restored"}'
        QMetaObject.invokeMethod(self.window, 'useEarlier', Q_ARG('QVariant', 'put-back'), Q_ARG('QVariant', item))
        self.wait_for(lambda: not self.window.property('earlierBusy'))
        self.assertIn('beside your file', self.window.property('earlierMessage'))

    def profile_fixture(self):
        item = dict(id='1'*32, fingerprint='a'*64, time=1793782800000, status='done',
                    settings=4, shortcuts=1, remaining=5, areas=['appearance', 'shortcuts'])
        self.helper.replies['profile-recovery'] = json.dumps(dict(ok=True, state='ready', items=[item]))
        self.window.setProperty('page', 'recovery'); QTest.qWait(80)
        return item

    def test_profile_undo_requires_review_and_protects_against_double_submission(self):
        item = self.profile_fixture()
        QMetaObject.invokeMethod(self.window, 'undoProfile')
        self.assertFalse(any(len(c) > 2 and c[1] == 'profile-recovery' for c in self.helper.commands))
        review = self.item('reviewProfile-'+item['id'])
        self.assertIsNotNone(review); QMetaObject.invokeMethod(review, 'clicked'); QTest.qWait(20)
        self.assertIsNotNone(self.window.property('profileReview'))
        cancel = self.item('cancelProfileUndo-'+item['id'])
        QMetaObject.invokeMethod(cancel, 'clicked'); QTest.qWait(10)
        self.assertIsNone(self.window.property('profileReview'))
        QMetaObject.invokeMethod(review, 'clicked')
        self.helper.held_commands.add('profile-recovery')
        confirm = self.item('confirmProfileUndo-'+item['id'])
        QMetaObject.invokeMethod(confirm, 'clicked'); QMetaObject.invokeMethod(confirm, 'clicked')
        actions = [c for c in self.helper.commands if c[1] == 'profile-recovery' and len(c) == 4]
        self.assertEqual(actions, [['helper', 'profile-recovery', item['id'], item['fingerprint']]])
        self.assertTrue(self.window.property('profileRestoring'))
        self.helper.held_commands.clear()
        self.helper.done.emit(self.helper.pending_commands[-1], '{"ok":false,"state":"conflicts","restored":4,"kept":1}', 0, '')
        QTest.qWait(80)
        self.assertFalse(self.window.property('profileRestoring'))
        self.assertIn('Newer choices', self.window.property('profileMessage'))
        self.assertFalse(any(c[1] in ('restart', 'rollback', 'look-reset') for c in self.helper.commands))

    def test_profile_history_failure_is_distinct_from_empty_and_does_not_poll(self):
        self.helper.replies['profile-recovery'] = '{"ok":false,"state":"unavailable"}'
        self.window.setProperty('page', 'recovery'); QTest.qWait(80)
        self.assertEqual(self.window.property('profileState'), 'unavailable')
        status = self.window.findChild(QObject, 'profileHistoryStatus')
        self.assertIn('could not be read', status.property('text'))
        self.helper.commands.clear()
        for _ in range(4): QMetaObject.invokeMethod(self.window, 'refresh')
        self.assertEqual(self.helper.commands, [])
        self.helper.replies['profile-recovery'] = '{"ok":true,"state":"ready","items":[]}'
        QMetaObject.invokeMethod(self.window, 'loadProfileHistory'); QTest.qWait(80)
        self.assertEqual(status.property('text'), 'No saved desktop changes yet.')

    def test_profile_keyboard_review_starts_on_cancel_and_reports_verified_success(self):
        item = self.profile_fixture()
        self.window.setWidth(760); self.window.setHeight(520)
        review = self.item('reviewProfile-'+item['id'])
        review.forceActiveFocus(); QTest.qWait(30)
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(30)
        cancel = self.item('cancelProfileUndo-'+item['id'])
        self.assertTrue(cancel.hasActiveFocus())
        # Reflow the open review without changing focus: the confirmation must
        # remain reachable after the explanatory text grows onto more lines.
        self.window.setWidth(1000); QTest.qWait(80)
        self.window.setWidth(760); QTest.qWait(120)
        point = cancel.mapToScene(cancel.boundingRect().bottomRight())
        self.assertGreater(point.y(), 0); self.assertLess(point.y(), self.window.height())
        selected = self.item('settingsPage-recovery')
        nav_point = selected.mapToScene(selected.boundingRect().center())
        self.assertGreater(nav_point.y(), 155)
        self.assertLess(nav_point.y(), self.window.height()-35)
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(30)
        self.assertIsNone(self.window.property('profileReview'))
        self.assertTrue(review.hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(30)
        QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
        self.assertTrue(self.item('confirmProfileUndo-'+item['id']).hasActiveFocus())
        self.helper.held_commands.add('profile-recovery')
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(10)
        self.assertTrue(self.window.property('profileRestoring'))
        self.helper.held_commands.clear()
        item.update(status='rolled-back', remaining=0)
        self.helper.replies['profile-recovery'] = json.dumps(dict(ok=True, state='ready', items=[item]))
        self.helper.done.emit(self.helper.pending_commands[-1], '{"ok":true,"state":"done","restored":5,"kept":0}', 0, '')
        QTest.qWait(80)
        self.assertIn('Desktop changes undone', self.window.property('profileMessage'))
        self.assertFalse(self.item('reviewProfile-'+item['id']).isVisible())
        self.assertFalse(any(c[1] in ('restart', 'rollback', 'look-reset') for c in self.helper.commands))

    def test_profile_false_success_keeps_a_retryable_result(self):
        for response, code in (('{"ok":true,"state":"done"}', 1), ('{}', 0), ('not json', 0)):
            item = self.profile_fixture()
            QMetaObject.invokeMethod(self.item('reviewProfile-'+item['id']), 'clicked')
            self.helper.held_commands.add('profile-recovery')
            QMetaObject.invokeMethod(self.window, 'undoProfile')
            self.helper.held_commands.clear()
            self.helper.done.emit(self.helper.pending_commands[-1], response, code, '')
            QTest.qWait(80)
            self.assertIn('could not finish', self.window.property('profileMessage'))

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

    def item(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name: return item
            pending.extend(item.childItems())
        self.fail("Missing visible control: " + name)

    def button(self):
        return self.item("restoreLookButton")

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
            QMetaObject.invokeMethod(self.window, "restoreLook")
            self.wait_for(lambda: not self.window.property("restoring"))
            self.assertFalse(self.window.property("restored"))
            self.assertTrue(self.window.property("restoreFailed"))
            self.assertEqual(self.button().property("text"), "Try again")
        self.helper.reply = ('{"done":true}', 0)
        QMetaObject.invokeMethod(self.window, "restoreLook")
        self.wait_for(lambda: not self.window.property("restoring"))
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
        self.assertEqual(self.window.property('page'), 'passwords')
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

    def test_app_login_switch_waits_for_service_result(self):
        state = dict(enabled=True, appOffers=False, appOffersAvailable=True, appOffersRunning=False)
        self.helper.replies['wallet-status'] = json.dumps(state)
        self.window.setProperty('page', 'passwords'); QTest.qWait(120)
        row = self.item('appLoginOffersRow')
        self.assertTrue(row.property('tappable'))
        self.helper.held_commands.add('wallet-app-offers')
        QMetaObject.invokeMethod(row, 'tapped')
        self.assertTrue(self.window.property('walletBusy'))
        self.assertFalse(self.window.property('walletInfo').toVariant()['appOffers'])
        self.assertEqual(self.helper.commands[-1][1:], ['wallet-app-offers', 'on'])
        ticket = self.helper.pending_commands.pop()
        self.helper.done.emit(ticket, json.dumps(dict(ok=False, state=state)), 0, '')
        QTest.qWait(20)
        self.assertFalse(self.window.property('walletInfo').toVariant()['appOffers'])
        self.assertTrue(self.window.property('walletProblem'))
        self.helper.held_commands.clear()
        self.helper.replies['wallet-app-offers'] = json.dumps(dict(ok=True, state=dict(state, appOffers=True, appOffersRunning=True)))
        QMetaObject.invokeMethod(row, 'tapped'); QTest.qWait(40)
        self.assertTrue(self.window.property('walletInfo').toVariant()['appOffers'])
        self.assertFalse(self.window.property('walletChanged'))  # unrelated unlock policy

    def test_passwords_page_opens_native_managers_without_reading_entries(self):
        state = dict(enabled=True, policy='session', unlocked=False, manager=True, preferences=True, browser=True)
        self.helper.replies['wallet-status'] = json.dumps(state)
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'passwords'))
        self.wait_for(lambda: self.window.property('walletInfo').toVariant().get('manager') is True
                      and not self.window.property('walletBusy'))
        pending = [self.window.contentItem()]; buttons = {}
        while pending:
            item = pending.pop()
            if item.objectName().startswith('wallet') and item.objectName().endswith('Button'):
                buttons[item.objectName()] = item
            pending.extend(item.childItems())
        for name, action in (('walletManageButton','manage'), ('walletAccessButton','access'), ('walletBrowserButton','browser'), ('walletZenButton','zen')):
            self.assertTrue(buttons[name].property('enabled'), name)
            self.helper.replies['wallet-' + action] = '{"ok":true}'
            self.assertTrue(QMetaObject.invokeMethod(buttons[name], 'clicked'))
            self.wait_for(lambda: not self.window.property('walletBusy'))
            self.assertEqual(self.helper.commands[-1][1], 'wallet-' + action)
        support = self.item('appLoginSupportButton')
        self.helper.replies['wallet-app-support'] = '{"ok":true}'
        self.assertTrue(QMetaObject.invokeMethod(support, 'clicked'))
        self.wait_for(lambda: not self.window.property('walletBusy'))
        self.assertEqual(self.helper.commands[-1][1], 'wallet-app-support')
        self.assertFalse(any(any(word in str(command) for word in ('readPassword', 'readEntry', 'folderList')) for command in self.helper.commands))

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
