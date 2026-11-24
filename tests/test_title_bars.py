"""Title bars that appear when you point at the top (0.9.8-7): Monet Titles, a KWin script
(share/kwin/scripts/monet-titles), the bare frame it goes with (tools/make-decoration.py), and
the Settings switch that turns both off.

The script runs here as it is, against a stand-in for KWin's scripting API (org.kde.kwin:
Workspace, KWin, Options, as KWin 6.8 has them) with windows described the way KWin describes
them. Only the Monet VM has a real KWin and a pointer to point with.
"""
import configparser
import json
from pathlib import Path
import re
import shutil
import tempfile
from tests.settings_support import settings_source
import unittest
import xml.etree.ElementTree as ET

from tests.test_look import FakeKDE, quick_helper, tempfile_dir

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "linux/share"
SCRIPT = SHARE / "kwin/scripts/monet-titles"
UI = SCRIPT / "contents/ui"
SETTINGS_QML = SHARE / "monet/settings-app/MonetSettings.qml"
try:
    from PySide6.QtCore import QObject, QPoint, QUrl, Qt, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine, QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


def hover_js():
    """hover.js as QML loads it, without the line that makes it a QML library."""
    source = (UI / "hover.js").read_text(encoding="utf-8")
    first, rest = source.split("\n", 1)
    assert first == ".pragma library"
    return rest


