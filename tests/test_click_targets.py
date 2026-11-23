"""Painted feedback must not cancel clicks after small pointer/trackpad movement."""
import os
from pathlib import Path
import tempfile
import unittest
from tests.test_settings_feedback import QT

if QT:
    from PySide6.QtCore import QObject, QPoint, QPointF, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QSignalSpy, QTest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class ClickTargets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.engine = QQmlApplicationEngine()
        self.errors = []
        self.engine.warnings.connect(lambda errors: self.errors.extend(e.toString() for e in errors))
        path = Path(self.folder.name) / "Clicks.qml"
        path.write_text('import QtQuick\nimport "' + (ROOT / 'linux/share/monet/games').as_uri() + '" as Games\n'
            'import "' + (ROOT / 'linux/share/monet/settings-app').as_uri() + '" as Settings\n'
            'import "' + (ROOT / 'linux/share/monet/store-app').as_uri() + '" as Store\n'
            'Window { width:520; height:350; visible:true\n'
            'QtObject { id:ink; property bool dark:false; property color lily:"#357f72"; '
            'property color ink:"#111111"; property real speed:1; property color line:"#aaaaaa"; '
            'property color wash:"#eeeeee"; property color wash2:"#dddddd"; property color press:"#cccccc"; property color dim:"#555555" }\n'
            'Games.Pill { objectName:"pill"; x:20; y:40; width:200; height:44; text:"Choose"; tone:ink }\n'
            'Games.SunButton { objectName:"sun"; x:280; y:40; width:200; height:44; text:"Play" }\n'
            'Settings.SettingsControls.Pill { objectName:"settings"; x:20; y:140; width:200; height:44; text:"Save"; tone:ink }\n'
            'Store.Tile { objectName:"store"; x:280; y:140; width:200; height:140; app:({name:"Fixture"}); tone:ink }\n}')
        self.engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        QTest.qWait(50)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        QTest.qWait(10)
        self.folder.cleanup()
        self.assertFalse(self.errors, '\n'.join(self.errors))

    def test_small_movement_at_each_edge_activates_once_after_the_press_animation(self):
        for name in ('pill', 'sun', 'settings', 'store'):
            button = self.window.findChild(QObject, name)
            clicks = QSignalSpy(button.chosen if name == 'store' else button.clicked)
            width, height = int(button.width()), int(button.height())
            for x, y, dx, dy in ((1, height//2, 0, 1), (width-2, height//2, 0, 1),
                                 (width//2, 1, 1, 0), (width//2, height-2, 1, 0)):
                with self.subTest(button=name, edge=(x, y)):
                    point = button.mapToScene(QPointF(x, y)).toPoint()
                    QTest.mouseMove(self.window, point)
                    QTest.qWait(180)
                    before = clicks.count()
                    QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, point)
                    QTest.qWait(200)
                    pressed_scale = button.property('scale')
                    release = point + QPoint(dx, dy)
                    QTest.mouseMove(self.window, release)
                    QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, release)
                    QTest.qWait(20)
                    self.assertEqual(clicks.count() - before, 1)
                    self.assertEqual(pressed_scale, 1.0)

    def test_releasing_outside_or_on_a_disabled_button_does_not_activate(self):
        for name in ('pill', 'sun', 'settings', 'store'):
            button = self.window.findChild(QObject, name)
            clicks = QSignalSpy(button.chosen if name == 'store' else button.clicked)
            point = QPoint(int(button.x()+100), int(button.y()+22))
            QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.mouseMove(self.window, QPoint(250, 140))
            QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(250, 140))
            self.assertEqual(clicks.count(), 0)
            button.setProperty('enabled', False)
            QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
            self.assertEqual(clicks.count(), 0)
