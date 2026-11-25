"""Watch selected desktop apps' user units, including those working without a window."""
import re

SYSTEMD = 'org.freedesktop.systemd1'
MANAGER = (SYSTEMD, '/org/freedesktop/systemd1', SYSTEMD + '.Manager')


def desktop_id(unit):
    # Desktop app units escape '-' inside the app ID so the launcher's prefix
    # and an optional instance/scope suffix can be removed unambiguously.
    match = re.fullmatch(r'app-(?:[^@-]+-)?([^-@]+)(?:@[^@]*\.service|\.service|-[^-@]+\.scope)', unit)
    if not match:
        return ''
    raw = re.sub(rb'\\x([a-fA-F0-9]{2})', lambda m: bytes([int(m[1], 16)]), match[1].encode())
    return raw.decode('utf-8', errors='replace') + '.desktop'


class AppUnits:
    def __init__(self, backend, Gio, GLib, changed):
        self.backend, self.Gio, self.GLib, self.changed = backend, Gio, GLib, changed
        self.selected = set()
        self.running = set()
        self.owner = ''
        self.events = []
        self.paths = {}
        self.pending = 0

    def subscribe(self, interface, member, path, arg, callback):
        return self.backend.connection.signal_subscribe(self.owner, interface, member, path, arg,
                                                       self.Gio.DBusSignalFlags.NONE, callback)

    def configure(self, selected):
        self.stop()
        self.selected = set(selected)
        if not self.selected:
            return
        try:
            self.owner = self.backend.owner(SYSTEMD)
            endpoint = (self.owner, *MANAGER[1:])
            for member in ('UnitNew', 'UnitRemoved'):
                self.events.append(self.subscribe(MANAGER[2], member, MANAGER[1], None, self.unit_changed))
            self.backend.call(endpoint, 'Subscribe', '()', ())
            self.refresh()
        except RuntimeError:
            self.stop()

    def unit_changed(self, bus, sender, path, interface, member, args):
        if desktop_id(args.unpack()[0]) in self.selected:
            self.schedule()

    def state_changed(self, bus, sender, path, interface, member, args):
        _, values, invalidated = args.unpack()
        if {'ActiveState', 'SubState'}.intersection(values.keys() | set(invalidated)):
            self.schedule()

    def schedule(self):
        if not self.pending:
            self.pending = self.GLib.idle_add(self.refresh)

    def refresh(self):
        self.pending = 0
        try:
            rows, = self.backend.call((self.owner, *MANAGER[1:]), 'ListUnitsByPatterns', '(asas)',
                                      ([], ['app-*.scope', 'app-*.service']))
        except RuntimeError:
            rows = []
        available = set()
        running = set()
        for name, _, _, active, sub, _, path, *_ in rows:
            ident = desktop_id(name)
            if ident not in self.selected:
                continue
            available.add(path)
            if active in ('active', 'reloading', 'refreshing') and sub != 'exited':
                running.add(ident)
        for path in self.paths.keys() - available:
            self.backend.connection.signal_unsubscribe(self.paths.pop(path))
        for path in available - self.paths.keys():
            self.paths[path] = self.subscribe('org.freedesktop.DBus.Properties', 'PropertiesChanged', path,
                                              SYSTEMD + '.Unit', self.state_changed)
            # A newly added unit can start between ListUnits and its subscription.
            self.schedule()
        if running != self.running:
            self.running = running
            self.changed()
        return False

    def stop(self):
        if self.pending:
            self.GLib.source_remove(self.pending)
            self.pending = 0
        for ident in [*self.events, *self.paths.values()]:
            self.backend.connection.signal_unsubscribe(ident)
        if self.owner:
            try:
                self.backend.call((self.owner, *MANAGER[1:]), 'Unsubscribe', '()', ())
            except RuntimeError:
                pass
        self.owner = ''
        self.events.clear()
        self.paths.clear()
        self.selected.clear()
        self.running.clear()
