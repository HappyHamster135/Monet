"""A user's ranked playback routes. The listener sleeps until the audio graph changes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

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
    return dict(enabled=value["enabled"], devices=devices)


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
    new = validate(value)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (path.parent / ".output-order.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = read(path)
        if expected != revision(old):
            return "changed"
        if new == old:
            return ""
        write(path, new)
        if new["enabled"] or old["enabled"]:
            try:
                service(new["enabled"])
            except (OSError, subprocess.SubprocessError):
                write(path, old)
                try:
                    service(old["enabled"])
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


def watch(config):
    if not config["enabled"]:
        return 0
    import pulsectl
    ranked = [(d["key"], d["port"]) for d in config["devices"]]
    with pulsectl.Pulse("Monet output preferences", connect=False) as pulse:
        pulse.connect(autospawn=False, timeout=4)
        changed, waiting = True, False
        topology = None
        independent_ports = set()
        def notice(event):
            nonlocal changed
            # Card changes include jack availability and audio profile changes.
            # Portless sink changes are usually volume or mute. A card also reports
            # its own route changes. Only independent ports need sink change events.
            if event.facility == "sink" and event.t == "change" and event.index not in independent_ports:
                return
            changed = True
            if waiting:
                raise pulsectl.PulseLoopStop()
        pulse.event_callback_set(notice)
        pulse.event_mask_set("sink", "card")
        while True:
            if not changed:
                waiting = True
                try:
                    pulse.event_listen()
                finally:
                    waiting = False
            # Coalesce device/port/profile notifications. Nothing wakes on a timer at idle.
            pulse.event_listen(timeout=0.12)
            changed = False
            sinks = pulse.sink_list()
            independent_ports = {s.index for s in sinks if s.port_list and s.card == 0xffffffff}
            found = available(sinks)
            current = frozenset((key, s.index) for key, sinks in found.items() for s in sinks)
            if current == topology:
                continue
            topology = current
            top = next((found[key] for key in ranked if key in found), [])
            if top:
                default = pulse.server_info().default_sink_name
                sink = next((s for s in top if s.name == default), top[0])
                # Record the choice even when currently effective: policy may still
                # be settling after a hotplug. Leave per-stream assignments to PipeWire.
                try:
                    pulse.sink_default_set(sink)
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