@unittest.skipUnless(QT, "requires PySide6")
class Arithmetic(unittest.TestCase):
    """hover.js: where the pointer brings a bar, which windows get one, where it goes."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.js = QJSEngine()
        result = self.js.evaluate(hover_js())
        self.assertFalse(result.isError(), result.toString())

    def run_js(self, expression):
        result = self.js.evaluate("JSON.stringify(" + expression + ")")
        self.assertFalse(result.isError(), result.toString())
        return json.loads(result.toString())

    def window(self, **kw):
        w = dict(deleted=False, managed=True, minimized=False, hidden=False, fullScreen=False, normalWindow=True,
                 dialog=False, utility=False, specialWindow=False, popupWindow=False, outline=False,
                 decorationHasAlpha=True, frameGeometry=dict(x=100, y=100, width=800, height=600),
                 clientGeometry=dict(x=100, y=100, width=800, height=600))
        w.update(kw)
        return json.dumps(w)

    def test_top_center_panel_leaves_room_for_the_title_buttons(self):
        result = self.js.evaluate("""
            var screen={x:100,y:50,width:1000,height:700};
            var dock={dock:true,frameGeometry:{x:550,y:50,width:100,height:32}};
            var bar=barRect(screen,screen,[dock]);
            bar.y===83 && bar.height===40 && !touches(dock.frameGeometry,bar)
                && barRect({x:100,y:130,width:500,height:400},screen,[dock]).y===130
        """)
        self.assertTrue(result.toBool(), result.toString())

    def test_the_bar_lies_over_the_windows_top_at_every_scale(self):
        screen = "rect(0, 0, 1920, 1080)"
        self.assertEqual(self.run_js(f"barRect(rect(100, 100, 800, 600), {screen})"),
                         dict(x=100, y=100, width=800, height=40))
        # Fractional scales give fractional logical geometry: the bar keeps to whole pixels,
        # never wider than the window. KWin draws it at the screen's scale (logical pixels).
        self.assertEqual(self.run_js(f"barRect(rect(100.4, 99.6, 800.2, 600), {screen})"),
                         dict(x=100, y=100, width=801, height=40))
        # A short window: never taller than it.
        self.assertEqual(self.run_js(f"barRect(rect(0, 0, 300, 24), {screen})")["height"], 24)
        # Reaching above its screen: at the screen's top, where it can be seen.
        self.assertEqual(self.run_js(f"barRect(rect(100, -50, 800, 600), {screen})")["y"], 0)
        # A second screen at 200% to the right is in logical pixels too.
        self.assertEqual(self.run_js("barRect(rect(1920, 0, 960, 540), rect(1920, 0, 960, 540))"),
                         dict(x=1920, y=0, width=960, height=40))
        self.assertEqual(self.run_js("BAR"), 40)

    def test_pointer_motion_in_app_content_never_scans_the_window_stack(self):
        self.js.evaluate('''
            var target = {clientGeometry:rect(100,100,800,600), output:{geometry:rect(0,0,1920,1080)}};
            var scans = 0;
            function pick(p) { return target; }
            function eligible(w) { ++scans; return true; }
            for (var i=0; i<10000; ++i) aimedAt({x:200+i%600,y:300},pick,eligible);
        ''')
        self.assertEqual(self.run_js('scans'), 0)
        self.assertTrue(self.run_js('aimedAt({x:200,y:105},pick,eligible) === target'))
        self.assertEqual(self.run_js('scans'), 1)
        self.assertIsNone(self.run_js('aimedAt({x:200,y:105},pick,w=>false)'))

    def test_overshooting_a_window_top_still_checks_occlusion(self):
        self.js.evaluate('''
            var target = {clientGeometry:rect(100,100,800,600), output:{geometry:rect(0,0,1920,1080)}};
            var scans = 0;
            function pick(p) { return p.y < 100 ? {desktopWindow:true} : target; }
            function eligible(w) { ++scans; return true; }
        ''')
        self.assertTrue(self.run_js('aimedAt({x:200,y:96},pick,eligible) === target'))
        self.assertEqual(self.run_js('scans'), 1)

    def test_the_pointer_brings_it_only_at_the_very_top(self):
        screen = "rect(0, 0, 1920, 1080)"
        client = "rect(100, 100, 800, 600)"
        at = lambda x, y: self.run_js(f"atTop({client}, {screen}, {{x: {x}, y: {y}}})")
        self.assertTrue(at(500, 100))
        self.assertTrue(at(500, 117))   # a wider band on a floating window
        self.assertFalse(at(500, 118))
        self.assertTrue(at(500, 93))     # just above the floating window
        self.assertFalse(at(500, 92))
        self.assertFalse(at(99, 101))    # beside it
        self.assertFalse(at(900, 101))
        # Filling the screen: the screen's top edge, where the pointer stops by itself.
        self.assertTrue(self.run_js(f"atTop(rect(0, 0, 1920, 1040), {screen}, {{x: 960, y: 0}})"))
        self.assertFalse(self.run_js(f"atTop(rect(0, 0, 1920, 1040), {screen}, {{x: 960, y: 6}})"))
        # Under a panel kept at the top, the window's top is the panel's bottom.
        self.assertTrue(self.run_js(f"atTop(rect(0, 44, 1920, 996), {screen}, {{x: 960, y: 44}})"))
        self.assertFalse(self.run_js(f"atTop(rect(0, 44, 1920, 996), {screen}, {{x: 960, y: 0}})"))

    def test_it_stays_while_the_pointer_is_on_it(self):
        bar = "rect(100, 100, 800, 40)"
        on = lambda x, y: self.run_js(f"onBar({bar}, {{x: {x}, y: {y}}})")
        self.assertTrue(on(500, 139))
        self.assertTrue(on(500, 143))    # only just off it
        self.assertFalse(on(500, 145))
        self.assertTrue(on(899, 120))
        self.assertFalse(on(905, 120))

    def test_which_windows_get_one(self):
        titleless = lambda **kw: self.run_js(f"titleless({self.window(**kw)})")
        self.assertTrue(titleless())
        self.assertTrue(titleless(normalWindow=False, dialog=True))      # dialogs too
        self.assertTrue(titleless(normalWindow=False, utility=True))
        # Apps drawing their own title bar: KWin frames them not at all.
        self.assertFalse(titleless(decorationHasAlpha=False))
        # A frame with a title bar of its own (switched off, or another theme).
        self.assertFalse(titleless(frameGeometry=dict(x=100, y=64, width=800, height=636)))
        for flag in ("fullScreen", "minimized", "hidden", "deleted", "specialWindow", "popupWindow", "outline"):
            self.assertFalse(titleless(**{flag: True}), flag)
        self.assertFalse(titleless(managed=False))
        self.assertFalse(titleless(normalWindow=False))                  # docks, the desktop, menus
        self.assertFalse(self.run_js("titleless(null)"))

    def test_nothing_is_covered(self):
        bar = "rect(100, 100, 800, 40)"
        js = self.js
        js.evaluate("var w = {}; function other(x, y, width, height, extra) {"
                    " return Object.assign({ frameGeometry: rect(x, y, width, height), deleted: false, minimized: false,"
                    " hidden: false, dock: false, onAllDesktops: true, desktops: [] }, extra || {}) }")
        covered = lambda stacking: self.run_js(f"covered(w, {bar}, {stacking}, 'one', null)")
        self.assertFalse(covered("[w]"))
        self.assertTrue(covered("[w, other(500, 80, 300, 300)]"))           # a window above it
        self.assertFalse(covered("[other(500, 80, 300, 300), w]"))          # one below
        self.assertFalse(covered("[w, other(500, 140, 300, 300)]"))         # only meets the bar's bottom
        self.assertFalse(covered("[w, other(500, 80, 300, 300, { minimized: true })]"))
        self.assertFalse(covered("[w, other(500, 80, 300, 300, { onAllDesktops: false, desktops: ['two'] })]"))
        # A panel along that edge, hidden away or not, above or below.
        self.assertTrue(covered("[other(0, 60, 1920, 40, { dock: true, hidden: true }), w]"))
        self.assertFalse(covered("[w, other(0, 1004, 1920, 76, { dock: true })]"))  # Monet's bar, at the bottom
        # The bar's own window doesn't count.
        preview = 'other(0, 0, 1920, 1080, {pid:-1,resourceClass:"",captionNormal:"Monet snap preview"})'
        self.assertFalse(covered(f"[w, {preview}]"))
        # Ordinary clients and the open, interactive layout picker still cover the controls.
        self.assertTrue(covered(f"[w, {preview.replace('pid:-1', 'pid:42')}]"))
        self.assertTrue(covered(f"[w, {preview.replace('Monet snap preview', '')}]"))
        self.assertFalse(self.run_js(f"covered(w, {bar}, [w, other(100, 100, 800, 40)], 'one', o => true)"))

    def test_buttons_are_the_frames_own(self):
        art = lambda *a: self.run_js("art('file:///s/', " + ", ".join(json.dumps(x) for x in a) + ")")
        self.assertEqual(art(False, "close", False, False, True), "file:///s/Monet-close-active.svg")
        self.assertEqual(art(True, "close", False, True, True), "file:///s/MonetSmoke-close-hover.svg")
        self.assertEqual(art(False, "maximize", True, True, False), "file:///s/Monet-maximize-pressed.svg")
        self.assertEqual(art(True, "restore", False, False, False), "file:///s/MonetSmoke-restore-inactive.svg")
        for light in ("Monet", "MonetSmoke"):
            for kind in ("minimize", "maximize", "restore", "close"):
                for state in ("active", "inactive", "hover", "pressed"):
                    self.assertTrue((SHARE / "monet/window-buttons" / f"{light}-{kind}-{state}.svg").is_file())
        self.assertTrue(self.run_js("filling(3)"))
        self.assertFalse(self.run_js("filling(1)"))


# A stand-in for KWin's scripting API: the parts Monet Titles uses, as KWin 6.8 has them.
FAKE_KWIN = {
    "qmldir": "module org.kde.kwin\nsingleton Workspace 1.0 Workspace.qml\nsingleton KWin 1.0 KWin.qml\n"
              "singleton Options 1.0 Options.qml\n",
    "KWin.qml": "pragma Singleton\nimport QtQml\nQtObject {\n    property var config: ({})\n"
                "    function readConfig(key, value) { return key in config ? config[key] : value }\n}\n",
    "Options.qml": "pragma Singleton\nimport QtQml\nQtObject { signal configChanged() }\n",
    "Workspace.qml": """pragma Singleton
