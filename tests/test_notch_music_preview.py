"""Playback fits the island and temporary hover never becomes an accidental open."""
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView, QQuickItem
from PySide6.QtTest import QTest

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


class MusicPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, body):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        source = Path(folder.name) / 'Panel.qml'
        source.write_text('import QtQuick\nimport QtQuick.Controls\nimport "' + UI.as_uri() + '" as Monet\n' + body)
        view = QQuickView()
        errors = []
        view.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
        view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.show()
        QTest.qWait(80)
        def close():
            view.close()
            view.deleteLater()
            QTest.qWait(30)
        self.addCleanup(close)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        return view, view.rootObject()

    def item(self, root, name):
        item = root.findChild(QQuickItem, name)
        self.assertIsNotNone(item, 'missing item ' + name)
        self.assertTrue(item.isVisible(), 'hidden item ' + name)
        return item

    def click(self, view, item):
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
        QTest.qWait(40)

    def test_edit_glow_follows_notch_and_preserves_native_click_target(self):
        view, root = self.scene('''Item {
            id: panel; width: 260; height: 80
            property var layoutManager: ({})
            property var configOverlay: null
            property bool editing: true
            MouseArea {
                id: target; objectName: "panelClickTarget"
                anchors.fill: parent; hoverEnabled: true
                Rectangle { id: nativeFill; anchors.fill: parent; color: "blue"; opacity: 0.5 }
            }
            Item {
                id: applet; anchors.fill: parent
                Monet.IslandSurface {
                    x: 40; y: 20; width: 178; height: 25; shoulder: 5; chin: 8
                    Monet.NotchEditHighlight {
                        id: glow; objectName: "editGlow"; anchors.fill: parent
                        applet: applet; active: panel.editing
                        shoulder: parent.shoulder; chin: parent.chin
                    }
                }
            }
            readonly property bool nativeVisible: nativeFill.visible
            readonly property bool clickTargetEnabled: target.enabled
            function resizeNotch() { glow.parent.width = 244; glow.parent.height = 32 }
        }''')
        glow = self.item(root, 'editGlow')
        self.assertFalse(root.property('nativeVisible'))
        self.assertTrue(root.property('clickTargetEnabled'))
        self.assertEqual((glow.width(), glow.height()), (178,25))
        root.resizeNotch(); QTest.qWait(30)
        self.assertEqual((glow.width(), glow.height()), (244,32))
        # Returning the applet to a shared taskbar restores the native hover.
        glow.setProperty('standalone', False); QTest.qWait(30)
        self.assertTrue(root.property('nativeVisible'))
        root.setProperty('editing', False); QTest.qWait(30)
        self.assertFalse(glow.isVisible())

    def music(self):
        return self.scene('''Item {
            id: fixture; width: 432; height: 193
            property string called: ""
            property int route: -1
            readonly property int testVolume: output.volume
            readonly property bool outputMuted: output.muted
            function i18n(s) { return s }
            ListModel { id: sources; property int currentIndex: 0
                ListElement { identity: "Automatic"; track: ""; iconName: "" }
                ListElement { identity: "A music source with a long title"; track: "Track"; iconName: "" }
            }
            QtObject {
                id: player
                property string track: "A song title that is far too long to fit on one line 🎵"
                property string artist: "An artist with a long name"
                property string identity: "A music source with a long title"
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
            QtObject { id: output; objectName:"fakeOutput"; property int volume: 32768; property bool muted:false }
            Component.onCompleted: music.children.find(child => child.objectName === "notchNowPlaying").output = output
            Monet.Music { id: music; objectName:"music"; anchors.fill: parent; player: player; sources: sources; playing: true; view: 0
                formatDuration: s=>Math.floor(s/60)+":"+String(Math.floor(s%60)).padStart(2,"0")
                onViewRequested: index=>fixture.route=index
            }
        }''')

    def test_responsive_layout_contains_every_control_and_uses_remaining_time(self):
        view, root = self.music()
        names = ['Artwork','Title','Previous','Play','Next','Lyrics','Queue','Mixer','Remaining']
        for width in (288, 324, 369, 370, 432, 608):
            root.setWidth(width)
            root.setHeight(257 if width < 370 else 193)
            QTest.qWait(40)
            for suffix in names:
                item = self.item(root, 'notchMusic'+suffix)
                top = item.mapToScene(QPointF(0,0))
                bottom = item.mapToScene(QPointF(item.width(),item.height()))
                self.assertGreaterEqual(top.x(), -0.1, (width,suffix,top))
                self.assertGreaterEqual(top.y(), -0.1, (width,suffix,top))
                self.assertLessEqual(bottom.x(), width+0.1, (width,suffix,bottom))
                self.assertLessEqual(bottom.y(), root.height()+0.1, (width,suffix,bottom))
            art = self.item(root,'notchMusicArtwork')
            title = self.item(root,'notchMusicTitle')
            self.assertLessEqual(art.mapToScene(QPointF(art.width(),0)).x(), title.mapToScene(QPointF(0,0)).x())
        self.assertTrue(self.item(root, 'notchMusicRemaining').property('text').startswith('−'))

    def test_details_and_source_menu_work_from_main_page(self):
        view, root = self.music()
        for suffix, route in [('Lyrics',1),('Queue',2),('Mixer',3)]:
            self.click(view,self.item(root,'notchMusic'+suffix))
            self.assertEqual(root.property('route'),route)
        self.click(view,self.item(root,'notchPlaybackSource'))
        menu=root.findChild(QObject,'notchPlaybackSourceMenu')
        self.assertTrue(menu.property('visible'))
        QTest.keyClick(view,Qt.Key_Escape)
        QTest.qWait(200)
        self.assertFalse(menu.property('visible'))

    def test_volume_and_mute_write_only_the_selected_output(self):
        view,root=self.music()
        QTest.qWait(30)
        self.click(view,self.item(root,'notchMusicMute'))
        self.assertTrue(root.property('outputMuted'))
        slider=self.item(root,'notchMusicVolume')
        QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,slider.mapToScene(QPointF(slider.width()*.75,slider.height()/2)).toPoint())
        QTest.qWait(30)
        self.assertFalse(root.property('outputMuted'))
        self.assertGreater(root.property('testVolume'),44000)
        self.assertLess(root.property('testVolume'),54000)

    def hover(self):
        view, root = self.scene('''Item {
            id: fixture; width: 300; height: 300
            property bool opened: false
            property int clicks: 0
            property int adoptions: 0
            TextField { id: editor; objectName:"editor"; x:200;y:250;width:95;height:30 }
            Rectangle { x:0;y:0;width:100;height:30
                HoverHandler { id: pill; blocking:false }
            }
            Rectangle { x:0;y:40;width:150;height:160;visible:fixture.opened
                HoverHandler { id: surface; blocking:false }
                Item { anchors.fill:parent;z:10000
                    PointHandler { onActiveChanged: if(active) preview.adopt() }
                }
                Button { x:20;y:20;width:100;height:40; text:"Play"; onClicked:fixture.clicks++ }
            }
            Monet.NotchHoverPreview {
                id: preview; objectName:"hover"
                opened:fixture.opened;overPill:pill.hovered;overPreview:surface.hovered
                onRequested:fixture.opened=true
                onDismissed:fixture.opened=false
                onAdopted:fixture.adoptions++
            }
        }''')
        editor = self.item(root,'editor')
        editor.forceActiveFocus()
        QTest.mouseMove(view,QPoint(250,220))
        return view,root,root.findChild(QObject,'hover')

    def test_hover_waits_previews_without_focus_loss_and_dismisses_after_crossing_gap(self):
        view, root, hover = self.hover()
        QTest.mouseMove(view,QPoint(50,15));QTest.qWait(150)
        self.assertFalse(root.property('opened'))
        QTest.qWait(230)
        self.assertTrue(root.property('opened'))
        self.assertTrue(self.item(root,'editor').hasActiveFocus())
        QTest.mouseMove(view,QPoint(50,35));QTest.qWait(150)
        QTest.mouseMove(view,QPoint(100,140));QTest.qWait(470)
        self.assertTrue(root.property('opened'))
        QTest.mouseMove(view,QPoint(250,220));QTest.qWait(480)
        self.assertFalse(root.property('opened'))

    def test_click_adopts_preview_without_swallowing_child_click_and_disabling_hover_closes_only_preview(self):
        view, root, hover = self.hover()
        QTest.mouseMove(view,QPoint(50,15));QTest.qWait(380)
        QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(70,80))
        self.assertEqual(root.property('adoptions'),1)
        self.assertEqual(root.property('clicks'),1)
        QTest.mouseMove(view,QPoint(250,220));QTest.qWait(480)
        self.assertTrue(root.property('opened'))
        hover.setProperty('allowed',False);QTest.qWait(50)
        self.assertTrue(root.property('opened'))
        root.setProperty('opened',False);hover.setProperty('allowed',True)
        QTest.mouseMove(view,QPoint(50,15));QTest.qWait(380)
        self.assertTrue(hover.property('previewing'))
        hover.setProperty('allowed',False);QTest.qWait(50)
        self.assertFalse(root.property('opened'))

    def test_explicit_close_requires_pointer_to_leave_and_pin_holds_preview(self):
        view, root, hover = self.hover()
        QTest.mouseMove(view,QPoint(50,15));QTest.qWait(380)
        root.setProperty('opened',False);QTest.qWait(380)
        self.assertFalse(root.property('opened'))
        QTest.mouseMove(view,QPoint(250,220));QTest.mouseMove(view,QPoint(50,15));QTest.qWait(380)
        hover.setProperty('held',True)
        QTest.mouseMove(view,QPoint(250,220));QTest.qWait(480)
        self.assertTrue(root.property('opened'))
        hover.setProperty('held',False);QTest.qWait(480)
        self.assertFalse(root.property('opened'))
