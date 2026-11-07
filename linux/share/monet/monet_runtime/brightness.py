"""Event-driven brightness memory using PowerDevil's logical, undimmed level.

The kernel backlight can stay at 100% in HDR mode even with a low brightness
slider. Never save that raw value or a temporary idle-dimming multiplier.
External monitors retain their independent native settings.
"""
import json
import math
import os
from pathlib import Path
import signal
import tempfile

SERVICE = 'org.kde.ScreenBrightness'
ROOT = '/org/kde/ScreenBrightness'
DISPLAY = SERVICE + '.Display'
CONTEXT = 'monet_restore'


class Memory:
    def __init__(self, path):
        self.path, self.ratio, self.dirty = path, None, False
        try:
            data = json.loads(path.read_text())
            value = data.get('internal')
            if data.get('version') == 1 and type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1:
                self.ratio = value
        except (OSError, ValueError, AttributeError):
            pass

    def remember(self, value, maximum, context=''):
        if context in (CONTEXT, 'profile_brightness'):
            return False
        if type(value) is not int or type(maximum) is not int or maximum <= 0 or not 0 <= value <= maximum:
            return False
        ratio = value / maximum
        if ratio != self.ratio:
            self.ratio, self.dirty = ratio, True
        return self.dirty

    def target(self, maximum):
        if self.ratio is None or type(maximum) is not int or maximum <= 0:
            return None
        return round(self.ratio * maximum)

    def save(self):
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix='brightness-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(dict(version=1, internal=self.ratio), stream)
                stream.write('\n')
            os.replace(temporary, self.path)
            self.dirty = False
        finally:
            Path(temporary).unlink(missing_ok=True)


def main():
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    # Single connection-owned instance even if a session helper is run twice.
    reply = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
        'RequestName', GLib.Variant('(su)', ('org.monet.Brightness', 4)), None,
        Gio.DBusCallFlags.NONE, 2500, None)
    if reply.unpack()[0] not in (1, 4):
        return 0
    memory = Memory(Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'monet/brightness.json')
    flags = Gio.DBusProxyFlags.DO_NOT_AUTO_START
    root = Gio.DBusProxy.new_sync(bus, flags, None, SERVICE, ROOT, SERVICE, None)
    displays, restored = {}, set()
    owner = [None]
    timer = [None]
    loop = GLib.MainLoop()

    def value(proxy, name):
        item = proxy.get_cached_property(name)
        return item.unpack() if item is not None else None

    def flush():
        timer[0] = None
        try:
            memory.save()
        except OSError as error:
            print('Could not save brightness:', error, flush=True)
        return False

    def remember(level, maximum, context=''):
        if memory.remember(level, maximum, context):
            if timer[0] is not None:
                GLib.source_remove(timer[0])
            timer[0] = GLib.timeout_add(250, flush)

    def finished(proxy, result):
        try:
            proxy.call_finish(result)
        except GLib.Error as error:
            print('Could not restore brightness:', error.message, flush=True)

    def refresh(*_args):
        current = root.get_name_owner()
        if current != owner[0]:
            displays.clear(); restored.clear(); owner[0] = current
        if not current:
            return
        names = value(root, 'DisplaysDBusNames') or []
        for name in list(displays):
            if name not in names:
                displays.pop(name)
        for name in names:
            if not isinstance(name, str) or not name.isascii() or not name.isidentifier():
                continue
            if name not in displays:
                try:
                    displays[name] = Gio.DBusProxy.new_sync(bus, flags, None, current, ROOT+'/'+name, DISPLAY, None)
                except GLib.Error:
                    continue
            display = displays[name]
            if value(display, 'IsInternal') is not True:
                continue
            maximum, level = value(display, 'MaxBrightness'), value(display, 'Brightness')
            if type(maximum) is not int or maximum <= 0:
                continue
            if name not in restored:
                restored.add(name)
                target = memory.target(maximum)
                if target is None:
                    remember(level, maximum)
                elif target != level:
                    display.call('SetBrightnessWithContext', GLib.Variant('(ius)', (target, 1, CONTEXT)),
                                 Gio.DBusCallFlags.NONE, 2500, None, finished)
                # The boot-time greeter seed chooses the most recently used
                # account, even when its brightness did not change this login.
                if memory.ratio is not None:
                    memory.dirty = True
                    remember(round(memory.ratio * maximum), maximum)
            # One built-in panel; never apply its level to a docked monitor.
            break

    def changed(_proxy, _sender, name, parameters):
        if name in ('DisplayAdded', 'DisplayRemoved'):
            refresh()
        elif name == 'BrightnessChanged':
            display_name, level, _client, context = parameters.unpack()
            display = displays.get(display_name)
            if display is not None and value(display, 'IsInternal') is True:
                remember(level, value(display, 'MaxBrightness'), context)

    root.connect('notify::g-name-owner', refresh)
    root.connect('g-properties-changed', refresh)
    root.connect('g-signal', changed)
    refresh()

    def quit_later():
        loop.quit()
        return False
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, quit_later)
    try:
        loop.run()
    finally:
        flush()
    return 0
