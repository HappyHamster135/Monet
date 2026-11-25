"""Local cooling telemetry and CoolerControl's per-channel API."""
import http.client
import json
import math
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from actions import tr


@dataclass(frozen=True)
class Fan:
    name: str
    rpm: int | None
    target_rpm: int | None
    mode: str
    duty: int | None = None
    source: tuple = ()


@dataclass(frozen=True)
class TemperatureSensor:
    name: str
    minimum: float
    maximum: float
    min_points: int
    max_points: int


def number(path):
    try:
        value = int(path.read_text().strip())
        return value if value >= 0 else None
    except (OSError, ValueError):
        return None


def hardware_fans(root=Path("/sys/class/hwmon")):
    fans = []
    for chip in sorted(root.glob("hwmon*")):
        try:
            chip_name = (chip / "name").read_text().strip()
            power = chip / "device/power/runtime_status"
            if power.is_file() and power.read_text().strip() == "suspended":
                continue
        except OSError:
            continue
        for source in sorted(chip.glob("fan[0-9]*_input")):
            channel = source.name.split("_")[0]
            index = channel[3:]
            if not index.isdecimal():
                continue
            label = {"thinkpad": "ThinkPad", "acpi_fan": "ACPI"}.get(chip_name, chip_name)
            try:
                name = (chip / (channel + "_label")).read_text().strip()
            except OSError:
                name = ""
            name = name or tr("{device} fan {number}").format(device=label, number=index)
            mode = number(chip / ("pwm" + index + "_enable"))
            control = ""
            if mode == 1:
                control = tr("Manual")
            elif mode is not None and mode >= 2:
                control = tr("Automatic")
            device = (chip / "device").resolve()
            fans.append(Fan(name, number(source), number(chip / (channel + "_target")), control,
                            source=(str(device), channel)))
    return fans


class ControllerError(Exception):
    pass


class AccessNeeded(ControllerError):
    pass


class Offline(ControllerError):
    pass


def local_server_sockets(port, client_port=0):
    # Native daemons have a listener. Rootful Podman can implement the same
    # published port entirely with DNAT, leaving no server socket on the host.
    endpoints = []
    for name, addresses in (("tcp", ("0" * 8, "0100007F")),
                            ("tcp6", ("0" * 32, "0000000000000000FFFF00000100007F"))):
        path = Path("/proc/net") / name
        if not path.exists():
            continue
        with path.open() as table:
            for line in table:
                fields = line.split()
                if len(fields) < 10 or fields[3] not in ("0A", "01"):
                    continue
                address, local = fields[1].split(":")
                if address not in addresses or int(local, 16) != port:
                    continue
                if fields[3] == "0A" or int(fields[2].split(":")[1], 16) == client_port:
                    endpoints.append(int(fields[7]))
    return endpoints


def system_port_forward(port):
    # Bazzite's system Quadlet publishes the daemon on loopback. Do not treat
    # a user's substitute listener at that port as the configured service.
    path = Path("/etc/containers/systemd/coolercontrol.container")
    try:
        info = path.stat()
        if info.st_uid or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
        lines = set(path.read_text().splitlines())
        return "[Container]" in lines and f"PublishPort=127.0.0.1:{port}:11987" in lines
    except OSError:
        return False


