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
            self.assertEqual(q.panel_icons('7'), {'ok':True, 'available':True, 'alignment':'start',
                                                'active':1, 'group':0, 'middle':2})
            self.assertEqual(q.panel_icons('7', 'center')['alignment'], 'center')
            self.assertEqual(q.panel_icons('7', 'start')['alignment'], 'start')
            self.assertFalse(q.panel_icons('8', 'center')['ok'])
            engine.evaluate('config.middleClickAction = "NewInstance"; config.minimizeActiveTaskOnClick = "false"')
            self.assertEqual(q.panel_icons('7')['active'], 0)
            self.assertEqual(q.panel_icons('7')['middle'], 2)
            self.assertEqual(q.panel_icons('7', 'group-3')['group'], 3)
            self.assertEqual(q.panel_icons('7', 'middle-3')['middle'], 3)
            self.assertEqual(q.panel_icons('7', 'active-1')['active'], 1)
            self.assertEqual(q.panel_icons('7', 'group-1')['group'], 1)
            self.assertTrue(engine.evaluate('config.showToolTips').toBool())
        config = json.loads(engine.evaluate('JSON.stringify(config)').toString())
        self.assertEqual(config['launchers'], ['my-app.desktop'])
        self.assertTrue(config['fill'])
        with patch.object(q, 'busjson') as bus:
            self.assertFalse(q.panel_icons('7; print(1)', 'center')['ok'])
            self.assertFalse(q.panel_icons('7', 'unknown')['ok'])
            for invalid in ('active-2', 'middle-6', 'group-4', 'group-1; print(1)'):
                self.assertFalse(q.panel_icons('7', invalid)['ok'])
            bus.assert_not_called()

    def test_advanced_native_operations_validate_targets_and_keep_other_widgets(self):
        q = quick_helper(); engine = QJSEngine()
        engine.evaluate("""
            var printed = "", screenCount = 2;
            var knownWidgetTypes = ["org.kde.plasma.panelspacer", "org.kde.plasma.marginsseparator"];
            var bar = {screen:0, items:["existing"], addWidget:function(id) {this.items.push(id);return {};}};
            function panelById(id) {return id === 8 ? bar : null;}
            function print(value) {printed = value;}
        """)
        def bus(*args):
            result = engine.evaluate(args[-1]); self.assertFalse(result.isError(), result.toString())
            return [engine.evaluate('printed').toString()]
        with patch.object(q, 'busjson', side_effect=bus):
            self.assertTrue(q.panel_detail('8','screen-1')['ok'])
            self.assertEqual(engine.evaluate('bar.screen').toInt(),1)
            self.assertFalse(q.panel_detail('8','screen-2')['ok'])
            self.assertEqual(engine.evaluate('bar.screen').toInt(),1)
            self.assertTrue(q.panel_detail('8','spacer')['ok'])
            self.assertTrue(q.panel_detail('8','separator')['ok'])
            self.assertEqual(engine.evaluate('bar.items.join(",")').toString(),
                'existing,org.kde.plasma.panelspacer,org.kde.plasma.marginsseparator')
            self.assertFalse(q.panel_detail('7','spacer')['ok'])
        with patch.object(q, 'busjson') as bus:
            self.assertFalse(q.panel_detail('8;print(1)','spacer')['ok'])
            self.assertFalse(q.panel_detail('8','screen-0;print(1)')['ok'])
            self.assertFalse(q.panel_detail('8','unknown')['ok'])
            bus.assert_not_called()


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class PanelEditor(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    def item(self, name):
        item = self.window.control(name)
        self.assertIsNotNone(item, name)
        return item


    def wait_for(self, condition, description):
        for _ in range(100):
            if condition():
                return
            QTest.qWait(20)
        self.fail(description)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        source = ROOT / 'linux/share/monet/panel'
        # Mirror the installed editor URL so Advanced exercises its shell-relative page.
        editor_page = 'monet-editor/' + 'a' * 64 + '/MonetPanelConfiguration.qml'
        (folder / 'MonetPanelEditor.ini').write_text('[Editor]\nPage=' + editor_page + '\n')
        for p in source.glob('*.qml'):
            (folder / p.name).write_text(p.read_text().replace('@LIBEXECDIR@', str(folder))
                                         .replace('@DATADIR@', str(ROOT / 'linux/share'))
                                         .replace('@PANEL_EDITOR@', 'monet-editor/old/MonetPanelConfiguration.qml')
                                         .replace('import "../games" as Shared', 'import "'+(ROOT/'linux/share/monet/games').as_uri()+'" as Shared'))
        (folder / editor_page).parent.mkdir(parents=True)
        (folder / editor_page).symlink_to('../../MonetPanelConfiguration.qml')
        helper = folder / 'monet-quick'
        helper.write_text("""#!/usr/bin/python3
import json
import sys
from pathlib import Path
choice = sys.argv[3] if len(sys.argv) > 3 else ""
if sys.argv[1] == "panel-add":
    print(json.dumps(dict(ok=choice in ("empty","home"), id=19, edge="left")))
elif sys.argv[1] == "panel-notch":
    saved = Path(__file__).with_name("notch-size.json")
    layout = json.loads(saved.read_text()) if saved.exists() else dict(expandedWidth=464, toolHeight=420)
    if choice:
        with Path(__file__).with_name("notch-commands").open("a") as log: log.write(choice+chr(10))
    if choice.startswith("size-"):
        _, width, height = choice.split("-")
        layout.update(expandedWidth=int(width),toolHeight=int(height))
        saved.write_text(json.dumps(layout))
    options_path = Path(__file__).with_name("notch-options.json")
    options = json.loads(options_path.read_text()) if options_path.exists() else dict(gestures=True,openActivity=True,autoHide=False,previews=False,countdown=True)
    if choice.endswith(("-on","-off")):
        key, value = choice.rsplit("-",1)
        options[key] = value == "on"
        options_path.write_text(json.dumps(options))
    if choice.startswith("reopen-"):
        layout["reopen"] = choice[7:]
        saved.write_text(json.dumps(layout))
    tabs = ["music", "activity", "time", "calendar", "notes"]
    if choice == "tab-clipboard-show": tabs.append("clipboard")
    if choice == "tab-music-hide": tabs.remove("music")
    if choice == "tab-activity-earlier": tabs[:2] = ["activity", "music"]
    if choice.startswith("tabs-"): tabs = choice[5:].split(",")
    print(json.dumps(dict(ok=True, mode="compact", tabs=tabs, layout=layout, options=options)))
elif sys.argv[1] == "panel-icons":
    actions = dict(active=1, group=0, middle=2)
    if "-" in choice:
        key, value = choice.split("-")
        actions[key] = int(value)
    print(json.dumps(dict(ok=True, available=True, alignment=choice or "start", **actions)))
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
    function control(name) {
        const pending = [contentItem]
        while (pending.length) {
            const item = pending.pop()
            if (item.objectName === name) return item
            // Query in QML to avoid wrapping every private KDE control in Python.
            if (item.visible) for (const child of item.children) pending.push(child)
        }
        return null
    }
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
        // Native PanelView.length is content length, not the custom window size.
        property int length: 600
        property int x: 0
        property int y: 0
        property int geometryWrites: 0
        property QtObject contentItem: Item {
            parent: window.contentItem
            Item {
                property int fixedTopFloatingPadding: 0
                property int fixedBottomFloatingPadding: 0
                property int fixedLeftFloatingPadding: 0
                property int fixedRightFloatingPadding: 0
            }
        }
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
    QtObject {
        id: configDialog; objectName: "testConfigDialog"
        property int width: window.width
        property int height: window.height
        property bool visible: true
        property bool floating: false
        property Item visualParent: panel.contentItem
        property int popupDirection: Qt.TopEdge
        property int margin: 4
        function queuePositionUpdate() {}
        function requestUpdate() {}
        function close() {}
        function showAddWidgetDialog() {}
    }
    MonetPanelConfiguration {
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

    def test_navigation_settings_persist_when_leaving_and_reopening_notch(self):
        self.click('panelNotchPage'); QTest.qWait(160)
        editor = self.item('notchVisualEditor')
        editor.setProperty('page', 3); QTest.qWait(30)
        for option in ('gestures', 'openActivity'):
            name = 'notchOption-' + option
            self.assertTrue(self.item(name).property('checked'))
            self.click(name)
            self.wait_for(lambda: not editor.property('busy'), 'Save navigation option')
            self.assertFalse(self.item(name).property('checked'))
        self.click('notchReopenLast')
        self.wait_for(lambda: not editor.property('busy'), 'Save reopen page')
        self.assertTrue(self.item('notchReopenLast').property('checked'))
        self.click('panelTaskbarPage'); self.click('panelNotchPage'); QTest.qWait(160)
        for option in ('gestures', 'openActivity'):
            self.assertFalse(self.item('notchOption-' + option).property('checked'))
            self.click('notchOption-' + option)
            self.wait_for(lambda: not editor.property('busy'), 'Restore navigation option')
            self.assertTrue(self.item('notchOption-' + option).property('checked'))
        self.assertTrue(self.item('notchReopenLast').property('checked'))
        self.click('notchReopenSections')
        self.wait_for(lambda: not editor.property('busy'), 'Save sections')
        self.assertTrue(self.item('notchReopenSections').property('checked'))

    def test_hidden_until_hover_is_optional_and_survives_reopening_settings(self):
        self.click('panelNotchPage'); QTest.qWait(160)
        self.click('notchBehaviorTab')
        editor = self.item('notchVisualEditor')
        name = 'notchOption-autoHide'
        self.assertFalse(self.item(name).property('checked'))
        self.click(name)
        self.wait_for(lambda: not editor.property('busy'), 'Save hidden-until-hover')
        self.assertTrue(self.item(name).property('checked'))
        self.click('panelTaskbarPage'); self.click('panelNotchPage'); QTest.qWait(160)
        self.assertTrue(self.item(name).property('checked'))
        self.click(name)
        self.wait_for(lambda: not editor.property('busy'), 'Restore always-visible notch')
        self.assertFalse(self.item(name).property('checked'))

    def test_shortcut_menu_keyboard_selection_and_scroll_safety(self):
        self.click('panelNotchPage'); QTest.qWait(160)
        choice = self.item('notchShortcut-0')
        choice.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(100)
        initial = choice.property('currentIndex')
        self.assertFalse(choice.property('wheelEnabled'))
        QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(50)
        QTest.keyClick(self.window, Qt.Key_Down)
        QTest.keyClick(self.window, Qt.Key_Return); QTest.qWait(160)
        commands = (Path(self.temp.name)/'notch-commands').read_text().splitlines()
        self.assertEqual(len(commands), 1)
        self.assertTrue(commands[0].startswith('rail-left-'), commands)

    def test_notification_preview_control_round_trips_in_customize_home_bar(self):
        self.click('panelNotchPage'); QTest.qWait(160)
        self.click('notchActivityTab')
        name = 'notchOption-previews'
        option = self.item(name)
        self.assertTrue(option.isVisible())
        self.assertFalse(option.property('checked'))
        for enabled in (True, False):
            self.click(name)
            QTest.qWait(160)
            self.assertEqual(self.item('monetPanelEditor').property('notchOptions').toVariant()['previews'], enabled)
            self.assertEqual(option.property('checked'), enabled)

    def test_running_timer_checkbox_defaults_on_and_can_be_switched_off(self):
        self.click('panelNotchPage'); QTest.qWait(160)
        self.click('notchActivityTab')
        name = 'notchOption-countdown'
        choice = self.item(name)
        self.assertTrue(choice.isVisible() and choice.property('checked'))
        for enabled in (False, True):
            self.click(name)
            QTest.qWait(160)
            self.assertEqual(self.item('monetPanelEditor').property('notchOptions').toVariant()['countdown'], enabled)
            self.assertEqual(choice.property('checked'), enabled)

    def test_notch_tab_editor_checks_and_moves_with_the_keyboard(self):
        self.click('panelNotchPage')
        editor = self.item('monetPanelEditor')
        self.wait_for(lambda: 'activity' in editor.property('notchTabs').toVariant(), 'Load notch tabs')
        self.wait_for(lambda: self.window.control('editNotchTabs') is not None, 'Build notch navigation')
        toggle = self.item('editNotchTabs')
        toggle.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertTrue(toggle.property('checked'))
        self.wait_for(lambda: self.window.control('notchEarlier-activity') is not None, 'Show page rows')
        self.click('notchEarlier-activity')
        self.wait_for(lambda: editor.property('notchTabs').toVariant()[:2] == ['activity', 'music'], 'Move Activity earlier')
        music = self.item('notchTab-music')
        music.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: not music.property('checked') and not editor.property('notchBusy'), 'Hide Music')
        self.assertFalse(self.item('notchEarlier-music').isEnabled())
        clipboard = self.item('notchTab-clipboard')
        self.assertFalse(clipboard.property('checked'))
        clipboard.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        self.wait_for(lambda: clipboard.property('checked') and not editor.property('notchBusy'), 'Show Clipboard')
        self.assertEqual(editor.property('notchTabs').toVariant()[-1], 'clipboard')

    def test_dragging_a_page_grip_reorders_the_saved_pages(self):
        self.click('panelNotchPage'); QTest.qWait(160); self.click('editNotchTabs')
        editor = self.item('monetPanelEditor')
        grip = self.item('notchGrip-music')
        target = self.item('notchGrip-activity')
        start = grip.mapToItem(self.window.contentItem(), QPointF(grip.width()/2, grip.height()/2)).toPoint()
        end = target.mapToItem(self.window.contentItem(), QPointF(target.width()/2, target.height()/2)).toPoint()
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, start)
        for i in range(1,10):
            QTest.mouseMove(self.window, start+(end-start)*i/9, 25)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, end)
        self.wait_for(lambda: editor.property('notchTabs').toVariant()[:2] == ['activity','music'], 'Save drag order')

    def drag(self, name, delta, release=True):
        grip = self.item(name)
        start = grip.mapToItem(self.window.contentItem(), QPointF(grip.width()/2, grip.height()/2)).toPoint()
        end = start+delta
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, start)
        for i in range(1,9): QTest.mouseMove(self.window, start+delta*i/8, 15)
        if release: QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, end)
        return end

    def test_notch_corner_previews_both_dimensions_and_saves_once_on_release(self):
        self.click('panelNotchPage'); QTest.qWait(180)
        editor = self.item('notchVisualEditor'); preview = self.item('notchSizePreview')
        before = (preview.width(), preview.height())
        end = self.drag('notchResizeRight',QPoint(18,25),release=False)
        self.assertGreater(preview.width(),before[0]+20)
        self.assertGreater(preview.height(),before[1]+15)
        self.assertFalse((Path(self.temp.name)/'notch-commands').exists())
        dimensions = (editor.property('draftWidth'),editor.property('draftHeight'))
        QTest.mouseRelease(self.window,Qt.LeftButton,Qt.NoModifier,end)
        self.wait_for(lambda: (Path(self.temp.name)/'notch-size.json').exists() and not editor.property('busy'), 'Save notch dimensions')
        self.assertEqual((Path(self.temp.name)/'notch-commands').read_text().splitlines(), ['size-%d-%d'%dimensions])
        self.click('panelTaskbarPage'); self.click('panelNotchPage')
        self.assertEqual((editor.property('draftWidth'),editor.property('draftHeight')),dimensions)
        self.click('notchResetSize')
        self.wait_for(lambda: editor.property('choices').toVariant()['toolHeight']==420, 'Reset both dimensions')

    def test_notch_resize_cancel_restores_preview_without_saving(self):
        self.click('panelNotchPage'); QTest.qWait(180)
        editor = self.item('notchVisualEditor')
        end = self.drag('notchResizeLeft',QPoint(-20,35),release=False)
        QTest.keyClick(self.window,Qt.Key_Escape)
        QTest.mouseRelease(self.window,Qt.LeftButton,Qt.NoModifier,end)
        QTest.qWait(100)
        self.assertEqual((editor.property('draftWidth'),editor.property('draftHeight')),(464,420))
        self.assertFalse((Path(self.temp.name)/'notch-commands').exists())

    def test_notch_height_slider_keyboard_changes_preview_and_persists(self):
        self.click('panelNotchPage'); QTest.qWait(180)
        editor = self.item('notchVisualEditor'); preview = self.item('notchSizePreview')
        slider = self.item('notchSize-toolHeight'); slider.forceActiveFocus(Qt.TabFocusReason)
        QTest.qWait(100)  # The viewport scrolls the keyboard-focused slider into view.
        height = preview.height()
        QTest.keyClick(self.window,Qt.Key_Right)
        self.wait_for(lambda: editor.property('choices').toVariant()['toolHeight']==422, 'Save keyboard height')
        self.assertGreater(preview.height(),height)

    def test_taskbar_center_resets_offset_and_preview_follows_icon_alignment(self):
        self.click('panelDock')
        self.panel.setProperty('alignment',Qt.AlignRight); self.panel.setProperty('offset',90)
        QTest.qWait(50)
        bar=self.item('taskbarSizePreview'); canvas=self.item('taskbarPreviewCanvas')
        self.assertNotAlmostEqual(bar.x()+bar.width()/2,canvas.width()/2,delta=1)
        self.click('panelCenterBar')
        self.assertEqual(self.panel.property('offset'),0)
        self.assertAlmostEqual(bar.x()+bar.width()/2,canvas.width()/2,delta=1)
        self.click('panelCenterApps'); QTest.qWait(180)
        icons=self.item('taskbarPreviewIconsHorizontal')
        self.assertAlmostEqual(icons.x()+icons.width()/2,bar.width()/2,delta=1)

    def test_taskbar_corner_resizes_custom_length_and_thickness_after_release(self):
        self.click('panelDock')
        before=self.panel.property('length')
        end=self.drag('taskbarResizeEnd',QPoint(12,-6),release=False)
        self.assertEqual(self.panel.property('length'),before)
        self.assertEqual(self.panel.property('thickness'),60)
        QTest.mouseRelease(self.window,Qt.LeftButton,Qt.NoModifier,end); QTest.qWait(100)
        self.assertGreater(self.panel.property('maximumLength'),before)
        self.assertGreater(self.panel.property('thickness'),60)
        self.assertEqual(self.panel.property('minimumLength'),self.panel.property('maximumLength'))
        self.click('panelFullWidth')
        self.assertEqual(self.panel.property('lengthMode'),0)

    def test_custom_size_stays_put_after_release_and_second_drag(self):
        self.panel.setProperty('minimumLength', 940)
        self.panel.setProperty('maximumLength', 940)
        self.panel.setProperty('lengthMode', 2)
        self.panel.setProperty('alignment', Qt.AlignCenter)
        QTest.qWait(50)
        editor = self.item('monetPanelEditor')
        self.assertEqual(editor.property('shownLength'), 940)
        for delta in (QPoint(-8, -4), QPoint(4, 2)):
            end = self.drag('taskbarResizeEnd', delta, release=False)
            length, thickness = editor.property('draftLength'), editor.property('draftSize')
            QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, end)
            QTest.qWait(70)
            self.assertEqual(editor.property('shownLength'), length)
            self.assertEqual(editor.property('draftSize'), thickness)
            self.assertEqual(self.panel.property('minimumLength'), length)
            self.assertEqual(self.panel.property('maximumLength'), length)

    def test_exact_dimensions_apply_together(self):
        for name, text in [('panelExactLength', '975'), ('panelExactThickness', '67')]:
            field = self.item(name); field.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(self.window, Qt.Key_A, Qt.ControlModifier)
            for character in text: QTest.keyClick(self.window, ord(character))
        self.assertEqual(self.panel.property('thickness'), 60)
        self.click('panelExactApply')
        self.assertEqual(self.panel.property('minimumLength'), 975)
        self.assertEqual(self.panel.property('maximumLength'), 975)
        self.assertEqual(self.panel.property('thickness'), 67)
        self.assertEqual(self.item('monetPanelEditor').property('shownLength'), 975)

    def test_corner_delta_does_not_include_canvas_scrolling(self):
        self.click('panelDock')
        grip = self.item('taskbarResizeEnd')
        start = grip.mapToScene(QPointF(grip.width()/2, grip.height()/2)).toPoint()
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, start)
        scroll = self.item('panelEditorScroll').property('contentItem')
        scroll.setProperty('contentY', scroll.property('contentY') + 20)
        QTest.qWait(50)
        QTest.mouseMove(self.window, start + QPoint(0,-7))
        QTest.qWait(20)
        self.assertEqual(self.item('monetPanelEditor').property('draftSize'), 80)
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, start + QPoint(0,-7))

    def test_editor_anchor_stays_fixed_across_panel_geometry_and_all_pages(self):
        placement = self.item('panelEditorPlacement')
        host = self.window.findChild(QObject, 'testConfigDialog')
        self.assertTrue(host.property('floating'))
        placement.moveTo(100, 20)
        editor = self.item('monetPanelEditor')
        size = editor.implicitWidth(), editor.implicitHeight()
        for direction in (Qt.TopEdge, Qt.LeftEdge, Qt.BottomEdge, Qt.RightEdge):
            host.setProperty('popupDirection', direction)
            self.panel.setProperty('x', 213); self.panel.setProperty('y', 500)
            self.panel.setProperty('thickness', 100)
            QTest.qWait(30)
            anchor_x = placement.x() + 213
            anchor_y = placement.y() + 500
            x = anchor_x - (host.property('width') + 4 if direction == Qt.LeftEdge else -4 if direction == Qt.RightEdge else host.property('width')/2)
            y = anchor_y - (host.property('height') + 4 if direction == Qt.TopEdge else -4 if direction == Qt.BottomEdge else host.property('height')/2)
            self.assertEqual((x,y), (100,20))
        for page in ('panelAppearancePage', 'panelBehaviorPage', 'panelNotchPage', 'panelAddPage', 'panelAdvanced'):
            self.click(page)
            self.assertEqual((editor.implicitWidth(),editor.implicitHeight()), size)

    def test_vertical_taskbar_corner_uses_vertical_length_axis(self):
        self.click('panelDock')
        self.panel.setProperty('location',self.panel.property('leftEdge')); QTest.qWait(100)
        before=self.panel.property('length')
        self.drag('taskbarResizeEnd',QPoint(5,8)); QTest.qWait(100)
        self.assertGreater(self.panel.property('maximumLength'),before)
        self.assertGreater(self.panel.property('thickness'),60)

    def test_taskbar_edge_resize_keeps_opposite_end_and_cancel_restores(self):
        self.click('panelDock')
        self.panel.setProperty('alignment',Qt.AlignLeft); self.panel.setProperty('offset',80)
        QTest.qWait(40)
        bar=self.item('taskbarSizePreview'); original_end=bar.x()+bar.width()
        end=self.drag('taskbarResizeStart',QPoint(9,-5),release=False)
        self.assertAlmostEqual(bar.x()+bar.width(),original_end,delta=1)
        self.assertEqual(self.panel.property('offset'),80)
        QTest.keyClick(self.window,Qt.Key_Escape)
        QTest.mouseRelease(self.window,Qt.LeftButton,Qt.NoModifier,end); QTest.qWait(40)
        self.assertEqual(self.panel.property('thickness'),60)
        self.assertAlmostEqual(bar.x()+bar.width(),original_end,delta=1)
        self.drag('taskbarResizeStart',QPoint(9,-5)); QTest.qWait(60)
        self.assertGreater(self.panel.property('offset'),80)
        self.assertAlmostEqual(bar.x()+bar.width(),original_end,delta=1)

    def test_notch_corner_clamps_to_supported_sizes_and_keeps_preview_in_canvas(self):
        self.click('panelNotchPage'); QTest.qWait(180)
        editor=self.item('notchVisualEditor')
        editor.previewSize(1000,900); QTest.qWait(30)
        self.assertEqual((editor.property('draftWidth'),editor.property('draftHeight')),(640,640))
        self.window.resize(360,760); QTest.qWait(80)
        preview=self.item('notchSizePreview'); handle=self.item('notchResizeRight')
        canvas=preview.parentItem()
        self.assertLessEqual(handle.x()+handle.width(),canvas.width())
        self.assertLessEqual(handle.y()+handle.height(),canvas.height())
        editor.previewSize(200,200); QTest.qWait(30)
        self.assertEqual((editor.property('draftWidth'),editor.property('draftHeight')),(340,316))
        self.assertLessEqual(preview.height(),canvas.height())

    def test_panel_picker_adds_panels_and_opens_notch_settings(self):
        self.click('panelAddPage')
        self.wait_for(lambda: self.item('panelAddEmpty').isEnabled(), 'Load panel choices')
        self.click('panelAddEmpty')
        editor = self.item('monetPanelEditor')
        self.wait_for(lambda: 'Panel added' in editor.property('addStatus'), 'Add an empty panel')
        self.click('panelAddNotch')
        self.wait_for(lambda: editor.property('page') == 3, 'Open notch settings')
        self.wait_for(lambda: self.window.control('editNotchTabs') is not None, 'Load visual notch editor')
        self.assertTrue(self.item('editNotchTabs').isVisible())

    def test_one_and_three_bar_choices_use_layout_helper(self):
        self.assertTrue(self.item('panelThreeBars').property('checked'))
        self.click('panelOneBar'); QTest.qWait(200)
        self.assertTrue(self.item('panelOneBar').property('checked'))
        self.click('panelThreeBars'); QTest.qWait(200)
        self.assertTrue(self.item('panelThreeBars').property('checked'))

    def test_keyboard_changes_group_click_action(self):
        self.click('panelBehaviorPage')
        group = self.item('panelClick-group')
        self.assertTrue(group.isVisible())
        self.assertEqual(group.property('currentIndex'), 0)
        group.forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(self.window, Qt.Key_Down)
        QTest.qWait(250)
        self.assertEqual(self.item('monetPanelEditor').property('iconActions').toVariant()['group'], 1)
        self.assertEqual(group.property('currentIndex'), 1)

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

    def test_advanced_monet_controls_stay_inside_narrow_window(self):
        button = self.click('panelAdvanced'); QTest.qWait(100)
        self.assertFalse(self.errors)
        self.assertIsNotNone(self.item('panelAdvancedOffset'))
        self.assertIsNotNone(self.item('panelFocusShortcut'))
        self.assertIsNone(self.item('monetPanelEditor').property('panelRuler'))
        scroll = self.item('panelEditorScroll')
        self.assertLessEqual(scroll.property('contentWidth'), scroll.property('availableWidth'))
        button.forceActiveFocus(Qt.TabFocusReason); QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(100)
        self.window.resize(360, 460); QTest.qWait(100)
        self.assertLessEqual(self.item('panelDock').width(), 180)
        if os.environ.get('MONET_PANEL_CAPTURE'):
            self.window.resize(440, 760); QTest.qWait(100)
            self.window.grabWindow().save(os.environ['MONET_PANEL_CAPTURE'])


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class DesktopEditorPlacement(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)

    def test_every_edit_mode_state_keeps_the_full_desktop(self):
        engine = QQmlApplicationEngine(); errors = []
        engine.warnings.connect(lambda messages: errors.extend(message.toString() for message in messages))
        source = '''
import QtQuick
import "@EDITMODE@" as EditMode
Item {
    id: root; width: 1280; height: 800
    function i18nd(domain, text) { return text }
    property rect editModeRect: Qt.rect(500, 0, 780, 800)
    property QtObject sidePanel: QtObject {
        property bool visible: false
        property QtObject mainItem: QtObject {
            property QtObject item: QtObject { property bool floatingEditor: false }
        }
    }
    property QtObject desktop: QtObject { property QtObject screenToFollow: screenRef }
    QtObject { id: screenRef }
    QtObject { id: testPanel; property QtObject screenToFollow: screenRef }
    property QtObject containment: QtObject {
        property QtObject plasmoid: QtObject {
            property QtObject corona: QtObject {
                property bool editMode: true
                property QtObject panelBeingConfigured: null
                function action(name) { return null }
            }
            function internalAction(name) { return null }
        }
    }
    Item {
        id: containmentParent
        property real scaleFactor: sidePanel.visible ? 0.55 : 0.65
        scale: scaleFactor
    }
    EditMode.MonetDesktopEditMode { id: editor; anchors.fill: parent }
    property real desktopScale: containmentParent.scaleFactor
    property real desktopCenterX: editor.centerX
    property real desktopCenterY: editor.centerY
    function editPanel() { containment.plasmoid.corona.panelBeingConfigured = testPanel }
    function gallery() { containment.plasmoid.corona.panelBeingConfigured = null; sidePanel.mainItem.item.floatingEditor = true; sidePanel.visible = true }
    function activities() { sidePanel.mainItem.item.floatingEditor = false }
    function closeGallery() { sidePanel.visible = false }
}
'''.replace('@EDITMODE@', (ROOT/'linux/share/monet/editmode').as_uri())
        try:
            # File loading releases the Python GIL while Qt resolves its imports.
            with tempfile.TemporaryDirectory() as folder:
                fixture = Path(folder) / 'desktop.qml'
                fixture.write_text(source)
                engine.load(QUrl.fromLocalFile(str(fixture)))
            self.assertTrue(engine.rootObjects(), errors)
            root = engine.rootObjects()[0]
            self.assertEqual(root.property('desktopScale'), 1)
            root.editPanel(); QTest.qWait(40)
            self.assertEqual(root.property('desktopScale'), 1)
            self.assertEqual((root.property('desktopCenterX'), root.property('desktopCenterY')), (640,400))
            root.gallery(); QTest.qWait(40)
            self.assertEqual(root.property('desktopScale'), 1)
            self.assertEqual((root.property('desktopCenterX'), root.property('desktopCenterY')), (640,400))
            root.activities(); QTest.qWait(40)
            self.assertEqual(root.property('desktopScale'), 1)
            root.closeGallery(); QTest.qWait(40)
            self.assertEqual(root.property('desktopScale'), 1)
        finally:
            engine.deleteLater(); QTest.qWait(20)
        self.assertFalse(errors, '\n'.join(errors))
