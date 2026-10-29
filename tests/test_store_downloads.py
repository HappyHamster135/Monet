"""Store requests survive their UI, failures and interrupted workers."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / "linux/libexec" / file))
    value = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(value)
    return value


store = module("download_store", "monet-store")
jobs = module("download_jobs", "monet-store-jobs") if os.name != "nt" else None
APP = {"id": "org.example.Paint", "name": "Paint", "ref": "app/org.example.Paint/x86_64/stable"}


@unittest.skipIf(os.name == "nt", "Linux user-service queue")
class DownloadQueue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = jobs.Queue(Path(self.temp.name))

    def test_saved_request_and_duplicate_clicks(self):
        first = self.queue.submit(APP, "install")
        self.assertIsNone(self.queue.submit(APP, "install"))
        reopened = jobs.Queue(Path(self.temp.name))
        self.assertEqual(reopened.read(), [first])
        self.assertEqual(self.queue.path.stat().st_mode & 0o777, 0o600)

    def test_queued_cancel_never_installs_and_can_retry_after_reopen(self):
        first = self.queue.submit(APP, "install")
        self.queue.change(APP["id"], "cancel")
        self.queue.run(lambda *_: self.fail("Cancelled download started"))
        retry = self.queue.change(APP["id"], "retry")
        self.assertNotEqual(first["token"], retry["token"])
        self.queue.run(lambda job, progress, cancelled: {"ok": True})
        self.assertEqual(self.queue.read()[0]["state"], "done")
        self.queue.change(APP["id"], "dismiss")
        self.assertEqual(self.queue.read(), [])

    def test_active_cancel_waits_for_flatpak_and_late_cancel_keeps_success(self):
        for result, expected in (({"cancelled": True}, "cancelled"), ({"ok": True}, "done")):
            self.queue.submit(APP, "install")
            def execute(job, progress, cancelled):
                self.queue.change(APP["id"], "cancel")
                self.assertEqual(self.queue.read()[0]["state"], "cancelling")
                self.assertTrue(cancelled())
                self.assertIsNone(self.queue.change(APP["id"], "retry"))
                return result
            self.queue.run(execute)
            self.assertEqual(self.queue.read()[0]["state"], expected)

    def test_failed_removal_retries_same_ref_and_installation(self):
        first = self.queue.submit(APP, "remove", "user")
        self.queue.run(lambda *_: {"error": "offline"})
        self.assertEqual(self.queue.read()[0]["error"], "offline")
        retry = self.queue.change(APP["id"], "retry")
        self.assertEqual((retry["action"], retry["ref"], retry["installation"]), ("remove", first["ref"], "user"))
        self.queue.run(lambda *_: {"ok": True})
        self.assertEqual(self.queue.read()[0]["state"], "done")

    def test_failed_transaction_does_not_block_next_request(self):
        self.queue.submit(APP, "install")
        other = dict(APP, id="org.example.Other", ref="app/org.example.Other/x86_64/stable")
        self.queue.submit(other, "install")
        def execute(job, *_):
            if job["id"] == APP["id"]:
                raise OSError("Could not start")
            return {"ok": True}
        self.queue.run(execute)
        self.assertEqual([j["state"] for j in self.queue.read()], ["failed", "done"])

    def test_disk_full_keeps_previous_queue_and_does_not_start_unrecorded_work(self):
        first = self.queue.submit(APP, "install")
        with patch.object(jobs.os, "replace", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                self.queue.change(APP["id"], "cancel")
            with self.assertRaises(OSError):
                self.queue.run(lambda *_: self.fail("Unrecorded install"))
        self.assertEqual(self.queue.read(), [first])
        self.assertEqual(list(self.queue.folder.glob(".downloads-*")), [])

    def test_malformed_queue_is_preserved_not_silently_reset(self):
        for raw in ('{broken', '{"version":1,"jobs":[null]}', '{"version":2,"jobs":[]}'):
            self.queue.path.write_text(raw)
            with self.assertRaises(OSError):
                self.queue.submit(APP, "install")
            self.assertEqual(self.queue.path.read_text(), raw)

    def test_live_worker_lock_prevents_recovery_and_stale_worker_becomes_interrupted(self):
        job = self.queue.submit(APP, "install")
        self.queue.update(job["token"], state="running")
        with self.queue.lock("worker"):
            self.queue.recover()
            self.assertEqual(self.queue.read()[0]["state"], "running")
        self.queue.recover()
        self.assertEqual(self.queue.read()[0]["state"], "interrupted")
        self.queue.run(lambda *_: self.fail("Interrupted operation automatically retried"))

    def test_worker_process_loss_releases_lock_and_retains_request(self):
        self.queue.submit(APP, "install")
        script = """import importlib.machinery, importlib.util, sys, time
