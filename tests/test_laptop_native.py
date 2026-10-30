"""Run real KDE/Qt components in private homes and D-Bus sessions."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KDE = (importlib.util.find_spec("PySide6") and shutil.which("dbus-run-session")
       and any(Path("/usr").glob("lib*/qt6/plugins/platformthemes/KDEPlasmaPlatformTheme6.so")))


@unittest.skipUnless(KDE, "KDE Plasma, Kvantum and PySide6 runtime")
class LaptopNative(unittest.TestCase):
    def run_fixture(self, name):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ("config", "data", "state", "cache", "runtime"):
                (root / folder).mkdir(mode=0o700)
            env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(root / "config"),
                       XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
                       DBUS_SYSTEM_BUS_ADDRESS="unix:path=/nonexistent",
                       QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="kde", XDG_CURRENT_DESKTOP="KDE")
            result = subprocess.run(["dbus-run-session", "--", "python3",
                                     str(ROOT / "tests/fixtures/laptop-native.py"), name],
                                    env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_manager_action_loads_and_launches_expected_helper(self):
        self.run_fixture("action")

    def test_open_widget_changes_between_mist_and_smoke(self):
        self.run_fixture("theme")

    def test_hardware_readings_distinguish_missing_values_from_idle_hardware(self):
        self.run_fixture("hardware")

    def test_performance_navigation_device_selection_and_pause(self):
        self.run_fixture("performance")

    def test_system_details_snapshot_refresh_navigation_and_lazy_readers(self):
        self.run_fixture("system")

    def test_native_table_wrappers_resolve_all_components(self):
        self.run_fixture("tables")

    def test_detached_faces_follow_the_displayed_contents_window(self):
        self.run_fixture("activity")

    def test_files_discovery_shortcuts_reveal_and_drive_removal(self):
        self.run_fixture("files")
