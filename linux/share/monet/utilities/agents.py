"""Summarize usage figures explicitly recorded by a local agent. Never send log contents."""
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

MAX_READ = 1024 * 1024

def counts(data):
    if not isinstance(data, dict):
        return {}
    names = {"input_tokens": "Input", "output_tokens": "Output", "cached_input_tokens": "Cached input",
             "cache_read_input_tokens": "Cached input", "reasoning_output_tokens": "Reasoning",
             "total_tokens": "Total"}
    return {title: val for key, title in names.items() if type(val := data.get(key)) is int and val >= 0}

def summary(file):
    path = Path(file)
    if not path.is_file():
        raise ValueError("The selected session file is unavailable.")
    if path.suffix in (".db", ".sqlite", ".sqlite3"):
        uri = "file:" + quote(str(path.resolve())) + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1) as db:
            db.execute("PRAGMA query_only=ON")
            latest = db.execute("SELECT json_extract(data,'$.tokens'),json_extract(data,'$.cost') FROM message "
                "WHERE json_extract(data,'$.role')='assistant' ORDER BY time_created DESC LIMIT 1").fetchone()
        if latest:
            tokens = json.loads(latest[0] or "{}")
            if not isinstance(tokens, dict):
                tokens = {}
            values = counts({"input_tokens": tokens.get("input"), "output_tokens": tokens.get("output")})
            if isinstance(latest[1], (int, float)):
                values["Reported cost (USD)"] = round(latest[1], 5)
            return values
        return {}
    with path.open("rb") as stream:
        stream.seek(0, 2)
        start = max(0, stream.tell() - MAX_READ)
        stream.seek(start)
        if start:
            stream.readline(MAX_READ)
        lines = stream.read(MAX_READ).splitlines()
    values = {}
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") or event.get("data") or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "token_count":
            info = payload.get("info") or {}
            if isinstance(info, dict):
                values = counts(info.get("total_token_usage") or info.get("last_token_usage") or {})
            rates = payload.get("rate_limits") or {}
            for key in ("primary", "secondary"):
                bucket = rates.get(key) if isinstance(rates, dict) else None
                used = bucket.get("used_percent") if isinstance(bucket, dict) else None
                if isinstance(used, (float, int)):
                    values[key.title() + " limit used (%)"] = used
            if values:
                break
        msg = event.get("message") or {}
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            values = counts(msg["usage"])
        elif isinstance(payload.get("usage"), dict):
            values = counts(payload["usage"])
        elif event.get("type") == "assistant.usage":
            values = counts({"input_tokens": payload.get("inputTokens"), "output_tokens": payload.get("outputTokens")})
        if values:
            break
    return values

def format_summary(values):
    return " · ".join(f"{key} {value:,}" for key, value in values.items())

if __name__ == "__main__":
    from PySide6.QtCore import QSettings
    file = QSettings("Monet", "Utilities").value("agentFile", "")
    try:
        print(format_summary(summary(file)) if file else "")
    except (OSError, ValueError, sqlite3.Error, TypeError):
        print("")
