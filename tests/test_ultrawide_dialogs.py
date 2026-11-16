"""File and folder dialogs on an ultrawide screen (0.9.8-7): KDE's file dialog opened as a strip
across a 32:9 screen (the owner: "it always opens super wide"). Monet Snap, a KWin script
(share/kwin/scripts/monet-snap), gives one the width KDE would give it on a 16:9 screen as tall,
once, as it opens (dialogs.js), and KDE keeps that size, or the one you give it, from then on.

The arithmetic runs in Qt's JavaScript engine as KWin loads it, and the script itself against a
stand-in for KWin's scripting API (org.kde.kwin, as KWin 6.8 has it) and for Kirigami. Only the
Monet VM has a real KWin, a portal and KDE's dialog.
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "linux/share"
SNAP = SHARE / "kwin/scripts/monet-snap"
UI = SNAP / "contents/ui"
PORTAL = "org.freedesktop.impl.portal.desktop.kde"
try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine, QJSValue, QQmlApplicationEngine, QQmlExpression
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


def dialogs_js():
    """dialogs.js as QML loads it, without the line that makes it a QML library."""
    first, rest = (UI / "dialogs.js").read_text(encoding="utf-8").split("\n", 1)
    assert first == ".pragma library"
    return rest


def qt_round(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def kde_first(width, height, line):
    """KIO's KFileWidget::sizeHint, as KDE's file dialog first opens: 48 by 30 lines of text,
    expandedTo half the screen, boundedTo 90% of it (QSize's own rounding)."""
    return (min(max(48 * line, qt_round(width / 2)), qt_round(width * 0.9)),
            min(max(30 * line, qt_round(height / 2)), qt_round(height * 0.9)))


def on_169(height, line):
    """What KDE's dialog gets on a 16:9 screen as tall: the most Monet lets it have."""
    return kde_first(qt_round(height * 16 / 9), height, line)


def window(**kw):
    """A window as KWin describes it: by default a file dialog an app opened over its window,
    which on Wayland is a normal window with a parent (transient), 2560 by 720 on a 32:9 screen."""
    screen = kw.pop("screen", dict(x=0, y=0, width=5120, height=1440))
    w = dict(deleted=False, managed=True, fullScreen=False, minimized=False, hidden=False, move=False, resize=False,
             maximizeMode=0, resizeable=True, specialWindow=False, popupWindow=False, outline=False,
             normalWindow=True, dialog=False, transient=True, transientFor=None, desktopFileName="org.kde.kate",
             resourceClass="org.kde.kate", minSize=dict(width=420, height=300), output=dict(geometry=screen),
             frameGeometry=dict(x=1280, y=360, width=2560, height=720))
    w.update(kw)
    w.setdefault("clientGeometry", w["frameGeometry"])
    return w


@unittest.skipUnless(QT, "requires PySide6")
class Arithmetic(unittest.TestCase):
    """dialogs.js: which windows are KDE's file dialog at its first size, and where they go."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.js = QJSEngine()
        result = self.js.evaluate(dialogs_js())
        self.assertFalse(result.isError(), result.toString())

    def run_js(self, expression):
        result = self.js.evaluate("JSON.stringify(" + expression + ")")
        self.assertFalse(result.isError(), result.toString())
        return json.loads(result.toString()) if result.toString() != "undefined" else None

    def fit(self, w, screens=None, area=None):
        screen = (w["output"] or {}).get("geometry") or dict(x=0, y=0, width=5120, height=1440)
        screens = screens or [screen]
        area = area or screen
        return self.run_js(f"fitted({json.dumps(w)}, {json.dumps(screens)}, {json.dumps(area)})")

    def test_at_every_size_and_scale_no_wider_than_on_a_16_9_screen(self):
        # The owner's 32:9 screen and the other ultrawides, and 16:9 ones, at 100% to 200%, with
        # small to large text: KDE's first size, centered on the screen as KWin puts it.
        cases = 0
        for physical in ((5120, 1440), (3440, 1440), (2560, 1080), (3840, 1600), (5120, 2160),
                         (1920, 1080), (2560, 1440), (3840, 2160), (1920, 1200), (2560, 1600)):
            for scale in (1, 1.25, 1.5, 1.75, 2):
                width, height = (qt_round(n / scale) for n in physical)
                screen = dict(x=0, y=0, width=width, height=height)
                for line in (18, 20, 24):
                    cw, ch = kde_first(width, height, line)
                    frame = dict(x=(width - cw) // 2, y=(height - ch) // 2, width=cw, height=ch)
                    got = self.fit(window(screen=screen, frameGeometry=frame))
                    case = (physical, scale, line, (cw, ch), got)
                    ultrawide, halved = width > 2 * height, cw == qt_round(width / 2)
                    if not ultrawide or not halved or on_169(height, line)[0] >= cw - 8:
                        # 16:9 and 16:10 screens, a dialog KDE sized by its text, or one no wider
                        # than on a 16:9 screen anyway: as KDE has it.
                        self.assertIsNone(got, case)
                        self.assertLessEqual(cw, max(on_169(height, line)[0], qt_round(width * 0.9)), case)
                        continue
                    cases += 1
                    self.assertEqual(got["height"], ch, case)
                    if ch < qt_round(height * 0.9):
                        self.assertLessEqual(abs(got["width"] - on_169(height, line)[0]), 1, case)
                    else:  # a dialog as tall as KDE allows: a little narrower still
                        self.assertLess(got["width"], on_169(height, line)[0], case)
                    self.assertLess(got["width"], cw, case)
                    # Centered where KWin put it, on the screen.
                    self.assertLessEqual(abs(got["x"] + got["width"] / 2 - width / 2), 1, case)
                    self.assertEqual(got["y"], frame["y"], case)
        self.assertGreater(cases, 40)

    def test_the_owners_screen_and_the_other_ultrawides(self):
        def first_and_fitted(width, height, line=20):
            cw, ch = kde_first(width, height, line)
            got = self.fit(window(screen=dict(x=0, y=0, width=width, height=height),
                                  frameGeometry=dict(x=(width - cw) // 2, y=(height - ch) // 2, width=cw, height=ch)))
            return (cw, ch), got and (got["width"], got["height"])
        # 32:9, KDE's 2560 by 720 strip: 1280 by 720, as on a 2560 by 1440 screen.
        self.assertEqual(first_and_fitted(5120, 1440), ((2560, 720), (1280, 720)))
        self.assertEqual(first_and_fitted(3440, 1440), ((1720, 720), (1280, 720)))
        self.assertEqual(first_and_fitted(2560, 1080), ((1280, 600), (960, 600)))
        # 32:9 at 125% and 150% (logical pixels).
        self.assertEqual(first_and_fitted(4096, 1152), ((2048, 600), (1024, 600)))
        self.assertEqual(first_and_fitted(3413, 960), ((1707, 600), (960, 600)))
        # 16:9 and 16:10: nothing changes.
        self.assertEqual(first_and_fitted(1920, 1080), ((960, 600), None))
        self.assertEqual(first_and_fitted(2560, 1440), ((1280, 720), None))
        self.assertEqual(first_and_fitted(1920, 1200), ((960, 600), None))
        self.assertEqual(first_and_fitted(3840, 2160), ((1920, 1080), None))

    def test_which_windows(self):
        fits = lambda **kw: self.fit(window(**kw)) is not None
        self.assertTrue(fits())                                              # a dialog on Wayland
        self.assertTrue(fits(transient=False, transientFor=dict(deleted=False, minimized=False,
                                                                frameGeometry=dict(x=0, y=0, width=900, height=700))))
        self.assertTrue(fits(normalWindow=False, dialog=True, transient=True))  # an X11 app's
        # KDE's portal (Flatpak, Electron, GTK and browser apps), with or without the app's window.
        self.assertTrue(fits(transient=False, desktopFileName=PORTAL, resourceClass=PORTAL))
        self.assertTrue(fits(transient=False, desktopFileName="", resourceClass=PORTAL))
        # An app's own window, even one KDE's size fits: Monet Work puts those back after a restart.
        self.assertFalse(fits(transient=False))
        self.assertFalse(fits(transient=False, desktopFileName="org.kde.dolphin"))
        # KWin's and Plasma's own, menus, toolbars, and windows in any state but plainly open.
        self.assertFalse(fits(normalWindow=False))
        self.assertFalse(fits(normalWindow=False, utility=True))
        for flag in ("deleted", "fullScreen", "minimized", "hidden", "move", "resize", "specialWindow",
                     "popupWindow", "outline"):
            self.assertFalse(fits(**{flag: True}), flag)
        self.assertFalse(fits(managed=False))
        self.assertFalse(fits(resizeable=False))
        for mode in (1, 2, 3):                                               # filling the screen, either way
            self.assertFalse(fits(maximizeMode=mode), mode)
        self.assertFalse(fits(output=None))
        self.assertIsNone(self.run_js("fitted(null, [], {})"))

    def test_a_size_kde_kept_is_left_alone(self):
        # Any size KDE kept from before (KWindowConfig), yours or the one Monet gave it.
        for size in ((1600, 900), (3000, 1000), (2400, 720), (2600, 720), (1280, 720), (4600, 1300), (2560, 600),
                     (2560, 1340)):
            frame = dict(x=(5120 - size[0]) // 2, y=(1440 - size[1]) // 2, width=size[0], height=size[1])
            self.assertIsNone(self.fit(window(frameGeometry=frame)), size)
        # Rounding between Qt's idea of the screen and KWin's (fractional scales, X11 apps).
        self.assertIsNotNone(self.fit(window(frameGeometry=dict(x=1280, y=360, width=2557.7, height=720))))
        # Qt may leave a panel out of the screen's height.
        self.assertIsNotNone(self.fit(window(frameGeometry=dict(x=1280, y=380, width=2560, height=682))))

    def test_centered_on_the_window_that_opened_it(self):
        app = dict(x=3400, y=100, width=1600, height=1200)
        got = self.fit(window(transientFor=dict(deleted=False, minimized=False, frameGeometry=app),
                              frameGeometry=dict(x=2560, y=340, width=2560, height=720)))
        self.assertEqual(got, dict(x=3560, y=340, width=1280, height=720))
        # Near the screen's edge: inside its work area (a bar along the right, here).
        app = dict(x=4200, y=100, width=900, height=1200)
        area = dict(x=0, y=0, width=5040, height=1440)
        got = self.fit(window(transientFor=dict(deleted=False, minimized=False, frameGeometry=app),
                              frameGeometry=dict(x=2480, y=340, width=2560, height=720)), area=area)
        self.assertEqual(got, dict(x=3760, y=340, width=1280, height=720))
        # No window of the app's (the portal's, asked without one), or one minimized: where KWin put it.
        self.assertEqual(self.fit(window(transient=False, desktopFileName=PORTAL, frameGeometry=dict(
            x=600, y=360, width=2560, height=720))), dict(x=1240, y=360, width=1280, height=720))
        self.assertEqual(self.fit(window(transientFor=dict(deleted=False, minimized=True, frameGeometry=app))),
                         dict(x=1920, y=360, width=1280, height=720))
        # A frame around it (title bars turned back on): the dialog itself 1280 wide, its title kept.
        got = self.fit(window(frameGeometry=dict(x=1276, y=324, width=2568, height=760),
                              clientGeometry=dict(x=1280, y=360, width=2560, height=720)))
        self.assertEqual(got, dict(x=1916, y=324, width=1288, height=760))
        # Never narrower than the dialog can be.
        got = self.fit(window(minSize=dict(width=1500, height=400)))
        self.assertEqual((got["x"], got["width"]), (1810, 1500))

    def test_measured_on_one_screen_opened_on_another(self):
        # Qt sizes it by the main screen: a 32:9 one beside a 16:9 one it opens on.
        ultra, side = dict(x=0, y=0, width=5120, height=1440), dict(x=5120, y=0, width=1920, height=1080)
        app = dict(x=5320, y=100, width=1500, height=900)
        got = self.fit(window(screen=side, transientFor=dict(deleted=False, minimized=False, frameGeometry=app),
                              frameGeometry=dict(x=5120, y=190, width=2560, height=720)), screens=[ultra, side], area=side)
        self.assertEqual(got, dict(x=5494, y=190, width=1152, height=720))
        # And the other way: sized by a 2560 by 1440 main screen, it already fits a 32:9 one.
        main = dict(x=5120, y=0, width=2560, height=1440)
        self.assertIsNone(self.fit(window(frameGeometry=dict(x=1920, y=360, width=1280, height=720)), screens=[ultra, main]))


# A stand-in for KWin's scripting API: what Monet Snap uses, as KWin 6.8 has it.
FAKE_KWIN = {
    "qmldir": "module org.kde.kwin\nsingleton Workspace 1.0 Workspace.qml\nsingleton KWin 1.0 KWin.qml\n"
              "singleton Options 1.0 Options.qml\nShortcutHandler 1.0 ShortcutHandler.qml\n"
              "WindowThumbnail 1.0 WindowThumbnail.qml\n",
    "KWin.qml": "pragma Singleton\nimport QtQml\nQtObject {\n    property var config: ({})\n"
                "    enum ClientAreaOption { PlacementArea, MovementArea, MaximizeArea }\n"
                "    function readConfig(key, value) { return key in config ? config[key] : value }\n}\n",
    "Options.qml": "pragma Singleton\nimport QtQml\nQtObject { signal configChanged() }\n",
    "ShortcutHandler.qml": "import QtQml\nQtObject {\n    property string name\n    property string text\n"
                           "    property var sequence\n    signal activated()\n}\n",
    "WindowThumbnail.qml": "import QtQuick\nItem { property var wId }\n",
    "Workspace.qml": """pragma Singleton
import QtQml
QtObject {
    signal windowAdded(var window)
    signal windowRemoved(var window)
    property var stackingOrder: []
    property var screens: []
    property var activeWindow: null
    property var currentDesktop: "one"
    property point cursorPos: Qt.point(0, 0)
    // Each screen's work area, by its name: the screen without its panels.
    property var areas: ({})
    function clientArea(kind, w) {
        const o = w.output || w
        return areas[o.name] || o.geometry
    }
    function screenAt(p) { return screens.length ? screens[0] : null }
    function isEffectActive(name) { return false }
    function add(w) {
        stackingOrder = stackingOrder.concat([w])
        windowAdded(w)
    }
}
""",
}
FAKE_KIRIGAMI = {
    "qmldir": "module org.kde.kirigami\nsingleton Units 1.0 Units.qml\nIcon 1.0 Icon.qml\n",
    "Units.qml": "pragma Singleton\nimport QtQml\nQtObject { property int longDuration: 200 }\n",
    "Icon.qml": "import QtQuick\nItem { property var source }\n",
}

SCENE = """import QtQuick
import org.kde.kwin

Item {
    id: scene
    property var snap: snapLoader.item

    component Screen: QtObject {
        property string name
        property rect geometry
    }
    property var ultra: Screen { name: "DP-1"; geometry: Qt.rect(0, 0, 5120, 1440) }
    property var side: Screen { name: "DP-2"; geometry: Qt.rect(5120, 0, 1920, 1080) }

    component FakeWindow: QtObject {
        property string caption: ""
        property string internalId: caption
        property string desktopFileName: "org.kde.kate"
        property string resourceClass: desktopFileName
        property bool deleted: false
        property bool managed: true
        property bool minimized: false
        property bool hidden: false
        property bool fullScreen: false
        property bool normalWindow: true
        property bool dialog: false
        property bool utility: false
        // KWin's transient too, which QML can't name (a word it keeps): a window opened over another.
        property var transientFor: null
        property bool specialWindow: false
        property bool popupWindow: false
        property bool outline: false
        property bool dock: false
        property bool notification: false
        property bool criticalNotification: false
        property bool demandsAttention: false
        property bool resizeable: true
        property bool move: false
        property bool resize: false
        property int maximizeMode: 0
        property size minSize: Qt.size(420, 300)
        property var tile: null
        property var output: scene.ultra
        property rect frameGeometry: Qt.rect(100, 100, 800, 600)
        // KWin's frame for the client: Monet's bare frame has no title bar, so they're the same.
        property rect clientGeometry: frameGeometry
        // Every size KWin is asked for, in order.
        property var asked: []
        onFrameGeometryChanged: asked = asked.concat([[frameGeometry.x, frameGeometry.y, frameGeometry.width, frameGeometry.height]])
        signal closed()
        signal interactiveMoveResizeStarted()
        signal interactiveMoveResizeStepped()
        signal interactiveMoveResizeFinished()
    }

    property var app: FakeWindow { caption: "Kate"; frameGeometry: Qt.rect(3400, 100, 1600, 1200) }
    // KDE's file dialog as the app opens it: half the screen, centered on the app (KWin keeps it inside).
    property var picker: FakeWindow {
        caption: "Open File"; transientFor: scene.app; frameGeometry: Qt.rect(2560, 340, 2560, 720)
    }

    // Started once the test has set out what's already open.
    Loader {
        id: snapLoader
        active: false
        source: "SNAP"
    }
}
"""


@unittest.skipUnless(QT, "requires PySide6")
class Behaviour(unittest.TestCase):
    """Monet Snap itself, against the stand-in for KWin."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        for module, files in (("org/kde/kwin", FAKE_KWIN), ("org/kde/kirigami", FAKE_KIRIGAMI)):
            path = folder / "imports" / module
            path.mkdir(parents=True)
            for name, text in files.items():
                (path / name).write_text(text, encoding="utf-8")
        # The script as install.sh lays it out.
        ui = folder / "monet-snap/contents/ui"
        shutil.copytree(UI, ui)
        scene = folder / "scene.qml"
        scene.write_text(SCENE.replace("SNAP", QUrl.fromLocalFile(str(ui / "main.qml")).toString()), encoding="utf-8")
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(folder / "imports"))
        self.errors = []
        self.engine.warnings.connect(lambda warnings: self.errors.extend(w.toString() for w in warnings))
        self.engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(self.engine.rootObjects(), "\n".join(self.errors))
        self.scene = self.engine.rootObjects()[0]
        self.addCleanup(self.engine.deleteLater)

    def start(self, *before):
        """Workspace as KWin has it when the script starts: these windows already open."""
        self.js("Workspace.screens = [scene.ultra, scene.side]")
        self.js("Workspace.areas = ({ 'DP-1': Qt.rect(0, 0, 5120, 1440), 'DP-2': Qt.rect(5120, 0, 1920, 1080) })")
        self.js("Workspace.stackingOrder = [" + ", ".join("scene." + n for n in before) + "]")
        self.js("scene.app.asked = []")
        self.js("scene.picker.asked = []")
        self.js("snapLoader.active = true")
        QTest.qWait(20)
        self.assertIsNotNone(self.scene.property("snap"), "\n".join(self.errors))

    def js(self, expression):
        expr = QQmlExpression(self.engine.contextForObject(self.scene), self.scene, expression)
        value, _ = expr.evaluate()
        self.assertFalse(expr.hasError(), expr.error().toString())
        return value.toVariant() if isinstance(value, QJSValue) else value

    def frame(self, name):
        r = self.js(f"scene.{name}.frameGeometry")
        return (r.x(), r.y(), r.width(), r.height())

    def test_a_file_dialog_opening_on_an_ultrawide_gets_a_16_9_width_once(self):
        self.start("app")
        self.js("Workspace.add(scene.picker)")
        # As on a 2560 by 1440 screen, centered on Kate's window.
        self.assertEqual(self.frame("picker"), (3560, 340, 1280, 720))
        self.assertEqual(self.js("scene.picker.asked.length"), 1)
        # Made wider again by hand: it stays as wide as that, and KDE keeps it.
        self.js("scene.picker.resize = true")
        self.js("scene.picker.frameGeometry = Qt.rect(2400, 340, 2800, 720)")
        self.js("scene.picker.resize = false")
        QTest.qWait(50)
        self.assertEqual(self.frame("picker"), (2400, 340, 2800, 720))
        self.assertFalse(self.errors, "\n".join(self.errors))

    def test_with_snap_layouts_off_too(self):
        self.start("app")
        self.js("KWin.config = { Snapping: false }")
        self.js("Options.configChanged()")
        self.js("Workspace.add(scene.picker)")
        self.assertEqual(self.frame("picker"), (3560, 340, 1280, 720))

    def test_the_portals_dialog_without_the_apps_window(self):
        self.start()
        self.js("scene.picker.transientFor = null")
        self.js(f"scene.picker.desktopFileName = '{PORTAL}'")
        self.js("scene.picker.frameGeometry = Qt.rect(1280, 360, 2560, 720)")
        self.js("Workspace.add(scene.picker)")
        self.assertEqual(self.frame("picker"), (1920, 360, 1280, 720))

    def test_already_open_and_app_windows_are_left_alone(self):
        # Open before the script started (KWin restarted it): left as it is.
        self.start("app", "picker")
        QTest.qWait(50)
        self.assertEqual(self.frame("picker"), (2560, 340, 2560, 720))
        self.assertEqual(self.js("scene.picker.asked.length"), 0)
        # An app's own window at half the screen, as an app may open (Monet Work's to put back).
        self.js("scene.app.frameGeometry = Qt.rect(1280, 360, 2560, 720)")
        self.js("scene.app.asked = []")
        self.js("Workspace.add(scene.app)")
        self.assertEqual(self.frame("app"), (1280, 360, 2560, 720))
        self.assertEqual(self.js("scene.app.asked.length"), 0)

    def test_on_a_16_9_screen_nothing_changes(self):
        self.start("app")
        self.js("Workspace.screens = [scene.side]")
        self.js("scene.app.output = scene.side")
        self.js("scene.picker.output = scene.side")
        self.js("scene.picker.frameGeometry = Qt.rect(5600, 270, 960, 540)")
        self.js("scene.picker.asked = []")
        self.js("Workspace.add(scene.picker)")
        self.assertEqual(self.frame("picker"), (5600, 270, 960, 540))
        self.assertEqual(self.js("scene.picker.asked.length"), 0)
        # Nor full screen, nor filling the screen.
        self.js("Workspace.screens = [scene.ultra]")
        self.js("scene.picker.output = scene.ultra")
        self.js("scene.picker.frameGeometry = Qt.rect(1280, 360, 2560, 720)")
        for state, back in (("fullScreen = true", "fullScreen = false"), ("maximizeMode = 3", "maximizeMode = 0")):
            self.js(f"scene.picker.{state}")
            self.js("scene.picker.asked = []")
            self.js("Workspace.add(scene.picker)")
            self.assertEqual(self.js("scene.picker.asked.length"), 0, state)
            self.js(f"scene.picker.{back}")
        # The same dialog, plainly open: it would have been, centered on Kate's window.
        self.js("Workspace.add(scene.picker)")
        self.assertEqual(self.frame("picker"), (3560, 360, 1280, 720))


