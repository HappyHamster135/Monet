"""Dock bounds leave room for content changes and avoid the other Monet panels."""
import json
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper

# A pretend Plasma: panels keep config like Plasma's, and settle() lays one out the way
# Plasma does, its contents' length within its limits when custom, its contents' when fit.
PLASMA = '''
function panel(id,screen,location,type,length,alignment) {
    return {id,screen,location,length,content:length,minimumLength:621,maximumLength:621,
            alignment:alignment||"left",offset:650,lengthMode:"fit",data:{},currentConfigGroup:[],
            readConfig:function(k,d){var v=this.data[this.currentConfigGroup.join("/")+"/"+k]; return v===undefined?d:v},
            writeConfig:function(k,v){this.data[this.currentConfigGroup.join("/")+"/"+k]=v},
            widgets:()=>type ? [].concat(type).map(t=>({type:t})) : []};
}
function settle(p) {
    p.length = p.lengthMode === "custom" ? Math.min(p.maximumLength, Math.max(p.minimumLength, p.content)) : p.content;
}
'''


def engine():
    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QJSEngine
    except ImportError:
        raise unittest.SkipTest("Qt runtime")
    QCoreApplication.instance() or QCoreApplication([])
    js = QJSEngine()
    js.evaluate(PLASMA)
    return js


def fitting_script():
    quick = quick_helper()
    with patch.object(quick, 'run', return_value='') as call:
        quick.fit_bars()
    assert call.call_count == 1
    return call.call_args.args[-1]


class DockBounds(unittest.TestCase):
    def test_center_dock_can_grow_and_shrink_without_reserving_closed_task_slots(self):
        js = engine()
        script = fitting_script()
        js.evaluate('''
            var left=panel(1,0,"bottom","org.monet.menu",120);
            var dock=panel(2,0,"bottom","org.kde.plasma.icontasks",553);
            var right=panel(3,0,"bottom","org.monet.quick",462);
            var unrelated=panel(4,1,"bottom","org.kde.plasma.icontasks",500);
            var top=panel(5,0,"top","org.kde.plasma.icontasks",500);
            function panels(){return [left,dock,right,unrelated,top]}
            function screenGeometry(){return {width:1920}}
        ''')
        result = js.evaluate(script)
        self.assertFalse(result.isError(), result.toString())
        value = json.loads(js.evaluate('JSON.stringify([dock,unrelated,top])').toString())
        dock = value[0]
        self.assertEqual((dock['alignment'],dock['offset'],dock['minimumLength']),('center',0,80))
        self.assertGreater(dock['maximumLength'],dock['minimumLength'])
        for content in (420,553,621,1500):
            width = min(dock['maximumLength'],max(dock['minimumLength'],content))
            self.assertGreaterEqual((1920-width)/2,120+32)
            self.assertLessEqual((1920+width)/2,1920-462-32)
        self.assertEqual(dock['length'],553)  # Never freeze length to a snapshot.
        self.assertEqual(value[1]['minimumLength'],621)
        self.assertEqual(value[2]['minimumLength'],621)


class NarrowScreens(unittest.TestCase):
    """Portrait, small or highly scaled screens: widths in Plasma's logical pixels, with the
    islands' usual lengths (Monet menu and Games 120; weather, quick settings, sound, tray
    and clock 462). Centred, the dock clears the right island only from 2 x 462 + 64 + 80
    = 1068 pixels."""

    def setUp(self):
        self.js = engine()
        self.script = fitting_script()
        self.js.evaluate('''
            var screenWidth=1920;
            var left=panel(1,0,"bottom",["org.monet.menu","org.monet.games"],120,"left");
            var dock=panel(2,0,"bottom",["org.kde.plasma.icontasks","org.kde.plasma.trash"],553,"center");
            var right=panel(3,0,"bottom",["org.monet.quick","org.kde.plasma.systemtray"],462,"right");
            var all=[left,dock,right];
            function panels(){return all}
            function screenGeometry(){return {width:screenWidth}}
        ''')

    def fit(self, width, dock=553):
        # Plasma lays the bars out, and the quick settings island asks again when it changes size.
        self.js.evaluate(f'screenWidth={width}; dock.content={dock};')
        for _ in range(3):
            result = self.js.evaluate(self.script)
            self.assertFalse(result.isError(), result.toString())
            self.js.evaluate('all.forEach(settle)')
        return json.loads(self.js.evaluate('JSON.stringify({left,dock,right})').toString())

    def spans(self, width, bars):
        left, dock, right = bars['left'], bars['dock'], bars['right']
        if dock['alignment'] == 'center':
            dock_span = ((width - dock['length']) / 2, (width + dock['length']) / 2)
        else:
            dock_span = (dock['offset'], dock['offset'] + dock['length'])
        return ((left['offset'], left['offset'] + left['length']), dock_span,
                (width - right['offset'] - right['length'], width - right['offset']))

    def test_the_dock_never_covers_a_side_island(self):
        for width, centred, narrowed in ((1920, True, False), (1280, True, False), (1068, True, False),
                                         (1024, False, False), (800, False, False), (640, False, True)):
            for content in (80, 300, 553, 1500):
                with self.subTest(width=width, dock=content):
                    bars = self.fit(width, content)
                    left, dock, right = self.spans(width, bars)
                    self.assertGreaterEqual(left[0], 0)
                    self.assertLessEqual(right[1], width)
                    self.assertGreaterEqual(dock[0] - left[1], 16)
                    self.assertGreaterEqual(right[0] - dock[1], 16)
                    self.assertGreaterEqual(bars['dock']['length'], 80)
                    self.assertEqual(bars['dock']['alignment'] == 'center', centred)
                    self.assertEqual(bars['right']['lengthMode'] == 'custom', narrowed)
                    self.assertEqual(bars['left']['lengthMode'], 'fit')
                    # Its whole length shows whenever there's room for it.
                    if not narrowed:
                        self.assertEqual(bars['right']['length'], 462)
                    # Nothing changes when it's asked again with nothing new.
                    again = self.fit(width, content)
                    self.assertEqual(again, bars)

    def test_a_narrowed_island_takes_its_length_again_when_there_is_room(self):
        self.assertEqual(self.fit(640)['right']['length'], 640 - 80 - 64 - 120)
        for width in (700, 800, 1920):
            with self.subTest(width=width):
                bars = self.fit(width)
                self.assertEqual(bars['right']['lengthMode'] == 'custom', width == 700)
                self.assertEqual(bars['right']['data'].get('MonetBar/narrowed'), 'true' if width == 700 else '')
                self.assertEqual(bars['right']['length'], 700 - 80 - 64 - 120 if width == 700 else 462)
        self.assertEqual(self.fit(1920)['dock']['alignment'], 'center')

    def test_role_markers_and_one_bar(self):
        # A side island whose own widgets were removed is still the island Monet made.
        self.js.evaluate('''
            left.widgets=()=>[]; left.currentConfigGroup=["MonetBar"]; left.writeConfig("role","left");
            var single=panel(4,1,"bottom",["org.monet.menu","org.kde.plasma.icontasks","org.monet.quick"],700,"center");
            single.lengthMode="fill"; all.push(single);
        ''')
        bars = self.fit(800)
        self.assertEqual(bars['dock']['alignment'], 'left')
        self.assertEqual(bars['dock']['offset'], 120 + 32)
        single = json.loads(self.js.evaluate('JSON.stringify(single)').toString())
        self.assertEqual((single['lengthMode'], single['offset'], single['alignment']), ('fill', 650, 'center'))
