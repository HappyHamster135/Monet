#!/usr/bin/env python3
"""Check the built Plasma shutdown service using private session and system buses."""
import json
from pathlib import Path
import subprocess
import sys
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.test import private_session, stop


class X11Session(dbus.service.Object):
    def __init__(self, bus):
        self.name = dbus.service.BusName('org.kde.ksmserver', bus, do_not_queue=True)
        super().__init__(self.name, '/KSMServer')
        self.pending = None
        self.reset = False

    @dbus.service.method('org.kde.KSMServerInterface', out_signature='b', async_callbacks=('reply', 'error'))
    def closeSession(self, reply, error):
        self.pending = reply, error

    @dbus.service.method('org.kde.KSMServerInterface')
    def resetLogout(self):
        self.reset = True


class WaylandSession(dbus.service.Object):
    def __init__(self, bus):
        self.name = dbus.service.BusName('org.kde.KWin', bus, do_not_queue=True)
        super().__init__(self.name, '/Session')
        self.pending = None

    @dbus.service.method('org.kde.KWin.Session', out_signature='b', async_callbacks=('reply', 'error'))
    def closeWaylandWindows(self, reply, error):
        self.pending = reply, error


class Logind(dbus.service.Object):
    def __init__(self, bus, target, deny_reboot, supported):
        self.name = dbus.service.BusName('org.freedesktop.login1', bus, do_not_queue=True)
        super().__init__(self.name, '/org/freedesktop/login1')
        self.target, self.deny_reboot, self.supported = target, deny_reboot, supported
        self.events = []

    @dbus.service.method('org.freedesktop.login1.Manager', out_signature='s')
    def CanRebootToFirmwareSetup(self):
        return 'yes' if self.supported else 'na'

    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
    def Get(self, interface, name):
        assert (interface, name) == ('org.freedesktop.login1.Manager', 'RebootToFirmwareSetup')
        return dbus.Boolean(self.target, variant_level=1)

    @dbus.service.method('org.freedesktop.login1.Manager', in_signature='b')
    def SetRebootToFirmwareSetup(self, enable):
        self.target = bool(enable)
        self.events.append(('target', self.target))

    @dbus.service.method('org.freedesktop.login1.Manager', in_signature='b')
    def Reboot(self, interactive):
        assert interactive and self.target
        self.events.append(('reboot', True))
        if self.deny_reboot:
            raise dbus.exceptions.DBusException('Reboot refused', name='org.freedesktop.DBus.Error.AccessDenied')


def wait_for(condition):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError('Expected shutdown state did not arrive')


def check(binary, outcome):
    with private_session() as env:
        env['DBUS_SYSTEM_BUS_ADDRESS'] = env['DBUS_SESSION_BUS_ADDRESS']
        (Path(env['XDG_CONFIG_HOME']) / 'ksmserverrc').write_text('[General]\nloginMode=emptySession\n')
        bus = dbus.bus.BusConnection(env['DBUS_SESSION_BUS_ADDRESS'], mainloop=DBusGMainLoop())
        x11, wayland = X11Session(bus), WaylandSession(bus)
        logind = Logind(bus, outcome == 'preexisting-target', outcome in ('refused-reboot', 'preexisting-target'),
                        outcome != 'unsupported')
        process = subprocess.Popen([binary], env=env, start_new_session=True)
        try:
            wait_for(lambda: bus.name_has_owner('org.kde.Shutdown'))

            def request():
                call = subprocess.Popen(['busctl', '--user', 'call', 'org.kde.Shutdown', '/Shutdown',
                                         'org.kde.Shutdown', 'logoutAndRebootToFirmware'],
                                        env=env, stdout=subprocess.PIPE, text=True, start_new_session=True)
                try:
                    wait_for(lambda: call.poll() is not None)
                    assert call.returncode == 0
                    return call.communicate()[0].strip()
                finally:
                    stop(call)

            assert request() == ('b false' if outcome == 'unsupported' else 'b true')
            if outcome == 'unsupported':
                assert not x11.pending and not logind.events
                return []

            wait_for(lambda: x11.pending is not None)
            assert not logind.events
            assert request() == 'b false'
            reply, error = x11.pending
            if outcome == 'x11-error':
                error(dbus.exceptions.DBusException('Close failed'))
            else:
                reply(outcome != 'x11-cancel')
            if outcome not in ('x11-cancel', 'x11-error'):
                wait_for(lambda: wayland.pending is not None)
                assert not logind.events
                wayland.pending[0](outcome != 'wayland-cancel')
            wait_for(lambda: process.poll() is not None)
            assert process.returncode == 0

            expected = {
                'reboot': [('target', True), ('reboot', True)],
                'refused-reboot': [('target', True), ('reboot', True), ('target', False)],
                'preexisting-target': [('reboot', True)],
            }.get(outcome, [])
            assert logind.events == expected, logind.events
            assert logind.target == (outcome in ('reboot', 'preexisting-target'))
            if outcome in ('wayland-cancel', 'refused-reboot', 'preexisting-target'):
                wait_for(lambda: x11.reset)
            return logind.events
        finally:
            stop(process)
            bus.close()


if __name__ == '__main__':
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    cases = ('unsupported', 'x11-cancel', 'x11-error', 'wayland-cancel',
             'refused-reboot', 'preexisting-target', 'reboot')
    print(json.dumps({case: check(binary, case) for case in cases}, indent=2))
