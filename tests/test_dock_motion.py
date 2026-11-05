"""Run the real QML motion component without touching the desktop panels."""
import os
from pathlib import Path
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QUrl, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine,QQmlComponent
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest

class DockMotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.engine=QQmlEngine()
        self.component=QQmlComponent(self.engine,QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1]/'image/dock/MonetDockMotion.qml')))
        self.assertFalse(self.component.isError(),[e.toString() for e in self.component.errors()])
        self.motion=self.component.create();self.assertIsNotNone(self.motion)
        self.motion.setProperty('duration',30)
    def tearDown(self):
        self.motion.deleteLater();self.component.deleteLater();self.engine.deleteLater();QTest.qWait(10)
    def settle(self): QTest.qWait(100)
    def test_hover_lifts_and_magnifies_then_settles_without_changing_layout(self):
        self.motion.setProperty('width',64);self.motion.setProperty('height',64)
        self.motion.setProperty('distance',0);self.motion.setProperty('hovering',True);self.settle()
        center=self.motion.property('iconScale');self.assertAlmostEqual(center,1.28,places=2)
        self.assertGreater(self.motion.property('lift'),3)
        self.motion.setProperty('distance',1);self.settle()
        self.assertGreater(self.motion.property('iconScale'),1);self.assertLess(self.motion.property('iconScale'),center)
        self.motion.setProperty('hovering',False);self.settle()
        self.assertAlmostEqual(self.motion.property('lift'),0);self.assertEqual(self.motion.property('width'),64)
        self.assertEqual(self.motion.property('height'),64)
        self.assertAlmostEqual(self.motion.property('amount'),0)
    def test_reduced_motion_and_disabled_context_are_stationary(self):
        self.motion.setProperty('distance',0);self.motion.setProperty('hovering',True);self.settle()
        for prop in ('duration','motionEnabled'):
            self.motion.setProperty(prop,0 if prop=='duration' else False);self.settle()
            self.assertEqual(self.motion.property('iconScale'),1);self.assertEqual(self.motion.property('lift'),0)
            self.motion.setProperty(prop,30 if prop=='duration' else True)
    def test_rapid_pointer_changes_finish_on_latest_icon_without_overshoot(self):
        self.motion.setProperty('hovering',True)
        for distance in (0,.2,1,2,1,0,3):
            self.motion.setProperty('distance',distance);QTest.qWait(5)
            self.assertLessEqual(self.motion.property('iconScale'),1.281)
        self.settle();self.assertAlmostEqual(self.motion.property('amount'),0)

class DockPointer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine = QQmlEngine()
        path = Path(__file__).resolve().parent / 'fixtures/dock-hover.qml'
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)), QQmlComponent.Asynchronous)
        for _ in range(100):
            if not self.component.isLoading(): break
            QTest.qWait(20)
        self.assertTrue(self.component.isReady(), [e.toString() for e in self.component.errors()])
        self.window = self.component.create()
        self.assertIsNotNone(self.window)
        QTest.qWait(40)
        self.move(10, 10)

    def tearDown(self):
        self.window.close(); self.window.deleteLater()
        self.component.deleteLater(); self.engine.deleteLater(); QTest.qWait(20)

    def find(self, name, item=None):
        item = item or self.window.contentItem()
        if item.objectName() == name: return item
        for child in item.childItems():
            found = self.find(name, child)
            if found is not None: return found

    def move(self, x, y=132, wait=100):
        QTest.mouseMove(self.window, QPoint(x, y)); QTest.qWait(wait)

    def amount(self, index): return self.find('motion' + str(index)).property('amount')

    def test_first_entry_and_repeated_sweeps_work_over_native_tooltips(self):
        # A HoverHandler on the ancestor never receives these first hovers:
        # ToolTipArea consumes them. Exercise real pointer events, not properties.
        for index in (0, 1, 2, 3, 4, 3, 2, 1, 0):
            self.move(80 + index * 64)
            self.assertTrue(self.window.property('tracking'))
            self.assertTrue(self.find('task' + str(index)).property('containsMouse'))
            self.assertAlmostEqual(self.amount(index), 1, places=2)
        self.move(10, 10)
        self.assertFalse(self.window.property('tracking'))
        self.assertTrue(all(abs(self.amount(i)) < .001 for i in range(5)))

    def test_fast_reentry_and_task_to_trash_keep_native_clicks(self):
        for index in (0, 4, 1, 3, 0, 4): self.move(80 + index * 64, wait=5)
        QTest.qWait(100)
        self.assertAlmostEqual(self.amount(4), 1, places=2)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(336, 132))
        QTest.mouseClick(self.window, Qt.RightButton, Qt.NoModifier, QPoint(336, 132))
        self.assertEqual(self.window.property('clicks'), 1)
        self.assertEqual(self.window.property('menus'), 1)
        self.move(400)
        self.assertFalse(self.window.property('tracking'))
        self.assertTrue(self.find('trash').property('containsMouse'))
        self.assertAlmostEqual(self.find('trashMotion').property('amount'), 1, places=2)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(400, 132))
        self.assertEqual(self.window.property('clicks'), 2)
        self.move(80)
        self.assertAlmostEqual(self.amount(0), 1, places=2)
        self.assertAlmostEqual(self.find('trashMotion').property('amount'), 0, places=2)

    def test_drag_and_motion_setting_interruptions_recover(self):
        self.move(80)
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(80, 132))
        self.move(105, wait=30); self.move(135, wait=30)
        self.assertTrue(self.window.property('dragging'))
        self.assertEqual(self.window.property('dragStarts'), 1)
        self.assertFalse(self.window.property('tracking'))
        self.assertEqual(self.find('motion0').property('iconScale'), 1)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(135, 132))
        self.assertFalse(self.window.property('dragging'))
        self.move(208)
        self.assertAlmostEqual(self.amount(2), 1, places=2)
        self.window.setProperty('motionEnabled', False); QTest.qWait(100)
        self.assertFalse(self.window.property('tracking'))
        self.move(272)
        self.window.setProperty('motionEnabled', True); QTest.qWait(100)
        self.assertAlmostEqual(self.amount(3), 1, places=2)
        self.window.setProperty('duration', 0); QTest.qWait(40)
        self.assertEqual(self.find('motion3').property('iconScale'), 1)
        self.window.setProperty('duration', 30); QTest.qWait(100)
        self.assertAlmostEqual(self.amount(3), 1, places=2)

    def test_hiding_and_showing_the_dock_does_not_leave_a_stuck_icon(self):
        self.move(144)
        self.window.hide(); QTest.qWait(50)
        self.window.show(); QTest.qWait(50)
        self.move(10, 10); self.move(272)
        self.assertAlmostEqual(self.amount(1), 0, places=2)
        self.assertAlmostEqual(self.amount(3), 1, places=2)

    def test_removing_the_hovered_task_and_adding_it_back_recovers(self):
        self.move(336)
        self.assertAlmostEqual(self.amount(4), 1, places=2)
        self.window.setProperty('taskCount', 4); QTest.qWait(100)
        self.assertFalse(self.window.property('tracking'))
        self.assertIsNone(self.find('motion4'))
        self.move(144)
        self.assertAlmostEqual(self.amount(1), 1, places=2)
        self.window.setProperty('taskCount', 5); QTest.qWait(50)
        self.move(336)
        self.assertAlmostEqual(self.amount(4), 1, places=2)


if __name__=='__main__':unittest.main()
