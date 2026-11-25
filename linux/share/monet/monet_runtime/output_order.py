"""A user's ranked playback routes. The listener sleeps until the audio graph changes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

UNIT = "monet-output-order.service"


def settings_path():
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "monet/output-order.json"


def validate(value):
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise ValueError("settings")
    rows = value.get("devices")
    if not isinstance(rows, list) or len(rows) > 48 or (value["enabled"] and not rows):
        raise ValueError("device count")
    seen = set()
    devices = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("device")
        key, port, name = (row.get(k) for k in ("key", "port", "name"))
        if (not isinstance(key, str) or not re.fullmatch(r"(?:[a-f0-9]{2}){1,1024}", key)
                or not isinstance(port, str) or len(port) > 256 or not isinstance(name, str)
                or not name.strip() or len(name) > 256 or any(ord(c) < 32 for c in name + port)
                or (key, port) in seen):
            raise ValueError("invalid route")
        seen.add((key, port))
        devices.append(dict(key=key, port=port, name=name.strip()))
    result = dict(enabled=value["enabled"], devices=devices)
    limit_enabled = value.get("headphoneLimitEnabled", False)
    limit = value.get("headphoneLimit", 20)
    if type(limit_enabled) is not bool or type(limit) is not int or not 0 <= limit <= 100:
        raise ValueError("speaker limit")
    # Preserve the original revisions for existing output orders.
    if limit_enabled:
        result["headphoneLimitEnabled"] = True
    if limit != 20:
        result["headphoneLimit"] = limit
    return result


def read(path):
    try:
        return validate(json.loads(path.read_text()))
    except FileNotFoundError:
        return dict(enabled=False, devices=[])


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def write(path, config):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(config, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def service(enabled):
    actions = [("enable", UNIT), ("restart", UNIT)] if enabled else [("disable", "--now", UNIT)]
    for args in actions:
        subprocess.run(["systemctl", "--user", *args], check=True, capture_output=True, timeout=12)


def save(path, value, expected):
    if not isinstance(value, dict):
        raise ValueError("settings")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (path.parent / ".output-order.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = read(path)
        if expected != revision(old):
            return "changed"
        # Editors already open during an update only know about the order.
        options = {k: old[k] for k in ("headphoneLimitEnabled", "headphoneLimit") if k in old}
        new = validate({**options, **value})
        if new == old:
            return ""
        write(path, new)
        if listening(new) or listening(old):
            try:
                service(listening(new))
            except (OSError, subprocess.SubprocessError):
                write(path, old)
                try:
                    service(listening(old))
                except (OSError, subprocess.SubprocessError):
                    return "service-unavailable"
                return "service"
    return ""


def route(props, active_port):
    name = props.get("node.name", "")
    if not isinstance(name, str) or not name or name == "auto_null":
        return None
    # Bluetooth codecs can give one physical headset a new node suffix or port.
    bt = re.fullmatch(r"bluez_output\.([a-f\d]{2}(?:[_:][a-f\d]{2}){5})(?:\..+)?", name, re.I)
    if bt:
        name = "bluez_output." + bt[1].lower().replace(":", "_")
        active_port = ""
    return (name.encode().hex(), active_port or "")


def available(sinks):
    result = {}
    for sink in sinks:
        port = sink.port_active
        if port and port.available == "no":
            continue
        identity = route(sink.proplist, port.name if port else "")
        if identity:
            result.setdefault(identity, []).append(sink)
    return result


def output_kind(sink):
    """Use route metadata. A single laptop output can serve both speakers and a jack."""
    props = sink.proplist
    port_name = sink.port_active.name.lower() if sink.port_active else ""
    form = props.get("device.form_factor", "").lower()
    icon = props.get("device.icon_name", "").lower()
    device_kind = ""
    if form in ("headset", "headphone", "headphones", "hands-free"):
        device_kind = "headphones"
    elif form == "speaker":
        device_kind = "speaker"
    elif icon.startswith(("audio-headphones", "audio-headset")):
        device_kind = "headphones"
    elif icon.startswith("audio-speakers"):
        device_kind = "speaker"
    # BlueZ can report the same port name for a headset and a wireless speaker.
    if device_kind and props.get("node.name", "").startswith("bluez_output."):
        return device_kind
    if any(word in port_name for word in ("headphone", "headset", "earphone")):
        return "headphones"
    if "speaker" in port_name:
        return "speaker"
    if any(word in port_name for word in ("hdmi", "spdif", "lineout", "line-out")):
        return ""
    return device_kind


class SpeakerLimit:
    def __init__(self, percent):
        self.level = percent / 100
        self.headphones = None
        self.deadline = 0
        self.lowered = None

    def restore(self, pulse, found, headphones):
        if not self.lowered:
            return
        key, index, original, limited = self.lowered
        self.lowered = None
        for speaker in found.get(key, ()):
            if speaker.index != index or speaker.index == headphones.index or output_kind(speaker) != "speaker":
                continue
            values = speaker.volume.values
            if len(values) != len(limited) or any(abs(a - b) > 1 / 65536 for a, b in zip(values, limited)):
                return
            # A game or call may still be playing on speakers through the app mixer.
            if any(stream.sink == index and not stream.corked for stream in pulse.sink_input_list()):
                return
            pulse.volume_set(speaker, type(speaker.volume)(original))
            return

    def update(self, pulse, found, default):
        key, sink = next(((key, s) for key, sinks in found.items() for s in sinks if s.name == default), (None, None))
        kind = output_kind(sink) if sink else ""
        if kind == "headphones":
            self.headphones = key
            self.deadline = 0
            self.restore(pulse, found, sink)
            return
        if self.headphones:
            connected = self.headphones in found or any(
                route(s.proplist, port.name) == self.headphones and port.available != "no"
                for sinks in found.values() for s in sinks for port in s.port_list)
            if connected and sink is None:
                return  # Default metadata can briefly disappear during route changes.
            self.headphones = None
            self.deadline = 0 if connected else time.monotonic() + 4
        if not self.deadline:
            return
        if time.monotonic() > self.deadline:
            self.deadline = 0
            return
        if sink is None:
            return
        self.deadline = 0
        if kind != "speaker":
            return
        original = list(sink.volume.values)
        peak = max(original, default=0)
        if peak > self.level:
            limited = [v * self.level / peak for v in original]
            pulse.volume_set(sink, type(sink.volume)(limited))
            self.lowered = key, sink.index, original, limited


def listening(config):
    return config["enabled"] or config.get("headphoneLimitEnabled", False)


def watch(config):
    if not listening(config):
        return 0
    import pulsectl
    ranked = [(d["key"], d["port"]) for d in config["devices"] if config["enabled"]]
    guard = SpeakerLimit(config.get("headphoneLimit", 20)) if config.get("headphoneLimitEnabled") else None
    with pulsectl.Pulse("Monet output preferences", connect=False) as pulse:
        pulse.connect(autospawn=False)
        changed, waiting = True, False
        topology = None
        watched_ports = set()
        def notice(event):
            nonlocal changed
            # Card changes include jack availability and audio profile changes.
            # Portless sink changes are usually volume or mute. A card also reports
            # its own route changes. Follow active ports as well for the speaker limit.
            if event.facility == "sink" and event.t == "change" and event.index not in watched_ports:
                return
            changed = True
            if waiting:
                raise pulsectl.PulseLoopStop()
        pulse.event_callback_set(notice)
        events = ("sink", "card", "server") if guard else ("sink", "card")
        pulse.event_mask_set(*events)
        while True:
            if not changed:
                waiting = True
                try:
                    pulse.event_listen()
                finally:
                    waiting = False
            # Coalesce device/port/profile notifications. Nothing wakes on a timer at idle.
            pulse.event_listen(timeout=0.12 if ranked else 0.025)
            changed = False
            sinks = pulse.sink_list()
            watched_ports = {s.index for s in sinks if s.port_list and (guard or s.card == 0xffffffff)}
            found = available(sinks)
            current = frozenset((key, s.index) for key, sinks in found.items() for s in sinks)
            top = next((found[key] for key in ranked if key in found), []) if current != topology else []
            topology = current
            if not top and not guard:
                continue
            default = pulse.server_info().default_sink_name
            try:
                if top:
                    sink = next((s for s in top if s.name == default), top[0])
                    # Record the choice even when policy is still settling after hotplug.
                    pulse.sink_default_set(sink)
                    if guard and sink.name != default:
                        default = pulse.server_info().default_sink_name
                if guard:
                    guard.update(pulse, found, default)
            except pulsectl.PulseIndexError:
                changed = True
                topology = None


def command(args, outputs):
    path = settings_path()
    if args == ["watch"]:
        import pulsectl
        try:
            return watch(read(path))
        except (pulsectl.PulseError, OSError, ValueError):
            return 1
    if args != ["get"] and not (len(args) == 2 and args[0] == "save"):
        return 2
    try:
        problem = ""
        if args[0] == "save":
            if len(args[1]) > 120000:
                raise ValueError("request size")
            request = json.loads(bytes.fromhex(args[1]))
            if not isinstance(request, dict):
                raise ValueError("request")
            problem = save(path, request, request.get("revision"))
        config = read(path)
        connected = []
        seen = set()
        for item in outputs():
            if not item.get("key") or item.get("none"):
                continue
            name = bytes.fromhex(item["key"]).decode()
            identity = route({"node.name": name}, item.get("port"))
            if identity and identity not in seen:
                seen.add(identity)
                connected.append(dict(key=identity[0], port=identity[1], name=item["name"]))
        data = dict(config, ok=not problem, problem=problem, revision=revision(config), connected=connected)
    except (OSError, ValueError, TypeError):
        data = dict(ok=False, problem="invalid")
    print(json.dumps(data))
    return 0 if data["ok"] else 1
