"""Real Plasma widgets consume native activity events, without host services."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

try:
    from PySide6.QtCore import QMetaObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
except ImportError:
    QGuiApplication = None


@unittest.skipUnless(QGuiApplication, "requires PySide6 and Kirigami")
class WidgetGlass(unittest.TestCase):
    def test_glass_follows_wallpaper_and_widget_replacement(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        widgets = ROOT / "linux/share/monet/widgets"
        component.setData(b"""
            import QtQuick
            Item {
                id: scene
                property Item current: null
                component Painting: Item {
                    property var hours: []
                    property Item below: null
                    property Item above: null
                }
                Painting { id: first }
                Painting { id: second; x: 20 }
                Item { id: otherWallpaper }
                Item { id: holder; x: 50 }
                Item { id: otherHolder; x: 90 }
                Glass { id: pane; objectName: "pane"; parent: holder; width: 100; height: 80; wallpaper: scene.current }
                function loadWallpaper() { current = first }
                function replaceWallpaper() { current = second }
                function moveWidget() { pane.parent = otherHolder; otherHolder.x = 100 }
                function useOtherWallpaper() { current = otherWallpaper }
            }
        """, QUrl.fromLocalFile(str(widgets / "GlassFixture.qml")))
        root = component.create()
        self.assertIsNotNone(root, component.errorString())
        pane = root.findChild(QQuickItem, "pane")
        self.assertIsNone(pane.property("painting"))
        self.assertTrue(QMetaObject.invokeMethod(root, "loadWallpaper"))
        self.assertEqual(pane.property("painting"), root.property("current"))
        self.assertEqual(pane.property("patch").width(), 180)
        self.assertEqual(pane.property("patch").x(), 10)
        self.assertTrue(QMetaObject.invokeMethod(root, "replaceWallpaper"))
        self.assertEqual(pane.property("painting"), root.property("current"))
        self.assertEqual(pane.property("patch").x(), -10)
        self.assertTrue(QMetaObject.invokeMethod(root, "moveWidget"))
        self.assertEqual(pane.property("patch").x(), 40)
        self.assertTrue(QMetaObject.invokeMethod(root, "useOtherWallpaper"))
        self.assertIsNone(pane.property("painting"))
        app.processEvents()


@unittest.skipUnless(os.environ.get('MONET_ACTIVITY_FIXTURE') and shutil.which('plasmawindowed'),
                     'native activity fixture and Plasma host')
class WidgetActivity(unittest.TestCase):
    def run_widget(self, name):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/widget-activity.py'), name], check=True, timeout=40)

    def test_batteries(self): self.run_widget('batteries')
    def test_quick(self): self.run_widget('quick')
    def test_system(self): self.run_widget('system')
    def test_network(self): self.run_widget('network')
    def test_storage(self): self.run_widget('storage')
    def test_played(self): self.run_widget('played')
    def test_frame(self): self.run_widget('frame')
    def test_clock(self): self.run_widget('clock')
    def test_calendar(self): self.run_widget('calendar')
    def test_placard(self): self.run_widget('placard')
    def test_sound(self): self.run_widget('sound')
    def test_stacks(self): self.run_widget('stacks')
    def test_transfers(self): self.run_widget('transfers')
    def test_worldclock(self): self.run_widget('worldclock')
    def test_weather(self): self.run_widget('weather')

    def test_user_writes_finish_while_inactive(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/activity-stores.py')], check=True, timeout=25)

    def test_wallpaper_keeps_static_image_and_pauses_network_and_animation(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/activity-wallpaper.py')], check=True, timeout=30)
