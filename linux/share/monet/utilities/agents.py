"""Read only recorded metrics and recognized activity markers from a selected file."""
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

from actions import tr

MAX_READ = 1024 * 1024
DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}

# Keys also serve older callers of summary(). Display names can be translated.
NAMES = {
    "Input": tr("Input"), "Output": tr("Output"), "Cached input": tr("Cached input"),
    "Reasoning": tr("Reasoning"), "Total": tr("Total"), "AI credits": tr("AI credits"),
    "Premium requests": tr("Premium requests"), "Reported cost (USD)": tr("Reported cost (USD)"),
    "Primary limit used (%)": tr("Primary limit used (%)"), "Secondary limit used (%)": tr("Secondary limit used (%)"),
}
STATUSES = {
    "started": tr("Last event · Turn started"), "finished": tr("Last event · Turn finished"),
    "interrupted": tr("Last event · Turn interrupted"), "tool": tr("Last event · Tool requested"),
    "ended": tr("Last event · Session ended"), "idle": tr("Last event · Session idle"), "failed": tr("Last event · Turn failed"),
}
SCOPES = {"session": tr("Session totals"), "run": tr("Run totals"), "request": tr("Latest request"),
          "database": tr("Latest assistant message in this database")}


def number(value):
    return type(value) in (int, float) and 0 <= value <= 2**63 - 1 and math.isfinite(value)


def counts(data):
    if not isinstance(data, dict):
        return {}
    names = {"input_tokens": "Input", "output_tokens": "Output", "cached_input_tokens": "Cached input",
             "cache_read_input_tokens": "Cached input", "reasoning_output_tokens": "Reasoning",
             "total_tokens": "Total"}
    return {label: value for key, label in names.items()
            if type(value := data.get(key)) is int and number(value)}


def database_snapshot(path):
    # OpenCode keeps several sessions in one database. This row is one message.
    with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.2)) as db:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_READ * 4)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        deadline = time.monotonic() + 0.5
        db.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
        row = db.execute("SELECT json_extract(data,'$.tokens'),json_extract(data,'$.cost') FROM message "
                         "WHERE json_extract(data,'$.role')='assistant' "
                         "ORDER BY time_created DESC LIMIT 1").fetchone()
    if not row:
        return {}, "", ""
    tokens = json.loads(row[0]) if isinstance(row[0], str) else {}
    tokens = tokens if isinstance(tokens, dict) else {}
    cache = tokens.get("cache")
    values = counts({"input_tokens": tokens.get("input"), "output_tokens": tokens.get("output"),
                     "reasoning_output_tokens": tokens.get("reasoning"), "total_tokens": tokens.get("total"),
                     "cached_input_tokens": cache.get("read") if isinstance(cache, dict) else None})
    if number(row[1]):
        values["Reported cost (USD)"] = round(row[1], 6)
    return values, "database", ""


def copilot_totals(data):
    values = {}
    models = data.get("modelMetrics")
    if isinstance(models, dict) and models:
        usage = [m.get("usage") if isinstance(m, dict) else None for m in models.values()]
        for field, name in (("inputTokens", "Input"), ("outputTokens", "Output"), ("cacheReadTokens", "Cached input")):
            amounts = [u.get(field) if isinstance(u, dict) else None for u in usage]
            if all(type(n) is int and number(n) for n in amounts):
                values[name] = sum(amounts)
    for field, name in (("totalAiCredits", "AI credits"), ("totalPremiumRequests", "Premium requests")):
        if number(data.get(field)):
            values[name] = data[field]
    return values


def event_fields(event):
    payload = event.get("payload") or event.get("data")
    payload = payload if isinstance(payload, dict) else {}
    kind = event.get("type")
    kind = kind if isinstance(kind, str) else ""
    tag = payload.get("type")
    tag = tag if isinstance(tag, str) else ""
    message = event.get("message")
    message = message if isinstance(message, dict) else {}
    values, scope, status = {}, "", ""
    if kind == "event_msg":
        status = {"task_started": "started", "task_complete": "finished", "turn_aborted": "interrupted"}.get(tag, "")
    if tag == "token_count":
        info = payload.get("info")
        if isinstance(info, dict):
            values = counts(info.get("total_token_usage"))
            scope = "session" if values else "request"
            if not values:
                values = counts(info.get("last_token_usage"))
        rates = payload.get("rate_limits")
        for bucket in ("primary", "secondary"):
            window = rates.get(bucket) if isinstance(rates, dict) else None
            used = window.get("used_percent") if isinstance(window, dict) else None
            if number(used) and used <= 100:
                values[bucket.title() + " limit used (%)"] = used
    elif kind == "result" and isinstance(event.get("subtype"), str):
        values = counts(event.get("usage"))
        if number(event.get("total_cost_usd")):
            values["Reported cost (USD)"] = event["total_cost_usd"]
        scope = "run"
        if event.get("is_error") is True:
            status = "failed"
        elif event["subtype"] == "success":
            status = "finished"
    elif kind == "session.shutdown":
        values, scope, status = copilot_totals(payload), "session", "ended"
    elif kind == "assistant.usage":
        values = counts({"input_tokens": payload.get("inputTokens"), "output_tokens": payload.get("outputTokens"),
                         "cached_input_tokens": payload.get("cacheReadTokens")})
        scope = "request"
    else:
        values = counts(message.get("usage") or payload.get("usage"))
        scope = "request"
        if kind == "assistant":
            reason = message.get("stop_reason")
            if reason == "tool_use":
                status = "tool"
            elif reason == "end_turn":
                status = "finished"
        elif kind == "assistant.turn_start":
            status = "started"
        elif kind == "session.idle":
            status = "idle"
        elif kind == "assistant.turn_end":
            status = "finished"
    return values, scope, status


def snapshot(file):
    path = Path(file)
    if path.suffix.lower() in DATABASE_SUFFIXES:
        if not path.is_file():
            raise ValueError("Unavailable session")
        return database_snapshot(path)
    # A file selected earlier can be replaced, including with a named pipe.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("Unavailable session")
        offset = max(0, st.st_size - MAX_READ)
        stream.seek(max(0, offset - 1))
        if offset and stream.read(1) != b"\n":
            stream.readline(MAX_READ)
        lines = stream.read(MAX_READ).splitlines()
    values, scope, last_event = {}, "", ""
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        metrics, source, status = event_fields(event)
        if not values and metrics:
            values, scope = metrics, source
        if not last_event:
            last_event = status
        if last_event and values:
            break
    return values, scope, last_event


def summary(file):
    return snapshot(file)[0]


def format_summary(values):
    return " · ".join(f"{NAMES[key]} {value:,}" for key, value in values.items())


def display(file):
    try:
        values, scope, status = snapshot(file)
    except (OSError, ValueError, sqlite3.Error, TypeError, RecursionError):
        return tr("Could not read the selected session file.")
    metrics = format_summary(values)
    if metrics and scope:
        metrics = SCOPES[scope] + " · " + metrics
    return "\n".join(filter(None, (STATUSES.get(status), metrics))) or tr("No usage figures were reported in recent session events.")


if __name__ == "__main__":
    from PySide6.QtCore import QSettings
    file = QSettings("Monet", "Utilities").value("agentFile", "")
    print(display(file) if file else "")
