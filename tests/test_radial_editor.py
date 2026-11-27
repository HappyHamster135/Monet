"""Saved actions, media dispatch and a bounded category-first radial editor."""
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from tests import test_notch_settings_tools as fixture
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QWidget
from notch_preferences import radial_records, radial_entries, radial_slots, save_radial_records
from radial_actions import CATALOG, MEDIA, entry
from radial_editor import RadialSlotEditor
from wheel_profiles import open_target


class Editor(fixture.Settings):
    # Reuse the native window fixture without rerunning its parent's checks.
    def choose(self,editor,key):
        editor.choose_category('Media' if key in MEDIA else 'Writing')
        item=next(editor.actions.item(i) for i in range(editor.actions.count()) if editor.actions.item(i).data(Qt.UserRole)==key)
        editor.actions.setCurrentItem(item)

    def test_cancel_save_remove_and_restore_do_not_change_other_slots(self):
        saved=['emoji','','record','text-tools','','snippets','mic','awake']
        self.owner.settings.setValue('notchRadial',json.dumps(saved));self.dialog.open_page('radial')
        page=self.dialog.pages['radial'];page.preview.buttons[1].click();editor=page.editor
        self.assertFalse(editor.save_button.isEnabled());self.choose(editor,'media-next')
        editor.name.setText('Skip song');editor.choose_icon('emblem-favorite');editor.reject()
        self.assertEqual(radial_slots(self.owner.settings),saved)
        page.preview.buttons[1].click();editor=page.editor;self.choose(editor,'media-next')
        editor.name.setText('Skip song');editor.choose_icon('emblem-favorite');editor.save_button.click()
        values=radial_records(self.owner.settings)
        self.assertEqual(values[1],{'action':'media-next','name':'Skip song','icon':'emblem-favorite'})
        self.assertEqual(radial_slots(self.owner.settings),saved[:1]+['media-next']+saved[2:])
        new=QSettings(self.owner.settings.fileName(),QSettings.IniFormat)
        self.assertEqual(radial_records(new),values)
        page.preview.buttons[1].click();editor=page.editor
        self.assertEqual(editor.action,'media-next');self.assertEqual(editor.name.text(),'Skip song')
        self.assertTrue(editor.icons.buttons['emblem-favorite'].isChecked())
        editor.remove_button.click();self.assertEqual(radial_slots(self.owner.settings),saved)

    def test_media_dispatch_is_exact_and_preview_never_executes_it(self):
        for key,(_,_,command) in MEDIA.items():
            selected=entry({'action':key,'name':'My action','icon':'rating'})
            self.assertEqual((selected.kind,selected.component,selected.value),('shortcut','mediacontrol',command))
            api=MagicMock();api.getComponent.return_value='/component/mediacontrol';api.shortcutNames.return_value=[command]
            with patch('dbus.SessionBus'),patch('dbus.Interface',return_value=api):
                self.assertTrue(open_target(selected));api.invokeShortcut.assert_called_once_with(command,timeout=2)
        self.dialog.open_page('radial');page=self.dialog.pages['radial']
        with patch('wheel_profiles.open_target') as execute:
            page.preview.buttons[0].click();self.choose(page.editor,'media-play-pause');page.editor.save()
            execute.assert_not_called()
        self.owner.Open(['radial']);wheel=self.owner.favorites_wheel
        self.assertEqual(wheel.buttons[0].entry.value,'playpausemedia')
        with patch('wheel_profiles.open_target',return_value=True) as execute:
            QTest.keyClick(wheel,Qt.Key_1)
            execute.assert_called_once_with(wheel.buttons[0].entry)
        self.assertFalse(wheel.isVisible());wheel.deleteLater()

    def test_icon_and_name_survive_tool_slot_and_corrupt_data_is_safe(self):
        values=[{'action':'emoji','name':'Symbols','icon':'rating'}]+[{}]*7
        save_radial_records(self.owner.settings,values)
        item=radial_entries(self.owner.settings)[0]
        self.assertEqual((item.title,item.icon_name),('Symbols','rating'))
        self.owner.settings.setValue('notchRadial',json.dumps([{'action':'media-next','name':['bad'],'icon':'/tmp/image.svg'},None,'missing',{'action':[]}]))
        self.assertEqual(radial_slots(self.owner.settings),['media-next']+['']*7)
        self.assertEqual(radial_records(self.owner.settings)[0],{'action':'media-next','name':'','icon':''})
        with self.assertRaises(ValueError):save_radial_records(self.owner.settings,[{'action':'wheel'}]+[{}]*7)

    def test_editor_fits_large_fonts_and_small_windows_without_dropdowns(self):
        editor=RadialSlotEditor(self.dialog,0,{'action':'media-play-pause'})
        editor.setFont(QFont('Sans Serif',16));editor.resize(360,460);editor.show();QTest.qWait(180)
        self.assertFalse(editor.findChildren(QComboBox))
        for group in (editor.icons,editor.categories):
            if group is editor.categories:editor.show_categories();QTest.qWait(100)
            for button in group.buttons.values():
                self.assertGreaterEqual(button.x(),0)
                self.assertLessEqual(button.geometry().right(),group.width())
                self.assertLessEqual(button.geometry().bottom(),group.height())
        for button in (editor.save_button,editor.remove_button):
            point=button.mapTo(editor,button.rect().bottomRight())
            self.assertLess(point.x(),editor.width());self.assertLess(point.y(),editor.height())
        editor.reject();editor.deleteLater()


# Only collect the new checks; the shared fixture has its own module.
for name in tuple(dir(fixture.Settings)):
    if name.startswith('test_') and name not in Editor.__dict__:setattr(Editor,name,None)
