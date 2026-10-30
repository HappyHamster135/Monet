"""Everyday phrases, safe navigation, and the actual Settings search controls."""
import importlib.machinery
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


class EverydaySearch(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()

    def test_everyday_phrases_reach_the_intended_destinations(self):
        for query, target in (("make text bigger", "accessibility#size"),
                              ("headphones", "sound#output"),
                              ("birthday", "calendar"),
                              ("Windows files", "storage#shared-files"),
                              ("how can I make bigger text?", "accessibility#size"),
                              ("pair headphones", "bluetooth"), ("Wi-Fi", "wifi"),
                              ("restore browser tabs", "windows#return")):
            with self.subTest(query=query):
                self.assertEqual(self.q.everyday_search(query)[0]["target"], target)

    def test_translated_aliases_accent_folding_and_english_fallback(self):
        alias = next(e["terms"] for e in self.q.search_catalog() if e["id"] == "text-size")
        with patch.object(self.q, "_", side_effect=lambda s: "gör text större; större text" if s == alias else s):
            for query in ("GÖR TEXT STÖRRE", "gor text storre", "make text bigger"):
                self.assertEqual(self.q.everyday_search(query)[0]["id"], "text-size")

    def test_queries_do_not_execute_commands_or_return_unrelated_actions(self):
        with patch.object(self.q.subprocess, "Popen") as popen:
            for query in ("", "i", "how can i", "banana", "'; reboot; $(touch x)"):
                self.assertEqual(self.q.everyday_search(query), [])
            for ident in ("headphones; reboot", "$(touch x)", "not-a-result"):
                self.assertFalse(self.q.open_search_result(ident))
            popen.assert_not_called()

    def test_open_uses_only_known_routes_and_calendar_widget(self):
        with patch.object(self.q, "open_settings") as settings, patch.object(self.q.subprocess, "Popen") as popen:
            self.assertTrue(self.q.open_search_result("text-size"))
            settings.assert_called_once_with("accessibility#size")
            self.assertTrue(self.q.open_search_result("calendar"))
            self.assertEqual(popen.call_args.args[0], ["plasmawindowed", "org.monet.calendar"])

    def test_clock_and_security_actions_still_reach_their_command_helper(self):
        with patch.object(self.q, "ok", return_value=True) as execute, patch.object(self.q, "emit"):
            self.q.main(["ntp", "on"])
            execute.assert_called_once_with("timedatectl", "set-ntp", "true", timeout=120)
            for action, args, timeout in (("firewall-on", [], 300), ("trust-key", [], 300),
                                          ("firewall-strict", ["on"], 120),
                                          ("firewall-allow", ["localsend", "on"], 120)):
                execute.reset_mock()
                self.q.main([action, *args])
                execute.assert_called_once_with("pkexec", f"{self.q.LIBEXECDIR}/monet-secure", action, *args, timeout=timeout)

    def test_familiar_names_reach_installed_apps_and_settings(self):
        with patch.object(self.q, "entry_by_id", return_value={"Type": "Application", "Exec": "fixture"}):
            for query, target in (("Finder", "org.kde.dolphin.desktop"),
                                  ("where is the file explorer", "org.kde.dolphin.desktop"),
                                  ("Nautilus", "org.kde.dolphin.desktop"),
                                  ("open Notepad", "org.kde.kate.desktop"),
                                  ("Activity Monitor", "org.kde.plasma-systemmonitor.desktop"),
                                  ("Task Manager", "org.kde.plasma-systemmonitor.desktop"),
                                  ("Snipping Tool", "org.kde.spectacle.desktop"),
                                  ("Archive Utility", "org.kde.ark.desktop"),
                                  ("Evince", "org.kde.okular.desktop"),
                                  ("GNOME Software", "monet-store.desktop"),
                                  ("System Preferences", "welcome"),
                                  ("File History", "backups")):
                with self.subTest(query=query):
                    self.assertEqual(self.q.everyday_search(query)[0]["target"], target)

    def test_hidden_removed_and_unavailable_apps_are_not_offered_or_opened(self):
        with tempfile.TemporaryDirectory() as temporary:
            local, system = Path(temporary) / "local", Path(temporary) / "system"
            local.mkdir(); system.mkdir()
            desktop = "[Desktop Entry]\nType=Application\nName=Files\nExec=dolphin\n"
            (system / "org.kde.dolphin.desktop").write_text(desktop)
            with patch.object(self.q, "app_dirs", return_value=(local, system)), patch.object(self.q, "launch") as launch:
                self.assertEqual(self.q.everyday_search("Finder")[0]["id"], "files")
                for override in ("Hidden=true", "NoDisplay=true", "Type=Link", "TryExec=nonexistent-fixture-app"):
                    (local / "org.kde.dolphin.desktop").write_text("[Desktop Entry]\n" + override + "\nType=Application\nExec=dolphin\n")
                    self.assertEqual(self.q.everyday_search("Finder"), [])
                    self.assertFalse(self.q.open_search_result("files"))
                (local / "org.kde.dolphin.desktop").unlink()
                (system / "org.kde.dolphin.desktop").unlink()
                self.assertEqual(self.q.everyday_search("Finder"), [])
                launch.assert_not_called()

    def test_app_result_launches_its_known_entry_and_reports_failure(self):
        with patch.object(self.q, "entry_by_id", return_value={"Type": "Application", "Exec": "fixture"}), \
                patch.object(self.q, "launch", return_value=True) as launch, patch.object(self.q, "open_settings") as settings:
            self.assertTrue(self.q.open_search_result("files"))
            launch.assert_called_once_with("org.kde.dolphin.desktop")
            settings.assert_not_called()
            launch.return_value = False
            self.assertFalse(self.q.open_search_result("files"))

    def test_unavailable_windows_files_never_get_a_fake_open_path(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(self.q, "FILES", Path(temporary)), \
                patch.object(self.q.os, "access", return_value=True):
            for state in ("", "bitlocker", "asleep", "unclean", "failed"):
                with patch.object(self.q, "shared_state", return_value={"state": state}):
                    result = self.q.shared_files_status()
                    self.assertFalse(result["available"])
                    self.assertEqual(result["path"], "")
            with patch.object(self.q, "shared_state", return_value={"state": "open"}):
                self.assertEqual(self.q.shared_files_status()["path"], temporary)
                with patch.object(self.q.os, "access", return_value=False):
                    self.assertFalse(self.q.shared_files_status()["available"])


try:
    from PySide6.QtCore import QObject, QSettings, QStandardPaths, QTimer, QUrl, Qt, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class SearchHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)
        def __init__(self):
            super().__init__()
            self.ticket = 0; self.q = quick_helper(); self.actions = []; self.delays = {}; self.fail = False

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1; ticket = self.ticket
            verb = command[1]; delay = 5; code = 0
            if verb == "search":
                query = bytes.fromhex(command[2]).decode()
                result = {"results": self.q.everyday_search(query)}
                delay = self.delays.get(query, 30)
                if self.fail: result = {}; code = 1
            elif verb == "search-open":
                self.actions.append(command[2]); result = {"ok": not self.fail}
                code = 1 if self.fail else 0
            else:
                result = {"access": {"scale": 125, "cursor": 24, "reduced": False},
                    "display-sizes": [{"name": "eDP-1", "scale": 125, "width": 1920, "height": 1080, "highDensity": False}],
                    "status": {"volume": 50, "mic": 80}, "outputs": [{"name": "Speakers", "id": "1", "default": True}],
                    "shared-files": {"state": "asleep", "available": False, "path": ""},
                    "apps-sound": [], "bt-list": [], "wifi-list": [], "defaults": []}.get(verb, {})
            output = json.dumps(result)
            QTimer.singleShot(delay, lambda: self.done.emit(ticket, output, code, ""))
            return ticket


@unittest.skipUnless(QT, "Qt/Kirigami runtime")
class SettingsSearchUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.identity = (cls.app.organizationName(), cls.app.organizationDomain(), cls.app.applicationName())
        cls.config = tempfile.TemporaryDirectory()
        cls.app.setOrganizationName("monet-search-tests"); cls.app.setOrganizationDomain("tests.invalid")
        cls.app.setApplicationName("settings")
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, cls.config.name)
        loader = importlib.machinery.SourceFileLoader("search_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    @classmethod
    def tearDownClass(cls):
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation))
        cls.app.setOrganizationName(cls.identity[0]); cls.app.setOrganizationDomain(cls.identity[1]); cls.app.setApplicationName(cls.identity[2])
        cls.config.cleanup()

    def setUp(self):
        self.engine = QQmlApplicationEngine(); self.helper = SearchHelper(); self.words = self.games.Words()
        self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "light", "blurBehind": False,
            "pictures": (ROOT / "linux/share/monet/settings").as_uri() + "/",
            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]; QTest.qWait(80)
        self.search = self.item("settingsSearch")

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(5)
        self.assertEqual(self.errors, [])

    def item(self, name):
        todo = [self.window.contentItem()]
        while todo:
            current = todo.pop()
            if current.objectName() == name: return current
            todo.extend(current.childItems())
        self.fail(name + " missing")

    def type_query(self, text):
        self.search.setProperty("text", text)
        self.search.forceActiveFocus()

    def test_enter_before_results_arrive_opens_and_focuses_the_correct_control(self):
        self.type_query("make text bigger")
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(240)
        self.assertEqual(self.window.property("page"), "accessibility")
        self.assertTrue(self.item("search-size").hasActiveFocus())

    def test_old_search_response_cannot_replace_a_newer_query(self):
        self.helper.delays = {"birthday": 450, "headphones": 20}
        self.type_query("birthday"); QTest.qWait(180)
        self.type_query("headphones"); QTest.qWait(600)
        self.assertEqual(self.window.property("searchResults").toVariant()[0]["id"], "headphones")
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("searchResult-headphones").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(150)
        self.assertEqual(self.window.property("page"), "sound")
        self.assertTrue(self.item("search-output").hasActiveFocus())

    def test_calendar_opens_without_saving_or_changing_any_notes(self):
        self.type_query("birthday")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(100)
        self.assertEqual(self.helper.actions, ["calendar"])
        self.assertEqual(self.window.property("page"), "light")

    def test_windows_files_shows_unavailable_state_and_the_access_control(self):
        self.type_query("Windows files")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(250)
        self.assertEqual(self.window.property("page"), "storage")
        row = self.item("search-shared-files")
        self.assertTrue(row.hasActiveFocus())
        self.assertIn("Shut down Windows completely", row.property("detail"))

    def test_size_controls_do_not_squeeze_or_overlap_text_in_a_narrow_window(self):
        self.window.setWidth(760)
        self.type_query("make text bigger")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(250)
        row = self.item("screenSizeRow-eDP-1")
        help_text = self.item("displaySizeHelp")
        self.assertGreater(help_text.property("lineCount"), 1)
        self.assertLessEqual(help_text.width(), row.width())
        parts = {child.objectName(): child for child in row.childItems()}
        label, controls = parts["settingRowText"], parts["settingRowControls"]
        self.assertGreater(label.width(), 250)
        self.assertGreaterEqual(controls.y(), label.y() + label.height())
        self.assertGreaterEqual(controls.x(), 0)
        self.assertLessEqual(controls.x() + controls.width(), row.width())
        self.assertLessEqual(controls.y() + controls.height(), row.height() - 10)
        # Growing and shrinking the window must clear the previous alignment.
        for width in (1100, 760, 1100):
            self.window.setWidth(width); QTest.qWait(50)
            self.assertGreaterEqual(label.y(), 10)
            self.assertGreaterEqual(controls.y(), 10)
            self.assertLessEqual(label.y() + label.height(), row.height() - 10)
            self.assertLessEqual(controls.y() + controls.height(), row.height() - 10)

    def test_short_controls_remain_centered_and_inside_the_row(self):
        self.window.setWidth(760)
        self.type_query("Windows files")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(250)
        row = self.item("search-shared-files")
        self.assertFalse(row.property("stacked"))
        parts = {child.objectName(): child for child in row.childItems()}
        for name in ("settingRowText", "settingRowControls"):
            child = parts[name]
            self.assertAlmostEqual(child.y() + child.height()/2, row.height()/2, delta=1)

    def test_absent_audio_hardware_still_has_a_visible_search_destination(self):
        self.type_query("headphones")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(250)
        self.window.setProperty("outputs", [])
        self.window.setProperty("info", {})
        QTest.qWait(50)
        for name in ("search-output", "search-microphone"):
            row = self.item(name)
            self.assertTrue(row.isVisible())
            self.assertGreater(row.height(), 30)

    def test_failed_search_can_be_retried_and_escape_clears_results(self):
        self.helper.fail = True
        self.type_query("headphones")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(80)
        self.assertTrue(self.window.property("searchProblem"))
        self.helper.fail = False
        # Enter retries the same query after failure.
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(180)
        self.assertFalse(self.window.property("searchProblem"))
        self.assertEqual(self.window.property("page"), "sound")
        self.type_query("headphone"); QTest.qWait(210)
        self.assertTrue(self.window.property("searchResults").toVariant())
        self.assertTrue(self.search.hasActiveFocus(), self.window.activeFocusItem().objectName())
        QTest.keyClick(self.window, Qt.Key_Escape); QTest.qWait(180)
        self.assertEqual(self.search.property("text"), "")
        self.assertEqual(self.window.property("searchResults").toVariant(), [])

    def test_app_result_uses_launcher_and_failed_launch_stays_visible(self):
        with patch.object(self.helper.q, "entry_by_id", return_value={"Type": "Application", "Exec": "fixture"}):
            self.type_query("Finder")
            QTest.qWait(250)
            previous = self.window.property("page")
            self.helper.fail = True
            QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(100)
            self.assertEqual(self.helper.actions, ["files"])
            self.assertEqual(self.window.property("page"), previous)
            self.assertTrue(self.window.property("searchProblem"))
            self.helper.fail = False
            QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(100)
            self.assertEqual(self.helper.actions, ["files", "files"])
            self.assertFalse(self.window.property("searchProblem"))


