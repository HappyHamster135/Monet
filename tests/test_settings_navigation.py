"""Actual Settings keys, scroll visibility and layout at the process's display scale."""
import importlib.machinery
import importlib.util
import gettext
import json
import os
from pathlib import Path
import time
from tests.settings_support import select_settings_page
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper
from tests.test_settings_feedback import QT

ROOT = Path(__file__).resolve().parents[1]

if QT:
    from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QLocale, QMetaObject, QUrl, Qt, Q_ARG
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QInputDevice, QKeyEvent, QPointingDevice, QWheelEvent, QWindow
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
                                    "power-mode": '{"ok":true}', "battery-saver": '{"ok":true}',
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
        select_settings_page(self.window, self.window.property("page"))
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
        # Store, panel and transfer fixtures also borrow this visual-tree finder.
        if self.window.metaObject().indexOfProperty("pageReady") >= 0:
            select_settings_page(self.window, self.window.property("page"))
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

    def test_every_page_loads_on_demand_with_its_window_context(self):
        pages = self.window.property("pages").toVariant()
        for page in [entry["id"] for entry in pages] + ["welcome"]:
            with self.subTest(page=page):
                select_settings_page(self.window, page)
                self.assertIsNotNone(self.window.findChild(QObject, "settingsPageLoader").property("item"))
                self.assertFalse(self.errors, "\n".join(self.errors))

    def test_mouse_settings_opens_the_wheel_profile_editor(self):
        from PySide6.QtQuick import QQuickItem
        select_settings_page(self.window, "input")
        row = self.window.findChild(QQuickItem, "wheelScrollingSettings")
        self.assertIsNotNone(row)
        row.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertIn(["helper", "utilities", "wheel-scrolling"], self.helper.commands)

    def test_input_deep_link_loads_devices_when_window_is_first_exposed(self):
        self.activity = self.games.WindowActivity()
        hidden = QWindow()
        self.activity.watch(hidden)
        self.engine.rootContext().setContextProperty("windowActivity", self.activity)
        self.helper.replies["input"] = json.dumps({"touchpads": [{"name": "Built-in pad", "id": "a" * 64}]})
        self.open("input#touchpad-clicks")
        self.assertFalse(self.window.property("pollingActive"))
        self.assertNotIn(["helper", "input"], self.helper.commands)
        self.app.processEvents()
        self.activity.watch(self.window)
        self.wait_for(lambda: bool(self.window.property("inputInfo").toVariant().get("touchpads")))
        self.assertEqual(self.window.property("currentAnchor"), "touchpad-clicks")

    def test_visible_touchpad_list_follows_native_hotplug_signals(self):
        from PySide6.QtDBus import QDBusConnection, QDBusMessage

        bus = QDBusConnection.sessionBus()
        self.helper.replies["input"] = json.dumps({"touchpads": []})
        self.open("input#touchpad-clicks")
        self.wait_for(lambda: "touchpads" in self.window.property("inputInfo").toVariant())
        watcher = self.window.findChild(QObject, "touchpadDevicesWatcher")
        self.assertTrue(watcher.setProperty("service", bus.baseService()))
        pad = {"name": "External pad", "id": "b" * 64}
        for member, pads in (("deviceAdded", [pad]), ("deviceRemoved", [])):
            self.helper.replies["input"] = json.dumps({"touchpads": pads})
            signal = QDBusMessage.createTargetedSignal(bus.baseService(), watcher.property("path"),
                                                       watcher.property("iface"), member)
            signal.setArguments(["event9"])
            self.assertTrue(bus.send(signal))
            self.wait_for(lambda: self.window.property("inputInfo").toVariant()["touchpads"] == pads)

    def test_touchpad_switches_reported_choices_and_counts_actual_buttons(self):
        from PySide6.QtQuick import QQuickItem
        def item(name):
            return self.window.findChild(QQuickItem, name)

        full = dict(name="Built-in pad", id="a" * 64, tap=True, fingers=3, drag=True,
                    map="secondary", method="areas", methods=["areas", "fingers"])
        small = dict(name="External pad", id="b" * 64, tap=True, fingers=1, drag=False)
        self.helper.replies["input"] = json.dumps(dict(touchpads=[full, small]))
        self.open("input#touchpad-clicks")
        self.wait_for(lambda: item("touchpadTapButtons").isVisible())
        selector = item("clickTouchpadDevice")
        self.assertTrue(selector.isVisible())
        self.assertEqual(selector.property("currentIndex"), 0)
        selector.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Down)
        self.wait_for(lambda: selector.property("currentIndex") == 1)
        self.assertFalse(item("touchpadPressMethod").isVisible())
        self.assertFalse(item("touchpadTapButtons").isVisible())
        self.helper.held_commands.add("touchpad-click")
        row = item("touchpadTapEnabled")
        row.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.helper.commands.count(["helper", "touchpad-click", small["id"], "tap", "off"]), 1)
        self.helper.done.emit(self.helper.pending_commands.pop(), json.dumps({"ok": True,
            "pads": [full, dict(small, tap=False)]}), 0, "")
        self.wait_for(lambda: not row.property("checked"))

        toggle = item("touchpadTestToggle")
        toggle.forceActiveFocus(); QTest.keyClick(self.window, Qt.Key_Return)
        view = item("settingsScroller"); area = item("touchpadClickTest")
        self.wait_for(area.isVisible)
        y = area.mapToItem(view, QPointF(0, 0)).y() + view.property("contentY")
        view.setProperty("contentY", max(0, min(view.property("contentHeight") - view.height(), y - 24)))
        QTest.qWait(70)
        pt = area.mapToScene(QPointF(area.width() / 2, area.height() / 2)).toPoint()
        for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
            QTest.mouseClick(self.window, button, pos=pt)
        panel = area
        while panel and panel.metaObject().indexOfProperty("primary") < 0:
            panel = panel.parentItem()
        self.assertEqual([panel.property(key) for key in ("primary", "secondary", "middle")], [1, 1, 1])
        self.capture("touchpad-clicks")
        self.assertEqual(selector.property("displayText"), small["name"])
        self.assertLessEqual(panel.width(), panel.parentItem().width() + 1)
        selector.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Up)
        self.wait_for(lambda: item("touchpadPressMethod").isVisible())
        self.capture("finger-clicks")

    def test_mouse_settings_opens_extra_click_preferences(self):
        from PySide6.QtQuick import QQuickItem
        select_settings_page(self.window, "input")
        row = self.window.findChild(QQuickItem, "extraClickSettings")
        self.assertIsNotNone(row)
        row.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertIn(["helper", "utilities", "extra-clicks"], self.helper.commands)

    def test_default_apps_opens_last_window_preferences(self):
        from PySide6.QtQuick import QQuickItem
        select_settings_page(self.window, "apps")
        row = self.window.findChild(QQuickItem, "quitOnCloseSettings")
        self.assertIsNotNone(row)
        row.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertIn(["helper", "utilities", "quit-on-close"], self.helper.commands)

    def test_sound_settings_opens_the_media_key_editor(self):
        from PySide6.QtQuick import QQuickItem
        select_settings_page(self.window, "sound")
        row = self.window.findChild(QQuickItem, "mediaKeySettings")
        self.assertIsNotNone(row)
        row.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertIn(["helper", "utilities", "media-keys"], self.helper.commands)

    def test_rapid_page_changes_finish_on_the_last_selection(self):
        for page in ("security", "apps", "wifi", "storage", "light"):
            self.window.setProperty("page", page)
        select_settings_page(self.window, "power")
        loader = self.window.findChild(QObject, "settingsPageLoader")
        self.assertTrue(loader.property("source").toString().endswith("SettingsPower.qml"))
        self.assertEqual(self.window.property("page"), "power")
        self.assertFalse(self.errors, "\n".join(self.errors))

    def test_display_colors_are_searchable_with_an_in_place_test(self):
        self.helper.replies["display-state"] = json.dumps({
            "sizes": [{"name": "eDP-1", "width": 3840, "height": 2400, "scale": 200, "highDensity": True}],
            "features": [{"name": "eDP-1", "hdr": False, "vrr": None}],
        })
        self.open("display#color")
        self.wait_for(lambda: self.window.property("pendingAnchor") == "")
        self.assertIn(["helper", "display-state"], self.helper.commands)
        self.assertNotIn(["helper", "display-sizes"], self.helper.commands)
        self.assertTrue(self.item("screenSizeRow-eDP-1").isVisible())
        profiles = self.item("openColorProfiles")
        profiles.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: ["helper", "kde", "display"] in self.helper.commands)
        self.capture("display-colors")

        parent_size = self.window.size()
        start_test = self.item("openDisplayTest")
        start_test.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        test_window = self.window.findChild(QWindow, "displayTestWindow")
        self.assertIsNotNone(test_window)
        self.wait_for(test_window.isVisible)
        self.wait_for(lambda: self.app.focusWindow() == test_window)
        self.assertEqual(test_window.visibility(), QWindow.FullScreen)
        self.assertEqual(test_window.screen(), self.window.screen())
        if os.environ.get("MONET_NAV_CAPTURE"):
            path = Path(os.environ["MONET_NAV_CAPTURE"]) / "display-test.png"
            self.assertTrue(test_window.grabWindow().save(str(path)))
        escape = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        QGuiApplication.sendEvent(test_window, escape)
        self.wait_for(lambda: not test_window.isVisible())
        self.assertEqual(self.window.size(), parent_size)

    def test_lan_opens_from_quick_settings_and_search_at_its_section(self):
        # Quick Settings' LAN tile and the search's "LAN settings" both open wifi#lan.
        lan = next(entry for entry in quick_helper().search_catalog() if entry["id"] == "lan")
        self.assertEqual(lan["target"], "wifi#lan")
        self.helper.replies["lan"] = json.dumps(dict(available=True, devices=[
            dict(device="enp1s0", profile="Wired connection 1", state="connected", ipv4=["192.0.2.2/24"],
                 ipv6=[], gateways=["192.0.2.1"], dns=["192.0.2.53"])]))
        self.open(lan["target"])
        self.wait_for(lambda: self.window.property("pendingAnchor") == "")
        self.assertEqual(self.window.property("page"), "wifi")
        caption = self.item("search-lan")
        self.assertTrue(caption.isVisible())
        self.assertEqual(self.window.property("highlightedItem"), caption)
        # Found by name in the window's items: wrapping every QObject in the window (timers,
        # attached objects) tripped an assertion in Fedora's PySide in the next test.
        manage = self.item("manageWiredConnections")
        manage.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: ["helper", "kde", "wifi"] in self.helper.commands)

    def test_windows_download_failure_uses_selected_iso(self):
        self.helper.replies["about"] = '{"windows":"Not found","setup":"download-failed"}'
        self.helper.replies["library"] = "[]"
        self.helper.replies["windows-setup-status"] = '{"status":"download-failed","active":false,"percent":0}'
        self.helper.held_commands.add("windows-setup-start")
        self.open("windows")
        self.assertTrue(self.item("startWindowsSetup").isVisible())
        self.assertTrue(self.item("chooseWindowsIso").isVisible())
        self.assertTrue(self.item("windowsIsoPage").isVisible())
        setup = self.item("prepareWindowsIso")
        self.assertFalse(setup.isVisible())
        iso = QUrl.fromLocalFile("/media/USB/Windows 11.iso")
        self.assertTrue(self.window.setProperty("windowsIso", iso))
        self.wait_for(setup.isVisible)
        setup.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: ["helper", "windows-setup-start", iso.toString().encode().hex()]
                      in self.helper.commands)
        self.assertFalse(setup.isVisible())
        self.assertNotIn(["helper", "windows-setup-start"], self.helper.commands)
        self.assertNotIn(["monet", "windows"], self.helper.commands)
        message = "the Windows ISO could not be opened"
        self.helper.replies["windows-setup-status"] = json.dumps({
            "status": "download-failed", "mediaError": True, "message": message,
        })
        self.helper.done.emit(self.helper.pending_commands.pop(), "", 0, "")
        self.wait_for(lambda: self.item("windowsSetupDetail").property("text") == message)
        self.assertFalse(setup.isVisible())

    def test_windows_retry_keeps_failure_detail_and_uses_explicit_retry(self):
        for state, title, detail in (
            ({"status": "download-failed", "message": "Microsoft's download service refused the request"},
             "Retry download", "Microsoft's download service refused the request"),
            ({"status": "pending", "interrupted": True}, "Try setup again",
             "This PC returned to Monet before Windows setup finished. Try again to resume the prepared installation."),
        ):
            with self.subTest(state=state):
                self.helper.held_commands.add("windows-setup-start")
                self.helper.replies.update({"about": '{"windows":"Not found"}', "library": "[]",
                                            "windows-setup-status": json.dumps(state)})
                self.open("display")
                self.open("windows")
                expected_detail = detail if "message" in state else self.words.i18n(detail)
                self.wait_for(lambda: self.item("windowsSetupDetail").property("text") == expected_detail)
                setup = self.item("startWindowsSetup")
                self.assertTrue(setup.isVisible())
                self.assertEqual(setup.property("text"), self.words.i18n(title))
                self.assertEqual(self.item("chooseWindowsIso").isVisible(), not state.get("interrupted", False))
                setup.forceActiveFocus()
                count = self.helper.commands.count(["helper", "windows-setup-start", "--retry"])
                QTest.keyClick(self.window, Qt.Key_Return)
                self.wait_for(lambda: self.helper.commands.count(["helper", "windows-setup-start", "--retry"]) == count + 1)
                self.helper.done.emit(self.helper.pending_commands.pop(), "", 0, "")

    def test_windows_setup_uses_detected_iso_in_one_click(self):
        iso = "file:///home/fixture/Downloads/Windows11%20x64.iso"
        self.helper.replies.update({"about": '{"windows":"Not found","setup":"download-failed"}',
                                    "library": "[]", "windows-setup-status": json.dumps({
                                        "status": "download-failed", "active": False, "iso": iso})})
        self.helper.held_commands.add("windows-setup-start")
        self.open("windows")
        setup = self.item("prepareWindowsIso")
        self.wait_for(setup.isVisible)
        self.assertFalse(self.item("windowsIsoPage").isVisible())
        setup.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: ["helper", "windows-setup-start", iso.encode().hex()] in self.helper.commands)

    def test_windows_setup_reports_preparation_failure_with_detected_iso(self):
        message = "a Windows setup partition contains an unexpected filesystem; it was not formatted"
        self.helper.replies.update({"about": '{"windows":"Not found","setup":"failed"}',
                                    "library": "[]", "windows-setup-status": json.dumps({
                                        "status": "failed", "active": False, "message": message,
                                        "iso": "file:///home/fixture/Downloads/Win11.iso"})})
        self.open("windows")
        self.wait_for(lambda: self.item("windowsSetupDetail").property("text") == message)

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
        search = self.item("settingsSearch")
        first_page = self.item("settingsPage-light")
        first_page.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Backtab)
        self.assertTrue(search.hasActiveFocus())
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

    def test_sidebar_hover_clears_as_the_pointer_moves_to_the_next_row(self):
        wifi = self.item("settingsPage-wifi")
        bluetooth = self.item("settingsPage-bluetooth")
        selected = self.item("settingsPage-light")

        def move_to(row):
            point = row.mapToScene(QPointF(row.width() / 2, row.height() / 2)).toPoint()
            QTest.mouseMove(self.window, point)
            self.app.processEvents()

        move_to(wifi)
        self.wait_for(lambda: wifi.property("color").alphaF() > 0.02)
        move_to(bluetooth)
        self.assertEqual(wifi.property("color").alpha(), 0)
        self.assertGreater(bluetooth.property("color").alpha(), 0)
        move_to(selected)
        self.assertEqual(bluetooth.property("color").alpha(), 0)
        self.assertEqual(selected.property("color").alpha(), 0)
        self.assertEqual(self.window.property("page"), "light")

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

    def test_search_recovers_from_null_and_wrong_shaped_helper_replies(self):
        search = self.item("settingsSearch")
        for index, reply in enumerate(("null", "[]", "42", "broken")):
            with self.subTest(reply=reply):
                self.helper.replies["search"] = reply
                search.setProperty("text", "battery " + str(index))
                self.wait_for(lambda: not self.window.property("searchBusy"))
                self.assertTrue(self.window.property("searchProblem"))
        self.helper.replies["search"] = '{"results":[]}'
        search.setProperty("text", "battery")
        self.wait_for(lambda: self.window.property("searchReady") == "battery")
        self.assertFalse(self.window.property("searchProblem"))

    def test_reopening_settings_restores_its_maximized_state(self):
        self.window.showMaximized()
        QTest.qWait(30)
        self.window.showMinimized()
        QTest.qWait(30)
        self.helper.wanted.emit("sound")
        self.wait_for(lambda: self.window.property("page") == "sound")
        self.assertEqual(self.window.visibility(), QWindow.Maximized)
        self.wait_for(self.window.isActive)
        close = self.item("windowClose")
        self.wait_for(lambda: abs(close.mapToScene(QPointF(close.width(), 0)).x() - self.window.width()) < 0.5
                      and abs(close.mapToScene(QPointF(0, 0)).y()) < 0.5)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(self.window.width() - 1, 0))
        self.wait_for(lambda: not self.window.isVisible())

    def test_a_normal_window_that_fits_keeps_its_chosen_size(self):
        width, height = self.window.property("availableWidth") - 8, self.window.property("availableHeight") - 8
        self.window.resize(width, height)
        QMetaObject.invokeMethod(self.window, "fitAvailableScreen")
        QTest.qWait(50)
        self.assertEqual((self.window.width(), self.window.height()), (width, height))

    def test_escape_cancels_privacy_and_recovery_questions_before_closing(self):
        for route, name in (("privacy", "forgetRecentApps"), ("updates", "resetPc"), ("updates", "rollbackPc")):
            with self.subTest(route=route, name=name):
                self.open(route)
                if name == "rollbackPc":
                    self.window.setProperty("previous", dict(date="2026-11-17", version="0.9.8-7"))
                    QTest.qWait(20)
                button = self.item(name)
                self.assertTrue(button.isVisible())
                before = button.property("text")
                button.forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(self.window, Qt.Key_Return)
                self.assertNotEqual(button.property("text"), before)
                self.helper.commands.clear()
                QTest.keyClick(self.window, Qt.Key_Escape)
                QTest.qWait(20)
                self.assertTrue(self.window.isVisible())
                self.assertEqual(button.property("text"), before)
                self.assertTrue(button.hasActiveFocus())
                self.assertFalse(any(c[1] in ("forget", "reset", "rollback") for c in self.helper.commands))

    def test_escape_cancels_account_forms_and_returns_focus(self):
        self.helper.replies["users"] = json.dumps([dict(login="sample", name="Sample User", you=True, admin=True, guest=False)])
        self.open("users")
        for name, state in (("changeUserName", "renaming"), ("changeUserPassword", "passwordState")):
            with self.subTest(name=name):
                button = self.item(name)
                button.forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(self.window, Qt.Key_Return)
                self.wait_for(lambda: self.window.property(state))
                self.helper.commands.clear()
                QTest.keyClick(self.window, Qt.Key_Escape)
                QTest.qWait(20)
                self.assertTrue(self.window.isVisible())
                self.assertFalse(self.window.property(state))
                self.assertTrue(button.hasActiveFocus())
                self.assertFalse(any(c[1] in ("rename", "password") for c in self.helper.commands))

    def test_escape_cancels_a_wifi_password_without_joining(self):
        ssid = "Example Wi-Fi"
        self.helper.replies["status"] = '{"wifi":true}'
        self.helper.replies["wifi-list"] = json.dumps([dict(name=ssid, active=False, secure=True, known=False, enterprise=False, signal=80)])
        self.open("wifi")
        row = self.item("wifiNetwork-" + ssid.encode().hex())
        row.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: self.window.property("joining") == ssid)
        self.helper.commands.clear()
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(20)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.property("joining"), "")
        self.assertTrue(row.hasActiveFocus())
        self.assertFalse(any(c[1] == "wifi-join" for c in self.helper.commands))

    def test_escape_cancels_windows_restart_and_trash_questions(self):
        self.helper.replies["about"] = '{"windows":"Ready"}'
        for route, name in (("windows", "windowsSwitch"), ("storage", "emptyTrash")):
            with self.subTest(route=route):
                self.open(route)
                if route == "storage":
                    self.window.setProperty("storageInfo", dict(total=4096, used=2048, trash=1024, measured=True))
                button = self.item(name)
                self.assertTrue(button.isVisible())
                before = button.property("text")
                button.forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(self.window, Qt.Key_Return)
                self.assertNotEqual(button.property("text"), before)
                calls = list(self.helper.commands)
                QTest.keyClick(self.window, Qt.Key_Escape)
                self.assertTrue(self.window.isVisible())
                self.assertEqual(button.property("text"), before)
                self.assertTrue(button.hasActiveFocus())
                self.assertEqual(self.helper.commands, calls)

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

    def test_returning_to_settings_preserves_the_scroll_position(self):
        self.open("power")
        view = self.item("settingsScroller")
        choice = self.item("powerMode-power-saver")
        choice.forceActiveFocus(Qt.TabFocusReason)
        self.wait_for(choice.hasActiveFocus)
        QTest.qWait(40)  # Let the keyboard focus reveal finish before scrolling away.
        bottom = view.property("contentHeight") - view.height()
        self.assertGreater(bottom, 50)
        view.setProperty("contentY", bottom)
        QTest.qWait(40)
        other = QWindow()
        self.addCleanup(other.close)
        other.show()
        other.requestActivate()
        self.wait_for(other.isActive)
        self.window.requestActivate()
        self.wait_for(choice.hasActiveFocus)
        QTest.qWait(100)
        self.assertAlmostEqual(view.property("contentY"), bottom, delta=1)

    def test_lid_lock_label_stays_on_one_line(self):
        self.helper.replies["power"] = json.dumps({"hasLid": True, "lidAction": 1})
        self.open("power")
        group = self.item("lidActionChoices")
        self.assertTrue(group.isVisible())
        choices = [item for row in group.childItems() for item in row.childItems()
                   if item.property("modelData") is not None]
        self.assertEqual(len(choices), 4)
        for choice in choices:
            label = next(child for child in choice.childItems() if child.inherits("QQuickText"))
            self.assertEqual(label.property("lineCount"), 1, label.property("text"))
            self.assertLessEqual(label.implicitWidth(), label.width() + 1)

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

    def test_mouse_wheel_combines_notches_and_yields_to_touchpad_input(self):
        nav = self.item("settingsNavigation")
        nav.setProperty("contentY", 0)
        point = nav.mapToScene(QPointF(nav.width() - 24, nav.height() / 2))
        screen = QPointF(self.window.mapToGlobal(point.toPoint()))
        touchpad = QPointingDevice("Settings fixture touchpad", 44, QInputDevice.TouchPad,
                                  QPointingDevice.Finger, QInputDevice.Position | QInputDevice.PixelScroll
                                  | QInputDevice.Scroll, 2, 0)
        QTest.mouseMove(self.window, point.toPoint())
        QTest.qWait(20)

        def send(amount, precise=False):
            event = QWheelEvent(point, screen, QPoint(0, amount) if precise else QPoint(),
                                QPoint() if precise else QPoint(0, amount), Qt.NoButton, Qt.NoModifier,
                                Qt.ScrollUpdate if precise else Qt.NoScrollPhase, False,
                                Qt.MouseEventSynthesizedBySystem if precise else Qt.MouseEventNotSynthesized,
                                touchpad if precise else QPointingDevice.primaryPointingDevice())
            event.setTimestamp(int(time.monotonic() * 1000))
            QGuiApplication.sendEvent(self.window, event)

        send(-120)
        animated = self.window.property("speed") > 1 / 200
        if animated:
            self.assertAlmostEqual(nav.property("contentY"), 0, delta=1)
        else:
            self.assertAlmostEqual(nav.property("contentY"), 96, delta=1)
        send(-120)
        self.wait_for(lambda: abs(nav.property("contentY") - 192) < 1)
        QTest.qWait(170)

        if animated:
            send(-120)
            send(120)
            self.wait_for(lambda: abs(nav.property("contentY") - 96) < 1)
            QTest.qWait(170)
        send(-120)
        position = nav.property("contentY")
        send(-30, precise=True)
        self.assertAlmostEqual(nav.property("contentY"), position + 30, delta=1)
        QTest.qWait(200)
        self.assertAlmostEqual(nav.property("contentY"), position + 30, delta=1)

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

    def test_automatic_battery_saver_is_available_from_the_keyboard(self):
        state = dict(mode="automatic", activeMode="balanced", modes=["automatic", "power-saver", "performance"],
                     hasBattery=True, batterySaverAuto=True, batterySaverThreshold=20, batteryCriticalLevel=5)
        self.helper.replies["power"] = json.dumps(state)
        self.open("power")
        self.assertTrue(self.item("powerMode-automatic").property("picked"))
        self.capture("automatic-battery-saver-on")
        row = self.item("automaticBatterySaver"); row.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(30)
        state = dict(state, batterySaverAuto=False)
        self.helper.replies.update({"power": json.dumps(state), "battery-saver": json.dumps(dict(ok=True, state=state))})
        self.helper.commands.clear(); QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: not self.window.property("powerBusy"))
        self.assertIn(["helper", "battery-saver", "off"], self.helper.commands)
        self.assertEqual(self.window.property("powerProblem"), "")
        self.assertFalse(self.item("automaticBatterySaver").property("checked"))
        self.assertFalse(self.item("batterySaverSwitch").property("active"))
        QTest.qWait(250)
        self.capture("automatic-battery-saver")

    def test_bluetooth_sleep_switches_follow_saved_choices(self):
        self.helper.replies.update({"status": '{"bluetooth":true}', "bluetooth-sleep": '{"ok":true,"mode":"off"}'})
        self.open("bluetooth")
        sleep_row = self.item("bluetoothSleepRow")
        wake_row = self.item("bluetoothWakeRow")
        self.assertTrue(sleep_row.isVisible())
        self.assertFalse(wake_row.isVisible())
        self.helper.commands.clear()
        self.helper.replies["bluetooth-sleep"] = '{"ok":true,"mode":"restore"}'
        sleep_row.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Space)
        self.wait_for(lambda: wake_row.isVisible() and wake_row.property("checked"))
        self.helper.replies["bluetooth-sleep"] = '{"ok":true,"mode":"stay-off"}'
        wake_row.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: not wake_row.property("checked"))
        self.assertTrue(sleep_row.property("checked"))
        self.open("light")
        self.open("bluetooth")
        self.assertTrue(self.item("bluetoothSleepRow").property("checked"))
        self.assertFalse(self.item("bluetoothWakeRow").property("checked"))
        self.assertEqual([command[2] for command in self.helper.commands if command[1] == "bluetooth-sleep"],
                         ["restore", "stay-off", "status"])

    def test_failed_power_change_keeps_the_confirmed_mode_and_releases_controls(self):
        state = dict(mode="automatic", activeMode="balanced", modes=["automatic", "power-saver", "performance"],
                     hasBattery=True, batterySaverAuto=True, batterySaverThreshold=20)
        self.helper.replies["power"] = json.dumps(state); self.open("power")
        self.helper.held_commands.add("power-mode")
        choice = self.item("powerMode-performance"); choice.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(self.window.property("powerBusy"))
        self.assertTrue(self.item("powerMode-automatic").property("picked"))
        self.helper.done.emit(self.helper.pending_commands[-1], json.dumps(dict(ok=False, state=state)), 1, "")
        QTest.qWait(50)
        self.assertFalse(self.window.property("powerBusy"))
        self.assertNotEqual(self.window.property("powerProblem"), "")
        self.assertTrue(self.item("powerMode-automatic").property("picked"))

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

    def test_storage_details_scan_is_on_demand_and_escape_closes_the_dialog(self):
        self.helper.replies['storage-details'] = json.dumps(dict(ok=True, unused=[], unusedKnown=True,
            oldDownloads=[], cacheSize=1024, cache='file:///private/cache', downloads='file:///private/Downloads'))
        self.open('storage')
        self.assertFalse(any(c[1] == 'storage-details' for c in self.helper.commands))
        button = self.item('moreStorageSettings'); button.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: any(c[1] == 'storage-details' for c in self.helper.commands))
        view = self.item('storageDetailsView')
        self.assertTrue(view.isVisible())
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(200)
        self.assertFalse(view.isVisible())

    def test_storage_cleanup_needs_review_and_failure_keeps_candidates(self):
        self.helper.replies['storage-details'] = json.dumps(dict(ok=True, unusedKnown=True, token='reviewed',
            unused=[dict(name='Old support files', ref='runtime/org.example.Platform/x86_64/1', size=1024)], oldDownloads=[]))
        self.helper.replies['storage-unused-clean'] = '{"ok":false}'
        self.open('storage')
        self.item('moreStorageSettings').forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(200)
        self.assertFalse(any(c[1] == 'storage-unused-clean' for c in self.helper.commands))
        review = self.item('storageUnusedReview')
        review.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(40)
        confirm = self.item('storageUnusedConfirm'); self.assertTrue(confirm.property('visible'))
        confirm.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Space)
        self.wait_for(lambda: ['helper','storage-unused-clean','reviewed'] in self.helper.commands)
        QTest.qWait(40)
        view = self.item('storageDetailsView')
        self.assertEqual(len(view.property('info').toVariant()['unused']), 1)
        self.assertNotEqual(view.property('message'), '')
