"""Operate the floating widget picker without modifying the user's desktop."""
from pathlib import Path
import tempfile
import unittest
from tests import test_settings_navigation as settings
from tests.test_look import ROOT

if settings.QT:
    from PySide6.QtCore import QPoint, QPointF, QUrl, Qt, QObject, Slot, QTimer
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class WidgetGallery(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        source = '''
import QtQuick
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import "@PANEL@/EditorWindows.js" as EditorWindows
Window {
    id: root; width: 1280; height: 800
    function i18nd(domain, text) { return text }
    function i18ndc(domain, context, text, name) { return text.replace("%1", name) }
    function i18ndp(domain, one, many, count) { return count === 1 ? one : many.replace("%1", count) }
    property QtObject widgetExplorer: backend
    property var galleryWindow: null
    property string added: backend.added
    function dragMime(name) { return control(name).Drag.mimeData["text/x-plasmoidservicename"] }
    function control(name) {
        const pending = [galleryWindow.contentItem]
        while (pending.length) {
            const item = pending.pop()
            if (item.objectName === name) return item
            if (item.visible) for (const child of item.children) pending.push(child)
        }
        return null
    }
    function unloadGallery() { galleryWindow?.close() }
    function loadGallery() {
        const host = EditorWindows.forParent(stableParent)
        host.openWidgets(targetContainment, root, pendingUninstallTimer, "@EXPLORER@/MonetWidgetExplorer.qml")
        galleryWindow = host.widgetWindow
        galleryWindow.nativeGeometry = false
    }
    Item { id: stableParent }
    Component.onCompleted: loadGallery()
    QtObject { id: pendingUninstallTimer; property bool running: true }
    QtObject {
        id: targetContainment
        property int id: 7
        property int containmentType: 1
        property bool userConfiguring: true
        property var applets: []
        property QtObject corona: QtObject { property bool editMode: true }
        function internalAction(name) { return null }
    }
    ListModel {
        id: rows
        property string searchTerm: ""
        ListElement { pluginName: "org.monet.clock"; name: "Clock"; description: "The time and date"; decoration: "chronometer"; screenshot: ""; isSupported: true }
        ListElement { pluginName: "org.kde.plasma.calculator"; name: "Calculator"; description: "Quick calculations"; decoration: "accessories-calculator"; screenshot: ""; isSupported: true }
    }
    QtObject {
        id: backend
        property QtObject containment
        property QtObject widgetsModel: rows
        property string added: ""
        signal shouldClose()
        function addApplet(name) { added = name }
    }

}
'''.replace('@EXPLORER@', (ROOT/'linux/share/monet/explorer').as_uri()).replace('@PANEL@', (ROOT/'linux/share/monet/panel').as_uri())
        gallery_page = Path(self.temp.name)/'MonetWidgetExplorer.qml'
        gallery_page.write_text((ROOT/'linux/share/monet/explorer/MonetWidgetExplorer.qml').read_text().replace('@DATADIR@',str(ROOT/'linux/share')))
        source = source.replace((ROOT/'linux/share/monet/explorer/MonetWidgetExplorer.qml').as_uri(), gallery_page.as_uri())
        fixture = Path(self.temp.name)/'gallery.qml'; fixture.write_text(source)
        self.engine = QQmlApplicationEngine(); self.errors = []
        class Words(QObject):
            @Slot(str, str, result=str)
            def i18nd(self, domain, text): return text
            @Slot(str, str, str, str, result=str)
            def i18ndc(self, domain, context, text, name): return text.replace("%1",name)
            @Slot(str, str, str, int, result=str)
            def i18ndp(self, domain, one, many, count): return one if count == 1 else many.replace("%1", str(count))
        self.words = Words(); self.engine.rootContext().setContextObject(self.words)
        self.engine.warnings.connect(lambda messages: self.errors.extend(message.toString() for message in messages))
        self.engine.load(QUrl.fromLocalFile(str(fixture)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.root = self.engine.rootObjects()[0]
        self.window = self.root.property('galleryWindow')
        self.window.requestActivate(); QTest.qWait(250)
        self.assertFalse(self.errors, '\n'.join(self.errors))

    def tearDown(self):
        self.root.unloadGallery(); self.root.close()
        self.engine.deleteLater(); QTest.qWait(30)
        self.assertFalse(self.errors, '\n'.join(self.errors))

    def test_categories_and_add_keep_a_bounded_floating_window(self):
        picker = self.root.control('monetWidgetPicker')
        self.assertTrue(self.window.flags() & Qt.FramelessWindowHint)
        self.assertGreater(self.window.property("titleHeight"), 0)
        before = self.window.geometry()
        for name in ('moreWidgetCategory','monetWidgetCategory'):
            button = self.root.control(name); button.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(self.window, Qt.Key_Space); QTest.qWait(40)
            self.assertEqual(self.window.geometry(), before)
        picker.addFirst()
        self.assertEqual(self.root.property('added'),'org.monet.clock')
        # Dragging widgets preserves the input-through contract with Desktop.qml.
        picker.setProperty('draggingWidget',True)
        self.assertTrue(picker.property('preventWindowHide'))
        self.assertTrue(picker.property('outputOnly'))
        picker.setProperty('draggingWidget',False)
        self.root.unloadGallery(); QTest.qWait(50)

    def test_resize_reopen_and_switch_apps_preserve_window(self):
        self.window.resize(560,490); QTest.qWait(250)
        self.root.show(); self.root.requestActivate(); QTest.qWait(50)
        self.assertTrue(self.window.isVisible())
        before = self.window.size()
        picker = self.root.control('monetWidgetPicker')
        self.assertEqual(picker.width(), self.window.width())
        self.assertEqual(picker.height(), self.window.height() - self.window.property("titleHeight"))
        self.root.unloadGallery(); QTest.qWait(60)
        self.root.loadGallery(); QTest.qWait(150)
        self.window = self.root.property('galleryWindow')
        self.assertEqual(self.window.size(),before)

    def test_cancelled_native_drag_restores_picker_and_keeps_widget_payload(self):
        self.root.setGeometry(450,40,320,340); self.root.show()
        self.window.setGeometry(20,40,420,600); self.window.show(); self.window.requestActivate()
        QTest.qWait(150)
        card = self.root.control('widgetCard-org.monet.clock')
        self.assertIsNotNone(card)
        start = card.mapToScene(QPointF(card.width()/2,90)).toPoint()
        destination = self.root.position() + QPoint(150,150) - self.window.position()
        trace = []
        picker = self.root.control("monetWidgetPicker")
        picker.draggingWidgetChanged.connect(lambda: trace.append(picker.property("draggingWidget")))
        QTest.mousePress(self.window,Qt.LeftButton,Qt.NoModifier,start)
        # Offscreen's native drag backend cancels instead of contacting a live
        # compositor. Exercise the real handler and cancellation cleanup.
        QTimer.singleShot(160,lambda: QTest.mouseMove(self.window,destination))
        QTimer.singleShot(350,lambda: QTest.mouseRelease(self.window,Qt.LeftButton,Qt.NoModifier,destination))
        QTest.mouseMove(self.window,start+QPoint(30,20))
        QTest.qWait(700)
        self.assertEqual(trace,[True,False])
        self.assertEqual(self.root.dragMime('widgetCard-org.monet.clock'),'org.monet.clock')
        self.assertEqual(self.root.property('added'),'')
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.root.control('monetWidgetPicker').property('draggingWidget'))

    def test_desktop_disappearing_before_picker_closes_is_safe(self):
        self.window.setProperty('desktopRoot', None)
        QTest.qWait(30)
        self.root.unloadGallery()
        QTest.qWait(60)
        self.assertFalse(self.errors, '\n'.join(self.errors))
