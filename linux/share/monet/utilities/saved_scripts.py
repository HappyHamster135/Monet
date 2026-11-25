"""User-selected executable files for the desktop Command Bar."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from actions import tr, words


@dataclass(frozen=True)
class Script:
    ident: str
    name: str
    path: str
    needs_text: bool
    preview: bool

    def key(self, argument):
        encoded = json.dumps([asdict(self), argument], sort_keys=True).encode()
        return "script/" + hashlib.sha256(encoded).hexdigest()


def library(settings):
    settings.sync()
    settings.beginGroup("savedScripts")
    try:
        scripts = []
        for ident in settings.childKeys():
            try:
                value = json.loads(settings.value(ident))
                name, path = value["name"], value["path"]
                if (not isinstance(name, str) or not name.strip() or "\0" in name or not isinstance(path, str)
                        or not os.path.isabs(path) or "\0" in path):
                    continue
                scripts.append(Script(ident, name, path, value.get("needs_text") is True, value.get("preview") is True))
            except (TypeError, ValueError, KeyError):
                continue
        return sorted(scripts, key=lambda script: script.name.casefold())
    finally:
        settings.endGroup()


def save(settings, name, path, needs_text, preview, ident=None):
    name = " ".join(name.split())
    if not name or "\0" in name:
        raise ValueError(tr("Give the script a name."))
    path = Path(path).expanduser()
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(tr("Choose a local script with permission to run."))
    scripts = library(settings)
    if any(s.name.casefold() == name.casefold() and s.ident != ident for s in scripts):
        raise ValueError(tr("A saved script already uses that name."))
    script = Script(ident or uuid4().hex, name, str(path), needs_text, preview)
    settings.setValue("savedScripts/" + script.ident, json.dumps(asdict(script), ensure_ascii=False))
    settings.sync()
    if settings.status() != settings.Status.NoError:
        raise ValueError(tr("Could not save the script settings."))
    return script


def choices(scripts, query):
    # Keep quoted text, case and punctuation in arguments. Longer names win over shared prefixes.
    head = query.strip()
    for script in sorted(scripts, key=lambda entry: len(entry.name), reverse=True):
        # Whole Unicode case-folds can change length, so split at word boundaries before comparing.
        name_parts = len(script.name.split())
        parts = head.split(None, name_parts)
        if " ".join(parts[:name_parts]).casefold() == script.name.casefold():
            argument = parts[name_parts] if len(parts) > name_parts else ""
            return [(script, argument, True)]
    tokens = words(head).split()
    return [(s, "", False) for s in scripts if all(token in words(s.name) for token in tokens)][:10]
