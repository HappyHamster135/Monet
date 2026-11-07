"""Per-output usable bounds, signal lifecycle, and real two-screen Qt plumbing."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QRect, Signal
    from PySide6.QtGui import QGuiApplication, QScreen, QWindow
    from PySide6.QtTest import QSignalSpy, QTest
    QT = True
except ImportError: QT = False


if QT:
    class Screen(QObject):
        availableGeometryChanged = Signal(QRect); geometryChanged = Signal(QRect)
        def __init__(self, rect): super().__init__(); self.rect = QRect(rect); self.reads = 0
        def availableGeometry(self): self.reads += 1; return QRect(self.rect)
        def availableVirtualGeometry(self): raise AssertionError("The virtual desktop is not this output's usable area")
        def update(self, rect):
            self.rect = QRect(rect); self.availableGeometryChanged.emit(self.rect); self.geometryChanged.emit(self.rect)

    class Window(QObject):
        screenChanged = Signal(QScreen)
        def __init__(self, screen): super().__init__(); self.display = screen
        def screen(self): return self.display


@unittest.skipUnless(QT, "requires PySide6")
class WindowArea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        loader = importlib.machinery.SourceFileLoader("area_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader)); loader.exec_module(cls.games)

    def test_usable_rectangle_keeps_negative_origins_and_does_not_poll(self):
        screen = Screen(QRect(-1280, 24, 1280, 696)); window = Window(screen)
        area = self.games.WindowArea(); area.watch(window)
        self.assertEqual(area.geometry, QRect(-1280, 24, 1280, 696))
        self.assertEqual((area.width, area.height), (1280, 696))
        reads = screen.reads; spy = QSignalSpy(area.changed); QTest.qWait(100)
        self.assertEqual(screen.reads, reads); self.assertEqual(spy.count(), 0)
        screen.update(QRect(-1280, 48, 1280, 672))
        self.assertEqual(area.height, 672); self.assertEqual(spy.count(), 1)
        screen.update(screen.rect); self.assertEqual(spy.count(), 1)
        area.watch(None)

    def test_rewatch_disconnects_only_its_old_screen_and_keeps_last_valid_size(self):
        one = Screen(QRect(0, 0, 1920, 1040)); two = Screen(QRect(1920, 0, 1280, 680))
        first, second = Window(one), Window(two)
        unrelated = QSignalSpy(one.availableGeometryChanged)
        area = self.games.WindowArea(); area.watch(first); area.watch(first)
        area.watch(second); self.assertEqual(area.width, 1280)
        one.update(QRect(0, 0, 800, 560))
        self.assertEqual(unrelated.count(), 1); self.assertEqual(area.width, 1280)
        two.update(QRect()); self.assertEqual(area.geometry, QRect(1920, 0, 1280, 680))
        two.update(QRect(1920, 0, 1200, 660)); self.assertEqual(area.width, 1200)
        area.watch(None); two.update(QRect(1920, 0, 1000, 600)); self.assertEqual(area.width, 1200)

    def test_native_window_and_receiver_destruction_leave_no_stale_callbacks(self):
        window = QWindow(); area = self.games.WindowArea(); area.watch(window)
        self.assertEqual(area.geometry, window.screen().availableGeometry())
        window.destroyed.connect(lambda: None)
        window.deleteLater(); QTest.qWait(20)
        self.assertIsNone(area._window); self.assertIsNone(area._screen)
        other = QWindow(); area.watch(other); area.deleteLater(); QTest.qWait(20)
        other.show(); other.resize(300, 200); QTest.qWait(20); other.close(); other.deleteLater(); QTest.qWait(20)

    def test_destroyed_screen_and_receiver_do_not_leave_a_callback(self):
        screen = Screen(QRect(0, 32, 1280, 688)); window = Window(screen)
        area = self.games.WindowArea(); area.watch(window)
        screen.deleteLater(); QTest.qWait(20)
        self.assertIsNone(area._screen); self.assertEqual(area.geometry, QRect(0, 32, 1280, 688))
        replacement = Screen(QRect(0, 0, 1024, 728)); second = Window(replacement)
        area.watch(second); self.assertEqual(area.width, 1024)
        window.screenChanged.emit(None); self.assertEqual(area.width, 1024)
        area.deleteLater(); QTest.qWait(20)
        failures = []
        with patch.object(sys, "excepthook", side_effect=lambda *args: failures.append(args)):
            replacement.update(QRect(0, 0, 800, 560)); QTest.qWait(20)
        self.assertEqual(failures, [])


@unittest.skipUnless(QT and shutil.which("Xvfb"), "requires Qt and Xvfb")
class NativeScreens(unittest.TestCase):
    def test_settings_and_store_follow_two_native_screens(self):
        with tempfile.TemporaryDirectory(prefix="monet-two-screen-") as folder:
            result = subprocess.run([sys.executable, str(ROOT / "tests/fixtures/settings-navigation.py"), folder,
                                     "--module", "tests.native_window_area", "--two-screens", "--fonts", "10"],
                                    cwd=ROOT, capture_output=True, text=True, timeout=150)
            details = "\n".join(p.read_text() for p in Path(folder).glob("*/tests.log"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr + details)
            summary = json.loads((Path(folder) / "result.json").read_text())
            self.assertTrue(summary["ok"]); self.assertEqual(summary["checks"], 6)
