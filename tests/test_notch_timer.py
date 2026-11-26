"""Run the notch's clock with deterministic deadlines, including pre-upgrade state."""
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree

try:
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
except ImportError:
    QQmlEngine = None

CONTENTS = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents"


def settings_properties():
    entries = ElementTree.parse(CONTENTS / "config/main.xml").findall(".//{*}entry")
    types = {"Int": "int", "Double": "double", "Bool": "bool", "String": "string"}
    fields = []
    for entry in entries:
        value = entry.findtext("{*}default") or ""
        kind = types[entry.get("type")]
        fields.append(f'property {kind} {entry.get("name")}: {json.dumps(value) if kind == "string" else value}')
    return "\n".join(fields)


@unittest.skipUnless(QQmlEngine, "requires Qt QML")
class NotchTimer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine = QQmlEngine()
        self.addCleanup(self.engine.deleteLater)
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Scene.qml"
            scene.write_text('import QtQml\nimport "' + (CONTENTS / "ui").as_uri() + '''" as Monet
QtObject {
    function i18n(text) { return text }
    property QtObject config: QtObject { objectName: "settings"; ''' + settings_properties() + ''' }
    property QtObject model: Monet.NotchTimer { objectName: "timer"; settings: config }
}''')
            self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(scene)))
            self.root = self.component.create()
        self.assertIsNotNone(self.root, self.component.errorString())
        self.timer = self.root.findChild(QObject, "timer")
        self.settings = self.root.findChild(QObject, "settings")
        self.quiet, self.alerts = [], []
        self.timer.quietRequested.connect(self.quiet.append)
        self.timer.finished.connect(self.alerts.append)
        self.settings.setProperty("timerMinutes", 1)

    def test_countdown_pauses_at_exact_remaining_time_and_rings_once(self):
        t = self.timer
        t.start(False, 1000)
        t.pause(2501)
        self.assertEqual(t.remaining(90000), 58499)
        t.finishIfDue(90000)
        self.assertFalse(self.alerts)
        t.resume(91000)
        t.finishIfDue(149498)
        self.assertFalse(self.alerts)
        t.finishIfDue(149499)
        t.finishIfDue(200000)
        self.assertEqual(self.alerts, ["Timer finished"])
        self.assertFalse(t.property("active"))
        self.assertFalse(self.quiet)

    def test_focus_rounds_wait_for_user_and_only_work_requests_quiet(self):
        t = self.timer
        self.settings.setProperty("focusSessions", 3)
        self.settings.setProperty("longBreakEvery", 2)
        now = 1000
        t.start(True, now)
        for index in (1, 2, 3):
            self.assertEqual(t.property("round"), index)
            now += 60000
            t.finishIfDue(now)
            if index == 3:
                break
            self.assertTrue(t.property("waiting"))
            self.assertEqual(t.property("longBreak"), index == 2)
            now += 1000000
            t.finishIfDue(now)
            self.assertTrue(t.property("waiting"))
            t.resume(now)
            now += (5 if index == 1 else 15) * 60000
            t.finishIfDue(now)
            self.assertTrue(t.property("waiting"))
            t.resume(now)
        self.assertFalse(t.property("active"))
        self.assertEqual(self.alerts, ["Focus session finished", "Break finished"] * 2 + ["Focus rounds finished"])
        self.assertEqual(self.quiet[1::2], [0, 0, 0])
        self.assertEqual(len(self.quiet), 6)
        self.assertEqual(t.property("completion"), "Focus rounds finished")

    def test_cancel_and_resume_restore_quiet_only_for_running_work(self):
        t = self.timer
        t.start(True, 1000)
        t.pause(16000)
        t.resume(20000)
        t.cancel()
        t.cancel()
        self.assertEqual(self.quiet, [61, 0, 65, 0])
        self.assertEqual(self.alerts, [])
        self.assertFalse(t.property("active"))

    def test_completion_can_be_dismissed_after_reload_without_a_second_ring(self):
        t = self.timer
        t.start(False, 1000)
        t.finishIfDue(61000)
        self.assertEqual(t.property("completion"), "Timer finished")
        self.assertEqual(self.settings.property("timerResult"), "timer")
        saved = self.settings.property("timerResult")
        t.dismiss()
        self.assertEqual(t.property("completion"), "")
        new_root = self.component.create()
        self.assertIsNotNone(new_root, self.component.errorString())
        self.addCleanup(new_root.deleteLater)
        new_root.findChild(QObject, "settings").setProperty("timerResult", saved)
        t = new_root.findChild(QObject, "timer")
        t.finished.connect(self.alerts.append)
        t.finishIfDue(62000)
        self.assertEqual(t.property("completion"), "Timer finished")
        self.assertEqual(self.alerts, ["Timer finished"])
        t.start(True, 71000)
        self.assertEqual(t.property("completion"), "")
        t.cancel()
        self.assertEqual(t.property("completion"), "")

    def test_legacy_focus_deadline_remains_a_single_session_even_when_overdue(self):
        self.settings.setProperty("focusSessions", 4)
        self.settings.setProperty("focus", True)
        self.settings.setProperty("deadline", "5010")
        self.timer.pause(6000)
        self.assertEqual(self.alerts, ["Focus session finished"])
        self.assertEqual(self.quiet, [0])
        self.assertFalse(self.timer.property("active"))


