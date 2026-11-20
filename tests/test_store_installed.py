"""Slow or failed Flatpak listings must not freeze the Store or erase its state."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_store_downloads import APP, jobs, store

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer, Signal
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


class InstalledQuery(unittest.TestCase):
    def test_a_successful_empty_listing_is_distinct_from_query_failure(self):
        self.assertEqual(store.installed_apps(lambda _: "", strict=True), {})
        errors = [OSError("missing executable"), subprocess.TimeoutExpired("flatpak", 30),
                  subprocess.CalledProcessError(1, "flatpak", output="org.example.Paint\tuser\n")]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(subprocess, "run", side_effect=error):
                with self.assertRaises(type(error)):
                    store.installed_apps(strict=True)
                self.assertEqual(store.installed_apps(), {})

    def test_flatpak_nonzero_status_is_checked_and_the_query_is_bounded(self):
        result = SimpleNamespace(stdout="org.example.Paint\tuser\n")
        with patch.object(subprocess, "run", return_value=result) as run:
            self.assertEqual(store.installed_apps(strict=True), {APP["id"]: "user"})
        run.assert_called_once_with(["flatpak", "list", "--app", "--columns=application,installation"],
                                    capture_output=True, text=True, timeout=30, check=True)


if QT:
    class QuietQueue(QObject):
        changed = Signal(object)
        problem = Signal(str)

        def poll(self): pass


@unittest.skipUnless(QT and os.name != "nt", "native Qt/Linux Store")
class InstalledRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="monet-installed-")
        self.events, self.threads = [], []
        fake_jobs = SimpleNamespace(ACTIVE=jobs.ACTIVE, Queue=lambda: jobs.Queue(Path(self.tmp.name)),
                                    watch_queue=lambda queue, parent: QuietQueue(parent))
        with patch.object(store, "jobs_module", return_value=fake_jobs):
            self.shop = store.shop_type(SimpleNamespace(startup_event=lambda *a: None))(None)

    def tearDown(self):
        for event in self.events: event.set()
        for thread in self.threads: thread.join(2)
        self.until(lambda: not self.shop.installed_running)
        self.shop.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.tmp.cleanup()

    def event(self):
        event = threading.Event()
        self.events.append(event)
        return event

    def until(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "Store did not settle")

    def job(self, state="running", **values):
        return dict(token="a" * 32, id=APP["id"], state=state, action="install", installation="user", **values)

    def test_completion_keeps_the_ui_alive_and_the_new_app_usable(self):
        entered, release = self.event(), self.event()
        reads, applied, beats = [], [], []
        main_thread = threading.get_ident()

        def read(**kwargs):
            reads.append(threading.get_ident())
            entered.set()
            release.wait(3)
            return {APP["id"]: "user", "org.example.Existing": "system"}

        self.shop.installedChanged.connect(lambda: applied.append(threading.get_ident()))
        timer = QTimer(self.shop)
        timer.setInterval(10)
        timer.timeout.connect(lambda: beats.append(True))
        timer.start()
        with patch.object(store, "installed_apps", side_effect=read):
            self.shop.jobs_changed([self.job()])
            self.shop.jobs_changed([self.job("done")])
            self.until(entered.is_set)
            QTest.qWait(150)
            self.assertGreaterEqual(len(beats), 3)
            self.assertEqual(self.shop.state(APP["id"]), "installed")
            self.assertEqual(applied, [])
            self.assertNotEqual(reads, [main_thread])
            release.set()
            self.until(lambda: not self.shop.installed_running)
        self.assertEqual(applied, [main_thread])
        timer.stop()

    def test_progress_is_quiet_and_completion_bursts_coalesce_without_publishing_stale_results(self):
        first, second, release_first, release_second = [self.event() for _ in range(4)]
        reads, published = [], []

        def read(**kwargs):
            reads.append(True)
            if len(reads) == 1:
                first.set(); release_first.wait(3)
                return {"org.example.Stale": "system"}
            second.set(); release_second.wait(3)
            return {"org.example.Latest": "user"}

        self.shop.installed = {"org.example.Kept": "user"}
        self.shop.installedChanged.connect(lambda: published.append(dict(self.shop.installed)))
        with patch.object(store, "installed_apps", side_effect=read):
            for n in range(30): self.shop.jobs_changed([self.job(progress=n / 30)])
            self.assertEqual(reads, [])
            self.shop.refresh_installed()
            self.until(first.is_set)
            for _ in range(20): self.shop.refresh_installed()
            self.assertEqual(len(reads), 1)
            release_first.set()
            self.until(second.is_set)
            self.assertEqual(published, [])
            self.assertEqual(self.shop.installed, {"org.example.Kept": "user"})
            release_second.set()
            self.until(lambda: not self.shop.installed_running)
        self.assertEqual(len(reads), 2)
        self.assertEqual(published, [{"org.example.Latest": "user"}])
        QTest.qWait(120)
        self.assertEqual(len(reads), 2)  # No idle polling or automatic retry loop.

    def test_failed_listing_keeps_known_apps_and_a_later_refresh_can_recover(self):
        self.shop.installed = {APP["id"]: "system"}
        for error in (OSError("missing flatpak"), subprocess.CalledProcessError(1, "flatpak"),
                      subprocess.TimeoutExpired("flatpak", 30)):
            with patch.object(store, "installed_apps", side_effect=error):
                self.shop.refresh_installed()
                self.until(lambda: not self.shop.installed_running)
            self.assertEqual(self.shop.installed, {APP["id"]: "system"})
        with patch.object(store, "installed_apps", return_value={}):
            self.shop.refresh_installed()
            self.until(lambda: not self.shop.installed_running)
        self.assertEqual(self.shop.installed, {})

    def test_slow_initial_catalog_cannot_undo_a_newer_install(self):
        entered, release = self.event(), self.event()
        directory = Path(self.tmp.name) / "catalog"
        directory.mkdir()
        (directory / "appstream.xml").touch()
        reads = []

        def read(**kwargs):
            reads.append(True)
            if len(reads) == 1:
                entered.set(); release.wait(3)
                return {"org.example.Old": "system"}
            return {APP["id"]: "user"}

        with patch.object(store, "installed_apps", side_effect=read), \
                patch.object(store, "CATALOGS", (directory,)), \
                patch.object(store, "cached_catalog", return_value={}), \
                patch.object(store, "popular", return_value={}):
            thread = threading.Thread(target=self.shop.load, daemon=True)
            self.threads.append(thread)
            thread.start()
            self.until(entered.is_set)
            self.shop.jobs_changed([self.job()])
            self.shop.jobs_changed([self.job("done")])
            self.until(lambda: not self.shop.installed_running)
            self.assertEqual(self.shop.installed, {APP["id"]: "user"})
            release.set()
            self.until(lambda: self.shop.ready)
            thread.join(2)
        self.assertEqual(self.shop.installed, {APP["id"]: "user"})

    def test_confirmed_removal_is_immediate_but_old_history_is_not_replayed(self):
        with patch.object(store, "installed_apps", return_value={APP["id"]: "user"}):
            self.shop.jobs_changed([dict(self.job("done"), action="remove")])
            self.until(lambda: not self.shop.installed_running)
        self.assertEqual(self.shop.installed, {APP["id"]: "user"})
        with patch.object(store, "installed_apps", side_effect=OSError("offline")):
            self.shop.jobs_changed([dict(self.job(), action="remove")])
            self.shop.jobs_changed([dict(self.job("done"), action="remove")])
            self.assertEqual(self.shop.state(APP["id"]), "get")
            self.until(lambda: not self.shop.installed_running)
        self.assertEqual(self.shop.installed, {})
