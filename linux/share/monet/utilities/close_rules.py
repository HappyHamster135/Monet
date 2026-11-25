"""Settings shared by the last-window rule and its on-demand session service."""
import json
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths


def settings():
    path = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "monet/quit-on-close.conf"
    return QSettings(str(path), QSettings.IniFormat)


def applications(config):
    try:
        rules = json.loads(config.value("applications", "{}"))
    except (ValueError, TypeError):
        return {}
    if not isinstance(rules, dict):
        return {}
    return {key: aliases for key, aliases in rules.items()
            if key.endswith(".desktop") and "/" not in key and isinstance(aliases, list)
            and all(isinstance(alias, str) and alias for alias in aliases)}


def application_aliases(selected):
    from gi.repository import Gio
    # A shared StartupWMClass cannot distinguish two applications.
    owners = {}
    aliases = {}
    for entry in Gio.AppInfo.get_all():
        ident = entry.get_id()
        if not ident or not ident.endswith(".desktop"):
            continue
        alias = (entry.get_startup_wm_class() or "").lower()
        owners.setdefault(ident[:-8].lower(), set()).add(ident)
        if alias:
            owners.setdefault(alias, set()).add(ident)
            aliases[ident] = alias
    rules = {}
    for ident in selected:
        alias = aliases.get(ident)
        rules[ident] = [alias] if alias and owners[alias] == {ident} else []
    return rules