class Controller:
    def __init__(self, port=11987, owner=0):
        self.port = port
        self.owner = owner
        self.token = ""

    def request(self, method, path, data=None):
        # All routes are local, with no proxy, redirect following or automatic write retries.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            before = local_server_sockets(self.port)
            forwarded = not before and system_port_forward(self.port)
            if (not before and not forwarded) or any(uid != self.owner for uid in before):
                raise Offline(tr("The local cooling service is unavailable."))
            conn.connect()
            peers = local_server_sockets(self.port, conn.sock.getsockname()[1])
            if (not peers and not forwarded) or any(uid not in (0, self.owner) for uid in peers):
                raise Offline(tr("The local cooling service is unavailable."))
            headers = {"Accept": "application/json"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            body = None
            if data is not None:
                body = json.dumps(data, allow_nan=False).encode()
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            if response.status in (401, 403):
                raise AccessNeeded(tr("A CoolerControl access token with the appropriate permissions is required."))
            if not 200 <= response.status < 300:
                raise ControllerError(tr("CoolerControl returned HTTP {status}.").format(status=response.status))
            raw = response.read(2 ** 21 + 1)
            if len(raw) > 2 ** 21:
                raise ControllerError(tr("The cooling service returned too much data."))
            return json.loads(raw) if raw.strip() else None
        except (OSError, http.client.HTTPException) as err:
            raise Offline(tr("The cooling service connection was interrupted.")) from err
        finally:
            conn.close()

    def catalog(self):
        devices = self.request("GET", "/devices")["devices"]
        profiles = self.request("GET", "/profiles")["profiles"]
        fans, sensors, names = {}, {}, {}
        for device in devices:
            uid, name = device["uid"], device["name"]
            info = device.get("info") or {}
            for channel, values in info.get("channels", {}).items():
                label = name + " · " + (values.get("label") or channel)
                locations = (info.get("driver_info") or {}).get("locations") or []
                names[uid, channel] = (label, locations)
                options = values.get("speed_options")
                if options and options.get("fixed_enabled"):
                    fans[uid, channel] = (label,
                                          options["min_duty"], options["max_duty"])
            for channel, values in info.get("temps", {}).items():
                sensors[uid, channel] = TemperatureSensor(name + " · " + (values.get("label") or channel),
                        info["temp_min"], info["temp_max"], info["profile_min_length"], info["profile_max_length"])
        return fans, sensors, {p["uid"]: p for p in profiles}, names

    @staticmethod
    def route(key):
        uid, name = key
        return "/devices/" + quote(uid, safe="") + "/settings/" + quote(name, safe="")

    def settings(self, key):
        result = self.request("GET", "/devices/" + quote(key[0], safe="") + "/settings")
        return next((s for s in result["settings"] if s["channel_name"] == key[1]
                     and (s.get("speed_fixed") is not None or s.get("profile_uid"))), {})

    def apply(self, key, mode, value=None):
        path = self.route(key)
        if mode == "fixed":
            return self.request("PUT", path + "/manual", {"speed_fixed": value})
        if mode == "profile":
            return self.request("PUT", path + "/profile", {"profile_uid": value})
        if mode == "default":
            return self.request("PUT", path + "/reset")
        raise ValueError(mode)


def curve_points(points, sensor):
    if not sensor.min_points <= len(points) <= sensor.max_points:
        raise ValueError(tr("Use between {low} and {high} points.").format(low=sensor.min_points, high=sensor.max_points))
    previous = None
    for temp, speed in points:
        if not math.isfinite(temp) or not 0 <= speed <= 100:
            raise ValueError(tr("Each point needs a temperature and a speed from 0 to 100%."))
        if not sensor.minimum <= temp <= sensor.maximum:
            raise ValueError(tr("This sensor supports temperatures from {low} to {high} °C.").format(
                low=sensor.minimum, high=sensor.maximum))
        if previous and (temp <= previous[0] or speed < previous[1]):
            raise ValueError(tr("Temperatures must increase and fan speeds must stay level or rise."))
        previous = temp, speed
    return points


def cooling_status(controller, devices, names, hardware):
    rows = []
    local = {fan.source: fan for fan in hardware if fan.source}
    matched = set()
    for record in controller.request("GET", "/status")["devices"]:
        history = record.get("status_history") or []
        for channel in history[-1].get("channels", []) if history else ():
            uid, name = record["uid"], channel["name"]
            rpm = channel.get("rpm")
            if rpm is None and (uid, name) not in devices:
                continue
            label, locations = names.get((uid, name), (name, []))
            sensor = next((local[path, name] for path in locations if (path, name) in local), None)
            duty = channel.get("duty")
            if sensor:
                matched.add(sensor.source)
                if rpm is None:
                    rpm = sensor.rpm
            rows.append(Fan(label, rpm, sensor.target_rpm if sensor else None, sensor.mode if sensor else "",
                            round(duty) if duty is not None else None))
    return rows + [fan for fan in hardware if fan.source not in matched]
