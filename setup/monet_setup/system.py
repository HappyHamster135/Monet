"""Languages, keyboards and time zones Monet Setup offers.

Each language brings a sensible keyboard and time zone, so most people only
pick one thing. The time zone is refined from the internet once Wi-Fi works.
"""

import json
import re
import unicodedata
import urllib.request

from .words import N_

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
    ("Magyar", "hu_HU.UTF-8", "hu", "Europe/Budapest"),
    ("Română", "ro_RO.UTF-8", "ro", "Europe/Bucharest"),
    ("Ελληνικά", "el_GR.UTF-8", "gr", "Europe/Athens"),
    ("Português (Brasil)", "pt_BR.UTF-8", "br", "America/Sao_Paulo"),
    ("Português", "pt_PT.UTF-8", "pt", "Europe/Lisbon"),
    ("Türkçe", "tr_TR.UTF-8", "tr", "Europe/Istanbul"),
    ("Русский", "ru_RU.UTF-8", "ru", "Europe/Moscow"),
    ("Українська", "uk_UA.UTF-8", "ua", "Europe/Kyiv"),
    ("Bahasa Indonesia", "id_ID.UTF-8", "us", "Asia/Jakarta"),
    ("Tiếng Việt", "vi_VN.UTF-8", "us", "Asia/Ho_Chi_Minh"),
    ("ไทย", "th_TH.UTF-8", "th", "Asia/Bangkok"),
    ("हिन्दी", "hi_IN.UTF-8", "us", "Asia/Kolkata"),
    ("العربية", "ar_EG.UTF-8", "ara", "Africa/Cairo"),
    ("עברית", "he_IL.UTF-8", "il", "Asia/Jerusalem"),
    ("日本語", "ja_JP.UTF-8", "jp", "Asia/Tokyo"),
    ("한국어", "ko_KR.UTF-8", "kr", "Asia/Seoul"),
    ("中文 (简体)", "zh_CN.UTF-8", "us", "Asia/Shanghai"),
    ("中文 (繁體)", "zh_TW.UTF-8", "us", "Asia/Taipei"),
]

# (name shown, XKB layout, XKB variant)
KEYBOARDS = [
    (N_("English (US)"), "us", ""),
    (N_("English (US, international)"), "us", "intl"),
    (N_("English (UK)"), "gb", ""),
    (N_("Swedish"), "se", ""),
    (N_("German"), "de", ""),
    (N_("French"), "fr", ""),
    (N_("Spanish"), "es", ""),
    (N_("Italian"), "it", ""),
    (N_("Norwegian"), "no", ""),
    (N_("Danish"), "dk", ""),
    (N_("Finnish"), "fi", ""),
    (N_("Polish"), "pl", ""),
    (N_("Czech"), "cz", ""),
    (N_("Hungarian"), "hu", ""),
    (N_("Romanian"), "ro", ""),
    (N_("Greek"), "gr", ""),
    (N_("Portuguese (Brazil)"), "br", ""),
    (N_("Portuguese"), "pt", ""),
    (N_("Turkish"), "tr", ""),
    (N_("Russian"), "ru", ""),
    (N_("Ukrainian"), "ua", ""),
    (N_("Thai"), "th", ""),
    (N_("Arabic"), "ara", ""),
    (N_("Hebrew"), "il", ""),
    (N_("Japanese"), "jp", ""),
    (N_("Korean"), "kr", ""),
]


# Keyboards without Latin letters come with the US one too, Alt+Shift switching
# between them as on Windows: Wi-Fi passwords and web addresses need Latin letters.
NON_LATIN = {"ru", "ua", "gr", "th", "ara", "il"}


def xkb(layout, variant):
    """The XKB layouts, variants and options for a keyboard."""
    if layout in NON_LATIN:
        return f"{layout},us", f"{variant},", "grp:alt_shift_toggle"
    return layout, variant, ""


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
