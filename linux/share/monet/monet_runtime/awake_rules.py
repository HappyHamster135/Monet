"""Opt-in Keep awake rules. Observe only the inputs the user selected."""
import json
import os
from pathlib import Path
import re
import tempfile

from .awake_apps import AppUnits


def preferences(settings=None):
    if settings is None:
        # A manual timer on a fresh account needs no Utilities configuration.
        config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        if not (config / 'Monet/Utilities.conf').is_file():
            return {}
        from PySide6.QtCore import QSettings
        settings = QSettings('Monet', 'Utilities')
    settings.sync()
    try:
        value = json.loads(settings.value('awakeRules', '{}'))
        hidden = json.loads(settings.value('hidden', '[]'))
    except (ValueError, TypeError):
        return {}
    if not isinstance(value, dict):
        return {}
    apps = value.get('apps', {})
    if not isinstance(apps, dict):
        apps = {}
    delay = value.get('powerDelay', 0)
    return dict(requireAll=value.get('requireAll') is True,
                powerDelay=delay if type(delay) is int and 0 <= delay <= 60 else 0,
                enabled=value.get('enabled') is True, power=value.get('power') is True,
                external=value.get('external') is True, display=value.get('display') is True,
                visible=isinstance(hidden, list) and 'awake' not in hidden,
                apps={k: aliases for k, aliases in apps.items()
                      if k.endswith('.desktop') and '/' not in k and isinstance(aliases, list)
                      and all(isinstance(alias, str) and alias for alias in aliases)})


def watching(rules):
    return bool(rules.get('enabled') and rules.get('visible') and
                (rules.get('power') or rules.get('external') or rules.get('apps')))


def external_connected(root=Path('/sys/class/drm')):
    # Connector types come from DRM. Internal panels and virtual capture outputs
    # must not turn a laptop's external-display rule on by themselves.
    for port in root.glob('card*-*'):
        if not re.fullmatch(r'card\d+-(?:HDMI-[AB]|DP|DVI-[ADI]|VGA|DisplayPort|USB|Thunderbolt|TV|SVIDEO|Composite|Component)-[\d-]+', port.name):
            continue
        try:
            if (port / 'status').read_text().strip() == 'connected':
                return True
        except OSError:
            continue
    return False


def reasons(rules, plugged, external, windows, running=(), waiting_for_power=False):
    if not watching(rules):
        return []
    hits = []
    require_all = rules.get('requireAll', False)
    if rules['power']:
        if plugged or waiting_for_power:
            hits.append('power' if plugged else 'power-delay')
        elif require_all:
            return []
    if rules['external']:
        if external:
            hits.append('external')
        elif require_all:
            return []
    apps = [desktop for desktop, aliases in rules['apps'].items()
            if desktop in running or desktop.removesuffix('.desktop').lower() in windows
            or any(alias in windows for alias in aliases)]
    if require_all and rules['apps'] and not apps:
        return []
    return sorted(hits + apps)


KWIN = 'org.kde.KWin'
SCRIPT = 'monet-keep-awake-windows'
SCRIPTING = (KWIN, '/Scripting', 'org.kde.kwin.Scripting')
WINDOWS = """
let previous = null;
function report(removed) {
    const ids = new Set();
    for (const w of workspace.stackingOrder) {
        if (w === removed || w.deleted || !w.managed || !(w.normalWindow || w.dialog)) continue;
        const id = String(w.desktopFileName || w.resourceClass || "").split("/").pop()
            .replace(/\\.desktop$/i, "").toLowerCase();
        if (id) ids.add(id);
    }
    const encoded = JSON.stringify(Array.from(ids).sort());
    if (encoded !== previous) {
        previous = encoded;
        callDBus(destination, "/org/monet/KeepAwake", "org.monet.KeepAwake", "WindowsChanged", encoded);
    }
}
function observe(w) {
    w.desktopFileNameChanged.connect(() => report());
    if (w.windowClassChanged) w.windowClassChanged.connect(() => report());
}
workspace.stackingOrder.forEach(observe);
workspace.windowAdded.connect(w => { observe(w); report(); });
workspace.windowRemoved.connect(w => report(w));
report();
"""


