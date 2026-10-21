"""Languages, keyboards and time zones Monet Setup offers.

Each language brings a sensible keyboard and time zone, so most people only
pick one thing. The time zone is refined from the internet once Wi-Fi works.
"""

import json
import re
import unicodedata
import urllib.request

# (name shown, locale, keyboard, time zone)
LANGUAGES = [
    ("English (United States)", "en_US.UTF-8", "us", "America/New_York"),
    ("English (United Kingdom)", "en_GB.UTF-8", "gb", "Europe/London"),
    ("Svenska", "sv_SE.UTF-8", "se", "Europe/Stockholm"),
    ("Deutsch", "de_DE.UTF-8", "de", "Europe/Berlin"),
    ("Français", "fr_FR.UTF-8", "fr", "Europe/Paris"),
    ("Español", "es_ES.UTF-8", "es", "Europe/Madrid"),
    ("Italiano", "it_IT.UTF-8", "it", "Europe/Rome"),
    ("Nederlands", "nl_NL.UTF-8", "us", "Europe/Amsterdam"),
    ("Norsk bokmål", "nb_NO.UTF-8", "no", "Europe/Oslo"),
    ("Dansk", "da_DK.UTF-8", "dk", "Europe/Copenhagen"),
    ("Suomi", "fi_FI.UTF-8", "fi", "Europe/Helsinki"),
    ("Polski", "pl_PL.UTF-8", "pl", "Europe/Warsaw"),
    ("Čeština", "cs_CZ.UTF-8", "cz", "Europe/Prague"),
    ("Português (Brasil)", "pt_BR.UTF-8", "br", "America/Sao_Paulo"),
    ("Português", "pt_PT.UTF-8", "pt", "Europe/Lisbon"),
    ("Türkçe", "tr_TR.UTF-8", "tr", "Europe/Istanbul"),
    ("Русский", "ru_RU.UTF-8", "ru", "Europe/Moscow"),
    ("日本語", "ja_JP.UTF-8", "jp", "Asia/Tokyo"),
    ("한국어", "ko_KR.UTF-8", "kr", "Asia/Seoul"),
    ("中文 (简体)", "zh_CN.UTF-8", "us", "Asia/Shanghai"),
]

# (name shown, XKB layout, XKB variant)
KEYBOARDS = [
    ("English (US)", "us", ""),
    ("English (US, international)", "us", "intl"),
    ("English (UK)", "gb", ""),
    ("Swedish", "se", ""),
    ("German", "de", ""),
    ("French", "fr", ""),
    ("Spanish", "es", ""),
    ("Italian", "it", ""),
    ("Norwegian", "no", ""),
    ("Danish", "dk", ""),
    ("Finnish", "fi", ""),
    ("Polish", "pl", ""),
    ("Czech", "cz", ""),
    ("Portuguese (Brazil)", "br", ""),
    ("Portuguese", "pt", ""),
    ("Turkish", "tr", ""),
    ("Russian", "ru", ""),
    ("Japanese", "jp", ""),
    ("Korean", "kr", ""),
]


def keyboard_for(language_index):
    """The keyboard that goes with a language."""
    layout = LANGUAGES[language_index][2]
    return next(i for i, k in enumerate(KEYBOARDS) if k[1] == layout and not k[2])


def guess_time_zone(fallback, timeout=6):
    """The time zone where this PC is, from Fedora's location service (the one
    Fedora's installer uses); the language's own guess if that can't answer."""
    try:
        with urllib.request.urlopen("https://geoip.fedoraproject.org/city", timeout=timeout) as r:
            zone = json.load(r).get("time_zone")
        if zone and "/" in zone:
            return zone
    except (OSError, ValueError):
        pass
    return fallback


def account_name(full_name):
    """The sign-in name: the first name, lower case, plain letters."""
    first = (full_name.strip().split() or [""])[0].lower()
    ascii_only = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode()
    plain = re.sub(r"[^a-z0-9]", "", ascii_only)
    if not plain or not plain[0].isalpha():
        plain = "player" + plain
    return plain[:32]
