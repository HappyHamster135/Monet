"""The desktop and bar share preferences, units, cached forecasts and recovery."""
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Linux file locking")
class SharedWeather(unittest.TestCase):
    def setUp(self):
        loader = importlib.machinery.SourceFileLoader("weather", str(ROOT / "linux/libexec/monet-weather"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.w = importlib.util.module_from_spec(spec)
        loader.exec_module(self.w)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w.CONFIG = Path(self.tmp.name) / "config/weather.json"
        self.w.CACHE = Path(self.tmp.name) / "cache/weather.json"
        self.stockholm = dict(place="Stockholm", latitude=59.32938, longitude=18.06871, fahrenheit=False)

    def test_existing_desktop_seeds_once_empty_panel_and_older_widgets_do_not_overwrite(self):
        self.w.update({}, seed=True)
        self.assertFalse(self.w.CONFIG.exists())
        self.w.update(self.stockholm, seed=True)
        self.w.update({"place": "Göteborg", "latitude": 57.7, "longitude": 11.9})
        self.w.update(self.stockholm, seed=True)
        self.assertEqual(self.w.read(self.w.CONFIG, {})["place"], "Göteborg")

    def test_panel_and_desktop_share_one_request_and_unit_changes_do_not_reuse_wrong_temperature(self):
        self.w.update(self.stockholm)
        with patch.object(self.w, "fetch", side_effect=lambda c: {"current": {"temperature_2m": 52 if c["fahrenheit"] else 11}}) as fetch:
            a, b = self.w.status(), self.w.status()
            self.assertEqual(a, b)
            self.assertEqual(fetch.call_count, 1)
            self.w.update({"fahrenheit": True})
            self.assertEqual(self.w.status()["weather"]["current"]["temperature_2m"], 52)
            self.assertEqual(fetch.call_count, 2)
            self.w.update({"fahrenheit": False})
            self.assertEqual(self.w.status()["weather"]["current"]["temperature_2m"], 11)
            self.assertEqual(fetch.call_count, 2)

    def test_offline_keeps_last_forecast_marks_stale_throttles_and_retry_recovers(self):
        self.w.update(self.stockholm)
        with patch.object(self.w, "fetch", return_value={"current": {"temperature_2m": 11}}):
            self.w.status()
        with patch.object(self.w, "fetch", side_effect=OSError("offline")) as fetch:
            result = self.w.status(force=True)
            self.assertTrue(result["stale"])
            self.assertEqual(result["weather"]["current"]["temperature_2m"], 11)
            self.w.status()
            self.assertEqual(fetch.call_count, 1)
        with patch.object(self.w, "fetch", return_value={"current": {"temperature_2m": 12}}):
            self.assertFalse(self.w.status(force=True)["stale"])

    def test_location_changed_during_request_never_displays_previous_places_weather(self):
        self.w.update(self.stockholm)
        def slow_request(config):
            self.w.update({"place": "Göteborg", "latitude": 57.7, "longitude": 11.9})
            return {"current": {"temperature_2m": 11}}
        with patch.object(self.w, "fetch", side_effect=slow_request):
            result = self.w.status()
        self.assertEqual(result["config"]["place"], "Göteborg")
        self.assertIsNone(result["weather"])

    def test_legacy_string_list_keeps_all_places_and_preferences_are_private(self):
        self.w.update(dict(self.stockholm, places=[json.dumps({"name": "Malmö", "latitude": 55.6, "longitude": 13})]))
        config = self.w.read(self.w.CONFIG, {})
        self.assertEqual([p["name"] for p in config["places"]], ["Malmö", "Stockholm"])
        self.assertEqual(self.w.CONFIG.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            self.w.update({"latitude": float("nan")})
        self.assertEqual(config, self.w.read(self.w.CONFIG, {}))

    def test_other_widgets_can_read_cached_weather_while_request_is_in_flight(self):
        self.w.update(self.stockholm)
        with self.w.lock(self.w.CACHE.with_suffix(".lock")):
            with patch.object(self.w, "fetch") as fetch:
                self.assertIsNone(self.w.status()["weather"])
                fetch.assert_not_called()

    def forecast(self):
        day = datetime(2026, 10, 27)
        return {"current": {"temperature_2m": 11}, "utc_offset_seconds": 3600,
            "daily": {"time": [(day + timedelta(days=i)).date().isoformat() for i in range(7)],
                **{k: [1] * 7 for k in ("weather_code", "temperature_2m_max", "temperature_2m_min",
                    "precipitation_probability_max", "sunrise", "sunset", "wind_speed_10m_max")}},
            "hourly": {"time": [(day + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(168)],
                **{k: [1] * 168 for k in ("temperature_2m", "weather_code", "is_day", "precipitation_probability", "wind_speed_10m")}}}

    def test_fetch_requests_and_validates_a_week_and_hourly_details_with_matching_units(self):
        sample = self.forecast()
        with patch.object(self.w, "urlopen", return_value=io.BytesIO(json.dumps(sample).encode())) as request:
            result = self.w.fetch(dict(self.stockholm, fahrenheit=True))
        self.assertEqual(result, sample)
        query = parse_qs(urlparse(request.call_args.args[0]).query)
        self.assertEqual(query["forecast_days"], ["7"])
        self.assertEqual(query["temperature_unit"], ["fahrenheit"])
        self.assertEqual(query["wind_speed_unit"], ["mph"])
        self.assertIn("precipitation_probability", query["hourly"][0])
        self.assertIn("apparent_temperature", query["current"][0])
        self.assertIn("sunrise", query["daily"][0])
        sample["hourly"]["temperature_2m"].pop()
        with patch.object(self.w, "urlopen", return_value=io.BytesIO(json.dumps(sample).encode())):
            with self.assertRaisesRegex(ValueError, "Incomplete forecast"):
                self.w.fetch(self.stockholm)

    def test_old_cache_upgrades_immediately_and_keeps_old_summary_if_offline(self):
        self.w.update(self.stockholm)
        old = {"current": {"temperature_2m": 11}}
        self.w.atomic(self.w.CACHE, {self.w.cache_key(self.stockholm): {"weather": old, "attempt": self.w.time.time()}})
        with patch.object(self.w, "fetch", side_effect=OSError("offline")) as request:
            self.assertEqual(self.w.status()["weather"], old)
            self.assertTrue(self.w.status()["stale"])
            self.assertEqual(request.call_count, 1)
        with patch.object(self.w, "fetch", return_value=self.forecast()):
            self.assertEqual(len(self.w.status(force=True)["weather"]["daily"]["time"]), 7)

    def test_incomplete_response_does_not_replace_the_last_complete_forecast(self):
        self.w.update(self.stockholm)
        good = self.forecast()
        with patch.object(self.w, "urlopen", return_value=io.BytesIO(json.dumps(good).encode())):
            self.w.status()
        incomplete = dict(good, daily={"time": ["2026-10-27"]})
        with patch.object(self.w, "urlopen", return_value=io.BytesIO(json.dumps(incomplete).encode())):
            result = self.w.status(force=True)
        self.assertTrue(result["stale"])
        self.assertEqual(result["weather"], good)


try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine
except ImportError:
    QJSEngine = None


@unittest.skipUnless(QJSEngine, "Qt JavaScript runtime")
class EverydayBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def policy(self, config, repeat=1):
        engine = QJSEngine()
        engine.evaluate("var config = " + json.dumps(config) + ";")
        engine.evaluate('''
            var added = [], tray = {readConfig:k=>config[k]||"", writeConfig:(k,v)=>config[k]=v.join(","), reloadConfig:()=>{}};
            var otherAdded = [];
            var panel = {widgets:id=>id==="org.monet.quick"?[{index:2}]:id==="org.kde.plasma.systemtray"?[tray]:added,
                         addWidget:id=>{var w={type:id,index:0};added.push(w);return w;}};
            function panels() { return [panel,{widgets:id=>[],addWidget:id=>otherAdded.push(id)}]; }
        ''')
        script = (ROOT / "linux/share/monet/bar-defaults.js").read_text()
        for _ in range(repeat):
            result = engine.evaluate(script)
            self.assertFalse(result.isError(), result.toString())
        return json.loads(engine.evaluate("JSON.stringify({config,added,otherAdded})").toString())

    def test_keeps_unrelated_apps_layout_switching_and_privacy_indicators(self):
        result = self.policy({"extraItems": "example.user-app,org.kde.plasma.keyboardlayout,org.kde.plasma.cameraindicator,org.kde.kscreen,org.kde.plasma.manage-inputmethod",
                              "disabledStatusNotifiers": "My deliberately disabled app"})
        enabled = result["config"]["extraItems"].split(",")
        for item in ("example.user-app", "org.kde.plasma.keyboardlayout", "org.kde.plasma.cameraindicator", "org.kde.plasma.networkmanagement", "org.kde.plasma.bluetooth"):
            self.assertIn(item, enabled)
        self.assertNotIn("org.kde.kscreen", enabled)
        self.assertNotIn("org.kde.plasma.manage-inputmethod", enabled)
        self.assertEqual(result["config"]["disabledStatusNotifiers"], "My deliberately disabled app,Xwayland Video Bridge")
        self.assertEqual(result["otherAdded"], [])

    def test_reapplying_does_not_duplicate_widgets_or_reenable_removed_items(self):
        result = self.policy({}, repeat=2)
        self.assertEqual(result["added"], [{"type": "org.monet.weather", "index": 2}])
        for key, value in result["config"].items():
            self.assertEqual(len(value.split(",")), len(set(value.split(","))), key)
        self.assertIn("org.kde.plasma.weather", result["config"]["knownItems"])
        self.assertNotIn("org.kde.plasma.weather", result["config"]["extraItems"])


@unittest.skipUnless(QJSEngine, "Qt JavaScript runtime")
class ForecastPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def evaluate(self, script):
        engine = QJSEngine()
        source = (ROOT / "linux/share/plasma/plasmoids/org.monet.weather/contents/ui/Forecast.js").read_text(encoding="utf-8")
        result = engine.evaluate(source.replace(".pragma library", "") + "\n" + script)
        self.assertFalse(result.isError(), result.toString())
        return json.loads(result.toString())

    def test_hourly_forecast_uses_places_day_across_midnight_and_selected_day(self):
        result = self.evaluate('''
            var weather = {utc_offset_seconds:7200, hourly:{time:["2026-10-27T23:00","2026-10-28T00:00","2026-10-28T01:00","2026-10-28T02:00"],
                temperature_2m:[10,9,8,7],precipitation_probability:[0,0,20,30]}};
            var now = Date.parse("2026-10-27T23:30:00Z");
            JSON.stringify({next:hours(weather,"",now), chosen:hours(weather,"2026-10-27",now)});
        ''')
        self.assertEqual([h["temperature"] for h in result["next"]], [8, 7])
        self.assertEqual([h["temperature"] for h in result["chosen"]], [10])

    def test_missing_values_remain_unknown_and_old_summary_can_still_be_shown(self):
        result = self.evaluate('''
            JSON.stringify({missing:number(null,"°"), zero:number(0,"%"), invalid:number(NaN,"°"),
                sunrise:clock(null), old:hours({daily:{time:["2026-10-27"]}},"",Date.now()),
                days:days({daily:{time:["2026-10-27"],temperature_2m_max:[11]}})});
        ''')
        self.assertEqual([result["missing"], result["invalid"], result["sunrise"]], ["—"] * 3)
        self.assertEqual(result["zero"], "0%")
        self.assertEqual(result["old"], [])
        self.assertEqual(result["days"][0]["high"], 11)
        self.assertIsNone(result["days"][0]["rain"])


if __name__ == "__main__":
    unittest.main()
