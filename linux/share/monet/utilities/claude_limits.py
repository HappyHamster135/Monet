"""Read Claude Code's structured usage response, without starting a conversation."""
import asyncio
from datetime import datetime
import json
import os
import signal
import time


def windows(result, now):
    limits = result.get("rate_limits")
    if not isinstance(limits, dict):
        return []
    rows = []
    buckets = [(name, minutes, scope, limits.get(name)) for name, minutes, scope in (
        ("five_hour", 300, ""), ("seven_day", 10080, ""), ("seven_day_opus", 10080, "Opus"),
        ("seven_day_sonnet", 10080, "Sonnet"), ("seven_day_oauth_apps", 10080, ""))]
    models = limits.get("model_scoped")
    if isinstance(models, list):
        for item in models[:32]:
            label = item.get("display_name") if isinstance(item, dict) else None
            if isinstance(label, str) and 0 < len(label.strip()) <= 80 and label.isprintable():
                buckets.append(("model_scoped", 10080, label.strip(), item))
    seen = set()
    for key, minutes, scope, item in buckets:
        if not isinstance(item, dict):
            continue
        used = item.get("utilization")
        if type(used) not in (int, float) or not 0 <= used <= 100:
            continue
        reset = 0
        if item.get("resets_at") is not None:
            try:
                date = datetime.fromisoformat(item["resets_at"])
                if date.utcoffset() is None:
                    continue
                reset = int(date.timestamp())
            except (ValueError, TypeError, OverflowError, OSError):
                continue
            if reset <= now:
                continue
        identity = (minutes, scope.casefold(), key == "seven_day_oauth_apps")
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(dict(window=key, minutes=minutes, scope=scope, left=round(100 - used, 1), reset=reset))
    return rows


async def fetch(cli):
    env = dict(os.environ, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", DISABLE_AUTOUPDATER="1")
    proc = await asyncio.create_subprocess_exec(
        cli, "--safe-mode", "--print", "--input-format", "stream-json", "--output-format", "stream-json",
        "--verbose", "--no-session-persistence", "--tools", "", "--strict-mcp-config", "--mcp-config",
        '{"mcpServers":{}}', "--setting-sources", "", cwd="/", env=env, start_new_session=True,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        limit=512 * 1024)

    async def request(kind, **params):
        envelope = {"type": "control_request", "request_id": kind, "request": {"subtype": kind, **params}}
        proc.stdin.write(json.dumps(envelope).encode() + b"\n")
        await proc.stdin.drain()
        while line := await proc.stdout.readline():
            event = json.loads(line)
            # A quota check has no reason to authorize a tool or a permission request.
            if isinstance(event, dict) and event.get("type") == "control_request":
                return "unavailable", {}
            if not isinstance(event, dict) or event.get("type") != "control_response":
                continue
            response = event.get("response")
            if not isinstance(response, dict) or response.get("request_id") != kind:
                continue
            if response.get("subtype") == "success" and isinstance(response.get("response"), dict):
                return "ready", response["response"]
            error = str(response.get("error", "")).casefold()
            if "unsupported" in error or "unknown" in error:
                return "outdated", {}
            if any(s in error for s in ("sign in", "log in", "login", "authenticat")):
                return "sign-in", {}
            return "unavailable", {}
        return "unavailable", {}

    try:
        async with asyncio.timeout(15):
            state, _ = await request("initialize")
            if state != "ready":
                return state, []
            state, result = await request("get_usage", skip_behaviors=True)
            if state != "ready":
                return state, []
            if result.get("rate_limits_available") is False:
                return "no-plan", []
            if result.get("rate_limits_available") is not True:
                return "empty", []
            rows = windows(result, time.time())
            return ("ready" if rows else "empty"), rows
    finally:
        proc.stdin.close()
        try:
            await asyncio.wait_for(proc.communicate(), timeout=.75)
        except TimeoutError:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await asyncio.wait_for(proc.communicate(), timeout=2)
