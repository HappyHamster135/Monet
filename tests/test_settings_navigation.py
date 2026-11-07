"""Actual Settings keys, scroll visibility and layout at the process's display scale."""
import importlib.machinery
import importlib.util
import gettext
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tests.test_settings_feedback import QT

ROOT = Path(__file__).resolve().parents[1]

if QT:
    from PySide6.QtCore import QPoint, QPointF, QLocale, QMetaObject, QUrl, Qt, Q_ARG
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QSignalSpy, QTest
    from tests.test_settings_feedback import FakeHelper


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class SettingsNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.old_locale = QLocale()
        cls.old_direction = cls.app.layoutDirection()
        if os.environ.get('MONET_SETTINGS_TEST_LOCALE'):
            locale = QLocale(os.environ['MONET_SETTINGS_TEST_LOCALE'])
            QLocale.setDefault(locale)
            cls.app.setLayoutDirection(locale.textDirection())
        cls.identity = (cls.app.organizationName(), cls.app.organizationDomain(), cls.app.applicationName())
        cls.app.setOrganizationName("monet-navigation-tests")
        cls.app.setOrganizationDomain("tests.invalid")
        cls.app.setApplicationName("settings")
        cls.old_font = cls.app.font()
        cls.app.setFont(QFont("Inter", int(os.environ.get("MONET_TEST_FONT_SIZE", "10"))))
        cls.font_ids = [QFontDatabase.addApplicationFont(str(p))
                        for p in (ROOT / "linux/share/fonts/monet").glob("*.ttf")]
        loader = importlib.machinery.SourceFileLoader("navigation_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    @classmethod
    def tearDownClass(cls):
        QLocale.setDefault(cls.old_locale)
        cls.app.setLayoutDirection(cls.old_direction)
        cls.app.setFont(cls.old_font)
        cls.app.setOrganizationName(cls.identity[0]); cls.app.setOrganizationDomain(cls.identity[1])
        cls.app.setApplicationName(cls.identity[2])
        for ident in cls.font_ids:
            QFontDatabase.removeApplicationFont(ident)

    def setUp(self):
        if os.environ.get("MONET_SETTINGS_TEST_LANGUAGE"):
            language_name = os.environ["MONET_SETTINGS_TEST_LANGUAGE"]
            words = gettext.translation("monet", localedir=str(ROOT / "linux/share/locale"),
                                        languages=[language_name], fallback=language_name == "en")
            language = patch.object(self.games, "WORDS", words)
            language.start(); self.addCleanup(language.stop)
        self.engine = QQmlApplicationEngine(); self.helper = FakeHelper(); self.words = self.games.Words()
        self.area = self.games.WindowArea()
        self.helper.replies.update({"power": json.dumps({"mode": "balanced", "modes": ["balanced", "power-saver", "performance"]}),
                                    "battery-care": '{"supported":true,"limit":80}',
                                    **{name: "[]" for name in ("wifi-list", "bt-list", "apps-sound", "defaults")}})
        self.errors = []
        self.engine.warnings.connect(lambda errors: self.errors.extend(e.toString() for e in errors))
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "windowArea": self.area, "firstPage": "light", "blurBehind": False,
                            "pictures": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]; self.area.watch(self.window)
        if not getattr(self, "keep_window_size", False): self.window.resize(760, 520)
        QTest.qWait(350)
        if os.environ.get("QT_SCALE_FACTOR"):
            self.assertAlmostEqual(self.window.devicePixelRatio(), float(os.environ["QT_SCALE_FACTOR"]), places=2)
        if os.environ.get("MONET_TEST_REDUCED_MOTION"):
            # The native KDE Units plugin clamps the disabled duration to 1ms.
            self.assertGreaterEqual(self.window.property("speed"), 0)
            self.assertLessEqual(self.window.property("speed"), 1 / 200)
        if os.environ.get("MONET_TEST_REQUIRE_FONTS"):
            self.assertIn("Inter", QFontDatabase.families())
            self.assertIn("Fraunces 72pt SuperSoft", QFontDatabase.families())

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(10)
        self.assertFalse(self.errors, "\n".join(self.errors))

    def item(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name: return item
            pending.extend(item.childItems())
        self.fail("Missing " + name)

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline: QTest.qWait(10)
        self.assertTrue(condition())

    def open(self, route):
        self.assertTrue(QMetaObject.invokeMethod(self.window, "open", Q_ARG("QVariant", route)))
        QTest.qWait(350)

    def capture(self, name):
        if os.environ.get("MONET_NAV_CAPTURE"):
            path = Path(os.environ["MONET_NAV_CAPTURE"]); path.mkdir(parents=True, exist_ok=True)
            self.assertTrue(self.window.grabWindow().save(str(path / (name + ".png"))))

    def assert_visible_in(self, item, view):
        point = item.mapToItem(view, QPointF())
        if point.x() < -1 or point.x() + item.width() > view.width() + 1:
            self.capture('horizontal-focus-overflow')
            context = []
            parent = item
            while parent and parent != view:
                context.append(dict(type=parent.metaObject().className(), name=parent.objectName(),
                                    text=parent.property('text'), x=parent.x(), width=parent.width()))
                parent = parent.parentItem()
            print('FOCUS_OVERFLOW '+json.dumps(context, ensure_ascii=False), flush=True)
        self.assertGreaterEqual(point.y(), -1, item.objectName())
        self.assertLessEqual(point.y() + min(item.height(), view.height()), view.height() + 1, item.objectName())
        self.assertGreaterEqual(point.x(), -1, item.objectName())
        self.assertLessEqual(point.x() + item.width(), view.width() + 1, item.objectName())

    def test_tab_reaches_every_sidebar_page_and_more_settings_with_visible_focus(self):
        search = self.item("settingsSearch"); search.forceActiveFocus(Qt.TabFocusReason)
        nav = self.item("settingsNavigation"); seen = set()
        expected = {"settingsPage-" + p["id"] for p in self.window.property("pages").toVariant()}
        for _ in range(len(expected) + 5):
            QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(20)
            focused = self.window.activeFocusItem()
            if focused is None: break
            name = focused.objectName(); seen.add(name)
            if name.startswith("settingsPage-"):
                self.assert_visible_in(focused, nav)
                self.assertEqual(self.engine.newQObject(focused).property("border").property("width").toInt(), 2)
            if name == "settingsMore": break
        self.assertTrue(expected.issubset(seen), expected - seen)
        self.assertIn("settingsMore", seen)
        more = self.item("settingsMore")
        self.assertEqual(self.engine.newQObject(more).property("border").property("width").toInt(), 2)
        self.capture("sidebar-focus")
        QTest.keyClick(self.window, Qt.Key_Backtab); QTest.qWait(30)
        focused = self.window.activeFocusItem()
        self.assertTrue(focused.objectName().startswith("settingsPage-"))
        self.assert_visible_in(focused, nav)
        QTest.keyClick(self.window, Qt.Key_Tab)
        self.assertTrue(more.hasActiveFocus())

    def test_sidebar_return_keypad_enter_and_more_settings_preserve_focus(self):
        for page, key in (("wifi", Qt.Key_Return), ("bluetooth", Qt.Key_Enter)):
            row = self.item("settingsPage-" + page); row.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(self.window, key); QTest.qWait(350)
            self.assertEqual(self.window.property("page"), page)
            self.assertTrue(row.hasActiveFocus())
        more = self.item("settingsMore"); more.forceActiveFocus(Qt.TabFocusReason)
        for key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            before = len(self.helper.commands)
            QTest.keyClick(self.window, key); QTest.qWait(20)
            self.assertEqual(self.helper.commands[before:], [["helper", "kde", "bluetooth"]])
            self.assertTrue(more.hasActiveFocus())

    def test_custom_choices_accept_both_enter_keys_once(self):
        for name, verb, value, key in (("lightChoice-mist", "light", "mist", Qt.Key_Return),
                                        ("lightChoice-smoke", "light", "smoke", Qt.Key_Enter),
                                        ("seriesChoice-hours", "series", "hours", Qt.Key_Enter)):
            choice = self.item(name); choice.forceActiveFocus(Qt.TabFocusReason)
            self.helper.commands.clear(); QTest.keyClick(self.window, key); QTest.qWait(40)
            self.assertEqual(self.helper.commands.count(["helper", verb, value]), 1)
            self.assertTrue(choice.hasActiveFocus())
        self.open("power")
        for key in (Qt.Key_Return, Qt.Key_Enter):
            choice = self.item("powerMode-power-saver"); choice.forceActiveFocus(Qt.TabFocusReason)
            self.helper.commands.clear(); QTest.keyClick(self.window, key); QTest.qWait(40)
            self.assertEqual(self.helper.commands.count(["helper", "power-mode", "power-saver"]), 1)

    def test_pill_and_tappable_row_accept_keypad_enter_and_disabled_pill_is_skipped(self):
        restore = self.item("restoreLookButton"); restore.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.wait_for(lambda: self.helper.resets == 1)
        self.wait_for(lambda: not self.window.property("restoring"))
        restore.setProperty("enabledPill", False)
        self.assertFalse(restore.isEnabled())
        self.assertFalse(restore.property("activeFocusOnTab"))
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(80)
        self.assertEqual(self.helper.resets, 1)
        self.open("power#battery-limit")
        row = self.item("search-battery-limit")
        self.wait_for(lambda: row.property("tappable"))
        row.forceActiveFocus(Qt.TabFocusReason); self.helper.commands.clear()
        QTest.keyClick(self.window, Qt.Key_Enter); QTest.qWait(40)
        self.assertEqual(self.helper.commands.count(["helper", "battery-limit", "100"]), 1)

    def test_find_escape_and_backward_navigation_do_not_trap_the_keyboard(self):
        self.item("settingsPage-power").forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_F, Qt.ControlModifier); QTest.qWait(20)
        search = self.item("settingsSearch"); self.assertTrue(search.hasActiveFocus())
        search.setProperty("text", "battery")
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(20)
        self.assertEqual(search.property("text"), "")
        self.assertTrue(self.window.isVisible())
        self.assertTrue(search.hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(20)
        self.assertFalse(self.window.isVisible())

    def test_tab_scrolls_power_controls_into_view_at_this_scale(self):
        self.open("power#keep-awake")
        self.wait_for(lambda: self.window.property("pendingAnchor") == "")
        view = self.item("settingsScroller"); focused_names = []; departed = ""
        for _ in range(26):
            QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
            item = self.window.activeFocusItem()
            ancestor = item
            while ancestor and ancestor != view: ancestor = ancestor.parentItem()
            if ancestor is None:
                departed = item.objectName() if item else "no focus"
                break
            self.assert_visible_in(item, view)
            focused_names.append(item.objectName())
        self.assertGreater(len(focused_names), 8, (focused_names, departed))
        self.capture("power-tab")

    def test_wheel_and_touchpad_pixel_deltas_scroll_only_the_panel_under_the_pointer(self):
        nav = self.item("settingsNavigation"); page = self.item("settingsScroller")

        def send(view, pixel):
            point = view.mapToScene(QPointF(view.width() - 24, view.height() / 2))
            screen = QPointF(self.window.mapToGlobal(point.toPoint()))
            QTest.mouseMove(self.window, point.toPoint()); QTest.qWait(20)
            samples = []
            if pixel:
                device = QPointingDevice("Fixture touchpad", 42, QInputDevice.TouchPad, QPointingDevice.Finger,
                                         QInputDevice.Position | QInputDevice.PixelScroll | QInputDevice.Scroll, 2, 0)
                for phase, delta in ((Qt.ScrollBegin, 0), (Qt.ScrollUpdate, -80), (Qt.ScrollEnd, 0)):
                    event = QWheelEvent(point, screen, QPoint(0, delta), QPoint(), Qt.NoButton,
                                        Qt.NoModifier, phase, False, Qt.MouseEventSynthesizedBySystem, device)
                    event.setTimestamp(int(time.monotonic() * 1000))
                    QGuiApplication.sendEvent(self.window, event)
                    QTest.qWait(20)
                    samples.append((str(phase), event.isAccepted(), view.property("contentY")))
            else:
                event = QWheelEvent(point, screen, QPoint(), QPoint(0, -120), Qt.NoButton,
                                    Qt.NoModifier, Qt.NoScrollPhase, False)
                event.setTimestamp(int(time.monotonic() * 1000))
                QGuiApplication.sendEvent(self.window, event)
            QTest.qWait(450)
            return samples

        for pixel in (False, True):
            for target, other in ((nav, page), (page, nav)):
                target.setProperty("contentY", 0); other.setProperty("contentY", 0)
                QTest.qWait(20)
                samples = send(target, pixel)
                self.assertGreater(target.property("contentY"), 0, (target.objectName(), pixel, samples))
                self.assertEqual(other.property("contentY"), 0, (other.objectName(), pixel))

    def test_scrolled_glyphs_do_not_paint_over_the_sidebar_title_or_search(self):
        nav = self.item("settingsNavigation")
        last = nav.property("contentHeight") - nav.height()
        positions = [last, last / 2] + [last / 2 + offset for offset in range(-20, 21, 2)]
        for position in positions:
            nav.setProperty("contentY", max(0, min(last, position)))
            QTest.qWait(30)
            image = self.window.grabWindow(); scale = self.window.devicePixelRatio()
            top = nav.mapToScene(QPointF()).y()
            # The white page marks belong inside the viewport. The title/search
            # above them use dark text on glass, including with the real fonts.
            for edge, start, end in (("above", 42, top - 3),
                                     ("below", top + nav.height() + 3, self.window.height() - 3)):
                white = sum(1 for x in range(int(24 * scale), int(36 * scale))
                            for y in range(int(start * scale), int(end * scale))
                            if min(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                                   image.pixelColor(x, y).blue()) > 253)
                self.assertLessEqual(white, 4, (position, scale, edge, white))
        self.capture("sidebar-clipping")

    def test_scroller_keys_and_modified_wheel_keep_native_page_steps_and_bounds(self):
        view = self.item("settingsScroller"); view.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Home)
        self.assertEqual(view.property("contentY"), 0)
        QTest.keyClick(self.window, Qt.Key_PageDown)
        self.assertGreater(view.property("contentY"), 0)
        QTest.keyClick(self.window, Qt.Key_End)
        last = view.property("contentHeight") - view.height()
        self.assertAlmostEqual(view.property("contentY"), last)
        QTest.keyClick(self.window, Qt.Key_Home)
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertAlmostEqual(view.property("contentY"), min(96, last))
        QTest.keyClick(self.window, Qt.Key_Home)
        point = view.mapToScene(QPointF(view.width() - 24, view.height() / 2))
        event = QWheelEvent(point, QPointF(self.window.mapToGlobal(point.toPoint())), QPoint(), QPoint(0, -120),
                            Qt.NoButton, Qt.ControlModifier, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(self.window, event); QTest.qWait(50)
        self.assertAlmostEqual(view.property("contentY"), min(view.height(), last))

    def test_scroll_background_still_drags_the_window_and_controls_still_click(self):
        method = self.window.metaObject().indexOfSignal("backgroundMoveRequested()")
        spy = QSignalSpy(self.window, self.window.metaObject().method(method))
        view = self.item("settingsScroller")
        point = view.mapToScene(QPointF(view.width() - 24, view.height() / 2)).toPoint()
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.mouseMove(self.window, point - QPoint(40, 0), 25)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, point - QPoint(40, 0))
        QTest.qWait(20)
        self.assertEqual(spy.count(), 1)
        self.assertEqual(view.property("contentY"), 0)
        choice = self.item("lightChoice-mist")
        point = choice.mapToScene(QPointF(choice.width() / 2, choice.height() / 2)).toPoint()
        self.helper.commands.clear()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point); QTest.qWait(20)
        self.assertEqual(self.helper.commands.count(["helper", "light", "mist"]), 1)
        self.assertEqual(spy.count(), 1)

    def test_choice_captions_are_readable_and_inside_their_cards_when_resizing(self):
        def descendants(item):
            for child in item.childItems():
                yield child
                yield from descendants(child)

        def check(names):
            cards = [self.item(name) for name in names]
            for card in cards:
                for text in (item for item in descendants(card)
                             if item.inherits("QQuickText") and item.isVisible() and item.property("text")):
                    self.assertFalse(text.property("truncated"), (card.objectName(), text.property("text")))
                    point = text.mapToItem(card, QPointF())
                    self.assertGreaterEqual(point.x(), -1, card.objectName())
                    self.assertGreaterEqual(point.y(), -1, card.objectName())
                    self.assertLessEqual(point.x() + text.width(), card.width() + 1,
                                         (card.objectName(), text.property("text")))
                    self.assertLessEqual(point.y() + text.height(), card.height() + 1,
                                         (card.objectName(), text.property("text")))
                for other in cards:
                    if card is other: continue
                    a = card.mapToScene(QPointF()); b = other.mapToScene(QPointF())
                    self.assertTrue(a.x() + card.width() <= b.x() + 1 or b.x() + other.width() <= a.x() + 1
                                    or a.y() + card.height() <= b.y() + 1 or b.y() + other.height() <= a.y() + 1,
                                    (card.objectName(), other.objectName()))

        lights = ["lightChoice-" + name for name in ("hours", "mist", "smoke")]
        series = ["seriesChoice-" + name for name in ("hours", "lilies", "haystacks", "magpie", "seasons", "photo")]
        modes = ["powerMode-" + name for name in ("power-saver", "balanced", "performance")]
        for width in (760, 900, 760):
            self.window.resize(width, 520); self.open("light")
            check(lights); check(series)
            self.capture("readable-light-" + str(width))
            self.item("seriesChoice-photo").forceActiveFocus(Qt.TabFocusReason); QTest.qWait(40)
            self.capture("readable-photo-" + str(width))
            self.open("power"); check(modes)
            self.item("powerMode-performance").forceActiveFocus(Qt.TabFocusReason); QTest.qWait(40)
            self.capture("readable-power-" + str(width))

    def test_power_choice_keeps_keyboard_focus_through_its_reply_and_refresh(self):
        self.open("power")
        choice = self.item("powerMode-power-saver"); choice.forceActiveFocus(Qt.TabFocusReason)
        self.helper.replies["power"] = json.dumps(dict(mode="power-saver", modes=["balanced", "power-saver", "performance"]))
        replies = QSignalSpy(self.helper.done)
        self.helper.commands.clear(); QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: replies.count() >= 2)
        self.assertEqual(self.helper.commands.count(["helper", "power-mode", "power-saver"]), 1)
        self.assertIs(self.item("powerMode-power-saver"), choice)
        self.assertTrue(choice.hasActiveFocus())
        before = replies.count()
        QMetaObject.invokeMethod(self.window, "reloadPower")
        self.wait_for(lambda: replies.count() > before)
        self.assertIs(self.item("powerMode-power-saver"), choice)
        self.assertTrue(choice.hasActiveFocus())

    def test_choice_reflow_keeps_focus_and_never_changes_a_preference(self):
        self.open("light")
        choice = self.item("seriesChoice-seasons"); choice.forceActiveFocus(Qt.TabFocusReason)
        self.helper.commands.clear()
        for width in (900, 760, 900):
            self.window.resize(width, 520); QTest.qWait(100)
            self.assertIs(self.item("seriesChoice-seasons"), choice)
            self.assertTrue(choice.hasActiveFocus())
            self.assert_visible_in(choice, self.item("settingsScroller"))
        self.assertFalse(any(c[1] in ("light", "series", "power-mode") for c in self.helper.commands))
