"""Execute the shipping layout migration with Plasma's JavaScript runtime."""
import json
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
from tests.test_look import ROOT, quick_helper
from tests import test_settings_navigation as settings


@unittest.skipUnless(settings.QT, 'Qt and Plasma runtime')
class PanelLayouts(unittest.TestCase):
    setUpClass = classmethod(settings.SettingsNavigation.setUpClass.__func__)
    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)

    def setUp(self):
        from PySide6.QtQml import QJSEngine
        self.engine = QJSEngine(); self.quick = quick_helper()
        self.engine.evaluate('''
        var printed='', all=[], sequence=20, failMove=false, failAfter=-1, moveCount=0;
        var knownWidgetTypes=['org.monet.menu','org.monet.games','org.kde.plasma.icontasks',
            'org.kde.plasma.marginsseparator','org.kde.plasma.trash','org.monet.weather',
            'org.monet.quick','org.monet.sound','org.kde.plasma.systemtray','org.monet.clock'];
        function print(value){printed=value}
        function config(o) {
            o.data={}; o.currentConfigGroup=[];
            o.readConfig=function(k,d){var v=this.data[this.currentConfigGroup.join('/')+'/'+k]; return v===undefined?d:v};
            o.writeConfig=function(k,v){this.data[this.currentConfigGroup.join('/')+'/'+k]=v};
            o.reloadConfig=function(){}; return o;
        }
        function Panel() {
            config(this); this.id=++sequence; this.items=[]; this.screen=0; this.location='bottom';
            this.height=60; this.hiding='dodgewindows'; all.push(this);
            this.widgets=function(type){return this.items.filter(w=>!type||w.type===type)};
            this.widgetById=function(id){return this.items.find(w=>w.id===id)};
            this.addWidget=function(w){
                if(typeof w==='string') {
                    w=config({id:++sequence,type:w});
                    Object.defineProperty(w,'index',{get:function(){return this.parent.items.indexOf(this)},
                        set:function(n){var items=this.parent.items; items.splice(items.indexOf(this),1); items.splice(Math.max(0,Math.min(n,items.length-1)),0,this)}});
                    w.remove=function(){this.parent.items=this.parent.items.filter(x=>x.id!==this.id)};
                } else {
                    if(failMove || moveCount++===failAfter) { failMove=false; failAfter=-1; return null; }
                    w.remove();
                }
                w.parent=this; this.items.push(w); return w;
            };
            this.remove=function(){ if(this.items.length) throw new Error('deleted widgets'); all=all.filter(p=>p.id!==this.id) };
        }
        function panels(){return all}
        function panelById(id){return all.find(p=>p.id===id)}
        var left=new Panel, middle=new Panel, right=new Panel;
        left.addWidget('org.monet.menu'); left.addWidget('org.monet.games');
        var task=middle.addWidget('org.kde.plasma.icontasks'); task.currentConfigGroup=['General'];
        task.writeConfig('launchers',['applications:my-pin.desktop']);
        var custom=right.addWidget('custom.widget'); custom.currentConfigGroup=['General']; custom.writeConfig('secret','keep');
        right.addWidget('org.monet.quick'); var tray=right.addWidget('org.kde.plasma.systemtray');
        tray.currentConfigGroup=['General']; tray.writeConfig('hiddenItems',['custom-status']);
        var other=new Panel; other.screen=1; other.addWidget('org.monet.menu');
        var top=new Panel; top.location='top'; top.addWidget('org.monet.quick');
        ''')

    def js(self, expression):
        value=self.engine.evaluate(expression)
        self.assertFalse(value.isError(), value.toString())
        return value

    def state(self, expression):
        return json.loads(self.js('JSON.stringify('+expression+')').toString())

    def choose(self, panel, layout=None):
        def bus(*args):
            self.js(args[-1]); return [self.js('printed').toString()]
        with patch.object(self.quick, 'DATADIR', str(ROOT/'linux/share')), patch.object(self.quick, 'busjson', side_effect=bus):
            return self.quick.panel_layout(str(self.js(panel+'.id').toInt()), layout)

    def test_notch_is_independent_of_home_bar_layout_and_other_screens(self):
        self.js("knownWidgetTypes.push('org.monet.notch')")
        def notch(panel, mode=None):
            def bus(*args):
                self.js(args[-1])
                return [self.js('printed').toString()]
            with patch.object(self.quick, 'DATADIR', str(ROOT/'linux/share')), patch.object(self.quick, 'busjson', side_effect=bus):
                return self.quick.panel_notch(str(self.js(panel+'.id').toInt()), mode)
        self.assertEqual(notch('right')['mode'], 'off')
        self.assertEqual(notch('right', 'compact')['mode'], 'compact')
        self.js("var notchPanel=all.find(p=>p.widgets('org.monet.notch').length)")
        self.assertEqual(self.state('[notchPanel.screen,notchPanel.location,notchPanel.alignment,notchPanel.lengthMode]'),
                         [0, 'top', 'center', 'fit'])
        self.assertFalse(self.choose('notchPanel')['available'])
        self.assertTrue(notch('right')['options']['gestures'])
        self.assertFalse(notch('left', 'gestures-off')['options']['gestures'])
        self.assertFalse(notch('right')['options']['gestures'])
        self.assertFalse(notch('right')['options']['previews'])
        self.assertTrue(notch('right', 'previews-on')['options']['previews'])
        self.assertFalse(notch('right', 'previews-off')['options']['previews'])
        self.assertTrue(notch('right', 'levels-on')['options']['levels'])
        self.assertEqual(notch('left', 'wide')['mode'], 'wide')
        self.assertEqual(notch('other')['mode'], 'off')
        self.assertTrue(notch('other', 'compact')['options']['gestures'])
        self.assertFalse(notch('right')['options']['gestures'])
        self.assertTrue(self.choose('right','one')['ok'])
        self.assertEqual(notch('right')['mode'], 'wide')
        self.assertTrue(self.choose('right','three')['ok'])
        standard = ['music', 'activity', 'time', 'calendar', 'notes']
        self.assertEqual(notch('right')['tabs'], standard)
        self.assertEqual(notch('right', 'tab-camera-show')['tabs'], standard + ['camera'])
        self.assertEqual(notch('right', 'tab-camera-earlier')['tabs'][-2:], ['camera', 'notes'])
        self.assertEqual(notch('right', 'tab-camera-hide')['tabs'], standard)
        self.assertEqual(notch('right', 'tab-activity-earlier')['tabs'][:2], ['activity', 'music'])
        self.assertEqual(notch('right', 'tab-activity-earlier')['tabs'][:2], ['activity', 'music'])
        self.assertEqual(notch('right', 'tab-time-hide')['tabs'], ['activity', 'music', 'calendar', 'notes'])
        self.assertFalse(notch('right', 'tab-new-show')['ok'])
        saved = notch('right')
        self.assertTrue(notch('right', 'off')['ok'])
        self.assertEqual(notch('other')['mode'], 'compact')
        self.assertTrue(self.js('!panelById(notchPanel.id)').toBool())
        self.assertEqual(notch('other')['tabs'], standard)
        self.assertTrue(self.choose('right', 'one')['ok'])
        self.assertEqual(notch('right', 'wide'), saved)
        for key in saved['tabs']:
            last = notch('right', 'tab-' + key + '-hide')
        self.assertEqual(last['tabs'], [])
        self.assertEqual(notch('right', 'tab-notes-show')['tabs'], ['notes'])
        self.assertEqual(notch('right', 'tab-notes-show')['tabs'], ['notes'])
        self.js("var n=all.find(p=>p.screen===right.screen&&p.widgets('org.monet.notch').length).widgets()[0]; n.currentConfigGroup=['General']; n.writeConfig('tabs','music,music,bad');")
        self.assertEqual(notch('right')['tabs'], standard)

    def test_switch_from_side_bar_round_trip_keeps_id_pins_widgets_and_other_screens(self):
        self.assertEqual(self.choose('right')['layout'], 'three')
        ids=self.state('[task.id,custom.id,tray.id]')
        self.assertTrue(self.choose('right','one')['ok'])
        self.assertEqual(self.state('all.length'),3)
        self.assertEqual(self.state('right.lengthMode'),'fill')
        self.assertEqual(self.state('right.items.map(w=>w.type)').count('org.monet.sound'),1)
        self.assertEqual(self.state('right.items.slice().sort((a,b)=>a.index-b.index).map(w=>w.type)')[0],'org.monet.menu')
        for choice in ('one','three','three','one','three'):
            self.assertTrue(self.choose('right',choice)['ok'])
        self.assertEqual(self.state('[task.id,custom.id,tray.id]'),ids)
        self.assertEqual(self.state('task.data["General/launchers"]'),['applications:my-pin.desktop'])
        self.assertEqual(self.state('custom.data["General/secret"]'),'keep')
        self.assertEqual(self.state('tray.data["General/hiddenItems"]'),['custom-status'])
        self.assertEqual(self.state('custom.parent.items.some(w=>w.type==="org.monet.quick")'),True)
        self.assertEqual(self.state('all.length'),5)
        self.assertEqual(self.state('[other.items.length,top.items.length,other.screen,top.location]'),[1,1,1,'top'])

    def test_missing_controls_and_default_shortcuts_are_filled_without_duplicate_sound(self):
        self.js("task.remove(); tray.remove(); left.widgets('org.monet.menu')[0].remove()")
        # Remaining legacy game island needs its role recorded after the user removed its menu.
        self.js("left.currentConfigGroup=['MonetBar']; left.writeConfig('role','left'); middle.currentConfigGroup=['MonetBar']; middle.writeConfig('role','middle')")
        self.assertTrue(self.choose('right','one')['ok'])
        self.assertEqual(self.state("right.widgets('org.monet.menu')[0].data['Shortcuts/global']"),'Alt+F1')
        self.assertIn('applications:monet-settings.desktop',self.state("right.widgets('org.kde.plasma.icontasks')[0].data['General/launchers']"))
        self.assertNotIn('org.kde.plasma.volume',self.state("right.widgets('org.kde.plasma.systemtray')[0].data['General/extraItems']"))
        self.assertEqual(self.state("right.widgets('org.monet.sound').length"),1)

    def test_failed_move_preserves_original_panels_and_widgets(self):
        before=self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])')
        self.js('failMove=true')
        self.assertFalse(self.choose('right','one')['ok'])
        self.assertEqual(self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])'),before)

    def test_failure_after_several_moves_restores_all_original_panels(self):
        before=self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])')
        self.js('failAfter=2')
        self.assertFalse(self.choose('right','one')['ok'])
        self.assertEqual(self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])'),before)

    def test_ambiguous_extra_taskbar_and_missing_plugin_do_not_mutate(self):
        self.js("var extra=new Panel; extra.addWidget('org.kde.plasma.icontasks')")
        self.assertFalse(self.choose('right','one')['available'])
        self.js("extra.items[0].remove(); extra.remove(); knownWidgetTypes=[]")
        before=self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])')
        self.assertFalse(self.choose('right','one')['ok'])
        self.assertEqual(self.state('all.map(p=>[p.id,p.items.map(w=>w.id)])'),before)

    def test_invalid_arguments_never_reach_plasma(self):
        with patch.object(self.quick,'busjson') as bus:
            self.assertFalse(self.quick.panel_layout('7; bad()','one')['ok'])
            self.assertFalse(self.quick.panel_layout('7','four')['ok'])
            bus.assert_not_called()

    def test_single_bar_fills_its_task_space_and_three_bars_restore_the_user_choice(self):
        self.js('task.currentConfigGroup=["General"]; task.writeConfig("fill",false)')
        self.assertTrue(self.choose('right','one')['ok'])
        self.assertTrue(self.state('task.data["General/fill"]'))
        self.assertTrue(self.choose('right','three')['ok'])
        self.assertFalse(self.state('task.data["General/fill"]'))
        self.js('task.currentConfigGroup=["General"]; task.writeConfig("fill",true)')
        for choice in ('one','three'): self.assertTrue(self.choose('right',choice)['ok'])
        self.assertTrue(self.state('task.data["General/fill"]'))


@unittest.skipUnless(shutil.which('kwin_wayland'), 'native Plasma virtual compositor')
class NativePanelLayout(unittest.TestCase):
    def test_panel_switch_and_persistence_on_private_wayland_desktop(self):
        subprocess.run([sys.executable, str(ROOT/'tests/fixtures/panel-layout.py')], check=True, timeout=75)