@unittest.skipUnless(QQmlEngine, "requires Qt Quick")
class TimerRuler(unittest.TestCase):
    def test_focus_controls_fit_the_narrow_popup(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Clock.qml"
            scene.write_text('import QtQuick\nimport "' + (CONTENTS / "ui").as_uri() + '''" as Monet
Item {
    id: scene; width: 310; height: 300
    function i18n(text) { return text }
    QtObject { id: config; @SETTINGS@ }
    Monet.NotchTimer { id: model; settings: config }
    Monet.TimePage {
        id: clock; anchors.fill: parent; timer: model; now: 0; message: ""; offerAwake: true
        formatDuration: seconds => "25:00"
    }
    function fits(label) {
        const pending = [clock]
        while (pending.length) {
            const item = pending.pop()
            if (!item.visible) continue
            if (item.clicked && item.text === label) {
                const left = item.mapToItem(scene, 0, 0).x
                return left >= 0 && left + item.width <= scene.width + 1
            }
            for (const child of item.children) pending.push(child)
        }
        return false
    }
    function showFocus() { clock.mode = 1 }
}
'''.replace("@SETTINGS@", settings_properties()))
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            window.rootObject().showFocus()
            QTest.qWait(60)
            for label in ("Start", "Keep awake", "Focus options"):
                self.assertTrue(window.rootObject().fits(label), label)

    def test_taps_and_drags_adjust_minutes_and_respect_the_limit(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Ruler.qml"
            scene.write_text('import QtQuick\nimport "' + (CONTENTS / "ui").as_uri() + '''" as Monet
Monet.MinuteRuler { width: 240; height: 54; minutes: 25; onChosen: m => minutes = m }
''')
            window = QQuickView()
            self.addCleanup(window.close)
            window.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(window.status(), QQuickView.Ready, [e.toString() for e in window.errors()])
            window.show()
            QTest.qWait(40)
            ruler = window.rootObject()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(165, 30))
            self.assertEqual(ruler.property("minutes"), 30)
            QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, QPoint(130, 30))
            for x in (103, 85, 67):
                QTest.mouseMove(window, QPoint(x, 30), 15)
            QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(67, 30))
            self.assertGreater(ruler.property("minutes"), 30)
            ruler.setProperty("minutes", 1440)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(165, 30))
            self.assertEqual(ruler.property("minutes"), 1440)
            ruler.setProperty("minutes", 1)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(70, 30))
            self.assertEqual(ruler.property("minutes"), 1)
