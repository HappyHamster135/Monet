"""Private audio server: never connects to or changes the laptop's audio devices."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import time

from PySide6.QtCore import QUrl, QMetaObject, QObject
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
TEMP = Path(os.environ['MONET_AUDIO_FIXTURE'])
assert Path(os.environ['XDG_RUNTIME_DIR']).is_relative_to(TEMP)
assert os.environ['PULSE_SERVER'] == 'unix:' + str(TEMP / 'runtime/pulse/native')
UI = ROOT / 'linux/share/plasma/plasmoids/org.monet.sound/contents/ui'
app = QGuiApplication([])
engine = QQmlEngine()
objects = []
server = None
core = None
module_ids = {}
log = (TEMP / 'server.log').open('w')
config = TEMP / 'core.conf'
config.write_text("""context.properties = { core.daemon = true core.name = pipewire-0 support.dbus = false }
context.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-access args = { access.force = unrestricted } }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-spa-node-factory }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-link-factory }
]
context.objects = [ { factory = metadata args = { metadata.name = default } } ]
""")
pulse_config = TEMP / 'pulse.conf'
pulse_config.write_text("""context.properties = { support.dbus = false }
context.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-protocol-pulse }
]
pulse.properties = { server.address = [ "unix:native" ] }
""")
value = TEMP / 'value'
value.write_text('Volume: 0.37\n')
failed = TEMP / 'failed'
calls = TEMP / 'calls'
helper = TEMP / 'fallback'
helper.write_text(f'''#!/bin/sh
echo call >> '{calls}'
[ ! -e '{TEMP / "slow"}' ] || sleep .4
[ ! -e '{failed}' ] || exit 1
cat '{value}'
''')
helper.chmod(0o700)


def wait_for(test, description, timeout=7000):
    until = time.monotonic() + timeout / 1000
    while time.monotonic() < until:
        if test(): return
        QTest.qWait(20)
    if not test():
        readings = [{key: obj.property(key) for key in ('nativeReady', 'volume', 'muted', 'description', 'pending')}
                    for _, obj in objects]
        children = [{key: obj.property(key) for key in ('ready', 'hasOutput', 'volume', 'muted', 'description')}
                    for _, parent in objects for obj in parent.findChildren(QObject)
                    if obj.metaObject().indexOfProperty('hasOutput') >= 0]
        try: sinks = [{k: row.get(k) for k in ['name', 'mute', 'volume']}
                      for row in json.loads(pactl('-f', 'json', 'list', 'sinks'))]
        except Exception: sinks = []
        raise AssertionError(f"{description}: {readings}; children={children}; sinks={sinks}")


def pactl(*args):
    return subprocess.check_output(['pactl', *args], text=True, stderr=subprocess.PIPE, timeout=5).strip()


def choose_sink(name):
    pactl('set-default-sink', name)
    # No session manager or hardware discovery runs in this fixture. Publish
    # the policy decision WirePlumber normally makes for a configured default.
    subprocess.run(['pw-metadata', '-n', 'default', '0', 'default.audio.sink',
                    json.dumps({'name': name}), 'Spa:String:JSON'], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5)


def start_server():
    global server, core
    if core is None:
        core = subprocess.Popen(['pipewire', '-c', str(config)], stdout=subprocess.DEVNULL, stderr=log)
        wait_for(lambda: (TEMP / 'runtime/pipewire-0').exists(), 'private PipeWire core')
    server = subprocess.Popen(['pipewire-pulse', '-c', str(pulse_config)], stdout=subprocess.DEVNULL, stderr=log)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise AssertionError((TEMP / 'server.log').read_text())
        try:
            pactl('info')
            module_ids['one'] = pactl('load-module', 'module-null-sink', 'sink_name=monet_one', 'sink_properties=device.description=First')
            module_ids['two'] = pactl('load-module', 'module-null-sink', 'sink_name=monet_two', 'sink_properties=device.description=Second')
            choose_sink('monet_one')
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            QTest.qWait(50)
    raise AssertionError('private PipeWire audio server did not start: ' + (TEMP / 'server.log').read_text())


def stop_server():
    global server
    if server:
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
        server = None


def create(native=True):
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(UI / 'AudioLevel.qml')))
    props = {'fallbackCommand': str(helper)}
    if not native: props['nativeSource'] = QUrl.fromLocalFile(str(TEMP / 'unsupported.qml'))
    obj = component.createWithInitialProperties(props)
    assert obj is not None, [e.toString() for e in component.errors()]
    objects.append((component, obj))
    return obj


def number_calls():
    return len(calls.read_text().splitlines()) if calls.exists() else 0


def refresh(obj):
    assert QMetaObject.invokeMethod(obj, 'refresh')


def native_updates():
    start_server()
    pactl('set-sink-volume', 'monet_one', '45%')
    obj = create()
    wait_for(lambda: obj.property('nativeReady') and obj.property('volume') == 45, 'native initial volume')
    QTest.qWait(500)
    count = number_calls()
    QTest.qWait(2400)
    assert number_calls() == count, 'idle native audio spawned a fallback command'
    pactl('set-sink-volume', 'monet_one', '0%')
    wait_for(lambda: obj.property('volume') == 0, 'zero volume', timeout=1000)
    assert obj.property('hasOutput')
    pactl('set-sink-mute', 'monet_one', '1')
    wait_for(lambda: obj.property('muted'), 'mute event', timeout=1000)
    pactl('set-sink-volume', 'monet_two', '73%')
    choose_sink('monet_two')
    wait_for(lambda: obj.property('volume') == 73 and not obj.property('muted'), 'new default sink')
    assert obj.property('description') == 'Second'
    pactl('unload-module', module_ids['two'])
    wait_for(lambda: obj.property('description') == 'First', 'removed default sink')
    print(json.dumps({'native_events': 'passed', 'idle_fallback_commands': number_calls() - count}))


def fallback():
    obj = create(native=False)
    wait_for(lambda: obj.property('volume') == 37, 'unsupported native reader fallback')
    value.write_text('Volume: 0.67 [MUTED]\n')
    count = number_calls()
    for _ in range(5): refresh(obj)
    wait_for(lambda: obj.property('volume') == 67 and obj.property('muted'), 'fresh fallback response')
    assert number_calls() == count + 1, 'overlapping refreshes were not coalesced'
    failed.touch(); refresh(obj)
    wait_for(lambda: obj.property('volume') is None, 'failed fallback must discard stale volume')
    failed.unlink(); value.write_text('Volume: 0.52\n')
    wait_for(lambda: obj.property('volume') == 52, 'automatic fallback retry')
    obj.setProperty('active', False)
    value.write_text('Volume: 0.29\n'); count = number_calls()
    for _ in range(5): refresh(obj)
    QTest.qWait(2400)
    assert number_calls() == count, 'inactive fallback kept launching commands'
    assert obj.property('volume') == 52, 'inactive view lost its last reading'
    obj.setProperty('active', True)
    wait_for(lambda: obj.property('volume') == 29, 'fresh reading immediately after resume')
    print(json.dumps({'fallback_refresh_failure_retry': 'passed', 'inactive_reads': 0, 'resume': 'fresh'}))


def recovery():
    start_server()
    pactl('set-sink-volume', 'monet_one', '45%')
    (TEMP / 'slow').touch()
    value.write_text('Volume: 0.91\n')
    obj = create(native=False)
    wait_for(lambda: bool(obj.property('pending')), 'slow request started')
    obj.setProperty('nativeSource', QUrl.fromLocalFile(str(UI / 'NativeAudioStatus.qml')))
    wait_for(lambda: obj.property('nativeReady') and obj.property('volume') == 45, 'native reader activated')
    QTest.qWait(700)
    assert obj.property('volume') == 45, 'late fallback reply overwrote native volume'
    (TEMP / 'slow').unlink(); value.write_text('Volume: 0.37\n')
    stop_server()
    wait_for(lambda: not obj.property('nativeReady') and obj.property('volume') == 37, 'disconnection fallback')
    start_server()
    pactl('set-sink-volume', 'monet_one', '62%')
    wait_for(lambda: obj.property('nativeReady') and obj.property('volume') == 62, 'audio service reconnect', timeout=15000)
    QTest.qWait(500); count = number_calls(); QTest.qWait(2400)
    assert number_calls() == count, 'fallback kept polling after reconnection'
    print(json.dumps({'late_reply_and_server_reconnect': 'passed'}))


def widget():
    start_server()
    pactl('set-sink-volume', 'monet_one', '45%')
    folder = TEMP / 'data/plasma/plasmoids/org.monet.sound'
    shutil.copytree(UI.parent.parent, folder)
    for part in (ROOT / 'linux/share/monet/widgets').iterdir():
        if part.is_file(): shutil.copy2(part, folder / 'contents/ui' / part.name)
    for name in ("VolumeMixer.qml", "MixerModel.qml"):
        shutil.copy2(ROOT / "linux/share/monet/settings-app" / name, folder / "contents/ui" / name)
    quick = TEMP / 'monet-quick'
    quick.write_text('#!/bin/sh\necho \'{"outputs":[{"id":1,"name":"First","default":true}],"apps":[],"inputs":[],"microphone":null}\'\n')
    quick.chmod(0o700)
    for part in (folder / 'contents/ui').glob('*.qml'):
        part.write_text(part.read_text().replace('@LIBEXECDIR@', str(TEMP)).replace('@DATADIR@', '/usr/share'))
    main = folder / 'contents/ui/main.qml'
    source = main.read_text()
    source = source[:source.rfind('}')] + '''
    property string fixtureState: JSON.stringify({volume: volume, muted: muted, silent: silent,
                                                 playing: playing, native: audioLevel.nativeReady})
    onFixtureStateChanged: console.log("MONET_AUDIO", fixtureState)
    Timer {
        interval: 1200; running: true
        onTriggered: root.grabToImage(result => result.saveToFile("SNAPSHOT"))
    }
}'''.replace('SNAPSHOT', str(TEMP / 'widget.png'))
    main.write_text(source)
    stdout = TEMP / 'widget.log'
    with stdout.open('w') as output:
        proc = subprocess.Popen(['plasmawindowed', 'org.monet.sound'], stdout=output, stderr=output)
        try:
            def shown(volume, muted):
                text = stdout.read_text()
                needle = json.dumps({'volume': volume, 'muted': muted, 'silent': False,
                                     'playing': 'First', 'native': True}, separators=(',', ':'))
                return needle in text
            wait_for(lambda: shown(45, False), 'native Sound widget initial level', timeout=10000)
            pactl('set-sink-volume', 'monet_one', '27%'); pactl('set-sink-mute', 'monet_one', '1')
            wait_for(lambda: shown(27, True), 'native Sound widget volume/mute updates')
            wait_for(lambda: (TEMP / 'widget.png').exists(), 'Sound widget rendering')
            assert QImage(str(TEMP / 'widget.png')).width() >= 300, 'Sound controls clipped in a narrow host'
            text = stdout.read_text()
            assert not any(word in text for word in ['ReferenceError', 'TypeError', 'Binding loop', 'is not a type']), text
            evidence = os.environ.get('MONET_AUDIO_EVIDENCE')
            if evidence:
                dest = Path(evidence); dest.mkdir(parents=True, exist_ok=True)
                for name in ['widget.png', 'widget.log']: shutil.copy2(TEMP / name, dest / name)
            print(json.dumps({'full_widget_native_events_and_rendering': 'passed'}))
        except Exception:
            print(stdout.read_text(), file=sys.stderr)
            raise
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


def notifications():
    import pulsectl

    start_server()
    with subprocess.Popen(['wireplumber', '--profile=policy'], stdout=log, stderr=log) as policy:
        try:
            def restore_ready():
                metadata = subprocess.check_output(['pw-metadata', '-l'], text=True, timeout=5)
                return 'Found "route-settings" metadata' in metadata

            wait_for(restore_ready, 'stream-restore policy')
            pactl('load-module', 'module-stream-restore')
            check_notification_volume(pulsectl)
        finally:
            policy.terminate()


def check_notification_volume(pulsectl):
    quick = str(ROOT / 'linux/libexec/monet-quick')
    event = 'sink-input-by-media-role:event'
    stereo = ['front-left', 'front-right']

    def level(*args):
        result = subprocess.check_output([sys.executable, quick, 'notification-audio', *args], timeout=5)
        return json.loads(result)

    with pulsectl.Pulse('Monet notification test') as pulse:
        def saved():
            return next((entry for entry in pulse.stream_restore_read() if entry.name == event), None)

        initial = level('defaults')
        assert initial == {'ok': True, 'volume': 35}, (initial, pulse.stream_restore_read())
        assert saved().channel_list == stereo
        pulse.stream_restore_write(event, channel_list=['mono'], volume=0.41, mute=True)
        wait_for(lambda: saved().channel_list == ['mono'], 'old mono notification entry')
        assert level() == {'ok': True, 'volume': 0}
        assert saved().channel_list == stereo and saved().mute
        assert all(abs(value - 0.41) < 0.001 for value in saved().volume.values)

        assert level('62') == {'ok': True, 'volume': 62}
        assert level('defaults') == {'ok': True}
        assert level() == {'ok': True, 'volume': 62}
        assert saved().channel_list == stereo and not saved().mute
        clip = ROOT / 'linux/share/sounds/monet/stereo/message-new-instant.oga'
        with subprocess.Popen(['paplay', '--property=media.role=event', str(clip)]) as player:
            def playing():
                return next((stream for stream in pulse.sink_input_list()
                             if stream.proplist.get('application.process.id') == str(player.pid)), None)

            try:
                wait_for(playing, 'stereo notification playback')
                # The stream-created event precedes WirePlumber's restore policy.
                # Check the observed volume after that policy has had its turn.
                def restored():
                    stream = playing()
                    return stream and all(abs(value - 0.62) < 0.001 for value in stream.volume.values)
                wait_for(restored, 'notification stream volume restored')
                stream = playing()
                assert stream.channel_list == stereo and not stream.mute, stream
                assert all(abs(value - 0.62) < 0.001 for value in stream.volume.values), stream
            finally:
                player.terminate()
        print('Notification volume defaults, mono migration, and stereo playback passed')


def dock_volume_memory():
    """The Home Bar's levels against made-up streams, with no sound server."""
    source = Path(os.environ['MONET_DOCK_AUDIO_QML'])
    # The actual patched stream delegate, in made-up surroundings.
    pulse = (source / 'PulseAudio.qml').read_text()
    delegate = pulse.split('        component StreamDelegate: QtObject {', 1)[1].split('\n        delegate: StreamDelegate', 1)[0]
    # And the patched parts of the dock that tell an app's streams apart by window.
    by_window_fn = '    function monetByWindow(' + pulse.split('    function monetByWindow(', 1)[1].split('    signal streamsChanged()', 1)[0]
    group = (source / 'ToolTipDelegate.qml').read_text()
    group = '                readonly property var monetWindowStreams: {' + group.split('                readonly property var monetWindowStreams: {', 1)[1].split('                // Required to know', 1)[0]
    instance = (source / 'ToolTipInstance.qml').read_text()
    instance = '    property var monetWindowStreams: null' + instance.split('    property var monetWindowStreams: null', 1)[1].split('    property bool hasTrackInATitle', 1)[0]
    # PulseAudio discovers Client metadata asynchronously. Exercise the actual
    # patched delegate with a client arriving after Component.onCompleted.
    delayed = TEMP / 'LateClient.qml'
    delayed.write_text('''import QtQuick
import "''' + source.as_uri() + '''" as Dock
QtObject {
    id: pulseAudio
    property int normalVolume: 65536
    property bool ready: false
    property Dock.MonetAppVolume monetVolume: Dock.MonetAppVolume {}
    property var fake: ({Client: ready ? {properties:{"application.id":"org.monet.delayed-browser","application.name":"Browser"}} : null,
                        Muted:false, Corked:false, Volume:65536})
    property StreamDelegate stream: StreamDelegate { model: pulseAudio.fake }
    component StreamDelegate: QtObject {''' + delegate + '''
    Component.onCompleted: monetVolume.settings.levels = '{"id:org.monet.delayed-browser":0.83}'
    function actual() { return fake.Volume }
}''')
    # PipeWire applies a player's own starting volume (paplay --volume, a
    # browser's level) only once its stream is set up, which can be just after
    # the Home Bar restored the app's level. Like the sound server, this stream
    # reports whatever was written to it last.
    late = TEMP / 'LatePlayer.qml'
    late.write_text('''import QtQuick
import "''' + source.as_uri() + '''" as Dock
QtObject {
    id: pulseAudio
    property int normalVolume: 65536
    property Dock.MonetAppVolume monetVolume: Dock.MonetAppVolume {}
    property int level: 65536
    readonly property var fake: ({Client: {properties: {"application.id": "org.monet.late-player"}}, Muted: false, Corked: false,
                                  get Volume() { return pulseAudio.level }, set Volume(value) { pulseAudio.level = value }})
    property StreamDelegate stream: StreamDelegate { model: pulseAudio.fake }
    function findStreamsFn(fn) { return [stream].filter(fn) }
    component StreamDelegate: QtObject {''' + delegate + '''
    Component.onCompleted: monetVolume.settings.levels = '{"id:org.monet.late-player":0.83}'
    function saved() { return monetVolume.levels()["id:org.monet.late-player"] }
}''')
    # Streams that come and go, the dock's windows, and the levels kept.
    # Each stream reports whatever was written to it last, like the sound server.
    streams = TEMP / 'Streams.qml'
    streams.write_text('''import QtQuick
import "''' + source.as_uri() + '''" as Dock
QtObject {
    id: pulseAudio
    property int normalVolume: 65536
    property var openWindows: []
    property var parents: ({})
    property Dock.MonetAppVolume monetVolume: Dock.MonetAppVolume {
        windows: () => pulseAudio.openWindows
        parentOf: pid => pulseAudio.parents[pid] ?? -1
    }
    property var streams: []
    property var fakes: []
    component Fake: QtObject {
        property var client
        property int volume: 65536
        property bool muted: false
        property bool corked: false
        property string name: ""
    }
    property Component fakeType: Component { Fake {} }
    // A model passed to createObject() would lose its getters and setters on the way.
    property var models: []
    property Component streamType: Component { StreamDelegate { property int slot; model: pulseAudio.models[slot] } }
    function findStreamsFn(fn) { return streams.filter(fn) }
    // A new stream: the client's properties (JSON), the player's name for it and its level.
    function add(props, name, volume) {
        const fake = fakeType.createObject(pulseAudio, {client: {properties: JSON.parse(props)}, name: name, volume: volume});
        const model = {get Client() { return fake.client }, get Name() { return fake.name }, get Corked() { return fake.corked },
                       get Volume() { return fake.volume }, set Volume(value) { fake.volume = value },
                       get Muted() { return fake.muted }, set Muted(value) { fake.muted = value }};
        fakes = fakes.concat([fake]);
        models = models.concat([model]);
        streams = streams.concat([streamType.createObject(pulseAudio, {slot: models.length - 1})]);
        return streams.length - 1;
    }
    function level(index) { return fakes[index].volume }
    function isMuted(index) { return fakes[index].muted }
    // The player, or another mixer, sets a stream's level.
    function setLevel(index, value) { fakes[index].volume = value }
    function setName(index, name) { fakes[index].name = name }
    function setCorked(index, corked) { fakes[index].corked = corked }
    function trackChanged(index) { streams[index].monetTrackChanged() }
    // As if this long had passed since the stream's last restore and track change.
    function rewind(index, ms) { streams[index].monetRestoredAt -= ms; streams[index].monetTrackAt -= ms }
    function setSaved(levels) { monetVolume.settings.levels = levels }
    function saved(app) { const value = monetVolume.levels()["id:" + app]; return Number.isFinite(value) ? value : -1 }
    function setWindows(windows) { openWindows = JSON.parse(windows) }
    function windowLevel(id) { return monetVolume.windowLevels[id]?.level ?? -1 }
    function rememberWindow(id, index, value) { monetVolume.rememberWindow(id, streams[index], value) }
    function remember(index, value) { monetVolume.remember(streams[index], value) }
    // Which tooltip window each stream plays for ({id: [stream indexes]}), or null.
    function byWindow(indexes, ids) {
        const found = monetVolume.byWindow(JSON.parse(indexes).map(index => streams[index]), JSON.parse(ids));
        if (!found) return "null";
        const result = {};
        for (const id in found) result[id] = found[id].map(stream => streams.indexOf(stream));
        return JSON.stringify(result);
    }
''' + by_window_fn + '''
    component StreamDelegate: QtObject {''' + delegate + '''
}''')
    # A group tooltip: its list of windows and one window's volume controls.
    tooltip = TEMP / 'Tooltip.qml'
    tooltip.write_text('''import QtQuick
QtObject {
    id: harness
    property QtObject audio
    property var ids: []
    property var titles: ({})
    property QtObject pulseAudio: QtObject { property QtObject item: harness.audio }
    property QtObject toolTipDelegate: QtObject {
        property QtObject parentTask: QtObject {
            property var audioStreams: []
            readonly property bool muted: audioStreams.length > 0 && audioStreams.every(stream => stream.muted)
            readonly property string appName: "Player"
            readonly property bool tooltipControlsEnabled: true
            property int toggled: 0
            function toggleMuted() { toggled++ }
        }
    }
    function use(indexes) { toolTipDelegate.parentTask.audioStreams = JSON.parse(indexes).map(index => audio.streams[index]) }
    property QtObject list: QtObject {
        property var model: ({items: {count: harness.ids.length,
                                      get: i => ({model: {display: harness.titles[harness.ids[i]] ?? "", WinIdList: [harness.ids[i]]}})}})
''' + group + '''    }
    property QtObject window: QtObject {
        id: root
        property string title: "First song"
        property QtObject thumbnail: QtObject { id: thumbnailSourceItem; property var winId: "w1" }
''' + instance.replace('property var monetWindowStreams: null', 'property var monetWindowStreams: harness.list.monetWindowStreams') + '''    }
    function look(id) { thumbnailSourceItem.winId = id }
    function shown() { return JSON.stringify(window.monetStreams?.map(stream => audio.streams.indexOf(stream)) ?? null) }
    function controlled() { return JSON.stringify(window.monetAudioStreams.map(stream => audio.streams.indexOf(stream))) }
    function name() { return window.monetName }
    function muted() { return window.monetMuted }
    function toggle() { window.monetToggleMuted() }
    function toggled() { return toolTipDelegate.parentTask.toggled }
    function slide(index, value) { window.monetRemember(audio.streams[index], value) }
}''')

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(delayed)))
    delayed_client = component.create()
    assert delayed_client is not None, [e.toString() for e in component.errors()]
    QTest.qWait(100)
    assert delayed_client.actual() == 65536
    delayed_client.setProperty('ready', True)
    wait_for(lambda: delayed_client.actual() == round(.83 * 65536), 'late app identity restores saved volume')
    delayed_client.deleteLater(); QTest.qWait(50)

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(late)))
    late_player = component.create()
    assert late_player is not None, [e.toString() for e in component.errors()]
    wait_for(lambda: late_player.property('level') == round(.83 * 65536), 'saved volume restored')
    late_player.setProperty('level', 65536)
    wait_for(lambda: late_player.property('level') == round(.83 * 65536), "the player's late starting volume was put back")
    # After the start, another mixer's change is the app's new level.
    QTest.qWait(1100)
    late_player.setProperty('level', round(.55 * 65536))
    wait_for(lambda: abs(late_player.saved() - .55) < .002, "another mixer's later change was kept")
    assert late_player.property('level') == round(.55 * 65536), "another mixer's later change was undone"
    late_player.deleteLater(); QTest.qWait(50)

    made_ups = []
    def made_up():
        # Each check on its own: the previous one goes first.
        for _, old in made_ups: old.deleteLater()
        made_ups.clear(); QTest.qWait(50)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(streams)))
        made = component.create()
        assert made is not None, [e.toString() for e in component.errors()]
        made_ups.append((component, made))
        return made

    full = 65536
    def at(value): return round(value * full)
    def by_window(made, indexes, ids):
        return json.loads(made.byWindow(json.dumps(indexes), json.dumps(ids)))

    # Spotify keeps one stream for every track and puts its own level back on
    # it when the next one starts. That isn't another mixer: the Home Bar puts
    # the level it keeps back.
    made = made_up()
    made.setSaved('{"id:org.monet.track-player":0.5}')
    flatpak = json.dumps({'pipewire.access.portal.app_id': 'org.monet.track-player', 'application.process.id': '2'})
    song = int(made.add(flatpak, 'Spotify', full))
    wait_for(lambda: made.level(song) == at(.5), "the app's level on a new stream")
    made.rewind(song, 1500)
    made.trackChanged(song)
    made.setLevel(song, full)
    wait_for(lambda: made.level(song) == at(.5), "the player's own level after a new track was put back")
    assert made.saved('org.monet.track-player') == .5, made.saved('org.monet.track-player')
    # The player can also say only afterwards that the track changed.
    made.rewind(song, 5000)
    made.setLevel(song, full)
    QTest.qWait(200)
    made.trackChanged(song)
    wait_for(lambda: made.level(song) == at(.5), 'the level put back when the new track is announced after it')
    assert made.saved('org.monet.track-player') == .5, made.saved('org.monet.track-player')
    # Another mixer, later: that level is kept, and the next track puts it back.
    made.rewind(song, 5000)
    made.setLevel(song, at(.55))
    wait_for(lambda: abs(made.saved('org.monet.track-player') - .55) < .002, "another mixer's level was kept")
    assert made.level(song) == at(.55), "another mixer's level was undone"
    made.trackChanged(song)
    made.setLevel(song, full)
    wait_for(lambda: made.level(song) == at(.55), "the next track put back another mixer's level")
    # Right after a new track, a level the stream never had (the player's own
    # slider) is a change like any other.
    QTest.qWait(100)
    made.setLevel(song, at(.7))
    wait_for(lambda: abs(made.saved('org.monet.track-player') - .7) < .002, "the player's slider after a new track was kept")
    QTest.qWait(300)
    assert made.level(song) == at(.7), "the player's slider after a new track was undone"
    # Playing again after a pause counts as a new start.
    made.rewind(song, 5000)
    made.setCorked(song, True); QTest.qWait(50)
    made.setCorked(song, False); QTest.qWait(50)
    made.setLevel(song, full)
    wait_for(lambda: made.level(song) == at(.7), 'the level put back after a pause')
    assert abs(made.saved('org.monet.track-player') - .7) < .002, made.saved('org.monet.track-player')

    # Two windows of a player, each its own process: each window keeps its own level.
    made = made_up()
    made.setSaved('{"id:org.monet.window-player":0.8}')
    made.setWindows(json.dumps([{'id': 'w1', 'pid': 101, 'appId': 'org.monet.window-player', 'title': 'First song — Player'},
                                {'id': 'w2', 'pid': 102, 'appId': 'org.monet.window-player', 'title': 'Second song — Player'}]))
    def player(pid): return json.dumps({'application.id': 'org.monet.window-player', 'application.process.id': str(pid)})
    first = int(made.add(player(101), 'Playback', full))
    second = int(made.add(player(102), 'Playback', full))
    wait_for(lambda: made.level(first) == at(.8) and made.level(second) == at(.8), "the app's level on both windows")
    assert by_window(made, [first, second], ['w1', 'w2']) == {'w1': [first], 'w2': [second]}
    # The first window's own slider, as the tooltip moves it.
    made.rememberWindow('w1', first, at(.3))
    made.setLevel(first, at(.3))
    QTest.qWait(1700)
    assert made.level(first) == at(.3) and made.level(second) == at(.8), (made.level(first), made.level(second))
    assert made.saved('org.monet.window-player') == .8, 'a window slider changed the app level'
    # The next track in each window keeps that window's level.
    first = int(made.add(player(101), 'Playback', full))
    second = int(made.add(player(102), 'Playback', full))
    wait_for(lambda: made.level(first) == at(.3) and made.level(second) == at(.8), "each window's next track kept its level")
    # Another mixer moves the first window's sound: the window's level follows, the app's doesn't.
    made.rewind(first, 5000)
    made.setLevel(first, at(.4))
    wait_for(lambda: abs(made.windowLevel('w1') - .4) < .002, "the window kept another mixer's level")
    assert made.saved('org.monet.window-player') == .8, made.saved('org.monet.window-player')
    # The app's slider makes the level the app's again.
    made.rememberWindow('w2', second, at(.2))
    made.remember(second, at(.6))
    assert made.windowLevel('w1') == -1 and made.windowLevel('w2') == -1, 'the app slider kept window levels'
    assert abs(made.saved('org.monet.window-player') - .6) < .002
    # A closed window's level goes with it.
    made.rememberWindow('w1', first, at(.25))
    made.setWindows(json.dumps([{'id': 'w2', 'pid': 102, 'appId': 'org.monet.window-player', 'title': 'Second song — Player'}]))
    again = int(made.add(player(101), 'Playback', full))
    wait_for(lambda: made.level(again) == at(.6), "a closed window's next stream got the app's level")
    assert made.windowLevel('w1') == -1, 'a closed window kept its level'

    # A browser plays every tab from one process. Firefox names a tab's stream
    # after the page, which is also its window's title while the tab shows.
    made = made_up()
    made.setSaved('{"id:org.monet.browser":0.7}')
    tabs = [{'id': 'b1', 'pid': 300, 'appId': 'org.monet.browser', 'title': 'Cats - YouTube — Zen Browser'},
            {'id': 'b2', 'pid': 300, 'appId': 'org.monet.browser', 'title': 'GitHub — Zen Browser'}]
    made.setWindows(json.dumps(tabs))
    browser = json.dumps({'application.id': 'org.monet.browser', 'application.process.id': '300'})
    cats = int(made.add(browser, 'Cats - YouTube', full))
    hub = int(made.add(browser, 'GitHub', full))
    wait_for(lambda: made.level(cats) == at(.7) and made.level(hub) == at(.7), "the browser's level")
    assert by_window(made, [cats, hub], ['b1', 'b2']) == {'b1': [cats], 'b2': [hub]}
    # A tab no window shows, or a private window's unnamed stream: one slider.
    hidden = int(made.add(browser, 'Dogs - YouTube', full))
    assert by_window(made, [cats, hub, hidden], ['b1', 'b2']) is None
    private = int(made.add(browser, 'AudioStream', full))
    assert by_window(made, [cats, private], ['b1', 'b2']) is None
    # A page whose title only begins the same is another page.
    short = int(made.add(browser, 'Cats', full))
    assert by_window(made, [short, hub], ['b1', 'b2']) is None
    # A window's own level follows its next video, named once the page is known.
    made.rememberWindow('b1', cats, at(.25))
    made.setLevel(cats, at(.25))
    tabs[0]['title'] = 'Kittens - YouTube — Zen Browser'
    made.setWindows(json.dumps(tabs))
    kittens = int(made.add(browser, 'AudioStream', full))
    wait_for(lambda: made.level(kittens) == at(.7), 'a nameless stream got the app level')
    made.setName(kittens, 'Kittens - YouTube')
    wait_for(lambda: made.level(kittens) == at(.25), "the window's next video kept the window's level")
    assert made.level(hub) == at(.7) and made.saved('org.monet.browser') == .7
    # In Flatpak the browser's process id is the sandbox's own: windows and
    # streams meet by app id, and the page tells them apart.
    sandbox = json.dumps({'pipewire.access.portal.app_id': 'org.monet.browser', 'application.process.id': '2'})
    boxed = int(made.add(sandbox, 'GitHub', full))
    assert by_window(made, [kittens, boxed], ['b1', 'b2']) == {'b1': [kittens], 'b2': [boxed]}
    # Chromium plays every tab from a child process with the same name: one slider.
    made.setProperty('parents', {'401': 400})
    chromium = [{'id': 'c1', 'pid': 400, 'appId': 'org.monet.chromium', 'title': 'Cats - YouTube - Chromium'},
                {'id': 'c2', 'pid': 400, 'appId': 'org.monet.chromium', 'title': 'GitHub - Chromium'}]
    made.setWindows(json.dumps(tabs + chromium))
    tab = json.dumps({'application.id': 'org.monet.chromium', 'application.process.id': '401'})
    playing = [int(made.add(tab, 'Playback', full)), int(made.add(tab, 'Playback', full))]
    assert by_window(made, playing, ['c1', 'c2']) is None
    # A child process of one window's own process plays for that window.
    made.setWindows(json.dumps(tabs + chromium[:1] + [{'id': 'c3', 'pid': 402, 'appId': 'org.monet.chromium', 'title': 'Other'}]))
    assert by_window(made, playing, ['c1', 'c3']) == {'c1': playing}

    # The tooltip itself: a slider under each window that plays, for that window only.
    made = made_up()
    made.setSaved('{"id:org.monet.window-player":0.8}')
    made.setWindows(json.dumps([{'id': 'w1', 'pid': 101, 'appId': 'org.monet.window-player', 'title': 'First song — Player'},
                                {'id': 'w2', 'pid': 102, 'appId': 'org.monet.window-player', 'title': 'Second song — Player'}]))
    first = int(made.add(player(101), 'Playback', full))
    second = int(made.add(player(102), 'Playback', full))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(tooltip)))
    tip = component.createWithInitialProperties({'audio': made})
    assert tip is not None, [e.toString() for e in component.errors()]
    made_ups.append((component, tip))
    tip.setProperty('ids', ['w1', 'w2'])
    # Plasma finds a group's streams by its first window's process only.
    tip.use(json.dumps([first]))
    assert json.loads(tip.shown()) == [first] and json.loads(tip.controlled()) == [first], (tip.shown(), tip.controlled())
    tip.look('w2')
    assert json.loads(tip.shown()) == [second], ('the second window plays from its own process', tip.shown())
    tip.look('w1')
    assert tip.name() == 'First song' and not tip.muted()
    tip.toggle()
    assert tip.muted() and made.isMuted(first) and not made.isMuted(second) and tip.toggled() == 0
    tip.toggle()
    assert not tip.muted() and not made.isMuted(first)
    tip.slide(first, at(.3))
    assert abs(made.windowLevel('w1') - .3) < .002 and made.windowLevel('w2') == -1
    assert made.saved('org.monet.window-player') == .8, 'a window slider changed the app level'
    # Sound nobody can place: the app's one slider, as before.
    tip.use(json.dumps([first, int(made.add(json.dumps({'application.id': 'org.monet.window-player'}), 'Playback', full))]))
    assert json.loads(tip.shown()) is None and len(json.loads(tip.controlled())) == 2
    assert tip.name() == 'Player'
    tip.toggle()
    assert tip.toggled() == 1, 'the app slider no longer mutes the app'
    tip.slide(first, at(.45))
    assert abs(made.saved('org.monet.window-player') - .45) < .002 and made.windowLevel('w1') == -1
    for _, made in made_ups: made.deleteLater()
    QTest.qWait(50)
    print('Dock volume memory: late identity, late start, new tracks, windows, tabs and other mixers passed')


