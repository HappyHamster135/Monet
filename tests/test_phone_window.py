"""Native Phone page checks; run inside a private HOME/XDG and D-Bus test session."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QCoreApplication, QEvent, QMetaObject, QPointF, QTimer, QUrl, Qt, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class PhoneHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self):
            super().__init__()
            self.ticket = 0
            self.calls = []
            self.rows = [{"id": ident, "name": name, "paired": True, "near": True, "battery": None, "charging": None}
                         for ident, name in (("first_phone", "First test phone"), ("second_phone", "Second test phone"))]
            self.discovery = (json.dumps(self.rows), 0)
            self.sharing = ('{"state":"dispatched"}', 0)
            self.delay = 30

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket = self.ticket
            self.calls.append(list(command))
            out, code = self.discovery if command[1] == "phones" else self.sharing if command[1] == "phone-send" else ("{}", 0)
            QTimer.singleShot(self.delay, lambda: self.done.emit(ticket, out, code, ""))
            return ticket


@unittest.skipUnless(QT and os.environ.get("MONET_PHONE_WINDOW_ROOT"), "requires the isolated Qt Phone fixture")
class PhoneWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(os.environ["MONET_PHONE_WINDOW_ROOT"]).resolve()
        for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
            path = Path(os.environ[name]).resolve()
            assert path.is_relative_to(fixture) and path.is_dir() and path.stat().st_uid == os.getuid(), name
        assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
        assert os.environ["QT_QUICK_BACKEND"] == "software"
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=" + str(fixture / "runtime") + "/")
        cls.artifacts = fixture / "artifacts"
        assert cls.artifacts.is_dir()
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setOrganizationName("monet-phone-tests")
        cls.app.setApplicationName("phone-settings-fixture")
        loader = importlib.machinery.SourceFileLoader("phone_fixture_words", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    def setUp(self):
        self.engine = QQmlApplicationEngine()
        self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(value.toString() for value in values))
        self.helper = PhoneHelper()
        self.words = self.games.Words()
        context = self.engine.rootContext()
        context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "phone", "blurBehind": False,
                            "pictures": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.assertIsInstance(self.window, QQuickWindow)
        self.window.setWidth(760)
        self.window.setHeight(600)
        QTest.qWait(450)
        self.assertEqual(self.window.property("page"), "phone")
        self.assertEqual(len(self.window.property("phoneList").toVariant()), 2)

    def tearDown(self):
        image = self.window.grabWindow()
        path = self.artifacts / (self._testMethodName + ".png")
        self.assertFalse(path.exists())
        self.assertFalse(image.isNull())
        self.assertTrue(image.save(str(path)))
        self.window.close()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QTest.qWait(5)
        self.assertEqual(self.errors, [])

    def items(self):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(item.childItems())

    def buttons(self, text):
        return [item for item in self.items() if item.isVisible() and item.property("text") == text
                and item.metaObject().indexOfSignal("clicked()") >= 0]

    def row(self, item):
        while item is not None:
            if item.property("title") in ("First test phone", "Second test phone"):
                return item
            item = item.parentItem()
        self.fail("Phone action lost its named device row")

    def click(self, item):
        self.assertTrue(item.isVisible())
        self.assertTrue(item.property("enabledPill"))
        item.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(60)

    def test_files_and_sharing_target_the_selected_device(self):
        files = {self.row(button).property("title"): button for button in self.buttons("Files")}
        self.assertEqual(set(files), {"First test phone", "Second test phone"})
        for title, ident in (("Second test phone", "second_phone"), ("First test phone", "first_phone")):
            self.click(files[title])
            self.assertEqual(self.helper.calls[-1], ["helper", "phone-files", ident])
        send = next(button for button in self.buttons("Send a file…") if self.row(button).property("title") == "Second test phone")
        self.click(send)
        self.assertEqual(self.helper.calls[-1], ["helper", "phone-send", "second_phone"])
        self.assertEqual(self.window.property("phoneFileState"), "dispatched")
        self.assertTrue(any(item.property("title") == "Sharing requested" for item in self.items()))
        for button in self.buttons("Files") + self.buttons("Send a file…"):
            row = self.row(button)
            point = button.mapToItem(row, QPointF(0, 0))
            self.assertGreaterEqual(point.x(), 0)
            self.assertLessEqual(point.x() + button.width(), row.width())
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y() + button.height(), row.height())

    def test_cancellation_failure_and_invalid_results_allow_retry(self):
        for output, code, state in (("{\"state\":\"canceled\"}", 0, "canceled"),
                                    ("{\"state\":\"dispatched\"}", 1, "failed"), ("null", 0, "failed")):
            self.helper.sharing = (output, code)
            self.helper.delay = 180
            before = len([call for call in self.helper.calls if call[1] == "phone-send"])
            self.click(self.buttons("Send a file…")[0])
            self.assertTrue(self.window.property("phoneSending"))
            self.assertTrue(all(not item.property("enabledPill") for item in self.buttons("Send a file…")))
            QTest.qWait(200)
            self.assertFalse(self.window.property("phoneSending"))
            self.assertEqual(self.window.property("phoneFileState"), state)
            self.assertEqual(len([call for call in self.helper.calls if call[1] == "phone-send"]), before + 1)

    def test_discovery_failure_clears_actions_and_retry_recovers(self):
        self.helper.discovery = (json.dumps(self.helper.rows), 1)
        QMetaObject.invokeMethod(self.window, "loadPhones")
        QTest.qWait(80)
        self.assertTrue(self.window.property("phoneFailed"))
        self.assertEqual(self.window.property("phoneList").toVariant(), [])
        self.assertEqual(self.buttons("Files"), [])
        self.assertEqual(self.buttons("Send a file…"), [])
        self.helper.discovery = (json.dumps(self.helper.rows), 0)
        self.helper.delay = 180
        self.click(self.buttons("Try again")[0])
        self.assertTrue(self.window.property("phoneChecking"))
        QTest.qWait(200)
        self.assertFalse(self.window.property("phoneFailed"))
        self.assertEqual(len(self.buttons("Files")), 2)
