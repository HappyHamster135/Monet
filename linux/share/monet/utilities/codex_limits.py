"""Read account quota windows from the signed-in Codex CLI, on demand."""
import asyncio
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
from uuid import uuid4

from PySide6.QtCore import QDateTime, QLocale, QLockFile, QSettings, QStandardPaths
from actions import tr

REPLY_TIMEOUT = 10


def generation(settings):
    value = settings.value("codexLimits", "")
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) else ""


def cache_file(key):
    # RuntimeLocation is private to the login and the OS clears it at logout.
    return Path(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)) / ("monet-codex-limits-" + key + ".json")


def enable(settings, on):
    old = generation(settings)
    if on:
        settings.setValue("codexLimits", uuid4().hex)
    else:
        settings.remove("codexLimits")
    settings.sync()
    if old:
        cache_file(old).unlink(missing_ok=True)


def executable(settings):
    chosen = settings.value("codexExecutable", "")
    if chosen:
        return chosen if isinstance(chosen, str) and os.path.isabs(chosen) and os.path.isfile(chosen) and os.access(chosen, os.X_OK) else None
    cli = shutil.which("codex")
    if cli:
        return cli
    # A relocatable ChatGPT desktop install also ships a CLI. Resolve the
    # registered application's binary without running its launcher.
    try:
        from gi.repository import GioUnix
    except ImportError:
        return None
    for desktop in ("chatgpt.desktop", "codex.desktop"):
        try:
            app = GioUnix.DesktopAppInfo.new(desktop)
            if not app:
                continue
            binary = Path(shlex.split(app.get_commandline())[0])
        except (ValueError, IndexError, TypeError):
            continue
        if not binary.is_absolute() or binary.name.lower() not in ("chatgpt", "codex"):
            continue
        for candidate in (binary.parent / "resources/codex", binary.parent.parent / "lib" / binary.name.lower() / "resources/codex"):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def windows(result):
    buckets = result.get("rateLimitsByLimitId")
    bucket = buckets.get("codex") if isinstance(buckets, dict) else None
    if not isinstance(bucket, dict):
        bucket = result.get("rateLimits")
    if not isinstance(bucket, dict) or bucket.get("limitId") not in (None, "codex"):
        return []
    rows = []
    for name in ("primary", "secondary"):
        window = bucket.get(name)
        if not isinstance(window, dict):
            continue
        used = window.get("usedPercent")
        if type(used) not in (int, float) or not 0 <= used <= 100:
            continue
        minutes, reset = window.get("windowDurationMins"), window.get("resetsAt")
        rows.append({"window": name, "left": round(100 - used, 1),
                     "minutes": minutes if type(minutes) is int and 0 < minutes <= 525600 else 0,
                     "reset": reset if type(reset) is int and 0 < reset <= 253402300799 else 0})
    return rows


async def fetch(cli):
    proc = await asyncio.create_subprocess_exec(cli, "-c", "features.plugins=false", "-c", "analytics.enabled=false",
        "app-server", cwd="/", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=512 * 1024)

    async def send(data):
        proc.stdin.write(json.dumps(data).encode() + b"\n")
        await proc.stdin.drain()

    async def reply(ident):
        while line := await proc.stdout.readline():
            message = json.loads(line)
            if not isinstance(message, dict):
                continue
            if "method" in message:
                if "id" in message:
                    await send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported method"}})
            elif message.get("id") == ident:
                return message
        raise ValueError("Codex closed the connection")

    async def exchange():
        await send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "monet_utilities", "title": "Monet Utilities", "version": "1"}}})
        if "result" not in await reply(1):
            return "unavailable", []
        await send({"method": "initialized"})
        await send({"id": 2, "method": "account/rateLimits/read"})
        response = await reply(2)
        result = response.get("result")
        if isinstance(result, dict):
            rows = windows(result)
            return ("ready" if rows else "empty"), rows
        error = response.get("error")
        message = str(error.get("message", "")).casefold() if isinstance(error, dict) else ""
        if any(term in message for term in ("sign in", "signed in", "login", "log in", "unauthorized", "authentication", "chatgpt auth", "api key", "not logged")):
            return "sign-in", []
        return "unavailable", []

    try:
        return await asyncio.wait_for(exchange(), timeout=REPLY_TIMEOUT)
    finally:
        proc.stdin.close()
        if proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=.4)
            except TimeoutError:
                if proc.returncode is None:
                    proc.kill()
                await asyncio.wait_for(proc.communicate(), timeout=2)


