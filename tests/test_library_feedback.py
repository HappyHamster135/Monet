"""Apps and Games keep a usable library when a refresh fails or arrives late."""
import importlib.machinery
import importlib.util
import gettext
import json
import os
from pathlib import Path
import time
import unittest

from tests.test_games_library import game

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QLocale, QMetaObject, QPoint, QPointF, QTimer, QUrl, Signal, Slot, Qt, Q_ARG
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    from PySide6.QtTest import QSignalSpy, QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class LibraryHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self):
            super().__init__()
            self.ticket, self.calls, self.pending = 0, [], []

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket = self.ticket
            self.calls.append(list(command))
            verb = command[1] if len(command) > 1 else ""
            if verb in ("library", "app-library"):
                self.pending.append(ticket)
            else:
                out = '{"steam":false,"hint":false}' if verb == "owned-refresh" else "{}"
                QTimer.singleShot(1, lambda: self.done.emit(ticket, out, 0, ""))
            return ticket

        def reply(self, value, code=0):
            self.done.emit(self.pending.pop(0), value, code, "")


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class LibraryFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setOrganizationName("monet-library-feedback-tests")
        cls.app.setOrganizationDomain("tests.invalid")
        cls.app.setApplicationName("libraries")
        cls.old_font, cls.old_locale, cls.old_direction = cls.app.font(), QLocale(), cls.app.layoutDirection()
        cls.app.setFont(QFont("Inter", int(os.environ.get("MONET_TEST_FONT_SIZE", "10"))))
        cls.fonts = [QFontDatabase.addApplicationFont(str(p))
                     for p in (ROOT / "linux/share/fonts/monet").glob("*.ttf")]
        if os.environ.get("MONET_SETTINGS_TEST_LOCALE"):
            locale = QLocale(os.environ["MONET_SETTINGS_TEST_LOCALE"])
            QLocale.setDefault(locale)
            cls.app.setLayoutDirection(locale.textDirection())
        loader = importlib.machinery.SourceFileLoader("library_feedback_host", str(ROOT / "linux/libexec/monet-games"))
        cls.host = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.host)
        language = os.environ.get("MONET_SETTINGS_TEST_LANGUAGE")
        if language:
            cls.host.WORDS = gettext.translation("monet", localedir=str(ROOT / "linux/share/locale"),
                                                languages=[language], fallback=language == "en")

    @classmethod
    def tearDownClass(cls):
        cls.app.setFont(cls.old_font)
        QLocale.setDefault(cls.old_locale)
        cls.app.setLayoutDirection(cls.old_direction)
        for font in cls.fonts:
            QFontDatabase.removeApplicationFont(font)

    def capture(self, name):
        folder = os.environ.get("MONET_LIBRARY_CAPTURE") or os.environ.get("MONET_NAV_CAPTURE")
        if folder:
            self.window.grabWindow().save(str(Path(folder) / (name + ".png")))

    def open(self, kind):
        self.kind = kind
        self.model = "games" if kind == "Games" else "apps"
        self.engine = QQmlApplicationEngine()
        self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        self.helper, self.words = LibraryHelper(), self.host.Words()
        context = self.engine.rootContext()
        context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "blurBehind": False,
                            "art": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/games" / (kind + ".qml"))))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.window.resize(1140, 760)
        self.addCleanup(self.close)
        self.window.requestActivate()
        self.wait_for(self.window.isActive)
        self.wait_for(lambda: self.helper.pending)

    def close(self):
        self.window.close()
        self.engine.deleteLater()
        QTest.qWait(5)
        self.assertFalse([e for e in self.errors if "QSettings" not in e], "\n".join(self.errors))

    def wait_for(self, condition):
        until = time.monotonic() + 3
        while not condition() and time.monotonic() < until:
            QTest.qWait(10)
        self.assertTrue(condition())

    def item(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail("Missing " + name)

    def refresh(self):
        self.assertTrue(QMetaObject.invokeMethod(self.window, "refresh"))

    def library(self, count=1):
        if self.kind == "Games":
            return [game("local:" + str(i), "Game %03d" % i, "ready", launcher="", here="local:" + str(i))
                    for i in range(count)]
        return [dict(id="app-%d.desktop" % i, name="App %03d" % i, detail="A useful app", icon="applications-other",
                     source="system", store="", group="utilities", last=0, removable=False) for i in range(count)]

    def initial_failure(self, kind):
        self.open(kind)
        self.assertFalse(self.window.property("loaded"))
        self.helper.reply("null")
        self.wait_for(lambda: self.window.property("libraryProblem"))
        self.assertFalse(self.window.property("loaded"))
        self.window.resize(760, 520)
        QTest.qWait(100)
        self.capture(kind.lower() + "-library-retry")
        retry = self.item("libraryRetry")
        self.assertTrue(retry.isVisible())
        retry.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: self.helper.pending)
        self.assertFalse(retry.property("enabled"))
        self.helper.reply("[]")
        self.wait_for(lambda: self.window.property("loaded"))
        self.assertFalse(self.window.property("libraryProblem"))
        self.assertFalse(retry.isVisible())
        self.wait_for(lambda: self.item("gamesGrid" if kind == "Games" else "appsGrid").hasActiveFocus())

    def test_apps_initial_failure_has_a_keyboard_retry(self):
        self.initial_failure("Apps")

    def test_games_initial_failure_has_a_keyboard_retry(self):
        self.initial_failure("Games")

    def invalid_refresh(self, kind):
        self.open(kind)
        library = self.library()
        self.helper.reply(json.dumps(library))
        self.wait_for(lambda: self.window.property("loaded"))
        self.window.setProperty("pageId", library[0]["id"])
        invalid = [("null", 0), ("{}", 0), ("[null]", 0), ("broken", 0),
                   (json.dumps(library), 1), (json.dumps(library * 2), 0),
                   (json.dumps([dict(library[0], name=42)]), 0)]
        for reply, code in invalid:
            with self.subTest(reply=reply, code=code):
                self.refresh()
                self.helper.reply(reply, code)
                QTest.qWait(10)
                self.assertTrue(self.window.property("libraryProblem"))
                self.assertEqual(self.window.property(self.model).toVariant(), library)
                self.assertEqual(self.window.property("pageId"), library[0]["id"])
                self.assertTrue(self.window.property("loaded"))
        self.refresh()
        self.helper.reply(json.dumps(library))
        self.wait_for(lambda: not self.window.property("libraryProblem"))

    def test_apps_failed_refresh_keeps_the_library_and_open_page(self):
        self.invalid_refresh("Apps")

    def test_games_failed_refresh_keeps_the_library_and_open_page(self):
        self.invalid_refresh("Games")

    def refreshes(self, kind):
        self.open(kind)
        for _ in range(3):
            self.refresh()
        self.assertEqual(len(self.helper.pending), 1)
        self.helper.reply(json.dumps(self.library()))
        self.wait_for(lambda: self.helper.pending)
        newer = self.library(60)
        self.helper.reply(json.dumps(newer))
        self.wait_for(lambda: not self.window.property("libraryBusy"))
        self.assertEqual(self.window.property(self.model).toVariant(), newer)
        self.assertEqual(len([c for c in self.helper.calls if c[-1] in ("library", "app-library")]), 2)

        grid = self.item("gamesGrid" if kind == "Games" else "appsGrid")
        grid.setProperty("currentIndex", 20)
        grid.setProperty("contentY", 180)
        grid.forceActiveFocus()
        QTest.qWait(100)
        before = grid.property("contentY")
        changed = QSignalSpy(getattr(self.window, self.model + "Changed"))
        self.refresh()
        self.helper.reply(json.dumps(newer, indent=2))
        QTest.qWait(100)
        self.assertEqual(changed.count(), 0)
        self.assertAlmostEqual(grid.property("contentY"), before)
        self.assertEqual(grid.property("currentIndex"), 20)
        self.assertTrue(grid.hasActiveFocus())

    def test_apps_refreshes_wait_their_turn_and_keep_scroll_and_focus(self):
        self.refreshes("Apps")

    def test_games_refreshes_wait_their_turn_and_keep_scroll_and_focus(self):
        self.refreshes("Games")

    def test_games_heading_and_controls_fit_a_narrow_window(self):
        self.open("Games")
        self.helper.reply(json.dumps(self.library(5)))
        self.window.resize(760, 520)
        QTest.qWait(100)
        heading, sorts, add = [self.item(name) for name in ("gameLibraryHeading", "gameSorts", "gameAdd")]
        self.assertGreaterEqual(heading.width(), 120)
        self.assertTrue(sorts.isVisible())
        self.assertGreaterEqual(sorts.y(), add.y() + add.height())
        self.assertLessEqual(sorts.width(), sorts.parentItem().width())
        grid = self.item("gamesGrid")
        self.assertGreater(grid.height(), 150)
        self.assertEqual(grid.property("count"), 5)
        self.capture("games-narrow")

    def test_games_software_rendering_keeps_covers_and_the_hero_visible(self):
        self.open("Games")
        library = self.library(5)
        self.helper.reply(json.dumps(library))
        QTest.qWait(100)
        expected = QSGRendererInterface.GraphicsApi.OpenGL if os.environ.get("QSG_RHI_BACKEND") == "opengl" else QSGRendererInterface.GraphicsApi.Software
        self.assertEqual(self.window.rendererInterface().graphicsApi(), expected)
        for name in ("gameCover-local:0", "gameHero"):
            if name == "gameHero":
                self.assertTrue(QMetaObject.invokeMethod(self.window, "openPage", Q_ARG("QVariant", library[0])))
                QTest.qWait(100)
            item = self.item(name)
            at = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            picture = self.window.grabWindow()
            scale = picture.width() / self.window.width()
            color = picture.pixelColor(round(at.x() * scale), round(at.y() * scale))
            self.assertGreater(max(color.red(), color.green(), color.blue()) - min(color.red(), color.green(), color.blue()),
                               30, "The painted cover must be visible: " + name + " rendered as " + color.name())
        self.capture("game-page-rendered")

    def back(self, kind):
        self.open(kind)
        library = self.library(60)
        if kind == "Apps":
            library[20].update(removable=True, source="mine")
        self.helper.reply(json.dumps(library))
        self.wait_for(lambda: self.window.property("loaded"))
        grid = self.item("gamesGrid" if kind == "Games" else "appsGrid")
        grid.setProperty("currentIndex", 20)
        if kind == "Games":
            self.window.setProperty("keyed", library[20]["id"])
        grid.setProperty("contentY", 180)
        QTest.qWait(100)
        before = grid.property("contentY")
        for mouse in (False, True):
            self.assertTrue(QMetaObject.invokeMethod(self.window, "openPage", Q_ARG("QVariant", library[20])))
            QTest.qWait(50)
            if mouse:
                QTest.mouseClick(self.window, Qt.BackButton, Qt.NoModifier, QPoint(450, 250))
            else:
                QTest.keyClick(self.window, Qt.Key_Left, Qt.AltModifier)
            self.wait_for(lambda: self.window.property("pageId") == "")
            self.wait_for(grid.hasActiveFocus)
            self.assertAlmostEqual(grid.property("contentY"), before)
        if kind == "Apps":
            self.assertTrue(QMetaObject.invokeMethod(self.window, "openPage", Q_ARG("QVariant", library[20])))
            self.window.setProperty("confirmRemove", True)
            QTest.keyClick(self.window, Qt.Key_Escape)
            self.wait_for(lambda: not self.window.property("confirmRemove"))
            self.assertEqual(self.window.property("pageId"), library[20]["id"])
            self.assertFalse(any(c[1:2] == ["app-remove"] for c in self.helper.calls))
        else:
            self.assertTrue(QMetaObject.invokeMethod(self.window, "openPage", Q_ARG("QVariant", library[20])))
            for dialog in ("keyOpen", "sheetOpen"):
                self.window.setProperty(dialog, True)
                QTest.qWait(100)
                QTest.keyClick(self.window, Qt.Key_Left, Qt.AltModifier)
                self.wait_for(lambda: not self.window.property(dialog))
                self.assertEqual(self.window.property("pageId"), library[20]["id"])

    def test_apps_back_keys_and_mouse_preserve_the_place_and_cancel_first(self):
        self.back("Apps")

    def test_games_back_keys_and_mouse_preserve_the_place(self):
        self.back("Games")


if __name__ == "__main__":
    unittest.main()
