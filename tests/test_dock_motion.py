"""Run the real QML motion component without touching the desktop panels."""
import os
from pathlib import Path
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine,QQmlComponent
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

if __name__=='__main__':unittest.main()
