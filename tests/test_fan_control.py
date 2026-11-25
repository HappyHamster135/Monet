"""Fan telemetry, controller ownership and editing a curve in the native UI."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
from fan_control import Controller, Fan, Offline, TemperatureSensor, cooling_status, curve_points, hardware_fans
from tests.test_settings_feedback import QT


class Cooling(unittest.TestCase):
    def test_hwmon_labels_rpm_targets_and_sleeping_devices(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            chip = root / "hwmon0"
            chip.mkdir()
            for key, value in {"name": "thinkpad", "fan1_input": "0", "fan1_target": "900",
                               "pwm1_enable": "2", "fan2_input": "n/a", "fan2_label": "Case fan"}.items():
                (chip / key).write_text(value)
            first, second = hardware_fans(root)
            self.assertEqual((first.name, first.rpm, first.target_rpm, first.mode),
                             ("ThinkPad fan 1", 0, 900, "Automatic"))
            self.assertEqual((second.name, second.rpm, second.target_rpm), ("Case fan", None, None))
            power = chip / "device/power"
            power.mkdir(parents=True)
            (power / "runtime_status").write_text("suspended")
            self.assertEqual(hardware_fans(root), [])

    def test_untrusted_loopback_listener_receives_no_credentials(self):
        import socket
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(.1)
            api = Controller(listener.getsockname()[1], os.getuid() + 10)
            api.token = "fixture"
            with self.assertRaises(Offline):
                api.request("GET", "/devices")
            with self.assertRaises(TimeoutError):
                listener.accept()

    def test_daemon_channel_matches_physical_target_and_keeps_unmanaged_fans(self):
        class Api:
            def request(self, method, path):
                return {"devices": [{"uid": "chip", "status_history": [{"channels": [
                    {"name": "fan1", "rpm": 1100, "duty": 50}]}]}]}

        other = Fan("Other", 700, None, "", source=("/sys/devices/controller2", "fan1"))
        first = Fan("Case", 1200, 1150, "Automatic", source=("/sys/devices/controller1", "fan1"))
        labels = {("chip", "fan1"): ("Case fan", ["/sys/devices/controller1"])}
        shown, extra = cooling_status(Api(), labels, labels, [first, other])
        self.assertEqual((shown.name, shown.rpm, shown.target_rpm, shown.duty), ("Case fan", 1100, 1150, 50))
        self.assertEqual(extra, other)

    def test_curve_matches_sensor_capabilities(self):
        sensor = TemperatureSensor("CPU", 0, 95, 2, 3)
        self.assertEqual(curve_points([(30, 20), (80, 100)], sensor), [(30, 20), (80, 100)])
        for points in ([(20, 0)], [(10, 0), (20, 5), (30, 10), (40, 15)],
                       [(10, 20), (10, 30)], [(40, 20), (60, 0)], [(20, 0), (100, 100)],
                       [(20, 0), (float("nan"), 40)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                curve_points(points, sensor)


@unittest.skipUnless(QT, "requires Qt Widgets")
class FanWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_graph_drag_updates_the_point_and_preserves_adjacent_points(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QDialog
        from fan_page import CurveEditor
        key = ("chip", "CPU")
        sensor = TemperatureSensor("CPU", 0, 100, 2, 10)
        editor = CurveEditor({key: sensor}, {"name": "Quiet", "temp_source": {"device_uid": "chip", "temp_name": "CPU"}}, None)
        editor.show()
        QTest.qWait(50)
        self.assertEqual(editor.sensor.currentData(), key)
        graph = editor.plot
        old = editor.points()
        pt = graph.position(old[1], graph.bounds()).toPoint()
        QTest.mousePress(graph, Qt.LeftButton, pos=pt)
        QTest.mouseMove(graph, pt + QPoint(15, -10))
        QTest.mouseRelease(graph, Qt.LeftButton, pos=pt + QPoint(15, -10))
        result = editor.points()
        self.assertGreater(result[1][0], old[1][0])
        self.assertGreater(result[1][1], old[1][1])
        self.assertEqual((result[0], result[-1]), (old[0], old[-1]))
        editor.validate()
        self.assertEqual(editor.result(), QDialog.Accepted)

    def test_poll_does_not_block_clicks_or_replace_newer_state(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from fan_page import Fans
        started, release = threading.Event(), threading.Event()
        changes = []

        class Api:
            def catalog(self):
                return {("chip", "fan1"): ("Case", 20, 100)}, {}, {}, {}

            def settings(self, key):
                return {"speed_fixed": changes[-1]} if changes else {}

            def request(self, method, path):
                started.set()
                release.wait(3)
                return {"devices": []}

            def apply(self, key, kind, value):
                changes.append(value)

        page = Fans(Api(), lambda: [])
        def wait(check):
            until = time.monotonic() + 3
            while not check() and time.monotonic() < until:
                QTest.qWait(10)
            self.assertTrue(check())
        try:
            page.show()
            wait(started.is_set)
            page.mode.setCurrentIndex(page.mode.findData("fixed"))
            page.duty.setValue(70)
            self.assertTrue(page.apply.isEnabled())
            QTest.mouseClick(page.apply, Qt.LeftButton)
            wait(lambda: changes == [70] and not page.busy)
            page.hide()
            release.set()
            wait(lambda: not page.reading)
            self.assertFalse(page.poll.isActive())
        finally:
            release.set()
            page.close()

    def test_close_while_controller_is_responding(self):
        from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
        from PySide6.QtTest import QTest
        from fan_page import Fans
        started, release = threading.Event(), threading.Event()

        class SlowApi:
            def catalog(self):
                started.set()
                release.wait(3)
                return {}, {}, {}, {}

        page = Fans(SlowApi(), lambda: [])
        page.show()
        self.assertTrue(started.wait(2))
        page.close()
        page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        release.set()
        self.assertTrue(QThreadPool.globalInstance().waitForDone(3000))
        QTest.qWait(10)
