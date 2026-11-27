"""The compact wave stays bounded, settles on pause and honors reduced motion."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


@unittest.skipUnless(QQuickView, 'requires Qt Quick')
class AudioWave(unittest.TestCase):
    def test_live_silent_paused_and_reduced_motion_shapes(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Wave.qml'
            path.write_text('import QtQuick\nimport "' + UI.as_uri() + '''" as Monet
Monet.IslandAudioBars {
    id: wave
    width: implicitWidth; height: 16; live: true; motion: false
    function snapshot() {
        let bars = []
        function visit(item) {
            if (item.objectName.startsWith("notchAudioBar-")) {
                const p = item.mapToItem(wave,0,0)
                bars.push({x:p.x,y:p.y,width:item.width,height:item.height})
            }
            for (const child of item.children) visit(child)
        }
        visit(wave)
        return JSON.stringify(bars)
    }
}''')
            view = QQuickView()
            errors = []
            view.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
            view.setSource(QUrl.fromLocalFile(str(path)))
            self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
            view.show(); QTest.qWait(40)
            wave = view.rootObject()
            for level in (0, 0.5, 1, 12):
                wave.setProperty('level', level); QTest.qWait(30)
                bars = json.loads(wave.snapshot())
                self.assertEqual(len(bars), 9)
                for bar in bars:
                    self.assertGreaterEqual(bar['x'], -0.01)
                    self.assertGreaterEqual(bar['y'], -0.01)
                    self.assertLessEqual(bar['x'] + bar['width'], wave.width()+0.01)
                    self.assertLessEqual(bar['y'] + bar['height'], wave.height()+0.01)
            before = json.loads(wave.snapshot()); QTest.qWait(120)
            self.assertEqual(json.loads(wave.snapshot()), before)
            wave.setProperty('motion', True); wave.setProperty('level', 0); QTest.qWait(150)
            self.assertTrue(all(abs(bar['height']-bar['width']) < .01 for bar in json.loads(wave.snapshot())))
            wave.setProperty('live', False); QTest.qWait(120)
            moving = json.loads(wave.snapshot()); QTest.qWait(120)
            self.assertNotEqual(json.loads(wave.snapshot()), moving)
            wave.setProperty('playing', False); QTest.qWait(40)
            paused = json.loads(wave.snapshot()); QTest.qWait(120)
            self.assertEqual(json.loads(wave.snapshot()), paused)
            self.assertTrue(all(abs(bar['height']-bar['width']) < .01 for bar in paused))
            view.close()
            self.assertFalse(errors, errors)
