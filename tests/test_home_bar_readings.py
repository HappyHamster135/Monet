"""Render panel readings and verify power estimates, presentation and subscriptions."""
from pathlib import Path
import unittest

try:
    from PySide6.QtCore import QObject, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
except ImportError:
    QQmlEngine = None

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.system/contents/ui'


@unittest.skipUnless(QQmlEngine, "requires Qt Quick and KDE sensors")
class HomeBarReadings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        class Words(QObject):
            @Slot(str, str, result=str)
            @Slot(str, str, "QVariant", result=str)
            @Slot(str, str, "QVariant", "QVariant", result=str)
            def i18nd(self, domain, text, *values):
                for i, v in enumerate(values, 1):
                    text = text.replace(f"%{i}", format(v, "g") if isinstance(v, float) else str(v))
                return text
        self.engine = QQmlEngine()
        self.words = Words()
        self.engine.rootContext().setContextObject(self.words)
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Layouts
Item {
    id: scene
    property var power: ({available: true, battery: 80, charging: false, minutes: 125})
    property bool sampling: false
    property bool vertical: false
    property string style: "both"
    property var selected: ["battery/time", "battery/charge"]
    property alias report: strip.summary
    property real extent: vertical ? strip.Layout.minimumHeight : strip.Layout.minimumWidth
    property alias percentBar: charge.showBar
    property alias percentValue: charge.showValue
    property bool hasSensor: cpu.sensor !== null
    ReadingNames { id: labels }
    ReadingStrip {
        id: strip; width: 120; height: 44
        power: scene.power; style: scene.style; readings: scene.selected
        vertical: scene.vertical; sampling: scene.sampling
    }
    ReadingCell {
        id: charge; names: labels; reading: "battery/charge"
        power: scene.power; sampling: scene.sampling; style: scene.style
    }
    ReadingCell {
        id: cpu; names: labels; reading: "cpu/all/usage"; power: ({}); sampling: scene.sampling; style: scene.style
    }
}''',
                          QUrl.fromLocalFile(str(UI / 'ReadingsTest.qml')))
        self.scene = self.component.create()
        self.assertIsNotNone(self.scene, self.component.errorString())
        self.view = QQuickWindow()
        self.view.resize(240, 140)
        self.scene.setParentItem(self.view.contentItem())
        self.view.show()
        self.addCleanup(self.view.close)
        QTest.qWait(50)
        self.addCleanup(self.engine.deleteLater)
        self.addCleanup(self.scene.deleteLater)

    def test_estimates_percentages_and_unknown_battery(self):
        p = self.scene
        self.assertEqual(p.property("report"), "Time left  2:05\nBattery charge  80%")
        p.setProperty("power", {"available": True, "charging": True, "minutes": 6, "battery": 4})
        self.assertEqual(p.property("report"), "To full  0:06\nBattery charge  4%")
        for power in ({"available": False}, {"available": True, "minutes": None, "battery": None}):
            p.setProperty("power", power)
            self.assertEqual(p.property("report"), "Battery time  —\nBattery charge  —")
            self.assertFalse(p.property("percentBar"))

    def test_style_orientation_and_fixed_extent(self):
        p = self.scene
        p.setProperty("selected", ["battery/charge"])
        QTest.qWait(40)
        one = p.property("extent")
        for value in (0, 100, 9):
            p.setProperty("power", {"available": True, "battery": value})
            self.assertEqual(p.property("extent"), one)
        for style, bar, number in (("bars", True, False), ("values", False, True), ("both", True, True)):
            p.setProperty("style", style)
            self.assertEqual((p.property("percentBar"), p.property("percentValue")), (bar, number))
        p.setProperty("vertical", True)
        QTest.qWait(40)
        height = p.property("extent")
        p.setProperty("selected", ["battery/charge", "battery/time"])
        QTest.qWait(40)
        self.assertGreater(p.property("extent"), height * 1.5)
        p.setProperty("selected", [])
        self.assertEqual(p.property("report"), "")
        self.assertGreater(p.property("extent"), 0)

    def test_inactive_reading_releases_its_sensor(self):
        self.assertFalse(self.scene.property("hasSensor"))
        self.scene.setProperty("sampling", True)
        self.assertTrue(self.scene.property("hasSensor"))
        self.scene.setProperty("sampling", False)
        self.assertFalse(self.scene.property("hasSensor"))
