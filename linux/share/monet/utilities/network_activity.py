"""Network interfaces and kernel byte counters for the on-demand activity view."""
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings, QStandardPaths
from PySide6.QtNetwork import QNetworkInterface

from actions import tr


@dataclass(frozen=True)
class Connection:
    name: str
    index: int
    title: str
    addresses: tuple
    received: int | None
    sent: int | None


def counters(path=Path("/proc/net/dev")):
    try:
        lines = path.read_text().splitlines()[2:]
    except OSError:
        return {}
    values = {}
    for line in lines:
        name, separator, data = line.rpartition(":")
        fields = data.split()
        if separator and len(fields) >= 9 and fields[0].isdigit() and fields[8].isdigit():
            values[name.strip()] = int(fields[0]), int(fields[8])
    return values


def default_routes(proc=Path("/proc/net")):
    """Return interface names in route metric order, preferring IPv4 for ties."""
    routes = []
    for filename in ("route", "ipv6_route"):
        try:
            rows = (proc / filename).read_text().splitlines()
        except OSError:
            continue
        for row in rows:
            parts = row.split()
            try:
                if filename == "route" and parts[1] == "00000000" and parts[7] == "00000000":
                    flag = int(parts[3], 16)
                    metric, family, name = int(parts[6]), 0, parts[0]
                elif filename == "ipv6_route" and parts[0] == "0" * 32 and parts[1] == "00":
                    flag = int(parts[8], 16)
                    metric, family, name = int(parts[5], 16), 1, parts[9]
                else:
                    continue
                if flag & 1 and not flag & 0x200 and name != "lo":
                    routes.append((metric, family, name))
            except (ValueError, IndexError):
                continue
    return list(dict.fromkeys(name for _, _, name in sorted(routes)))


def connections():
    totals = counters()
    found = []
    flag = QNetworkInterface.InterfaceFlag
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not flags & flag.IsUp or not flags & flag.IsRunning or flags & flag.IsLoopBack:
            continue
        addresses = []
        for entry in iface.addressEntries():
            host = entry.ip().toString()
            try:
                address = ipaddress.ip_address(host.partition("%")[0])
            except ValueError:
                continue
            if not (address.is_unspecified or address.is_loopback or address.is_multicast):
                addresses.append((address.version, address.is_link_local, host))
        if addresses:
            name = iface.name()
            title = iface.humanReadableName() or name
            if title == name:
                kind = iface.type()
                # Some Linux Wi-Fi drivers identify as Ethernet through Qt.
                if kind == QNetworkInterface.Wifi or (Path("/sys/class/net") / name / "wireless").is_dir():
                    title = tr("Wi-Fi ({interface})").format(interface=name)
                elif kind == QNetworkInterface.Ethernet:
                    title = tr("Ethernet ({interface})").format(interface=name)
            found.append(Connection(name, iface.index(), title,
                                    tuple(a for _, _, a in sorted(set(addresses))),
                                    *totals.get(name, (None, None))))
    order = {name: i for i, name in enumerate(default_routes())}
    return sorted(found, key=lambda link: (order.get(link.name, len(order)), link.title.casefold()))


class Traffic:
    def __init__(self):
        self.last = {}

    def sample(self, links, now):
        current = {}
        rates = {}
        for link in links:
            if link.received is None or link.sent is None:
                continue
            key = (link.index, link.name)
            old = self.last.get(key)
            current[key] = (now, link.received, link.sent)
            if old:
                elapsed = now - old[0]
                if 0 < elapsed <= 5 and link.received >= old[1] and link.sent >= old[2]:
                    rates[link.name] = ((link.received-old[1])/elapsed, (link.sent-old[2])/elapsed)
        self.last = current
        return rates


class SessionTotals:
    """Keep the first reading for this login and preserve counted data across counter resets."""
    def __init__(self, settings=None, session=None):
        if session is None:
            session = os.environ.get("XDG_SESSION_ID") or os.environ.get("WAYLAND_DISPLAY", "")
        self.session = session
        if settings is None:
            runtime = Path(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation))
            # Two graphical logins by the same user share XDG_RUNTIME_DIR.
            key = hashlib.sha256(session.encode()).hexdigest()[:24]
            settings = QSettings(str(runtime / f"monet-network-{key}.ini"), QSettings.IniFormat)
        self.settings = settings
        self.devices = {}
        if settings.value("session", None) == self.session:
            try:
                saved = json.loads(settings.value("devices", "{}"))
                if isinstance(saved, dict):
                    for name, values in saved.items():
                        if isinstance(values, list) and len(values) == 5 and all(type(v) is int and v >= 0 for v in values):
                            self.devices[name] = values
            except (TypeError, ValueError):
                pass
        self.dirty = False

    def sample(self, links):
        checkpoint = False
        for link in links:
            if link.received is None or link.sent is None:
                continue
            previous = self.devices.get(link.name)
            rx = tx = 0
            if previous:
                idx, last_rx, last_tx, rx, tx = previous
                if idx == link.index:
                    rx += link.received - last_rx if link.received >= last_rx else link.received
                    tx += link.sent - last_tx if link.sent >= last_tx else link.sent
                checkpoint |= idx != link.index or link.received < last_rx or link.sent < last_tx
            else:
                checkpoint = True
            new = [link.index, link.received, link.sent, rx, tx]
            if new != previous:
                self.devices[link.name] = new
                self.dirty = True
        if checkpoint:
            self.save()

    def reset(self, link):
        self.devices[link.name] = [link.index, link.received, link.sent, 0, 0]
        self.dirty = True
        self.save()

    def save(self):
        if self.dirty:
            self.settings.setValue("devices", json.dumps(self.devices))
            self.settings.setValue("session", self.session)
            self.settings.sync()
            self.dirty = self.settings.status() != QSettings.NoError


def rate_text(value, bits=False):
    if value is None:
        return "—"
    scale = value * 8 if bits else value
    units = ("bit/s", "kbit/s", "Mbit/s", "Gbit/s", "Tbit/s") if bits else ("B/s", "kB/s", "MB/s", "GB/s", "TB/s")
    for unit in units[:-1]:
        if scale < 1000:
            break
        scale /= 1000
    else:
        unit = units[-1]
    return QLocale().toString(float(scale), "f", 0 if scale >= 100 or unit == units[0] else 1) + " " + unit
