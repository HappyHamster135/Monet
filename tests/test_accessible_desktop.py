"""Logical-screen layout, recurring notes, and actual keyboard-operated QML controls."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
WIDGETS=ROOT/'linux/share/monet/widgets'

def helper(name):
    loader=importlib.machinery.SourceFileLoader(name,str(ROOT/'linux/libexec'/name))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(name,loader))
    loader.exec_module(module)
    return module

@unittest.skipIf(os.name=='nt','Linux file locking')
class Notes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.q=helper('monet-quick'); self.q.NOTES=Path(self.temp.name)/'notes.json'

    def test_legacy_notes_and_future_yearly_edits_survive_reload(self):
        self.q.set_note('2026-10-28','Birthday','yearly')
        self.q.set_note('2026-10-29','Dentist')
        self.q.set_note('2027-10-28','Birthday dinner','yearly')
        self.assertEqual(self.q.notes(),{'2026-10-28':{'text':'Birthday dinner','repeat':'yearly'},'2026-10-29':'Dentist'})
        self.assertEqual(self.q.NOTES.stat().st_mode&0o777,0o600)

    def test_stop_repeating_and_remove_from_future_occurrence(self):
        self.q.set_note('2026-02-28','Birthday','yearly')
        self.q.set_note('2027-02-28','Once','none')
        self.assertEqual(self.q.notes(),{'2027-02-28':'Once'})
        self.q.set_note('2027-02-28','Again','yearly')
        self.q.set_note('2028-02-28','')
        self.assertEqual(self.q.notes(),{})

    def test_invalid_dates_and_corrupt_file_do_not_replace_notes(self):
        self.q.set_note('2028-02-29','Leap day','yearly')
        with self.assertRaises(ValueError): self.q.set_note('2027-02-29','bad','yearly')
        self.q.NOTES.write_text('broken')
        with self.assertRaises(ValueError): self.q.set_note('2026-10-28','new')
        self.assertEqual(self.q.NOTES.read_text(),'broken')

    def test_failed_atomic_write_keeps_original(self):
        self.q.set_note('2026-10-28','Before')
        with mock.patch('os.replace',side_effect=OSError('full disk')):
            with self.assertRaises(OSError): self.q.set_note('2026-10-28','After','yearly')
        self.assertEqual(self.q.notes(),{'2026-10-28':'Before'})

    def test_clear_command_accepts_empty_text_and_recurrence(self):
        folder=Path(self.temp.name)/'monet'; folder.mkdir()
        path=folder/'notes.json'; path.write_text('{"2026-10-28":{"text":"Birthday","repeat":"yearly"}}')
        subprocess.run([sys.executable,str(ROOT/'linux/libexec/monet-quick'),'note','2027-10-28','','none'],
                       env={**os.environ,'XDG_DATA_HOME':self.temp.name},check=True,capture_output=True)
        self.assertEqual(json.loads(path.read_text()),{})

    def test_each_interval_survives_reload_edit_and_removal(self):
        for repeat, future in [('daily','2026-11-01'),('weekly','2026-11-04'),('monthly','2026-11-28')]:
            with self.subTest(repeat=repeat):
                self.q.save_notes({})
                self.q.set_note('2026-10-28','Routine',repeat)
                self.q.set_note(future,'Edited')  # An older caller preserves the saved interval.
                self.assertEqual(self.q.notes(strict=True),{'2026-10-28':{'text':'Edited','repeat':repeat}})
                self.q.set_note(future,'')
                self.assertEqual(self.q.notes(),{})

    def test_changing_interval_anchors_it_to_the_selected_occurrence(self):
        self.q.set_note('2026-10-28','Routine','weekly')
        self.q.set_note('2026-11-04','Routine','monthly')
        self.assertEqual(self.q.notes(),{'2026-11-04':{'text':'Routine','repeat':'monthly'}})
        self.q.set_note('2026-12-04','Just once','none')
        self.assertEqual(self.q.notes(),{'2026-12-04':'Just once'})

    def test_invalid_interval_keeps_saved_notes(self):
        self.q.set_note('2026-10-28','Routine','daily')
        with self.assertRaises(ValueError): self.q.set_note('2026-10-29','bad','hourly')
        self.assertEqual(self.q.notes(),{'2026-10-28':{'text':'Routine','repeat':'daily'}})

try:
    from PySide6.QtCore import QObject,QUrl,QMetaObject,Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine,QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT=True
except ImportError: QT=False

@unittest.skipUnless(QT,'Qt runtime')
class DesktopUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND','software')
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def js(self,filename,code):
        engine=QJSEngine(); result=engine.evaluate((WIDGETS/filename).read_text()+'\nJSON.stringify('+code+')')
        self.assertFalse(result.isError(),result.toString())
        return json.loads(result.toString())

    def test_widgets_fit_at_every_supported_scale_without_overlap(self):
        items=[dict(id=1,x=48,y=48,width=400,height=352,minWidth=390,minHeight=349),
               dict(id=2,x=1168,y=48,width=352,height=192,minWidth=252,minHeight=180),
               dict(id=3,x=1552,y=48,width=352,height=272,minWidth=234,minHeight=252),
               dict(id=4,x=1552,y=336,width=352,height=144,minWidth=270,minHeight=126)]
        for scale in (1,1.25,1.5,1.75,2):
            area=dict(width=int(1920/scale),height=int(1080/scale)-80)
            out=self.js('LayoutMath.js',f'arrange({json.dumps(items)},{{width:1920,height:1080}},{json.dumps(area)},16)')
            for i,r in enumerate(out):
                self.assertGreaterEqual(r['x'],0); self.assertGreaterEqual(r['y'],0)
                self.assertLessEqual(r['x']+r['width'],area['width'])
                self.assertLessEqual(r['y']+r['height'],area['height'])
                for other in out[:i]:
                    self.assertTrue(r['x']>=other['x']+other['width'] or other['x']>=r['x']+r['width']
                                    or r['y']>=other['y']+other['height'] or other['y']>=r['y']+r['height'],(scale,r,other))

    def test_notes_open_inward_with_negative_monitor_origins(self):
        for origin in (-960,0,1920):
            screen=dict(x=origin,y=0,width=960,height=540)
            for x in (origin+16,origin+650):
                p=self.js('LayoutMath.js',f'beside({{x:{x},y:350,width:270,height:180}},{{width:304,height:400}},{json.dumps(screen)},12)')
                self.assertGreaterEqual(p['x'],origin+8); self.assertLessEqual(p['x']+304,origin+952)
                self.assertGreaterEqual(p['y'],8); self.assertLessEqual(p['y']+400,532)
                self.assertTrue(p['x']>x if x==origin+16 else p['x']<x)

    def test_annual_notes_appear_in_future_months_and_upcoming_without_invalid_leap_days(self):
        notes={'2026-12-31':{'text':'Birthday','repeat':'yearly'},'2028-02-29':{'text':'Leap birthday','repeat':'yearly'},'2027-01-02':'Once'}
        result=self.js('NoteLogic.js',f'after({json.dumps(notes)},new Date(2026,11,30),3).map(n=>({{day:key(n.day),text:n.text}}))')
        self.assertEqual([n['day'] for n in result],['2026-12-31','2027-01-02','2027-12-31'])
        self.assertEqual(self.js('NoteLogic.js',f'text({json.dumps(notes)},new Date(2027,11,31))'),'Birthday')
        self.assertEqual(self.js('NoteLogic.js',f'text({json.dumps(notes)},new Date(2027,1,28))'),'')

    def test_recurring_dates_match_the_persistence_helper(self):
        q=helper('monet-quick')
        fixtures=[
            ('2026-03-28','daily',['2026-03-27','2026-03-28','2026-03-29','2027-01-01'],[False,True,True,True]),
            ('2026-03-22','weekly',['2026-03-15','2026-03-29','2026-04-05','2026-04-06'],[False,True,True,False]),
            ('2026-10-18','weekly',['2026-10-25','2026-11-01','2026-11-02'],[True,True,False]),
            ('2026-01-31','monthly',['2025-12-31','2026-02-28','2026-03-03','2026-03-31','2027-01-31'],[False,False,False,True,True]),
            ('2026-01-29','monthly',['2026-02-28','2026-03-29','2028-02-29'],[False,True,True]),
            ('2096-02-29','yearly',['2100-02-28','2100-03-01','2104-02-29'],[False,False,True]),
        ]
        for start,repeat,days,wanted in fixtures:
            notes={start:{'text':'Routine','repeat':repeat}}
            for day,present in zip(days,wanted):
                with self.subTest(repeat=repeat,day=day):
                    expected=start if present else day
                    self.assertEqual(q.note_source(notes,day),expected)
                    self.assertEqual(self.js('NoteLogic.js',f'source({json.dumps(notes)},parse("{day}"))'),expected)
                    self.assertEqual(self.js('NoteLogic.js',f'text({json.dumps(notes)},parse("{day}"))'),'Routine' if present else '')

    def test_coming_up_expands_intervals_without_drifting_or_duplicate_days(self):
        cases=[
            ('2026-12-31','daily','2026-12-31',['2027-01-01','2027-01-02','2027-01-03']),
            ('2026-03-22','weekly','2026-03-22',['2026-03-29','2026-04-05','2026-04-12']),
            ('2026-10-18','weekly','2026-10-19',['2026-10-25','2026-11-01','2026-11-08']),
            ('2026-01-31','monthly','2026-01-31',['2026-03-31','2026-05-31','2026-07-31']),
            ('2026-01-29','monthly','2026-01-29',['2026-03-29','2026-04-29','2026-05-29']),
            ('2096-02-29','yearly','2096-02-29',['2104-02-29','2108-02-29','2112-02-29']),
            ('2027-01-01','daily','2026-10-27',['2027-01-01','2027-01-02','2027-01-03']),
        ]
        for start,repeat,day,wanted in cases:
            with self.subTest(repeat=repeat,day=day):
                notes={start:{'text':'Routine','repeat':repeat}}
                self.assertEqual(self.js('NoteLogic.js',f'after({json.dumps(notes)},parse("{day}"),3).map(n=>key(n.day))'),wanted)
        notes={'2026-10-27':{'text':'Daily','repeat':'daily'},'2026-10-28':'Appointment',
               '2026-10-29':{'text':'Weekly','repeat':'weekly'}}
        result=self.js('NoteLogic.js',f'after({json.dumps(notes)},parse("2026-10-27"),3).map(n=>[key(n.day),n.text])')
        self.assertEqual(result,[['2026-10-28','Appointment'],['2026-10-29','Weekly'],['2026-10-30','Daily']])
        self.assertEqual(self.js('NoteLogic.js',f'text({json.dumps(notes)},parse("2026-11-05"))'),'Weekly')

    def test_local_edits_preserve_or_change_the_series_anchor(self):
        notes={'2026-10-28':{'text':'Routine','repeat':'weekly'}}
        for interval,expected in [('weekly',{'2026-10-28':{'text':'Edited','repeat':'weekly'}}),
                                  ('monthly',{'2026-11-04':{'text':'Edited','repeat':'monthly'}}),
                                  ('none',{'2026-11-04':'Edited'})]:
            self.assertEqual(self.js('NoteLogic.js',f'updated({json.dumps(notes)},parse("2026-11-04"),"Edited","{interval}")'),expected)
        self.assertEqual(self.js('NoteLogic.js',f'updated({json.dumps(notes)},parse("2026-11-04"),"","weekly")'),{})

    def test_calendar_and_repeat_control_work_by_keyboard(self):
        engine=QQmlApplicationEngine(); words=helper('monet-games').Words()
        engine.rootContext().setContextObject(words)
        errors=[]; engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.qml'
            path.write_text('''import QtQuick
import "'''+QUrl.fromLocalFile(str(WIDGETS)).toString()+'''"
Window { width:700; height:450; visible:true
 QtObject { id:noteData; property var notes:({}); property string problem:""; property var saved:[]
 function noteFor(day){return "Birthday"} function repeatFor(day){return "none"}
 function after(day,count){return []} function write(day,text,repeat){saved=[day,text,repeat]} function retry(){} }
 Month { id:month; objectName:"month"; width:300; height:370; today:new Date(2026,9,27); store:noteData;
 ink:"black"; dim:"gray"; lily:"green"; onOpened:notes.write() }
 DayNotes { id:notes; objectName:"notes"; x:340; width:320; height:410; store:noteData; day:month.chosen;
 today:month.today; ink:"black"; dim:"gray"; lily:"green" }
 property var saved:noteData.saved
}''')
            engine.load(QUrl.fromLocalFile(str(path)))
            self.assertTrue(engine.rootObjects(),'\n'.join(errors)); window=engine.rootObjects()[0]
            QTest.qWait(100)
            month=window.findChild(QObject,'month'); QMetaObject.invokeMethod(month,'forceActiveFocus')
            QTest.keyClick(window,Qt.Key_Right)
            QTest.keyClick(window,Qt.Key_PageDown)
            self.assertEqual(month.property('chosen').date().month(),11)
            QTest.keyClick(window,Qt.Key_PageUp)
            self.assertEqual(month.property('chosen').date().month(),10)
            QTest.keyClick(window,Qt.Key_Return)
            self.assertEqual(month.property('chosen').date().day(),28)
            QTest.keyClick(window,Qt.Key_Tab)
            repeat=window.findChild(QObject,'noteRepeat')
            self.assertTrue(repeat.property('activeFocus'))
            for index,interval in enumerate(['yearly','monthly','weekly','daily'],1):
                QTest.keyClick(window,Qt.Key_Down); QTest.keyClick(window,Qt.Key_Return); QTest.qWait(50)
                self.assertEqual(repeat.property('currentIndex'),index)
                self.assertEqual(window.property('saved').toVariant()[2],interval)
            QTest.keyClick(window,Qt.Key_Home); QTest.keyClick(window,Qt.Key_Return); QTest.qWait(50)
            self.assertEqual(window.property('saved').toVariant()[2],'none')
            self.assertFalse(errors,'\n'.join(errors))
            window.close(); engine.deleteLater(); QTest.qWait(1)

    def test_glass_flags_follow_same_count_renames_and_disable(self):
        errors=[]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'flags'; folder.mkdir()
            path=Path(tmp)/'flags.qml'
            path.write_text('import QtQuick\nimport "'+QUrl.fromLocalFile(str(WIDGETS)).toString()+'"\n'
                'Item { GlassSettings { objectName:"flags"; directory:Qt.resolvedUrl("flags") } }')
            engine=QQmlApplicationEngine()
            engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            root=engine.rootObjects()[0]; flags=root.findChild(QObject,'flags')
            def wait_for(key,value):
                for _ in range(100):
                    if flags.property(key)==value: break
                    QTest.qWait(20)
                self.assertEqual(flags.property(key),value)
            QTest.qWait(100)
            (folder/'glass-frosted').touch(); wait_for('level',1)
            (folder/'glass-frosted').rename(folder/'glass-matte'); wait_for('level',2)
            (folder/'glass-lite').touch(); wait_for('lite',True)
            (folder/'glass-off').touch(); wait_for('off',True)
            (folder/'glass-matte').unlink(); wait_for('level',0)
            flags.setProperty('enabled',False); wait_for('off',False); wait_for('lite',False)
            flags.setProperty('enabled',True); wait_for('off',True); wait_for('lite',True)
            self.assertFalse(errors,'\n'.join(errors))
            engine.deleteLater(); QTest.qWait(20)

    def test_wallpaper_keeps_one_idle_image_and_waits_for_transition_loading(self):
        from PySide6.QtGui import QImage, QColor
        errors=[]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name,color in [('night','black'),('dawn','red'),('day','blue'),('dusk','green')]:
                picture=QImage(128,80,QImage.Format_RGB32); picture.fill(QColor(color))
                self.assertTrue(picture.save(str(folder/(name+'.jpg'))))
            wallpaper=(ROOT/'linux/share/plasma/wallpapers/org.monet.hours/contents/ui/main.qml').read_text()
            # Exercise the shipped transition functions and real asynchronous
            # Image items. The containment, weather and clock are unrelated.
            body=wallpaper[wallpaper.index('    function source(i)'):wallpaper.index('    // Each minute;')]
            body=body.replace('duration: 1500','duration: 30')
            body=body.replace('property Image below:', 'property QtObject below:').replace('property Image above:', 'property QtObject above:')
            body=body.replace('id: first', 'id: first; property int loadStatus: status').replace('id: second', 'id: second; property int loadStatus: status')
            path=folder/'paintings.qml'
            path.write_text('''import QtQuick
import QtQuick.Window
Window { id:root; width:320; height:200; visible:true
 property string folder:Qt.resolvedUrl(".").toString()
 property var hours:[{name:"night"},{name:"dawn"},{name:"day"},{name:"dusk"}]
 property int fromLight:0; property int toLight:1; property real blend:0
 function apply() { show(fromLight,toLight,blend) }
'''+body+'}')
            engine=QQmlApplicationEngine()
            engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            root=engine.rootObjects()[0]
            def show(start,end,blend):
                root.setProperty('fromLight',start); root.setProperty('toLight',end); root.setProperty('blend',blend)
                QMetaObject.invokeMethod(root,'apply')
            def ready(item):
                for _ in range(100):
                    if item.property('loadStatus')==1: break
                    QTest.qWait(10)
                self.assertEqual(item.property('loadStatus'),1)
                QTest.qWait(60)
            show(0,1,0)
            below=root.property('below'); ready(below)
            self.assertTrue(root.property('above').property('source').isEmpty())
            show(0,1,.5)
            above=root.property('above'); ready(above)
            self.assertAlmostEqual(above.property('opacity'),.5)
            self.assertEqual(root.property('below'),below)
            show(1,2,0)
            self.assertEqual(root.property('below'),above)  # Reuse the loaded painting.
            self.assertTrue(root.property('above').property('source').isEmpty())
            show(1,1,0)  # Pinned light must not allocate a duplicate image.
            self.assertTrue(root.property('above').property('source').isEmpty())
            show(3,3,0)  # Manual jump waits for the new light and then fades.
            jumping=root.property('above'); ready(jumping)
            self.assertAlmostEqual(jumping.property('opacity'),1)
            show(3,3,0)
            self.assertEqual(root.property('below'),jumping)
            self.assertTrue(root.property('above').property('source').isEmpty())
            self.assertFalse(errors,'\n'.join(errors))
            root.close(); engine.deleteLater(); QTest.qWait(20)

    def test_layout_guard_discovers_reparenting_and_has_no_idle_timers(self):
        errors=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.qml'
            path.write_text('''import QtQuick
import QtQuick.Layouts
import "'''+QUrl.fromLocalFile(str(WIDGETS)).toString()+'''"
Item { width:1920; height:1080
 Item { id:board; objectName:"board"; width:1920; height:1004
  property QtObject containmentItem: QtObject { property real height:1080 }
  property bool editMode:false; property bool relayoutLock:false; property int cellWidth:16
  property string configKey:"1920x1080"
  function releaseSpace(item){} function save(){} function positionItem(item){}
 }
 Item { id:widget; x:48; y:48; width:224; height:224
  property var applet:({plasmoid:{id:1,pluginName:"org.monet.notes",containment:{id:1}}})
  Layout.minimumWidth:100; Layout.minimumHeight:100
  LayoutGuard { objectName:"guard"; storageFile:Qt.resolvedUrl("layouts.conf") }
 }
 function attach() { widget.parent=board }
 function move() { widget.x=160; widget.width=352 }
}''')
            engine=QQmlApplicationEngine()
            engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            root=engine.rootObjects()[0]; guard=root.findChild(QObject,'guard')
            def idle():
                self.assertFalse([obj for obj in guard.findChildren(QObject)
                    if 'Timer' in obj.metaObject().className() and obj.property('running')])
            QTest.qWait(100); idle()  # No desktop container: no retry polling.
            QMetaObject.invokeMethod(root,'attach'); QTest.qWait(1500); idle()
            self.assertTrue(guard.property('initialized'))
            QMetaObject.invokeMethod(root,'move'); QTest.qWait(1200); idle()
            item=guard.property('last').toVariant()['items'][0]
            self.assertEqual((item['x'],item['width']),(160,352))
            self.assertFalse(errors,'\n'.join(errors))
            engine.deleteLater(); QTest.qWait(20)

    def test_layout_guard_keeps_edits_on_done_and_after_restart(self):
        errors=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'edited.qml'
            path.write_text('''import QtQuick
import QtQuick.Layouts
import "'''+QUrl.fromLocalFile(str(WIDGETS)).toString()+'''"
Window { width:1920; height:1080
 Item { id:board; objectName:"board"; width:1920; height:1004
  property QtObject containmentItem: QtObject { property real height:1080 }
  property bool editMode:false; property bool relayoutLock:false; property int cellWidth:16
  property string configKey:"ItemGeometries-1920x1080"
  function releaseSpace(item){} function save(){} function positionItem(item){}
  Component { id:widget
   Item { property int number; objectName:"widget"+number
    property var applet:({plasmoid:{id:number,pluginName:"org.monet.notes",containment:{id:1}}})
    Layout.minimumWidth:100; Layout.minimumHeight:100
    LayoutGuard { storageFile:Qt.resolvedUrl("layouts.conf") }
   }
  }
  function add(number,x,y,w,h) { widget.createObject(board,{number:number,x:x,y:y,width:w,height:h}) }
  function edit() {
   editMode=true; height=852
   const first=children.find(c=>c.number===1)
   first.x=320; first.y=320; first.width=320; first.height=256
   children.find(c=>c.number===2).destroy()
   add(3,800,400,224,224)
  }
  function done() { editMode=false; height=1004 }
  function removeLeader() {
   editMode=true; height=852
   children.find(c=>c.number===1).destroy()
   const remaining=children.find(c=>c.number===3)
   remaining.x=640; remaining.y=336
  }
  Component.onCompleted: { add(1,48,48,224,224); add(2,1552,48,224,224) }
 }
}''')
            def load():
                engine=QQmlApplicationEngine()
                engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
                engine.load(QUrl.fromLocalFile(str(path)))
                self.assertTrue(engine.rootObjects(),errors)
                return engine,engine.rootObjects()[0]
            engine,window=load(); QTest.qWait(1500)
            board=window.findChild(QObject,'board')
            QMetaObject.invokeMethod(board,'edit'); QTest.qWait(50)
            QMetaObject.invokeMethod(board,'done'); QTest.qWait(1700)
            for name,expected in [('widget1',(320,320,320,256)),('widget3',(800,400,224,224))]:
                item=window.findChild(QObject,name)
                self.assertEqual(tuple(item.property(k) for k in ('x','y','width','height')),expected)
            self.assertIsNone(window.findChild(QObject,'widget2'))
            window.close(); engine.deleteLater(); QTest.qWait(20)
            # Plasma reopens the same widget IDs; the guard must use the new snapshot.
            path.write_text(path.read_text().replace('add(2,1552,48,224,224)', 'add(3,48,600,224,224)'))
            engine,window=load(); QTest.qWait(1700)
            item=window.findChild(QObject,'widget1')
            self.assertEqual(tuple(item.property(k) for k in ('x','y','width','height')),(320,320,320,256))
            self.assertEqual(window.findChild(QObject,'widget3').property('x'),800)
            board=window.findChild(QObject,'board')
            QMetaObject.invokeMethod(board,'removeLeader'); QTest.qWait(50)
            QMetaObject.invokeMethod(board,'done'); QTest.qWait(1700)
            self.assertIsNone(window.findChild(QObject,'widget1'))
            item=window.findChild(QObject,'widget3')
            self.assertEqual((item.property('x'),item.property('y')),(640,336))
            self.assertFalse(errors,'\n'.join(errors))
            window.close(); engine.deleteLater(); QTest.qWait(20)

    def test_layout_guard_bypasses_animations_and_restores_positions_after_restart(self):
        engine=QQmlApplicationEngine(); errors=[]
        engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guard.qml'
            path.write_text('''import QtQuick
import QtQuick.Layouts
import "'''+QUrl.fromLocalFile(str(WIDGETS)).toString()+'''"
Window { width:1920; height:1080
 Item { id:board; objectName:"board"; width:1920; height:1004
  property QtObject containmentItem: QtObject { property real height: board.height+76 }
  property bool editMode:false; property bool relayoutLock:false; property int cellWidth:16
  property string configKey:width+"x"+height; property int invalid:0
  function releaseSpace(item){} function save(){}
  function positionItem(item){if(item.x+item.width>width || item.y+item.height>height) invalid++;}
  Item { objectName:"weather"; x:1168; y:48; width:352; height:192
   property var applet:({plasmoid:{id:1,pluginName:"org.monet.weather"}})
   Layout.minimumWidth:252; Layout.minimumHeight:180
   Behavior on x {NumberAnimation {duration:500}} Behavior on y {NumberAnimation {duration:500}}
   LayoutGuard { storageFile: Qt.resolvedUrl("layouts.conf") }
  }
  Item { objectName:"calendar"; x:1552; y:48; width:352; height:272
   property var applet:({plasmoid:{id:2,pluginName:"org.monet.calendar"}})
   Layout.minimumWidth:234; Layout.minimumHeight:252
   Behavior on x {NumberAnimation {duration:500}} Behavior on y {NumberAnimation {duration:500}}
  }
 }
}''')
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            window=engine.rootObjects()[0]; board=window.findChild(QObject,'board')
            QTest.qWait(1400)
            board.setProperty('width',960); board.setProperty('height',464); QTest.qWait(1400)
            self.assertEqual(board.property('invalid'),0)
            board.setProperty('width',1920); board.setProperty('height',1004); QTest.qWait(1400)
            for name,x in [('weather',1168),('calendar',1552)]:
                item=window.findChild(QObject,name)
                self.assertEqual(item.property('x'),x); self.assertEqual(item.property('y'),48)
            # Restart at the smaller logical screen, then return to the original.
            # In-memory snapshots used to lose the original positions here.
            board.setProperty('width',960); board.setProperty('height',464); QTest.qWait(1700)
            self.assertTrue((Path(tmp)/'layouts.conf').exists())
            window.close(); engine.deleteLater(); QTest.qWait(20)
            text=path.read_text().replace('objectName:"board"; width:1920; height:1004',
                                          'objectName:"board"; width:960; height:464')
            path.write_text(text)
            engine=QQmlApplicationEngine()
            engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            window=engine.rootObjects()[0]; board=window.findChild(QObject,'board')
            QTest.qWait(1700)
            self.assertEqual(board.property('invalid'),0)
            board.setProperty('width',1920); board.setProperty('height',1004); QTest.qWait(1700)
            for name,x in [('weather',1168),('calendar',1552)]:
                item=window.findChild(QObject,name)
                self.assertEqual(item.property('x'),x); self.assertEqual(item.property('y'),48)
            self.assertFalse(errors,'\n'.join(errors))
            window.close(); engine.deleteLater(); QTest.qWait(1)

    def test_notes_popup_reopens_and_follows_parent_visibility(self):
        engine=QQmlApplicationEngine(); words=helper('monet-games').Words()
        engine.rootContext().setContextObject(words)
        errors=[]; engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'popup.qml'
            path.write_text('''import QtQuick
import "'''+QUrl.fromLocalFile(str(WIDGETS)).toString()+'''"
Window { id:host; width:960; height:540; visible:true; property bool notesOpen:false
 Item { id:anchor; x:650; y:20; width:280; height:300 }
 QtObject { id:noteData; property var notes:({}); property string problem:""
  function noteFor(day){return ""} function repeatFor(day){return "none"}
  function after(day,count){return []} function write(day,text,repeat){} function retry(){} }
 NotesPopup { objectName:"popup"; anchorItem:anchor; store:noteData
  day:new Date(2026,9,27); today:day; visible:host.notesOpen; onClosed:host.notesOpen=false }
}''')
            engine.load(QUrl.fromLocalFile(str(path))); self.assertTrue(engine.rootObjects(),errors)
            window=engine.rootObjects()[0]; popup=window.findChild(QObject,'popup')
            for _ in range(2):
                window.setProperty('notesOpen',True); QMetaObject.invokeMethod(popup,'write'); QTest.qWait(30)
                self.assertTrue(popup.property('visible'))
                QMetaObject.invokeMethod(popup,'finish'); QTest.qWait(30)
                self.assertFalse(window.property('notesOpen')); self.assertFalse(popup.property('visible'))
            window.setProperty('notesOpen',True); QMetaObject.invokeMethod(popup,'write'); QTest.qWait(30)
            window.setProperty('notesOpen',False); QTest.qWait(30)
            self.assertFalse(popup.property('visible'))
            self.assertFalse(errors,'\n'.join(errors))
            window.close(); engine.deleteLater(); QTest.qWait(1)
