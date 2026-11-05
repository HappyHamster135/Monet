"""Real filesystem events keep the Store quiet without losing worker recovery."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_store_downloads import APP, jobs

try:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT and os.name != "nt", "native Qt/Linux queue observer")
class QueueObserver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="monet-store-observer-")
        self.queue = jobs.Queue(Path(self.tmp.name) / "store")
        self.observer = jobs.watch_queue(self.queue)
        self.changes, self.problems = [], []
        self.observer.changed.connect(self.changes.append)
        self.observer.problem.connect(self.problems.append)
        QTest.qWait(180)

    def tearDown(self):
        self.observer.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.tmp.cleanup()

    def test_an_idle_store_does_not_keep_reading_or_locking_its_queue(self):
        self.assertFalse(self.observer.timer.isActive())
        self.assertIn(str(self.queue.folder), self.observer.watcher.directories())
        with patch.object(self.queue, "recover", wraps=self.queue.recover) as recover, \
                patch.object(self.queue, "read", wraps=self.queue.read) as read:
            QTest.qWait(1700)
            (self.queue.folder.parent / "unrelated-state").write_text("changed")
            QTest.qWait(180)
            recover.assert_not_called()
            read.assert_not_called()
        self.assertEqual(self.problems, [])

    def test_external_atomic_updates_wake_it_without_multiplying_active_polls(self):
        with self.queue.lock("worker"):
            job = self.queue.submit(APP, "install")
            QTest.qWait(180)
            self.assertEqual(self.observer.items[0]["state"], "queued")
            self.assertEqual(self.observer.timer.interval(), 750)
            self.assertTrue(self.observer.timer.isActive())
            with patch.object(self.queue, "recover", wraps=self.queue.recover) as recover:
                for n in range(15):
                    self.queue.update(job["token"], state="running", progress=n / 20)
                QTest.qWait(850)
                self.assertLessEqual(recover.call_count, 2)
                self.assertEqual(self.observer.items[0]["progress"], .7)
            self.queue.update(job["token"], state="done", progress=1)
            QTest.qWait(850)
        self.assertEqual(self.observer.items[0]["state"], "done")
        self.assertFalse(self.observer.timer.isActive())
        self.assertEqual(sum(rows[0]["state"] == "done" for rows in self.changes), 1)

    def test_worker_lock_loss_is_detected_without_a_new_file_event(self):
        with self.queue.lock("worker"):
            job = self.queue.submit(APP, "install")
            self.queue.update(job["token"], state="running")
            QTest.qWait(1000)
            self.assertEqual(self.observer.items[0]["state"], "running")
        # Releasing the native flock is all that happens when the worker dies.
        QTest.qWait(900)
        self.assertEqual(self.observer.items[0]["state"], "interrupted")
        self.assertFalse(self.observer.timer.isActive())

    def test_a_removed_directory_is_rewatched_before_future_submissions(self):
        self.queue.folder.rename(Path(self.tmp.name) / "old-store")
        QTest.qWait(220)
        self.assertTrue(self.queue.folder.is_dir())
        self.assertIn(str(self.queue.folder), self.observer.watcher.directories())
        self.queue.submit(APP, "install")
        QTest.qWait(180)
        self.assertEqual(self.observer.items[0]["id"], APP["id"])

    def test_watch_failure_falls_back_and_returns_to_event_driven_idle(self):
        self.observer.watcher.removePaths(self.observer.watcher.directories())
        with patch.object(self.observer.watcher, "addPath", return_value=False):
            self.observer.poll()
            self.assertTrue(self.observer.timer.isActive())
            self.assertEqual(self.observer.timer.interval(), 30000)
        self.observer.poll()
        self.assertFalse(self.observer.timer.isActive())
        self.assertIn(str(self.queue.folder), self.observer.watcher.directories())

    def test_unreadable_queue_stays_intact_and_can_recover(self):
        self.queue.path.write_text("{broken")
        QTest.qWait(180)
        self.assertEqual(self.problems, ["storage"])
        self.observer.poll()
        self.assertEqual(self.problems, ["storage"])
        self.assertEqual(self.queue.path.read_text(), "{broken")
        self.assertEqual(self.observer.timer.interval(), 30000)
        self.queue.write([])
        QTest.qWait(180)
        self.assertFalse(self.observer.failed)
        self.assertFalse(self.observer.timer.isActive())

    def test_submission_during_initial_watch_is_not_missed(self):
        self.observer.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.observer = jobs.watch_queue(self.queue)
        original = self.observer.watcher.addPath

        def add_and_submit(path):
            watched = original(path)
            self.queue.submit(APP, "install")
            return watched

        with patch.object(self.observer.watcher, "addPath", side_effect=add_and_submit):
            QTest.qWait(180)
        self.assertEqual(self.observer.items[0]["state"], "queued")
        self.assertTrue(self.observer.timer.isActive())