def snapshot(settings, force=False):
    settings.sync()
    key = generation(settings)
    if not key:
        return {"state": "off"}
    cache = cache_file(key)
    lock = QLockFile(str(cache) + ".lock")
    started = time.time()
    if not lock.tryLock(12000):
        return {"state": "unavailable", "generation": key}
    try:
        settings.sync()
        if generation(settings) != key:
            return {"state": "off"}
        try:
            prior = json.loads(cache.read_bytes())
            checked = prior["checked"]
            if prior.get("generation") == key and checked <= time.time() < prior["expires"] and (not force or checked >= started):
                return prior
        except (OSError, KeyError, ValueError, TypeError):
            pass
        cli = executable(settings)
        state, rows = "missing", []
        if cli:
            try:
                state, rows = asyncio.run(fetch(cli))
            except (OSError, ValueError, TimeoutError, RecursionError):
                state, rows = "unavailable", []
        now = time.time()
        expires = min([now + (300 if state == "ready" else 30),
                       *(row["reset"] for row in rows if row["reset"] > now)])
        data = dict(state=state, generation=key, rows=rows, checked=now, expires=expires)
        # All readers hold this lock. Disable/reenable gets a fresh generation
        # so an earlier request can never reintroduce the old account's display.
        try:
            descriptor = os.open(cache, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as out:
                json.dump(data, out)
        except OSError:
            pass  # A full runtime directory should not hide a successful reading.
        settings.sync()
        if generation(settings) != key:
            cache.unlink(missing_ok=True)
            return {"state": "off"}
        return data
    finally:
        lock.unlock()


def display(data):
    state = data["state"]
    messages = {"missing": tr("Install the Codex CLI or choose its executable."),
                "sign-in": tr("Sign in to the Codex CLI with a ChatGPT account to see limits."),
                "empty": tr("Codex did not report any account limit windows."),
                "unavailable": tr("Could not check Codex limits. Try refreshing.")}
    if state != "ready":
        return {"state": state, "generation": data.get("generation", ""), "summary": "" if state == "off" else tr("Codex limits unavailable"),
                "details": messages.get(state, ""), "rows": []}
    locale = QLocale()
    def date_time(stamp):
        return locale.toString(QDateTime.fromSecsSinceEpoch(int(stamp)).toLocalTime(), QLocale.ShortFormat)
    rows = []
    for item in data["rows"]:
        mins = item["minutes"]
        if mins and mins % 1440 == 0:
            name = tr("%1d window").replace("%1", str(mins // 1440))
        elif mins and mins % 60 == 0:
            name = tr("%1h window").replace("%1", str(mins // 60))
        elif mins:
            name = tr("%1min window").replace("%1", str(mins))
        else:
            name = tr("Primary window") if item["window"] == "primary" else tr("Secondary window")
        left = tr("%1% left").replace("%1", locale.toString(float(item["left"]), "f", 0 if item["left"] % 1 == 0 else 1))
        reset = tr("Resets %1").replace("%1", date_time(item["reset"])) if item["reset"] else ""
        rows.append(dict(name=name, remaining=left, reset=reset, value=item["left"]))
    checked = tr("Checked %1").replace("%1", date_time(data["checked"]))
    return {"state": state, "generation": data["generation"], "rows": rows, "summary": "Codex · " + " · ".join(r["name"] + " " + r["remaining"] for r in rows),
            "details": "\n".join(" · ".join(filter(None, (r["name"], r["remaining"], r["reset"]))) for r in rows) + "\n" + checked,
            "checked": checked}


if __name__ == "__main__":
    print(json.dumps(display(snapshot(QSettings("Monet", "Utilities"), "--refresh" in sys.argv[1:]))))