l = importlib.machinery.SourceFileLoader('q', sys.argv[1])
m = importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name, l)); l.exec_module(m)
m.Queue(sys.argv[2]).run(lambda *_: time.sleep(60))
"""
        child = subprocess.Popen([sys.executable, "-c", script, str(ROOT / "linux/libexec/monet-store-jobs"), self.temp.name])
        try:
            deadline = time.monotonic() + 5
            while self.queue.read()[0]["state"] != "running" and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(self.queue.read()[0]["state"], "running")
            child.kill(); child.wait(timeout=5)
            self.queue.recover()
            self.assertEqual(self.queue.read()[0]["state"], "interrupted")
        finally:
            if child.poll() is None:
                child.kill(); child.wait(timeout=5)

    def test_invalid_ref_or_identity_cannot_be_queued(self):
        for app in (dict(APP, ref="--delete"), dict(APP, id="org.other.App")):
            with self.assertRaises(ValueError):
                self.queue.submit(app, "install")
        self.assertEqual(self.queue.read(), [])

    def test_rebooted_queued_request_needs_retry_and_cancel_stays_cancelled(self):
        job = self.queue.submit(APP, "install")
        with patch.object(jobs.time, "time", return_value=time.time() + 20):
            self.queue.recover()
        self.assertEqual(self.queue.read()[0]["state"], "interrupted")
        self.queue.update(job["token"], state="cancelling")
        self.queue.recover()
        self.assertEqual(self.queue.read()[0]["state"], "cancelled")

    def test_two_workers_do_not_install_the_same_request_twice(self):
        self.queue.submit(APP, "install")
        script = """import importlib.machinery, importlib.util, sys, time
from pathlib import Path
l = importlib.machinery.SourceFileLoader('q', sys.argv[1])
m = importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name, l)); l.exec_module(m)
def execute(*_):
    with (Path(sys.argv[2])/'calls').open('a') as f: f.write('install\\n')
    time.sleep(.1)
    return {'ok': True}
