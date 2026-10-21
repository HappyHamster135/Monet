"""Turns the Fedora installer's start menu into Monet's.

    python3 tools/patch-grub.py grub.cfg [more grub.cfg files...]

- The first entry becomes "Install Monet and Windows (erases this PC)".
- A second entry, "Install Monet next to my Windows", adds `monet.keep`.
- Other "Fedora" titles say Monet, and the first entry is the default.
- Monet's look: the theme in /EFI/BOOT/monet (image/installer/grub), loaded
  only if its fonts are there, so the plain menu still works otherwise.
- Ten seconds before it starts by itself, instead of a minute.
- Monet's entries leave NVIDIA's open-source driver off (`nouveau.modeset=0`):
  on RTX cards it can stop the installer; the screen still works without it.
"""

import re
import sys

ERASE = "Install Monet and Windows (erases this PC)"
KEEP = "Install Monet next to my Windows"
MORE = "More options"
THEME_DIR = "($root)/EFI/BOOT/monet"
# The text font loads last and is named: GRUB's text layer otherwise takes the
# newest font, and the 56px title is too wide for its 40 columns, which drops
# the whole theme ("glyphs too large to fit on screen"). With Secure Boot on,
# GRUB refuses fonts from the stick, so the plain menu shows instead.
THEME = f"""
# Monet's start menu: the harbor at dawn, the choices on smoked glass.
if loadfont {THEME_DIR}/title-56.pf2 ; then
  loadfont {THEME_DIR}/strong-20.pf2
  loadfont {THEME_DIR}/text-14.pf2
  loadfont {THEME_DIR}/text-20.pf2
  set gfxterm_font="Monet Text Regular 20"
  insmod all_video
  insmod gfxterm
  insmod gfxmenu
  insmod png
  set gfxmode=1920x1080,1600x900,1366x768,1280x720,auto
  terminal_output gfxterm
  set theme={THEME_DIR}/theme.txt
  export theme
fi
"""


def patch(text):
    entry = re.search(r"menuentry '([^']*)'[^\n]*\{.*?\n\}", text, re.S)
    if not entry:
        raise SystemExit("no menu entry found")
    block, title = entry.group(0), entry.group(1)
    block_quiet = re.sub(r"(\n\s*linux(?:efi)?\s+[^\n]+)", r"\1 nouveau.modeset=0", block, count=1)
    erase = block_quiet.replace(f"'{title}'", f"'{ERASE}'", 1)
    keep = block_quiet.replace(f"'{title}'", f"'{KEEP}'", 1)
    keep, added = re.subn(r"(\n\s*linux(?:efi)?\s+[^\n]+)", r"\1 monet.keep", keep, count=1)
    if not added:
        raise SystemExit("no linux line in the first entry")
    text = text.replace(block, erase + "\n" + keep, 1)
    text = re.sub(r"(menuentry '[^']*?)Fedora(?: Linux)?(?: \d+)?", r"\1Monet", text)
    text = text.replace("submenu 'Troubleshooting -->'", f"submenu '{MORE}'")
    text, defaults = re.subn(r'set default="?\d+"?', 'set default="0"', text)
    if not defaults:
        text = 'set default="0"\n' + text
    text = re.sub(r"set timeout=\d+", "set timeout=10", text)

    # The theme needs $root, which the search line sets: load it right after.
    search = re.search(r"^search [^\n]*$", text, re.M)
    if search:
        text = text[:search.end()] + "\n" + THEME + text[search.end():]
    else:
        text = text + "\n" + THEME
    return text


if __name__ == "__main__":
    for path in sys.argv[1:]:
        with open(path) as f:
            patched = patch(f.read())
        with open(path, "w") as f:
            f.write(patched)
        print(f"patched {path}")
