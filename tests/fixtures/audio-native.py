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
                stream = playing()
                assert stream.channel_list == stereo and not stream.mute, stream
                assert all(abs(value - 0.62) < 0.001 for value in stream.volume.values), stream
            finally:
                player.terminate()
        print('Notification volume defaults, mono migration, and stereo playback passed')


def dock_volume():
    import pulsectl
    import wave

    source = Path(os.environ['MONET_DOCK_AUDIO_QML'])
    # PulseAudio discovers Client metadata asynchronously. Exercise the actual
    # patched delegate with a client arriving after Component.onCompleted.
    delegate = (source / 'PulseAudio.qml').read_text().split('        component StreamDelegate: QtObject {', 1)[1].split('\n        delegate: StreamDelegate', 1)[0]
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
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(delayed)))
    delayed_client = component.create()
    assert delayed_client is not None, [e.toString() for e in component.errors()]
    QTest.qWait(100)
    assert delayed_client.actual() == 65536
    delayed_client.setProperty('ready', True)
    wait_for(lambda: delayed_client.actual() == round(.83 * 65536), 'late app identity restores saved volume')
    delayed_client.deleteLater(); QTest.qWait(50)

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
            assert at(other, 100), 'another app was changed'
            print('Dock volume: next track, separate app, persistence, zero, unmute and other mixers passed')
        finally:
            for player in players:
                if player.poll() is None: player.terminate()
                player.wait(timeout=5)
            policy.terminate()


try:
    {'native': native_updates, 'fallback': fallback, 'recovery': recovery,
     'widget': widget, 'notifications': notifications, 'dock-volume': dock_volume}[sys.argv[1]]()
finally:
    for component, obj in objects: obj.deleteLater()
    QTest.qWait(50)
    stop_server()
    if core:
        core.terminate(); core.wait(timeout=5)
    log.close()