def dock_volume():
    import pulsectl
    import wave

    start_server()
    clip = TEMP / 'track.wav'
    with wave.open(str(clip), 'wb') as sound:
        sound.setnchannels(2); sound.setsampwidth(2); sound.setframerate(8000)
        sound.writeframes(b'\0' * 4 * 8000 * 30)
    source = Path(os.environ['MONET_DOCK_AUDIO_QML'])
    harness = TEMP / 'DockAudio.qml'
    harness.write_text('''import QtQuick
import "''' + source.as_uri() + '''" as Dock
QtObject {
    property int requested: -1
    property string appName: "Monet Browser"
    readonly property Dock.PulseAudio audio: Dock.PulseAudio {}
    function hasStream(pid) { return audio.streamsForAppName(appName).some(stream => stream.pid === pid) }
    // The player says it started another track (the dock hears it over MPRIS).
    function trackChanged(pid) { audio.streamsForAppName(appName).filter(stream => stream.pid === pid).forEach(stream => stream.monetTrackChanged()) }
    // What the Home Bar keeps for the test player, from 0 to 1 (-1: nothing).
    function savedLevel() {
        const level = audio.monetVolume.levels()["id:org.monet.test-browser"];
        return Number.isFinite(level) ? level : -1;
    }
    onRequestedChanged: {
        const streams = audio.streamsForAppName(appName);
        if (!streams.length) throw new Error("No playback stream");
        streams.forEach(stream => {
            audio.monetVolume.remember(stream, requested / 100 * audio.normalVolume);
            stream.model.Volume = Math.round(requested / 100 * audio.normalVolume);
            stream.model.Muted = requested === 0;
        });
    }
}''')

    def controller():
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(harness)))
        obj = component.create()
        assert obj is not None, [e.toString() for e in component.errors()]
        objects.append((component, obj))
        return obj

    def play(name='Monet Browser', identity='org.monet.test-browser'):
        return subprocess.Popen(['paplay', '--client-name=' + name, '--volume=65536',
                                 '--property=application.id=' + identity, str(clip)],
                                stdout=log, stderr=log)

    with subprocess.Popen(['wireplumber', '--profile=policy'], stdout=log, stderr=log) as policy, \
            pulsectl.Pulse('Monet dock test') as pulse:
        players = []
        try:
            def stream(player):
                return next((item for item in pulse.sink_input_list()
                             if item.proplist.get('application.process.id') == str(player.pid)), None)
            def at(player, value):
                item = stream(player)
                return item and all(abs(v - value / 100) < .002 for v in item.volume.values)
            obj = controller()
            first = play(); players.append(first)
            wait_for(lambda: at(first, 100), 'first track initial volume')
            wait_for(lambda: obj.hasStream(first.pid), 'first track appears in Home Bar')
            obj.setProperty('requested', 83)
            wait_for(lambda: at(first, 83), 'Home Bar changed active track')
            first.terminate(); first.wait(timeout=5)
            wait_for(lambda: stream(first) is None, 'first track removed')
            second = play(); players.append(second)
            wait_for(lambda: at(second, 83), 'next track retained app volume')
            QTest.qWait(300)
            assert at(second, 83), 'player initial volume overwrote the saved choice'
            other = play('Monet Other Player', 'org.monet.other-player'); players.append(other)
            wait_for(lambda: at(other, 100), 'unrelated app kept its volume')
            obj.setProperty('requested', 0)
            wait_for(lambda: at(second, 0) and stream(second).mute, 'zero app volume')
            second.terminate(); second.wait(timeout=5)
            # Closing the controller flushes QSettings, as closing Plasma does.
            previous = objects.pop()
            obj.deleteLater(); QTest.qWait(100)
            del previous
            obj = controller()
            third = play(); players.append(third)
            wait_for(lambda: obj.hasStream(third.pid), 'restarted track appears in Home Bar')
            try:
                # A muted stream is effectively zero. WirePlumber can retain a
                # nonzero underlying gain for unmute without producing sound.
                wait_for(lambda: stream(third) and stream(third).mute, 'saved zero after controller restart')
            except AssertionError:
                print((Path(os.environ['XDG_CONFIG_HOME']) / 'monet/app-volume.ini').read_text())
                print(stream(third))
                raise
            obj.setProperty('requested', 42)
            wait_for(lambda: at(third, 42) and not stream(third).mute, 'adjust and unmute saved volume')
            # A change from another mixer sticks, and the next track keeps it.
            QTest.qWait(1100)
            pulse.volume_set_all_chans(stream(third), 0.55)
            wait_for(lambda: at(third, 55), 'another mixer changed the track')
            # The Home Bar keeps it once it has seen the change, which it hears after the server
            # (and WirePlumber restores the next track too, so only this shows Monet's part).
            wait_for(lambda: abs(obj.savedLevel() - 0.55) < 0.002, "the Home Bar kept the other mixer's level")
            QTest.qWait(300)
            assert at(third, 55), 'the Home Bar put its old level back'
            third.terminate(); third.wait(timeout=5)
            wait_for(lambda: stream(third) is None, 'third track removed')
            fourth = play(); players.append(fourth)
            try:
                wait_for(lambda: at(fourth, 55), "next track kept the other mixer's level")
            except AssertionError:
                print('saved', obj.savedLevel(), 'fourth', stream(fourth))
                raise
            # Like Spotify, the player keeps its stream for the next track and
            # puts its own level back on it: the Home Bar puts its level back.
            QTest.qWait(1100)
            obj.trackChanged(fourth.pid)
            pulse.volume_set_all_chans(stream(fourth), 1.0)
            QTest.qWait(300)
            try:
                wait_for(lambda: at(fourth, 55), "the player's own level on its next track was put back")
            except AssertionError:
                print('saved', obj.savedLevel(), 'fourth', stream(fourth))
                raise
            QTest.qWait(1700)
            assert at(fourth, 55) and abs(obj.savedLevel() - 0.55) < 0.002, (obj.savedLevel(), stream(fourth))
            assert at(other, 100), 'another app was changed'
            print('Dock volume: next track, separate app, persistence, zero, unmute, other mixers and a kept stream passed')
        finally:
            for player in players:
                if player.poll() is None: player.terminate()
                player.wait(timeout=5)
            policy.terminate()


