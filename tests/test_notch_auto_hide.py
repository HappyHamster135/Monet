"""Pointer reveal stays reachable without moving the panel or taking focus."""
from pathlib import Path
import tempfile
import unittest

# These scenes are required in the desktop job; the CLI job has no Qt runtime.
import importlib.util
if importlib.util.find_spec("PySide6") is None:
    raise unittest.SkipTest("requires the native Qt desktop runtime")

from PySide6.QtCore import QObject, QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


class AutoHide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name) / 'Reveal.qml'
        path.write_text('''import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "''' + UI.as_uri() + '''" as Monet
Item {
    id: scene; width: 300; height: 240
    property bool opened: false
    property bool editing: false
    property bool keyboardUse: false
    property bool hoverPreview: false
    property int clicks: 0
    TextField { id: field; objectName: "field"; x: 180; y: 195; width: 110; height: 32 }
    // Model Plasma's panel, clipped applet host, and translated compact content.
    // The reveal target belongs to the panel, outside the clipped applet tree.
    Item {
      id: panel; x: 50; width: 178; height: 44
      Item {
        y: 8; width: parent.width; height: 24; clip: true
    AbstractButton {
        id: pill; objectName: "pill"; width: 178; height: 24
        onClicked: { scene.clicks++; scene.opened = true; preview.adopt() }
        background: Rectangle { y: -8; height: 25; color: "black"; opacity: conceal.shown ? 1 : 0 }
        contentItem: RowLayout {
            transform: Translate { y: -8 }
            Label { text: "Music"; Layout.fillWidth: true }
            Button { objectName: "quick"; text: "Play"; visible: conceal.hovered; onClicked: scene.clicks++ }
        }
        Monet.NotchAutoHide {
            id: conceal; objectName: "conceal"; parent: panel; anchors.fill: parent; z: 1000
            automatic: true
            occupied: scene.opened || scene.editing || scene.keyboardUse
        }
    }
      }
    }
    Rectangle {
        x: 50; y: 40; width: 178; height: 130; visible: scene.opened
        HoverHandler { id: expandedPointer; blocking: false }
    }
    Monet.NotchHoverPreview {
        id: preview
        allowed: scene.hoverPreview; opened: scene.opened
        overPill: conceal.hovered; overPreview: expandedPointer.hovered
        onRequested: scene.opened = true
        onDismissed: scene.opened = false
    }
}''')
        self.view = QQuickView(); self.errors = []
        self.view.engine().warnings.connect(lambda errors: self.errors.extend(e.toString() for e in errors))
        self.view.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(self.view.status(), QQuickView.Ready, self.errors)
        self.view.show(); self.root = self.view.rootObject()
        self.conceal = self.root.findChild(QObject, 'conceal')
        self.field = self.root.findChild(QObject, 'field')
        self.field.forceActiveFocus()
        QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(650)

    def tearDown(self):
        self.view.close(); self.view.deleteLater(); QTest.qWait(20)
        self.folder.cleanup()
        self.assertFalse(self.errors, '\n'.join(self.errors))

    def test_whole_notch_reveals_without_clicking_even_outside_clipped_applet(self):
        self.assertFalse(self.conceal.property('shown'))
        for point in ((51, 2), (100, 2), (226, 2), (100, 20), (100, 42)):
            with self.subTest(point=point):
                QTest.mouseMove(self.view, QPoint(*point)); QTest.qWait(20)
                self.assertTrue(self.conceal.property('hovered'))
                self.assertTrue(self.conceal.property('shown'))
                self.assertTrue(self.field.hasActiveFocus())
                QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(650)
                self.assertFalse(self.conceal.property('shown'))
        self.assertEqual(self.root.property('clicks'), 0)

    def test_reveal_keeps_geometry_focus_and_survives_a_brief_pointer_exit(self):
        pill = self.root.findChild(QObject, 'pill')
        geometry = (pill.x(), pill.y(), pill.width(), pill.height())
        self.assertFalse(self.conceal.property('shown'))
        QTest.mouseMove(self.view, QPoint(100, 20)); QTest.qWait(40)
        self.assertTrue(self.conceal.property('shown'))
        self.assertTrue(self.field.hasActiveFocus())
        QTest.mouseMove(self.view, QPoint(100, 24)); QTest.qWait(650)
        self.assertTrue(self.conceal.property('shown'))
        QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(100)
        self.assertTrue(self.conceal.property('shown'))
        QTest.mouseMove(self.view, QPoint(100, 20)); QTest.qWait(650)
        self.assertTrue(self.conceal.property('shown'))
        QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(650)
        self.assertFalse(self.conceal.property('shown'))
        self.assertEqual((pill.x(), pill.y(), pill.width(), pill.height()), geometry)

    def test_revealed_quick_control_does_not_flicker_or_block_clicks(self):
        QTest.mouseMove(self.view, QPoint(100, 20)); QTest.qWait(20)
        button = self.root.findChild(QObject, 'quick')
        center = button.mapToScene(button.boundingRect().center()).toPoint()
        QTest.mouseMove(self.view, center); QTest.qWait(650)
        self.assertTrue(self.conceal.property('hovered'))
        self.assertTrue(button.isVisible())
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, center)
        self.assertEqual(self.root.property('clicks'), 1)
        self.assertFalse(self.root.property('opened'))

    def test_click_open_editing_keyboard_and_disabling_auto_hide_keep_it_visible(self):
        QTest.mouseMove(self.view, QPoint(100, 2)); QTest.qWait(40)
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, QPoint(100, 20))
        self.assertEqual(self.root.property('clicks'), 1)
        QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(650)
        self.assertTrue(self.conceal.property('shown'))
        self.root.setProperty('opened', False); QTest.qWait(650)
        self.assertFalse(self.conceal.property('shown'))
        for reason in ('editing', 'keyboardUse'):
            self.root.setProperty(reason, True); QTest.qWait(650)
            self.assertTrue(self.conceal.property('shown'))
            self.root.setProperty(reason, False); QTest.qWait(650)
            self.assertFalse(self.conceal.property('shown'))
        self.conceal.setProperty('automatic', False); QTest.qWait(650)
        self.assertTrue(self.conceal.property('shown'))

    def test_hover_preview_remains_usable_then_closes_and_hides(self):
        self.root.setProperty('hoverPreview', True)
        QTest.mouseMove(self.view, QPoint(100, 2)); QTest.qWait(380)
        self.assertTrue(self.root.property('opened'))
        self.assertTrue(self.field.hasActiveFocus())
        QTest.mouseMove(self.view, QPoint(100, 120)); QTest.qWait(650)
        self.assertTrue(self.root.property('opened'))
        self.assertTrue(self.conceal.property('shown'))
        QTest.mouseMove(self.view, QPoint(270, 180)); QTest.qWait(1150)
        self.assertFalse(self.root.property('opened'))
        self.assertFalse(self.conceal.property('shown'))
