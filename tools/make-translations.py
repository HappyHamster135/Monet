"""Monet in many languages: gathers every word Monet shows, keeps the
translations in po/, and builds what Monet installs from them.

    python3 tools/make-translations.py          gather (po/monet.pot), merge each po/<language>.po, build
    python3 tools/make-translations.py --check  fail if the catalog is behind the sources or a
                                                translation breaks a %1 (tests run this)

What it gathers, and where each is said in your language:
  - the Plasma widgets, Monet Settings and Monet's screens (QML i18n*, KDE's
    catalogs: plasma_applet_<widget>.mo and monet.mo, linked by install.sh);
  - Monet Setup (tr/trc/setup.say in its QML, _/tr/trc/ntr/N_ in its Python:
    setup/locale/<language>/LC_MESSAGES/monet-setup.mo);
  - monet-quick (tr/_) and the scripts' `say "..."` (monet-quick says them);
  - the menu's plain names (monet-look: share/monet/names.tsv);
  - Monet's menu entries and its widgets' names (written into the .desktop
    and metadata.json files as Name[language] and so on);
  - the monet tool's messages (t!(...), said through monet-quick) and the USB
    stick maker's (tr/trf/t!, built into it: crates/monet-usb/src/words_table.rs).

Placeholders are %1, %2... everywhere, so translators meet one convention.
Needs only Python.
"""

import argparse
import ast
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "po"
POT = PO / "monet.pot"
LOCALE = ROOT / "linux" / "share" / "locale"
SETUP_LOCALE = ROOT / "setup" / "locale"
NAMES = ROOT / "linux" / "share" / "monet" / "names.tsv"
USB_TABLE = ROOT / "crates" / "monet-usb" / "src" / "words_table.rs"

# The languages Monet speaks, most spoken first, with how each counts (gettext's Plural-Forms).
ONE = "nplurals=1; plural=0;"
TWO = "nplurals=2; plural=(n != 1);"
TWO_FR = "nplurals=2; plural=(n > 1);"
EAST_SLAVIC = ("nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);")
LANGUAGES = {
    "es": ("Spanish", TWO),
    "zh_CN": ("Chinese (Simplified)", ONE),
    "pt_BR": ("Portuguese (Brazil)", TWO_FR),
    "fr": ("French", TWO_FR),
    "de": ("German", TWO),
    "ru": ("Russian", EAST_SLAVIC),
    "ja": ("Japanese", ONE),
    "ko": ("Korean", ONE),
    "it": ("Italian", TWO),
    "tr": ("Turkish", TWO),
    "pl": ("Polish", "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"),
    "nl": ("Dutch", TWO),
    "id": ("Indonesian", ONE),
    "vi": ("Vietnamese", ONE),
    "uk": ("Ukrainian", EAST_SLAVIC),
    "zh_TW": ("Chinese (Traditional)", ONE),
    "ar": ("Arabic", "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5);"),
    "hi": ("Hindi", TWO),
    "th": ("Thai", ONE),
    "sv": ("Swedish", TWO),
    "cs": ("Czech", "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;"),
    "pt": ("Portuguese (Portugal)", TWO),
    "ro": ("Romanian", "nplurals=3; plural=(n==1 ? 0 : (n==0 || (n%100 > 0 && n%100 < 20)) ? 1 : 2);"),
    "hu": ("Hungarian", TWO),
    "el": ("Greek", TWO),
    "da": ("Danish", TWO),
    "fi": ("Finnish", TWO),
    "nb": ("Norwegian (Bokmål)", TWO),
    "he": ("Hebrew", TWO),
}

# Context for words that stand alone in menus and widget lists.
MENU_NAME = "an app's name in the menu"
MENU_KEYS = {"Name": MENU_NAME, "GenericName": "what an app is, under its name in the menu",
             "Comment": "an app's description in the menu",
             "Keywords": "words the menu's search finds an app by; keep the semicolons between them"}
PLUGIN_KEYS = {"Name": "the name of a part of Monet (a widget, a style, a painting) in KDE's lists",
               "Description": "what a part of Monet is, in KDE's lists"}


# Reading string literals --------------------------------------------------------

