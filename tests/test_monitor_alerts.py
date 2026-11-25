"""Real kernel data formats, sustained alerts, service lifecycle and cooldowns."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
import monitor_alerts as alerts
from monitor_readings import Reading, Sampler, disk_space


class SystemReadings(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.proc = self.root / "proc"
        self.sys = self.root / "sys"
        self.sampler = Sampler(self.proc, self.sys)

    def put(self, path, value):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value)
        return dest

    def test_cpu_uses_two_fresh_samples_and_memory_uses_pressure(self):
        self.put("proc/stat", "cpu 20 0 20 60 0 0 0 0 9 0\n")
        self.assertEqual(self.sampler.sample({"cpu"}), [])
        self.put("proc/stat", "cpu 24 0 21 65 0 0 0 0 12 0\n")
        self.put("proc/pressure/memory", "some avg10=70\nfull avg10=2.43 avg60=0.03 total=20\n")
        result = self.sampler.sample({"cpu", "memory"})
        self.assertEqual([(r.kind, r.value) for r in result], [("cpu", 50), ("memory", 2.43)])
        self.put("proc/pressure/memory", "full avg10=nan\n")
        self.assertEqual(self.sampler.sample({"cpu", "memory"}), [])
        self.sampler.sample(set())
        self.assertEqual(self.sampler.sample({"cpu"}), [])

    def test_cpu_and_battery_sources_exclude_sleeping_devices_and_peripherals(self):
        for name, chip, temp in (("hwmon0", "coretemp", 87000), ("hwmon1", "k10temp", 94000), ("hwmon2", "nvme", 107000)):
            self.put(f"sys/class/hwmon/{name}/name", chip)
            self.put(f"sys/class/hwmon/{name}/temp1_input", str(temp))
        self.put("sys/class/hwmon/hwmon1/device/power/runtime_status", "suspended")
        for dev, scope in (("BAT0", "System"), ("mouse", "Device")):
            self.put(f"sys/class/power_supply/{dev}/type", "Battery")
            self.put(f"sys/class/power_supply/{dev}/scope", scope)
            self.put(f"sys/class/power_supply/{dev}/status", "Discharging")
            self.put(f"sys/class/power_supply/{dev}/capacity", "12")
            self.put(f"sys/class/power_supply/{dev}/temp", "425")
        readings = self.sampler.sample(set(alerts.LIMITS))
        self.assertEqual([(r.kind, r.value, r.device) for r in readings],
                         [("cpu-temp", 87, ""), ("battery-temp", 42.5, "BAT0"), ("battery", 12, "BAT0")])
        self.assertTrue(readings[2].discharging)
        self.put("sys/class/power_supply/BAT0/status", "Charging")
        self.assertFalse(self.sampler.sample({"battery"})[0].discharging)
        self.put("sys/class/power_supply/BAT0/present", "0")
        self.assertEqual(self.sampler.sample({"battery", "battery-temp"}), [])

    def test_multiple_batteries_share_a_capacity_weighted_charge_warning(self):
        for device, level, status in (("BAT0", 10, "Discharging"), ("BAT1", 100, "Full")):
            for field, value in (("type", "Battery"), ("capacity", str(level)), ("status", status)):
                self.put(f"sys/class/power_supply/{device}/{field}", value)
        self.put("sys/class/power_supply/BAT0/energy_full", "10000000")
        self.put("sys/class/power_supply/BAT1/charge_full", "2000000")
        self.put("sys/class/power_supply/BAT1/voltage_min_design", "10000000")
        pack, = self.sampler.sample({"battery"})
        self.assertEqual((pack.value, pack.discharging), (70, True))
        self.put("sys/class/power_supply/BAT1/status", "Charging")
        self.assertFalse(self.sampler.sample({"battery"})[0].discharging)

    def test_physical_temperature_and_battery_hwmon_fallback(self):
        self.put("sys/class/hwmon/hwmon0/name", "k10temp")
        self.put("sys/class/hwmon/hwmon0/temp1_input", "101000")
        self.put("sys/class/hwmon/hwmon0/temp2_input", "81000")
        self.put("sys/class/hwmon/hwmon0/temp2_label", "Tdie")
        self.put("sys/class/power_supply/BAT1/type", "Battery")
        self.put("sys/class/power_supply/BAT1/hwmon3/temp1_input", "39500")
        rows = self.sampler.sample({"cpu-temp", "battery-temp"})
        self.assertEqual([r.value for r in rows], [81, 39.5])

    def test_atomic_root_binds_and_external_disks(self):
        mountinfo = self.put("mountinfo", r"""4 1 0:1 / / ro - overlay composefs ro
