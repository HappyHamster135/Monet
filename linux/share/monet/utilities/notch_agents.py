"""Read and configure the same opt-in session and account readings as Utilities."""
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QSettings, QUrl
from actions import stored


def selected_file(address):
    url = QUrl(bytes.fromhex(address).decode("utf-8"))
    path = Path(url.toLocalFile())
    if not url.isLocalFile() or url.host() or not path.is_absolute() or not path.is_file():
        raise ValueError("Expected a local file")
    return path


def reading(provider, action, address=""):
    settings = QSettings("Monet", "Utilities")
    if "agents" in stored(settings, "hidden", []):
        return {"ok": False}
    if provider == "session":
        from agents import DATABASE_SUFFIXES, display
        if action == "select":
            path = selected_file(address)
            if path.suffix.lower() not in {".jsonl", ".json", ".log", *DATABASE_SUFFIXES}:
                return {"ok": False}
            settings.setValue("agentFile", str(path))
        elif action == "forget":
            settings.remove("agentFile")
        elif action != "read":
            return {"ok": False}
        settings.sync()
        filename = settings.value("agentFile", "")
        return {"ok": True, "name": Path(filename).name if filename else "", "summary": display(filename) if filename else ""}
    if provider not in ("codex", "claude") or action not in ("read", "refresh", "on", "off", "cli"):
        return {"ok": False}
    from codex_limits import display, enable, generation, snapshot
    if action == "cli":
        path = selected_file(address)
        if not os.access(path, os.X_OK):
            return {"ok": False}
        settings.setValue(provider + "Executable", str(path))
        settings.sync()
    if action in ("on", "off") and bool(generation(settings, provider)) != (action == "on"):
        enable(settings, action == "on", provider)
    return dict(display(snapshot(settings, force=action in ("refresh", "cli"), provider=provider), provider),
                ok=True, enabled=bool(generation(settings, provider)))


if __name__ == "__main__":
    try:
        result = reading(*sys.argv[1:])
    except (ValueError, OSError, TypeError):
        result = {"ok": False}
    print(json.dumps(result))
