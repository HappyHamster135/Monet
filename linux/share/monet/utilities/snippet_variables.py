"""Expand explicitly enabled snippet variables at the moment a snippet is used."""
from functools import cache
import os
import re
import select
import subprocess
import time

from PySide6.QtCore import QDateTime, QLocale, QTimeZone

VARIABLE = re.compile(r"\{\{(?:(clipboard)|(date|time|datetime)(?:-tz\(([\w+./-]{1,128})\))?(?::([^{}\r\n]{1,128}))?)\}\}")
MAX_TEXT_BYTES = 1024 * 1024


class ClipboardUnavailable(Exception):
    """The current selection could not supply plain text."""


def current_text():
    # IBus and the search provider have no foreground Qt window. Read the
    # session's current selection, including text offered by a Wayland app.
    until = time.monotonic() + .45
    for mime in ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING"):
        with subprocess.Popen(["/usr/bin/wl-paste", "--no-newline", "--type", mime],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as reader:
            data = bytearray()
            try:
                while len(data) <= MAX_TEXT_BYTES:
                    remaining = until - time.monotonic()
                    if remaining <= 0 or not select.select([reader.stdout], [], [], remaining)[0]:
                        raise ClipboardUnavailable()
                    block = os.read(reader.stdout.fileno(), 65536)
                    if not block:
                        if reader.wait(timeout=max(.001, until - time.monotonic())) == 0 and data:
                            return data.decode("utf-8")
                        break
                    data.extend(block)
                else:
                    raise ClipboardUnavailable()
            finally:
                if reader.poll() is None:
                    reader.kill()
    raise ClipboardUnavailable()


def expand(text, read_text=current_text, *, now=None, locale=None):
    if "{{" not in text:
        return text
    now = now or QDateTime.currentDateTime()
    locale = locale or QLocale()

    @cache
    def clipboard():
        try:
            value = read_text()
        except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
            raise ClipboardUnavailable() from error
        if not value or "\0" in value:
            raise ClipboardUnavailable()
        return value

    def replace(match):
        clip, kind, zone_id, pattern = match.groups()
        if clip:
            return clipboard()
        stamp = now
        if zone_id:
            zone = QTimeZone(zone_id.encode())
            if not zone.isValid():
                return match[0]
            stamp = stamp.toTimeZone(zone)
        if pattern:
            return locale.toString(stamp, pattern)
        if kind == "date":
            return locale.toString(stamp.date(), QLocale.ShortFormat)
        if kind == "time":
            return locale.toString(stamp.time(), QLocale.ShortFormat)
        return locale.toString(stamp, QLocale.ShortFormat)

    # Substitute once. Braces in pasted text are part of that text.
    return VARIABLE.sub(replace, text)