class Script(unittest.TestCase):
    """How Monet Snap goes about it, and that it's installed with the rest of the script."""

    def test_only_as_a_window_opens_whatever_the_snap_switch(self):
        main = (UI / "main.qml").read_text(encoding="utf-8")
        self.assertIn('import "dialogs.js" as Dialogs', main)
        self.assertIn("Workspace.windowAdded.connect(fitDialog)", main)
        # Never for the windows already open when the script starts.
        start = main[main.index("Component.onCompleted: {"):]
        start = start[:start.index("\n    }\n")]
        self.assertIn("Workspace.stackingOrder.forEach(watch)", start)
        self.assertNotIn("forEach(fitDialog)", main)
        body = main[main.index("function fitDialog(w) {"):]
        body = body[:body.index("\n    }\n")]
        self.assertNotIn("snapping", body)
        self.assertIn("Workspace.clientArea(KWin.MaximizeArea, w)", body)
        self.assertIn("Workspace.screens.map(s => s.geometry)", body)
        # The frame KWin sizes, never a frame of its own, nor a size kept anywhere else.
        js = (UI / "dialogs.js").read_text(encoding="utf-8")
        for gone in ("frameGeometry =", "noBorder", "readConfig", "Workspace"):
            self.assertNotIn(gone, js)
        self.assertIn('var PORTAL = "org.freedesktop.impl.portal.desktop.kde"', js)
        # Installed with Monet Snap, which is on.
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/kwin/scripts/monet-snap" "$DATADIR/kwin/scripts/monet-snap"', install)
        self.assertIn("look --file kwinrc --group Plugins --key monet-snapEnabled true",
                      (ROOT / "linux/libexec/monet-look").read_text())

    def test_monet_works_windows_are_never_its(self):
        # Monet Work puts back an app's own windows after a restart (not one opened over another):
        # those are never a file dialog here, except the portal's own, which Monet never reopens.
        work = (SHARE / "kwin/scripts/monet-work/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("!w.transient", work)
        js = (UI / "dialogs.js").read_text(encoding="utf-8")
        self.assertIn("return !!(w.dialog || w.transient || w.transientFor || w.desktopFileName === PORTAL"
                      " || w.resourceClass === PORTAL)", js)

    def test_said_in_whats_new(self):
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        section = notes[notes.index("### New in 0.9.8-7"):notes.index("### New in 0.9.8-6")]
        self.assertIn("ultrawide", section)


if __name__ == "__main__":
    unittest.main()
