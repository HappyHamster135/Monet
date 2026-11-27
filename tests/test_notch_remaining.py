"""Exercise compact secondary pages with native KDE controls and isolated data."""
from pathlib import Path
import tempfile
import shutil
import unittest

from tests.test_notch_timer import settings_properties
try:
    from PySide6.QtCore import QObject, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


@unittest.skipUnless(QQuickView, 'requires Qt Quick')
class RemainingPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle('org.kde.desktop')
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, body, width=432):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        source = Path(folder.name) / 'Panel.qml'
        ui = Path(folder.name) / 'ui'
        shutil.copytree(UI, ui)
        shared = UI.parents[4] / 'monet/widgets'
        shutil.copy2(shared / 'GraphicsPolicy.qml', ui / 'GraphicsPolicy.qml')
        source.write_text('import QtQuick\nimport "' + ui.as_uri() + '" as Monet\nItem {\n'
                          + f'width: {width}; height: 257\n'
                          + 'function i18n(s,...args) { return s.replace(/%([1-9])/g,(_,n)=>args[Number(n)-1]) }\n'
                          + body + '\n}')
        view = QQuickView()
        errors = []
        view.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
        view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.show()
        QTest.qWait(100)
        self.addCleanup(view.close)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        return view, view.rootObject()

    def item(self, root, name):
        pending = [root]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail('missing item ' + name)

    def click(self, view, item):
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier,
                         item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint())
        QTest.qWait(60)

    def test_metrics_open_and_close_live_history_without_inventing_missing_values(self):
        view, root = self.scene('Monet.IslandSystem { objectName: "system"; anchors.fill: parent }')
        system = self.item(root, 'system')
        for index in range(4):
            self.click(view, self.item(root, f'notchMetric-{index}'))
            self.assertEqual(system.property('selected'), index)
            self.assertTrue(system.property('editingEvent'))
            chart = self.item(root, 'notchMetricChart')
            self.assertGreater(chart.height(), 40)
            self.click(view, self.item(root, 'notchMetricBack'))
            self.assertFalse(system.property('editingEvent'))
        view, root = self.scene('''Monet.IslandChart {
            objectName: "chart"; anchors.fill: parent
            Component.onCompleted: { for (let i=0;i<70;i++) append(i); append(NaN) }
        }''')
        samples = self.item(root, 'chart').property('samples').toVariant()
        self.assertEqual(len(samples), 60)
        self.assertEqual(samples[-2], 69)
        self.assertIsNone(samples[-1])

    def test_timer_presets_set_duration_and_do_not_start_the_timer(self):
        view, root = self.scene('''QtObject { id: config; objectName: "settings"; ''' + settings_properties() + ''' }
            Monet.NotchTimer { id: timer; objectName: "timer"; settings: config }
            Monet.TimePage { anchors.fill: parent; timer: timer; now: 0; message: ""; formatDuration: s=>String(s); offerAwake: true }
        ''', 288)
        self.click(view, self.item(root, 'notchTimerPreset-45'))
        self.assertEqual(root.findChild(QObject, 'settings').property('timerMinutes'), 45)
        self.assertFalse(root.findChild(QObject, 'timer').property('active'))

    def test_clipboard_literal_search_pin_copy_and_bounded_edit_keep_original_entry(self):
        view, root = self.scene('''ListModel {
            id: fixture
            property bool starredOnly: false
            property string copied: ""
            function moveToTop(uuid) { copied = uuid }
            function invokeAction(uuid) {}
            ListElement { uuid: "one"; display: "A [literal] match"; type: 2; starred: false; decoration: "" }
            ListElement { uuid: "two"; display: "Other text"; type: 2; starred: false; decoration: "" }
        }
        property alias copied: fixture.copied
        property bool hidden: false
        Monet.IslandClipboardHistory { objectName: "clipboard"; anchors.fill: parent; historyModel: fixture; onRequestHidePopup: parent.hidden = true }
        ''', 288)
        search = self.item(root, 'notchClipboardSearch')
        search.setProperty('text', '[literal]')
        QTest.qWait(100)
        self.assertEqual(self.item(root, 'notchClipboardEntries').property('count'), 1)
        self.click(view, self.item(root, 'notchClipboardPin-0'))
        self.assertTrue(self.item(root, 'notchClipboardPin-0').property('checked'))
        row = self.item(root, 'notchClipboardRow-0')
        row.edit()
        QTest.qWait(300)
        editor = self.item(root, 'notchClipboardEditor')
        editor.setProperty('text', '漢字🙂 ' * 1000 + 'z' * 800)
        QTest.qWait(100)
        self.assertLessEqual(editor.width(), 288)
        self.assertGreater(editor.height(), 269)
        self.click(view, self.item(root, 'notchClipboardSave'))
        QTest.qWait(300)
        self.assertFalse(self.item(root, 'clipboard').property('inDetail'))
        self.assertEqual(root.property('copied'), 'one')
        search.setProperty('text', '')
        QTest.qWait(100)
        self.item(root, 'notchClipboardRow-0').copy()
        self.assertTrue(root.property('hidden'))

    def test_media_timeline_spans_the_narrow_panel_with_long_track_labels(self):
        view, root = self.scene('''ListModel { id: fakeSources; property int currentIndex: 0 }
        property int requested: -1
        QtObject {
            id: fakePlayer
            property string track: "A song title that is much longer than the notch can display"
            property string artist: "An artist with a long name"
            property string identity: "Music player"
            property string artUrl: ""
            property real length: 240000000
            property real position: 60000000
            property real rate: 1
            property bool canSeek: false
            property bool canPlay: true
            property bool canPause: true
            property bool canControl: true
            property bool canGoNext: true
            property bool canGoPrevious: true
            property int shuffle: 0
            property int loopStatus: 0
            property int instancePid: 0
            function updatePosition() {}
        }
        Monet.Music { anchors.fill: parent; player: fakePlayer; sources: fakeSources; playing: true; view: 0; formatDuration: s=>Math.floor(s/60)+":"+String(Math.floor(s%60)).padStart(2,"0"); onViewRequested: index=>parent.requested=index }
        ''', 288)
        slider = self.item(root, 'notchPlaybackPosition')
        self.assertGreater(slider.width(), 200)
        self.assertLessEqual(slider.mapToScene(QPointF(slider.width(),0)).x(), 288)
        for name, route in (('Lyrics', 1), ('Queue', 2), ('Mixer', 3)):
            self.click(view, self.item(root, 'notchMusic'+name))
            self.assertEqual(root.property('requested'), route)

    def test_agent_quota_long_labels_and_capture_filter_fit_small_surface(self):
        view, root = self.scene('''Monet.AgentDetail {
            anchors.fill: parent; provider: "codex"; presented: false
            result: ({ok:true,enabled:true,state:"ready",summary:"Connected account",checked:"Updated just now",rows:[
                {name:"Weekly allowance for a very long account name",remaining:"15% remaining",value:15,reset:"Resets Friday at 14:30"}]})
        }''', 288)
        view, root = self.scene('''Monet.IslandCaptures {
            objectName: "captures"; anchors.fill: parent; helper: "/usr/bin/false"
            images: true; videos: true; shelf: true; showCopied: false
        }''', 288)
        captures = self.item(root, 'captures')
        captures.setProperty('recent', [{'name':'Video with a long name.mp4','url':'file:///nonexistent.mp4','video':True}])
        captures.setProperty('filter', 1)
        QTest.qWait(50)
        self.assertEqual(self.item(root, 'notchCaptureGrid').property('count'), 0)
        captures.setProperty('filter', 2)
        QTest.qWait(50)
        self.assertEqual(self.item(root, 'notchCaptureGrid').property('count'), 1)
