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
