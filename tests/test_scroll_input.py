"""Monet's shared scroll input keeps a scroll it has started, as browsers do: a control that
takes the wheel itself (KDE's combo boxes and spin boxes) moving under the pointer neither stops
the page nor has its value changed. A scroll that starts on such a control is still its own."""
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QPoint, QPointF, QUrl, Qt
    from PySide6.QtGui import QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False

PAGE = """
import QtQuick
import QtQuick.Controls as QQC2
import "WIDGETS" as Shared
Item {
    width: 400; height: 400
    property int clicks: 0
    Flickable {
        id: page
        objectName: "page"
        anchors.fill: parent
        contentWidth: width
        contentHeight: rows.height
        boundsBehavior: Flickable.StopAtBounds
        Shared.ScrollInput { view: page }
        Column {
            id: rows
            width: page.width
            Repeater {
                model: 16
                delegate: Item {
                    width: rows.width
                    height: 220
                    QQC2.Button { width: parent.width; height: 40; onClicked: clicks++ }
                    // A choice that takes the wheel, as KDE's combo boxes and spin boxes do.
                    QQC2.ComboBox {
                        anchors.centerIn: parent
                        width: 300
                        height: 60
                        wheelEnabled: true
                        model: ["one", "two", "three", "four"]
                        currentIndex: 2
                    }
                }
            }
        }
    }
}
"""


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class ScrollInputKeepsItsScroll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="monet-scroll-input-")
        self.addCleanup(folder.cleanup)
        source = Path(folder.name) / "Page.qml"
        source.write_text(PAGE.replace("WIDGETS", (ROOT / "linux/share/monet/widgets").as_uri()), encoding="utf-8")
        self.view = QQuickView()
        self.view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(self.view.status(), QQuickView.Ready, [e.toString() for e in self.view.errors()])
        self.view.show()
        QTest.qWait(100)
        self.root = self.view.rootObject()
        self.page = next(i for i in self.items() if i.objectName() == "page")
        self.choices = [i for i in self.items() if i.inherits("QQuickComboBox")]
        self.touchpad = QPointingDevice("Scroll fixture touchpad", 45, QInputDevice.TouchPad, QPointingDevice.Finger,
                                        QInputDevice.Position | QInputDevice.PixelScroll | QInputDevice.Scroll, 2, 0)

    def tearDown(self):
        self.view.close()
        self.view.deleteLater()
        QTest.qWait(10)

    def items(self, item=None):
        item = item or self.view.rootObject()
        yield item
        for child in item.childItems():
            yield from self.items(child)

    def send(self, angle=0, pixel=0, phase=None, at=(200, 200)):
        phase = Qt.NoScrollPhase if phase is None else phase
        point = QPointF(*at)
        precise = phase != Qt.NoScrollPhase
        event = QWheelEvent(point, QPointF(self.view.mapToGlobal(QPoint(*at))), QPoint(0, pixel), QPoint(0, angle),
                            Qt.NoButton, Qt.NoModifier, phase, False,
                            Qt.MouseEventSynthesizedBySystem if precise else Qt.MouseEventNotSynthesized,
                            self.touchpad if precise else QPointingDevice.primaryPointingDevice())
        event.setTimestamp(int(time.monotonic() * 1000))
        QGuiApplication.sendEvent(self.view, event)

    def y(self):
        return self.page.property("contentY")

    def to_the_end(self):
        self.page.setProperty("contentY", self.page.property("contentHeight") - self.page.height())
        QTest.qWait(500)  # longer than a held scroll lasts
        return self.y()

    def unchanged_choices(self):
        return [c.property("currentIndex") for c in self.choices].count(2)

    def test_a_touchpad_swipe_scrolls_on_over_choices_that_take_the_wheel(self):
        start = self.to_the_end()
        self.assertGreater(start, 2000)
        self.send(phase=Qt.ScrollBegin)
        for _ in range(int(start / 20) + 20):
            self.send(pixel=20, angle=80, phase=Qt.ScrollUpdate)
            QTest.qWait(8)
        self.send(phase=Qt.ScrollEnd)
        QTest.qWait(50)
        self.assertAlmostEqual(self.y(), 0, delta=1)
        self.assertEqual(self.unchanged_choices(), len(self.choices))

    def test_wheel_notches_in_a_row_scroll_on_over_them(self):
        start = self.to_the_end()
        for _ in range(int(start / 96) + 5):
            self.send(angle=120)
            QTest.qWait(30)
        QTest.qWait(300)
        self.assertAlmostEqual(self.y(), 0, delta=1)
        self.assertEqual(self.unchanged_choices(), len(self.choices))

    def test_a_scroll_that_starts_on_a_choice_is_the_choices(self):
        self.to_the_end()
        choice = self.choices[-2]
        middle = choice.mapToScene(QPointF(choice.width() / 2, choice.height() / 2))
        at = (int(middle.x()), int(middle.y()))
        self.assertTrue(0 < at[1] < 400, at)
        position = self.y()
        self.send(angle=120, at=at)
        QTest.qWait(500)
        self.assertEqual(choice.property("currentIndex"), 1)
        self.assertAlmostEqual(self.y(), position, delta=1)
        # A swipe begun there is the choice's too. (Qt's combo box also counts the swipe's
        # empty begin and end as steps, so only the page is checked.)
        self.send(phase=Qt.ScrollBegin, at=at)
        for _ in range(10):
            self.send(pixel=20, angle=80, phase=Qt.ScrollUpdate, at=at)
            QTest.qWait(8)
        self.send(phase=Qt.ScrollEnd, at=at)
        QTest.qWait(50)
        self.assertAlmostEqual(self.y(), position, delta=1)

    def test_clicks_reach_the_page_while_it_holds_a_scroll(self):
        self.send(angle=-120)
        QTest.qWait(250)  # scrolled, and still held
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, QPoint(200, 230 - round(self.y()) % 220))
        self.send(phase=Qt.ScrollBegin)
        self.send(pixel=-20, angle=-80, phase=Qt.ScrollUpdate)
        QTest.qWait(30)
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, QPoint(200, 230 - round(self.y()) % 220))
        self.send(phase=Qt.ScrollEnd)
        QTest.qWait(50)
        self.assertEqual(self.root.property("clicks"), 2)


if __name__ == "__main__":
    unittest.main()
