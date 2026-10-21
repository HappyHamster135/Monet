"""Turns the Fedora installer's start menu into Monet's.

    python3 tools/patch-grub.py grub.cfg [more grub.cfg files...]

- The first entry becomes "Install Monet and Windows (erases this PC)".
- A second entry, "Install Monet next to my Windows", adds `monet.keep`.
- Other "Fedora" titles say Monet, and the first entry is the default.
"""

import re
import sys

ERASE = "Install Monet and Windows (erases this PC)"
KEEP = "Install Monet next to my Windows"


def patch(text):
    entry = re.search(r"menuentry '([^']*)'[^\n]*\{.*?\n\}", text, re.S)
    if not entry:
        raise SystemExit("no menu entry found")
    block, title = entry.group(0), entry.group(1)
    erase = block.replace(f"'{title}'", f"'{ERASE}'", 1)
    keep = block.replace(f"'{title}'", f"'{KEEP}'", 1)
    keep, added = re.subn(r"(\n\s*linux(?:efi)?\s+[^\n]+)", r"\1 monet.keep", keep, count=1)
    if not added:
        raise SystemExit("no linux line in the first entry")
    text = text.replace(block, erase + "\n" + keep, 1)
    text = re.sub(r"(menuentry '[^']*?)Fedora(?: Linux)?(?: \d+)?", r"\1Monet", text)
    text, defaults = re.subn(r'set default="?\d+"?', 'set default="0"', text)
    if not defaults:
        text = 'set default="0"\n' + text
    return text


if __name__ == "__main__":
    for path in sys.argv[1:]:
        with open(path) as f:
            patched = patch(f.read())
        with open(path, "w") as f:
            f.write(patched)
        print(f"patched {path}")