import QtQml
QtObject {
    property point cursorPos: Qt.point(0, 0)
    property var stackingOrder: []
    property var activeWindow: null
    property var currentDesktop: "one"
    property var effects: []
    property var calls: []
    signal windowAdded(var window)
    signal windowRemoved(var window)
    signal windowActivated(var window)
    // The topmost windows under a point, as KWin's windowAt: on this desktop, shown, hit.
    function windowAt(p, count) {
        const found = []
        for (let i = stackingOrder.length - 1; i >= 0 && found.length < count; i--) {
            const w = stackingOrder[i]
            const g = w.frameGeometry
            if (w.deleted || w.minimized || w.hidden) continue
            if (!w.onAllDesktops && w.desktops.indexOf(currentDesktop) < 0) continue
            if (p.x >= g.x && p.x < g.x + g.width && p.y >= g.y && p.y < g.y + g.height) found.push(w)
        }
        return found
    }
    function isEffectActive(name) { return effects.indexOf(name) >= 0 }
    function slotWindowMove() { calls = calls.concat(["move " + (activeWindow ? activeWindow.caption : "")]) }
    function slotWindowOperations() { calls = calls.concat(["menu " + (activeWindow ? activeWindow.caption : "")]) }
}
""",
}

SCENE = """import QtQuick
import org.kde.kwin

Item {
    id: scene
    property var titles: titlesLoader.item
    // An X11 app's window turns active only once it takes the focus, a moment after it's asked.
    property bool holdBack: false
    property var mouseDrags: []
    property QtObject mouseBridge: QtObject {
        function beginMove(window, press, bar) {
            scene.mouseDrags = scene.mouseDrags.concat([window.caption]);
            window.move = true;
            return true;
        }
    }

    component FakeWindow: QtObject {
        property string caption: ""
        property var icon: ""
        property bool deleted: false
        property bool managed: true
        property bool minimized: false
        property bool hidden: false
        property bool fullScreen: false
        property bool normalWindow: true
        property bool dialog: false
        property bool utility: false
        property bool specialWindow: false
        property bool popupWindow: false
        property bool outline: false
        property bool dock: false
        property bool decorationHasAlpha: true
        property rect frameGeometry: Qt.rect(100, 100, 800, 600)
        property rect clientGeometry: frameGeometry
        property var output: ({ geometry: Qt.rect(0, 0, 1920, 1080) })
        property bool move: false
        property bool resize: false
        property bool active: Workspace.activeWindow === this
        property bool onAllDesktops: true
        property var desktops: []
        property int maximizeMode: 0
        property bool minimizable: true
        property bool maximizable: true
        property bool closeable: true
        property var log: []
        signal closed()
        signal interactiveMoveResizeFinished()
        function setMaximize(v, h) { log = log.concat(["maximize " + v + " " + h]); maximizeMode = v && h ? 3 : 0 }
        function closeWindow() { log = log.concat(["close"]) }
    }

    property var app: FakeWindow { caption: "Files" }
    property var gtk: FakeWindow { caption: "GTK app"; decorationHasAlpha: false; frameGeometry: Qt.rect(1000, 100, 600, 400) }
    property var titled: FakeWindow {
        caption: "Titled"; frameGeometry: Qt.rect(1000, 600, 600, 400); clientGeometry: Qt.rect(1000, 636, 600, 364)
    }
    property var full: FakeWindow { caption: "Game"; fullScreen: true; frameGeometry: Qt.rect(0, 0, 1920, 1080) }
    property var filled: FakeWindow { caption: "Filled"; frameGeometry: Qt.rect(0, 0, 1920, 1040); maximizeMode: 3 }
    property var popup: FakeWindow { caption: "menu"; normalWindow: false; popupWindow: true; frameGeometry: Qt.rect(300, 90, 200, 200) }
    property var topPanel: FakeWindow { caption: "panel"; normalWindow: false; dock: true; specialWindow: true; hidden: true;
                                        frameGeometry: Qt.rect(0, 0, 1920, 44) }

    Loader {
        id: titlesLoader
        source: "TITLES"
    }
}
"""


if QT:
    class Words(QObject):
        """KDE's i18nd, as KWin gives its scripts: the English words here."""

        @Slot(str, str, result=str)
        def i18nd(self, domain, text):
            return text