@unittest.skipUnless(QT, "Qt/Plasma runtime")
class MenuSearchUI(unittest.TestCase):
    """The real menu representation, with inert app models and a controllable helper.

    Search/list keyboard handlers and layout are loaded unchanged. Only external
    services are replaced, so testing Enter can never launch a real application.
    """
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        directory = ROOT / "linux/share/plasma/plasmoids/org.monet.menu/contents/ui"
        source = (directory / "main.qml").read_text()
        imports = source[source.index("import QtQuick"):source.index("PlasmoidItem {")]
        representation = source.split("    fullRepresentation: ", 1)[1].rsplit("\n}", 1)[0]
        functions = "\n".join(re.search(r"    (function " + name + r"\(.*?\n    })", source, re.S).group(1)
                              for name in ("findEveryday", "runEveryday", "launchEveryday"))
        receiver = re.search(r"onNewData: (\(source, data\) => \{.*?\n        })", source, re.S).group(1)
        qml = imports + '''
import QtQuick.Window
Window {
    id: window; width: 560; height: 420; visible: true
    Item {
        id: root; anchors.fill: parent
        property real speed: 0
        property string firstName: "Test"
        property bool expanded: true
        property var everydayResults: []
        property string everydaySource: ""
        property string everydayQuery: ""
        property bool everydayPending: false
        property string everydayError: ""
        property string openingResult: ""
        property string launched: ""
        property var sent: []
        property var appendResult: function(row) { nativeResults.append(row) }
        signal everydayReady()
        function i18n(text) { return text }
        function i18nc(context, text) { return text }
        function launch(model, index) { launched = "native-" + index }
        function showAppMenu(item, id) {}
        property var everyApp: empty
        property var recent: empty
        property var apps: QtObject {
            property var favoritesModel: empty
            function refresh() {}
        }
        property var finder: QtObject {
            objectName: "testFinder"
            property string query: ""
            property int count: 1
            property bool querying: false
            signal queryFinished()
            function modelForRow(row) { return nativeResults }
        }
        ListModel { id: empty }
        ListModel { id: nativeResults
            objectName: "testNativeResults"
            Component.onCompleted: {
                for (let i = 0; i < 20; i++) append({display: "Native result " + i, description: "Folder", decoration: "folder", favoriteId: ""})
            }
        }
        QtObject { id: user; property string fullName: "Test"; property string loginName: "test"; property string faceIconUrl: "" }
        QtObject { id: sessions; property bool canLock: false }
        QtObject {
            id: helper
            function connectSource(source) { root.sent = root.sent.concat([source]) }
            function disconnectSource(source) {}
        }
        Timer { id: everydayDelay; interval: 140; onTriggered: root.runEveryday() }
        function disconnectSource(source) {}
        property var complete: RECEIVER
        FUNCTIONS
        REPRESENTATION
    }
}
'''.replace("RECEIVER", receiver).replace("FUNCTIONS", functions).replace("REPRESENTATION", representation)
        # Give the real representation the same available area as the shell.
        qml = qml.replace("id: page", 'id: page; objectName: "testPage"; anchors.fill: parent')
        qml = qml.replace("id: root;", 'id: root; objectName: "testRoot";')
        qml = qml.replace("id: results", 'id: results; objectName: "testResults"')
        self.engine = QQmlApplicationEngine(); self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        # loadData holds Python's GIL while the QML loader thread initializes
        # Kirigami on some PySide builds. Loading a saved fixture avoids that.
        self.fixture = tempfile.TemporaryDirectory()
        path = Path(self.fixture.name) / "SearchTest.qml"
        path.write_text('import "' + directory.as_uri() + '"\n' + qml)
        self.engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]; QTest.qWait(100)
        self.root = self.item("testRoot"); self.search = self.item("menuSearch")
        self.page = self.item("testPage"); self.results = self.item("testResults")
        self.native = self.root.findChild(QObject, "testNativeResults")
        self.finder = self.root.findChild(QObject, "testFinder")

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(5)
        self.fixture.cleanup()
        self.assertEqual(self.errors, [])

    item = SettingsSearchUI.item

    def deliver(self, source, results=None, code=0):
        payload = {"stdout": json.dumps({"results": results or []}), "exit code": code}
        result = self.root.property("complete").call([self.engine.toScriptValue(source), self.engine.toScriptValue(payload)])
        self.assertFalse(result.isError(), result.toString())
        QTest.qWait(30)

    def query(self, text="headphones"):
        self.search.setProperty("text", text); self.search.forceActiveFocus()
        QTest.qWait(170)
        return self.root.property("everydaySource")

    def test_delayed_suggestions_are_visible_without_moving_keyboard_focus(self):
        for query in ("headphones", "birthday", "headphones"):
            source = self.query(query)
            suggestions = quick_helper().everyday_search(query)
            self.deliver(source, suggestions)
            row = self.item("menuSearchResult-" + suggestions[0]["id"])
            y = row.mapToItem(self.results, 0, 0).y()
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y + row.height(), self.results.height())
            self.assertTrue(self.search.hasActiveFocus())

    def test_focus_returns_to_visible_suggestions_after_scrolling_native_results(self):
        source = self.query()
        self.deliver(source, quick_helper().everyday_search("headphones"))
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("menuSearchResult-headphones").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("menuSearchResult-bluetooth").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.results.hasActiveFocus())
        for _ in range(12): QTest.keyClick(self.window, Qt.Key_Down)
        self.assertEqual(self.results.property("currentIndex"), 12,
                         (self.results.property("count"), self.window.activeFocusItem().objectName()))
        steps = []
        for _ in range(13):
            QTest.keyClick(self.window, Qt.Key_Up)
            steps.append((self.results.property("currentIndex"), self.window.activeFocusItem().objectName()))
        QTest.qWait(30)
        row = self.item("menuSearchResult-bluetooth")
        self.assertTrue(row.hasActiveFocus(), steps)
        y = row.mapToItem(self.results, 0, 0).y()
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y + row.height(), self.results.height())
        QTest.keyClick(self.window, Qt.Key_Up)
        self.assertTrue(self.item("menuSearchResult-headphones").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(self.root.property("openingResult").endswith("search-open headphones"))

    def test_enter_waits_for_suggestions_and_stale_responses_cannot_launch(self):
        old = self.query("birthday")
        QTest.keyClick(self.window, Qt.Key_Return)
        new = self.query("headphones")
        self.deliver(old, quick_helper().everyday_search("birthday"))
        self.assertEqual(self.root.property("everydayResults").toVariant(), [])
        self.assertEqual(self.root.property("openingResult"), "")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.root.property("launched"), "")
        self.deliver(new, quick_helper().everyday_search("headphones"))
        self.assertTrue(self.root.property("openingResult").endswith("search-open headphones"))

    def test_failed_suggestions_do_not_launch_an_unrelated_native_result(self):
        source = self.query()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.deliver(source, code=1)
        self.assertTrue(self.root.property("everydayError"))
        self.assertEqual(self.root.property("launched"), "")
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(170)
        self.assertTrue(self.root.property("everydayPending"))
        self.deliver(self.root.property("everydaySource"), quick_helper().everyday_search("headphones"))
        self.assertTrue(self.root.property("openingResult").endswith("search-open headphones"))

    def add_app(self, name="ChatGPT", ident="applications:chatgpt.desktop"):
        # The folder deliberately ranks ahead of the application in KRunner.
        row = {"display": name, "description": "Application", "decoration": "system-run", "favoriteId": ident}
        self.root.property("appendResult").call([self.engine.toScriptValue(row)])
        QTest.qWait(20)

    def test_application_precedes_same_name_folder_and_launches_source_row(self):
        self.query("chatgpt")
        self.add_app()
        self.assertEqual(self.results.property("count"), 20)  # no duplicate app among files
        app = self.item("menuApplicationResult-0")
        self.assertEqual(app.property("name"), "ChatGPT")
        self.assertTrue(app.property("current"))
        self.assertGreaterEqual(app.mapToItem(self.results, 0, 0).y(), 0)
        # An app can open without waiting for the unrelated suggestions helper.
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.root.property("launched"), "native-20")
        self.assertEqual(self.root.property("openingResult"), "")

    def test_windows_apps_and_keyboard_cross_all_sections(self):
        source = self.query("chatgpt")
        self.add_app("ChatGPT.exe", "applications:wine-chatgpt.desktop")
        self.add_app("ChatGPT tools")
        self.deliver(source, quick_helper().everyday_search("headphones"))
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("menuApplicationResult-0").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("menuApplicationResult-1").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertTrue(self.item("menuSearchResult-headphones").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Up)
        self.assertTrue(self.item("menuApplicationResult-1").hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.root.property("launched"), "native-21")

    def test_early_enter_waits_for_app_query_and_changed_query_cancels_launch(self):
        self.query("chatgpt")
        self.add_app()
        self.finder.setProperty("querying", True)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.root.property("launched"), "")
        self.query("different")
        self.finder.setProperty("querying", False)
        self.finder.queryFinished.emit()
        self.assertEqual(self.root.property("launched"), "")
        self.finder.setProperty("querying", True)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.finder.setProperty("querying", False)
        self.finder.queryFinished.emit()
        QTest.qWait(20)
        self.assertEqual(self.root.property("launched"), "native-20")

    def test_no_application_keeps_folder_launch_mapping(self):
        source = self.query("folder")
        self.deliver(source)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.root.property("launched"), "native-0")