class RuleMonitor:
    def __init__(self, backend, controller, Gio, GLib):
        self.backend, self.controller, self.Gio, self.GLib = backend, controller, Gio, GLib
        self.rules = {}
        self.power = self.udev = self.rescan = self.poll = self.script = None
        self.kwin_owner = ''
        self.plugged = self.external = False
        self.unplugged_at = None
        self.power_deadline = 0.
        self.deadline_changed = lambda: None
        self.windows = set()
        self.units = AppUnits(backend, Gio, GLib, self.update)

    def update(self):
        delay = self.rules.get('powerDelay', 0)
        deadline = self.unplugged_at + delay if self.unplugged_at is not None and delay else 0.
        waiting = bool(deadline and self.controller.clock() < deadline)
        hits = reasons(self.rules, self.plugged, self.external, self.windows, self.units.running, waiting)
        if 'power-delay' not in hits:
            self.unplugged_at = None
            deadline = 0.
        self.controller.set_rules(hits, self.rules.get('display', False))
        if self.power_deadline != deadline:
            self.power_deadline = deadline
            self.deadline_changed()

    def reload(self):
        rules = preferences()
        self.rules = rules if watching(rules) else {}
        self.controller.watching = bool(self.rules)
        if bool(self.rules.get('power')) != bool(self.power):
            self.watch_power(bool(self.rules.get('power')))
        if bool(self.rules.get('external')) != bool(self.udev or self.poll):
            self.watch_displays(bool(self.rules.get('external')))
        selected = set(self.rules.get('apps', {}))
        if selected != self.units.selected:
            self.units.configure(selected)
        if selected and not self.script:
            self.watch_windows()
        elif not selected:
            self.stop_windows()
        self.update()

    def watch_power(self, enable):
        if self.power:
            for handler in self.power_handlers:
                self.power.disconnect(handler)
        self.power = None
        self.plugged = False
        self.unplugged_at = None
        if not enable:
            return
        try:
            self.power = self.Gio.DBusProxy.new_for_bus_sync(self.Gio.BusType.SYSTEM,
                self.Gio.DBusProxyFlags.NONE, None, 'org.freedesktop.UPower', '/org/freedesktop/UPower',
                'org.freedesktop.UPower', None)
        except self.GLib.Error:
            return
        def changed(*_):
            prop = self.power.get_cached_property('OnBattery')
            known = bool(self.power.get_name_owner() and prop is not None)
            plugged = known and prop.unpack() is False
            if plugged or not known:
                self.unplugged_at = None
            elif self.plugged and self.rules.get('powerDelay') and 'power' in self.controller.reasons and self.controller.cookies is not None:
                self.unplugged_at = self.controller.clock()
            self.plugged = plugged
            self.update()
        self.power_handlers = [self.power.connect(key, changed) for key in ('g-properties-changed', 'notify::g-name-owner')]
        changed()

    def watch_displays(self, enable):
        if self.udev:
            self.udev.disconnect(self.udev_handler)
        if self.rescan:
            self.GLib.source_remove(self.rescan)
            self.rescan = None
        if self.poll:
            self.GLib.source_remove(self.poll)
            self.poll = None
        self.udev = None
        self.external = False
        if not enable:
            return
        def scan():
            self.rescan = None
            self.external = external_connected()
            self.update()
            return False
        def changed(*_):
            if not self.rescan:
                self.rescan = self.GLib.timeout_add(150, scan)
        try:
            import gi
            gi.require_version('GUdev', '1.0')
            from gi.repository import GUdev
            self.udev = GUdev.Client.new(['drm'])
            self.udev_handler = self.udev.connect('uevent', changed)
        except (ImportError, ValueError):
            # Portable installations can lack GUdev. Check connectors only while
            # this rule is selected. The Monet image uses native hotplug events.
            def poll():
                scan()
                return True
            self.poll = self.GLib.timeout_add_seconds(15, poll)
        scan()

    def stop_windows(self):
        if self.script:
            try:
                self.backend.call((self.kwin_owner, *SCRIPTING[1:]), 'unloadScript', '(s)', (SCRIPT,))
            except RuntimeError:
                pass
            self.script.cleanup()
        self.script = None
        self.kwin_owner = ''
        self.windows.clear()

    def watch_windows(self):
        self.stop_windows()
        try:
            self.kwin_owner = self.backend.owner(KWIN)
            endpoint = (self.kwin_owner, *SCRIPTING[1:])
            if self.backend.call(endpoint, 'isScriptLoaded', '(s)', (SCRIPT,))[0]:
                self.backend.call(endpoint, 'unloadScript', '(s)', (SCRIPT,))
            self.script = tempfile.TemporaryDirectory(prefix='monet-awake-')
            path = Path(self.script.name) / 'windows.js'
            destination = json.dumps(self.backend.connection.get_unique_name())
            path.write_text('const destination = ' + destination + ';\n' + WINDOWS)
            ident, = self.backend.call(endpoint, 'loadScript', '(ss)', (str(path), SCRIPT))
            if ident < 0:
                raise RuntimeError('KWin could not load the window observer')
            self.backend.call((self.kwin_owner, f'/Scripting/Script{ident}', 'org.kde.kwin.Script'), 'run', '()', ())
        except (OSError, RuntimeError):
            self.stop_windows()

    def windows_changed(self, sender, text):
        if sender != self.kwin_owner or not self.script:
            return False
        ids = json.loads(text)
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            return False
        self.windows = set(ids)
        self.update()
        return True

    def close(self):
        self.rules = {}
        self.controller.watching = False
        self.watch_power(False)
        self.watch_displays(False)
        self.stop_windows()
        self.units.stop()
        self.update()
