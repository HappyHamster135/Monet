"""Offline sun-driven light changes, including polar and date-line locations."""
from datetime import datetime, timezone
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('daylight', str(ROOT/'linux/libexec/monet-daylight'))
spec = importlib.util.spec_from_loader(loader.name, loader)
daylight = importlib.util.module_from_spec(spec); loader.exec_module(daylight)

class Daylight(unittest.TestCase):
    def light(self, stamp, where=(59.32938, 18.06871)):
        return daylight.light_at(datetime.fromisoformat(stamp), where)
    def test_stockholm_october_sunset_precedes_old_five_pm_change(self):
        self.assertEqual(self.light('2026-10-30T15:45:00+01:00'), 'mist')
        self.assertEqual(self.light('2026-10-30T16:15:00+01:00'), 'smoke')
        self.assertEqual(self.light('2026-10-30T06:30:00+01:00'), 'smoke')
        self.assertEqual(self.light('2026-10-30T07:15:00+01:00'), 'mist')
    def test_polar_day_and_night_do_not_fall_back_to_clock_hours(self):
        for hour in [0,6,12,18]:
            self.assertEqual(self.light(f'2026-06-21T{hour:02}:00:00+02:00',(78.2,15.6)), 'mist')
            self.assertEqual(self.light(f'2026-12-21T{hour:02}:00:00+01:00',(78.2,15.6)), 'smoke')
    def test_same_instant_across_timezones_dst_and_date_line(self):
        for where in [(59.3,18.1),(-36.85,174.76),(0,-179),(0,179)]:
            for stamp in ['2026-10-25T01:30:00+00:00','2026-03-29T01:30:00+00:00','2026-06-21T20:30:00+00:00']:
                now=datetime.fromisoformat(stamp)
                expected=daylight.light_at(now,where)
                for zone in ['Europe/Stockholm','Pacific/Auckland','America/Los_Angeles']:
                    self.assertEqual(daylight.light_at(now.astimezone(ZoneInfo(zone)),where),expected)
        self.assertEqual(self.light('2026-06-22T12:00:00+12:00',(-36.85,174.76)),'mist')
        self.assertEqual(self.light('2026-06-22T00:00:00+12:00',(-36.85,174.76)),'smoke')
    def test_location_validation_timezone_fallback_and_no_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp);(config/'monet').mkdir();file=config/'monet/weather.json'
            file.write_text(json.dumps(dict(place='Stockholm',latitude=59.3,longitude=18.1)))
            self.assertEqual(daylight.location(config,'Europe/London'),(59.3,18.1))
            for bad in ['{}','null','{',json.dumps(dict(place='Bad',latitude=float('nan'),longitude=0))]:
                file.write_text(bad)
                self.assertAlmostEqual(daylight.location(config,'Europe/Stockholm')[0],59.333333,places=4)
                self.assertIsNone(daylight.location(config,'Unknown/Zone'))
            self.assertEqual(daylight.light_at(datetime(2026,1,1,12,tzinfo=timezone.utc),None),'mist')

if __name__ == '__main__': unittest.main()
