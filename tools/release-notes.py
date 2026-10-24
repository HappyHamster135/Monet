#!/usr/bin/env python3
"""A release's own notes: RELEASE_NOTES.md's opening (what Monet is, the downloads) and the
newest "### New in" section, then a link to every version's notes. The whole file in every
release made GitHub's Releases page tens of thousands of words long, and slow.

    python3 tools/release-notes.py RELEASE_NOTES.md > notes.md
"""

import re
import sys

HISTORY = "https://github.com/HappyHamster135/Monet/blob/main/RELEASE_NOTES.md"


def this_release(text):
    """The opening and the first "### New in" section of text, or text as it is without one."""
    sections = [m.start() for m in re.finditer(r"(?m)^### New in ", text)]
    if not sections:
        return text
    end = sections[1] if len(sections) > 1 else len(text)
    return text[:end].rstrip() + f"\n\nWhat earlier versions brought: [every release's notes]({HISTORY}).\n"


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        sys.stdout.write(this_release(f.read()))