@unittest.skipUnless(QT, "requires PySide6")
class Behaviour(unittest.TestCase):
    """The script itself, against the stand-in for KWin."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        kwin = folder / "imports/org/kde/kwin"
        kwin.mkdir(parents=True)
        for name, text in FAKE_KWIN.items():
            (kwin / name).write_text(text, encoding="utf-8")
        # The script as install.sh lays it out, with Monet's files where it says.
        ui = folder / "monet-titles/contents/ui"
        shutil.copytree(UI, ui)
        for qml in ui.glob("*.qml"):
            qml.write_text(qml.read_text(encoding="utf-8").replace("@DATADIR@", SHARE.as_posix()), encoding="utf-8")
        scene = folder / "scene.qml"
        scene.write_text(SCENE.replace("TITLES", QUrl.fromLocalFile(str(ui / "main.qml")).toString()), encoding="utf-8")
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(folder / "imports"))
        self.errors = []
        self.engine.warnings.connect(lambda warnings: self.errors.extend(w.toString() for w in warnings))
        self.words = Words()
        self.engine.rootContext().setContextObject(self.words)
        self.engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(self.engine.rootObjects(), "\n".join(self.errors))
        self.scene = self.engine.rootObjects()[0]
        self.titles = self.scene.property("titles")
        if self.titles is None and any('"org.kde.kirigami" is not installed' in e for e in self.errors):
            self.skipTest("requires Kirigami (the Monet VM has it)")
        self.assertIsNotNone(self.titles, "\n".join(self.errors))
        self.bar = self.titles.findChild(QQuickWindow)
        self.assertIsNotNone(self.bar)
        self.addCleanup(self.engine.deleteLater)
        self.addCleanup(self.bar.close)

    def js(self, expression, scope=None):
        """Evaluate in the scene, with Workspace and the windows at hand."""
        from PySide6.QtQml import QJSValue, QQmlExpression
        expr = QQmlExpression(self.engine.contextForObject(self.scene), scope or self.scene, expression)
        value, _ = expr.evaluate()
        self.assertFalse(expr.hasError(), expr.error().toString())
        return value.toVariant() if isinstance(value, QJSValue) else value

    def stack(self, *names):
        self.js("Workspace.stackingOrder = [" + ", ".join("scene." + n for n in names) + "]")

    def point(self, x, y, wait=0):
        self.js(f"Workspace.cursorPos = Qt.point({x}, {y})")
        QTest.qWait(wait)

    def shown_for(self):
        if not self.bar.isVisible() or not self.bar.property("open"):
            return None
        window = self.bar.property("window")
        return window.property("caption") if window is not None else ""

    def test_pointing_at_the_top_brings_the_bar_over_the_window(self):
        self.stack("app")
        self.point(500, 400, 300)
        self.assertIsNone(self.shown_for())
        self.point(500, 102, 400)
        self.assertEqual(self.shown_for(), "Files")
        # Over the window's top, as wide as the window: the app keeps its size and place.
        self.assertEqual((self.bar.x(), self.bar.y(), self.bar.width(), self.bar.height()), (100, 100, 800, 40))
        self.assertEqual(self.js("scene.app.frameGeometry"), self.js("Qt.rect(100, 100, 800, 600)"))
        self.assertTrue(self.bar.flags() & Qt.ToolTip)
        self.assertTrue(self.bar.flags() & Qt.WindowDoesNotAcceptFocus)
        caption = self.bar.findChild(QObject, "titleCaption")
        self.assertEqual(caption.property("text"), "Files")
        # It stays while the pointer is on it, and goes a moment after it leaves.
        self.point(500, 130, 700)
        self.assertEqual(self.shown_for(), "Files")
        self.point(500, 300, 200)
        self.assertEqual(self.shown_for(), "Files")
        QTest.qWait(700)
        self.assertIsNone(self.shown_for())
        self.assertFalse(self.bar.isVisible())
        self.assertFalse(self.errors, "\n".join(self.errors))

    def test_stationary_pointer_gets_controls_after_a_snap_overlay_closes(self):
        self.stack("filled", "popup")
        self.js("Workspace.activeWindow = scene.filled; scene.popup.frameGeometry = Qt.rect(50, 0, 400, 60)")
        self.point(150, 1, 800)
        self.assertIsNone(self.shown_for())
        self.stack("filled")
        self.js("Workspace.windowRemoved(scene.popup)")
        QTest.qWait(350)
        self.assertEqual(self.shown_for(), "Filled")

    def test_maximizing_under_a_stationary_pointer_reveals_the_controls(self):
        self.stack("app")
        self.js("Workspace.activeWindow = scene.app")
        self.point(150, 1, 400)
        self.assertIsNone(self.shown_for())
        self.js("scene.app.frameGeometry = Qt.rect(0, 0, 1920, 1080)")
        QTest.qWait(350)
        self.assertEqual(self.shown_for(), "Files")

    def test_passing_by_is_not_pointing(self):
        self.stack("app")
        self.point(500, 102, 60)
        self.point(500, 300, 500)
        self.assertIsNone(self.shown_for())

    def test_a_small_floating_window_previews_the_bar_then_can_reveal_it_again(self):
        self.stack("app")
        self.js("scene.app.frameGeometry = Qt.rect(280, 300, 320, 220)")
        self.point(440, 400)
        self.js("Workspace.activeWindow = scene.app; Workspace.windowAdded(scene.app)")
        QTest.qWait(500)
        self.assertEqual(self.shown_for(), "Files")
        QTest.qWait(2100)
        self.assertFalse(self.bar.isVisible())
        # Below the old six-pixel band, still near the floating window's top.
        self.point(440, 313, 400)
        self.assertEqual(self.shown_for(), "Files")
        self.point(440, 400, 550)
        self.assertIsNone(self.shown_for())
        # A slight overshoot onto the desktop also brings the controls back.
        self.point(440, 295, 400)
        self.assertEqual(self.shown_for(), "Files")

    def test_launch_preview_respects_focus_and_stays_under_the_pointer(self):
        self.stack("app", "gtk")
        self.point(500, 300)
        self.js("Workspace.activeWindow = scene.gtk; Workspace.windowAdded(scene.app)")
        QTest.qWait(400)
        self.assertIsNone(self.shown_for())
        self.js("Workspace.activeWindow = scene.app; Workspace.windowAdded(scene.app)")
        QTest.qWait(500)
        self.assertEqual(self.shown_for(), "Files")
        self.point(500, 132, 2200)
        self.assertEqual(self.shown_for(), "Files")

    def test_only_windows_kwin_frames_without_a_title_bar(self):
        self.stack("app", "gtk", "titled", "full")
        self.point(1200, 102, 500)
        self.assertIsNone(self.shown_for())          # draws its own title bar
        self.point(1200, 601, 500)
        self.assertIsNone(self.shown_for())          # has a title bar in its frame
        self.stack("full")
        self.point(960, 0, 500)
        self.assertIsNone(self.shown_for())          # a game, full screen

    def test_filling_the_screen_it_comes_at_the_screens_top(self):
        self.stack("filled")
        self.point(960, 0, 400)
        self.assertEqual(self.shown_for(), "Filled")
        self.assertEqual((self.bar.y(), self.bar.width()), (0, 1920))
        maximize = self.bar.findChild(QObject, "titleMaximize")
        self.assertEqual(maximize.property("kind"), "restore")
        self.assertEqual(maximize.property("name"), "Restore")
        # A panel hidden at the top comes back there instead.
        self.point(960, 500, 800)
        self.stack("filled", "topPanel")
        self.point(960, 0, 400)
        self.assertIsNone(self.shown_for())

    def test_never_over_a_menu_or_another_window(self):
        self.stack("app", "popup")
        self.point(500, 102, 400)
        self.assertIsNone(self.shown_for())
        self.stack("app")
        self.point(501, 102, 400)
        self.assertEqual(self.shown_for(), "Files")
        # A menu opening over it meanwhile: it goes.
        self.stack("app", "popup")
        QTest.qWait(500)
        self.assertIsNone(self.shown_for())

    def test_kwins_views_and_the_switch_keep_it_away(self):
        self.stack("app")
        self.js("Workspace.effects = ['overview']")
        self.point(500, 102, 400)
        self.assertIsNone(self.shown_for())
        self.js("Workspace.effects = []")
        self.js("KWin.config = { Hover: false }")
        self.js("Options.configChanged()")
        self.point(501, 102, 400)
        self.assertIsNone(self.shown_for())
        self.js("KWin.config = { Hover: true }")
        self.js("Options.configChanged()")
        self.point(502, 102, 400)
        self.assertEqual(self.shown_for(), "Files")
        self.js("KWin.config = { Hover: false }")
        self.js("Options.configChanged()")
        QTest.qWait(400)
        self.assertIsNone(self.shown_for())

    def reveal(self):
        self.stack("app")
        self.point(500, 102, 400)
        self.assertEqual(self.shown_for(), "Files")

    def click(self, name):
        item = self.bar.findChild(QObject, name)
        self.assertIsNotNone(item, name)
        centre = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.bar, Qt.LeftButton, Qt.NoModifier, centre)
        QTest.qWait(50)

    def test_the_buttons_minimize_fill_and_close(self):
        self.reveal()
        for name in ("titleMinimize", "titleMaximize", "titleClose"):
            art = self.bar.findChild(QObject, "titleArt-" + self.bar.findChild(QObject, name).property("kind"))
            self.assertTrue(art.property("source").toString().endswith("-active.svg") or
                            art.property("source").toString().endswith("-inactive.svg"))
            self.assertTrue(self.js("status === Image.Ready", art), name)   # the frames' art loads
        self.click("titleMaximize")
        self.assertEqual(self.js("scene.app.log"), ["maximize true true"])
        self.click("titleMaximize")
        self.assertEqual(self.js("scene.app.log")[-1], "maximize false false")
        self.click("titleMinimize")
        self.assertTrue(self.js("scene.app.minimized"))
        self.assertIsNone(self.shown_for())
        self.js("scene.app.minimized = false")
        self.point(500, 300)
        self.reveal()
        # The top-right pixel is part of Close.
        QTest.mouseClick(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(self.bar.width() - 1, 1))
        self.assertEqual(self.js("scene.app.log")[-1], "close")
        self.assertIsNone(self.shown_for())

    def test_a_press_keeps_the_bar_until_release_and_can_be_cancelled(self):
        self.reveal()
        edge = QPoint(self.bar.width() - 1, 1)
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, edge)
        self.assertTrue(self.bar.property("held"))
        outside = QPoint(self.bar.width() - 1, self.bar.height() + 12)
        QTest.mouseMove(self.bar, outside)
        self.point(self.bar.x() + outside.x(), self.bar.y() + outside.y(), 500)
        self.assertEqual(self.shown_for(), "Files")
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, outside)
        QTest.qWait(500)
        self.assertIsNone(self.shown_for())
        self.assertEqual(self.js("scene.app.log"), [])

    def test_a_visible_fading_bar_accepts_the_first_close_click(self):
        self.reveal()
        self.js("close()", self.bar)
        self.assertTrue(self.bar.isVisible())
        self.assertFalse(self.bar.property("open"))
        QTest.mouseClick(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(self.bar.width() - 1, 1))
        self.assertEqual(self.js("scene.app.log"), ["close"])

    def test_a_visible_fading_bar_accepts_the_first_drag(self):
        self.reveal()
        self.js("close()", self.bar)
        self.assertFalse(self.bar.property("open"))
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(250, 20))
        self.assertTrue(self.bar.property("open"))
        QTest.mouseMove(self.bar, QPoint(280, 22))
        self.assertEqual(self.js("Workspace.calls"), ["move Files"])
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(280, 22))

    def test_finished_fade_leaves_no_invisible_input_window(self):
        self.reveal()
        sheet = self.bar.findChild(QObject, "titleSheet")
        intercepted = []
        def changed():
            if sheet.property("opacity") == 0:
                intercepted.append(self.bar.isVisible())
        sheet.opacityChanged.connect(changed)
        self.js("close()", self.bar)
        QTest.qWait(300)
        self.assertEqual(intercepted, [False])

    def test_a_window_moving_away_retracts_its_bar_without_pointer_movement(self):
        self.reveal()
        self.js("scene.app.frameGeometry = Qt.rect(100, 250, 800, 600)")
        QTest.qWait(650)
        self.assertIsNone(self.shown_for())
        self.assertFalse(self.bar.isVisible())

    def test_the_bar_moves_fills_and_opens_the_menu(self):
        self.reveal()
        grip = QPoint(250, 20)
        # A press brings the window forward, as a title bar's does.
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, grip)
        self.assertTrue(self.js("Workspace.activeWindow === scene.app"))
        # Dragged, KWin moves the window (only ever the active one), and the bar lets go of the press.
        QTest.mouseMove(self.bar, QPoint(280, 22))
        QTest.qWait(50)
        self.assertEqual(self.js("Workspace.calls"), ["move Files"])
        self.assertFalse(self.bar.property("held"))
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(280, 22))
        # A click without a drag moves nothing.
        QTest.mouseClick(self.bar, Qt.LeftButton, Qt.NoModifier, grip)
        QTest.qWait(400)
        self.assertEqual(self.js("Workspace.calls"), ["move Files"])
        QTest.mouseDClick(self.bar, Qt.LeftButton, Qt.NoModifier, grip)
        QTest.qWait(50)
        self.assertEqual(self.js("scene.app.log"), ["maximize true true"])
        QTest.mouseClick(self.bar, Qt.RightButton, Qt.NoModifier, grip)
        QTest.qWait(50)
        self.assertEqual(self.js("Workspace.calls"), ["move Files", "menu Files"])

    def test_an_x11_window_turns_active_a_moment_later(self):
        # KWin moves only the active window: the move waits for the app to take the focus, and
        # never moves the window that was active before.
        self.reveal()
        self.js("Workspace.activeWindow = scene.gtk")
        self.js("scene.holdBack = true")
        self.js("Workspace.activeWindowChanged.connect(function () {"
                " if (scene && scene.holdBack && Workspace.activeWindow === scene.app) Workspace.activeWindow = scene.gtk })")
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(250, 20))
        QTest.mouseMove(self.bar, QPoint(290, 20))
        QTest.qWait(30)
        self.assertEqual(self.js("Workspace.calls"), [])
        self.js("scene.holdBack = false")
        self.js("Workspace.activeWindow = scene.app")
        QTest.qWait(60)
        self.assertEqual(self.js("Workspace.calls"), ["move Files"])
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(290, 20))

    def test_native_drag_targets_the_held_window_without_waiting_for_activation(self):
        self.reveal()
        self.js("titles.mouseMove = scene.mouseBridge; Workspace.activeWindow = scene.gtk; scene.holdBack = true")
        self.js("Workspace.activeWindowChanged.connect(function () {"
                " if (scene && scene.holdBack && Workspace.activeWindow === scene.app) Workspace.activeWindow = scene.gtk })")
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(250, 20))
        QTest.mouseMove(self.bar, QPoint(280, 22))
        self.assertEqual(self.js("scene.mouseDrags"), ["Files"])
        self.assertEqual(self.js("Workspace.calls"), [])
        self.assertFalse(self.bar.property("held"))
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(280, 22))
        self.js("scene.app.move = false")

    def test_let_go_before_it_turns_active_nothing_sticks_to_the_pointer(self):
        self.reveal()
        self.js("Workspace.activeWindow = scene.gtk")
        self.js("scene.holdBack = true")
        self.js("Workspace.activeWindowChanged.connect(function () {"
                " if (scene && scene.holdBack && Workspace.activeWindow === scene.app) Workspace.activeWindow = scene.gtk })")
        QTest.mousePress(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(250, 20))
        QTest.mouseMove(self.bar, QPoint(290, 20))
        QTest.mouseRelease(self.bar, Qt.LeftButton, Qt.NoModifier, QPoint(290, 20))
        self.js("scene.holdBack = false")
        self.js("Workspace.activeWindow = scene.app")
        QTest.qWait(300)
        self.assertEqual(self.js("Workspace.calls"), [])


class Frames(unittest.TestCase):
    """The bare frame: KWin's frame with no title bar, only the shadow, for every light and glass."""
    BARE = SHARE / "aurorae/themes/MonetBare"

    def test_no_title_no_buttons_no_glass(self):
        meta = configparser.ConfigParser(interpolation=None)
        meta.read_string((self.BARE / "metadata.desktop").read_text())
        self.assertEqual(meta["Desktop Entry"]["X-KDE-PluginInfo-Name"], "MonetBare")
        rc = configparser.ConfigParser(interpolation=None)
        rc.read_string((self.BARE / "MonetBarerc").read_text())
        layout = rc["Layout"]
        # Aurorae's top border is the title's edges and the taller of title and buttons: all none,
        # filling the screen too, so the app has the whole window.
        for key in ("TitleEdgeTop", "TitleEdgeBottom", "TitleHeight", "ButtonHeight", "ButtonMarginTop",
                    "TitleEdgeTopMaximized", "TitleEdgeBottomMaximized", "ButtonMarginTopMaximized", "ButtonWidth"):
            self.assertEqual(layout[key], "0", key)
        # The shadow's room is the glass frames' own, so windows keep their size switching between them.
        glass = configparser.ConfigParser(interpolation=None)
        glass.read_string((SHARE / "aurorae/themes/Monet/Monetrc").read_text())
        for key in ("PaddingTop", "PaddingBottom", "PaddingLeft", "PaddingRight"):
            self.assertEqual(layout[key], glass["Layout"][key], key)
        # The title's words would be drawn into the shadow: in a color no one sees.
        self.assertEqual(rc["General"]["ActiveTextColor"].split(",")[3], "0")
        self.assertEqual(rc["General"]["InactiveTextColor"].split(",")[3], "0")
        self.assertEqual(sorted(p.name for p in self.BARE.iterdir()), ["MonetBarerc", "decoration.svg", "metadata.desktop"])
        svg = (self.BARE / "decoration.svg").read_text()
        ET.fromstring(svg)
        ids = set(re.findall(r'id="([^"]+)"', svg))
        pieces = ("topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright")
        for prefix in ("decoration", "decoration-inactive", "decoration-maximized", "decoration-maximized-inactive"):
            for piece in pieces:
                self.assertIn(f"{prefix}-{piece}", ids)
        # No mask: KWin then blurs nothing behind a frame that has no glass. And only pictures of
        # the shadow (no shapes of glass), each piece ending where the window begins.
        self.assertFalse(any(i.startswith("mask") for i in ids))
        self.assertNotIn("<path", svg)
        root = ET.fromstring(svg)
        ns = "{http://www.w3.org/2000/svg}"
        sizes = {g.get("id"): (float(g.find(ns + "rect").get("width")), float(g.find(ns + "rect").get("height")))
                 for g in root.iter(ns + "g")}
        self.assertEqual(sizes["decoration-topleft"], (40.0, 30.0))
        self.assertEqual(sizes["decoration-bottomright"], (40.0, 54.0))

    def test_made_by_the_frames_tool(self):
        tool = (ROOT / "tools/make-decoration.py").read_text(encoding="utf-8")
        for piece in ('BARE = "MonetBare"', "def bare_svg():", "def bare_rc():", "write_bare()"):
            self.assertIn(piece, tool)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/aurorae/themes/MonetBare" "$DATADIR/aurorae/themes/MonetBare"', install)
        self.assertIn('"$PREFIX/share/aurorae/themes/MonetBare"', (ROOT / "linux/uninstall.sh").read_text())


