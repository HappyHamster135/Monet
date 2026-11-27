"""Compact routing, async settings writes and nested editor geometry."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_notch_compact_tools as compact
from tests import test_notch_settings_tools as settings
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QDialog, QFrame, QLineEdit, QPushButton, QWidget
from actions import ACTIONS, FULL_APPLICATIONS, notch_catalog
from compact_system import SYSTEM_PAGES
from tool_pages import SETTINGS_GROUPS

DEVICE = dict(id=42,key='737065616b6572',name='Speakers',default=True)
SNAPSHOTS = {
 ('status','display'):dict(brightness=55,night=False),
 ('display-state',):dict(features=[dict(name='eDP-1',hdr=False,vrr=True)]),
 ('status','sound'):dict(volume=35,mic=60),
 ('sound','devices'):dict(outputs=[DEVICE],inputs=[DEVICE],microphone=dict(DEVICE,muted=False)),
 ('power',):dict(mode='automatic',modes=['automatic','power-saver'],hasBattery=True,
                ac=dict(screen=600,sleep=900),battery=dict(screen=300,sleep=600),batterySaverAuto=True),
 ('input',):dict(mouse=dict(speed=50,natural=False,left=False),touchpad=dict(speed=50,natural=True,tap=True,typing=True),
                windowFocus=dict(policy='ClickToFocus',first='pass',delay=300)),
 ('notify',):dict(quiet=False,mirrored=True,fullscreen=True,urgent=True,place='clock',time=5),
 ('status','light'):dict(light='hours'), ('status','bluetooth'):dict(bluetooth=True),
 ('bt-list',):[dict(address='AA:BB:CC:DD:EE:FF',name='Headphones',connected=False)],
 ('output-order','get'):dict(enabled=False,devices=[],connected=[dict(key='61',port='analog',name='Speakers')],revision='a'*64),
}

def worker(args, done, failed=None, **kwargs):
    command = tuple(map(str,args[1:]))
    if str(args[0]) == 'lsusb': done('Bus 001 Device 001: Example USB device'); return
    done(json.dumps(SNAPSHOTS.get(command,{})))


class InlineSettings(unittest.TestCase):
    setUpClass = classmethod(compact.CompactTools.setUpClass.__func__)
    setUp = compact.CompactTools.setUp
    tearDown = compact.CompactTools.tearDown
    show = compact.CompactTools.show

    def test_full_apps_remain_in_desktop_utilities_only(self):
        rows = {r['key'] for r in notch_catalog()['rows']}
        self.assertFalse(rows & FULL_APPLICATIONS)
        self.assertTrue(FULL_APPLICATIONS <= set(ACTIONS))
        self.show('emoji')
        for key in FULL_APPLICATIONS:
            response = self.tools.handle(json.dumps(dict(action='run',key=key)))
            self.assertFalse(json.loads(response)['ok'],key)

    def test_system_pages_are_passive_and_fit_both_widths(self):
        with patch('window.Window.worker', side_effect=worker) as commands, patch('window.Window.run_tool') as launch:
            for width in (288,414):
                for key in sorted(SYSTEM_PAGES | {'color','ocr','screenshot'}):
                    page = self.show(key,width,290)
                    self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(),0,key)
                    for control in page.findChildren(QWidget):
                        if isinstance(control,(QPushButton,QComboBox,QLineEdit)) and control.isVisibleTo(page):
                            point=control.mapTo(page,control.rect().topLeft())
                            self.assertGreaterEqual(point.x(),0,key)
                            self.assertLessEqual(point.x()+control.width(),page.width(),(key,control.accessibleName()))
            launch.assert_not_called()
            self.assertTrue(all(tuple(map(str,c.args[0][1:])) in SNAPSHOTS or c.args[0][0] == 'lsusb' for c in commands.call_args_list))
            self.assertFalse(self.window.isVisible())

    def test_explicit_changes_use_stable_device_ids_and_preserve_order_options(self):
        with patch('window.Window.worker', side_effect=worker) as commands:
            page = self.show('sound')
            page.controls['output'].activated.emit(0)
            self.assertIn(['output','42','737065616b6572'],[c.args[0][1:] for c in commands.call_args_list])
            page.controls['mic-muted'].click()
            self.assertIn(['mic-mute','42','on','737065616b6572'],[c.args[0][1:] for c in commands.call_args_list])
            page = self.show('output-order')
            page.controls['enabled'].click()
            saves=[c.args[0] for c in commands.call_args_list if c.args[0][1:3] == ['output-order','save']]
            value=json.loads(bytes.fromhex(saves[-1][3]))
            self.assertEqual(value['revision'],'a'*64)
            self.assertTrue(value['enabled']);self.assertEqual(value['devices'][0]['port'],'analog')

    def test_pending_reads_keep_values_and_failed_writes_restore_snapshot(self):
        with patch('window.Window.worker', side_effect=worker): page=self.show('display')
        pending=[]
        with patch.object(page.host,'worker',side_effect=lambda args,done,failed:pending.append((args,done,failed))):
            page.refresh();page.refresh()
            self.assertEqual(len(pending),1)
            self.assertEqual(page.controls['brightness'].value(),55)
            self.assertTrue(page.body.isEnabled())
            pending[0][2]('Connection unavailable')
            self.assertFalse(page.pending)
            page.controls['night'].click()
            pending[-1][2]('Not accepted')
            self.assertFalse(page.controls['night'].isChecked())
            self.assertIn('last known',page.message.text())

    def test_script_editor_and_link_subeditors_stay_inside_the_surface(self):
        page=self.show('scripts',288,290)
        page.edit(None);QTest.qWait(80)
        editor=self.tools.scroll.widget()
        self.assertIsInstance(editor,QDialog);self.assertFalse(editor.isWindow())
        editor.name.setText('Unsaved draft')
        self.assertIsNone(self.app.activeModalWidget())
        self.assertLessEqual(editor.needs_text.text().count("\n"),2)
        self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(),0)
        self.tools.back();QTest.qWait(30)
        self.assertIs(self.tools.scroll.widget(),page)
        self.assertTrue(self.tools.area.isVisible())
        page=self.show('link-settings',288,290)
        page.edit();QTest.qWait(60)
        rules=self.tools.scroll.widget();rules.add_site();QTest.qWait(60)
        prompt=self.tools.scroll.widget()
        self.assertFalse(prompt.isWindow())
        self.tools.back();self.assertIs(self.tools.scroll.widget(),rules)
        self.tools.back();self.assertIs(self.tools.scroll.widget(),page)
        page.edit();self.show('emoji');QTest.qWait(30)
        self.assertEqual(self.tools.dialogs.stack,[])
        self.assertFalse(self.window.isVisible())

    def test_record_editor_has_local_back_and_preserves_state(self):
        with patch.object(self.window,'Open') as launch:
            page=self.show('record',288,290);page.editor.click();QTest.qWait(100)
            self.assertIsNotNone(page.clip);self.assertTrue(page.clip.isVisible())
            self.assertFalse(page.form.isVisible());self.assertFalse(page.clip.isWindow())
            self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(),0)
            for control in page.clip.findChildren(QWidget):
                if isinstance(control,(QPushButton,QComboBox)) and control.isVisibleTo(page):
                    pos=control.mapTo(page,control.rect().topLeft())
                    self.assertLessEqual(pos.x()+control.width(),page.width(),control.accessibleName())
            self.tools.back();QTest.qWait(40)
            self.assertTrue(page.form.isVisible());self.assertFalse(page.clip.isVisible())
            self.assertTrue(self.tools.area.isVisible());launch.assert_not_called()

    def test_recording_and_cleaning_preferences_save_without_starting(self):
        with patch('subprocess.run') as command,patch.object(self.window,'start_desktop_cleaning') as cleaning:
            page=self.show('record')
            page.sound.click(); page.mode.setCurrentIndex(1);page.mode.activated.emit(1)
            self.assertTrue(page.config().value('GuiConfig/videoRecordSystemAudio',False,type=bool))
            self.assertEqual(self.window.settings.value('notchRecordingArea'),'w')
            page=self.show('lock');page.duration.setCurrentIndex(2);page.duration.activated.emit(2)
            self.assertEqual(self.window.settings.value('cleaningSeconds',type=int),120)
            self.assertFalse(page.cleaning.isActive());cleaning.assert_not_called();command.assert_not_called()

    def test_watch_starts_only_after_selection_and_stops_explicitly(self):
        with patch('watch.WindowStream') as stream:
            stream.return_value.image.return_value=None
            page=self.show('watch',288,290)
            stream.return_value.start.assert_not_called()
            page.choose_window()
            stream.return_value.start.assert_called_once()
            self.assertTrue(page.capture_active)
            page.stop_watching();self.assertFalse(page.capture_active)
            self.assertFalse(page.frames.isActive())

    def test_inline_video_trim_exports_a_new_copy(self):
        import subprocess
        source=Path(self.temp.name)/'source.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=64x64:r=10:d=2',
                        '-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True,capture_output=True)
        original=source.read_bytes()
        page=self.show('record');page.open_editor();editor=page.clip;editor.open_file(source)
        for _ in range(100):
            QTest.qWait(20)
            if editor.player.duration()>0:break
        self.assertGreater(editor.player.duration(),0)
        editor.starts.setValue(.5);editor.ends.setValue(1.5)
        target=Path(self.temp.name)/'trimmed.mp4'
        with patch('compact_capture.QFileDialog.getSaveFileName',return_value=(str(target),'')):
            editor.export()
        for _ in range(200):
            QTest.qWait(20)
            if editor.job is None:break
        self.assertIsNone(editor.job);self.assertTrue(target.is_file(),editor.message.text())
        self.assertEqual(source.read_bytes(),original)
        duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
                      '-of','default=noprint_wrappers=1:nokey=1',str(target)],text=True))
        self.assertAlmostEqual(duration,1,delta=.2)
        exported=target.read_bytes()
        with patch('compact_capture.QFileDialog.getSaveFileName',return_value=(str(target),'')):
            editor.export()
        self.assertIsNone(editor.job);self.assertEqual(target.read_bytes(),exported)
        self.assertIn('Existing files are kept',editor.message.text())

    def test_screen_selection_returns_results_without_showing_utilities(self):
        with patch('window.Window.worker',side_effect=worker): page=self.show('color')
        with patch.object(page,'wait_for_scene'),patch.object(page.owner,'show') as show:
            page.pick(True)
            self.assertFalse(self.tools.area.isVisible());self.assertTrue(page.return_to_page)
            page.finish('Copied')
            show.assert_not_called();self.assertFalse(page.busy)


class MenuCoverage(unittest.TestCase):
    setUpClass=classmethod(settings.Settings.setUpClass.__func__)
    setUp=settings.Settings.setUp
    tearDown=settings.Settings.tearDown

    def test_every_grouped_tool_has_a_working_settings_page(self):
        with patch('window.Window.worker',side_effect=worker),patch('window.Window.run_tool') as launch:
            self.dialog.resize(760,600)
            for group,entries in SETTINGS_GROUPS:
                for key,detail in entries:
                    with self.subTest(key=key):
                        self.dialog.open_page(key);QTest.qWait(60)
                        self.assertIs(self.dialog.stack.currentWidget(),self.dialog.containers[key])
                        self.assertTrue(self.dialog.description.text())
                        container=self.dialog.containers[key]
                        self.assertEqual(container.horizontalScrollBar().maximum(),0)
            launch.assert_not_called()

    def test_favorites_editor_preserves_desktop_application_preferences(self):
        self.owner.settings.setValue('favorites','["files","emoji"]')
        self.owner.settings.setValue('hidden','["store"]')
        self.dialog.open_page('tools');page=self.dialog.pages['tools']
        rows={page.tree.topLevelItem(i).data(0,Qt.UserRole):page.tree.topLevelItem(i) for i in range(page.tree.topLevelItemCount())}
        self.assertNotIn('files',rows)
        rows['text-tools'].setCheckState(2,Qt.Checked)
        from actions import preferences
        self.assertEqual(preferences(self.owner.settings),(['files','emoji','text-tools'],['store']))

    def test_grouped_settings_keep_full_width_and_retain_working_controls(self):
        with patch('window.Window.worker',side_effect=worker) as commands:
            for width in (640,980):
                self.dialog.resize(width,600)
                for key in ('windows','theme','devices','sound','power','cleaning','clipboard-expiry','awake'):
                    self.dialog.open_page(key);QTest.qWait(70)
                    page=self.dialog.pages[key]
                    cards=[frame for frame in page.findChildren(QFrame) if frame.objectName()=='settingsCard']
                    self.assertTrue(cards,key)
                    for card in cards:
                        self.assertGreater(card.width(),page.width()*.85,(key,card.width(),page.width()))
                        for control in card.findChildren(QWidget):
                            if isinstance(control,(QComboBox,QPushButton,QLineEdit)) and control.isVisibleTo(card):
                                x=control.mapTo(card,control.rect().topLeft()).x()
                                self.assertGreaterEqual(x,0,(key,control.accessibleName()))
                                self.assertLessEqual(x+control.width(),card.width(),(key,control.accessibleName()))
            self.dialog.open_page('sound');page=self.dialog.pages['sound']
            page.controls['mic-muted'].click()
            self.assertIn(['mic-mute','42','on','737065616b6572'],[call.args[0][1:] for call in commands.call_args_list])
            self.dialog.open_page('windows');combo=self.dialog.pages['windows'].controls['policy']
            combo.showPopup();QTest.keyClick(combo,Qt.Key_Down);QTest.keyClick(combo,Qt.Key_Return)
            self.assertIn(['window-focus','policy','hover'],[call.args[0][1:] for call in commands.call_args_list])
