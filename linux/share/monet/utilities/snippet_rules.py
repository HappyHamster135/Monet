"""Named shortcuts are explicit, so existing copy-only snippets keep their behavior."""
import re

from actions import stored


def valid_shortcut(value):
    return isinstance(value, str) and re.fullmatch(r"[\w-]{1,40}", value) is not None


def expansion_table(settings):
    if "snippets" in stored(settings, "hidden", []):
        return {}, set()
    entries = stored(settings, "snippets", {})
    rules = {}
    duplicates = set()
    for name, shortcut in stored(settings, "snippetShortcuts", {}).items():
        body = entries.get(name)
        if not valid_shortcut(shortcut) or not isinstance(body, str) or not body:
            continue
        trigger = ";" + shortcut + ";"
        if trigger in rules:
            duplicates.add(trigger)
        rules[trigger] = body
    for trigger in duplicates:
        del rules[trigger]
    prefixes = {trigger[:i] for trigger in rules for i in range(1, len(trigger))}
    return rules, prefixes
