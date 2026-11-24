"""Read-only iCalendar agenda. The notch runs the reader only while viewing appointments."""
import contextlib
import datetime as dt
import fcntl
import heapq
import http.client
import itertools
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import uuid

MAX_BYTES = 5 * 1024 * 1024
MAX_EVENTS = 200
WINDOW_DAYS = 14


def directory(cache=False):
    variable, fallback = ("XDG_CACHE_HOME", ".cache") if cache else ("XDG_CONFIG_HOME", ".config")
    return Path(os.environ.get(variable) or Path.home() / fallback) / "monet/agenda"


def read_json(path, default):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        return default


def write(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


@contextlib.contextmanager
def transaction():
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(root, os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def sources():
    rows = read_json(directory() / "sources.json", [])
    if not isinstance(rows, list) or not all(isinstance(s, dict)
            and re.fullmatch("[0-9a-f]{32}", str(s.get("id", "")))
            and s.get("kind") in ("file", "url")
            and all(isinstance(s.get(k), str) for k in ("name", "location")) for s in rows):
        raise ValueError("Cannot read the saved calendar list.")
    return rows


def https_url(value):
    if re.search(r"[\x00-\x20\x7f]", value):
        raise ValueError("Enter an HTTPS calendar subscription link.")
    url = urlsplit(value)
    if url.scheme not in ("webcal", "https") or not url.hostname or url.username is not None or url.fragment:
        raise ValueError("Enter an HTTPS or webcal subscription link without a username or password.")
    _ = url.port  # Reject malformed ports before saving.
    return urlunsplit(("https", url.netloc, url.path, url.query, ""))


def read_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("Choose a calendar file smaller than 5 MiB.")
        return bounded_read(stream)


def bounded_read(stream, deadline=None):
    data = bytearray()
    read = stream.read1 if hasattr(stream, "read1") else stream.read
    while len(data) <= MAX_BYTES:
        block = read(65536)
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError()
        if not block:
            return bytes(data)
        data.extend(block)
    raise ValueError("Calendar exceeds 5 MiB.")


def check_format(data):
    clean = data.removeprefix(b"\xef\xbb\xbf").strip()
    if not clean.upper().startswith(b"BEGIN:VCALENDAR") or not clean.upper().endswith(b"END:VCALENDAR"):
        raise ValueError("This is not an iCalendar file.")
    return clean


def add(kind, location, name=""):
    if kind == "file":
        location = str(Path(location).expanduser().resolve())
        check_format(read_file(location))
        default = Path(location).stem
    elif kind == "url":
        location = https_url(location.strip())
        default = urlsplit(location).hostname
    else:
        raise ValueError("Unknown calendar source.")
    with transaction():
        rows = sources()
        for row in rows:
            if row["kind"] == kind and row["location"] == location:
                return row["id"]
        ident = uuid.uuid4().hex
        rows.append(dict(id=ident, kind=kind, location=location, name=name.strip()[:160] or default))
        write(directory() / "sources.json", json.dumps(rows).encode())
        return ident


def remove(ident):
    with transaction():
        rows = sources()
        if not any(s["id"] == ident for s in rows):
            return
        write(directory() / "sources.json", json.dumps([s for s in rows if s["id"] != ident]).encode())
        for suffix in (".ics", ".json"):
            (directory(True) / (ident + suffix)).unlink(missing_ok=True)


def calendar(data):
    import icalendar
    return icalendar.Calendar.from_ical(check_format(data))


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ValueError("Calendar redirected to an insecure address.")
        return super().redirect_request(req, fp, code, msg, headers, https_url(newurl))


def download(source, meta):
    headers = {"Accept": "text/calendar", "User-Agent": "Monet-Agenda/1"}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("modified"):
        headers["If-Modified-Since"] = meta["modified"]
    request = urllib.request.Request(https_url(source["location"]), headers=headers)
    deadline = time.monotonic() + 12
    try:
        with urllib.request.build_opener(SecureRedirect()).open(request, timeout=5) as response:
            data = bounded_read(response, deadline)
            calendar(data)  # Keep the last usable copy if the provider returns an error page.
            return data, dict(etag=response.headers.get("ETag"), modified=response.headers.get("Last-Modified"))
    except urllib.error.HTTPError as err:
        if err.code != 304:
            raise
        err.close()
        return None, meta


def cache_meta(ident):
    try:
        state = read_json(directory(True) / (ident + ".json"), {})
        return state if isinstance(state, dict) else {}
    except ValueError:
        return {}


def sync_source(source, force=False):
    ident = source["id"]
    meta_path = directory(True) / (ident + ".json")
    data_path = meta_path.with_suffix(".ics")
    token = uuid.uuid4().hex
    with transaction():
        if source not in sources():
            return
        state = cache_meta(ident)
        if state.get("started", 0) + 30 > time.time():
            return
        if not force and state.get("next", 0) > time.time() and (state.get("failed") or data_path.is_file()):
            return
        if not data_path.exists():
            state = {}
        write(meta_path, json.dumps(dict(state, started=time.time(), token=token)).encode())
    try:
        data, updated = download(source, state)
        if data is None and not data_path.is_file():
            raise ValueError("Missing cached calendar.")
        result = dict(etag=updated.get("etag"), modified=updated.get("modified"), next=time.time() + 900)
    except (OSError, ValueError, TypeError, OverflowError, http.client.HTTPException):
        data = None
        result = dict(state, failed=True, next=time.time() + 180)
    with transaction():
        if cache_meta(ident).get("token") != token or source not in sources():
            return
        if data is not None:
            write(data_path, data)
        write(meta_path, json.dumps(result).encode())


def local_zone():
    from dateutil.tz import gettz
    return gettz(os.environ.get("TZ") or None)


def occurrences(data, first, last, now):
    import recurring_ical_events
    zone = first.tzinfo
    def local(value):
        if isinstance(value, dt.datetime):
            return value.astimezone(zone) if value.tzinfo else value.replace(tzinfo=zone)
        return dt.datetime.combine(value, dt.time(), zone)
    for event in recurring_ical_events.of(calendar(data), skip_bad_series=True).between(first, last):
        if str(event.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = event.start
        end = event.end
        all_day = not isinstance(start, dt.datetime)
        begins, ends = local(start), local(end)
        floor = first if all_day or first.date() != now.date() else now
        begin_ts, end_ts = begins.timestamp(), ends.timestamp()
        floor_ts = floor.timestamp()
        if begin_ts >= last.timestamp() or (end_ts <= floor_ts if end_ts > begin_ts else begin_ts < floor_ts):
            continue
        yield dict(start=begins.isoformat(), end=ends.isoformat(), allDay=all_day,
                   title=str(event.get("SUMMARY", ""))[:512], location=str(event.get("LOCATION", ""))[:512])


@contextlib.contextmanager
def time_limit(seconds):
    def expired(*_):
        raise TimeoutError("Calendar took too long to expand.")
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def agenda(day, now=None):
    rows = sources()
    result = dict(sources=len(rows), events=[], needsSync=False, unavailable=[], saved=[], truncated=False)
    if not rows:
        return result
    zone = local_zone()
    now = now.astimezone(zone) if now else dt.datetime.now(zone)
    first = dt.datetime.combine(day, dt.time(), zone)
    last = first + dt.timedelta(days=WINDOW_DAYS)
    events = []
    def order(event):
        return (event["start"][:10], not event["allDay"], dt.datetime.fromisoformat(event["start"]).timestamp(),
                event["title"].casefold(), event["source"])
    for source in rows:
        path = source["location"]
        if source["kind"] == "url":
            state = cache_meta(source["id"])
            result["needsSync"] |= state.get("next", 0) <= time.time()
            path = directory(True) / (source["id"] + ".ics")
            if not path.is_file() and not state.get("failed"):
                result["needsSync"] = True
                continue
            if state.get("failed") and path.is_file():
                result["saved"].append(source["name"])
        try:
            with time_limit(3):
                entries = (dict(e, source=source["name"]) for e in occurrences(read_file(path), first, last, now))
                events = heapq.nsmallest(MAX_EVENTS + 1, itertools.chain(events, entries), key=order)
        except (OSError, ValueError, TypeError, KeyError, OverflowError, MemoryError):
            result["unavailable"].append(source["name"])
    result["truncated"] = len(events) > MAX_EVENTS
    result["events"] = events[:MAX_EVENTS]
    return result


def main(args):
    wheels = Path(__file__).resolve().parents[1] / "agenda-wheels"
    sys.path[:0] = [str(w) for w in sorted(wheels.glob("*.whl"))]
    if len(args) == 2 and args[0] == "list":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, resource.getrlimit(resource.RLIMIT_AS)[1]))
        print(json.dumps(agenda(dt.date.fromisoformat(args[1]))))
    elif args in (["sync"], ["sync", "force"]):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda s: sync_source(s, len(args) == 2), (s for s in sources() if s["kind"] == "url")))
        print("{}")
    else:
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        # A private feed URL, event or path may occur in an exception.
        print('{"error":true}')
        sys.exit(1)
