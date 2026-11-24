"""The desktop's opt-in Bluetooth policy must preserve manual radio choices."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "linux/share/monet/monet_runtime/bluetooth_sleep.py"
spec = importlib.util.spec_from_file_location("bluetooth_sleep", RUNTIME)
sleep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sleep)
ADDRESS = "00:11:22:33:44:55"


class BluetoothSleep(unittest.TestCase):
    def test_enable_failure_rolls_back_and_off_is_default(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_STATE_HOME=directory):
            config = Path(directory) / "mode"
            self.assertEqual(sleep.read_mode(config), "off")
            with patch.object(sleep, "service", side_effect=[OSError(), None]) as service:
                with self.assertRaises(OSError):
                    sleep.configure(config, "restore")
            self.assertEqual([call.args[0] for call in service.call_args_list], ["restore", "off"])
            self.assertFalse(config.exists())
            with patch.object(sleep, "service"):
                for mode in ("restore", "stay-off", "off"):
                    sleep.configure(config, mode)
                    self.assertEqual(sleep.read_mode(config), mode)

    def test_manual_power_and_block_take_precedence_over_pending_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            pending = Path(directory) / "pending"
            bus = Mock()
            bus.objects.return_value = ("owner", {"/hci0": {sleep.ADAPTER: {"Address": ADDRESS, "Powered": False}}})
            for choice in ("manual", "blocked", "expired"):
                sleep.store(pending, ADDRESS)
                p = sleep.SleepPolicy(bus, pending, lambda d: False, blocked=lambda _: choice == "blocked")
                if choice == "manual":
                    with patch.object(sleep, "pending_path", return_value=pending):
                        sleep.cancel_restore()
                if choice == "expired":
                    p.expire()
                p.restore()
                self.assertFalse(pending.exists())
                bus.power.assert_not_called()

    def test_both_desktop_radio_actions_cancel_recovery_before_writing_power(self):
        from tests.test_look import quick_helper
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_STATE_HOME=directory):
            quick = quick_helper()
            pending = sleep.pending_path()
            def run(*args, **kwargs):
                self.assertFalse(pending.exists())
                return ""
            with patch.object(quick, "run", side_effect=run) as command, patch.object(quick, "bluetooth_state", return_value=False):
                sleep.store(pending, ADDRESS)
                self.assertTrue(quick.quick_options(["bluetooth", "off"])["ok"])
                command.assert_called_with("bluetoothctl", "power", "off", timeout=5)
                sleep.store(pending, ADDRESS)
                quick.main(["bluetooth", "on"])
                command.assert_called_with("bluetoothctl", "power", "on", timeout=5)

    def test_prepare_releases_inhibitor_if_state_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "choice"
            sleep.store(path, "restore")
            worker = sleep.SleepWatcher(Mock(), Mock(), path)
            read_fd, worker.lock_fd = os.pipe2(os.O_NONBLOCK)
            try:
                worker.policy.prepare.side_effect = OSError("test journal unavailable")
                message = Mock()
                message.unpack.return_value = (True,)
                with patch("sys.stderr"):
                    worker.preparing(None, None, None, None, None, message)
                self.assertEqual(os.read(read_fd, 1), b"")
            finally:
                worker.unlock()
                os.close(read_fd)

    def test_rfkill_on_this_adapter_or_platform_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "rfkill3"
            entry.mkdir()
            for key, value in {"type": "bluetooth", "name": "hci0", "soft": "1", "hard": "0"}.items():
                (entry / key).write_text(value)
            self.assertFalse(sleep.rfkill_blocked("/org/bluez/hci1", root))
            self.assertTrue(sleep.rfkill_blocked("/org/bluez/hci0", root))
            (entry / "name").write_text("platform-bluetooth")
            self.assertTrue(sleep.rfkill_blocked("/org/bluez/hci1", root))


@unittest.skipUnless(importlib.util.find_spec("gi") and importlib.util.find_spec("dbus"), "requires GLib and dbus-python")
class SleepBus(unittest.TestCase):
    def cycle(self, mode, inactive=False, interrupted=False):
        with private_session() as env:
            env["DBUS_SYSTEM_BUS_ADDRESS"] = env["DBUS_SESSION_BUS_ADDRESS"]
            runtime = Path(env["XDG_RUNTIME_DIR"])
            self.assertTrue(env["DBUS_SYSTEM_BUS_ADDRESS"].startswith("unix:path=" + str(runtime / "bus")))
            events = runtime / "events"
            def wait_for(predicate):
                end = time.monotonic() + 4
                while time.monotonic() < end and not predicate():
                    time.sleep(.02)
                self.assertTrue(predicate(), events.read_text() if events.exists() else "fixture did not start")

            def action(name):
                return subprocess.check_output(["gdbus", "call", "--session", "--dest", sleep.LOGIN,
                    "--object-path", sleep.LOGIN_PATH, "--method", "org.monet.Test.Action", name],
                    env=env, text=True, timeout=3).strip()

            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
                env["NOTIFY_SOCKET"] = str(runtime / "ready")
                notify.bind(env["NOTIFY_SOCKET"])
                notify.settimeout(4)
                config = Path(env["XDG_CONFIG_HOME"]) / "monet/bluetooth-sleep"
                sleep.store(config, mode)
                def start_watcher():
                    shared = Path(os.environ.get("MONET_SLEEP_TEST_RUNTIME", RUNTIME))
                    helpers = Path(os.environ.get("MONET_SLEEP_TEST_HELPERS", ROOT / "linux/libexec"))
                    proc = subprocess.Popen([sys.executable, "-B", shared, "watch", helpers], env=env)
                    self.addCleanup(lambda: proc.poll() is None and (proc.kill(), proc.wait()))
                    self.assertEqual(notify.recv(64), b"READY=1")
                    return proc

                with subprocess.Popen([sys.executable, ROOT / "tests/fixtures/bluetooth-sleep-bus.py", events], env=env) as fake:
                    try:
                        wait_for(lambda: events.exists())
                        proc = start_watcher()
                        if inactive:
                            action("background")
                        self.assertIn("no", action("released"))
                        action("sleep")
                        wait_for(lambda: "yes" in action("released"))
                        before = events.read_text().splitlines()
                        self.assertEqual(before, ["ready", "inhibit"] + ([] if inactive else ["/org/bluez/hci12 0"]))
                        if interrupted:
                            proc.kill()
                            proc.wait()
                        action("replug")
                        action("wake")
                        if interrupted:
                            proc = start_watcher()
                        wait_for(lambda: events.read_text().count("inhibit") == 2)
                        expected = before + ["inhibit"]
                        if mode == "restore" and not inactive:
                            expected.append("/org/bluez/hci13 1")
                            if not interrupted:
                                expected.append("connect /org/bluez/hci13/dev_1")
                        wait_for(lambda: len(events.read_text().splitlines()) >= len(expected))
                        self.assertEqual(events.read_text().splitlines(), expected)
                        self.assertIn("no", action("released"))
                        proc.terminate()
                        self.assertEqual(proc.wait(timeout=3), 0)
                        self.assertFalse((Path(env["XDG_STATE_HOME"])/"monet/bluetooth-restore").exists())
                    finally:
                        fake.terminate()

    def test_only_restore_previously_powered_adapter_and_its_connected_input(self):
        self.cycle("restore")

    def test_stay_off(self):
        self.cycle("stay-off")

    def test_background_session_leaves_radios_alone(self):
        self.cycle("restore", inactive=True)

    def test_interrupted_worker_recovers_record_after_path_change(self):
        self.cycle("restore", interrupted=True)
