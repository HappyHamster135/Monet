"""Real Qt windows survive their Plasma request and keep their own geometry."""
from pathlib import Path
import tempfile
import unittest
from tests import test_settings_navigation as settings
from tests.test_look import ROOT

if settings.QT:
    from PySide6.QtCore import QUrl, Qt, QObject, Slot
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from shiboken6 import isValid


@unittest.skipUnless(settings.QT, 'Qt runtime')
class EditorWindows(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)

    def test_handoff_survives_popup_destruction_and_reopens_at_user_size(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/'page.qml').write_text('''import QtQuick
Item { required property QtObject panelConfiguration
    property int liveThickness: panel.thickness
    property QtObject windowHost: configDialog
    property int selectedPage: -1
    function selectPage(number) { selectedPage = number }
}''')
            (folder/'fixture.qml').write_text('''import QtQuick
import QtQuick.Window
import "@PANEL@/EditorWindows.js" as EditorWindows
Window {
    id: root; width: 1280; height: 800; visible: true
    function i18nd(domain, text) { return text }
    property var appWindow: null
    property QtObject panel: QtObject {
        property int thickness: 50
        property QtObject screenToFollow: QtObject { property string name: "" }
    }
    property QtObject plasmoid: QtObject { property int id: 98531; property QtObject corona: QtObject { property bool editMode: true } }
    function openEditor() { request.active = false; request.active = true }
    function resizePanel() { panel.thickness = 90 }
    property QtObject notch: QtObject {
        property int id: 98532
        property QtObject widget: QtObject { property string pluginName: "org.monet.notch" }
        property var applets: [widget]
        property QtObject corona: root.plasmoid.corona
    }
    Item { id: otherPanelParent }
    function openNotch() {
        const host = EditorWindows.forParent(otherPanelParent)
        host.openPanel(panel, notch, Qt.resolvedUrl("page.qml"))
        return host.panelWindow === appWindow
    }
    function endEditing() { plasmoid.corona.editMode = false }
    Item { id: stableParent; anchors.fill: parent }
    Loader {
        id: request
        sourceComponent: Item {
            Component.onCompleted: {
                const host = EditorWindows.forParent(stableParent)
                host.openPanel(root.panel, root.plasmoid, Qt.resolvedUrl("page.qml"))
                root.appWindow = host.panelWindow
                root.appWindow.nativeGeometry = false
                Qt.callLater(() => request.active = false)
            }
        }
    }
    property bool requestAlive: request.active
}'''.replace('@PANEL@',(ROOT/'linux/share/monet/panel').as_uri()))
            engine = QQmlApplicationEngine(); errors = []
            class Words(QObject):
                @Slot(str, str, result=str)
                def i18nd(self, domain, text): return text
                @Slot(str, result=str)
                def i18n(self, text): return text
            words = Words(); engine.rootContext().setContextObject(words)
            engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
            engine.load(QUrl.fromLocalFile(str(folder/'fixture.qml')))
            self.assertTrue(engine.rootObjects(), errors)
            root = engine.rootObjects()[0]
            try:
                QTest.qWait(150)
                self.assertFalse(errors, '\n'.join(errors))
                app = root.property('appWindow')
                self.assertIsNotNone(app)
                self.assertFalse(root.property('requestAlive'))
                self.assertTrue(app.isVisible())
                self.assertTrue(app.flags() & Qt.FramelessWindowHint)
                self.assertIsNotNone(app.findChild(QObject, 'windowTitleBar'))
                self.assertTrue(root.openNotch())
                self.assertEqual(app, root.property('appWindow'))
                self.assertEqual(app.property('plasmoid').property('id'), 98531)
                app.resize(580,510); QTest.qWait(300)
                root.resizePanel(); root.requestActivate(); QTest.qWait(80)
                self.assertTrue(app.isVisible(), str(errors))
                self.assertEqual((app.width(),app.height()),(580,510))
                app.close(); QTest.qWait(80)
                root.openEditor(); QTest.qWait(100)
                app = root.property('appWindow')
                self.assertTrue(app.isVisible(), str(errors))
                self.assertEqual((app.width(),app.height()),(580,510))
                # Ending edit mode from outside closes this same window, including
                # the asynchronous geometry-capture path and its deadline.
                app.setProperty('nativeGeometry', True)
                root.endEditing(); QTest.qWait(30)
                self.assertTrue(not isValid(app) or not app.isVisible())
                QTest.qWait(1250)
            finally:
                root.close(); engine.deleteLater(); QTest.qWait(30)
            self.assertFalse(errors, '\n'.join(errors))

class EditorGeometry(unittest.TestCase):
    def setUp(self):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader('editor_geometry', str(ROOT/'linux/libexec/monet-editor-window'))
        self.module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(self.module)

    def test_restore_across_output_origins_and_disconnection(self):
        # Logical geometry is independent of physical monitor density.
        first = dict(name='left', x=-1920, y=0, width=1920, height=1080)
        second = dict(name='retina', x=0, y=0, width=1512, height=902)
        saved = dict(screen='left', area=first, rect=dict(x=-1800,y=100,width=900,height=800))
        self.assertEqual(self.module.placement(saved,[first,second],second), saved['rect'])
        self.assertEqual(self.module.placement(saved,[second],second),dict(x=120,y=100,width=900,height=800))
        small = dict(name='retina',x=0,y=0,width=640,height=480)
        self.assertEqual(self.module.placement(saved,[small],small),dict(x=0,y=0,width=640,height=480))

    def test_capture_and_restore_only_the_exact_editor_window(self):
        from urllib.parse import quote
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            self.module.STATE = Path(directory)
            info = dict(id='a'*32, rect=dict(x=300,y=100,width=600,height=700), area=dict(x=0,y=0,width=1400,height=900), screen='one', mode=0,
                        outputs=[dict(name='one',x=0,y=0,width=1400,height=900)])
            runner = Mock(return_value=info)
            self.assertTrue(self.module.run('capture','Panel-8',quote('Desktop layout'),runner=runner)['ok'])
            self.assertIn('w.normalWindow',runner.call_args.args[0])
            self.assertTrue(self.module.run('restore','Panel-8','Desktop%20layout','a'*32,runner=runner)['ok'])
            self.assertIn('String(w.internalId) === "'+'a'*32+'"',runner.call_args.args[0])
            self.assertIn('w.frameGeometry =',runner.call_args.args[0])
            info['mode'] = 3
            saved = (Path(directory)/'Panel-8.json').read_text()
            self.module.run('capture','Panel-8','Desktop%20layout',runner=runner)
            self.assertEqual((Path(directory)/'Panel-8.json').read_text(),saved)
            self.module.run('restore','Panel-8','Desktop%20layout',runner=runner)
            self.assertIn('w.setMaximize(true,true,',runner.call_args.args[0])
            runner.reset_mock()
            self.assertTrue(self.module.run('activate','Panel-8','Desktop%20layout','a'*32,runner=runner)['ok'])
            self.assertIn('w.minimized = false',runner.call_args.args[0])
            self.assertIn('workspace.activeWindow = w',runner.call_args.args[0])
            runner.reset_mock()
            for key in ('../other','Panel-abc','Panel-8;true'):
                self.assertFalse(self.module.run('restore',key,'Widgets',runner=runner)['ok'])
            runner.assert_not_called()
