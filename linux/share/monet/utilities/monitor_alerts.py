"""Opt-in system notifications for the current desktop session."""
import fcntl
import json
import math
from html import escape
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from actions import stored, tr
from monitor_readings import Sampler


UNIT = "monet-monitor-alerts.service"
LIMITS = {"cpu": (50, 100, 90), "cpu-temp": (70, 105, 90), "battery-temp": (30, 50, 40),
          "memory": (10, 10, 10), "disk": (5, 30, 10), "battery": (5, 50, 15)}
NAMES = {"cpu": tr("High CPU usage"), "cpu-temp": tr("High CPU temperature"),
         "battery-temp": tr("High battery temperature"), "memory": tr("High memory pressure"),
         "disk": tr("Low disk space"), "battery": tr("Low battery charge")}
REPEATS = (2, 5, 15, 30, 60)
FAST = {"cpu", "cpu-temp", "battery-temp", "memory"}
INTERVAL = 4
HOLD = 12


def preferences(settings):
    settings.sync()
    data = stored(settings, "monitorAlerts", {})
    raw = data.get("enabled")
    enabled = set(k for k in raw if isinstance(k, str) and k in LIMITS) if isinstance(raw, list) else set()
    limits = {}
    for key, (low, high, default) in LIMITS.items():
        value = data.get(key)
        limits[key] = value if type(value) is int and low <= value <= high else default
    repeat = data.get("repeat")
    return enabled, limits, repeat if type(repeat) is int and repeat in REPEATS else 15


def visible(settings):
    return "monitor-alerts" not in stored(settings, "hidden", [])


def description(reading):
    percent = round(reading.value)
    if reading.kind == "cpu":
        return tr("CPU usage has stayed near {percent}%.").format(percent=percent)
    if reading.kind in {"cpu-temp", "battery-temp"}:
        return tr("{sensor} has stayed near {degrees} °C.").format(sensor=reading.name or tr("CPU"), degrees=percent)
    if reading.kind == "memory":
        return tr("Tasks are stalling while the system waits for memory.")
    if reading.kind == "disk":
        return tr("{disk} has {percent}% free.").format(disk=reading.name, percent=f"{reading.value:.1f}")
    return tr("{battery} has {percent}% charge and is discharging.").format(battery=reading.name, percent=percent)


class AlertHistory:
    def __init__(self, runtime_file=None):
        self.above = {}
        self.sent = {}
        self.retry = {}
        self.runtime_file = runtime_file
        if runtime_file:
            try:
                for kind, device, when, critical in json.loads(runtime_file.read_bytes()):
                    if kind in LIMITS and isinstance(device, str) and type(when) in (float, int) and math.isfinite(when):
                        self.sent[(kind, device)] = (when, critical is True)
            except (OSError, TypeError, ValueError):
                pass

    def remember(self):
        if self.runtime_file:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.runtime_file.parent, delete=False) as temp:
                json.dump([[*key, *value] for key, value in self.sent.items()], temp)
            os.replace(temp.name, self.runtime_file)

    def check(self, readings, limits, repeat, now, notify):
        active = {}
        delivered = False
        for r in readings:
            if r.kind not in limits:
                continue
            key = (r.kind, r.device)
            limit = limits[r.kind]
            if r.kind == "disk":
                reached = r.value < limit
            elif r.kind == "battery":
                reached = r.discharging and r.value <= limit
            else:
                reached = r.value >= limit
            if not reached:
                continue
            start, previous, old_limit = self.above.get(key, (now, now, limit))
            if limit != old_limit or now - previous > 2 * INTERVAL:
                start = now
            active[key] = (start, now, limit)
            if r.kind in FAST and now - start < HOLD:
                continue
            critical = r.kind == "disk" and r.value < limit / 2
            last = self.sent.get(key)
            cooldown = 6 * 3600 if r.kind == "disk" else repeat * 60
            if last and now - last[0] < cooldown and not (critical and not last[1]):
                continue
            if now < self.retry.get(key, 0):
                continue
            if notify(NAMES[r.kind], description(r)):
                delivered = True
                self.sent[key] = (now, critical)
                self.retry.pop(key, None)
            else:
                self.retry[key] = now + 60
        self.above = active
        self.sent = {k: v for k, v in self.sent.items() if now - v[0] < 6 * 3600}
        self.retry = {k: v for k, v in self.retry.items() if now < v}
        if delivered:
            try:
                self.remember()
            except OSError:
                # A full runtime directory must not restart the service and
                # lose the cooldowns it still holds in memory.
                pass


def notify(title, body):
    # Normal urgency allows Plasma to honor Do Not Disturb and per-app preferences.
    try:
        reply = subprocess.run(["notify-send", "--app-name", tr("Monet Utilities"), "--icon", "utilities-system-monitor",
                                "--hint=string:desktop-entry:monet-utilities", "--", title, escape(body)],
                               capture_output=True, timeout=5)
        return reply.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def reconcile(settings):
    # Several UI changes can finish out of order. Read the latest saved state
    # while holding the lock so the last action always wins.
    lock = Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-monitor-alerts.lock"
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        enabled, _, _ = preferences(settings)
        command = "enable" if enabled and visible(settings) else "disable"
        result = subprocess.run(["systemctl", "--user", command, "--now", UNIT],
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or tr("Could not update the system alert service."))


def monitor(settings):
    sampler = Sampler()
    history = AlertHistory(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-monitor-alert-history.json")
    last = None
    slow_read = {}
    while True:
        enabled, limits, repeat = preferences(settings)
        if not enabled or not visible(settings):
            return
        now = time.clock_gettime(time.CLOCK_BOOTTIME)
        if last is not None and now - last > 2 * INTERVAL:
            sampler.ticks = None
            history.above.clear()
        last = now
        fresh = enabled & FAST
        # Recheck preferences promptly but avoid reading disks and battery
        # charge at CPU sampling frequency.
        for kind in ("disk", "battery"):
            if kind not in enabled:
                slow_read.pop(kind, None)
            elif kind not in slow_read or now - slow_read[kind][0] >= 30 or slow_read[kind][1] != limits[kind]:
                fresh.add(kind)
                slow_read[kind] = (now, limits[kind])
        readings = sampler.sample(fresh)
        history.check(readings, limits, repeat, now, notify)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    from PySide6.QtCore import QSettings
    settings = QSettings("Monet", "Utilities")
    try:
        if sys.argv[1:] == ["sync"]:
            reconcile(settings)
        elif sys.argv[1:] == ["watch"]:
            monitor(settings)
        else:
            sys.exit(2)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
