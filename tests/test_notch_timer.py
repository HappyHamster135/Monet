"""Run the notch's clock with deterministic deadlines, including pre-upgrade state."""
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree

try:
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
except ImportError:
    QQmlEngine = None

CONTENTS = Path(__file__).resolve().parents[1] / "linux/share/plasma/plasmoids/org.monet.notch/contents"


@unittest.skipUnless(QQmlEngine, "requires Qt QML")
class NotchTimer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine = QQmlEngine()
        self.addCleanup(self.engine.deleteLater)
        entries = ElementTree.parse(CONTENTS / "config/main.xml").findall(".//{*}entry")
        types = {"Int": "int", "Double": "double", "Bool": "bool", "String": "string"}
        fields = []
        for entry in entries:
            value = entry.findtext("{*}default") or ""
            kind = types[entry.get("type")]
            fields.append(f'property {kind} {entry.get("name")}: {json.dumps(value) if kind == "string" else value}')
        with tempfile.TemporaryDirectory() as folder:
            scene = Path(folder) / "Scene.qml"
            scene.write_text('import QtQml\nimport "' + (CONTENTS / "ui").as_uri() + '''" as Monet
QtObject {
    function i18n(text) { return text }
    property QtObject config: QtObject { objectName: "settings"; ''' + "\n".join(fields) + ''' }
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

    def test_legacy_focus_deadline_remains_a_single_session_even_when_overdue(self):
        self.settings.setProperty("focusSessions", 4)
        self.settings.setProperty("focus", True)
        self.settings.setProperty("deadline", "5010")
        self.timer.pause(6000)
        self.assertEqual(self.alerts, ["Focus session finished"])
        self.assertEqual(self.quiet, [0])
        self.assertFalse(self.timer.property("active"))
