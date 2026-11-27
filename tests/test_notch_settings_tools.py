"""Exercise settings and local tools without running capture or desktop actions."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests import test_notch_compact_tools as compact
from PySide6.QtCore import QObject, QPointF, QSettings, Qt, QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QPushButton, QWidget
from actions import preferences, stored
from notch_preferences import RADIAL_DEFAULT, RADIAL_PRESETS, radial_slots, save_radial
from notch_settings import LayoutBridge, NotchSettingsWindow, present, SERVICE
from quick_text_colors import ColorToolsPage, color_values, transform_text
from window import Window

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


class LocalTools(unittest.TestCase):
    setUpClass = classmethod(compact.CompactTools.setUpClass.__func__)
    setUp = compact.CompactTools.setUp
    tearDown = compact.CompactTools.tearDown
    show = compact.CompactTools.show

    def test_text_operations_undo_and_explicit_copy(self):
        original = '  Ångström  \n\nrepeat\nrepeat\n'
        self.assertEqual(transform_text(original, 'trim'), 'Ångström\n\nrepeat\nrepeat')
        self.assertEqual(transform_text(original, 'unique'), '  Ångström  \n\nrepeat')
        self.assertEqual(transform_text(original, 'lines'), '  Ångström  \nrepeat\nrepeat')
        copies = []
        with patch('notch_pages.copy_text', side_effect=lambda host, text, done: (copies.append(text), done(True))):
            page = self.show('text-tools')
            self.assertEqual(copies, [])
            page.edit.setPlainText(original)
            page.mode.setCurrentIndex(page.mode.findData('upper'))
            page.apply()
            self.assertEqual(page.edit.toPlainText(), original.upper())
            page.edit.undo()
            self.assertEqual(page.edit.toPlainText(), original)
            page.copy_button.click()
            self.assertEqual(copies, [original])
            self.show('emoji')
            self.assertIs(self.show('text-tools'), page)
            self.assertEqual(page.edit.toPlainText(), original)

    def test_palette_validation_conversion_and_persistence(self):
        self.assertEqual(color_values('#ff0000'), ['#FF0000', 'rgb(255, 0, 0)', 'hsl(0, 100%, 50%)'])
        for invalid in ('red', '#FFF', '#00zz00', '#ffffffff'):
            self.assertIsNone(color_values(invalid))
        page = self.show('color-tools')
        self.assertFalse(self.window.settings.contains('notchPalette'))
        page.input.setText('#ff0000'); page.save_button.click(); page.save_button.click()
        self.assertEqual(page.colors, ['#FF0000'])
        page.format.setCurrentIndex(1)
        self.assertEqual(page.value.text(), 'rgb(255, 0, 0)')
        page.input.setText('bad')
        self.assertFalse(page.save_button.isEnabled())
        self.assertFalse(page.copy_button.isEnabled())
        restored = ColorToolsPage(self.window)
        self.assertEqual(restored.colors, ['#FF0000'])
        restored.palette_list.setCurrentRow(0); restored.remove()
        self.assertEqual(stored(self.window.settings, 'notchPalette', []), [])
        restored.deleteLater()

    def test_new_tools_fit_narrow_and_wide_notches(self):
        for width in (288, 414):
            for key in ('text-tools', 'color-tools'):
                page = self.show(key, width, 290)
                self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(), 0)
                for control in page.findChildren(QWidget):
                    if isinstance(control, (QPushButton, QLineEdit, QComboBox)) and control.isVisibleTo(page):
                        pos = control.mapTo(page, control.rect().topLeft())
                        self.assertGreaterEqual(pos.x(), 0)
                        self.assertLessEqual(pos.x() + control.width(), page.width(), (key, width, control.accessibleName()))


class Settings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.owner = Window('/usr/libexec', defer_catalog=True)
        self.owner.settings = QSettings(self.folder.name + '/settings.ini', QSettings.IniFormat)
        self.dialog = NotchSettingsWindow(self.owner)

    def tearDown(self):
        self.dialog.close(); self.dialog.deleteLater(); self.owner.deleteLater()
        QTest.qWait(30); self.folder.cleanup()

    def test_radial_choices_validate_and_do_not_write_on_open(self):
        self.assertEqual(radial_slots(self.owner.settings), RADIAL_DEFAULT)
        self.dialog.open_page('radial')
        page = self.dialog.pages['radial']
        self.assertFalse(self.owner.settings.contains('notchRadial'))
        page.preset(RADIAL_PRESETS['Writing'])
        self.assertEqual(radial_slots(self.owner.settings), RADIAL_PRESETS['Writing'])
        choices = [''] * 8; choices[5] = 'emoji'
        save_radial(self.owner.settings, choices)
        page.refresh()
        self.assertEqual(page.preview.keys, choices)
        with self.assertRaises(ValueError): save_radial(self.owner.settings, ['wheel'] * 8)
        self.owner.settings.setValue('notchRadial', '["missing",null,"emoji"]')
        self.assertEqual(radial_slots(self.owner.settings), ['', '', 'emoji', '', '', '', '', ''])

    def test_search_favorites_and_visibility_keep_saved_order(self):
        self.owner.settings.setValue('favorites', '["emoji","plain"]')
        self.dialog.open_page('tools')
        page = self.dialog.pages['tools']
        self.assertEqual(preferences(self.owner.settings)[0], ['emoji', 'plain'])
        rows = {page.tree.topLevelItem(i).data(0, Qt.UserRole):page.tree.topLevelItem(i) for i in range(page.tree.topLevelItemCount())}
        rows['text-tools'].setCheckState(2, Qt.Checked)
        self.assertEqual(preferences(self.owner.settings)[0], ['emoji', 'plain', 'text-tools'])
        rows['emoji'].setCheckState(1, Qt.Unchecked)
        self.assertEqual(preferences(self.owner.settings)[0], ['plain', 'text-tools'])
        self.assertEqual(rows['emoji'].checkState(2), Qt.Unchecked)
        self.dialog.search.setText('wheel')
        self.assertEqual(self.dialog.navigation.currentItem().data(Qt.UserRole), 'radial')
        self.assertIs(self.dialog.stack.currentWidget(), self.dialog.containers['radial'])
        self.dialog.search.setText('no matching page')
        self.assertTrue(self.dialog.no_matches.isVisible())

    def test_layout_sidebar_and_editor_navigation_stay_in_sync(self):
        commands = []
        state = dict(ok=True, mode='wide', layout=dict(expandedWidth=464, toolHeight=416),
                     options={}, tabs=['music', 'time', 'tools'])
        def worker(argv, done, failed=None, **kwargs):
            commands.append(argv[1:])
            done(json.dumps([dict(id=93, screen=0)] if argv[1] == 'notch-screens' else state))
        with patch.object(self.owner, 'worker', side_effect=worker):
            self.dialog.open_page('content'); QTest.qWait(80)
            quick = self.dialog.pages['layout']
            self.assertIsNotNone(quick.rootObject(), [e.toString() for e in quick.errors()])
            editor = quick.rootObject().findChild(QObject, 'notchVisualEditor')
            self.assertEqual(editor.property('page'), 1)
            editor.setProperty('page', 0)
            self.assertEqual(self.dialog.navigation.currentItem().data(Qt.UserRole), 'layout')
            self.dialog.open_page('behavior')
            self.assertEqual(editor.property('page'), 3)
            self.dialog.open_page('activity')
            self.assertEqual(editor.property('page'), 2)
            self.assertEqual(commands[0], ['notch-screens'])
            self.assertTrue(all(command == ['panel-notch','93'] for command in commands[1:]))
            self.assertFalse(self.owner.settings.allKeys())

    def test_layout_errors_leave_a_useful_message(self):
        with patch.object(self.owner, 'worker', side_effect=lambda argv, done, failed:done('[]')):
            self.dialog.bridge.discover()
        self.assertIn('No desktop panel', self.dialog.bridge.problem)
        with patch.object(self.owner, 'worker', side_effect=lambda argv, done, failed:done('not json')):
            self.dialog.bridge.discover()
        self.assertIn('Could not load', self.dialog.bridge.problem)

    def test_preferences_fit_small_windows_with_large_fonts(self):
        self.dialog.setFont(QFont('Sans Serif', 16))
        self.dialog.resize(640, 460)
        for key in ('radial', 'cleaning', 'color-tools'):
            self.dialog.open_page(key);QTest.qWait(150)
            page = self.dialog.pages[key]
            scroll = self.dialog.containers[key]
            self.assertLessEqual(page.width(), scroll.viewport().width())
            for label in page.findChildren(QLabel):
                if label.wordWrap() and label.isVisibleTo(page):
                    self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()), label.text())
            for control in page.findChildren(QWidget):
                if isinstance(control, (QPushButton,QLineEdit,QComboBox)) and control.isVisibleTo(page):
                    x=control.mapTo(page,control.rect().topLeft()).x()
                    self.assertGreaterEqual(x,0)
                    self.assertLessEqual(x+control.width(),page.width(),(key,control.accessibleName()))
            self.assertFalse(self.dialog.grab().isNull())
            QTest.qWait(100)
            self.assertFalse(scroll.settle.isActive(), key)


class Radial(unittest.TestCase):
    setUpClass = classmethod(Settings.setUpClass.__func__)

    def test_keyboard_actions_and_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Test.qml'
            path.write_text('import QtQuick\nimport "' + UI.as_uri() + '" as Monet\n' + '''
            Monet.NotchRadial {
                width:288; height:290
                slots:["screenshot","record","color","text-tools","emoji","snippets","mic","awake"]
                rows:slots.map(key => ({key:key,label:key}))
                property string chosen:""
                onSelected:key=>chosen=key
                function slotItems() {
                    let pending=[this], result=[]
                    while(pending.length) {
                        const item=pending.pop()
                        if (item.objectName.startsWith("radialSlot")) result.push(item)
                        else pending=pending.concat(Array.from(item.children || []))
                    }
                    return result.sort((a,b)=>a.index-b.index)
                }
                function focusSlot(index) { slotItems()[index].forceActiveFocus() }
                function measurements() {
                    return JSON.stringify(slotItems().map(item=>{
                        const p=item.mapToItem(this,0,0)
                        return {index:item.index,x:p.x,y:p.y,w:item.width,h:item.height}
                    }))
                }
            }''')
            view = QQuickView(); warnings=[]
            view.engine().warnings.connect(lambda errors:warnings.extend(e.toString() for e in errors))
            view.setSource(QUrl.fromLocalFile(str(path)))
            self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
            view.show(); QTest.qWait(100)
            page = view.rootObject()
            for width,height in ((288,290),(414,290),(288,210)):
                page.setWidth(width);page.setHeight(height);QTest.qWait(40)
                buttons=json.loads(page.measurements())
                self.assertEqual(len(buttons), 8)
                for button in buttons:
                    self.assertGreaterEqual(button['x'], 0);self.assertGreaterEqual(button['y'], 0)
                    self.assertLessEqual(button['x']+button['w'], width)
                    self.assertLessEqual(button['y']+button['h'], height)
                    for other in buttons:
                        if other is button:continue
                        overlap=(min(button['x']+button['w'],other['x']+other['w'])>max(button['x'],other['x']) and
                                 min(button['y']+button['h'],other['y']+other['h'])>max(button['y'],other['y']))
                        self.assertFalse(overlap, (button,other))
                    page.focusSlot(button['index'])
                    QTest.keyClick(view, Qt.Key_Return)
                    self.assertEqual(page.property('chosen'), RADIAL_DEFAULT[button['index']])
                QTest.keyClick(view, Qt.Key_5);QTest.keyClick(view, Qt.Key_Return)
                self.assertEqual(page.property('chosen'), 'emoji')
                QTest.keyClick(view, Qt.Key_Right);QTest.keyClick(view, Qt.Key_Return)
                self.assertEqual(page.property('chosen'), 'snippets')
            self.assertFalse(warnings, warnings)
            view.close();view.deleteLater();QTest.qWait(30)


class SettingsProcess(unittest.TestCase):
    setUpClass = classmethod(Settings.setUpClass.__func__)

    def test_settings_launches_once_and_accepts_navigation(self):
        from PySide6.QtDBus import QDBusConnection
        modules = ROOT / 'linux/share/monet/utilities'
        bus = QDBusConnection.sessionBus()
        self.assertFalse(bus.interface().isServiceRegistered(SERVICE).value())
        with tempfile.TemporaryDirectory() as folder:
            # Opening preferences may read layout, but must not run any action.
            helper = Path(folder) / 'monet-quick'
            helper.write_text('#!/usr/bin/python3\nprint("[]")\n')
            helper.chmod(0o755)
            child = subprocess.Popen([sys.executable,str(modules/'notch_settings.py'),str(modules),folder,'radial'],
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                for _ in range(100):
                    if bus.interface().isServiceRegistered(SERVICE).value():break
                    if child.poll() is not None:self.fail(child.communicate()[1])
                    QTest.qWait(30)
                self.assertTrue(bus.interface().isServiceRegistered(SERVICE).value())
                self.assertTrue(present('text-tools'))
                self.assertTrue(present('color-tools'))
                self.assertTrue(present('layout'))
                forwarded = subprocess.run([sys.executable,str(modules/'notch_settings.py'),str(modules),folder,'tools'],
                                           capture_output=True,text=True,timeout=10)
                self.assertEqual(forwarded.returncode,0,forwarded.stderr)
                self.assertIsNone(child.poll())
                self.assertFalse(QSettings('Monet','Utilities').contains('notchRadial'))
            finally:
                child.terminate()
                _, errors = child.communicate(timeout=10)
            self.assertNotIn('Traceback', errors)
            self.assertNotIn('ReferenceError', errors)

    def test_split_preview_bootstrap_loads_shared_dependencies_before_tool_pages(self):
        import shutil
        from PySide6.QtDBus import QDBusConnection
        modules=ROOT/'linux/share/monet/utilities'
        bus=QDBusConnection.sessionBus()
        with tempfile.TemporaryDirectory() as folder:
            private=Path(folder)/'preview';private.mkdir()
            for name in ('notch_settings.py','notch_settings_style.py','tool_pages.py','compact_system.py',
                         'notch_pages.py','notch_preferences.py','radial_actions.py','actions.py','links.py'):
                shutil.copy2(modules/name,private/name)
            helper=Path(folder)/'monet-quick';helper.write_text('#!/usr/bin/python3\nprint("{}")\n');helper.chmod(0o755)
            child=subprocess.Popen([sys.executable,str(private/'notch_settings.py'),str(modules),folder,'sound'],
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                for _ in range(100):
                    if bus.interface().isServiceRegistered(SERVICE).value():break
                    if child.poll() is not None:self.fail(child.communicate()[1])
                    QTest.qWait(30)
                self.assertTrue(bus.interface().isServiceRegistered(SERVICE).value())
                self.assertTrue(present('screenshot'))
                self.assertTrue(present('record'))
                QTest.qWait(60);self.assertIsNone(child.poll())
            finally:
                child.terminate();_,errors=child.communicate(timeout=10)
            self.assertNotIn('Traceback',errors)
