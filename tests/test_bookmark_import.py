"""Import preparation is read-only; browser confirmation never substitutes for verification."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_look import libexec_helper, quick_helper
from tests.test_settings_feedback import QT

if QT:
    from PySide6.QtCore import QObject, QMetaObject, QPointF, QTimer, QUrl, Qt, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest

    class ImportHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self):
            super().__init__(); self.ticket = 0; self.calls = []; self.reply = {}

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1; ticket = self.ticket
            result = {}; delay = 40
            if command[1] == "windows-browsers":
                result = {"profiles": [{"id": "one", "name": "Personal"}, {"id": "two", "name": "Work"}]}
            elif command[1] == "defaults":
                delay = 350
                result = [{"id": str(n), "name": "Default app " + str(n), "current": "fixture", "apps": []} for n in range(8)]
            elif command[1].startswith("bookmarks-"):
                self.calls.append((command[1], json.loads(bytes.fromhex(command[2]))))
                result = self.reply
            QTimer.singleShot(delay, lambda: self.done.emit(ticket, json.dumps(result), 0, ""))
            return ticket


@unittest.skipIf(os.name == "nt", "Linux profile locks")
class BookmarkImport(unittest.TestCase):
    def setUp(self):
        self.b = libexec_helper("monet-bookmarks")
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, value in (("profile_root", self.root / "zen"), ("state_root", self.root / "state")):
            replacement = patch.object(self.b, name, return_value=value)
            replacement.start(); self.addCleanup(replacement.stop)
        self.b.profile_root().mkdir()
        (self.b.profile_root() / "profiles.ini").write_text(
            "[Profile0]\nName=Personal\nIsRelative=1\nPath=one\n[Profile1]\nName=Work\nIsRelative=1\nPath=two\n")
        for name in ("one", "two"):
            profile = self.b.profile_root() / name; profile.mkdir()
            (profile / ".parentlock").touch()
            with closing(sqlite3.connect(profile / "places.sqlite")) as db, db:
                db.executescript("CREATE TABLE moz_places(id INTEGER PRIMARY KEY,url TEXT);"
                    "CREATE TABLE moz_bookmarks(id INTEGER PRIMARY KEY,type INT,fk INT,parent INT,title TEXT,guid TEXT);"
                    "INSERT INTO moz_places VALUES(1,'https://existing.example/');"
                    "INSERT INTO moz_bookmarks VALUES(1,1,1,0,'Keep me','existingGUID');")
        self.source = self.root / "export.html"
        self.source.write_bytes(self.b.html([
            {"title": "Already here", "url": "https://existing.example/"},
            {"title": "Work åäö", "children": [
                {"title": "Wiki <team>", "url": "https://new.example/?a=1&b=2"},
                {"title": "Repeated", "url": "https://new.example/?a=1&b=2"},
                {"title": "Unsafe", "url": "javascript:alert(1)"}]}], "Browser export"))
        self.request = {"profile": "one", "source": self.source.as_uri()}

    def plan(self):
        return self.b.plan(self.request, self.source)[0]

    def prepare(self, launch=None):
        self.request["token"] = self.plan()["token"]
        return self.b.prepare(self.request, self.source, self.root / "Downloads", "Imported bookmarks", launch or Mock())

    def test_review_filters_links_preserves_tree_and_does_not_write_either_profile(self):
        before = {p: p.read_bytes() for p in self.b.profile_root().rglob("*") if p.is_file()}
        result, tree, urls = self.b.plan(self.request, self.source)
        self.assertEqual((result["count"], result["new"], result["duplicates"], result["unsupported"]), (4, 1, 2, 1))
        self.assertEqual(tree[0]["children"][0]["title"], "Work åäö")
        self.assertEqual(urls, ["https://new.example/?a=1&b=2"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(self.b.state_root().exists())

    def test_prepare_is_private_does_not_overwrite_and_launches_only_selected_profile(self):
        downloads = self.root / "Downloads"; downloads.mkdir()
        old = downloads / "Bookmarks from Windows.html"; old.write_text("keep")
        launch = Mock(); result = self.prepare(launch)
        self.assertEqual(old.read_text(), "keep")
        export = Path(result["file"])
        self.assertEqual(export.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.b.state_root() / (result["id"] + ".json")).stat().st_mode & 0o777, 0o600)
        self.assertIn(b"Wiki &lt;team&gt;", export.read_bytes())
        self.assertNotIn(b"javascript:", export.read_bytes())
        launch.assert_called_once_with(["flatpak", "run", self.b.ZEN, "--new-instance", "--profile",
                                       str(self.b.profile_root() / "one"), "-chrome", self.b.LIBRARY])
        self.assertEqual(self.b.recent()[0]["id"], result["id"])
        self.assertEqual(self.b.verify(result["id"])["state"], "not-imported")

    def test_changed_source_or_destination_requires_a_new_review(self):
        self.request["token"] = self.plan()["token"]
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        with self.assertRaisesRegex(self.b.ImportError, "changed"):
            self.b.prepare(self.request, self.source, self.root / "Downloads", "Imported", Mock())
        self.request["token"] = self.plan()["token"]
        with closing(sqlite3.connect(self.b.profile_root() / "one/places.sqlite")) as db, db:
            db.executescript("INSERT INTO moz_places VALUES(2,'https://added.example/');"
                             "INSERT INTO moz_bookmarks VALUES(2,1,2,0,'Added','newGUID');")
        with self.assertRaisesRegex(self.b.ImportError, "changed"):
            self.b.prepare(self.request, self.source, self.root / "Downloads", "Imported", Mock())
        self.assertFalse((self.root / "Downloads").exists())

    def test_verification_checks_the_import_folder_and_repeated_review_skips_imported_urls(self):
        result = self.prepare()
        with closing(sqlite3.connect(self.b.profile_root() / "one/places.sqlite")) as db, db:
            db.execute("INSERT INTO moz_bookmarks VALUES(2,2,NULL,0,?,'folderGUID')", (result["folder"],))
            db.execute("INSERT INTO moz_places VALUES(2,'https://new.example/?a=1&b=2')")
            db.execute("INSERT INTO moz_bookmarks VALUES(3,1,2,2,'Wiki','importedGUID')")
        self.assertEqual(self.b.verify(result["id"])["state"], "verified")
        self.assertEqual(self.plan()["new"], 0)
        with closing(sqlite3.connect(self.b.profile_root() / "one/places.sqlite")) as db, db:
            self.assertEqual(db.execute("SELECT title,guid FROM moz_bookmarks WHERE id=1").fetchone(), ("Keep me", "existingGUID"))
            db.execute("INSERT INTO moz_bookmarks VALUES(4,1,2,2,'Duplicate','duplicateGUID')")
        self.assertEqual(self.b.verify(result["id"])["duplicates"], 1)
        self.request["profile"] = "two"
        self.assertEqual(self.plan()["new"], 1)

    def test_invalid_and_oversized_files_fail_before_any_export_is_created(self):
        with patch.object(self.b, "MAX_LINKS", 2):
            with self.assertRaisesRegex(self.b.ImportError, "large"):
                self.plan()
        for data in (b"not bookmarks", b"\xff\x00", b'<!DOCTYPE NETSCAPE-Bookmark-file-1><DL><A HREF="https://a/">a'):
            self.source.write_bytes(data)
            with self.assertRaisesRegex(self.b.ImportError, "invalid"):
                self.plan()
        with patch.object(self.b, "LIMIT", 16):
            self.source.write_bytes(b"x" * 17)
            with self.assertRaisesRegex(self.b.ImportError, "large"):
                self.plan()
        self.assertFalse(self.b.state_root().exists())

    def test_unreadable_profile_list_and_external_profile_are_not_offered(self):
        ini = self.b.profile_root() / "profiles.ini"
        ini.write_text("[Profile0]\nName=Outside\nIsRelative=1\nPath=..\n")
        self.assertEqual(self.b.profiles(), [])
        ini.write_bytes(b"\xff\x00")
        self.assertEqual(self.b.profiles(), [])

    def test_nonregular_sources_external_profiles_and_invalid_requests_are_rejected(self):
        fifo = self.root / "pipe"; os.mkfifo(fifo)
        self.request["source"] = fifo.as_uri()
        with self.assertRaisesRegex(self.b.ImportError, "source"):
            self.plan()
        self.request["source"] = self.source.as_uri()
        self.request["profile"] = "../outside"
        with self.assertRaisesRegex(self.b.ImportError, "profile"):
            self.plan()
        for ident in ("../other", "", None):
            with self.assertRaisesRegex(self.b.ImportError, "request"):
                self.b.verify(ident)

    def test_locked_and_corrupt_profiles_are_not_treated_as_empty(self):
        code = "import fcntl,sys;f=open(sys.argv[1],'r+');fcntl.lockf(f,fcntl.LOCK_EX);print('locked',flush=True);sys.stdin.read()"
        process = subprocess.Popen([sys.executable, "-c", code, str(self.b.profile_root() / "one/.parentlock")],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            with self.assertRaisesRegex(self.b.ImportError, "busy"):
                self.plan()
        finally:
            process.communicate(timeout=5)
        (self.b.profile_root() / "one/places.sqlite").write_bytes(b"corrupted database")
        with self.assertRaisesRegex(self.b.ImportError, "database"):
            self.plan()

    def test_launch_failure_retains_prepared_file_and_no_false_import_success(self):
        result = self.prepare(Mock(side_effect=OSError("unavailable")))
        self.assertFalse(result["opened"])
        self.assertTrue(Path(result["file"]).is_file())
        self.assertEqual(self.b.verify(result["id"])["state"], "not-imported")

    def test_failed_export_or_receipt_is_removed_without_launching(self):
        launch = Mock()
        for fail_at in (1, 2):
            with patch.object(self.b.os, "fsync", side_effect=[None] * (fail_at - 1) + [OSError("full")]):
                with self.assertRaises(OSError):
                    self.prepare(launch)
            self.assertEqual(list((self.root / "Downloads").iterdir()), [])
            self.assertEqual(list(self.b.state_root().glob("*.json")), [])
            launch.assert_not_called()

    def test_corrupt_or_empty_receipts_cannot_report_success(self):
        result = self.prepare()
        path = self.b.state_root() / (result["id"] + ".json")
        record = json.loads(path.read_text())
        for data in ("broken", "null", "[]", json.dumps({**record, "urls": []}),
                     json.dumps({**record, "urls": [None]})):
            path.write_text(data)
            with self.assertRaisesRegex(self.b.ImportError, "request"):
                self.b.verify(result["id"])
            self.assertEqual(self.b.recent(), [])

    def test_dispatch_reports_invalid_input_and_does_not_launch(self):
        q = quick_helper()
        with patch.object(q, "zen_here", return_value=True), patch.object(q.subprocess, "Popen") as launch:
            for value in ("not JSON", "null", "[]", "{}"):
                self.assertFalse(q.bookmarks_action("preview", value.encode().hex())["ok"])
            launch.assert_not_called()


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class BookmarkImportUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.engine = QQmlApplicationEngine(); self.words = libexec_helper("monet-games").Words()
        self.helper = ImportHelper(); context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "firstPage": "apps#bookmarks", "blurBehind": False,
                            "pictures": QUrl.fromLocalFile(str(root / "linux/share/monet/settings") + "/").toString(),
                            "brush": QUrl.fromLocalFile(str(root / "linux/share/monet/textures/brush.png")).toString()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(root / "linux/share/monet/settings-app/MonetSettings.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]; QTest.qWait(150)
        self.card = self.item("search-bookmarks")

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(1)

    def item(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name: return item
            pending.extend(item.childItems())
        self.fail("Missing " + name)

    def click(self, name, reply):
        self.helper.reply = reply
        QMetaObject.invokeMethod(self.item(name), "clicked")

    def test_review_is_required_and_preparation_never_claims_import_success(self):
        QTest.qWait(300)
        self.assertFalse(self.item("bookmarkReview").property("enabledPill"))
        self.card.setProperty("source", "file:///tmp/bookmarks.html")
        self.window.requestActivate(); QTest.qWait(20)
        self.item("bookmarkProfile-two").forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        self.assertEqual(self.card.property("profile"), "two")
        self.assertTrue(self.item("bookmarkProfile-two").property("checked"))
        self.assertFalse(self.item("bookmarkProfile-one").property("checked"))
        self.click("bookmarkReview", {"ok": True, "token": "reviewed", "new": 1, "duplicates": 2, "unsupported": 1, "sample": []})
        self.assertTrue(self.card.property("busy"))
        self.assertFalse(self.item("bookmarkPrepare").property("enabledPill"))
        QTest.qWait(80)
        self.assertTrue(self.item("bookmarkPrepare").property("enabledPill"))
        self.click("bookmarkPrepare", {"ok": True, "state": "prepared", "id": "a" * 32, "file": "/tmp/prepared.html", "folder": "Imported", "opened": True})
        QMetaObject.invokeMethod(self.item("bookmarkPrepare"), "clicked")
        QTest.qWait(80)
        self.assertEqual(len(self.helper.calls), 2)
        self.assertEqual(self.helper.calls[-1][1], {"profile": "two", "source": "file:///tmp/bookmarks.html", "token": "reviewed"})
        self.assertEqual(self.card.property("checkedState"), "")
        self.click("bookmarkVerify", {"ok": False, "error": "busy"}); QTest.qWait(80)
        self.assertIn("Close this Zen profile", self.card.property("message"))
        self.assertTrue(self.item("bookmarkVerify").property("enabledPill"))
        self.click("bookmarkVerify", {"ok": True, "state": "verified", "count": 1, "expected": 1, "duplicates": 0}); QTest.qWait(80)
        self.assertEqual(self.card.property("checkedState"), "verified")

    def test_direct_link_waits_for_slow_default_apps_above_the_import_card(self):
        self.assertEqual(self.window.property("pendingAnchor"), "bookmarks")
        QTest.qWait(400)
        self.assertEqual(self.window.property("pendingAnchor"), "")
        view = self.item("settingsScroller")
        top = self.card.mapToItem(view, QPointF(0, 0)).y()
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(top + self.card.height(), view.height())

    def test_failed_review_stays_retryable_and_disables_preparation(self):
        self.card.setProperty("source", "file:///tmp/bookmarks.html"); self.card.setProperty("profile", "one")
        for code in ("invalid", "changed", "storage"):
            self.click("bookmarkReview", {"ok": False, "error": code}); QTest.qWait(80)
            self.assertFalse(self.card.property("busy"))
            self.assertTrue(self.card.property("message"))
            self.assertFalse(self.item("bookmarkPrepare").property("enabledPill"))


if __name__ == "__main__":
    unittest.main()
