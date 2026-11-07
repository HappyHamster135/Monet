"""Actual Gio signal/restore round trips on a private bus; never laptop hardware."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

assert os.environ['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:path=/tmp/monet-tests-')
assert os.environ['DBUS_SYSTEM_BUS_ADDRESS'] == 'unix:path=/nonexistent'
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'linux/share/monet'))
from monet_runtime.brightness import SERVICE, ROOT as OBJECT, DISPLAY, Memory
TEST = 'org.monet.BrightnessTest'
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(name, path, interface, method, signature='()', args=()):
    return bus.call_sync(name, path, interface, method, GLib.Variant(signature, args), None,
                         Gio.DBusCallFlags.NONE, 2500, None).unpack()


def own(name):
    return call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                'RequestName', '(su)', (name, 4))[0]


if len(sys.argv) > 1:
    internal = sys.argv[1]
    state = dict(level=1000, external=750, calls=[], steps=[])
    root_xml = '''<node><interface name="org.kde.ScreenBrightness">
    <property name="DisplaysDBusNames" type="as" access="read"/>
    <method name="AdjustBrightnessStepWithContext"><arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/></method>
    <method name="AdjustBrightnessStep"><arg type="u" direction="in"/><arg type="u" direction="in"/></method>
    <signal name="BrightnessChanged"><arg type="s"/><arg type="i"/><arg type="s"/><arg type="s"/></signal>
    </interface></node>'''
    display_xml = '''<node><interface name="org.kde.ScreenBrightness.Display">
    <property name="IsInternal" type="b" access="read"/>
    <property name="Label" type="s" access="read"/>
    <property name="Brightness" type="i" access="read"/>
    <property name="MaxBrightness" type="i" access="read"/>
    <method name="SetBrightnessWithContext"><arg type="i" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/></method>
    </interface></node>'''
    test_xml = '''<node><interface name="org.monet.BrightnessTest">
    <method name="Snapshot"><arg type="s" direction="out"/></method>
    <method name="Change"><arg type="s" direction="in"/><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
    <method name="Reset"/></interface></node>'''

    def emit(name, level, context, client=':1.99'):
        key = 'level' if name == internal else 'external'
        state[key] = level
        bus.emit_signal(None, OBJECT, SERVICE, 'BrightnessChanged', GLib.Variant('(siss)', (name, level, client, context)))

    def prop(_bus, _sender, path, interface, name):
        if name == 'DisplaysDBusNames': return GLib.Variant('as', ['display0', internal])
        if name == 'IsInternal': return GLib.Variant('b', path.endswith('/'+internal))
        if name == 'Label': return GLib.Variant('s', 'Built-in Screen' if path.endswith('/'+internal) else 'External Screen')
        if name == 'MaxBrightness': return GLib.Variant('i', 1000)
        return GLib.Variant('i', state['level' if path.endswith('/'+internal) else 'external'])

    def method(_bus, sender, path, interface, name, args, invocation):
        values = args.unpack()
        if name == 'Snapshot':
            invocation.return_value(GLib.Variant('(s)', (json.dumps(state),))); return
        if name == 'SetBrightnessWithContext':
            assert path.endswith('/'+internal), 'external monitor was changed'
            state['calls'].append(list(values))
            emit(internal, values[0], values[2], sender)
        elif name in ('AdjustBrightnessStepWithContext','AdjustBrightnessStep'):
            state['steps'].append(list(values))
            emit(internal, max(0,min(1000,state['level'] + (50 if values[0] in (0,2) else -50))), values[2] if len(values)>2 else '', sender)
        elif name == 'Change': emit(*values)
        elif name == 'Reset': state['level'] = 1000
        invocation.return_value(GLib.Variant('()', ()))

    infos = []
    for path, xml in [(OBJECT, root_xml), (OBJECT+'/display0', display_xml),
                      (OBJECT+'/'+internal, display_xml), ('/test', test_xml)]:
        info = Gio.DBusNodeInfo.new_for_xml(xml); infos.append(info)
        bus.register_object(path, info.interfaces[0], method, prop, None)
    assert own(SERVICE) == own(TEST) == 1
    print('READY', flush=True)
    GLib.MainLoop().run()
else:
    memory_path = Path(os.environ['XDG_STATE_HOME'])/'monet/brightness.json'
    memory = Memory(memory_path); memory.remember(27, 100); memory.save()
    children = []
    def wait(condition):
        end = time.monotonic()+5
        while time.monotonic() < end:
            if condition(): return
            time.sleep(.03)
        raise AssertionError('Brightness round trip timed out')
    def worker():
        child = subprocess.Popen([sys.executable, str(ROOT/'linux/libexec/monet-brightness')],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        children.append(child); return child
    def fake(name):
        child = subprocess.Popen([sys.executable, __file__, name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        children.append(child)
        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline().strip() == 'READY', child.stderr.read()
        return child
    def snapshot(): return json.loads(call(TEST, '/test', TEST, 'Snapshot')[0])
    def change(name, value, context=''):
        call(TEST, '/test', TEST, 'Change', '(sis)', (name, value, context))
    def stop(child):
        child.terminate(); child.wait(timeout=4)
    def saved(value): return Memory(memory_path).target(1000) == value
    try:
        process = worker()  # Service deliberately arrives late.
        server = fake('display1')
        wait(lambda: snapshot()['level'] == 270)
        assert snapshot()['calls'] == [[270, 1, 'monet_restore']]
        change('display1', 430, 'brightness-key')
        wait(lambda: saved(430))
        change('display0', 900)  # Docked display stays independent.
        change('display1', 300, 'profile_brightness')
        time.sleep(.35)
        assert saved(430)
        assert snapshot()['external'] == 900
        stop(process)
        call(TEST, '/test', TEST, 'Reset')
        process = worker()
        wait(lambda: snapshot()['level'] == 430)
        # A PowerDevil restart renumbers the panel; the saved level is not tied
        # to display0/display1, and the external screen is never mistaken for it.
        stop(server)
        server = fake('display9')
        wait(lambda: snapshot()['level'] == 430)
        for value in (100, 300, 520, 610): change('display9', value, 'slider')
        wait(lambda: saved(610))
        assert snapshot()['external'] == 750
        assert snapshot()['calls'] == [[430, 1, 'monet_restore']]
        stop(process)
        assert process.returncode == 0, process.stderr.read()
        print('BRIGHTNESS_MEMORY_OK', flush=True)
    finally:
        for child in children:
            if child.poll() is None: child.kill(); child.wait()
            child.stdout.close(); child.stderr.close()
