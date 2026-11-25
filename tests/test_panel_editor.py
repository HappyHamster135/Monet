"""Render and operate Monet's real panel editor with an isolated panel object."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import ROOT, quick_helper
from tests import test_settings_navigation as settings

if settings.QT:
    from PySide6.QtCore import QObject, QPoint, QPointF, QUrl, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtQml import QQmlApplicationEngine, QJSEngine
    from PySide6.QtTest import QTest


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class PanelIcons(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)

    def test_center_only_changes_chosen_panels_app_alignment_and_keeps_pins(self):
        q = quick_helper(); engine = QJSEngine()
        engine.evaluate('''
        var printed = "";
        function print(value) { printed = value; }
        var config = {launchers:["my-app.desktop"], fill:false};
        var task = {writeConfig:function(k,v){config[k]=v}, readConfig:function(k,v){return config[k] === undefined ? v : config[k]}, reloadConfig:function(){}};
        function panelById(id) { return id === 7 ? {widgets:function(type){return type === "org.kde.plasma.icontasks" ? [task] : []}} : null; }
        ''')
        def bus(*args):
            value = engine.evaluate(args[-1]); self.assertFalse(value.isError(), value.toString())
            return [engine.evaluate('printed').toString()]
        with patch.object(q, 'busjson', side_effect=bus):
            self.assertEqual(q.panel_icons('7'), {'ok':True, 'available':True, 'alignment':'start'})
            self.assertEqual(q.panel_icons('7', 'center')['alignment'], 'center')
            self.assertEqual(q.panel_icons('7', 'start')['alignment'], 'start')
            self.assertFalse(q.panel_icons('8', 'center')['ok'])
        config = json.loads(engine.evaluate('JSON.stringify(config)').toString())
        self.assertEqual(config['launchers'], ['my-app.desktop'])
        self.assertTrue(config['fill'])
        with patch.object(q, 'busjson') as bus:
            self.assertFalse(q.panel_icons('7; print(1)', 'center')['ok'])
            self.assertFalse(q.panel_icons('7', 'unknown')['ok'])
            bus.assert_not_called()


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class PanelEditor(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    item = settings.SettingsNavigation.item

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        source = ROOT / 'linux/share/monet/panel'
        for p in source.glob('*.qml'):
            (folder / p.name).write_text(p.read_text().replace('@LIBEXECDIR@', str(folder)))
        helper = folder / 'monet-quick'
        helper.write_text("""#!/usr/bin/python3
import json
import sys
choice = sys.argv[3] if len(sys.argv) > 3 else ""
if sys.argv[1] == "panel-notch":
    tabs = ["music", "activity", "time", "calendar", "notes"]
    if choice == "tab-music-hide": tabs.remove("music")
    if choice == "tab-activity-earlier": tabs[:2] = ["activity", "music"]
    print(json.dumps(dict(ok=True, mode="compact", tabs=tabs, options=dict(previews=choice == "previews-on"))))
else:
    print(json.dumps(dict(ok=True, available=True, layout=choice or "three", alignment=choice or "start")))