def output_priority():
    start_server()
    quick = str(ROOT / "linux/libexec/monet-quick")
    sys.path.insert(0, str(ROOT / "linux/share/monet"))
    from monet_runtime import output_order
    from contextlib import ExitStack
    with ExitStack() as stack:
        def launch(args):
            proc = subprocess.Popen(args, stdout=log, stderr=log)
            stack.callback(lambda: (proc.terminate(), proc.wait(5)))
            return proc
        launch(["wireplumber", "--profile=policy"])
        wait_for(lambda: "route-settings" in subprocess.check_output(["pw-metadata", "-l"], text=True), "policy")
        def listed():
            return json.loads(subprocess.check_output([quick, "output-order", "get"], text=True))["connected"]
        wait_for(lambda: len(listed()) == 2, "two available outputs")
        by_name = {bytes.fromhex(d["key"]).decode(): d for d in listed()}
        third = dict(key="monet_three".encode().hex(), name="Third", port="")
        path = output_order.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        output_order.write(path, dict(enabled=True, devices=[third, by_name["monet_two"], by_name["monet_one"]]))
        pactl("set-default-sink", "monet_one")
        launch([quick, "output-order", "watch"])
        def expect(name):
            wait_for(lambda: pactl("get-default-sink") == name, "preferred " + name)
        expect("monet_two")
        def plug():
            return pactl("load-module", "module-null-sink", "sink_name=monet_three", "sink_properties=device.description=Third")
        plugged = plug()
        expect("monet_three")
        pactl("set-default-sink", "monet_one")
        pactl("set-sink-volume", "monet_two", "37%")
        QTest.qWait(400)
        assert pactl("get-default-sink") == "monet_one", "manual choice reverted"
        pactl("unload-module", plugged)
        expect("monet_two")
        # Pulse may reuse module IDs. Occupy a slot to exercise renumbering as well.
        pactl("load-module", "module-null-sink", "sink_name=unranked")
        reconnected = plug()
        expect("monet_three")
        pactl("unload-module", reconnected)
        expect("monet_two")


