"""Observe actual widget state/helper launches on private native fixture services.

The staged copies add logging, shorten long periodic intervals and select the
fixture output. Production activity bindings and refresh functions stay intact.
"""
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

import dbus
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[2]
name = sys.argv[1]
assert name in {'batteries', 'quick', 'system', 'network', 'storage', 'played', 'frame', 'clock',
               'calendar', 'placard', 'sound', 'stacks', 'transfers', 'worldclock', 'weather'}
assert os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
assert os.environ['HOME'].startswith('/tmp/monet-tests-')


def stop(process):
    process.terminate()
    try: process.wait(timeout=3)
    except subprocess.TimeoutExpired: process.kill(); process.wait()


with tempfile.TemporaryDirectory(prefix='monet-activity-widget-') as temporary:
    folder = Path(temporary)
    data = folder / 'data'; data.mkdir()
    helper_log = folder / 'commands.jsonl'
    env = dict(os.environ, XDG_DATA_HOME=str(data), WAYLAND_DISPLAY='monet-activity-test',
               DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],
               QT_QPA_PLATFORMTHEME='kde', QT_FORCE_STDERR_LOGGING='1', QT_LOGGING_RULES='qml.debug=true')
    package = data / 'plasma/plasmoids' / ('org.monet.' + name)
    shutil.copytree(ROOT / 'linux/share/plasma/plasmoids' / ('org.monet.' + name), package)
    ui = package / 'contents/ui'
    for part in (ROOT / 'linux/share/monet/widgets').iterdir():
        if part.is_file(): shutil.copy2(part, ui / part.name)
    helper = folder / 'helper'
    helper.write_text('''#!/usr/bin/python3
import json, os, sys, time
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(LOG, 'a') as output: output.write(json.dumps([name, args]) + '\\n')
command = args[0] if args else ''
result = {}
if name == 'monet-quick':
    if command == 'listen': time.sleep(25); sys.exit(0)
    if command == 'notes': result = {}
    elif command in ('outputs','played','batteries'): result = []
    elif command == 'sound': result = dict(outputs=[], apps=[], inputs=[], microphone=None)
    elif command == 'status': result = dict(wifi=True, network='', bluetooth=False, night=False, quiet=False,
        volume=40, mic=30, brightness=50, keyboard=None, light='mist')
elif name == 'monet-files-tools': result = dict(free=12345678, total=98765432)
elif name == 'monet-files': result = dict(groups=[], limited=False, folder=Path.home().as_uri())
elif name == 'monet-file-jobs': result = dict(files=[dict(token='a'*32, name='A native transfer',kind='extract',
    destination=str(Path.home()/'Desktop'), destinationUrl=(Path.home()/'Desktop').as_uri(), state='running',
    progress=.4, updated=1, error='')], store=[])
elif name == 'monet-weather': result = dict(config=dict(place='Stockholm', latitude=59.3, longitude=18.1,
    places=[],fahrenheit=False), weather=None, updated=0, stale=True, problem='')
print(json.dumps(result))
'''.replace('LOG', repr(str(helper_log))))
    helper.chmod(0o700)
    for command in ('monet-quick', 'monet-files-tools', 'monet-files', 'monet-file-jobs', 'monet-weather'):
        (folder / command).symlink_to(helper)
    for part in ui.glob('*.qml'):
        source = part.read_text().replace('@LIBEXECDIR@', str(folder)).replace('@BINDIR@', str(folder)).replace('@DATADIR@', '/usr/share')
        # Speed up only the long sampling intervals in disposable source copies.
        source = re.sub(r'interval: (?:10 \* 60 \* 1000|60 \* 1000|60000|3000|1000)(?!\d)', 'interval: 180', source)
        if part.name == 'SessionActivity.qml':
            source = source.replace('property string outputName: Screen.name', 'property string outputName: "eDP-1"')
        part.write_text(source)
    sensors = {'system': '[cpu,cpuHeat,memory,memoryUsed,download,upload,gpu0,gpu1,gpuHeat0,gpuHeat1]',
               'network': '[download,upload,downloaded,uploaded]'}
    extra = {
        'batteries': 'state.levels = root.batteries.map(b => b.level); state.ready = activity.powerReady;',
        'quick': 'state.battery = root.info.battery; state.power = activity.observePower;',
        'clock': 'state.tick = minuteTick.running; state.notes = noteStore.active;',
        'calendar': 'state.notes = noteStore.active;',
        'placard': 'state.tick = minuteTick.running;',
        'frame': 'state.tick = changer.running;',
        'weather': '''state.reading = shared.active;
            root.choosing = fixtureCitySearch.count > 0;
            const search = fixtureFindSearch(root.fullRepresentationItem);
            if (search && root.choosing && search.visible && search.enabled) {
                search.Window.window.requestActivate();
                search.forceActiveFocus();
            }
            state.search = search ? {visible:search.visible, enabled:search.enabled,
                focused:search.activeFocus, cursor:search.cursorVisible} : null;''',
        'sound': 'state.request = root.soundRequest; state.serial = root.requestSerial;',
    }.get(name, '')
    if name in sensors: extra += 'state.sensors = ' + sensors[name] + '.map(s => s.enabled);'
    main = ui / 'main.qml'; source = main.read_text()
    if 'import Qt.labs.folderlistmodel' not in source:
        source = 'import Qt.labs.folderlistmodel\n' + source
    injection = '''
    property int fixtureBeat: 0
    FolderListModel { id: fixtureSwitch; folder: CONTROL; nameFilters: ["collapsed"]; showDirs: false }
    Timer {
        interval: 80; running: true; repeat: true
        onTriggered: {
            root.expanded = fixtureSwitch.count === 0;
            const state = {active: activity.active, native: activity.nativeReady,
                known: activity.nativeReady && activity.nativeState.displayKnown, expanded: root.expanded};
            EXTRA
            console.log("ACTIVITY_FIXTURE", JSON.stringify(state));
            if (root.fullRepresentationItem && root.fullRepresentationItem.width > 100 && fixtureBeat === 2)
                root.fullRepresentationItem.grabToImage(result => result.saveToFile(SNAPSHOT));
            fixtureBeat++;
        }
    }
'''.replace('EXTRA', extra).replace('SNAPSHOT', json.dumps(str(folder / 'widget.png'))).replace('CONTROL', json.dumps(folder.as_uri()))
    if name == 'worldclock':
        # Exercise the native Clock loaders in actual delegates, not an empty list.
        source = source.replace('Array.from(Plasmoid.configuration.zones || [])', '["Europe/Stockholm", "America/New_York"]')
    if name == 'weather':
        injection += '''
    FolderListModel { id: fixtureCitySearch; folder: CONTROL; nameFilters: ["choose-place"]; showDirs: false }
    function fixtureFindSearch(item) {
        if (!item) return null;
        if (item.objectName === "weatherPlaceSearch") return item;
        for (let child of item.children || []) {
            const found = fixtureFindSearch(child);
            if (found) return found;
        }
        return null;
    }
'''.replace('CONTROL', json.dumps(folder.as_uri()))
    source = source[:source.rfind('}')] + injection + '}\n'; main.write_text(source)
    with (folder/'fixture.log').open('w') as fixture_log, (folder/'widget.log').open('w') as widget_log:
        service = subprocess.Popen([os.environ['MONET_ACTIVITY_FIXTURE'], '--fixture'], env=env,
                                   stdout=subprocess.PIPE, stderr=fixture_log, text=True)
        widget = None
        try:
            assert select.select([service.stdout], [], [], 5)[0], 'Native fixture did not start'
            assert service.stdout.readline().strip() == 'READY', (folder/'fixture.log').read_text()
            control = dbus.Interface(dbus.SessionBus().get_object('org.monet.ActivityFixture', '/Fixture'), 'org.monet.ActivityFixture')
            widget = subprocess.Popen(['plasmawindowed', 'org.monet.' + name], env=env, stdout=widget_log, stderr=widget_log)

            def states():
                result = []
                for line in (folder/'widget.log').read_text().splitlines():
                    if 'ACTIVITY_FIXTURE ' in line:
                        result.append(json.loads(line.split('ACTIVITY_FIXTURE ', 1)[1]))
                return result

            def until(predicate, seconds=5):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    observed = states()
                    if observed and predicate(observed[-1]): return observed[-1]
                    assert widget.poll() is None, (folder/'widget.log').read_text()
                    time.sleep(.04)
                raise AssertionError((name, states()[-5:], (folder/'widget.log').read_text()))

            def commands():
                calls = [json.loads(line) for line in helper_log.read_text().splitlines()] if helper_log.exists() else []
                # The program-opening listener and saved panel-layout action
                # remain available while locked; neither is a sampling read.
                return [call for call in calls if call[1] and call[1][0] not in ('listen', 'bar-layout')]

            def paused():
                state = until(lambda s: s['native'] and s['known'] and not s['active'])
                if name in sensors: assert not any(state['sensors']), state
                if name in ('clock','placard','frame'): assert not state['tick'], state
                if name in ('clock','calendar'): assert not state['notes'], state
                if name == 'weather': assert not state['reading'], state
                time.sleep(.25)  # Let already-submitted jobs finish; they need not be cancelled.
                before = len(commands()); metrics = json.loads(str(control.Metrics()))
                time.sleep(.55)
                assert len(commands()) == before, (name, commands()[before:])
                assert json.loads(str(control.Metrics())) == metrics, name

            until(lambda s: s['native'] and s['known'] and s['active'])
            if name == 'batteries': until(lambda s: s['ready'] and len(s['levels']) > 0)
            if name == 'weather':
                until(lambda s: s['search'] and not s['search']['visible'])
                (folder / 'choose-place').touch()
                until(lambda s: s['search'] and s['search']['visible'] and s['search']['focused'] and s['search']['cursor'])
                (folder / 'choose-place').unlink()
                hidden = until(lambda s: s['search'] and not s['search']['visible'])
                assert not any(hidden['search'][k] for k in ('enabled','focused','cursor')), hidden
            time.sleep(.5)
            visible = len(commands())
            control.SetLocked(True); paused()
            control.SetBattery(dbus.Double(37), dbus.Boolean(True))
            control.SetLocked(False)
            resumed = until(lambda s: s['active'])
            if name in sensors: assert all(resumed['sensors']), resumed
            if name == 'batteries': until(lambda s: s['ready'] and 37 in s['levels'])
            if name == 'quick': until(lambda s: s.get('battery') == 37)
            if name in ('storage','played','clock','calendar','sound','stacks','transfers','weather'):
                deadline = time.monotonic() + 3
                while len(commands()) <= visible and time.monotonic() < deadline: time.sleep(.05)
                assert len(commands()) > visible, (name, 'no fresh read after resume', commands())
            assert control.SetMode('eDP-1', dbus.UInt32(3)); paused()
            assert control.SetMode('eDP-1', dbus.UInt32(0)); until(lambda s: s['active'])
            time.sleep(.2)
            if name in ('quick', 'clock', 'transfers'):
                (folder / 'collapsed').touch()
                state = until(lambda s: not s['expanded'])
                assert state['active'], state
                if name == 'clock': assert not state['notes'] and state['tick'], state
                if name == 'quick': assert not state['power'], state
                time.sleep(.25)
                before = len(commands()); metrics = json.loads(str(control.Metrics()))
                time.sleep(.55)
                assert len(commands()) == before, (name, 'closed popup still polls', commands()[before:])
                assert json.loads(str(control.Metrics())) == metrics, (name, 'closed popup still reads power')
                (folder / 'collapsed').unlink(); until(lambda s: s['expanded'])
            assert not any(args and args[0] == 'batteries' for command,args in commands()), commands()
            metrics = json.loads(str(control.Metrics())); assert metrics['modeRequests'] == 0, metrics
            errors = ('is not a type','is not installed','TypeError:','ReferenceError:',
                      'Cannot assign to non-existent property','Unable to assign', 'Cannot assign object')
            log = (folder/'widget.log').read_text()
            assert not any(error in log for error in errors), log
            assert (folder/'widget.png').exists(), log
            image = QImage(str(folder/'widget.png')); assert image.width() > 100 and image.height() > 80, image.size()
            print(json.dumps(dict(widget=name, helperCalls=len(commands()), nativeMetrics=metrics, rendered=[image.width(),image.height()])))
        finally:
            if widget is not None: stop(widget)
            stop(service); service.stdout.close()
            if os.environ.get('MONET_ACTIVITY_CAPTURE'):
                destination = Path(os.environ['MONET_ACTIVITY_CAPTURE']) / name; destination.mkdir(parents=True, exist_ok=True)
                for filename in ('widget.log', 'widget.png', 'fixture.log', 'commands.jsonl'):
                    if (folder/filename).exists(): shutil.copy2(folder/filename, destination/filename)
