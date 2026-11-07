"""Inactive QML stores defer reads while preserving queued preference writes."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from PySide6.QtCore import QMetaObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
assert os.environ['HOME'].startswith('/tmp/monet-tests-')
app = QGuiApplication([])
with tempfile.TemporaryDirectory(prefix='monet-activity-stores-') as temporary:
    folder = Path(temporary); log = folder / 'calls.jsonl'; preferences = folder / 'weather.json'
    for part in (ROOT / 'linux/share/monet/widgets').iterdir():
        if part.is_file(): shutil.copy2(part, folder / part.name)
    shutil.copy2(ROOT / 'linux/share/plasma/plasmoids/org.monet.weather/contents/ui/WeatherStore.qml', folder / 'WeatherStore.qml')
    script = folder / 'helper'
    script.write_text('''#!/usr/bin/python3
import json, subprocess, sys, time
from pathlib import Path
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with open(LOG, 'a') as output: output.write(json.dumps([name, args]) + '\\n')
time.sleep(.08)
if name == 'notes':
    raise SystemExit(subprocess.run([sys.executable, REAL, *args]).returncode)
file = Path(PREFS)
config = json.loads(file.read_text()) if file.exists() else dict(place='',latitude=0,longitude=0,places=[],fahrenheit=False)
if args[0] == 'set':
    config.update(json.loads(bytes.fromhex(args[1])))
    file.write_text(json.dumps(config))
print(json.dumps(dict(config=config,weather=None,updated=0,stale=False,problem='')))
'''.replace('LOG', repr(str(log))).replace('REAL', repr(str(ROOT / 'linux/libexec/monet-quick'))).replace('PREFS', repr(str(preferences))))
    script.chmod(0o700)
    for name in ('notes','weather'): (folder / name).symlink_to(script)
    path = folder / 'Stores.qml'
    path.write_text('''import QtQuick
Item {
    property bool sampling: false
    property int pendingNotes: notes.writing
    property int pendingWeather: weather.queue.length + (weather.inFlight ? 1 : 0)
    property bool notesLoaded: notes.loaded
    property bool weatherLoaded: weather.loaded
    NoteStore { id: notes; helper: NOTE_HELPER; active: sampling }
    WeatherStore { id: weather; helper: WEATHER_HELPER; active: sampling }
    function writeWhileInactive() {
        notes.write(new Date(2026, 10, 5), "Saved while inactive", "none");
        notes.write(new Date(2026, 10, 6), "Second queued note", "weekly");
        weather.refresh(); weather.seed({place: "Deferred legacy seed"});
        weather.write({place:"Stockholm",latitude:59.3,longitude:18.1});
        weather.write({fahrenheit:true});
    }
    function requestReads() { notes.refresh(); weather.refresh(); }
}'''.replace('NOTE_HELPER', json.dumps(str(folder/'notes'))).replace('WEATHER_HELPER', json.dumps(str(folder/'weather'))))
    engine = QQmlApplicationEngine(); errors = []
    engine.warnings.connect(lambda values: errors.extend(v.toString() for v in values))
    engine.load(QUrl.fromLocalFile(str(path))); assert engine.rootObjects(), errors
    root = engine.rootObjects()[0]

    def until(predicate):
        for _ in range(150):
            if predicate(): return
            QTest.qWait(20)
        raise AssertionError((errors, log.read_text() if log.exists() else 'no calls'))

    def calls(): return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    try:
        QTest.qWait(150); assert calls() == [], calls()
        QMetaObject.invokeMethod(root, 'writeWhileInactive')
        until(lambda: root.property('pendingNotes') == 0 and root.property('pendingWeather') == 1)
        # Seed is deferred; both explicit weather writes and both real note saves finish.
        saved = json.loads((Path(os.environ['XDG_DATA_HOME'])/'monet/notes.json').read_text())
        assert saved['2026-11-05'] == 'Saved while inactive', saved
        assert saved['2026-11-06'] == dict(text='Second queued note', repeat='weekly'), saved
        assert json.loads(preferences.read_text())['fahrenheit'] is True
        assert len([args for command,args in calls() if command == 'notes' and args[0] == 'note']) == 2
        assert len([args for command,args in calls() if command == 'weather' and args[0] == 'set']) == 2
        assert not any(args[0] in ('notes', 'status', 'seed') for command,args in calls()), calls()
        QMetaObject.invokeMethod(root, 'requestReads'); QTest.qWait(200)
        before = calls(); assert len(before) == 4, before
        root.setProperty('sampling', True)
        until(lambda: root.property('notesLoaded') and root.property('weatherLoaded') and root.property('pendingWeather') == 0)
        assert any(args[0] == 'notes' for command,args in calls())
        assert any(args[0] == 'seed' for command,args in calls())
        assert any(args[0] == 'status' for command,args in calls())
        assert not errors, errors
        print(json.dumps(dict(inactiveNoteSaves=2, inactiveWeatherWrites=2, deferredReads='resumed')))
    finally:
        engine.deleteLater(); QTest.qWait(30)