def headphone_volume():
    """Exercise native device removal, delayed defaults and user volume changes."""
    from contextlib import ExitStack
    import pulsectl
    sys.path.insert(0, str(ROOT / "linux/share/monet"))
    from monet_runtime import output_order
    start_server()
    for module_id in module_ids.values():
        pactl("unload-module", module_id)
    quick = str(ROOT / "linux/libexec/monet-quick")
    with ExitStack() as stack:
        def launch(args):
            proc = subprocess.Popen(args, stdout=log, stderr=log)
            stack.callback(lambda: (proc.terminate(), proc.wait(timeout=5)))
        launch(["wireplumber", "--profile=policy"])
        wait_for(lambda: "route-settings" in subprocess.check_output(["pw-metadata", "-l"], text=True), "policy")
        def plug(name, kind):
            return pactl("load-module", "module-null-sink", "sink_name=" + name,
                         "sink_properties=device.form_factor=" + kind)
        def expect(name):
            wait_for(lambda: pactl("get-default-sink") == name, "default " + name)
        plug("desk", "speaker")
        headset = plug("phones", "headphone")
        monitor = stack.enter_context(pulsectl.Pulse("speaker limit test"))
        def speaker():
            return next(s for s in monitor.sink_list() if s.name == "desk")
        def levels():
            return [round(v * 100) for v in speaker().volume.values]
        path = output_order.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        output_order.write(path, dict(enabled=False, devices=[], headphoneLimitEnabled=True, headphoneLimit=20))
        pactl("set-default-sink", "desk")
        pactl("set-sink-volume", "desk", "76%", "38%")
        pactl("set-sink-mute", "desk", "1")
        launch([quick, "output-order", "watch"])
        wait_for(lambda: any(c.proplist.get("application.name") == "Monet output preferences"
                             for c in monitor.client_list()), "volume listener")
        QTest.qWait(260)
        assert levels() == [76, 38]
        def select(name):
            pactl("set-default-sink", name)
            expect(name)
            QTest.qWait(300)  # Let independent server and card changes settle.
        select("phones")
        select("desk")
        assert levels() == [76, 38], "manual output change lowered the speakers"
        for override in (False, True):
            select("phones")
            pactl("unload-module", headset)
            expect("desk")
            wait_for(lambda: levels() == [20, 10], "speaker limit with stereo balance")
            assert speaker().mute, "disconnect unmuted the speaker"
            if override:
                pactl("set-sink-volume", "desk", "45%", "25%")
            headset = plug("phones", "headphone")
            select("phones")
            desired = [45, 25] if override else [76, 38]
            wait_for(lambda: levels() == desired, "restore or keep the user's volume")
            assert speaker().mute, "reconnect unmuted the speaker"