def js_string(text, i):
    """The JavaScript/QML string literal starting at text[i] (a quote): (value, index after it)."""
    quote, out, i = text[i], [], i + 1
    while text[i] != quote:
        c = text[i]
        if c == "\\":
            n = text[i + 1]
            if n == "u":
                out.append(chr(int(text[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append({"n": "\n", "t": "\t", "r": "\r", "\n": ""}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out), i + 1


def rust_string(text, i):
    """The Rust string literal at text[i]: escapes, and a backslash at a line's end that skips to the next words."""
    out, i = [], i + 1
    while text[i] != '"':
        c = text[i]
        if c == "\\":
            n = text[i + 1]
            if n == "\n" or (n == "\r" and text[i + 2] == "\n"):
                i += 2 if n == "\n" else 3
                while text[i] in " \t\r\n":
                    i += 1
                continue
            if n == "u":
                end = text.index("}", i)
                out.append(chr(int(text[i + 3:end], 16)))
                i = end + 1
                continue
            out.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out), i + 1


def python_string(text, i):
    """A Python string literal at text[i] (prefixes aside), via Python itself."""
    quote = text[i]
    j = i + 1
    while text[j] != quote:
        j += 2 if text[j] == "\\" else 1
    return ast.literal_eval(text[i:j + 1]), j + 1


def literals(text, i, read, count):
    """count string literals separated by commas from text[i] on, skipping spaces and a
    first domain argument already consumed by the caller; joins "a" + "b". None if the
    arguments aren't literals."""
    found = []
    while len(found) < count:
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        if i >= len(text) or text[i] not in "\"'":
            return None
        value, i = read(text, i)
        # "a" + "b": one sentence over two lines.
        while True:
            j = i
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            if j < len(text) and text[j] == "+":
                k = j + 1
                while text[k] in " \t\r\n":
                    k += 1
                if text[k] in "\"'":
                    more, i = read(text, k)
                    value += more
                    continue
            break
        found.append(value)
    return found


def line_of(text, i):
    return text.count("\n", 0, i) + 1


# What each kind of source marks ----------------------------------------------------

# (call, how many literals: context?, plural?) for KDE's i18n family and Setup's QML.
QML_CALLS = {"i18n": "s", "i18nc": "cs", "i18np": "sp", "i18ncp": "csp",
             "i18nd": "ds", "i18ndc": "dcs", "i18ndp": "dsp", "i18ndcp": "dcsp"}
SETUP_QML_CALLS = {"tr": "s", "trc": "cs", "setup.say": "s", "setup.sayIn": "cs"}
PYTHON_CALLS = {"_": "s", "N_": "s", "tr": "s", "trc": "cs", "ntr": "sp"}
RUST_CALLS = {"t!": "s", "tr": "s", "trf": "s", "say": "s"}


def scan(text, calls, read, path, add):
    names = "|".join(re.escape(c) for c in sorted(calls, key=len, reverse=True))
    for m in re.finditer(r"(?<![\w.])(" + names + r")\s*\(", text):
        shape = calls[m.group(1)]
        args = literals(text, m.end(), read, len(shape))
        if args is None:
            continue
        parts = dict(zip(shape, args))
        if "d" in parts and parts["d"] != "monet":
            continue  # another catalog's words (KDE's own lock screen)
        add(parts.get("c"), parts["s"], parts.get("p"), f"{path}:{line_of(text, m.start())}")


def gather():
    """Every word Monet shows: {(context, text): {"plural": ..., "refs": [...]}}, in order found."""
    found = {}

    def add(context, text, plural, ref):
        if not text.strip():
            return
        entry = found.setdefault((context or None, text), {"plural": None, "refs": []})
        entry["plural"] = entry["plural"] or plural
        entry["refs"].append(ref)

    def rel(p):
        return p.relative_to(ROOT).as_posix()

    qml = sorted(set((ROOT / "linux").rglob("*.qml")) | set((ROOT / "image").rglob("*.qml")))
    for p in qml:
        scan(p.read_text(encoding="utf-8"), QML_CALLS, js_string, rel(p), add)
    for p in sorted((ROOT / "setup" / "qml").glob("*.qml")):
        scan(p.read_text(encoding="utf-8"), SETUP_QML_CALLS, js_string, rel(p), add)
    for p in sorted((ROOT / "setup" / "monet_setup").glob("*.py")) + [ROOT / "linux/libexec/monet-quick"]:
        scan(p.read_text(encoding="utf-8"), PYTHON_CALLS, python_string, rel(p), add)
    # The Windows helper's progress lines, which the person's dialog says.
    prep = ROOT / "linux/libexec/monet-prepare-windows"
    text = prep.read_text(encoding="utf-8")
    for m in re.finditer(r"\bprogress\(\s*[^,]+,\s*", text):
        args = literals(text, m.end(), python_string, 1)
        if args:
            add(None, args[0], None, f"{rel(prep)}:{line_of(text, m.start())}")
    # The scripts' notifications.
    for p in sorted((ROOT / "linux/libexec").iterdir()):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'(?<![\w-])say "', text):
            value, _ = js_string(text, m.end() - 1)
            if "$" not in value:
                add(None, value, None, f"{rel(p)}:{line_of(text, m.start())}")
    # The menu's plain names.
    look = ROOT / "linux/libexec/monet-look"
    text = look.read_text(encoding="utf-8")
    for m in re.finditer(r'"[\w-]+\.[\w.-]+:([A-Z][^"]*)"', text):  # "org.kde.dolphin:Files"
        add(MENU_NAME, m.group(1), None, f"{rel(look)}:{line_of(text, m.start())}")
    for m in re.finditer(r'rename "[^"]+" (\w+|"[^"]*") "([^"]+)"', text):
        add(MENU_NAME, m.group(1).strip('"'), None, f"{rel(look)}:{line_of(text, m.start())}")
        add(MENU_KEYS["Comment"], m.group(2), None, f"{rel(look)}:{line_of(text, m.start())}")
    # Menu entries and the widgets' names.
    for p in sorted((ROOT / "linux/share/applications").glob("*.desktop")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            key, _, value = line.partition("=")
            if key in MENU_KEYS and value:
                add(MENU_KEYS[key], value, None, f"{rel(p)}:{n}")
    for p in plugin_metadata():
        plugin = json.loads(p.read_text(encoding="utf-8")).get("KPlugin", {})
        for key, context in PLUGIN_KEYS.items():
            if plugin.get(key):
                add(context, plugin[key], None, rel(p))
    # The monet tool and the USB stick maker.
    for crate in ("monet", "monet-usb"):
        for p in sorted((ROOT / "crates" / crate / "src").glob("*.rs")):
            text = p.read_text(encoding="utf-8")
            cut = text.find("#[cfg(test)]")
            scan(text[:cut] if cut >= 0 else text, RUST_CALLS, rust_string, rel(p), add)
    return found


def plugin_metadata():
    return sorted(p for p in (ROOT / "linux/share/plasma").glob("*/*/metadata.json"))


# po files -------------------------------------------------------------------------

def po_quote(text):
    s = text.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\r", "\\r")
    if "\n" in s.rstrip("\n") or len(s) > 70:
        lines = s.split("\n")
        parts = [l + "\\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
        return '""\n' + "\n".join(f'"{p}"' for p in parts)
    return '"' + s.replace("\n", "\\n") + '"'


def header(language=None):
    fields = ["Project-Id-Version: Monet", "MIME-Version: 1.0", "Content-Type: text/plain; charset=UTF-8",
              "Content-Transfer-Encoding: 8bit"]
    if language:
        fields += [f"Language: {language}", f"Plural-Forms: {LANGUAGES[language][1]}"]
    return "".join(f + "\n" for f in fields)


def write_po(path, entries, language=None, translations=None):
    out = ['# Monet\'s words' + (f" in {LANGUAGES[language][0]}" if language else "") + '.',
           '# Gathered by tools/make-translations.py; %1, %2... stand for what is filled in.',
           'msgid ""', 'msgstr ' + po_quote(header(language)), ""]
    nplurals = int(re.search(r"nplurals=(\d+)", LANGUAGES[language][1]).group(1)) if language else 2
    for (context, text), entry in entries.items():
        refs = entry["refs"]
        for i in range(0, len(refs), 3):
            out.append("#: " + " ".join(refs[i:i + 3]))
        if context:
            out.append("msgctxt " + po_quote(context))
        out.append("msgid " + po_quote(text))
        said = (translations or {}).get((context, text), {})
        if entry["plural"]:
            out.append("msgid_plural " + po_quote(entry["plural"]))
            forms = said.get("forms") or []
            for n in range(nplurals):
                out.append(f"msgstr[{n}] " + po_quote(forms[n] if n < len(forms) else ""))
        else:
            out.append("msgstr " + po_quote(said.get("text", "")))
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def read_po(path):
    """{(context, text): {"text": ..., "forms": [...], "plural": ...}} from a po file (the header aside)."""
    entries, current, last = {}, {}, None

    def flush():
        if "msgid" in current and current["msgid"]:
            key = (current.get("msgctxt"), current["msgid"])
            forms = [current[f"msgstr[{n}]"] for n in range(10) if f"msgstr[{n}]" in current]
            entries[key] = {"text": current.get("msgstr", ""), "forms": forms, "plural": current.get("msgid_plural"),
                            "fuzzy": current.get("fuzzy", False)}

    for raw in path.read_text(encoding="utf-8").splitlines() + [""]:
        line = raw.strip()
        if not line:
            flush()
            current, last = {}, None
            continue
        if line.startswith("#,") and "fuzzy" in line:
            current["fuzzy"] = True
        if line.startswith("#"):
            continue
        m = re.match(r'^(msgctxt|msgid_plural|msgid|msgstr\[\d+\]|msgstr)\s+(".*")$', line)
        if m:
            last = m.group(1)
            current[last] = ast.literal_eval(m.group(2))
        elif line.startswith('"') and last:
            current[last] += ast.literal_eval(line)
    return entries


# Building -------------------------------------------------------------------------

def placeholders(text):
    return set(re.findall(r"%\d", text))


def usable(entry, said):
    """The translation, if it's there, not doubtful, and keeps every %1 of the English."""
    if not said or said.get("fuzzy"):
        return None
    if entry["plural"]:
        forms = said.get("forms") or []
        if not forms or not all(forms):
            return None
        return forms
    return said.get("text") or None


def write_mo(path, catalog, language):
    """A GNU .mo file: the header, then each (context + \\x04 +) text with its translation, sorted."""
    pairs = {b"": header(language).encode()}
    for (context, text), (plural, said) in catalog.items():
        key = ((context + "\x04") if context else "") + text + (("\0" + plural) if plural else "")
        value = "\0".join(said) if isinstance(said, list) else said
        pairs[key.encode()] = value.encode()
    keys = sorted(pairs)
    n = len(keys)
    start = 7 * 4 + n * 16
    ids = b"".join(k + b"\0" for k in keys)
    strs = b"".join(pairs[k] + b"\0" for k in keys)
    table, offset = [], start
    for k in keys:
        table.append((len(k), offset))
        offset += len(k) + 1
    trans, offset = [], start + len(ids)
    for k in keys:
        trans.append((len(pairs[k]), offset))
        offset += len(pairs[k]) + 1
    head = struct.pack("<7I", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    body = b"".join(struct.pack("<2I", *t) for t in table) + b"".join(struct.pack("<2I", *t) for t in trans)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(head + body + ids + strs)


def build(entries):
    names, usb = [], {}
    menus = {}  # (context, English) -> {language: translation}
    for language in LANGUAGES:
        po = PO / f"{language}.po"
        if not po.exists():
            continue
        said = read_po(po)
        everything, setup = {}, {}
        for key, entry in entries.items():
            translation = usable(entry, said.get(key))
            if translation is None:
                continue
            everything[key] = (entry["plural"], translation)
            if any(r.startswith("setup/") for r in entry["refs"]):
                setup[key] = (entry["plural"], translation)
            if key[0] in (MENU_NAME, *MENU_KEYS.values(), *PLUGIN_KEYS.values()):
                menus.setdefault(key, {})[language] = translation
            if any(r.startswith("crates/monet-usb/") for r in entry["refs"]) and not entry["plural"]:
                usb.setdefault(language, []).append((key[1], translation))
            if key[0] == MENU_NAME and any(r.startswith("linux/libexec/monet-look") for r in entry["refs"]):
                names.append((key[1], language, translation))
            if key[0] == MENU_KEYS["Comment"] and any(r.startswith("linux/libexec/monet-look") for r in entry["refs"]):
                names.append((key[1], language, translation))
        write_mo(LOCALE / language / "LC_MESSAGES" / "monet.mo", everything, language)
        write_mo(SETUP_LOCALE / language / "LC_MESSAGES" / "monet-setup.mo", setup, language)
    NAMES.write_text("".join(f"{e}\t{l}\t{t}\n" for e, l, t in sorted(names)), encoding="utf-8", newline="\n")
    write_usb_table(usb)
    localize_menu_entries(menus)
    localize_plugins(menus)


def rust_quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def write_usb_table(usb):
    out = ["// The USB stick maker's words in each language Monet speaks: written by",
           "// tools/make-translations.py from po/ (change the translations there).",
           "",
           "pub static TABLE: &[(&str, &[(&str, &str)])] = &["]
    for language in sorted(usb):
        out.append(f"    (\n        {rust_quote(language)},\n        &[")
        for english, said in sorted(usb[language]):
            out.append(f"            ({rust_quote(english)}, {rust_quote(said)}),")
        out.append("        ],\n    ),")
    out.append("];\n")
    USB_TABLE.write_text("\n".join(out), encoding="utf-8", newline="\n")


def localize_menu_entries(menus):
    """Name[language]= and the like, under each key of Monet's own menu entries."""
    for p in sorted((ROOT / "linux/share/applications").glob("*.desktop")):
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if not re.match(r"^(Name|GenericName|Comment|Keywords)\[", l)]
        out = []
        for line in lines:
            out.append(line)
            key, _, value = line.partition("=")
            if key in MENU_KEYS and value:
                for language, said in sorted(menus.get((MENU_KEYS[key], value), {}).items()):
                    out.append(f"{key}[{language}]={said}")
        p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def localize_plugins(menus):
    """KPlugin's Name[language] and Description[language] in each metadata.json, each on a
    line under its English one, so the file keeps its own layout."""
    for p in plugin_metadata():
        lines = [l for l in p.read_text(encoding="utf-8").splitlines()
                 if not re.match(r'^\s*"(Name|Description)\[[\w@]+\]": ', l)]
        # KPlugin's own keys sit beside its Id (an author's Name is deeper).
        plugin = next(re.match(r'^(\s*)"Id": ', l).group(1) for l in lines if re.match(r'^\s*"Id": ', l))
        out = []
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)"(Name|Description)": ("(?:[^"\\]|\\.)*"),?$', line)
            if not m:
                out.append(line)
                continue
            indent, key, english = m.groups()
            # A comma unless it's the last in its object (an earlier run may have added one).
            comma = "" if i + 1 < len(lines) and lines[i + 1].strip().startswith("}") else ","
            said = sorted((language, text) for language, text in
                          menus.get((PLUGIN_KEYS[key], json.loads(english)), {}).items()
                          if text != json.loads(english)) if indent == plugin else []
            out.append(f'{indent}"{key}": {english}' + ("," if said else comma))
            for n, (language, text) in enumerate(said):
                last = n == len(said) - 1
                out.append(f'{indent}"{key}[{language}]": {json.dumps(text, ensure_ascii=False)}' + (comma if last else ","))
        text = "\n".join(out) + "\n"
        json.loads(text)  # still JSON
        p.write_text(text, encoding="utf-8", newline="\n")


# Checking -------------------------------------------------------------------------

def check(entries):
    """Problems: a catalog behind its sources, or a translation that drops or invents a %1."""
    problems = []
    if not POT.exists() or set(read_po(POT)) != set(entries):
        problems.append("po/monet.pot is behind the sources: run python3 tools/make-translations.py")
    for language in LANGUAGES:
        po = PO / f"{language}.po"
        if not po.exists():
            continue
        said = read_po(po)
        for key, entry in entries.items():
            got = said.get(key)
            if not got or got.get("fuzzy"):
                continue
            wanted = placeholders(key[1]) | placeholders(entry["plural"] or "")
            texts = (got.get("forms") or []) if entry["plural"] else [got.get("text") or ""]
            for t in texts:
                # A plural's form for exactly one may say "one" instead of %1.
                need = wanted - ({"%1"} if entry["plural"] else set())
                if t and (not need <= placeholders(t) or not placeholders(t) <= wanted):
                    problems.append(f"{language}: {key[1]!r} -> {t!r} changes its placeholders")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    entries = gather()
    if args.check:
        problems = check(entries)
        for p in problems:
            print(p)
        sys.exit(1 if problems else 0)
    PO.mkdir(exist_ok=True)
    write_po(POT, entries)
    # Every language gets its file, with what's translated kept and what's new left to do.
    for language in LANGUAGES:
        po = PO / f"{language}.po"
        write_po(po, entries, language, read_po(po) if po.exists() else {})
    build(entries)
    done = {}
    for language in LANGUAGES:
        said = read_po(PO / f"{language}.po")
        done[language] = sum(1 for k, e in entries.items() if usable(e, said.get(k)))
    print(f"{len(entries)} texts;", ", ".join(f"{l} {n}" for l, n in done.items()) or "no translations yet")


if __name__ == "__main__":
    main()
