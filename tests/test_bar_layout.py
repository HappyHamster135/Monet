"""Dock bounds leave room for content changes and avoid the other Monet panels."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_look import quick_helper


class DockBounds(unittest.TestCase):
    def test_center_dock_can_grow_and_shrink_without_reserving_closed_task_slots(self):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            self.skipTest("Qt runtime")
        app = QCoreApplication.instance() or QCoreApplication([])
        quick = quick_helper()
        with patch.object(quick, 'DATADIR', Path(__file__).resolve().parents[1] / 'linux/share'), \
             patch.object(quick, 'plasma_script') as call:
            quick.fit_bars()
        self.assertEqual(call.call_count, 1)
        script = call.call_args.args[-1]
        engine = QJSEngine()
        engine.evaluate('''
            function panel(id,screen,location,types,length,alignment="left") {
                let config = {};
                return {id,screen,location,length,minimumLength:621,maximumLength:621,
                        alignment,offset:0,widgets:type=>types.filter(t=>!type || t===type).map(type=>({type})),
                        readConfig:(key,fallback)=>config[key]||fallback,writeConfig:(key,value)=>{config[key]=value}};
            }
            var left=panel(1,0,"bottom",["org.monet.menu"],120);
            var dock=panel(2,0,"bottom",["org.kde.plasma.icontasks","org.kde.plasma.trash",
                           "org.kde.plasma.marginsseparator"],553,"center");
            var right=panel(3,0,"bottom",["org.monet.quick"],462,"right");
            var unrelated=panel(4,1,"bottom",["org.kde.plasma.icontasks"],500);
            var top=panel(5,0,"top",["org.kde.plasma.icontasks"],500);
            function panels(){return [left,dock,right,unrelated,top]}
            var width=1920;
            function screenGeometry(){return {width}}
            function print(){}
        ''')
        result = engine.evaluate('{'+script+'}')
        self.assertFalse(result.isError(), result.toString())
        value = json.loads(engine.evaluate('JSON.stringify([dock,unrelated,top])').toString())
        dock = value[0]
        self.assertEqual((dock['alignment'],dock['offset'],dock['minimumLength']),('left',675,80))
        self.assertGreater(dock['maximumLength'],dock['minimumLength'])
        for content in (420,553,621,1500):
            width = min(dock['maximumLength'],max(dock['minimumLength'],content))
            self.assertGreaterEqual(dock['offset'],120+16+8)
            self.assertLessEqual(dock['offset']+width,1920-462-16-8)
        self.assertEqual(dock['length'],553)  # Never freeze length to a snapshot.
        self.assertEqual(value[1]['minimumLength'],621)
        self.assertEqual(value[2]['minimumLength'],621)
        self.assertFalse(engine.evaluate('width=460; {'+script+'}').isError())
        self.assertEqual(json.loads(engine.evaluate('JSON.stringify([dock.maximumLength,right.maximumLength])').toString()),
                         [80,228])