class Script(unittest.TestCase):
    """The KWin script's package, and how it's installed and turned on."""

    def test_a_kwin_script_of_monets(self):
        meta = json.loads((SCRIPT / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["KPlugin"]["Id"], meta["X-Plasma-API"], meta["X-Plasma-MainScript"], meta["KPackageStructure"]),
                         ("monet-titles", "declarativescript", "ui/main.qml", "KWin/Script"))
        self.assertTrue(meta["KPlugin"]["EnabledByDefault"])
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/kwin/scripts/monet-titles" "$DATADIR/kwin/scripts/monet-titles"', install)
        self.assertIn('fill "$DATADIR"/kwin/scripts/monet-titles/contents/ui/*.qml', install)
        self.assertIn('"$PREFIX/share/kwin/scripts/monet-titles"', (ROOT / "linux/uninstall.sh").read_text())
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn("look --file kwinrc --group Plugins --key monet-titlesEnabled true", look)

    def test_the_script_keeps_to_kwins_ways(self):
        main = (UI / "main.qml").read_text(encoding="utf-8")
        bar = (UI / "TitleBar.qml").read_text(encoding="utf-8")
        # Shown and hidden by hand: KWin ignores a script window's first visible: true.
        for text in (main, bar):
            self.assertNotIn("visible: true", text)
            self.assertNotRegex(text, r"property \w+ (x|y|z|width|height|visible|opacity|scale|state)\b")
        self.assertIn("show()", bar)
        self.assertIn("bar.hide()", bar)
        # A tooltip to KWin: OverlayLayer like any of KWin's own windows, no focus, no popup grab,
        # and the scale effect leaves it alone (it animates managed normal windows, not popups).
        self.assertIn("flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint | Qt.WindowDoesNotAcceptFocus", bar)
        # The pointer is KWin's API: the cursor, the window under it, the active window's move and menu.
        for piece in ("function onCursorPosChanged()", "Workspace.windowAt(Qt.point(p.x, p.y), 2)",
                      "Hover.aimedAt(p, root.topWindow, root.canShow)", "Workspace.slotWindowMove()",
                      "Workspace.slotWindowOperations()", 'KWin.readConfig("Hover", true)', "target: Options",
                      "Workspace.isEffectActive(\"overview\")", "Kirigami.Units.longDuration / 200"):
            self.assertIn(piece, main)
        # The window itself is never moved or resized for the bar.
        for text in (main, bar):
            self.assertNotIn("frameGeometry =", text)
            self.assertNotIn("noBorder", text)
        # Its buttons, minimize, maximize and close, in Monet's words (catalog "monet").
        for word in ("Minimize", "Maximize", "Restore", "Close"):
            self.assertIn(f'i18nd("monet", "{word}")', bar)
        self.assertIn('"file://@DATADIR@/monet/window-buttons/"', bar)