def app_mixer():
    """Group separate live streams, move them together, and remember pins after they go away."""
    from contextlib import ExitStack
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtQuick import QQuickWindow  # Register the QML window type with PySide.
    start_server()
    loader = SourceFileLoader("mixer_words", str(ROOT / "linux/libexec/monet-games"))
    module = module_from_spec(spec_from_loader(loader.name,loader))
    loader.exec_module(module)
    words = module.Words()
    engine.rootContext().setContextObject(words)
    ui = Path(os.environ.get("MONET_MIXER_UI") or ROOT / "linux/share/monet/settings-app")
    qml = TEMP / "MixerCheck.qml"
    qml.write_text('import QtQuick\nimport QtQuick.Controls as C\nimport QtQuick.Templates as T\nimport "' + ui.as_uri() + '''" as Monet
C.ApplicationWindow {
    id: window
    visible: true; width: 400; height: 340
    Monet.VolumeMixer {
        anchors.fill: parent
        outputNames: [{ key: "6d6f6e65745f74776f", name: "Desk speakers" }]
    }
    function locate(text, label) {
        function find(item) {
            if (!item || !item.visible || !item.enabled) return null
            if (item instanceof T.Slider && item.Accessible.name === text) {
                const handle = item.handle.width
                const x = item.leftPadding + handle / 2 + (item.availableWidth - handle) * 0.37
                const p = item.mapToItem(window.contentItem, x, item.height / 2)
                return [Math.round(p.x), Math.round(p.y)]
            }
            if ((label ? item instanceof T.Label : item instanceof T.AbstractButton) && item.text === text) {
                const p = item.mapToItem(window.contentItem, item.width / 2, item.height / 2)
                return [Math.round(p.x), Math.round(p.y)]
            }
            for (const child of item.children) {
                const point = find(child)
                if (point) return point
            }
            return null
        }
        return find(window.C.Overlay.overlay) || find(window.contentItem)
    }
}''')
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml)))
    assert component.isReady(), [e.toString() for e in component.errors()]
    win = component.create()
    assert isinstance(win, QQuickWindow), warnings
    model = win.findChild(QObject, "appMixerModel")
    helper_path = "/usr/libexec/monet-quick" if os.environ.get("MONET_MIXER_UI") else str(ROOT / "linux/libexec/monet-quick")
    model.setProperty("helper", helper_path)
    def js(code):
        from PySide6.QtQml import QQmlExpression, qmlContext
        expr = QQmlExpression(qmlContext(model), model, code)
        val, _ = expr.evaluate()
        assert not expr.hasError(), expr.error().toString()
        return val.toVariant() if hasattr(val, "toVariant") else val

    def point(text, label=False):
        result = win.locate(text, label)
        return result.toVariant() if hasattr(result, "toVariant") else result

    def choose(text):
        wait_for(lambda: point(text), text)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(*point(text)))
        QTest.qWait(80)

    def state():
        return js("Array.from({length:rows.count},(_,i)=>[rows.get(i).appKey,rows.get(i).pinned,matching(rows.get(i).appKey).length])")

    def inputs(name):
        return [s for s in json.loads(pactl("-f", "json", "list", "sink-inputs"))
                if s["properties"].get("application.id") == name]

    def play(name, label, event=False):
        args = ["pacat", "--playback", "--raw", "--channels=1", "--rate=8000", "--client-name", label,
                "--stream-name", "Playback", "--property=application.id="+name, "--device=monet_one"]
        if event:
            args.append("--property=media.role=event")
        proc = subprocess.Popen([*args, "/dev/zero"], stdout=log, stderr=log)
        stack.callback(stop, proc)
        return proc

    def stop(proc):
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)

    with ExitStack() as stack:
        policy = subprocess.Popen(["wireplumber", "--profile=policy"], stdout=log, stderr=log)
        stack.callback(stop, policy)
        wait_for(lambda: "route-settings" in subprocess.check_output(["pw-metadata", "-l"], text=True), "audio graph")
        first = play("test.music", "Music")
        second = play("test.music", "Music")
        play("test.browser", "Browser")
        play("test.event", "Alerts", True)
        wait_for(lambda: state() == [["id:test.browser", False, 1], ["id:test.music", False, 2]], "grouped apps without notification")
        wait_for(lambda: js("devices.filter(d=>d.available).length") == 2, "both outputs")
        choose("Volume for Music")
        wait_for(lambda: all(next(iter(s["volume"].values()))["value_percent"] == "37%" for s in inputs("test.music")), "both sliders")
        assert next(iter(inputs("test.browser")[0]["volume"].values()))["value_percent"] == "100%"
        choose("Mute Music")
        wait_for(lambda: all(s["mute"] for s in inputs("test.music")), "both muted")
        assert not inputs("test.browser")[0]["mute"]
        choose("Unmute Music")
        choose("Options for Music")
        choose("Play through")
        choose("Desk speakers")
        sinks = {s["name"]:s["index"] for s in json.loads(pactl("-f", "json", "list", "sinks"))}
        wait_for(lambda: all(s["sink"] == sinks["monet_two"] for s in inputs("test.music")), "group routed")
        assert inputs("test.browser")[0]["sink"] == sinks["monet_one"]
        assert pactl("get-default-sink") == "monet_one"
        # Reorder by dragging the label across the neighboring row.
        source = QPoint(*point("Music", label=True))
        target = QPoint(*point("Browser", label=True))
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, source)
        for part in range(1, 9):
            QTest.mouseMove(win, source + (target - source) * (part / 8), 18)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, target)
        wait_for(lambda: state()[0][0] == "id:test.music", "drop moved the row")
        QTest.qWait(200)
        choose("Options for Music")
        choose("Move down")
        wait_for(lambda: state()[1][0] == "id:test.music", "menu moved the row down")
        QTest.qWait(200)
        choose("Options for Music")
        choose("Move up")
        wait_for(lambda: state()[0][0] == "id:test.music", "menu moved the row up")
        choose("Options for Music")
        choose("Pin app")
        stop(first)
        stop(second)
        wait_for(lambda: state()[0] == ["id:test.music", True, 0], "offline pinned row")
        win.close()
        win.deleteLater()
        QTest.qWait(50)
        win = component.create()
        model = win.findChild(QObject, "appMixerModel")
        model.setProperty("helper", helper_path)
        wait_for(lambda: state() == [["id:test.music", True, 0], ["id:test.browser", False, 1]], "reopened mixer")
        play("test.music", "Music")
        wait_for(lambda: state()[0] == ["id:test.music", True, 1], "new stream inherited pin")
        assert next(iter(inputs("test.music")[0]["volume"].values()))["value_percent"] == "37%", inputs("test.music")[0]["volume"]
        choose("Options for Music")
        choose("Unpin app")
        wait_for(lambda: state()[0] == ["id:test.music", False, 1], "unpin preserves order")
        edits = [{"key": "id:test." + name, "pin": True, "name": name} for name in ("Mail", "Recorder")]
        jobs = [subprocess.Popen([helper_path, "mixer-arrange", json.dumps(edit).encode().hex()],
                                 stdout=subprocess.PIPE, text=True) for edit in edits]
        for job in jobs:
            stdout, _ = job.communicate(timeout=10)
            assert job.returncode == 0 and json.loads(stdout)["ok"]
        wait_for(lambda: {s[0] for s in state() if s[1]} == {e["key"] for e in edits}, "concurrent edits from other mixers")
        win.close()
        win.deleteLater()
        QTest.qWait(50)
    assert not warnings, warnings


try:
    {'native': native_updates, 'fallback': fallback, 'recovery': recovery,
     'widget': widget, 'mixer': app_mixer, 'output-order': output_priority, 'headphone-volume': headphone_volume, 'notifications': notifications, 'dock-volume': dock_volume,
     'dock-volume-memory': dock_volume_memory}[sys.argv[1]]()
finally:
    for component, obj in objects: obj.deleteLater()
    QTest.qWait(50)
    stop_server()
    if core:
        core.terminate(); core.wait(timeout=5)
    log.close()
