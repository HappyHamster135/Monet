"""Text results for the desktop command bar. Read each source only in its own search."""
import hashlib
import json
from functools import lru_cache
from io import BytesIO
from struct import Struct, error as StructError
import zlib
from pathlib import Path
import re
import shutil
import subprocess

import dbus

from actions import stored, tr, words
from color_values import conversion, parse_color

KLIPPER = "org.kde.klipper"
SCOPES = {"snippet": "snippets", "clip": "clipboard", "emoji": "emoji", "menu": "command-bar", "script": "scripts"}


def command_query(query, tool_prefixes):
    head, separator, tail = query.partition(":")
    if not separator:
        return None
    head = head.strip()
    prefix, space, keyword = head.rpartition(" ")
    if space and words(prefix) in tool_prefixes:
        head = keyword
    aliases = {tr("snippet").casefold(): "snippet", tr("clip").casefold(): "clip", tr("menu").casefold(): "menu",
               tr("script").casefold(): "script"}
    scope = aliases.get(head.casefold(), head.casefold())
    if scope in SCOPES:
        return scope, tail.strip()
    return None


def identity(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def result(key, label, icon, category, hint, score=1.0):
    return key, label, icon, 100, score, {"category": category, "subtext": hint}


@lru_cache(maxsize=64)
def color_swatch(color):
    # A checkerboard makes translucent and fully transparent colors visible on both themes.
    side = 24
    rgb = color.bytes()[:3]
    tiles = [bytes(round(c * color.alpha + background * (1 - color.alpha)) for c in rgb)
             for background in (230, 158)]
    pixels = b"".join(tiles[(x // 6 + y // 6) % 2] for y in range(side) for x in range(side))
    return dbus.Struct((side, side, side * 3, False, 8, 3, dbus.ByteArray(pixels)), signature="iiibiiay")


def color_match(query):
    converted = conversion(query)
    if converted is None:
        return None
    color, text = converted
    return ("convert-color/" + query, text, "color-picker", 100, 1.0,
            {"category": tr("Color conversion"), "subtext": tr("Copy converted color"), "icon-data": color_swatch(color)})


def measurement_match(query, scoped):
    from PySide6.QtCore import QLocale
    import measurements
    decimal = QLocale().decimalPoint()
    previous = measurements.session_answer() if measurements.ANSWER.search(query) else ''
    formula = measurements.expression(query, scoped=scoped, answer=previous, decimal=decimal)
    value = measurements.evaluate(formula, measurements.HELPER) if formula else ''
    if not value:
        return None
    # Capture the previous answer so selecting an old result still copies exactly
    # what it showed, even after another launcher updates ans or this runner exits.
    key = json.dumps([query, previous, decimal], ensure_ascii=False, separators=(',', ':'))
    label = measurements.localized(value, decimal).replace('approx. ', '≈ ', 1)
    return result('measure/' + key, label, 'accessories-calculator', tr('Calculator'),
                  tr('Copy result and use it as ans'))


def copy_measurement(ref, bus):
    import measurements
    try:
        query, previous, decimal = json.loads(ref)
        if not (isinstance(query, str) and isinstance(previous, str) and len(previous) <= 160 and decimal in ('.', ',', '٫')):
            return
    except (ValueError, TypeError):
        return
    formula = measurements.expression(query, scoped=True, answer=previous, decimal=decimal)
    value = measurements.evaluate(formula, measurements.HELPER) if formula else ''
    if not value:
        notify(bus, tr("This search result is no longer available."))
    elif copy_text(bus, measurements.localized(value.removeprefix('approx. '), decimal)):
        measurements.session_answer(value)
    else:
        notify(bus, tr("Could not copy this search result."))


def clipboard(bus):
    # Use Klipper's live session. Its text API also works when saving history to disk is off.
    return dbus.Interface(bus.get_object(KLIPPER, "/klipper", introspect=False), KLIPPER + ".klipper")


def snippets(settings, query):
    entries = stored(settings, "snippets", {})
    shortcuts = stored(settings, "snippetShortcuts", {})
    tokens = query.casefold().split()
    ranked = []
    for name, body in entries.items():
        if not isinstance(name, str) or not isinstance(body, str) or not body:
            continue
        title = name.casefold()
        shortcut = shortcuts.get(name)
        trigger = shortcut.casefold() if isinstance(shortcut, str) else ""
        if tokens and query.casefold() in (title, trigger):
            rank = 0
        elif all(term in title or term in trigger for term in tokens):
            rank = 1
        else:
            text = body.casefold()
            if not all(term in text for term in tokens):
                continue
            rank = 2
        ranked.append((rank, title, name))
    return [result("snippet/" + identity(name), name, "edit-paste", tr("Text snippets"),
                   tr("Copy snippet"), 1 - index * .01)
            for index, (_, _, name) in enumerate(sorted(ranked)[:8])]


def history(bus):
    try:
        return clipboard(bus).getClipboardHistoryMenu(timeout=1)
    except dbus.DBusException:
        return ()


class ClipboardSearch:
    """Share one history read across keystrokes while the clipboard chooser is open."""
    def __init__(self, bus):
        self.bus = bus
        self.items = None
        self.changed = bus.add_signal_receiver(self.invalidate, signal_name="clipboardHistoryUpdated",
                                               dbus_interface=KLIPPER + ".klipper", bus_name=KLIPPER, path="/klipper")
        self.owner = bus.watch_name_owner(KLIPPER, self.invalidate)

    def invalidate(self, *_):
        self.items = None

    def read(self):
        if self.items is None:
            self.items = history(self.bus)
        return self.items

    def close(self):
        self.changed.remove()
        self.owner.cancel()
        self.items = None


def clips(items, query):
    tokens = query.casefold().split()
    rows, seen = [], set()
    for index, text in enumerate(items):
        # Klipper describes images with a size marker in its plain-text interface.
        if not text or re.fullmatch(r"▨\s*\d+\s*[x×]\s*\d+", text):
            continue
        if tokens:
            folded = text.casefold()
            if not all(term in folded for term in tokens):
                continue
        digest = identity(text)
        if digest in seen:
            continue
        seen.add(digest)
        label = " ".join(text[:160].split()) or tr("Whitespace")
        if len(text) > 160:
            label += "…"
        row = result(f"clip/{index}/{digest}", label, "edit-paste", tr("Clipboard history"),
                     tr("Copy as plain text"), 1 - len(rows) * .01)
        color = parse_color(text)
        if color is not None:
            row[5]["icon-data"] = color_swatch(color)
        rows.append(row)
        if len(rows) == 8:
            break
    return rows


def emoji_dictionary(path, *, with_categories=False):
    # Plasma's emoji picker uses a fixed Qt 5.15 little-endian stream of UTF-8 strings.
    # Only system-installed dictionaries are opened. Each starts with a qCompress header.
    content = path.read_bytes()
    stream = BytesIO(zlib.decompress(content[4:]))
    size = Struct("<I")
    def number():
        return size.unpack(stream.read(4))[0]
    def string():
        return stream.read(number()).decode("utf-8")
    for _ in range(number()):
        glyph, name = string(), string()
        category = number()
        terms = " ".join(string() for _ in range(number()))
        yield (glyph, name, terms, category) if with_categories else (glyph, name, terms)


@lru_cache(maxsize=1)
def emoji_index():
    from gi.repository import GLib
    root = Path("/usr/share/plasma/emoji")
    forms = [lang.partition(".")[0].partition("@")[0] for lang in GLib.get_language_names()]
    languages = ["en"]
    for lang in dict.fromkeys(forms):
        if re.fullmatch(r"[a-zA-Z]{2,3}(?:_[A-Za-z0-9]+)*", lang) and (root / (lang + ".dict")).is_file():
            if lang != "en":
                languages.append(lang)
            break
    index = {}
    for lang in languages:
        try:
            for glyph, name, terms in emoji_dictionary(root / (lang + ".dict")):
                previous = index.get(glyph)
                keywords = (previous[3] + " " if previous else "") + terms.casefold()
                index[glyph] = (glyph, name, name.casefold(), keywords, previous[2] if previous else "")
        except (OSError, StructError, UnicodeError, zlib.error):
            continue
    return index


def emoji(query):
    index = emoji_index()
    needle = query.casefold()
    tokens = needle.split()
    if not tokens:
        matches = [index[key] for key in ("😀", "❤️", "👍", "🎉", "🙏", "✅", "🚀", "👋") if key in index]
    else:
        def score(entry):
            glyph, _, title, terms, fallback = entry
            if needle in (title, fallback) or glyph == query:
                return 0
            if title.startswith(needle) or fallback.startswith(needle):
                return 1
            if all(term in title or term in fallback for term in tokens):
                return 2
            if all(term in title or term in fallback or term in terms for term in tokens):
                return 3
            return 4
        buckets = [[], [], [], []]
        for entry in index.values():
            rank = score(entry)
            if rank < len(buckets) and len(buckets[rank]) < 8:
                buckets[rank].append(entry)
        matches = [entry for bucket in buckets for entry in bucket][:8]
    return [result("emoji/" + glyph, glyph + "  " + name, "face-smile", tr("Emoji"),
                   tr("Copy emoji"), 1 - pos * .01) for pos, (glyph, name, _, _, _) in enumerate(matches)]


def matches(scope, query, hidden, settings, clip_search):
    if SCOPES[scope] in hidden:
        return []
    if scope == "clip":
        return clips(clip_search.read(), query)
    if scope == "snippet":
        return snippets(settings, query)
    return emoji(query)


def copy_result(key, hidden, settings, bus):
    scope, _, ref = key.partition("/")
    if SCOPES.get(scope) in hidden:
        return
    if scope == "measure":
        if "command-bar" not in hidden and len(ref) <= 900:
            copy_measurement(ref, bus)
        return
    value = ""
    if scope == "convert-color":
        if "command-bar" in hidden:
            return
        converted = conversion(ref)
        if converted is None:
            return
        value = converted[1]
    elif scope == "clip":
        row, _, digest = ref.partition("/")
        if not row.isascii() or not row.isdigit() or len(row) > 8 or not re.fullmatch("[0-9a-f]{64}", digest):
            return
        try:
            value = clipboard(bus).getClipboardHistoryItem(int(row), timeout=1)
        except dbus.DBusException:
            value = ""
        if identity(value) != digest:
            # The index can change while the chooser is open. Match the exact text again.
            value = next((text for text in history(bus) if identity(text) == digest), "")
    elif scope == "snippet":
        for name, body in stored(settings, "snippets", {}).items():
            if identity(name) == ref and isinstance(body, str):
                value = body
                if stored(settings, "snippetVariables", {}).get(name) is True:
                    from snippet_variables import ClipboardUnavailable, expand
                    try:
                        value = expand(body)
                    except ClipboardUnavailable:
                        notify(bus, tr("Copy some text first."))
                        return
                break
    elif scope == "emoji":
        entry = emoji_index().get(ref)
        if entry and entry[0] == ref:
            value = ref
    if not value:
        notify(bus, tr("This search result is no longer available."))
    elif not copy_text(bus, value):
        notify(bus, tr("Could not copy this search result."))


def copy_text(bus, value):
    try:
        clipboard(bus).setClipboardContents(value, timeout=2)
        return True
    except dbus.DBusException:
        copier = shutil.which("wl-copy")
        if copier:
            try:
                subprocess.run([copier, "--type", "text/plain;charset=utf-8"], input=value.encode(),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2, check=True)
                return True
            except (OSError, subprocess.SubprocessError):
                pass
    return False


def notify(bus, notice, icon="edit-paste", body=""):
    try:
        service = "org.freedesktop.Notifications"
        proxy = bus.get_object(service, "/org/freedesktop/Notifications", introspect=False)
        proxy.Notify(tr("Command Bar"), 0, icon, notice, body,
                     dbus.Array(signature="s"), dbus.Dictionary(signature="sv"), 3500,
                     dbus_interface=service, signature="susssasa{sv}i", timeout=1)
    except dbus.DBusException:
        pass
