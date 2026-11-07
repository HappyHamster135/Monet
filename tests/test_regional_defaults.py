"""City-based defaults work offline and preserve later account choices."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'setup'))
from monet_setup import region

try:
    from PySide6.QtCore import QLocale, QTime
except ImportError:
    QLocale = None


@unittest.skipUnless(QLocale, 'Qt regional data')
class RegionalDefaults(unittest.TestCase):
    def test_city_controls_clock_and_weather_independently_of_language(self):
        for zone, language, hours24, fahrenheit, city in (
            ('Europe/Stockholm', 'en_US.UTF-8', True, False, 'Stockholm'),
            ('America/New_York', 'sv_SE.UTF-8', False, True, 'New York'),
            ('Europe/London', 'en_US.UTF-8', True, False, 'London'),
            ('America/Toronto', 'en_US.UTF-8', False, False, 'Toronto'),
            ('Pacific/Honolulu', 'sv_SE.UTF-8', False, True, 'Honolulu'),
            ('America/Nassau', 'en_US.UTF-8', False, True, 'Nassau'),
            ('Africa/Monrovia', 'en_US.UTF-8', False, False, 'Monrovia'),
        ):
            with self.subTest(zone=zone):
                defaults = region.settings(zone, language)
                clock = QLocale(defaults['locale'])
                self.assertEqual('18' in clock.toString(QTime(18, 20), QLocale.ShortFormat), hours24)
                self.assertEqual(defaults['weather']['place'], city)
                self.assertEqual(defaults['weather']['fahrenheit'], fahrenheit)
                self.assertEqual(defaults['weather']['places'][0]['name'], city)
        stockholm = region.settings('Europe/Stockholm', 'en_US.UTF-8')['weather']
        self.assertAlmostEqual(stockholm['latitude'], 59.3333, places=3)
        self.assertAlmostEqual(stockholm['longitude'], 18.05, places=3)

    def test_unknown_zone_has_no_invented_weather_location(self):
        for zone in ('UTC', 'Unknown/City'):
            self.assertEqual(region.settings(zone, 'sv_SE.UTF-8'), {'locale': 'sv_SE.UTF-8', 'weather': None})

    def test_existing_account_migrates_once_and_explicit_preferences_win(self):
        loader = importlib.machinery.SourceFileLoader('region_helper', str(ROOT / 'linux/libexec/monet-region'))
        helper = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(helper)
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)
            rc = config / 'plasma-localerc'
            rc.write_text('[Formats]\nLANG=en_US.UTF-8\n')
            with patch.dict(os.environ, XDG_CONFIG_HOME=folder), \
                 patch.object(helper.region, 'current_zone', return_value='Europe/Stockholm'):
                helper.main()
                saved = rc.read_text()
                self.assertIn('LANG=en_US.UTF-8', saved)
                locale = subprocess.check_output(['kreadconfig6', '--file', str(rc), '--group', 'Formats',
                    '--key', 'LC_TIME'], text=True).strip()
                self.assertIn('18', QLocale(locale).toString(QTime(18, 20), QLocale.ShortFormat))
                weather = config / 'monet/weather.json'
                self.assertEqual(json.loads(weather.read_text())['place'], 'Stockholm')
                self.assertEqual(weather.stat().st_mode & 0o777, 0o600)
                # A later explicit preference (including following LANG again) stays.
                rc.write_text('[Formats]\nLANG=en_US.UTF-8\n')
                weather.write_text('{"place":"Malmö","fahrenheit":true}')
                helper.main()
                self.assertNotIn('LC_TIME', rc.read_text())
                self.assertEqual(json.loads(weather.read_text())['place'], 'Malmö')
                (config / 'monet/region-defaults-v1').unlink()
                rc.write_text('[Formats]\nLANG=en_US.UTF-8\nLC_TIME=en_US.UTF-8\n')
                helper.main()
                self.assertIn('LC_TIME=en_US.UTF-8', rc.read_text())
                self.assertTrue(json.loads(weather.read_text())['fahrenheit'])
