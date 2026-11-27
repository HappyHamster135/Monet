"""Open popups in a Plasma dialog, including its content-before-window sizing."""
from pathlib import Path
import tempfile
import unittest

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
class Popups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle('org.kde.desktop')
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, contents):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'Popup.qml'
        path.write_text('''import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.core as PlasmaCore
import "''' + UI.as_uri() + '''" as Monet
Item {
    width: 1; height: 1
    function i18n(s) { return s }
    PlasmaCore.Dialog {
        objectName: "dialog"; visible: true
        backgroundHints: PlasmaCore.Dialog.NoBackground
        mainItem: Item {
            objectName: "surface"; width: 464; height: 316
            Monet.IslandPopupOverlay {}
            Item {
                id: viewport; objectName: "bounds"
                x: 25; y: 46; width: parent.width - 50; height: parent.height - 59
''' + contents + '\n}\n}\n}\n}')
        host = QQuickView()
        errors = []
        host.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
        host.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(host.status(), QQuickView.Ready, [e.toString() for e in host.errors()])
        root = host.rootObject()
        dialog = root.findChild(QObject, 'dialog')
        self.addCleanup(host.close)
        self.addCleanup(dialog.close)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        # Retain the engine while the separate Plasma window is being tested.
        self.host = host
        QTest.qWait(100)
        return dialog, root

    def assert_bounded(self, popup, bounds):
        # Popup.x/y alone miss displacement of the window's actual overlay.
        content = popup.property('contentItem')
        background = popup.property('background')
        for item in (content, background):
            point = item.mapToItem(bounds, QPointF())
            self.assertGreaterEqual(point.x(), -0.1)
            self.assertGreaterEqual(point.y(), -0.1)
            self.assertLessEqual(point.x() + item.width(), bounds.width() + 0.1)
            self.assertLessEqual(point.y() + item.height(), bounds.height() + 0.1)
        return content

    def test_last_category_opens_inside_plasma_notch_after_resize_and_reopen(self):
        dialog, root = self.scene('''
            Monet.ToolDirectory {
                id: tools; anchors.fill: parent
                rows: [{key:"sample",label:"Sample",terms:"",group:"desktop",icon:"document-edit"}]
                groups: ["all","favorites","files","writing","input","sound","capture","display","system","desktop"].map(key=>({key:key,label:key}))
                hidden: []; favorites: []; group: "desktop"; query: ""
                onFilterChanged: (g,q) => { group=g; query=q }
            }
''')
        bounds = root.findChild(QObject, 'bounds')
        surface = root.findChild(QObject, 'surface')
        choice = root.findChild(QObject, 'notchToolCategory')
        popup = choice.findChild(QObject, 'notchComboPopup')
        for width, height in ((464,316), (338,239), (464,316)):
            surface.setWidth(width)
            surface.setHeight(height)
            QTest.qWait(70)
            for selected in (0, 9):
                choice.setProperty('currentIndex', selected)
                choice.forceActiveFocus()
                QTest.keyClick(dialog, Qt.Key_Space)
                QTest.qWait(250)
                self.assertTrue(popup.property('opened'))
                content = self.assert_bounded(popup, bounds)
                self.assertEqual(content.height() % 32, 0)
                current = content.property('currentItem')
                point = current.mapToItem(content, QPointF())
                self.assertGreaterEqual(point.y(), -0.1)
                self.assertLessEqual(point.y() + current.height(), content.height() + 0.1)
                QTest.keyClick(dialog, Qt.Key_Escape)
                QTest.qWait(250)
                self.assertFalse(popup.property('visible'))
                self.assertTrue(dialog.isVisible())
            dialog.hide()
            dialog.show()
            QTest.qWait(70)

    def test_long_bottom_menu_scrolls_to_last_action_and_closes_with_page(self):
        dialog, root = self.scene('''
            property int chosen: -1
            C.Button {
                id: trigger; objectName: "trigger"; width: 28; height: 28
                anchors.right: parent.right; anchors.bottom: parent.bottom
                onClicked: menu.open()
                Monet.IslandMenu {
                    id: menu; objectName: "menu"; bounds: viewport; anchorItem: trigger
                    preferredWidth: 500
                    Instantiator {
                        model: 30
                        delegate: C.MenuItem {
                            required property int index
                            text: "A long action name that needs to remain inside the menu " + index
                            onTriggered: viewport.chosen = index
                        }
                        onObjectAdded: (index,item) => menu.insertItem(index,item)
                        onObjectRemoved: (index,item) => menu.removeItem(item)
                    }
                }
            }
''')
        bounds = root.findChild(QObject, 'bounds')
        menu = root.findChild(QObject, 'menu')
        menu.open()
        QTest.qWait(250)
        content = self.assert_bounded(menu, bounds)
        self.assertTrue(content.property('interactive'))
        menu.forceActiveFocus(Qt.OtherFocusReason)
        for _ in range(30):
            QTest.keyClick(dialog, Qt.Key_Down)
        QTest.qWait(250)
        self.assertEqual(menu.property('currentIndex'), 29)
        self.assertGreater(content.property('contentY'), 0, {k: content.property(k) for k in ("width","height","contentHeight","count","currentIndex","highlightFollowsCurrentItem")})
        self.assert_bounded(menu, bounds)
        QTest.keyClick(dialog, Qt.Key_Return)
        QTest.qWait(250)
        self.assertEqual(bounds.property('chosen'), 29)
        self.assertFalse(menu.property('visible'))
        menu.open()
        QTest.qWait(250)
        root.findChild(QObject, 'surface').setWidth(338)
        root.findChild(QObject, 'surface').setHeight(239)
        QTest.qWait(100)
        self.assert_bounded(menu, bounds)
        bounds.setVisible(False)
        QTest.qWait(250)
        self.assertFalse(menu.property('visible'))
