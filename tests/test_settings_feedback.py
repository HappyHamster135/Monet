"""The appearance repair reports real failures and keeps its result visible."""
import importlib.machinery
import importlib.util
import gettext
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QEvent, QObject, QMetaObject, QPointF, QTimer, QUrl, Signal, Slot, Q_ARG, Qt
    from PySide6.QtGui import QGuiApplication, QKeyEvent, QWindow
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
        if os.environ.get('MONET_SETTINGS_TEST_LANGUAGE'):
            words = gettext.translation('monet', localedir=str(ROOT / 'linux/share/locale'),
                                        languages=[os.environ['MONET_SETTINGS_TEST_LANGUAGE']])
            language = patch.object(self.games, 'WORDS', words); language.start(); self.addCleanup(language.stop)
        self.engine = QQmlApplicationEngine(); self.words = self.games.Words(); self.helper = FakeHelper()
        self.activity = self.games.WindowActivity()
        self.clock = self.games.BootClock()
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "windowActivity": self.activity, "bootClock": self.clock, "firstPage": "light", "blurBehind": False,
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

    def test_security_shows_unknown_and_pending_checks_in_the_overview(self):
        state = dict(secureBoot="on", encrypted=True, encryptionSetup="complete",
                     firewall="unavailable", selinux="enforcing", autoUpdates="on",
                     updateWaiting=False, network={"known": True, "devices": []})
        self.helper.replies["security"] = json.dumps(state)
        self.helper.replies["firmware-check"] = '{"ok":true,"updates":[]}'
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        overview = self.window.findChild(QObject, "security-overview")
        self.assertIn("couldn’t be completed", overview.property("title"))

        self.helper.replies["security"] = json.dumps(dict(state, firewall="on", encryptionSetup="pending"))
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        self.wait_for(lambda: overview.property("title") == "Finishing disk encryption.")
        action = self.window.findChild(QObject, "security-overview-action")
        action.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: self.window.findChild(QObject, "search-security-device").hasActiveFocus())

    def test_security_waits_for_the_first_result_before_showing_errors(self):
        self.helper.held_commands.add("security")
        self.window.setProperty("page", "security")
        self.wait_for(lambda: bool(self.helper.pending_commands))
        self.assertFalse(self.window.property("securityChecked"))
        self.assertEqual(self.item("security-overview").property("title"), "Checking this PC…")
        titles = {"Secure Boot", "Encryption", "App isolation", "Firewall",
                  "Ports for nearby devices", "Automatic updates", "Recent activity"}
        rows = {row.property("title"): row for row in self.window.findChildren(QObject)
                if row.metaObject().indexOfProperty("detail") >= 0 and row.property("title") in titles}
        self.assertEqual(rows.keys(), titles)
        for row in rows.values():
            self.assertEqual(row.property("detail"), "")

        self.helper.done.emit(self.helper.pending_commands.pop(), "{}", 1, "")
        self.wait_for(lambda: self.window.property("securityChecked"))
        for row in rows.values():
            self.assertIn("couldn’t", row.property("detail").lower())

    def test_security_does_not_turn_a_failed_firewall_action_into_success(self):
        self.helper.replies["security"] = '{"secureBoot":"on","firewall":"off"}'
        self.helper.held_commands.add("firewall-on")
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        action = self.window.findChild(QObject, "security-overview-action")
        action.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: self.window.property("securityFixing") == "firewall-on")
        self.helper.done.emit(self.helper.pending_commands.pop(), "{}", 1, "")
        self.wait_for(lambda: bool(self.window.property("securityProblem"))
                      and not self.window.property("securityChecking"))
        self.assertEqual(self.window.findChild(QObject, "security-overview").property("title"), "The firewall is off.")

    def test_security_ignores_a_firewall_snapshot_started_before_a_change(self):
        network = dict(known=True, complete=True, sharingAsDefault=False, devices=[],
                       sharing={"apps": [], "ports": []},
                       appPorts=dict.fromkeys(("games", "localsend", "syncthing", "sunshine", "deskflow"), []))
        state = dict(secureBoot="on", firewall="on", networkActions=True, network=network)
        self.helper.replies.update(security=json.dumps(state), **{"firewall-sharing": '{"ok":true}'})
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        games = self.item("security-sharing-app-games")
        self.assertFalse(games.property("checked"))

        self.helper.held_commands.add("security")
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        old = self.helper.pending_commands.pop()
        games.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Space)
        self.wait_for(lambda: bool(self.helper.pending_commands))
        new = self.helper.pending_commands.pop()
        self.assertIn(["helper", "firewall-sharing", "games", "on"], self.helper.commands)
        self.assertFalse(games.property("tappable"))

        updated = dict(state, network=dict(network, sharing={"apps": ["games"], "ports": []}))
        self.helper.done.emit(new, json.dumps(updated), 0, "")
        self.wait_for(lambda: games.property("checked") and games.property("tappable"))
        self.helper.done.emit(old, json.dumps(state), 0, "")
        self.assertTrue(games.property("checked"))
        self.assertFalse(self.window.property("securityChecking"))
        self.assertTrue(games.hasActiveFocus())
        for key, text in ((Qt.Key_Space, " "), (Qt.Key_Return, "\r"), (Qt.Key_Enter, "\r")):
            with self.subTest(repeated_key=key):
                repeat = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text, True)
                self.app.sendEvent(self.window, repeat)
                self.assertNotIn(["helper", "firewall-sharing", "games", "off"], self.helper.commands)

    def test_security_network_controls_can_be_tabbed_and_activated(self):
        profile = dict(interface="eth0", uuid="6ac182e3-476f-4074-9600-c591f288c71c", name="Wired",
                       zone="monet", changeable=True)
        network = dict(known=True, complete=True, sharingAsDefault=False, devices=[profile],
                       sharing={"apps": [], "ports": [{"name": "Test", "port": "tcp/8765"}]},
                       appPorts=dict.fromkeys(("games", "localsend", "syncthing", "sunshine", "deskflow"), []))
        state = dict(secureBoot="on", firewall="on", firewallStrict=True, networkActions=True, network=network)
        self.helper.replies["security"] = json.dumps(state)
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        self.item("search-security-network").forceActiveFocus(Qt.TabFocusReason)
        view = self.item("settingsScroller")
        actions = (
            ("security-default-firewall", Qt.Key_Return, ["firewall-strict", "off"]),
            ("security-sharing-profile-eth0", Qt.Key_Enter, ["firewall-network", profile["uuid"], "on"]),
            ("security-sharing-app-games", Qt.Key_Space, ["firewall-sharing", "games", "on"]),
            ("security-sharing-port-tcp/8765", Qt.Key_Return, ["firewall-remove-port", "tcp/8765"]),
        )
        for name, _, _ in actions:
            control = self.item(name)
            for _ in range(8):
                QTest.keyClick(self.window, Qt.Key_Tab)
                if control.hasActiveFocus():
                    break
            self.assertTrue(control.hasActiveFocus(), name)
            self.wait_for(lambda: 0 <= control.mapToItem(view, QPointF()).y() <= view.height() - control.height())

        for name, key, command in actions:
            with self.subTest(control=name):
                self.helper.replies[command[0]] = '{"ok":true}'
                self.item(name).forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(self.window, key)
                self.wait_for(lambda: not self.window.property("securityFixing"))
                self.assertEqual(self.helper.commands.count(["helper", *command]), 1)

    def test_security_firmware_and_legacy_rules_review_focuses_cancel(self):
        self.helper.replies["security"] = json.dumps(dict(
            secureBoot="off", keyTrusted=True, firmwareRestartAvailable=True, firewall="on", networkActions=True,
            network=dict(known=True, devices=[], legacy=True, legacyPorts=[{"port": "7777"}]),
        ))
        self.helper.replies["firewall-clear-legacy"] = '{"ok":false}'
        self.helper.replies["firmware-setup"] = '{"ok":false}'
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))

        for name, command in (("firmware", "firmware-setup"), ("legacy", "firewall-clear-legacy")):
            with self.subTest(action=name):
                review = self.item(f"security-{name}-review")
                review.forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(self.window, Qt.Key_Return)
                cancel = self.item(f"security-{name}-cancel")
                self.assertTrue(cancel.hasActiveFocus())
                repeat = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r", True)
                self.app.sendEvent(self.window, repeat)
                self.assertTrue(cancel.hasActiveFocus())
                self.assertNotIn(["helper", command], self.helper.commands)
                QTest.keyClick(self.window, Qt.Key_Escape)
                self.assertTrue(self.window.isVisible())
                self.assertTrue(review.hasActiveFocus())
                confirm = self.item(f"security-{name}-confirm")
                self.assertFalse(confirm.isVisible())

                QTest.keyClick(self.window, Qt.Key_Space)
                self.assertTrue(cancel.hasActiveFocus())
                QTest.keyClick(self.window, Qt.Key_Enter)
                self.assertTrue(review.hasActiveFocus())
                self.assertNotIn(["helper", command], self.helper.commands)

                QTest.keyClick(self.window, Qt.Key_Enter)
                QTest.keyClick(self.window, Qt.Key_Tab)
                self.assertTrue(confirm.hasActiveFocus())
                QTest.keyClick(self.window, Qt.Key_Return)
                self.wait_for(lambda: bool(self.window.property("securityProblem")))
                self.assertEqual(self.helper.commands.count(["helper", command]), 1)
                self.assertFalse(confirm.isVisible())
                self.wait_for(lambda: not self.window.property("securityChecking"))

    def test_security_hides_firmware_restart_without_the_session_method(self):
        state = dict(secureBoot="off", keyTrusted=True, firmwareRestartAvailable=False)
        self.helper.replies["security"] = json.dumps(state)
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        review = self.item("security-firmware-review")
        self.assertFalse(review.isVisible())
        self.assertIn("at startup", self.item("search-security-device").property("detail"))

        self.helper.replies["security"] = json.dumps(dict(state, firmwareRestartAvailable=True))
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        self.wait_for(review.isVisible)
        review.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(self.item("security-firmware-confirm").isVisible())

        self.helper.replies["security"] = json.dumps(state)
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        self.wait_for(lambda: self.window.property("securityConfirmation") == "")
        self.assertFalse(review.isVisible())
        self.assertNotIn(["helper", "firmware-setup"], self.helper.commands)

    def test_security_key_enrollment_waits_for_a_separate_restart(self):
        self.helper.replies["security"] = '{"secureBoot":"off","keyTrusted":false}'
        self.helper.replies["trust-key"] = '{"ok":true}'
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        action = self.item("security-firmware-review")
        self.assertEqual(action.property("text"), "Trust Monet…")
        action.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.wait_for(lambda: action.property("text") == "Restart")
        self.assertEqual(self.helper.commands.count(["helper", "trust-key"]), 1)
        self.assertNotIn(["helper", "restart"], self.helper.commands)
        action.forceActiveFocus(Qt.TabFocusReason)
        repeat = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier, "\r", True)
        self.app.sendEvent(self.window, repeat)
        self.assertNotIn(["helper", "restart"], self.helper.commands)
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.assertEqual(self.helper.commands.count(["helper", "restart"]), 1)

    def test_security_keeps_restart_available_with_automatic_updates_off(self):
        state = dict(secureBoot="on", encrypted=False, firewall="on", autoUpdates="off", updateWaiting=True)
        self.helper.replies["security"] = json.dumps(state)
        self.helper.replies["restart"] = '{"ok":false}'
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))
        self.assertEqual(self.item("security-overview").property("title"), "Device security needs a look.")
        self.assertIn("An update is ready", self.item("search-security-updates").property("detail"))
        action = self.item("security-update-action")
        self.assertEqual(action.property("text"), "Restart")
        action.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertIn(["helper", "restart"], self.helper.commands)
        self.assertNotIn(["helper", "auto-updates", "on"], self.helper.commands)
        self.wait_for(lambda: "restart confirmation" in self.window.property("securityProblem"))
        self.assertEqual(action.property("text"), "Restart")
        self.helper.replies["restart"] = '{"ok":true}'
        action.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: not self.window.property("securityFixing"))
        self.assertEqual(self.window.property("securityProblem"), "")

        self.helper.replies["security"] = json.dumps(dict(state, updateWaiting=False, lastUpdateFailed=True))
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        self.wait_for(lambda: action.property("text") == "Open Updates")
        self.assertEqual(self.item("search-security-updates").property("detail"), "The last automatic update failed.")
        action.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.window.property("page"), "updates")
        self.wait_for(lambda: self.item("search-update-history").hasActiveFocus())

    def test_security_does_not_mark_an_unknown_check_as_healthy(self):
        network = {"known": True, "complete": True, "devices": [], "sharingAsDefault": False,
                   "sharing": {"apps": [], "ports": []}}
        state = dict(secureBoot="on", encrypted=True, encryptionSetup="complete", firewall="on",
                     selinux="enforcing", autoUpdates="on", updateWaiting=False,
                     network=network)
        available = '{"ok":true,"updates":[]}'
        self.helper.replies.update(security=json.dumps(state), **{"firmware-check": available})
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked") and self.window.property("firmwareState") == "none")
        overview = self.item("security-overview")
        self.assertEqual(overview.property("title"), "The main checks look good.")
        for changes, firmware, firmware_state in (
            ({"secureBoot": "unavailable"}, available, "none"),
            ({"secureBoot": "unknown"}, available, "none"),
            ({"encrypted": None}, available, "none"),
            ({"firewall": "unavailable"}, available, "none"),
            ({"firewall": "unknown"}, available, "none"),
            ({"network": dict(network, complete=False, sharingAsDefault=None)}, available, "none"),
            ({"updateWaiting": None}, available, "none"),
            ({}, '{"ok":false,"unavailable":true}', "unavailable"),
            ({}, '{"ok":false}', "failed"),
        ):
            with self.subTest(changes=changes, firmware=firmware_state):
                self.helper.replies.update(security=json.dumps(dict(state, **changes)), **{"firmware-check": firmware})
                QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
                QMetaObject.invokeMethod(self.window, "checkFirmware")
                self.wait_for(lambda: not self.window.property("securityChecking")
                              and self.window.property("firmwareState") == firmware_state)
                self.assertIn("couldn’t be completed", overview.property("title"))
                if "network" in changes:
                    self.assertIn("couldn’t check all firewall rules",
                                  self.item("search-security-network").property("detail"))
                if "updateWaiting" in changes:
                    mark = self.item("security-update-mark")
                    self.assertFalse(mark.property("known"))
                    self.assertFalse(mark.property("good"))

    def test_security_keeps_removal_controls_available_when_the_default_zone_is_unknown(self):
        network = dict(known=True, complete=False, sharingAsDefault=None,
                       devices=[dict(interface="eth0", zone="monet", changeable=True),
                                dict(interface="eth1", zone="monet-shared", changeable=True)],
                       sharing={"apps": ["localsend"], "ports": []},
                       appPorts=dict.fromkeys(("games", "localsend", "syncthing", "sunshine", "deskflow"), []))
        state = dict(secureBoot="on", firewall="on", networkActions=True, network=network)
        self.helper.replies["security"] = json.dumps(state)
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked"))

        self.assertFalse(self.item("security-sharing-profile-eth0").property("enabledPill"))
        self.assertTrue(self.item("security-sharing-profile-eth1").property("enabledPill"))
        self.assertFalse(self.item("security-sharing-app-games").property("tappable"))
        self.assertTrue(self.item("security-sharing-app-localsend").property("tappable"))

        self.helper.replies["security"] = json.dumps(dict(state, network=dict(network, complete=True, sharingAsDefault=False)))
        QMetaObject.invokeMethod(self.window, "loadSecurity", Q_ARG("QVariant", False))
        self.wait_for(lambda: not self.window.property("securityChecking"))
        self.assertTrue(self.item("security-sharing-profile-eth0").property("enabledPill"))
        self.assertTrue(self.item("security-sharing-app-games").property("tappable"))

    def test_security_keeps_an_in_progress_firmware_update_visible(self):
        state = dict(secureBoot="on", encrypted=True, encryptionSetup="complete", firewall="on",
                     selinux="enforcing", autoUpdates="on", updateWaiting=False,
                     network={"known": True, "complete": True, "devices": [], "sharing": {"apps": [], "ports": []}})
        self.helper.replies.update(security=json.dumps(state), **{
            "firmware-check": '{"ok":true,"updates":[{"device":"Dock","version":"2","restart":true}]}'
        })
        self.helper.held_commands.add("firmware-update")
        self.window.setProperty("page", "security")
        self.wait_for(lambda: self.window.property("securityChecked")
                      and self.window.property("firmwareState") == "available")
        overview = self.item("security-overview")
        QMetaObject.invokeMethod(self.window, "installFirmware")
        self.assertEqual(overview.property("title"), "Updating firmware…")
        checks = self.helper.commands.count(["helper", "firmware-check"])
        QMetaObject.invokeMethod(self.window, "checkFirmware")
        self.assertEqual(self.helper.commands.count(["helper", "firmware-check"]), checks)
        self.helper.done.emit(self.helper.pending_commands.pop(), '{"ok":true}', 0, "")
        self.wait_for(lambda: self.window.property("firmwareState") == "done")
        self.assertTrue(self.window.property("firmwareRestart"))
        self.assertEqual(overview.property("title"), "Updates need a look.")
        QMetaObject.invokeMethod(self.window, "checkFirmware")
        self.assertEqual(self.helper.commands.count(["helper", "firmware-check"]), checks)
        self.assertEqual(self.window.property("firmwareState"), "done")

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

    def test_keep_awake_preserves_policy_coalesces_clicks_and_ignores_old_reads(self):
        self.helper.held_commands |= {'keep-awake-status', 'keep-awake'}
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power'))
        self.wait_for(lambda: bool(self.helper.pending_commands))
        old_read = self.helper.pending_commands[-1]
        for _ in range(2):
            QMetaObject.invokeMethod(self.window, 'changeKeepAwake', Q_ARG('QVariant', 1800))
        self.assertEqual(self.helper.commands.count(['helper', 'keep-awake', '30']), 1)
        pending = self.helper.pending_commands[-1]
        self.helper.done.emit(old_read, '{"active":false,"duration":0}', 0, '')
        self.assertTrue(self.window.property('keepAwakeBusy'))
        state = dict(active=True, duration=1800, end=self.clock.now()+1800, remaining=1800,
                     indefinite=False, pending=False, error='')
        self.helper.done.emit(pending, json.dumps(dict(ok=True, state=state)), 0, '')
        self.wait_for(lambda: not self.window.property('keepAwakeBusy'))
        self.assertGreater(self.window.property('keepAwakeLeft'), 1790)
        self.assertEqual(self.item('keepAwakeDuration').property('current'), 1800)
        self.assertFalse(any(c[1] in ('power-time','lock-after','lock-resume') for c in self.helper.commands))

    def test_keep_awake_backend_recovery_replaces_the_unavailable_message(self):
        state = dict(active=False, duration=1800, end=self.clock.now()+1800, remaining=1800,
                     indefinite=False, pending=True, error='backend-unavailable')
        self.helper.replies['keep-awake'] = json.dumps(dict(ok=False,state=state))
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power'))
        QTest.qWait(60)
        QMetaObject.invokeMethod(self.window, 'changeKeepAwake', Q_ARG('QVariant', 1800))
        self.wait_for(lambda: 'unavailable' in self.item('search-keep-awake').property('detail'))
        state.update(active=True,pending=False,error='')
        self.helper.replies['keep-awake-status'] = json.dumps(state)
        QMetaObject.invokeMethod(self.window, 'loadKeepAwake')
        self.wait_for(lambda: 'remaining' in self.item('search-keep-awake').property('detail'))
        self.assertEqual(self.item('keepAwakeDuration').property('current'),1800)

    def test_keep_awake_countdown_resyncs_and_hidden_views_do_no_reads(self):
        state = dict(active=True, duration=1800, end=self.clock.now()+65, remaining=65,
                     indefinite=False, pending=False, error='')
        self.helper.replies['keep-awake-status'] = json.dumps(state)
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power#keep-awake'))
        self.wait_for(lambda: 'remaining' in self.item('search-keep-awake').property('detail'))
        before = self.window.property('keepAwakeLeft')
        self.assertTrue(self.window.property('pollingActive'))
        # Native timer delivery and ceiling the remaining seconds need not
        # coincide with one fixed test sleep, especially in the full suite.
        self.wait_for(lambda: self.window.property('keepAwakeLeft') < before)
        self.window.setVisibility(QWindow.Minimized); QTest.qWait(40)
        self.helper.commands.clear()
        QMetaObject.invokeMethod(self.window, 'loadKeepAwake')
        self.assertNotIn(['helper','keep-awake-status'], self.helper.commands)
        self.window.showNormal()
        self.wait_for(lambda: ['helper','keep-awake-status'] in self.helper.commands)

    def test_keep_awake_keyboard_choices_keep_focus_and_fit_the_window(self):
        from PySide6.QtCore import QPointF
        self.window.resize(760, 520)
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power#keep-awake'))
        self.wait_for(lambda: self.window.property('pendingAnchor') == '')
        segments = self.item('keepAwakeDuration')
        choices = {}
        for item in segments.childItems()[0].childItems():
            value = item.property('modelData')
            if hasattr(value, 'toVariant'): value = value.toVariant()
            if isinstance(value, list) and len(value) == 2:
                choices[value[0]] = item
        self.assertEqual(set(choices), {0, 1800, 3600, -1})
        for duration, key, mode in ((1800, Qt.Key_Return, '30'), (3600, Qt.Key_Enter, '60'),
                                    (-1, Qt.Key_Space, 'on'), (0, Qt.Key_Return, 'off')):
            state = dict(active=duration != 0, duration=duration, end=self.clock.now()+duration if duration > 0 else 0,
                         remaining=max(0,duration), indefinite=duration == -1, pending=False, error='')
            self.helper.replies['keep-awake'] = json.dumps(dict(ok=True, state=state))
            choice = choices[duration]; choice.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(self.window, key)
            self.wait_for(lambda: not self.window.property('keepAwakeBusy'))
            self.assertEqual(self.helper.commands.count(['helper', 'keep-awake', mode]), 1)
            self.assertTrue(choice.hasActiveFocus())
            self.assertEqual(segments.property('current'), duration)
        left = segments.mapToItem(self.window.contentItem(), QPointF()).x()
        self.assertGreaterEqual(left, 0)
        self.assertLessEqual(left + segments.width(), self.window.width())
        if os.environ.get('MONET_SCALE_CAPTURE'):
            output = Path(os.environ['MONET_SCALE_CAPTURE']); output.mkdir(parents=True, exist_ok=True)
            self.assertTrue(self.window.grabWindow().save(str(output / 'keep-awake.png')))

    def test_open_loads_each_page_snapshot_once(self):
        self.helper.commands.clear()
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power'))
        QTest.qWait(80)
        self.assertEqual(self.helper.commands.count(['helper', 'power']), 1)
        self.assertEqual(self.helper.commands.count(['helper', 'battery-care']), 1)

    def test_power_and_download_search_targets_are_focused_and_highlighted(self):
        self.helper.replies['battery-care'] = '{"supported":true,"limit":80}'
        self.helper.replies['status'] = '{"battery":100,"charging":false,"plugged":true}'
        self.window.resize(760, 520)
        if os.environ.get('QT_SCALE_FACTOR'):
            self.assertAlmostEqual(self.window.devicePixelRatio(), float(os.environ['QT_SCALE_FACTOR']), places=2)
        for route, target in [('power#lock', 'search-lock'), ('storage#downloads', 'search-downloads'),
                              ('power#battery-limit', 'search-battery-limit')]:
            with self.subTest(route=route):
                QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', route))
                self.wait_for(lambda: self.window.property('pendingAnchor') == '')
                item = self.item(target)
                self.assertTrue(item.property('activeFocus'))
                self.assertEqual(self.window.property('highlightedItem'), item)
                self.assertTrue(self.item('searchHighlightOutline').isVisible())
                scroller = self.item('settingsScroller')
                from PySide6.QtCore import QPointF
                top = item.mapToItem(scroller, QPointF()).y()
                self.assertGreaterEqual(top, -2)
                self.assertLess(top, scroller.height())
                if os.environ.get('MONET_SCALE_CAPTURE'):
                    QTest.qWait(350)
                    output = Path(os.environ['MONET_SCALE_CAPTURE']); output.mkdir(parents=True, exist_ok=True)
                    self.assertTrue(self.window.grabWindow().save(str(output / (target + '.png'))))
        self.assertFalse(any(c[1] in ('lock-after', 'battery-limit') for c in self.helper.commands))

    def test_battery_limit_search_explains_unsupported_hardware(self):
        self.helper.replies['battery-care'] = '{"supported":false,"limit":100}'
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power#battery-limit'))
        self.wait_for(lambda: self.window.property('pendingAnchor') == '')
        item = self.item('search-battery-limit')
        self.wait_for(lambda: 'support' in item.property('detail'))
        self.assertFalse(item.property('tappable'))
        self.assertTrue(item.isVisible())
        self.assertTrue(item.property('activeFocus'))

    def test_battery_limit_search_survives_slow_hardware_reply(self):
        self.helper.held_commands.add('battery-care')
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power#battery-limit'))
        self.wait_for(lambda: self.window.property('pendingAnchor') == '')
        item = self.item('search-battery-limit')
        self.assertIn('Checking', item.property('detail'))
        QTest.qWait(1200)
        self.helper.done.emit(self.helper.pending_commands[-1], '{"supported":true,"limit":80}', 0, '')
        self.wait_for(lambda: item.property('tappable'))
        self.assertTrue(item.property('activeFocus'))
        self.assertIn('Stops charging', item.property('detail'))
        self.assertEqual(self.helper.commands.count(['helper', 'battery-care']), 1)

    def test_battery_description_distinguishes_paused_full_and_unplugged(self):
        self.helper.replies['battery-care'] = '{"supported":true,"limit":80}'
        for state, expected in [({'battery':100,'charging':False,'plugged':True}, '80% limit'),
                                ({'battery':70,'charging':False,'plugged':True}, 'not charging'),
                                ({'battery':100,'charging':False,'plugged':False}, 'On battery'),
                                ({'battery':70,'charging':True,'plugged':True}, 'Charging')]:
            self.helper.replies['status'] = json.dumps(state)
            QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power'))
            self.wait_for(lambda: expected in self.item('batteryStatusRow').property('detail'))
        self.helper.replies['battery-care'] = '{"supported":true,"limit":100}'
        self.helper.replies['status'] = '{"battery":100,"charging":false,"plugged":true}'
        QMetaObject.invokeMethod(self.window, 'open', Q_ARG('QVariant', 'power'))
        self.wait_for(lambda: 'fully charged' in self.item('batteryStatusRow').property('detail'))

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
        self.wait_for(lambda: not self.window.property("storageBusy"))
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
