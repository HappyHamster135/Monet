"""Run the wallpaper scene with native activity and a controlled weather server.

Only the containment-provided configuration and root window are supplied by the
fixture. Painting, network callbacks, timers and animations use the full source.
"""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dbus
from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlPropertyMap
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
assert os.environ['HOME'].startswith('/tmp/monet-tests-')
os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = os.environ['DBUS_SESSION_BUS_ADDRESS']
os.environ['WAYLAND_DISPLAY'] = 'monet-activity-test'


class Words(QObject):
    @Slot(str, result=str)
    def i18n(self, text): return text
    @Slot(str, str, result=str)
    def i18nd(self, domain, text): return text


class Weather(BaseHTTPRequestHandler):
    requests = 0
    weather_code = 45
    arrived = threading.Event()
    release = threading.Event()

    def log_message(self, *args): pass
    def do_GET(self):
        type(self).requests += 1; self.arrived.set()
        if not self.release.wait(timeout=10): return
        raw = json.dumps({'current': {'weather_code': type(self).weather_code}}).encode()
        try:
            self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError): pass


app = QGuiApplication([])
with tempfile.TemporaryDirectory(prefix='monet-activity-wallpaper-') as temporary:
    folder = Path(temporary)
    with (folder/'service.log').open('w') as log:
        service = subprocess.Popen([os.environ['MONET_ACTIVITY_FIXTURE'], '--fixture'], stdout=subprocess.PIPE,
                                   stderr=log, text=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Weather)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        engine = QQmlApplicationEngine(); root = None
        try:
            assert select.select([service.stdout], [], [], 5)[0] and service.stdout.readline().strip() == 'READY'
            control = dbus.Interface(dbus.SessionBus().get_object('org.monet.ActivityFixture', '/Fixture'), 'org.monet.ActivityFixture')
            control.SetLocked(True)
            config = QQmlPropertyMap()
            for key, value in dict(PhotoFolder='', Series='hours', Painting='day', Place='59.3,18.1', Weather=True, Focus='').items():
                config.insert(key, value)
            words = Words(); engine.rootContext().setContextObject(words)
            engine.rootContext().setContextProperty('fixtureConfig', config)
            errors = []; engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
            for part in ('SessionActivity.qml', 'TaskManagerAction.qml'):
                shutil.copy2(ROOT/'linux/share/monet/widgets'/part, folder/part)
            gate = folder/'SessionActivity.qml'
            gate.write_text(gate.read_text().replace('property string outputName: Screen.name', 'property string outputName: "eDP-1"'))
            source = (ROOT/'linux/share/plasma/wallpapers/org.monet.hours/contents/ui/main.qml').read_text()
            source = source.replace('WallpaperItem {', '''Window {
    width: 640; height: 360; visible: true
    property var configuration: fixtureConfig
    property list<QtObject> contextualActions
    readonly property bool sampling: activity.active
    readonly property bool nativeReady: activity.nativeReady && activity.nativeState.lockKnown && activity.nativeState.displayKnown
    readonly property bool paintingReady: below.status === Image.Ready
    readonly property string paintedSource: below.source.toString()
    readonly property bool fading: fade.running || veilMotion.running
    readonly property bool fetching: skyRequest !== null
''', 1)
            source = source.replace('@DATADIR@', str(ROOT/'linux/share'))
            source = source.replace('https://api.open-meteo.com', 'http://127.0.0.1:' + str(server.server_port))
            path = folder/'Wallpaper.qml'; path.write_text(source)
            engine.load(QUrl.fromLocalFile(str(path))); assert engine.rootObjects(), errors
            root = engine.rootObjects()[0]

            def until(predicate):
                for _ in range(200):
                    if predicate(): return
                    QTest.qWait(20)
                raise AssertionError(dict(errors=errors, requests=Weather.requests,
                                          sampling=root.property('sampling'), fetching=root.property('fetching')))

            until(lambda: root.property('nativeReady') and not root.property('sampling') and root.property('paintingReady'))
            assert not root.property('fading') and not root.property('fetching')
            assert Weather.requests == 0
            assert root.property('paintedSource').endswith('/day.jpg')
            control.SetLocked(False)
            until(lambda: Weather.arrived.is_set() and root.property('fetching'))
            # Abort an in-flight response at lock; releasing it cannot animate or repaint.
            control.SetLocked(True); until(lambda: not root.property('sampling') and not root.property('fetching'))
            Weather.release.set(); QTest.qWait(150)
            assert root.property('veil') == 0 and not root.property('fading')
            config.insert('Painting', 'night')
            QTest.qWait(100); assert root.property('paintedSource').endswith('/day.jpg')
            count = Weather.requests; QTest.qWait(250); assert Weather.requests == count
            control.SetLocked(False)
            until(lambda: root.property('veil') == .32)
            until(lambda: root.property('fading'))
            # Weather should settle shortly after its response, rather than
            # drive full-desktop frames throughout the first minutes of use.
            until(lambda: not root.property('fading'))
            assert abs(root.property('paintedVeil') - .32) < .0001
            # A later weather change must still pause immediately at DPMS off.
            Weather.weather_code = 3
            config.insert('Place', '59.4,18.1')
            until(lambda: root.property('veil') == .08 and root.property('fading'))
            assert control.SetMode('eDP-1', dbus.UInt32(3))
            until(lambda: not root.property('sampling') and not root.property('fading'))
            assert control.SetMode('eDP-1', dbus.UInt32(0))
            until(lambda: root.property('sampling'))
            root.hide(); until(lambda: not root.property('sampling') and not root.property('fading'))
            root.show(); until(lambda: root.property('sampling'))
            image = root.grabWindow(); assert not image.isNull()
            if os.environ.get('MONET_ACTIVITY_CAPTURE'):
                destination = Path(os.environ['MONET_ACTIVITY_CAPTURE'])/'wallpaper'; destination.mkdir(parents=True, exist_ok=True)
                image.save(str(destination/'wallpaper.png'))
            assert not errors, errors
            assert json.loads(str(control.Metrics()))['modeRequests'] == 0
            print(json.dumps(dict(staticLockedPainting=True, inFlightAbort=True, pausedAnimations=True,
                                  weatherSettles=True,
                                  displayAndWindowGating=True, requests=Weather.requests)))
        finally:
            if root is not None: root.close()
            engine.deleteLater(); QTest.qWait(40)
            Weather.release.set(); server.shutdown(); server.server_close(); thread.join(timeout=2)
            service.terminate()
            try: service.wait(timeout=3)
            except subprocess.TimeoutExpired: service.kill(); service.wait()
            service.stdout.close()
