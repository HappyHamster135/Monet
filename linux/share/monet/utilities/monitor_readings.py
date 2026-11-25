"""Read only selected Linux metrics. Missing devices supply no reading."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re

from actions import tr


@dataclass(frozen=True)
class Reading:
    kind: str
    value: float
    device: str = ""
    name: str = ""
    discharging: bool = False


def read(path):
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def number(path, divisor=1):
    try:
        return int(read(path)) / divisor
    except (ValueError, OverflowError):
        return None


def cpu_time(proc):
    try:
        with (proc / "stat").open() as stream:
            row = stream.readline().split()
        if row[:1] == ["cpu"] and len(row) >= 5:
            ticks = list(map(int, row[1:9]))  # guest ticks are already included in user and nice
            return sum(ticks), sum(ticks[3:5])
    except (OSError, ValueError):
        pass
    return None


def cpu_temperature(sysroot):
    values = []
    for chip in (sysroot / "class/hwmon").glob("hwmon*"):
        driver = read(chip / "name")
        if driver not in {"coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu_thermal_zone"}:
            continue
        if read(chip / "device/power/runtime_status") == "suspended":
            continue
        # Intel exposes the package at temp1. AMD may report both Tctl
        # (a cooling control value) and Tdie (the measured temperature).
        preferred = chip / "temp1_input"
        if driver in {"k10temp", "zenpower"}:
            for label in chip.glob("temp*_label"):
                if read(label) == "Tdie":
                    preferred = label.with_name(label.name.replace("_label", "_input"))
                    break
        value = number(preferred, 1000)
        if value is not None and 0 < value <= 150:
            values.append(value)
            continue
        for sensor in chip.glob("temp*_input"):
            value = number(sensor, 1000)
            if value is not None and 0 < value <= 150:
                values.append(value)
    if not values:
        for zone in (sysroot / "class/thermal").glob("thermal_zone*"):
            if read(zone / "type") in {"x86_pkg_temp", "cpu-thermal", "cpu_thermal", "soc-thermal"}:
                value = number(zone / "temp", 1000)
                if value is not None and 0 < value <= 150:
                    values.append(value)
    return max(values, default=None)


def batteries(sysroot, kinds):
    packs = [dev for dev in (sysroot / "class/power_supply").glob("*")
             if read(dev / "type") == "Battery" and read(dev / "scope") != "Device" and read(dev / "present") != "0"]
    levels = []
    full_energy = []
    charging = False
    for device in packs:
        name = tr("Battery") if len(packs) == 1 else device.name
        if "battery" in kinds:
            percent = number(device / "capacity")
            if percent is not None and 0 <= percent <= 100:
                status = read(device / "status")
                charging |= status == "Charging"
                levels.append(Reading("battery", percent, device.name, name, status == "Discharging"))
                if len(packs) > 1:
                    full = number(device / "energy_full")
                    if not full:
                        charge = number(device / "charge_full") or 0
                        volts = number(device / "voltage_min_design", 1_000_000) or 0
                        full = charge * volts
                    full_energy.append(full)
        if "battery-temp" in kinds:
            degrees = number(device / "temp", 10)
            if degrees is None:
                for hw in device.glob("hwmon*/temp1_input"):
                    degrees = number(hw, 1000)
                    if degrees is not None:
                        break
            if degrees is not None and -40 <= degrees <= 100:
                yield Reading("battery-temp", degrees, device.name, name)

    if len(levels) > 1 and len(levels) == len(packs) and all(w > 0 for w in full_energy):
        charge = sum(r.value * weight for r, weight in zip(levels, full_energy)) / sum(full_energy)
        yield Reading("battery", charge, "system", tr("Battery"), not charging and any(r.discharging for r in levels))
    else:
        yield from levels


def memory_pressure(proc):
    # PSI full measures the fraction of time every runnable task was stalled
    # reclaiming memory. Filesystem cache occupying RAM does not imply pressure.
    for line in read(proc / "pressure/memory").splitlines():
        fields = line.split()
        if fields[:1] == ["full"]:
            for field in fields[1:]:
                if field.startswith("avg10="):
                    try:
                        percent = float(field[6:])
                        if math.isfinite(percent) and 0 <= percent <= 100:
                            return percent
                    except ValueError:
                        pass
    return None


def disk_space(mountinfo, statvfs=os.statvfs):
    mounts = {}
    for line in read(mountinfo).splitlines():
        mount, _, filesystem = line.partition(" - ")
        left, right = mount.split(), filesystem.split()
        if len(left) < 6 or len(right) < 2 or "rw" not in left[5].split(","):
            continue
        if not right[1].startswith("/dev/") or right[1].startswith("/dev/loop"):
            continue
        path = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), left[4])
        if path in {"/", "/var", "/home", "/var/home"} or path.startswith(("/mnt/", "/var/mnt/", "/media/", "/run/media/")):
            mounts[path] = right[1]
    seen = set()
    for path, source in sorted(mounts.items(), key=lambda pair: len(pair[0])):
        try:
            fs = statvfs(path)
        except OSError:
            continue
        identity = str(fs.f_fsid or source)
        if identity in seen or fs.f_blocks * fs.f_frsize < 10_000_000_000:
            continue
        seen.add(identity)
        name = Path(path).name
        if path in {"/", "/var"}:
            name = tr("System disk")
        elif path in {"/home", "/var/home"}:
            name = tr("Home folder")
        yield Reading("disk", 100 * fs.f_bavail / fs.f_blocks, identity, name)


class Sampler:
    def __init__(self, proc=Path("/proc"), sysroot=Path("/sys")):
        self.proc = proc
        self.sysroot = sysroot
        self.ticks = None

    def sample(self, kinds):
        readings = []
        if "cpu" in kinds:
            old, self.ticks = self.ticks, cpu_time(self.proc)
            if old and self.ticks:
                total, idle = (current - prev for current, prev in zip(self.ticks, old))
                if total > 0 and 0 <= idle <= total:
                    readings.append(Reading("cpu", 100 * (total - idle) / total))
        else:
            self.ticks = None
        if "cpu-temp" in kinds:
            value = cpu_temperature(self.sysroot)
            if value is not None:
                readings.append(Reading("cpu-temp", value))
        if "memory" in kinds:
            value = memory_pressure(self.proc)
            if value is not None:
                readings.append(Reading("memory", value))
        if kinds & {"battery", "battery-temp"}:
            readings.extend(batteries(self.sysroot, kinds))
        if "disk" in kinds:
            readings.extend(disk_space(self.proc / "self/mountinfo"))
        return readings
