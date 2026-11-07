"""Actual Transfers representation, with inert job and folder-operation endpoints."""
import gettext
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_settings_navigation as settings
from tests import test_store_scrolling as scrolling

QT = settings.QT
if QT:
    from PySide6.QtCore import QEvent, QMetaObject, QObject, QPointF, QRectF, QUrl, Qt
    from PySide6.QtGui import QGuiApplication, QKeyEvent
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QSignalSpy, QTest


@unittest.skipUnless(QT, "requires Qt and Plasma")
class TransfersNavigation(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    item = settings.SettingsNavigation.item
    capture = settings.SettingsNavigation.capture
    assert_visible_in = settings.SettingsNavigation.assert_visible_in
    wheel = scrolling.StoreScrolling.wheel
    bounds = staticmethod(scrolling.StoreScrolling.bounds)

    def setUp(self):
        language = os.environ.get("MONET_SETTINGS_TEST_LANGUAGE", "en")
        words = gettext.translation("monet", localedir=str(settings.ROOT / "linux/share/locale"),
                                    languages=[language], fallback=language == "en")
        change = patch.object(self.games, "WORDS", words); change.start(); self.addCleanup(change.stop)
        self.words = self.games.Words()
        directory = settings.ROOT / "linux/share/plasma/plasmoids/org.monet.transfers/contents/ui"
        source = (directory / "main.qml").read_text()
        imports = source[:source.index("PlasmoidItem {")]
        representation = source.split("    fullRepresentation: ", 1)[1].rsplit("\n}", 1)[0]
        representation = representation.replace("Rectangle {", "Rectangle {\n        anchors.fill: parent", 1)
        qml = imports + '''
import QtQuick.Window
Window {
    id: window; width: 500; height: 480; visible: true
    Item {
        id: root; objectName: "transfersTestRoot"; anchors.fill: parent
        property var localJobs: []
        property string problem: ""
        property bool expanded: true
        property rect usableScreen: Qt.rect(0, 0, Screen.width, Screen.height)
        property var actions: []
        function i18n(text) { return fixtureWords.i18n(text) }
        function label(state) { return state }
        function refresh() { actions = actions.concat(["refresh"]) }
        function control(action, job) { actions = actions.concat([action + ":" + job.token]) }
        function representedExtraction(job) { return false }
        // Keep private style items inside QML. Some KDE style C++ items have
        // no public PySide wrapper; only controls cross the test boundary.
        function fixtureNodes(item, buttons) {
            let result = [];
            if (buttons && item instanceof T.AbstractButton && item.visible && item.enabled) result.push(item);
            if (!buttons && item instanceof T.Label && item.visible)
                result.push({text: item.text, width: item.width, paintedWidth: item.paintedWidth});
            for (const child of item.children || []) result = result.concat(fixtureNodes(child, buttons));
            return result;
        }
        function fixtureButtons() { return fixtureNodes(root, true) }
        function fixtureLabels() { return fixtureNodes(root, false) }
        function fixtureMotion(item) {
            let result = [];
            if (item instanceof T.ProgressBar) result.push({kind: "progress", active: item.indeterminate});
            if (item instanceof T.BusyIndicator) result.push({kind: "busy", active: item.running});
            for (const child of item.children || []) result = result.concat(fixtureMotion(child));
            return result;
        }
        function fixtureAnimations() { return fixtureMotion(root) }
        QtObject { id: activity; objectName: "transfersTestActivity"; property bool active: true }
        QtObject {
            id: folderOpen; objectName: "transfersTestFolder"
            property bool busy: false
            property bool cancellable: true
            property string error: ""
            function plainText(value) { return String(value) }
            function cancel() { root.actions = root.actions.concat(["cancel-opening"]); busy = false }
            function dismissError() { error = "" }
            function open(url, exact, item) { root.actions = root.actions.concat(["open:" + String(url)]) }
        }
        QtObject {
            id: nativeJob
            property string summary: "Copying a file with a long name into the selected destination folder"
            property string text: "A controlled native copy"
            property int state: NotificationManager.Notifications.JobStateRunning
            property int percentage: 25
            property int error: 0
            property bool suspendable: true
            property bool killable: true
            property url effectiveDestUrl: "file:///tmp/controlled-copy"
            property url destUrl: effectiveDestUrl
            function suspend() { root.actions = root.actions.concat(["native-pause"]) }
            function resume() { root.actions = root.actions.concat(["native-resume"]) }
            function kill() { root.actions = root.actions.concat(["native-cancel"]) }
        }
        ListModel { id: nativeJobs; Component.onCompleted: append({jobDetails: nativeJob}) }
        REPRESENTATION
    }
}
'''.replace("REPRESENTATION", representation)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        qml = 'import "' + (settings.ROOT / "linux/share/monet/widgets").as_uri() + '"\n' + qml
        entry = Path(self.temp.name) / "transfers.qml"; entry.write_text(qml)
        self.engine = QQmlApplicationEngine(); self.errors = []
        self.engine.warnings.connect(lambda errors: self.errors.extend(error.toString() for error in errors))
        self.engine.rootContext().setContextObject(self.words)
        self.engine.rootContext().setContextProperty("fixtureWords", self.words)
        self.engine.addImportPath(str(directory)); self.engine.addImportPath(str(settings.ROOT / "linux/share/monet/widgets"))
        self.engine.load(QUrl.fromLocalFile(str(entry)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]; self.root = self.item("transfersTestRoot")
        self.page = self.root.childItems()[0]
        self.folder = self.root.findChild(QObject, "transfersTestFolder")
        jobs = [dict(owner="files", token=f"{index + 1:032x}", name="Archive with a long name " + str(index),
                     kind="extract", state=("running", "paused", "failed", "done")[index % 4], progress=.25,
                     error="Retry is available; existing partial files were retained." if index % 4 == 2 else "",
                     destinationUrl="file:///tmp/controlled-output-" + str(index)) for index in range(12)]
        self.jobs = jobs; self.root.setProperty("localJobs", jobs)
        screen = min(self.app.screens(), key=lambda screen: screen.availableGeometry().width())
        self.window.setScreen(screen)
        self.window.resize(min(500, screen.availableGeometry().width() - 32), min(480, screen.availableGeometry().height() - 48))
        self.window.show(); self.window.requestActivate()
        self.assertTrue(QTest.qWaitForWindowExposed(self.window, 2000))
        QTest.qWait(100)
        if os.environ.get("MONET_NAV_CAPTURE"):
            output = Path(os.environ["MONET_NAV_CAPTURE"])
            (output / "transfers-fixture.qml").write_text(qml)
            items = [dict(type=item.metaObject().className(), name=item.objectName(), text=item.property("text"),
                          visible=item.isVisible(), enabled=item.isEnabled(), width=item.width(), height=item.height()) for item in self.buttons()]
            (output / (self._testMethodName + ".json")).write_text(json.dumps(items, indent=2, default=str))
            self.capture(self._testMethodName)
        self.assertGreater(len(self.buttons()), 10, "The fixture must render actual native and local job actions")
        self.assertGreater(len(self.labels()), 12, "The fixture must measure the actual transfer labels")

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(20)
        self.assertFalse(self.errors, "\n".join(self.errors))

    def buttons(self):
        value = self.root.fixtureButtons()
        return value.toVariant() if hasattr(value, "toVariant") else value

    def actions(self):
        value = self.root.property("actions")
        return value.toVariant() if hasattr(value, "toVariant") else value

    def labels(self):
        value = self.root.fixtureLabels()
        return value.toVariant() if hasattr(value, "toVariant") else value

    def test_tab_and_shift_tab_reveal_each_action_with_native_focus(self):
        refresh = next(item for item in self.buttons() if not item.property("text"))
        refresh.forceActiveFocus(Qt.TabFocusReason)
        buttons = self.buttons(); seen = set(); scroll = self.item("transferScroll").property("contentItem")
        for key, modifiers in ((Qt.Key_Tab, Qt.NoModifier), (Qt.Key_Backtab, Qt.ShiftModifier)):
            for _ in range(len(buttons) + 3):
                QTest.keyClick(self.window, key, modifiers); QTest.qWait(30)
                focus = self.window.activeFocusItem()
                if focus in buttons:
                    seen.add(focus)
                    self.assertTrue(focus.property("visualFocus"))
                    if focus is not refresh:
                        point = focus.mapToItem(scroll, QPointF())
                        self.assertTrue(point.y() >= -1 and point.y() + focus.height() <= scroll.height() + 1,
                                        str(dict(text=focus.property("text"), y=point.y(), height=focus.height(),
                                                 content_y=scroll.property("contentY"), viewport=scroll.height())))
        self.assertEqual(set(buttons) - seen, set())

    def test_enter_keypad_and_space_activate_the_focused_action_once(self):
        button = next(item for item in self.buttons() if item.property("text") == self.words.i18n("Pause"))
        for key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.root.setProperty("actions", []); button.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(self.window, key); QTest.qWait(30)
            self.assertEqual(self.actions(), ["native-pause"])
        self.root.setProperty("actions", [])
        QGuiApplication.sendEvent(self.window, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "", True, 2))
        QTest.qWait(30)
        self.assertEqual(self.actions(), [], "A held Enter key must not repeat a transfer action")

    def test_native_wheel_and_touchpad_pixels_scroll_without_triggering_actions(self):
        view = self.item("transferScroll").property("contentItem")
        for pixel in (False, True):
            first, last = self.bounds(view); self.assertGreater(last, first)
            view.setProperty("contentY", first); QTest.qWait(20)
            samples = self.wheel(view, pixel=pixel)
            self.assertGreater(view.property("contentY"), first, str(dict(pixel=pixel, samples=samples)))
            if pixel: self.assertAlmostEqual(view.property("contentY") - first, 80, delta=1)
        self.assertEqual(self.actions(), [])

    def test_full_action_captions_and_labels_fit_a_narrow_panel(self):
        self.window.resize(360, self.window.height()); QTest.qWait(100)
        for button in self.buttons():
            self.assertGreaterEqual(button.width() + 1, button.implicitWidth(), button.property("text"))
        for item in self.labels():
            self.assertLessEqual(item["paintedWidth"], item["width"] + 1, item["text"])
        self.capture("transfers-narrow")

    def test_progress_refresh_and_reordering_preserve_the_focused_job_control(self):
        url = self.jobs[-1]["destinationUrl"]
        button = next(item for item in self.buttons() if item.objectName() == "openLocalTransferFolder"
                      and item.property("destination").toString() == url)
        button.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(60)
        destroyed = QSignalSpy(button.destroyed)
        self.root.setProperty("localJobs", [dict(job, progress=.65) for job in reversed(self.jobs)])
        QTest.qWait(100)
        self.assertEqual(destroyed.count(), 0)
        self.assertIs(self.window.activeFocusItem(), button)
        self.assertEqual(button.property("destination").toString(), url)
        self.assert_visible_in(button, self.item("transferScroll").property("contentItem"))
        self.assertEqual(self.actions(), [])

    def test_manual_home_is_not_undone_by_a_later_progress_update(self):
        buttons = [item for item in self.buttons() if item.objectName() == "openLocalTransferFolder"]
        buttons[-1].forceActiveFocus(Qt.TabFocusReason); QTest.qWait(60)
        view = self.item("transferScroll").property("contentItem")
        self.assertGreater(view.property("contentY"), self.bounds(view)[0])
        QTest.keyClick(self.window, Qt.Key_Home); QTest.qWait(60)
        self.assertAlmostEqual(view.property("contentY"), self.bounds(view)[0], delta=1)
        jobs = [dict(job, progress=.7) for job in self.jobs]; jobs[0]["error"] = "A progress message that changes the first row's height."
        self.root.setProperty("localJobs", jobs); QTest.qWait(100)
        self.assertAlmostEqual(view.property("contentY"), self.bounds(view)[0], delta=1)
        self.assertEqual(self.actions(), [])

    def test_resizing_and_changing_screen_limits_preserve_a_smaller_current_size(self):
        self.root.setProperty("usableScreen", QRectF(0, 0, 900, 900))
        self.window.resize(500, 600); QTest.qWait(60)
        self.root.setProperty("usableScreen", QRectF(0, 0, 640, 360))
        self.window.resize(500, 312)
        self.assertTrue(QMetaObject.invokeMethod(self.page, "fitPopup"))
        QTest.qWait(100)
        self.assertEqual((self.window.width(), self.window.height()), (500, 312))

    def test_a_completed_job_hands_focus_to_its_open_folder_action(self):
        cancel = next(item for item in self.buttons() if item.objectName() == "cancelLocalTransfer")
        cancel.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(60)
        jobs = [dict(job) for job in self.jobs]; jobs[0].update(state="done", progress=1)
        self.root.setProperty("localJobs", jobs); QTest.qWait(100)
        focus = self.window.activeFocusItem()
        self.assertEqual(focus.objectName(), "openLocalTransferFolder")
        self.assertEqual(focus.property("destination").toString(), self.jobs[0]["destinationUrl"])
        self.assert_visible_in(focus, self.item("transferScroll").property("contentItem"))
        self.assertEqual(self.actions(), [])

    def test_folder_loading_and_long_errors_keep_the_list_and_actions_usable(self):
        self.window.resize(360, 312); QTest.qWait(60)
        for busy, error in ((True, ""), (False, "The destination is disconnected. Existing files were retained. " * 8)):
            with self.subTest(busy=busy):
                self.root.setProperty("problem", "Could not read transfers. Try refreshing.")
                self.folder.setProperty("busy", busy); self.folder.setProperty("error", error); QTest.qWait(100)
                view = self.item("transferScroll").property("contentItem")
                self.assertGreaterEqual(view.height(), 40, "Folder messages must leave a usable scrolling area")
                for label in self.labels():
                    self.assertLessEqual(label["paintedWidth"], label["width"] + 1, label["text"])
                button = next(item for item in self.buttons() if (item.property("text") == self.words.i18n("Cancel opening")
                              if busy else item.objectName() == "dismissFolderMessage"))
                button.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(40)
                point = button.mapToScene(QPointF())
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.y() + button.height(), self.window.height() + 1)
                QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(40)
                self.assertFalse(self.folder.property("busy") if busy else self.folder.property("error"))

    def test_hidden_and_inactive_views_stop_their_indeterminate_animations(self):
        def animations():
            value = self.root.fixtureAnimations()
            return value.toVariant() if hasattr(value, "toVariant") else value
        jobs = [dict(job) for job in self.jobs]; jobs[0]["progress"] = -1
        self.root.setProperty("localJobs", jobs); self.folder.setProperty("busy", True); QTest.qWait(60)
        self.assertGreaterEqual(len(animations()), 14)
        self.assertTrue(any(item["kind"] == "progress" and item["active"] for item in animations()))
        self.assertTrue(any(item["kind"] == "busy" and item["active"] for item in animations()))
        activity = self.root.findChild(QObject, "transfersTestActivity")
        activity.setProperty("active", False); QTest.qWait(30)
        self.assertFalse(any(item["active"] for item in animations()))
        activity.setProperty("active", True); self.root.setProperty("expanded", False); QTest.qWait(30)
        self.assertFalse(any(item["active"] for item in animations()))


if __name__ == "__main__":
    unittest.main()
