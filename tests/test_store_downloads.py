"""Store requests survive their UI, failures and interrupted workers."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, file, folder=ROOT / "linux/libexec"):
    loader = importlib.machinery.SourceFileLoader(name, str(folder / file))
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


WORKER = ROOT / "tests/fixtures/store-install-worker.py"
fixture = module("store_install_fixture", WORKER.name, WORKER.parent)


class FlatpakTransaction(unittest.TestCase):
    """What each phase asks of Flatpak (a pretend one), and the name of what went wrong in it."""

    def transaction(self, phase, failures=None, installed=False, action="install", downloaded=lambda done: None):
        modules, seen = fixture.fake_flatpak(failures, installed)
        progress = []
        with patch.dict(sys.modules, modules):
            result = store.flatpak_transaction(action, APP["ref"], "system", progress.append, lambda: False, phase=phase,
                                               downloaded=downloaded)
        return result, seen, progress

    def test_the_download_only_downloads_and_the_install_only_installs(self):
        result, seen, progress = self.transaction("fetch")
        self.assertEqual((result, seen["runs"], seen["installed"]),
                         ({"ok": True}, [("fetch", ("install", "flathub", APP["ref"]))], False))
        # Only real progress is said: a meter ticking in place is a stalled pull.
        self.assertEqual(progress, [0.0, 0.4, 1.0])
        # And when a part starts downloading, and when it's all here.
        said = []
        self.transaction("fetch", downloaded=said.append)
        self.assertEqual(said, [False, True])
        result, seen, progress = self.transaction("deploy")
        self.assertEqual((result, seen["runs"], seen["installed"], progress),
                         ({"ok": True}, [("deploy", ("install", "flathub", APP["ref"]))], True, []))
        result, seen, _ = self.transaction("fetch", installed=True)
        self.assertEqual((result, seen["runs"]), ({"ok": True, "installed": True}, []))

    def test_what_went_wrong_keeps_its_name_in_either_phase(self):
        for phase, action, installed in (("fetch", "install", False), ("deploy", "install", False), ("", "remove", True)):
            for message, name in (("No space left on device", "no-space"),
                                  ("Deploy not allowed for user", "not-allowed"),
                                  ("While pulling " + APP["ref"] + " from remote flathub: Could not resolve host", "offline"),
                                  ("Something else", "failed")):
                with self.subTest(phase=phase, message=message):
                    result, _, _ = self.transaction(phase, {phase: message}, installed, action)
                    self.assertEqual(result, {"error": name})


@unittest.skipIf(os.name == "nt", "Linux download process")
class InstallSupervision(unittest.TestCase):
    """An install downloads in a process of its own, which a stall or Cancel stops."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "worker.log"
        self.progress = []

    def command(self, scenario):
        return [sys.executable, str(WORKER), str(ROOT / "linux/libexec/monet-store"), scenario, str(self.log)]

    def install(self, scenario, cancelled=lambda: False, **options):
        return store.install_app(APP["ref"], "system", self.progress.append, cancelled, command=self.command(scenario), **options)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def steps(self):
        return [event[1:] for event in self.events()]

    def clock(self, step):
        """A clock that moves only once the download is under way, `step` seconds at each look."""
        now = [0]

        def clock():
            if self.progress:
                now[0] += step
            return now[0]
        return clock, now

    def assertStopped(self, pid):
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_an_install_downloads_in_its_own_process_and_installs_only_a_complete_download(self):
        self.assertEqual(store.install_command(APP["ref"], "user")[1:],
                         [str(ROOT / "linux/libexec/monet-store"), "--install-worker", APP["ref"], "user"])
        with patch.object(store, "install_command", lambda ref, scope: self.command("complete")):
            self.assertEqual(store.transact("install", APP["ref"], self.progress.append, lambda: False, "system"), {"ok": True})
        self.assertEqual(self.steps(), [["fetch", "start"], ["fetch", "end"], ["deploy", "start"], ["deploy", "end"]])
        workers = {event[0] for event in self.events()}
        self.assertEqual(len(workers), 1)
        self.assertNotIn(os.getpid(), workers)
        self.assertEqual(self.progress, [0.5, 0.99, 1])  # All of it only once it's installing.
        # A download that fails, or a process that ends without a word, installs nothing.
        for scenario, result in (("fetch:No space left on device", {"error": "no-space"}), ("crash", {"error": "failed"})):
            with self.subTest(scenario):
                self.log.unlink()
                self.assertEqual(self.install(scenario), result)
                self.assertEqual(self.steps(), [["fetch", "start"]])

    def test_removing_needs_no_download_process(self):
        with patch.object(store, "flatpak_transaction", return_value={"ok": True}) as transaction, \
                patch.object(store, "install_app", side_effect=AssertionError("download process")):
            self.assertEqual(store.transact("remove", APP["ref"], scope="user"), {"ok": True})
        self.assertEqual(transaction.call_args.args[:3], ("remove", APP["ref"], "user"))
        self.assertEqual(store.transact("install", APP["ref"], scope="elsewhere"), {"error": "failed"})
        refused = subprocess.run([sys.executable, str(ROOT / "linux/libexec/monet-store"), "--install-worker", "--delete", "system"],
                                 capture_output=True, timeout=30)
        self.assertEqual((refused.returncode, refused.stdout), (2, b""))

    def test_a_download_without_progress_for_the_idle_limit_is_offline_and_stopped(self):
        self.assertEqual(store.DOWNLOAD_IDLE_SECONDS, 45)
        clock, now = self.clock(15)
        started = time.monotonic()
        self.assertEqual(self.install("stall", clock=clock), {"error": "offline"})
        self.assertLess(time.monotonic() - started, 10)
        self.assertGreaterEqual(now[0], store.DOWNLOAD_IDLE_SECONDS)
        self.assertEqual(self.progress, [0.1])
        self.assertEqual(self.steps(), [["fetch", "start"]])
        self.assertStopped(self.events()[0][0])  # Even though it ignored SIGTERM.

    def test_copying_a_whole_download_is_not_a_stall_but_the_next_part_can_be(self):
        # A system-wide install copies what it downloaded into the system's store without
        # progress: on a slow disk that took longer than the idle limit, and wasn't offline.
        clock, _ = self.clock(15)  # Each look at the clock while it waited would be 15 s more.
        self.assertEqual(self.install("copying", clock=clock), {"ok": True})
        self.assertEqual(self.steps(), [["fetch", "start"], ["fetch", "end"], ["deploy", "start"], ["deploy", "end"]])
        # Once the next part starts, a pull that goes quiet has lost Flathub again.
        self.log.unlink()
        clock, _ = self.clock(15)
        self.assertEqual(self.install("next-stalls", clock=clock), {"error": "offline"})
        self.assertEqual(self.steps(), [["fetch", "start"]])
        self.assertStopped(self.events()[0][0])

    def test_slow_but_steady_progress_is_not_a_stall(self):
        clock, now = self.clock(5)
        self.assertEqual(self.install("steady", clock=clock), {"ok": True})
        self.assertGreater(now[0], store.DOWNLOAD_IDLE_SECONDS)
        self.assertEqual(self.progress, [step / 10 for step in range(1, 10)] + [0.99, 1])

    def test_cancel_stops_the_download_but_never_the_install(self):
        queue = jobs.Queue(Path(self.temp.name) / "queue")

        def press_cancel(when):
            deadline = time.monotonic() + 10
            while when not in self.steps() and time.monotonic() < deadline:
                time.sleep(0.01)
            queue.change(APP["id"], "cancel")
            with self.log.open("a") as stream:
                stream.write(json.dumps([os.getpid(), "cancel", "pressed"]) + "\n")

        for scenario, when, state, steps in (
                ("slow-fetch", ["fetch", "start"], "cancelled", [["fetch", "start"], ["cancel", "pressed"]]),
                ("wait-for-cancel", ["deploy", "start"], "done",
                 [["fetch", "start"], ["fetch", "end"], ["deploy", "start"], ["cancel", "pressed"], ["deploy", "end"]])):
            with self.subTest(scenario):
                self.log.unlink(missing_ok=True)
                queue.submit(APP, "install")
                presser = threading.Thread(target=press_cancel, args=(when,))
                presser.start()
                started = time.monotonic()
                queue.run(lambda job, progress, cancelled: store.install_app(
                    job["ref"], job["installation"], progress, cancelled, command=self.command(scenario)))
                presser.join(10)
                self.assertLess(time.monotonic() - started, 8)  # The whole download would take ten seconds.
                self.assertEqual(queue.read()[0]["state"], state)
                self.assertEqual(self.steps(), steps)
                self.assertStopped(self.events()[0][0])

    def test_the_window_knows_at_once_when_installing_starts(self):
        # Cancel can't stop the install, so the Store stops offering it then: a whole download is
        # said as just short of all of it, and the install, once it starts, as all of it at once.
        queue = jobs.Queue(Path(self.temp.name) / "queue")
        seen = []

        def watch():
            deadline = time.monotonic() + 10
            while ["deploy", "start"] not in self.steps() and time.monotonic() < deadline:
                time.sleep(0.01)
            deadline = time.monotonic() + 2
            while queue.read()[0]["progress"] < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            seen.append((queue.read()[0]["state"], queue.read()[0]["progress"]))
            with self.log.open("a") as stream:  # Lets the install finish.
                stream.write(json.dumps([os.getpid(), "cancel", "pressed"]) + "\n")

        queue.submit(APP, "install")
        watcher = threading.Thread(target=watch)
        watcher.start()
        queue.run(lambda job, progress, cancelled: store.install_app(
            job["ref"], job["installation"], progress, cancelled, command=self.command("wait-for-cancel")))
        watcher.join(10)
        self.assertEqual(seen, [("running", 1)])
        self.assertEqual(queue.read()[0]["state"], "done")
        self.log.unlink()
        self.progress.clear()
        self.assertEqual(self.install("copying", clock=self.clock(15)[0]), {"ok": True})
        self.assertEqual(self.progress, [0.99, 1])

    def test_what_went_wrong_reaches_the_store_by_its_name(self):
        downloaded = [["fetch", "start"], ["fetch", "end"], ["deploy", "start"]]
        for scenario, name, steps in (("fetch:No space left on device", "no-space", [["fetch", "start"]]),
                                      ("fetch:Could not resolve host: dl.flathub.org", "offline", [["fetch", "start"]]),
                                      ("deploy:No space left on device", "no-space", downloaded),
                                      ("deploy:Deploy not allowed for user", "not-allowed", downloaded)):
            with self.subTest(scenario):
                self.log.unlink(missing_ok=True)
                self.assertEqual(self.install(scenario), {"error": name})
                self.assertEqual(self.steps(), steps)


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