m.Queue(sys.argv[2]).run(execute)
"""
        processes = [subprocess.Popen([sys.executable, "-c", script, str(ROOT / "linux/libexec/monet-store-jobs"), self.temp.name]) for _ in range(2)]
        try:
            for process in processes:
                self.assertEqual(process.wait(timeout=5), 0)
            self.assertEqual((self.queue.folder / "calls").read_text(), "install\n")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)

    def test_worker_start_failure_is_reported(self):
        with patch.object(jobs.subprocess, "run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(OSError):
                jobs.start_worker(ROOT / "linux/libexec/monet-store")
            self.assertIn("--setenv=XDG_STATE_HOME=" + str(jobs.directory().parent.parent.resolve()), run.call_args.args[0])

    def test_worker_holds_shutdown_veto_before_starting_any_transaction(self):
        with patch.object(jobs.subprocess, "run") as run:
            run.return_value.returncode = 0
            jobs.start_worker(ROOT / "linux/libexec/monet-store")
            command = run.call_args.args[0]
            guarded = command[command.index("systemd-inhibit"):]
            self.assertEqual(guarded, ["systemd-inhibit", "--what=shutdown", "--mode=block", "--who=Store",
                                      "--why=Installing or removing apps", "--no-ask-password", "/usr/bin/python3",
                                      str(ROOT / "linux/libexec/monet-store"), "--worker"])


class DownloadErrors(unittest.TestCase):
    def test_network_permissions_and_space_have_distinct_messages(self):
        for message, expected in (("No space left on device", "no-space"),
                                  ("min-free-space-size would be exceeded", "no-space"),
                                  ("Could not resolve host", "offline"),
                                  ("Deploy not allowed for user", "not-allowed")):
            self.assertEqual(store.trouble(message), expected)


try:
    from PySide6.QtCore import QObject, QMetaObject, Q_ARG, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class FakeShop(QObject):
        loaded = Signal(); changed = Signal(str, bool, str); progress = Signal(str, float)
        facts = Signal(str, "QVariant"); wanted = Signal(str)
        jobsChanged = Signal("QVariant"); queueProblem = Signal(str)
        def __init__(self):
            super().__init__(); self.actions = []
        @Slot(result="QVariant")
        def home(self): return {"rows": [], "today": None, "top": [], "fresh": []}
        @Slot(result="QVariant")
        def counts(self): return {}
        @Slot(result="QVariant")
        def windows(self): return []
        @Slot(str, str)
        def downloadAction(self, app_id, action): self.actions.append((app_id, action))
        @Slot()
        def poll(self): pass


@unittest.skipUnless(QT, "PySide6/Kirigami on Linux")
class DownloadUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.games = module("download_games", "monet-games")

    def test_queue_available_without_catalog_cancel_and_retry_are_keyboard_actions(self):
        engine = QQmlApplicationEngine(); words = self.games.Words(); shop = FakeShop(); helper = self.games.Helper()
        context = engine.rootContext(); context.setContextObject(words)
        for name, value in {"shop": shop, "helper": helper, "firstPage": "downloads", "blurBehind": False,
                            "banners": "", "art": "", "brush": ""}.items():
            context.setContextProperty(name, value)
        engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/store-app/Store.qml")))
        self.assertTrue(engine.rootObjects())
        window = engine.rootObjects()[0]
        try:
            QTest.qWait(100)
            self.assertEqual(window.property("section"), "downloads")
            window.setProperty("pageId", APP["id"])
            QMetaObject.invokeMethod(window, "chooseSection", Q_ARG("QVariant", "downloads"))
            self.assertEqual(window.property("pageId"), "")
            job = dict(APP, state="running", action="install", progress=.4, error="")
            shop.jobsChanged.emit([job]); QTest.qWait(50)
            def find(name):
                pending = [window.contentItem()]
                while pending:
                    item = pending.pop()
                    if item.objectName() == name: return item
                    pending.extend(item.childItems())
                self.fail(name)
            cancel = find("cancel-" + APP["id"])
            self.assertTrue(cancel.isVisible()); self.assertTrue(cancel.property("activeFocusOnTab"))
            cancel.forceActiveFocus()
            shop.jobsChanged.emit([dict(job, progress=.5)]); QTest.qWait(50)
            self.assertEqual(find("cancel-" + APP["id"]), cancel)
            self.assertTrue(cancel.property("activeFocus"))
            QTest.keyClick(window, Qt.Key_Return)
            self.assertEqual(shop.actions, [(APP["id"], "cancel")])
            job.update(state="interrupted")
            shop.jobsChanged.emit([job]); QTest.qWait(50)
            retry = find("retry-" + APP["id"])
            self.assertTrue(retry.isVisible()); self.assertTrue(retry.property("activeFocusOnTab"))
            retry.forceActiveFocus()
            QTest.keyClick(window, Qt.Key_Space)
            self.assertEqual(shop.actions[-1], (APP["id"], "retry"))
        finally:
            window.close(); engine.deleteLater(); QTest.qWait(1)
