#!/usr/bin/python3
"""Add conservative English suggestion priorities to the image's dictionaries."""
from pathlib import Path
import re
import sys

LANGUAGES = ("en_US", "en_GB", "en_CA", "en_AU")


def replacements(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2 or not re.fullmatch("[a-z]+", fields[0]) or not re.fullmatch("[A-Za-z'_]+", fields[1]):
            raise ValueError(f"Invalid English replacement: {line!r}")
        rows.append(f"REP ^{fields[0]}$ {fields[1]}")
        # Hunspell's initial-capital path treats the pronoun I specially and
        # otherwise puts "In"/"I" before "I'm" for "Im".
        if fields[1].startswith("I'"):
            rows.append(f"REP ^{fields[0].capitalize()}$ {fields[1]}")
    if len(rows) != len(set(rows)):
        raise ValueError("Duplicate English replacements")
    return rows


def patched(text, additions):
    lines = text.splitlines()
    if not any(line in ("SET UTF-8", "SET ISO8859-1") for line in lines):
        raise ValueError("Unexpected English dictionary encoding")
    headers = [i for i, line in enumerate(lines) if re.fullmatch(r"REP \d+", line)]
    if len(headers) != 1:
        raise ValueError("Expected one Hunspell replacement table")
    start = headers[0]
    count = int(lines[start].split()[1])
    existing = [line for line in lines if line.startswith("REP ") and not re.fullmatch(r"REP \d+", line)]
    if len(existing) != count:
        raise ValueError("Hunspell replacement table count is incorrect")
    extra = [line for line in additions if line not in existing]
    if not extra:
        return text
    lines[start:start + 1] = [f"REP {count + len(extra)}", *extra]
    return "\n".join(lines) + "\n"


def main(directory):
    additions = replacements(Path(__file__).with_name("english-replacements.txt"))
    # Prepare every file first: a changed upstream format must stop the image
    # build, not silently leave only some regional dictionaries updated.
    changes = []
    for language in LANGUAGES:
        path = directory / f"{language}.aff"
        # Latin-1 is a reversible byte view, not a conversion of the dictionary:
        # Fedora's British dictionary still uses ISO8859-1; the others use UTF-8.
        # Only ASCII REP lines change, preserving every existing non-ASCII byte.
        old = path.read_bytes().decode("latin-1")
        changes.append((path, old, patched(old, additions)))
    for path, old, new in changes:
        if new != old:
            path.write_bytes(new.encode("latin-1"))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) == 2 else Path("/usr/share/hunspell"))