from tests import test_store_navigation as navigation  # noqa: E402

if navigation.QT:
    from PySide6.QtCore import QObject, QPointF, SIGNAL
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QSignalSpy


@unittest.skipUnless(navigation.QT, "requires PySide6 and Kirigami")
class DownloadKeys(unittest.TestCase):
    """Each download by the keys and to a screen reader: in Downloads and on an app's page."""
    setUpClass = classmethod(navigation.StoreNavigation.setUpClass.__func__)
    tearDownClass = classmethod(navigation.StoreNavigation.tearDownClass.__func__)
    setUp = navigation.StoreNavigation.setUp
    tearDown = navigation.StoreNavigation.tearDown
    item = navigation.StoreNavigation.item
    wait_for = navigation.StoreNavigation.wait_for
    open_app = navigation.StoreNavigation.open_app

    def job(self, index, **values):
        app = self.shop.apps[index]
        return dict(dict(id=app["id"], name=app["name"], action="install", state="queued", progress=0, error=""), **values)

    def jobs(self, *jobs):
        self.shop.jobsChanged.emit([dict(job) for job in jobs]); QTest.qWait(60)

    def said(self, item):
        face = QAccessible.queryAccessibleInterface(item)
        return face.text(QAccessible.Name), face.text(QAccessible.Description)

    def focused(self):
        return self.window.activeFocusItem().objectName()

    def wait_for_focus(self, name):
        self.wait_for(lambda: self.focused() == name)
        self.assertTrue(self.window.activeFocusItem().isVisible(), name)

    def downloads(self):
        QMetaObject.invokeMethod(self.window, "chooseSection", Q_ARG("QVariant", "downloads")); QTest.qWait(60)

    def test_each_download_says_which_app_and_how_it_is_going(self):
        offline = self.job(2, state="failed", progress=.2, error="offline")
        self.jobs(self.job(0, state="running", progress=.4), self.job(1, action="remove"), offline)
        self.downloads()
        ids = [app["id"] for app in self.shop.apps[:3]]
        self.assertEqual(self.said(self.item("cancel-" + ids[0])), ("Cancel downloading Fixture 0", "Downloading…"))
        self.assertEqual(self.said(self.item("cancel-" + ids[1])), ("Cancel removing Fixture 1", "Waiting its turn"))
        retry = self.said(self.item("retry-" + ids[2]))
        self.assertEqual(retry, ("Retry Fixture 2", "The download stopped because Flathub couldn't be reached. "
                                                     "Check your connection, then retry."))
        # How far it is, as a progress bar's value.
        meter = QAccessible.queryAccessibleInterface(self.item("progress-" + ids[0]))
        self.assertEqual((meter.role(), meter.text(QAccessible.Name)), (QAccessible.ProgressBar, "Fixture 0"))
        self.assertAlmostEqual(meter.valueInterface().currentValue(), .4)
        self.assertEqual(meter.valueInterface().maximumValue(), 1)

    def test_the_keys_stay_with_a_download_as_its_buttons_change(self):
        ids = [app["id"] for app in self.shop.apps[:2]]
        paint, other = self.job(0, state="running", progress=.3), self.job(1, state="running", progress=.1)
        self.jobs(paint, other)
        self.downloads()
        self.item("cancel-" + ids[0]).forceActiveFocus(Qt.TabFocusReason)
        # Cancel becomes Retry when the download fails: the keys go with it.
        self.jobs(dict(paint, state="failed", error="offline"), other)
        self.wait_for_focus("retry-" + ids[0])
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.shop.actions[-1], (ids[0], "retry"))
        self.jobs(dict(paint, state="queued", progress=0), other)
        self.wait_for_focus("cancel-" + ids[0])
        # Installing can't be cancelled: no Cancel then, and the row itself says so.
        self.jobs(dict(paint, state="running", progress=1), other)
        self.wait_for_focus("download-" + ids[0])
        self.assertFalse(self.item("cancel-" + ids[0]).isVisible())
        self.assertEqual(self.said(self.window.activeFocusItem()),
                         ("Fixture 0", "Installing… This part can't be cancelled."))
        self.jobs(dict(paint, state="done", progress=1), other)
        self.wait_for_focus("open-" + ids[0])
        self.assertEqual(self.said(self.window.activeFocusItem()), ("Open Fixture 0", "Installed"))
        QTest.keyClick(self.window, Qt.Key_Tab)
        self.wait_for_focus("dismiss-" + ids[0])
        QTest.keyClick(self.window, Qt.Key_Space)
        self.assertEqual(self.shop.actions[-1], (ids[0], "dismiss"))
        # A row that goes: the keys on the next one.
        self.jobs(other)
        self.wait_for_focus("cancel-" + ids[1])
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.assertEqual(self.shop.actions[-1], (ids[1], "cancel"))
        self.jobs(dict(other, state="cancelling"))
        self.wait_for_focus("download-" + ids[1])
        self.assertEqual(self.said(self.window.activeFocusItem()), ("Fixture 1", "Cancelling…"))
        self.jobs(dict(other, state="cancelled"))
        self.wait_for_focus("retry-" + ids[1])
        # The last one gone: the keys on Downloads in the side.
        self.jobs()
        self.wait_for_focus("storeSection-downloads")

    def test_download_changes_are_said_without_moving_the_keys(self):
        spy = QSignalSpy(self.window, SIGNAL("announced(QString,bool)"))
        self.jobs()
        search = self.item("storeSearch"); search.forceActiveFocus(Qt.TabFocusReason)
        paint = self.job(0)
        for job in (paint, dict(paint, state="running", progress=.1), dict(paint, state="running", progress=.5),
                    dict(paint, state="running", progress=1), dict(paint, state="done", progress=1)):
            self.jobs(job)
        self.jobs(dict(paint, state="done", progress=1), self.job(1, state="failed", error="no-space"))
        said = [(spy.at(i)[0], spy.at(i)[1]) for i in range(spy.count())]
        self.assertEqual(said, [("Fixture 0: Waiting its turn", False), ("Fixture 0: Downloading…", False),
                                ("Fixture 0: Installing… This part can't be cancelled.", False),
                                ("Fixture 0: Installed", False),
                                ("Fixture 1: There isn't enough free space. Free some space, then retry.", True)])
        self.assertTrue(search.hasActiveFocus())
        # With the keys on its own buttons, their focus and words say it: not twice.
        self.downloads()
        retry = self.item("retry-" + self.shop.apps[1]["id"]); retry.forceActiveFocus(Qt.TabFocusReason)
        self.jobs(dict(paint, state="done", progress=1), self.job(1))
        self.wait_for_focus("cancel-" + self.shop.apps[1]["id"])
        self.assertEqual(spy.count(), len(said))

    def test_an_app_page_keeps_the_keys_while_it_installs(self):
        ident = self.open_app()
        self.wait_for(lambda: self.window.activeFocusItem().property("text") == "Install")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(self.shop.actions, [(ident, "install")])
        paint = self.job(0)
        # Install becomes Cancel.
        self.jobs(paint)
        self.wait_for_focus("appCancel")
        self.assertEqual(self.said(self.window.activeFocusItem()), ("Cancel downloading Fixture 0", "Waiting its turn"))
        QTest.keyClick(self.window, Qt.Key_Space)
        self.assertEqual(self.shop.actions[-1], (ident, "cancel"))
        self.jobs(dict(paint, state="cancelling"))
        self.wait_for_focus("appJobStatus")
        self.assertEqual(self.said(self.window.activeFocusItem())[0], "Cancelling…")
        self.jobs(dict(paint, state="cancelled"))
        self.wait_for_focus("appRetry")
        self.assertEqual(self.said(self.window.activeFocusItem()),
                         ("Retry Fixture 0", "Cancelled. You can try again whenever you're ready."))
        QTest.keyClick(self.window, Qt.Key_Enter)
        self.assertEqual(self.shop.actions[-1], (ident, "retry"))
        self.jobs(dict(paint, state="running", progress=.6))
        self.wait_for_focus("appCancel")
        # Once it's installing, Cancel couldn't stop it: it isn't offered, and the page says why.
        self.jobs(dict(paint, state="running", progress=1))
        self.wait_for_focus("appJobStatus")
        self.assertFalse(self.item("appCancel").isVisible())
        self.assertEqual(self.said(self.window.activeFocusItem())[0], "Installing… This part can't be cancelled.")
        status = self.window.activeFocusItem()
        self.assertLessEqual(status.mapToItem(self.item("storeAppPage"), QPointF(status.width(), 0)).x(),
                             self.item("storeAppPage").width())
        self.shop.apps[0]["state"] = "installed"
        self.jobs(dict(paint, state="done", progress=1))
        self.wait_for_focus("appOpen")
        self.assertEqual(self.said(self.window.activeFocusItem()), ("Open", "Installed"))

    def test_a_waiting_meter_stands_still_with_reduced_motion(self):
        units = self.engine.singletonInstance("org.kde.kirigami", "Units") \
            or self.engine.singletonInstance("org.kde.kirigami.platform", "Units")
        self.assertIsNotNone(units)
        units.setProperty("longDuration", 1)
        self.assertLessEqual(self.window.property("speed"), 0.01)
        self.open_app()
        self.jobs(self.job(0))
        bar = self.item("appMeterBar")
        self.assertTrue(bar.isVisible())
        # Not sliding to and fro: all of the bar, faint and still.
        sweeps = [child for child in bar.findChildren(QObject) if "SequentialAnimation" in child.metaObject().className()]
        self.assertEqual([sweep.property("running") for sweep in sweeps], [False])
        self.assertEqual(round(bar.x()), 0)
        self.assertAlmostEqual(bar.width(), bar.parentItem().width(), delta=1)
        self.assertLess(bar.opacity(), 1)
