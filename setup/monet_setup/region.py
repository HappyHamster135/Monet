"""Offline regional defaults from the city in tzdata, independent of UI language.

Also installed as monet_region.py beside Monet's desktop helpers.
"""
import json
from functools import lru_cache
import os
from pathlib import Path
import re


@lru_cache(maxsize=256)
def settings(zone, language, table=Path('/usr/share/zoneinfo/zone.tab')):
    result = {'locale': language, 'weather': None}
    # zone.tab keeps cities which zone1970.tab merges across countries.
    for path in dict.fromkeys((table, table.with_name('zone1970.tab'))):
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            fields = line.split('\t')
            if len(fields) < 3 or fields[2] != zone:
                continue
            from PySide6.QtCore import QLocale
            country = fields[0].split(',')[0]
            territory = QLocale.codeToTerritory(country)
            regional = QLocale(QLocale.AnyLanguage, territory)
            # Use an existing language/territory pair when available. Otherwise
            # the country's primary locale gives libc and Qt the same format.
            matches = QLocale.matchingLocales(QLocale(language).language(), QLocale.AnyScript, territory)
            locale = matches[0] if matches else regional
            result['locale'] = locale.name() + '.UTF-8'
            match = re.fullmatch(r'([+-]\d{4}(?:\d{2})?)([+-]\d{5}(?:\d{2})?)', fields[1])
            if not match:
                return result

            def degrees(value, digits):
                number = value[1:]
                angle = int(number[:digits]) + int(number[digits:digits + 2]) / 60
                if len(number) > digits + 2:
                    angle += int(number[digits + 2:]) / 3600
                return -angle if value[0] == '-' else angle

            result['weather'] = dict(place=zone.rsplit('/', 1)[-1].replace('_', ' '),
                latitude=degrees(match[1], 2), longitude=degrees(match[2], 3), places=[],
                # CLDR measurementData's temperature overrides (LR uses Celsius).
                fahrenheit=country in {'US', 'BS', 'BZ', 'KY', 'PR', 'PW'})
            result['weather']['places'] = [dict(name=result['weather']['place'],
                latitude=result['weather']['latitude'], longitude=result['weather']['longitude'])]
            return result
    return result


def current_zone(localtime=Path('/etc/localtime')):
    try:
        return str(localtime.resolve(strict=True)).split('zoneinfo/', 1)[1].removeprefix('posix/')
    except (OSError, IndexError):
        return 'UTC'


def seed_weather(config, defaults):
    """Exclusive creation: a saved place or unit choice always wins."""
    path = config / 'monet/weather.json'
    if defaults['weather'] is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, 'w') as stream:
        json.dump(defaults['weather'], stream, ensure_ascii=False)
