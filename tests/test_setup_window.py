"""Installer keyboard navigation, rendering and completion without touching a disk."""
import os
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "setup"))
try:
    from monet_setup import app
    from monet_setup.qt import QObject, QProcess, QGuiApplication, QQmlApplicationEngine, QUrl
    from PySide6.QtCore import QMetaObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, "requires PySide6 in the Monet VM")
class SetupWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.gui = QGuiApplication.instance() or QGuiApplication([])
        cls.gui.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(mock.patch.object(app, "DEMO", True))
        patches.enter_context(mock.patch.object(app, "STATE", Path(self.folder.name) / "state"))
        self.setup = app.Setup()
        self.setup._step = 5
        self.setup._phase = "install"
        self.setup._log = ["Writing the downloaded system to disk"]
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("setup", self.setup)
        self.engine.rootContext().setContextProperty("art", (ROOT / "setup/art").as_uri() + "/")
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "setup/qml/Main.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]
        self.window.showNormal()
        self.window.resize(1440, 900)
        QTest.qWait(500)

    def tearDown(self):
        if self.setup._proc and self.setup._proc.state() != QProcess.ProcessState.NotRunning:
            self.setup._proc.kill()
            self.setup._proc.waitForFinished(3000)
        self.window.close()
        self.engine.deleteLater()
        self.setup._clock.stop()
        self.setup.deleteLater()
        QTest.qWait(1)
        self.folder.cleanup()

    def worker(self, script):
        self.start_worker(script)
        self.wait_for_worker()

    def start_worker(self, script):
        self.setup._proc = QProcess(self.setup)
        self.setup._proc.setWorkingDirectory(str(ROOT / "setup"))
        self.setup._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.setup._proc.readyReadStandardOutput.connect(self.setup._read)
        self.setup._proc.finished.connect(self.setup._finished)
        self.setup._proc.start(sys.executable, ["-c", script])

    def wait_for_worker(self):
        for _ in range(100):
            if self.setup._proc is None:
                break
            QTest.qWait(50)
        self.assertIsNone(self.setup._proc, "worker did not finish")
        QTest.qWait(500)

    def test_live_install_details_arrive_while_worker_is_running(self):
        child = "import time; print('Unpacking image', flush=True); time.sleep(2)"
        self.start_worker("import sys; from monet_setup import install; "
                          f"install.run(sys.executable, '-c', {child!r}, live=True); "
                          "install.emit(done=True)")
        for _ in range(60):
            if "Unpacking image" in self.setup.details:
                break
            QTest.qWait(25)
        self.assertIn("Unpacking image", self.setup.details)
        self.assertIsNotNone(self.setup._proc)
        self.assertEqual(self.setup._proc.state(), QProcess.ProcessState.Running)
        button = self.window.findChild(QObject, "installDetailsButton")
        QMetaObject.invokeMethod(button, "click")
        QTest.qWait(100)
        self.assertTrue(self.window.findChild(QQuickItem, "installDetails").isVisible())
        self.wait_for_worker()
        self.assertEqual(self.window.property("phase"), "done")

    def test_details_and_final_buffered_completion(self):
        button = self.window.findChild(QObject, "installDetailsButton")
        panel = self.window.findChild(QQuickItem, "installDetails")
        self.assertTrue(button.property("visible"))
        self.assertFalse(panel.property("visible"))
        QMetaObject.invokeMethod(button, "clicked")
        QTest.qWait(100)
        self.assertTrue(panel.property("visible"))
        self.assertLessEqual(panel.y() + panel.height(), panel.parentItem().height())
        self.worker("import sys; sys.stdout.write('{\"done\": true}')")
        self.assertEqual(self.window.property("phase"), "done")
        self.assertFalse(self.window.property("showingKey"))
        self.assertTrue(any(item.property("text") == "Restart" and item.property("visible")
                            for item in self.window.findChildren(QObject)))

    def test_unsuccessful_exit_is_not_success(self):
        self.worker("print('{\"done\": true}', flush=True); raise SystemExit(7)")
        self.assertEqual(self.window.property("phase"), "failed")
        self.assertTrue(self.setup._error)

    def test_encrypted_completion_keeps_the_recovery_step(self):
        self.worker("print('{\"recovery\": \"synthetic-test-key\"}'); print('{\"done\": true}')")
        self.assertEqual(self.window.property("phase"), "done")
        self.assertTrue(self.window.property("showingKey"))
        self.assertFalse(any("synthetic-test-key" in line for line in self.setup._log))

    def tab_to(self, item):
        visited = []
        for _ in range(40):
            QTest.keyClick(self.window, Qt.Key_Tab)
            visited.append(self.window.activeFocusItem().objectName())
            if item.hasActiveFocus():
                return
        self.fail(f"Tab did not reach {item.objectName()}: {visited}")

    def visual_items(self):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(reversed(item.childItems()))

    def test_tab_reaches_continue_and_enter_advances(self):
        for key in (Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                self.window.setProperty("step", 0)
                self.window.requestActivate()
                QTest.qWait(500)
                first = self.window.findChild(QQuickItem, "languageChoice")
                first.forceActiveFocus(Qt.TabFocusReason)
                next_button = self.window.findChild(QQuickItem, "nextButton")
                self.tab_to(next_button)
                QTest.keyClick(self.window, key)
                QTest.qWait(100)
                self.assertEqual(self.window.property("step"), 1)
                QTest.keyClick(self.window, Qt.Key_Backtab, Qt.ShiftModifier)
                self.assertTrue(self.window.findChild(QQuickItem, "backButton").hasActiveFocus())
                QTest.keyClick(self.window, key)
                self.assertEqual(self.window.property("step"), 0)

    def test_account_enter_respects_validation(self):
        self.window.setProperty("step", 2)
        self.window.requestActivate()
        QTest.qWait(500)
        name = self.window.findChild(QQuickItem, "nameEntry")
        password = self.window.findChild(QQuickItem, "passwordEntry")
        confirm = self.window.findChild(QQuickItem, "confirmEntry")
        next_button = self.window.findChild(QQuickItem, "nextButton")
        confirm.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertFalse(next_button.isEnabled())
        self.assertEqual(self.window.property("step"), 2)
        name.setProperty("text", "Keyboard Test")
        name.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(password.hasActiveFocus())
        password.setProperty("text", "synthetic-test-password")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(confirm.hasActiveFocus())
        confirm.setProperty("text", "mismatch")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertFalse(next_button.isEnabled())
        self.assertEqual(self.window.property("step"), 2)
        confirm.setProperty("text", "synthetic-test-password")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.window.property("step"), 3)

    def test_keyboard_app_selection_and_install_choices(self):
        self.window.resize(800, 600)
        self.window.setProperty("step", 3)
        self.window.requestActivate()
        QTest.qWait(500)
        # Built-in apps are labels; Tab reaches only the choices that can change.
        tiles = [item for item in self.visual_items()
                 if item.property("builtIn") is not None]
        self.assertTrue(tiles)
        next_button = self.window.findChild(QQuickItem, "nextButton")
        scroll = self.window.findChild(QQuickItem, "appsScroll")
        next_button.forceActiveFocus()
        for tile in tiles:
            if tile.property("builtIn"):
                self.assertFalse(tile.property("activeFocusOnTab"))
                continue
            self.tab_to(tile)
            top = tile.mapToItem(scroll, QPointF()).y()
            self.assertGreaterEqual(top, -1)
            self.assertLessEqual(top + tile.height(), scroll.height() + 1)
            data = tile.property("modelData")
            before = self.setup._apps[data["index"]]
            QTest.keyClick(self.window, Qt.Key_Return)
            self.assertEqual(self.setup._apps[data["index"]], not before)
            self.assertTrue(tile.hasActiveFocus())
        self.tab_to(next_button)
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.assertEqual(self.window.property("step"), 4)
        QTest.qWait(500)
        encrypt = next(item for item in self.window.findChildren(QQuickItem)
                       if item.property("title") == "Encrypt this PC")
        self.tab_to(encrypt)
        before = self.setup.encrypt
        QTest.keyClick(self.window, Qt.Key_Space)
        self.assertEqual(self.setup.encrypt, not before)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.setup.encrypt, before)
        # A keyboard click must never bypass the same disk blocker as a mouse click.
        self.tab_to(next_button)
        with mock.patch.object(self.setup, "install") as install:
            self.setup._disks = []
            self.setup.changed.emit()
            self.assertFalse(next_button.isEnabled())
            QTest.keyClick(self.window, Qt.Key_Return)
            QTest.keyClick(self.window, Qt.Key_Enter)
            install.assert_not_called()
            self.assertEqual(self.window.property("step"), 4)

    def test_dropdown_keyboard_selection(self):
        self.window.setProperty("step", 0)
        self.window.resize(800, 600)
        self.window.requestActivate()
        QTest.qWait(500)
        for name, value in (("keyboardChoice", "Swedish"), ("regionChoice", "Europe"),
                            ("cityChoice", "Stockholm")):
            with self.subTest(choice=name):
                choice = self.window.findChild(QQuickItem, name)
                target = choice.property("model").index(value)
                choice.forceActiveFocus()
                QTest.keyClick(self.window, Qt.Key_Space)
                QTest.keyClick(self.window, Qt.Key_Home)
                for _ in range(target):
                    QTest.keyClick(self.window, Qt.Key_Down)
                QTest.keyClick(self.window, Qt.Key_Return)
                self.assertEqual(choice.property("displayText"), value)
                self.assertEqual(self.window.property("step"), 0)
                QTest.keyClick(self.window, Qt.Key_Space)
                QTest.keyClick(self.window, Qt.Key_Home)
                QTest.keyClick(self.window, Qt.Key_Escape)
                self.assertEqual(choice.property("displayText"), value)
        self.assertEqual(self.setup._zone, "Europe/Stockholm")

    def test_dropdown_rows_have_text_in_software_rendering(self):
        self.window.setProperty("step", 0)
        for width, height in ((800, 600), (1024, 768), (1440, 900)):
            self.window.resize(width, height)
            QTest.qWait(500)
            for name in ("languageChoice", "keyboardChoice", "regionChoice", "cityChoice"):
                with self.subTest(size=(width, height), choice=name):
                    choice = self.window.findChild(QQuickItem, name)
                    self.assertTrue(choice.property("displayText"))
                    popup = choice.findChild(QObject, "choicePopup")
                    QMetaObject.invokeMethod(popup, "open")
                    QTest.qWait(200)
                    view = popup.property("contentItem")
                    rows = [item for item in view.property("contentItem").childItems()
                            if item.property("modelData") is not None]
                    self.assertTrue(rows)
                    for row in rows:
                        text = row.property("contentItem")
                        self.assertEqual(text.property("text"), str(row.property("modelData")))
                        self.assertGreater(text.height(), 0)
                        self.assertGreater(text.property("lineCount"), 0)
                    QMetaObject.invokeMethod(popup, "close")
                    QTest.qWait(100)
