"""A private BlueZ provider for boot-input tests; never uses the system bus."""
import json
import sys
import time
from pathlib import Path
from gi.repository import Gio, GLib

output, scenario = Path(sys.argv[1]), sys.argv[2]
ADAPTER, DEVICE = 'org.bluez.Adapter1', 'org.bluez.Device1'
AP, DP = '/org/bluez/hci0', '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
GATT = 'org.bluez.GattCharacteristic1'
GP = DP+'/service0001/char0002'
objects = {AP: {ADAPTER: {'Powered': GLib.Variant('b', scenario != 'power-on')}}}
device = {'Adapter': GLib.Variant('o', AP), 'Paired': GLib.Variant('b', True),
    'Trusted': GLib.Variant('b', scenario != 'untrusted'), 'Blocked': GLib.Variant('b', False),
    'Icon': GLib.Variant('s', 'input-mouse'),
    'Connected': GLib.Variant('b', scenario == 'disconnect'),
    'UUIDs': GLib.Variant('as', ['00001812-0000-1000-8000-00805f9b34fb'])}
if scenario != 'added':
    objects[DP] = {DEVICE: device}
if scenario == 'traffic':
    objects[GP] = {GATT: {'Value': GLib.Variant('ay', [0])}}
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
    'RequestName', GLib.Variant('(su)', ('org.bluez', 0)),
    GLib.VariantType.new('(u)'), Gio.DBusCallFlags.NONE, 3000, None)
loop = GLib.MainLoop()
started = False


def record(event):
    with output.open('a') as stream:
        stream.write(json.dumps(dict(event=event, time=time.monotonic())) + '\n')


def changed(path, interface, properties):
    objects[path][interface].update(properties)
    bus.emit_signal(None, path, 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                    GLib.Variant('(sa{sv}as)', (interface, properties, [])))


def transition():
    if scenario == 'power-on':
        record('powered')
        changed(AP, ADAPTER, {'Powered': GLib.Variant('b', True)})
    elif scenario == 'added':
        record('added')
        objects[DP] = {DEVICE: device}
        bus.emit_signal(None, '/', 'org.freedesktop.DBus.ObjectManager', 'InterfacesAdded',
                        GLib.Variant('(oa{sa{sv}})', (DP, objects[DP])))
    elif scenario == 'disconnect':
        record('user-disconnect')
        changed(DP, DEVICE, {'Connected': GLib.Variant('b', False)})
    return False


def traffic():
    changed(GP, GATT, {'Value': GLib.Variant('ay', [1, 2, 3])})
    changed(DP, DEVICE, {'RSSI': GLib.Variant('n', -50)})
    return True


def method(connection, sender, path, interface, name, parameters, invocation):
    global started
    record(name)
    if name == 'GetManagedObjects':
        invocation.return_value(GLib.Variant('(a{oa{sa{sv}}})', (objects,)))
        if not started:
            started = True
            GLib.timeout_add(150, transition)
            if scenario == 'traffic':
                GLib.timeout_add(10, traffic)
            GLib.timeout_add(1400, lambda: loop.quit() or False)
    elif name == 'Connect':
        if scenario in ('in-progress', 'traffic'):
            invocation.return_dbus_error('org.bluez.Error.InProgress', 'Another client is connecting')
        else:
            invocation.return_value(None)
            changed(DP, DEVICE, {'Connected': GLib.Variant('b', True)})
    else:
        invocation.return_dbus_error('org.bluez.Error.NotSupported', name)


def prop(connection, sender, path, interface, name):
    return objects.get(path, {}).get(interface, {}).get(name)


def register(path, xml):
    info = Gio.DBusNodeInfo.new_for_xml(xml)
    for interface in info.interfaces:
        bus.register_object(path, interface, method, prop, None)


register('/', """<node><interface name="org.freedesktop.DBus.ObjectManager">
<method name="GetManagedObjects"><arg direction="out" type="a{oa{sa{sv}}}"/></method>
<signal name="InterfacesAdded"><arg type="o"/><arg type="a{sa{sv}}"/></signal>
</interface></node>""")
register(AP, """<node><interface name="org.bluez.Adapter1">
<property name="Powered" type="b" access="read"/>
</interface></node>""")
register(DP, """<node><interface name="org.bluez.Device1"><method name="Connect"/>
<property name="Adapter" type="o" access="read"/>
<property name="Paired" type="b" access="read"/>
<property name="Trusted" type="b" access="read"/>
<property name="Blocked" type="b" access="read"/>
<property name="Icon" type="s" access="read"/>
<property name="Connected" type="b" access="read"/>
<property name="UUIDs" type="as" access="read"/>
</interface></node>""")
register(GP, """<node><interface name="org.bluez.GattCharacteristic1">
<property name="Value" type="ay" access="read"/>
</interface></node>""")
print('READY', flush=True)
loop.run()
