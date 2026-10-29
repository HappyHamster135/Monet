"""Exercise the notification policy with Plasma's real model on an isolated bus."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
ISOLATED = os.environ.get("MONET_NOTIFICATION_TEST_BUS") == "1"
try:
    from PySide6.QtCore import QObject, QUrl, Slot, QEvent, QCoreApplication, QMetaObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT and shutil.which("dbus-run-session") and not ISOLATED, "isolated Linux notification bus")
class NotificationPolicyProcess(unittest.TestCase):
    def test_native_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {**os.environ, "MONET_NOTIFICATION_TEST_BUS": "1", "QT_QPA_PLATFORM": "offscreen",
                   "XDG_CONFIG_HOME": temp + "/config", "XDG_DATA_HOME": temp + "/data", "XDG_CACHE_HOME": temp + "/cache"}
            result = subprocess.run(["dbus-run-session", "--", sys.executable, "-m", "unittest",
                                     "tests.test_notification_policy.NativePolicy", "-v"],
                                    env=env, cwd=ROOT, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if QT:
    class Words(QObject):
        @Slot(str, str, result=str)
        def i18nd(self, domain, text):
            return text


@unittest.skipUnless(QT and ISOLATED, "only run on the isolated test bus")
class NativePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setApplicationName("monet-notification-policy-test")
        cls.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def setUp(self):
        self.engine = QQmlEngine()
        self.words = Words()
        self.engine.rootContext().setContextObject(self.words)
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        source = '''import QtQuick
import org.kde.notificationmanager as Notifications
import "%s" as Monet
QtObject {
    property QtObject preferences: QtObject {
        property var popupBlacklistedApplications: []
        property var popupBlacklistedServices: []
    }
    property Monet.MonetNotificationPolicy policy: Monet.MonetNotificationPolicy { notificationSettings: preferences }
    property var retentionChecks: [
        policy.keepPopup(Notifications.Notifications.NotificationType, Notifications.Notifications.CriticalUrgency, false),
        policy.keepPopup(Notifications.Notifications.NotificationType, Notifications.Notifications.CriticalUrgency, true),
        policy.keepPopup(Notifications.Notifications.NotificationType, Notifications.Notifications.NormalUrgency, false),
        policy.keepPopup(Notifications.Notifications.JobType, Notifications.Notifications.CriticalUrgency, false)
    ]
    property Notifications.Notifications history: Notifications.Notifications {
        objectName: "policyHistory"
        showJobs: false; showExpired: true; showDismissed: true; showAddedDuringInhibition: true
        urgencies: Notifications.Notifications.LowUrgency | Notifications.Notifications.NormalUrgency | Notifications.Notifications.CriticalUrgency
        groupMode: Notifications.Notifications.GroupDisabled
    }
    function clearTestHistory() { history.clear(Notifications.Notifications.ClearExpired) }
}''' % (ROOT / "image/notifications").as_uri()
        self.component = QQmlComponent(self.engine)
        self.component.setData(source.encode(), QUrl("file:///monet-notification-policy-test.qml"))
        self.root = self.component.create()
        self.assertIsNotNone(self.root, [error.toString() for error in self.component.errors()])
        self.history = self.root.findChild(QObject, "policyHistory")
        self.preferences = self.root.property("preferences")
        self.ids = []
        self.pump()

    def tearDown(self):
        for ident in self.ids:
            self.bus("CloseNotification", "u", str(ident))
        self.root.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.pump()
        self.assertEqual(self.warnings, [])

    def pump(self, seconds=0.08):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.app.processEvents()
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(0.002)

    def bus(self, method, signature, *args):
        process = subprocess.Popen(["busctl", "--user", "call", "org.freedesktop.Notifications",
                                    "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
                                    method, signature, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            self.pump(0.01)
        if process.poll() is None:
            process.kill()
        stdout, stderr = process.communicate()
        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.pump()
        return stdout.strip()

    def notify(self, *, urgency=1, service="", action=False, transient=False, replaces=0):
        actions = ["view", "View"] if action else []
        hints = {"desktop-entry": GLib.Variant("s", "org.kde.dolphin"), "urgency": GLib.Variant("y", urgency)}
        if service: hints["x-kde-appname"] = GLib.Variant("s", service)
        if transient: hints["transient"] = GLib.Variant("b", True)
        arguments = GLib.Variant("(susssasa{sv}i)", ("Monet policy test", replaces, "dialog-information",
            "Test message", f"Notification policy fixture {time.monotonic_ns()}", actions, hints, 0))
        result = []
        def completed(connection, reply, unused):
            try: result.append(connection.call_finish(reply).unpack()[0])
            except GLib.Error as error: result.append(error)
        self.connection.call("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications", "Notify", arguments, GLib.VariantType.new("(u)"),
            Gio.DBusCallFlags.NONE, 5000, None, completed, None)
        deadline = time.monotonic() + 6
        while not result and time.monotonic() < deadline: self.pump(0.01)
        self.assertTrue(result)
        self.assertIsInstance(result[0], int, str(result[0]))
        ident = result[0]
        if ident not in self.ids: self.ids.append(ident)
        self.pump()
        return ident

    def rows(self):
        names = {int(role): bytes(name).decode() for role, name in self.history.roleNames().items()}
        return [{name: self.history.data(self.history.index(row, 0), role) for role, name in names.items()}
                for row in range(self.history.rowCount())]

    def row(self, ident):
        return next(row for row in self.rows() if str(row["notificationId"]) == str(ident))

    def test_muted_messages_stay_hidden_after_unmuting_but_new_messages_can_popup(self):
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        ident = self.notify(urgency=2, action=True)
        muted = self.row(ident)
        self.assertTrue(muted["expired"])
        self.assertIn("view", muted["actionNames"])
        self.preferences.setProperty("popupBlacklistedApplications", [])
        self.pump()
        self.assertTrue(self.row(ident)["expired"])
        self.assertFalse(self.row(self.notify())["expired"])

    def test_muting_an_app_hides_existing_popups_without_deleting_them(self):
        ident = self.notify()
        self.assertFalse(self.row(ident)["expired"])
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        self.pump()
        self.assertTrue(self.row(ident)["expired"])

    def test_service_muting_also_preserves_history_without_replaying(self):
        self.preferences.setProperty("popupBlacklistedServices", ["monet-policy-fixture"])
        ident = self.notify(service="monet-policy-fixture")
        self.assertEqual(self.row(ident)["notifyRcName"], "monet-policy-fixture")
        self.assertTrue(self.row(ident)["expired"])
        self.preferences.setProperty("popupBlacklistedServices", [])
        self.pump()
        self.assertTrue(self.row(ident)["expired"])

    def test_muting_multiple_active_messages_retains_every_message_and_action(self):
        identifiers = [self.notify(urgency=2, action=True) for _ in range(5)]
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        self.pump()
        self.assertEqual(len(self.rows()), len(identifiers))
        for ident in identifiers:
            self.assertTrue(self.row(ident)["expired"])
            self.assertIn("view", self.row(ident)["actionNames"])
        self.preferences.setProperty("popupBlacklistedApplications", [])
        self.pump()
        self.assertTrue(all(self.row(ident)["expired"] for ident in identifiers))

    def test_replacing_a_muted_message_updates_history_without_replaying_it(self):
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        ident = self.notify(urgency=2, action=True)
        self.assertTrue(self.row(ident)["expired"])
        previous_body = self.row(ident)["body"]
        self.preferences.setProperty("popupBlacklistedApplications", [])
        self.pump()
        updated = self.notify(urgency=2, action=True, replaces=ident)
        self.assertEqual(updated, ident)
        # Plasma deliberately preserves expired/read state when an app replaces
        # the same notification ID. Replacements update history in place; apps
        # use a new ID for a new popup. Keep that native distinction intact.
        self.assertEqual(len(self.rows()), 1)
        self.assertTrue(self.row(ident)["expired"])
        self.assertNotEqual(self.row(ident)["body"], previous_body)
        self.assertIn("view", self.row(ident)["actionNames"])

    def test_muted_transient_messages_are_not_added_to_history(self):
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        ident = self.notify(transient=True)
        self.assertFalse(any(str(row["notificationId"]) == str(ident) for row in self.rows()))
        self.ids.remove(ident)

    def test_history_filters_and_clear_history_still_work(self):
        self.preferences.setProperty("popupBlacklistedApplications", ["org.kde.dolphin"])
        self.history.setProperty("blacklistedDesktopEntries", ["org.kde.dolphin"])
        ident = self.notify()
        self.assertEqual(self.rows(), [])
        self.history.setProperty("blacklistedDesktopEntries", [])
        self.pump()
        self.assertTrue(self.row(ident)["expired"])
        # Invoke the same native clear operation used by the history's Clear button.
        self.assertTrue(QMetaObject.invokeMethod(self.root, "clearTestHistory"))
        self.pump()
        self.assertEqual(self.rows(), [])
        self.ids.remove(ident)

    def test_only_important_nontransient_notifications_use_dismiss_to_history(self):
        self.assertEqual(self.root.property("retentionChecks").toVariant(), [True, False, False, False])