class Switch(unittest.TestCase):
    """Settings → Light & Wallpaper: on unless turned off, and off is today's glass title bars."""

    def test_settings_has_the_switch(self):
        settings = settings_source()
        self.assertIn('["titles", i18n("Title bars appear when you point at the top"), ', settings)
        # The page is found by the words people use.
        self.assertIn("title bar titlebar", settings)

    def test_the_choice_is_kept_and_applied_at_once(self):
        from unittest import mock
        quick = quick_helper()
        with tempfile_dir() as tmp:
            quick.PREFS = Path(tmp) / "prefs.json"
            quick.drawn_by_processor = lambda: False
            self.assertTrue(quick.prefs()["titles"])    # on, as the owner asked
            quick.save_pref("titles", False)
            self.assertFalse(quick.prefs()["titles"])
        written, called, ran = [], [], []
        with mock.patch.object(quick, "kwrite", lambda *a: written.append(a) or True), \
                mock.patch.object(quick, "busctl", lambda *a: called.append(a) or ""), \
                mock.patch.object(quick, "run", lambda *a, **k: ran.append(a) or ""):
            self.assertTrue(quick.set_titles(False))
            self.assertTrue(quick.set_titles(True))
        self.assertEqual(written, [("kwinrc", "Script-monet-titles", "Hover", "false"),
                                   ("kwinrc", "Script-monet-titles", "Hover", "true")])
        # The frames change at once (monet-light), and KWin reads the script's switch again.
        self.assertEqual(ran, [(f"{quick.LIBEXECDIR}/monet-light", "apply")] * 2)
        self.assertEqual(called, [("call", "org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure")] * 2)
        source = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('"titles")', source[source.index('elif cmd == "pref" and len(args) == 2'):][:200])
        # Put back keeps the choice: monet-look never writes the script's switch, and monet-light,
        # which Put back runs, picks the frame from the choice.
        reset = source[source.index("def look_reset():"):]
        reset = reset[:reset.index("\n\n\n")]
        self.assertIn('run(f"{LIBEXECDIR}/monet-light", "paint", "wall"', reset)
        self.assertNotIn("Script-monet-titles", (ROOT / "linux/libexec/monet-look").read_text())

    def run_light(self, prefs=None, frame="__aurorae__svg__Monet", hour=21):
        with tempfile.TemporaryDirectory() as tmp:
            kde = FakeKDE(tmp, hour=hour)
            kde.light("apply")
            if prefs is not None:
                path = Path(tmp) / "config/monet/prefs.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(prefs))
            kde.set("kwinrc|org.kde.kdecoration2|theme", frame)
            kde.light("apply")
            return kde.settings()["kwinrc|org.kde.kdecoration2|theme"]

    def test_the_bare_frame_while_on_and_todays_frames_when_off(self):
        self.assertEqual(self.run_light(), "__aurorae__svg__MonetBare")
        self.assertEqual(self.run_light({"glass": "matte"}, hour=12), "__aurorae__svg__MonetBare")
        self.assertEqual(self.run_light({"titles": True}), "__aurorae__svg__MonetBare")
        # Off: exactly the glass title bars there were, in the light and glass there are.
        self.assertEqual(self.run_light({"titles": False}), "__aurorae__svg__MonetSmoke")
        self.assertEqual(self.run_light({"titles": False}, frame="__aurorae__svg__MonetBare", hour=12),
                         "__aurorae__svg__Monet")
        self.assertEqual(self.run_light({"titles": False, "glass": "solid"}, frame="__aurorae__svg__MonetBare"),
                         "__aurorae__svg__MonetSmokeSolid")
        # Someone's own frame is theirs, either way.
        self.assertEqual(self.run_light({}, frame="__aurorae__svg__Sweet"), "__aurorae__svg__Sweet")

    def test_an_update_keeps_the_choice(self):
        # Settings keeps it in prefs.json, which monet-look never writes; monet-light reads it.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertNotIn("Script-monet-titles", look)
        self.assertNotIn('"titles"', look)
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn('grep -q \'"titles": false\' "$CONFIG/monet/prefs.json"', light)


if __name__ == "__main__":
    unittest.main()
