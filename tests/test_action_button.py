"""Shared painted buttons retain keyboard activation and disabled behavior."""
import os
import tempfile
from pathlib import Path
import unittest
from tests.test_settings_feedback import QT

if QT:
    from PySide6.QtCore import QObject, QMetaObject, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class ActionButton(unittest.TestCase):
    def test_keyboard_and_disabled_state(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        app = QGuiApplication.instance() or QGuiApplication([])
        app.setQuitOnLastWindowClosed(False)
        engine = QQmlApplicationEngine()
        directory = (Path(__file__).resolve().parents[1] / "linux/share/monet/widgets").as_uri()
        fixture = tempfile.TemporaryDirectory()
        path = Path(fixture.name) / "ButtonTest.qml"
        path.write_text('import QtQuick\nimport "' + directory + '"\n'
            'Window { id: fixture; visible: true; width: 400; height: 100; property int clicks: 0; '
            'ActionButton { objectName: "button"; text: "Mute microphone"; onClicked: fixture.clicks++ } }')
        engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(engine.rootObjects())
        window = engine.rootObjects()[0]; button = window.findChild(QObject, "button")
        try:
            window.requestActivate(); QTest.qWait(50); QMetaObject.invokeMethod(button, "forceActiveFocus")
            QTest.keyClick(window, Qt.Key_Space); QTest.keyClick(window, Qt.Key_Return)
            self.assertEqual(window.property("clicks"), 2)
            button.setProperty("enabled", False)
            QTest.keyClick(window, Qt.Key_Space); QTest.keyClick(window, Qt.Key_Return)
            self.assertEqual(window.property("clicks"), 2)
        finally:
            window.close(); engine.deleteLater(); QTest.qWait(1)
            fixture.cleanup()