""")
        helper.chmod(0o700)
        native = Path('/usr/share/plasma/shells/org.kde.plasma.desktop/contents/configuration')
        original = native / 'KdePanelConfiguration.qml'
        if not original.exists(): original = native / 'PanelConfiguration.qml'
        if not original.exists(): self.skipTest('native Plasma panel editor')
        shutil.copy2(original, folder / 'KdePanelConfiguration.qml')
        shutil.copytree(native / 'panelconfiguration', folder / 'panelconfiguration')
        fixture = folder / 'fixture.qml'
        fixture.write_text('''
import QtQuick
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.shell
import org.kde.kirigami as Kirigami
Window {
    id: window
    function i18nd(domain, text) { return text }
    function i18ndc(domain, context, text) { return text }
    width: 440; height: 760; visible: true; color: "#f3f1ec"
    QtObject {
        id: panel; objectName: "testPanel"
        property int location: PlasmaCore.Types.BottomEdge
        readonly property int leftEdge: PlasmaCore.Types.LeftEdge
        readonly property int bottomEdge: PlasmaCore.Types.BottomEdge
        property int lengthMode: Panel.FillAvailable
        property bool floating: false
        property bool floatingApplets: false
        property int alignment: Qt.AlignLeft
        property int visibilityMode: Panel.DodgeWindows
        property int thickness: 60
        property int minThickness: 20
        property int offset: 0
        property int minimumLength: 200
        property int maximumLength: 1200
        property int opacityMode: Panel.Adaptive
        property bool adaptiveOpacityEnabled: false
        property QtObject screenToFollow: QtObject { property rect geometry: Qt.rect(0,0,1280,800) }
        property int width: 1280
        property int height: 60
        property int length: 1280
        property int x: 0
        property int y: 0
        property int geometryWrites: 0
        property QtObject contentItem: QtObject { property var children: [{fixedTopFloatingPadding:0,
            fixedBottomFloatingPadding:0, fixedLeftFloatingPadding:0, fixedRightFloatingPadding:0}] }
        function setGeometry(x, y, width, height) { geometryWrites++ }
    }
    QtObject {
        id: plasmoid
        property int id: 7
        property string globalShortcut: ""
        property QtObject corona: QtObject { function enteredEditModeViaDesktop() { return false } }
        function internalAction(name) { return action }
    }
    QtObject { id: action; property int count: 0; function trigger() { count++ } }
    QtObject { id: configDialog; function close() {} function showAddWidgetDialog() {} }
    PanelConfiguration {
        id: wrapper; anchors.fill: parent
        Kirigami.Theme.inherit: false
        Kirigami.Theme.highlightColor: "#357f72"
        Kirigami.Theme.backgroundColor: "#f3f1ec"
        Kirigami.Theme.textColor: "#1c1b19"
        panelConfiguration: QtObject {
            property QtObject panelRulerView: QtObject { property bool visible: false }
        }
    }
}''')
        self.engine = QQmlApplicationEngine(); self.errors = []
        self.engine.warnings.connect(lambda errors: self.errors.extend(e.toString() for e in errors
            # Plasma 6.8's temporary ComboBox size probes warn under the offscreen Basic style.
            if not ('KdePanelConfiguration.qml:' in e.toString() and
                    'QML ComboBox: Binding loop detected for property "implicitWidth"' in e.toString())))
        self.words = self.games.Words(); self.engine.rootContext().setContextObject(self.words)
        # Panel's enum namespace is registered by plasmashell, not its QML plugin.
        self.engine.rootContext().setContextProperty('Panel', dict(FillAvailable=0, FitContent=1, Custom=2,
            NormalPanel=0, AutoHide=1, DodgeWindows=2, WindowsGoBelow=3, Adaptive=0, Opaque=1, Translucent=2))
        self.engine.load(QUrl.fromLocalFile(str(fixture)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.panel = self.window.findChild(QObject, 'testPanel')
        self.window.show(); self.window.requestActivate(); QTest.qWait(300)
        self.assertFalse(self.errors)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(20)
        self.assertFalse(self.errors, '\n'.join(self.errors))

    def click(self, name):
        item = self.item(name); item.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(100)
        return item

    def test_notification_preview_control_round_trips_in_customize_home_bar(self):
        name = 'notchOption-previews'
        option = self.item(name)
        self.assertTrue(option.isVisible())
        self.assertFalse(option.property('checked'))
        for enabled in (True, False):
            self.click(name)
            QTest.qWait(160)
            self.assertEqual(self.item('monetPanelEditor').property('notchOptions').toVariant()['previews'], enabled)
            self.assertEqual(option.property('checked'), enabled)

    def test_notch_tab_editor_checks_and_moves_with_the_keyboard(self):
        toggle = self.item('editNotchTabs')
        toggle.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(toggle.property('checked'))
        self.click('notchEarlier-activity')
        editor = self.item('monetPanelEditor')
        self.assertEqual(editor.property('notchTabs').toVariant()[:2], ['activity', 'music'])
        music = self.item('notchTab-music')
        music.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(200)
        self.assertFalse(music.property('checked'))
        self.assertFalse(self.item('notchEarlier-music').isEnabled())

    def test_one_and_three_bar_choices_use_layout_helper(self):
        self.assertTrue(self.item('panelThreeBars').property('checked'))
        self.click('panelOneBar'); QTest.qWait(200)
        self.assertTrue(self.item('panelOneBar').property('checked'))
        self.click('panelThreeBars'); QTest.qWait(200)
        self.assertTrue(self.item('panelThreeBars').property('checked'))

    def test_shape_choices_apply_without_rebuilding_or_changing_height(self):
        self.click('panelDock')
        self.assertTrue(self.panel.property('floating'))
        self.assertEqual(self.panel.property('alignment'), Qt.AlignCenter)
        self.assertEqual(self.panel.property('thickness'), 60)
        self.assertTrue(self.item('panelDock').property('checked'))
        self.click('panelFullWidth')
        self.assertFalse(self.panel.property('floating'))
        self.assertTrue(self.item('panelFullWidth').property('checked'))

    def test_edge_changes_cancel_delayed_surface_resizes(self):
        editor = self.item('monetPanelEditor')
        # A thickness/floating change may have queued a surface resize just
        # before the user moves the bar. Plasma owns the new orientation.
        editor.setProperty('surfaceResizePending', True)
        for _ in range(10):
            self.panel.setProperty('location', self.panel.property('leftEdge'))
            self.panel.setProperty('width', 60)
            self.panel.setProperty('height', 800)
            QTest.qWait(10)
            self.panel.setProperty('location', self.panel.property('bottomEdge'))
            self.panel.setProperty('width', 1280)
            self.panel.setProperty('height', 80)  # compositor's current buffer
            QTest.qWait(10)
        QTest.qWait(400)
        self.assertFalse(editor.property('surfaceResizePending'))
        self.assertEqual(self.panel.property('geometryWrites'), 0)

    def test_keyboard_focus_scrolls_controls_into_view_in_a_short_window(self):
        self.window.resize(360, 400); QTest.qWait(80)
        self.item('panelDone').forceActiveFocus(Qt.TabFocusReason)
        for _ in range(14):
            QTest.keyClick(self.window, Qt.Key_Tab); QTest.qWait(30)
            item = self.window.activeFocusItem()
            if item and item.property('text'):
                point = item.mapToScene(QPointF())
                self.assertGreaterEqual(point.y(), -1, item.property('text'))
                self.assertLessEqual(point.y() + item.height(), self.window.height() + 1, item.property('text'))

    def test_app_center_and_start_use_the_selected_panel(self):
        self.click('panelIconsCenter'); QTest.qWait(200)
        self.assertTrue(self.item('panelIconsCenter').property('checked'))
        self.click('panelIconsStart'); QTest.qWait(200)
        self.assertTrue(self.item('panelIconsStart').property('checked'))

    def test_size_changes_only_on_apply_and_wheel_does_not_resize(self):
        self.click('panelAppearancePage')
        editor = self.item('monetPanelEditor')
        original_size = (editor.implicitWidth(), editor.implicitHeight())
        self.click('panelSizeIncrease')
        self.assertEqual(self.panel.property('thickness'), 60)
        slider = self.item('panelSizeSlider')
        point = slider.mapToScene(QPointF(slider.width() / 2, slider.height() / 2))
        wheel = QWheelEvent(point, self.window.mapToGlobal(point.toPoint()), QPoint(), QPoint(0, 120),
                            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        self.app.sendEvent(self.window, wheel)
        self.assertEqual(slider.property('value'), 61)
        self.click('panelSizeApply')
        self.assertEqual(self.panel.property('thickness'), 61)
        self.assertEqual((editor.implicitWidth(), editor.implicitHeight()), original_size)

    def test_advanced_native_editor_loads_and_narrow_layout_remains_scrollable(self):
        button = self.click('panelAdvanced'); QTest.qWait(100)
        self.assertFalse(self.errors)
        # Keep the public button wrapper; do not traverse KDE's private C++ controls through PySide.
        button.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(100)
        self.window.resize(360, 460); QTest.qWait(100)
        self.assertLessEqual(self.item('panelDock').width(), 180)
        if os.environ.get('MONET_PANEL_CAPTURE'):
            self.window.resize(440, 760); QTest.qWait(100)
            self.window.grabWindow().save(os.environ['MONET_PANEL_CAPTURE'])
