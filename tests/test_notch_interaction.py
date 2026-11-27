"""Exercise deliberate edits, background dragging, and persistent notch bindings."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests import test_notch_compact_tools as compact
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtQuick import QQuickView
from PySide6.QtGui import QKeySequence, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QComboBox, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QStyleOptionSpinBox, QTextEdit, QVBoxLayout, QWidget)
from window_interaction import install_interaction
from notch_settings import NotchSettingsWindow
from window import Window
import notch_shortcuts as shortcuts


class Interaction(unittest.TestCase):
    setUpClass = classmethod(compact.CompactTools.setUpClass.__func__)

    def setUp(self):
        self.area=QScrollArea();self.area.setWidgetResizable(True);self.area.resize(400,230)
        self.policy=install_interaction(self.area)
        self.page=QWidget();layout=QVBoxLayout(self.page)
        self.combo=QComboBox();self.combo.addItems(['First','Second','Third']);self.combo.setCurrentIndex(1)
        self.spin=QSpinBox();self.spin.setValue(50)
        self.slider=QSlider(Qt.Horizontal);self.slider.setValue(50)
        self.button=QPushButton('Clickable');self.editor=QTextEdit('Selectable text')
        for control in (self.combo,self.spin,self.slider,self.button,self.editor):layout.addWidget(control)
        layout.addSpacing(500);self.area.setWidget(self.page);self.area.show();QTest.qWait(50)

    def tearDown(self):self.area.close();self.area.deleteLater();QTest.qWait(20)

    def wheel(self,widget,point=None,pixels=None):
        point=point or QPoint(12,widget.height()//2)
        event=QWheelEvent(QPointF(point),QPointF(widget.mapToGlobal(point)),pixels or QPoint(),
            QPoint(0,-120) if pixels is None else QPoint(),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        QApplication.sendEvent(widget,event)

    def test_scroll_over_focused_fields_browses_without_editing(self):
        for control,value in ((self.combo,lambda:self.combo.currentIndex()),(self.spin,self.spin.value),(self.slider,self.slider.value)):
            self.area.verticalScrollBar().setValue(0);control.setFocus();before=value()
            self.wheel(control)
            self.assertEqual(value(),before)
            self.assertGreater(self.area.verticalScrollBar().value(),0)
        self.area.verticalScrollBar().setValue(0)
        self.wheel(self.spin.findChild(QLineEdit),pixels=QPoint(0,-22))
        self.assertEqual(self.spin.value(),50);self.assertGreater(self.area.verticalScrollBar().value(),0)
        self.spin.setFocus();QTest.keyClick(self.spin,Qt.Key_Up);self.assertEqual(self.spin.value(),51)
        self.combo.setFocus();QTest.keyClick(self.combo,Qt.Key_Down);self.assertEqual(self.combo.currentIndex(),2)

    def test_only_spin_arrows_accept_wheel_edits(self):
        self.area.ensureWidgetVisible(self.spin)
        option=QStyleOptionSpinBox();self.spin.initStyleOption(option)
        arrow=self.spin.style().subControlRect(QStyle.CC_SpinBox,option,QStyle.SC_SpinBoxDown,self.spin).center()
        before=self.area.verticalScrollBar().value();self.wheel(self.spin,arrow)
        self.assertEqual(self.spin.value(),49);self.assertEqual(self.area.verticalScrollBar().value(),before)

    def test_new_controls_added_after_opening_are_protected(self):
        late=QComboBox();late.addItems(['A','B','C']);late.setCurrentIndex(1)
        self.page.layout().insertWidget(0,late);QTest.qWait(30)
        self.area.verticalScrollBar().setValue(0);self.wheel(late)
        self.assertEqual(late.currentIndex(),1);self.assertGreater(self.area.verticalScrollBar().value(),0)

    def test_blank_drag_preserves_clicks_and_interactive_content(self):
        self.assertTrue(self.policy.draggable(self.page))
        for widget in (self.button,self.editor.viewport(),self.combo,self.spin):self.assertFalse(self.policy.draggable(widget))
        with patch.object(self.policy,'start_move',return_value=True) as move:
            point=QPoint(10,self.page.height()-40)
            QTest.mousePress(self.page,Qt.LeftButton,Qt.NoModifier,point)
            QTest.mouseMove(self.page,point+QPoint(1,0));move.assert_not_called()
            QTest.mouseMove(self.page,point+QPoint(40,0));move.assert_called_once()
            QTest.mouseRelease(self.page,Qt.LeftButton,Qt.NoModifier,point+QPoint(40,0))
            self.area.setProperty('monetWindowDrag',False)
            self.assertFalse(self.policy.draggable(self.page))
        clicks=[];self.button.clicked.connect(lambda:clicks.append(True));QTest.mouseClick(self.button,Qt.LeftButton)
        self.assertEqual(clicks,[True])


class Shortcuts(unittest.TestCase):
    setUpClass=classmethod(compact.CompactTools.setUpClass.__func__)

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.api=MagicMock();self.api.shortcutKeys.return_value=[];self.api.globalShortcutAvailable.return_value=True
        self.api.setShortcutKeys.return_value=[1];self.api.actionList.return_value=shortcuts.details('radial')
        self.registry=patch.object(shortcuts,'registry',return_value=self.api);self.registry.start()
        self.paths=patch.object(shortcuts,'path_for',side_effect=lambda key:self.root/shortcuts.SHORTCUTS[key][0]);self.paths.start()

    def tearDown(self):self.registry.stop();self.paths.stop();self.folder.cleanup()

    def test_assign_persists_launcher_and_rejects_conflicts_without_changes(self):
        sequence=QKeySequence('Meta+Alt+R');shortcuts.assign('radial',self.root,sequence)
        path=shortcuts.path_for('radial');saved=path.read_bytes();self.assertIn(b'" radial',saved)
        self.api.globalShortcutAvailable.return_value=False
        with self.assertRaisesRegex(ValueError,'already in use'):shortcuts.assign('radial',self.root,QKeySequence('Meta+F9'))
        self.assertEqual(path.read_bytes(),saved);self.assertEqual(self.api.setShortcutKeys.call_count,1)
        with self.assertRaises(ValueError):shortcuts.assign('radial',self.root,QKeySequence('R'))

    def test_failed_registration_restores_previous_binding_and_launcher(self):
        path=shortcuts.path_for('radial');path.write_bytes(b'previous launcher')
        previous=[[[123,0,0,0]]];self.api.shortcutKeys.return_value=previous;self.api.setShortcutKeys.return_value=[]
        with self.assertRaises(ValueError):shortcuts.assign('radial',self.root,QKeySequence('Meta+Alt+R'))
        self.assertEqual(path.read_bytes(),b'previous launcher')
        self.assertEqual(self.api.setShortcutKeys.call_args_list[-1].args[1],previous)

    def test_clear_removes_binding_and_launcher(self):
        path=shortcuts.path_for('radial');path.write_text('saved');self.api.shortcutKeys.return_value=[[[123,0,0,0]]]
        shortcuts.assign('radial',self.root,QKeySequence())
        self.api.unregister.assert_called_once();self.assertFalse(path.exists())

    def test_desktop_signal_normalizes_qvariant_arguments_and_targets_one_notch(self):
        bus=QDBusConnection.sessionBus();self.assertTrue(bus.registerService('org.monet.Utilities'))
        try:
            ui=Path(__file__).resolve().parents[1]/'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'
            scene=self.root/'Shortcut.qml'
            scene.write_text('import QtQuick\nimport "'+ui.as_uri()+'" as Monet\nItem { id:root; property string chosen:""; Monet.NotchShortcut { ownerId:"85"; onRequested:command=>root.chosen=command } }')
            view=QQuickView();view.setSource(QUrl.fromLocalFile(str(scene)))
            self.assertEqual(view.status(),QQuickView.Ready,[e.toString() for e in view.errors()]);QTest.qWait(30)
            for widget,command,expected in [('86','toggle',''),('85','unknown',''),('85','radial',''),('85','toggle','toggle')]:
                message=QDBusMessage.createSignal('/NotchShortcuts','org.monet.Utilities','NotchShortcut')
                message.setArguments([widget,command]);self.assertTrue(bus.send(message));QTest.qWait(40)
                self.assertEqual(view.rootObject().property('chosen'),expected)
            view.close();view.deleteLater();QTest.qWait(20)
        finally:bus.unregisterService('org.monet.Utilities')

    def test_legacy_radial_binding_opens_floating_menu_without_consulting_plasma(self):
        owner=MagicMock()
        with patch.object(shortcuts.dbus,'SessionBus') as bus:
            shortcuts.trigger(owner,'radial')
        owner.wheel.assert_called_once_with('radial');bus.assert_not_called()

    def test_home_exposes_recorders_and_routes_without_writing_preferences(self):
        owner=Window('/usr/libexec',defer_catalog=True);owner.settings=QSettings(str(self.root/'prefs.ini'),QSettings.IniFormat)
        owner.worker=lambda args,done,failed=None,**kw:done(json.dumps([{'id':8,'screen':0}] if args[1]=='notch-screens' else {'ok':True,'mode':'wide','layout':{},'tabs':['tools']}))
        dialog=NotchSettingsWindow(owner);dialog.open_page();QTest.qWait(100)
        self.assertEqual(dialog.navigation.currentItem().data(Qt.UserRole),'overview')
        page=dialog.pages['overview'];self.assertEqual(len(page.shortcuts),2)
        card=page.shortcuts[0];card.edit();QTest.qWait(50)
        self.assertIsNotNone(card.recorder.rootObject())
        card.recorder.rootObject().setProperty('keySequence',QKeySequence('Meta+Alt+R'))
        dialog.open_page('tools');QTest.qWait(40)
        self.assertIsNone(card.recorder);self.api.setShortcutKeys.assert_not_called()
        dialog.open_page('overview');dialog.resize(640,460);QTest.qWait(150)
        self.assertEqual(page.columns,1)
        for card in page.cards:
            for child in card.findChildren(QLabel):
                self.assertLessEqual(child.geometry().bottom(),card.height(),child.text())
        for child in page.findChildren(QPushButton):
            if child.isVisibleTo(page):
                x=child.mapTo(page,child.rect().topLeft()).x()
                self.assertGreaterEqual(x,0);self.assertLessEqual(x+child.width(),page.width())
        self.assertFalse(owner.settings.allKeys())
        dialog.open_page('radial');QTest.qWait(80)
        radial=dialog.pages['radial'];radial.preview.buttons[5].click()
        self.assertEqual(radial.preview.index,5)
        editor=radial.editor;self.assertEqual(editor.index,5)
        editor.choose_category('Writing')
        item=next(editor.actions.item(i) for i in range(editor.actions.count()) if editor.actions.item(i).data(Qt.UserRole)=='emoji')
        editor.actions.setCurrentItem(item);editor.save_button.click()
        self.assertEqual(radial.preview.keys[5],'emoji')
        dialog.close();dialog.deleteLater();owner.deleteLater();QTest.qWait(40)
