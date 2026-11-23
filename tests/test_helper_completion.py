"""The real shared helper resolves QML requests once, including immediate failures."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_store_downloads import module

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QProcess, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "native Qt helper and QML callbacks")
class HelperCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.games = module("completion_games", "monet-games")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="monet-helper-completion-")
        self.helper = self.games.Helper()
        self.results = []
        self.helper.done.connect(lambda *reply: self.results.append(reply))
        path = Path(self.tmp.name) / "Request.qml"
        path.write_text('''import QtQuick
import QtQml
QtObject {
    id: root
    property var waiting: ({})
    property bool busy: false
    property int callbacks: 0
    property int code: -1
    property Connections replies: Connections {
        target: helper
        function onDone(ticket, out, code, err) {
            const callback = root.waiting[ticket]
            delete root.waiting[ticket]
            if (callback) callback(out, code, err)
        }
    }
    function ask(command) {
        busy = true
        waiting[helper.run(command)] = function(out, result, err) {
            root.callbacks++
            root.code = result
            root.busy = false
        }
    }
    function rejected() { ask(["unsupported"]) }
    function missing() { ask(["helper"]) }
}
''', encoding="utf-8")
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("helper", self.helper)
        self.engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.engine.rootObjects())
        self.root = self.engine.rootObjects()[0]

    def tearDown(self):
        for process in self.helper.findChildren(QProcess):
            if process.state() != QProcess.NotRunning:
                process.kill(); process.waitForFinished(2000)
        self.engine.deleteLater()
        self.helper.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.tmp.cleanup()

    def until(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "helper request never completed")

    def test_deferred_requests_keep_tickets_and_stdin_until_resumed_once(self):
        helper = self.games.Helper(defer_start=True)
        self.addCleanup(helper.deleteLater)
        replies = []
        helper.done.connect(lambda *reply: replies.append(reply))
        with patch.dict(self.games.PROGRAMS, {"echo": sys.executable}):
            first = helper.feed(["echo", "-c", "import sys; print(sys.stdin.read(), end='')"], "héllo")
            second = helper.run(["echo", "-c", "print('second', end='')"])
            QTest.qWait(30)
            self.assertEqual(replies, [])
            self.assertEqual(helper.findChildren(QProcess), [])
            helper.resume(); helper.resume()
            self.until(lambda: len(replies) == 2)
        self.assertEqual(sorted(replies), [(first, "héllo", 0, ""), (second, "second", 0, "")])
        QTest.qWait(30)
        self.assertEqual(len(replies), 2)

    def test_rejected_command_reaches_the_callback_registered_by_qml(self):
        self.assertTrue(QMetaObject.invokeMethod(self.root, "rejected", Qt.DirectConnection))
        self.until(lambda: not self.root.property("busy"))
        self.assertEqual(self.root.property("callbacks"), 1)
        self.assertEqual(self.root.property("code"), 1)
        self.assertEqual(len(self.results), 1)

    def test_missing_executable_unblocks_qml_and_does_not_accumulate_process_objects(self):
        with patch.dict(self.games.PROGRAMS, {"helper": str(Path(self.tmp.name) / "not-installed")}):
            for n in range(8):
                self.assertTrue(QMetaObject.invokeMethod(self.root, "missing", Qt.DirectConnection))
                self.until(lambda: not self.root.property("busy"))
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.assertEqual(self.helper.findChildren(QProcess), [])
                self.assertEqual(self.root.property("callbacks"), n + 1)
        self.assertEqual([reply[2] for reply in self.results], [1] * 8)
        self.assertTrue(all(reply[3] for reply in self.results))

    def test_a_crashed_process_completes_once_and_following_requests_still_work(self):
        with patch.dict(self.games.PROGRAMS, {"helper": sys.executable}):
            crashed = self.helper.run(["helper", "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"])
            self.until(lambda: len(self.results) == 1)
            normal = self.helper.feed(["helper", "-c", "import sys; print(sys.stdin.read(), end='')"], "héllo")
            self.until(lambda: len(self.results) == 2)
        QTest.qWait(40)
        self.assertEqual(len(self.results), 2)
        self.assertEqual(self.results[0][0], crashed)
        self.assertNotEqual(self.results[0][2], 0)
        self.assertEqual(self.results[1], (normal, "héllo", 0, ""))
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.helper.findChildren(QProcess), [])
