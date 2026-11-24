"""Notch agenda behavior across time zones, modified series and offline subscriptions."""
import datetime as dt
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

UTILITIES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(UTILITIES))
import agenda


def ics(*entries):
    parts = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Monet//Agenda test//EN"]
    for event in entries:
        parts += ["BEGIN:VEVENT", "DTSTAMP:20261001T120000Z", *event.splitlines(), "END:VEVENT"]
    return ("\r\n".join([*parts, "END:VCALENDAR"]) + "\r\n").encode()


class PrivateAgenda(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root / "config"),
                         XDG_CACHE_HOME=str(self.root / "cache"), TZ="Europe/Stockholm")
        env.start()
        self.addCleanup(env.stop)


class SourceTests(PrivateAgenda):
    def test_local_sources_are_private_idempotent_and_non_destructive(self):
        path = self.root / "Week.ics"
        path.write_bytes(ics())
        ident = agenda.add("file", path)
        self.assertEqual(ident, agenda.add("file", path))
        self.assertEqual(0o600, (agenda.directory() / "sources.json").stat().st_mode & 0o777)
        self.assertEqual("Week", agenda.sources()[0]["name"])
        agenda.remove(ident)
        self.assertEqual([], agenda.sources())
        self.assertTrue(path.is_file())
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(ValueError):
            agenda.add("file", path)
        path.unlink()
        with path.open("wb") as f:
            f.truncate(agenda.MAX_BYTES + 1)
        with self.assertRaises(ValueError):
            agenda.add("file", path)

    def test_private_subscription_links(self):
        key = agenda.add("url", "webcal://site.example/p.ics?key=secret", "Work")
        source, = agenda.sources()
        self.assertEqual("https://site.example/p.ics?key=secret", source["location"])
        for invalid in ("file:///etc/passwd", "http://site.example/", "https://u:p@site.example/",
                        "https://site.example/a\nb", "https://site.example:bad/a"):
            with self.assertRaises(ValueError):
                agenda.add("url", invalid)
        with patch.object(agenda, "download", return_value=(ics(), {"etag": '"A"'})) as get:
            agenda.sync_source(source)
            agenda.sync_source(source)
            self.assertEqual(1, get.call_count)
        cache = agenda.directory(True) / (key + ".ics")
        self.assertEqual(ics(), cache.read_bytes())
        self.assertEqual(0o600, cache.stat().st_mode & 0o777)
        with patch.object(agenda, "download", side_effect=OSError):
            agenda.sync_source(source, True)
        self.assertTrue(agenda.cache_meta(key)["failed"])
        self.assertEqual(ics(), cache.read_bytes())
        def removed(*_):
            agenda.remove(key)
            return ics(), {}
        with patch.object(agenda, "download", side_effect=removed):
            agenda.sync_source(source, True)
        self.assertFalse(cache.exists())
        self.assertEqual({}, agenda.cache_meta(key))


@unittest.skipUnless(importlib.util.find_spec("recurring_ical_events"), "needs packaged calendar reader")
class Appointments(PrivateAgenda):
    def setUp(self):
        super().setUp()
        self.file = self.root / "Meetings.ics"

    def test_repeating_series_moved_cancelled_excluded_and_dst(self):
        self.file.write_bytes(ics(
            "UID:weekly\nDTSTART;TZID=Europe/Stockholm:20261016T100000\nDURATION:PT1H\n"
            "RRULE:FREQ=WEEKLY;COUNT=6\nEXDATE;TZID=Europe/Stockholm:20261023T100000\nSUMMARY:Återkommande",
            "UID:weekly\nRECURRENCE-ID;TZID=Europe/Stockholm:20261030T100000\n"
            "DTSTART;TZID=Europe/Stockholm:20261031T130000\nDURATION:PT1H\nSUMMARY:Moved",
            "UID:weekly\nRECURRENCE-ID;TZID=Europe/Stockholm:20261106T100000\n"
            "DTSTART;TZID=Europe/Stockholm:20261106T100000\nDURATION:PT1H\nSTATUS:CANCELLED\nSUMMARY:Cancelled"))
        agenda.add("file", self.file)
        first = agenda.agenda(dt.date(2026, 10, 16))["events"]
        self.assertEqual([("Återkommande", "2026-10-16T10:00:00+02:00")], [(v["title"], v["start"]) for v in first])
        second = agenda.agenda(dt.date(2026, 10, 29))["events"]
        self.assertEqual([("Moved", "2026-10-31T13:00:00+01:00")], [(v["title"], v["start"]) for v in second])

    def test_local_dates_now_midnight_and_linked_file_edits(self):
        self.file.write_bytes(ics("UID:trip\nDTSTART;VALUE=DATE:20261121\nDTEND;VALUE=DATE:20261125\nSUMMARY:Trip",
            "UID:before\nDTSTART;VALUE=DATE:20261122\nDTEND;VALUE=DATE:20261124\nSUMMARY:Finished",
            "UID:past\nDTSTART:20261124T070000Z\nDTEND:20261124T080000Z\nSUMMARY:Past",
            "UID:live\nDTSTART:20261124T100000Z\nDTEND:20261124T120000Z\nSUMMARY:Ongoing",
            "UID:floating\nDTSTART:20261124T160000\nDURATION:PT30M\nSUMMARY:Later"))
        agenda.add("file", self.file)
        start = dt.date(2026, 11, 24)
        now = dt.datetime(2026, 11, 24, 11, tzinfo=dt.timezone.utc)
        events = agenda.agenda(start, now)["events"]
        self.assertEqual(["Trip", "Ongoing", "Later"], [v["title"] for v in events])
        self.assertTrue(events[0]["allDay"])
        self.assertEqual("2026-11-24T16:00:00+01:00", events[-1]["start"])
        self.file.write_bytes(ics())
        self.assertEqual([], agenda.agenda(start, now)["events"])
        self.file.unlink()
        self.assertEqual(["Meetings"], agenda.agenda(start, now)["unavailable"])


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "needs Qt")
class SourceManager(PrivateAgenda):
    def test_link_and_remove_through_manager(self):
        from PySide6.QtWidgets import QApplication, QFileDialog
        from calendars import Calendars
        self.app = QApplication.instance() or QApplication([])
        page = Calendars()
        self.addCleanup(page.close)
        file = self.root / "Meetings.ics"
        file.write_bytes(ics())
        self.assertFalse(page.forget.isEnabled())
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(file), "")):
            page.files.click()
        self.assertEqual(1, page.list.count())
        self.assertTrue(page.forget.isEnabled())
        page.forget.click()
        self.assertEqual(0, page.list.count())
        self.assertTrue(file.is_file())