5 1 0:2 /v /var rw - btrfs /dev/nvme0 rw
6 1 0:2 /h /var/home rw - btrfs /dev/nvme0 rw
7 1 8:0 / /run/media/me/Music\040drive rw - ext4 /dev/sdb1 rw
8 1 0:3 / /mnt/server rw - nfs host:/share rw
9 1 7:0 / /mnt/image rw - ext4 /dev/loop0 rw
""")
        def fs(path):
            self.assertIn(path, ("/var", "/var/home", "/run/media/me/Music drive"))
            return SimpleNamespace(f_fsid=2 if path.startswith("/var") else 3, f_frsize=4096, f_blocks=10**7, f_bavail=10**5)
        readings = list(disk_space(mountinfo, fs))
        self.assertEqual([(r.name, r.value) for r in readings], [("System disk", 1), ("Music drive", 1)])


class Alerts(unittest.TestCase):
    def test_peaks_missing_samples_sleep_and_changed_thresholds_reset_the_hold(self):
        history = alerts.AlertHistory()
        say = Mock(return_value=True)
        def step(at, value=None, threshold=90):
            rows = [Reading("cpu", value)] if value is not None else []
            history.check(rows, {"cpu": threshold}, 2, at, say)
        for at, val in [(0, 95), (4, 96), (8, 80), (12, 95), (16, None), (20, 95), (24, 95), (70, 95)]:
            step(at, val)
        for t in (74, 78, 82):
            step(t, 99, 98)
        say.assert_not_called()
        step(86, 99, 98)
        say.assert_called_once()
        step(90, 99, 98)
        say.assert_called_once()

    def test_charge_only_warns_while_discharging_disk_escalates_per_volume_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "history"
            history = alerts.AlertHistory(file)
            say = Mock(return_value=True)
            def step(at, percent, external=65, on_battery=False):
                rows = [Reading("disk", percent, "a", "System"), Reading("disk", external, "b", "Music"),
                        Reading("battery", 12, "BAT0", "BAT0", on_battery)]
                history.check(rows, {"disk": 10, "battery": 15}, 15, at, say)
            step(20, 9)
            self.assertEqual(say.call_count, 1)
            history = alerts.AlertHistory(file)
            step(22, 8)
            self.assertEqual(say.call_count, 1)
            step(30, 4, 8)
            self.assertEqual(say.call_count, 3)
            step(40, 3, 7, True)
            self.assertEqual(say.call_count, 4)
            step(45, 2, 7, True)
            self.assertEqual(say.call_count, 4)
            step(950, 2, 7, True)
            self.assertEqual(say.call_count, 5)
            step(6*3600+40, 3)
            self.assertEqual(say.call_count, 6)

    def test_failed_delivery_retries_with_backoff(self):
        history = alerts.AlertHistory()
        say = Mock(side_effect=[False, True])
        for t in (100, 104, 120, 159, 160, 161):
            history.check([Reading("disk", 2, "a", "Drive")], {"disk": 10}, 15, t, say)
        self.assertEqual(say.call_count, 2)

    def test_disabled_or_hidden_tool_does_not_sample_and_sync_stops_unit(self):
        settings = Mock()
        data = {"enabled": ["cpu", "bad", 4], "repeat": 0, "cpu": -1}
        settings.value.side_effect = lambda key, default: json.dumps(data if key == "monitorAlerts" else ["monitor-alerts"])
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_RUNTIME_DIR=folder):
            with patch.object(alerts.Sampler, "sample") as sample, patch("subprocess.run") as run:
                run.return_value.returncode = 0
                alerts.monitor(settings)
                sample.assert_not_called()
                alerts.reconcile(settings)
                self.assertIn("disable", run.call_args.args[0])
                settings.value.side_effect = lambda key, default: json.dumps(data if key == "monitorAlerts" else [])
                enabled, limits, repeat = alerts.preferences(settings)
                self.assertEqual((enabled, limits["cpu"], repeat), ({"cpu"}, 90, 15))
                alerts.reconcile(settings)
                self.assertIn("enable", run.call_args.args[0])
                run.return_value = subprocess.CompletedProcess([], 1, "", "manager unavailable")
                with self.assertRaisesRegex(RuntimeError, "manager unavailable"):
                    alerts.reconcile(settings)
