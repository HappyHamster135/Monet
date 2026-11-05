"""Run real KDE/Qt components in private homes and D-Bus sessions."""
import importlib.util
import os
from pathlib import Path
import shutil
import signal
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
            # Native widgets do not need desktop service activation. In a host
            # run it could otherwise mount a document portal inside this temp
            # home, leaving a disconnected FUSE mount during cleanup.
            bus_config = root / "bus.conf"
            bus_config.write_text('<busconfig><type>session</type><auth>EXTERNAL</auth>'
                '<listen>unix:path=' + str(root / 'runtime/bus') + '</listen>'
                '<policy context="default"><allow send_destination="*"/>'
                '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
            env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(root / "config"),
                       XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
                       DBUS_SYSTEM_BUS_ADDRESS="unix:path=/nonexistent",
                       QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="kde", XDG_CURRENT_DESKTOP="KDE")
            # KDE may activate private-bus descendants which inherit stdout.
            # Wait for the fixture itself, not for every inherited pipe to close.
            output = root / "fixture.log"
            with output.open("w") as log:
                process = subprocess.Popen(["dbus-run-session", "--config-file=" + str(bus_config), "--", "python3",
                    str(ROOT / "tests/fixtures/laptop-native.py"), name],
                    env=env, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
                try:
                    code = process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    self.fail("Native fixture timed out: " + output.read_text())
                finally:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait(timeout=5)
            self.assertEqual(code, 0, output.read_text())

    def test_task_manager_action_loads_and_launches_expected_helper(self):
        self.run_fixture("action")

    def test_open_widget_changes_between_mist_and_smoke(self):
        self.run_fixture("theme")

    def test_hardware_readings_distinguish_missing_values_from_idle_hardware(self):
        self.run_fixture("hardware")

    def test_performance_navigation_device_selection_and_pause(self):
        self.run_fixture("performance")

    def test_performance_history_draws_early_and_keeps_only_the_last_minute(self):
        self.run_fixture("performance-history")

    @unittest.skipUnless(shutil.which("Xvfb"), "Xvfb for native chart rendering")
    def test_performance_history_renders_single_points_and_short_lines(self):
        self.run_fixture("performance-history-render")

    def test_startup_apps_add_toggle_search_failure_and_hidden_idle(self):
        self.run_fixture("startup")

    def test_system_details_snapshot_refresh_navigation_and_lazy_readers(self):
        self.run_fixture("system")

    def test_native_table_wrappers_resolve_all_components(self):
        self.run_fixture("tables")

    def test_detached_faces_follow_the_displayed_contents_window(self):
        self.run_fixture("activity")

    def test_files_discovery_shortcuts_reveal_and_drive_removal(self):
        self.run_fixture("files")
