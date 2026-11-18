"""Native power policy in disposable profiles; never change the host power mode."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


class PowerProfiles(unittest.TestCase):
    def test_real_busctl_variants_are_unwrapped_in_one_snapshot(self):
        q = quick_helper()
        reply = [{"ActiveProfile": {"type": "s", "data": "balanced"}, "Profiles": {"type": "aa{sv}", "data": [
            {"Profile": {"type": "s", "data": value}} for value in ("power-saver", "balanced", "performance")]}}]
        with patch.object(q, "busjson", return_value=reply) as read:
            self.assertEqual(q.power_mode(), ("balanced", ["power-saver", "balanced", "performance"]))
        read.assert_called_once()
        self.assertIn("GetAll", read.call_args.args)

    def test_missing_service_and_old_service_name_are_supported(self):
        q = quick_helper()
        reply = [{"ActiveProfile": {"data": "power-saver"}, "Profiles": {"data": [{"Profile": {"data": "power-saver"}}]}}]
        with patch.object(q, "busjson", side_effect=[None, reply]):
            self.assertEqual(q.power_mode(), ("power-saver", ["power-saver"]))
        with patch.object(q, "busjson", return_value=None):
            self.assertEqual(q.power_mode(), ("", []))

    def test_invalid_inputs_do_not_read_write_or_contact_the_desktop(self):
        q = quick_helper()
        for values in ({"mode": "fast"}, {"saver": "yes"}, {"threshold": True}, {"threshold": 0}, {"threshold": 100}):
            with self.subTest(values=values), patch.object(q, "power_policy") as read, patch.object(q, "kwrite") as write:
                self.assertFalse(q.change_power_policy(**values)["ok"])
                read.assert_not_called(); write.assert_not_called()


@unittest.skipUnless(shutil.which("kreadconfig6") and shutil.which("kwriteconfig6"), "requires native KConfig")
class NativeBatteryPolicy(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name); self.config = self.root / "config"; self.config.mkdir()
        self.q = quick_helper()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.config), XDG_CONFIG_DIRS=str(self.root / "defaults"),
                         XDG_STATE_HOME=str(self.root / "state"), XDG_CACHE_HOME=str(self.root / "cache"))
        env.start(); self.addCleanup(env.stop)
        for name, value in (("power_mode", ("balanced", ["power-saver", "balanced", "performance"])),
                            ("reload_power", ""), ("has_battery", True), ("has_lid", True), ("virtual_machine", False)):
            mock = patch.object(self.q, name, return_value=value); mock.start(); self.addCleanup(mock.stop)

    def value(self, group, key="PowerProfile", default=""):
        return self.q.kread("powerdevilrc", group, key, default)

    def test_automatic_configures_native_charger_and_low_battery_transitions(self):
        result = self.q.set_power_mode("automatic")
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["mode"], "automatic")
        self.assertEqual(result["state"]["modes"], ["automatic", "power-saver", "performance"])
        for group, expected in (("AC", "balanced"), ("Battery", "balanced"), ("LowBattery", "power-saver")):
            self.assertEqual(self.value((group, "Performance")), expected)
        self.assertEqual(result["state"]["batterySaverThreshold"], 20)
        self.assertEqual(self.value("BatteryManagement", "BatteryLowLevel"), "20")
        self.q.reload_power.assert_called_once()

    def test_manual_choices_and_saver_preference_survive_later_changes(self):
        self.assertTrue(self.q.set_power_mode("performance")["ok"])
        self.assertTrue(self.q.change_power_policy(saver=False)["ok"])
        for group in ("AC", "Battery", "LowBattery"):
            self.assertEqual(self.value((group, "Performance")), "performance")
        self.assertTrue(self.q.set_power_mode("automatic")["ok"])
        self.assertFalse(self.q.power_policy()["batterySaverAuto"])
        self.assertEqual(self.value(("LowBattery", "Performance")), "balanced")
        self.assertTrue(self.q.change_power_policy(saver=True)["ok"])
        self.assertEqual(self.value(("LowBattery", "Performance")), "power-saver")

    def test_threshold_is_saved_without_changing_critical_sleep_or_display_settings(self):
        self.q.kwrite("powerdevilrc", "BatteryManagement", "BatteryCriticalLevel", "7")
        self.q.kwrite("powerdevilrc", "BatteryManagement", "BatteryCriticalAction", "2")
        self.q.kwrite("powerdevilrc", ("Battery", "Display"), "TurnOffDisplayIdleTimeoutSec", "600")
        self.assertTrue(self.q.change_power_policy(threshold=30)["ok"])
        self.assertEqual(self.value("BatteryManagement", "BatteryLowLevel"), "30")
        self.assertEqual(self.value("BatteryManagement", "BatteryCriticalLevel"), "7")
        self.assertEqual(self.value("BatteryManagement", "BatteryCriticalAction"), "2")
        self.assertEqual(self.value(("Battery", "Display"), "TurnOffDisplayIdleTimeoutSec"), "600")
        with patch.object(self.q, "kwrite") as write:
            self.assertEqual(self.q.change_power_policy(threshold=5)["problem"], "critical-level")
            write.assert_not_called()

    def test_changing_the_saver_preserves_distinct_native_ac_and_battery_preferences(self):
        for group, mode in (("AC", "performance"), ("Battery", "balanced")):
            self.q.kwrite("powerdevilrc", (group, "Performance"), "PowerProfile", mode)
        self.assertTrue(self.q.change_power_policy(saver=False)["ok"])
        self.assertEqual(self.value(("AC", "Performance")), "performance")
        self.assertEqual(self.value(("Battery", "Performance")), "balanced")
        self.assertEqual(self.value(("LowBattery", "Performance")), "balanced")

    def test_existing_manual_choice_is_recognized(self):
        for group in ("AC", "Battery"):
            self.q.kwrite("powerdevilrc", (group, "Performance"), "PowerProfile", "power-saver")
        self.assertEqual(self.q.power_policy()["mode"], "power-saver")

    def test_missing_profile_support_does_not_save_a_false_success(self):
        with patch.object(self.q, "power_mode", return_value=("", [])), patch.object(self.q, "kwrite") as write:
            self.assertFalse(self.q.set_power_mode("automatic")["ok"])
            write.assert_not_called()

    def test_locked_native_key_rolls_back_the_other_policy_writes(self):
        (self.config / "powerdevilrc").write_text("[Battery][Performance]\nPowerProfile[$i]=power-saver\n")
        result = self.q.set_power_mode("automatic")
        self.assertFalse(result["ok"])
        self.assertEqual(self.value(("AC", "Performance"), default="missing"), "missing")
        self.assertEqual(self.value(("Battery", "Performance")), "power-saver")
        self.assertEqual(self.value("Monet", "PowerMode", "missing"), "missing")

    def test_desktop_reload_failure_restores_the_previous_complete_policy(self):
        self.assertTrue(self.q.set_power_mode("performance")["ok"])
        before = self.q.power_policy()
        with patch.object(self.q, "reload_power", return_value=None):
            self.assertFalse(self.q.set_power_mode("automatic")["ok"])
        self.assertEqual(self.q.power_policy(), before)
        self.assertEqual(self.value(("LowBattery", "Performance")), "power-saver")

    def test_upgrade_defaults_use_the_real_native_profile_writer_and_keep_choices(self):
        # Run the exact new defaults from monet-look, with the real reversible writer.
        script = (ROOT / "linux/libexec/monet-look").read_text()
        start = script.index("# PowerDevil reacts to battery/charger events")
        last = "refreshStatus >/dev/null 2>&1 || true"
        end = script.index(last, start) + len(last)
        block = script[start:end]
        profile = self.root / "monet-profile"
        profile.write_text((ROOT / "linux/libexec/monet-profile").read_text().replace("@DATADIR@", str(ROOT / "linux/share")))
        profile.chmod(0o755)
        command = 'kw() { "' + str(profile) + '" put --default-only "$@"; };\nkw_default() { kw --file "$1" --group "$2" --key "$3" "$4"; };\n' + block
        result = subprocess.run(["bash", "-eu", "-c", command], capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.value("BatteryManagement", "BatteryLowLevel"), "20")
        self.assertEqual(self.value(("LowBattery", "Performance")), "power-saver")
        self.q.kwrite("powerdevilrc", ("AC", "Performance"), "PowerProfile", "performance")
        self.q.kwrite("powerdevilrc", "BatteryManagement", "BatteryLowLevel", "30")
        result = subprocess.run(["bash", "-eu", "-c", command], capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.value(("AC", "Performance")), "performance")
        self.assertEqual(self.value("BatteryManagement", "BatteryLowLevel"), "30")
