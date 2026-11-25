"""Read the selected MPRIS player's queue and local lyrics on demand."""
import os
import re
import stat
from pathlib import Path
from urllib.parse import unquote, urlsplit

MPRIS = "org.mpris.MediaPlayer2"
PLAYER = MPRIS + ".Player"
TRACKS = MPRIS + ".TrackList"
OBJECT = "/org/mpris/MediaPlayer2"
MAX_LYRICS = 256 * 1024
STAMP = re.compile(r"\[(\d{1,4}):([0-5]\d)(?:[.:](\d{1,3}))?\]")
OFFSET = re.compile(r"^\[offset:\s*([+-]?\d{1,8})\s*\]$", re.I | re.M)
TAG = re.compile(r"^\[[a-z]+:[^\]]*\]$", re.I)


def parse_lyrics(text):
    """LRC times are milliseconds. Keep blanks that mark an instrumental break."""
    text = text[:MAX_LYRICS].replace("\r\n", "\n").lstrip("\ufeff").strip()
    offset_match = OFFSET.search(text)
    offset = int(offset_match[1]) if offset_match else 0
    by_time = {}
    plain = []
    for line in text.splitlines():
        line = line.strip()
        start = 0
        times = []
        while match := STAMP.match(line, start):
            minutes, seconds, fraction = match.groups()
            at = (int(minutes) * 60 + int(seconds)) * 1000 + int((fraction or "").ljust(3, "0"))
            times.append(max(0, at - offset))
            start = match.end()
        if times:
            lyric = line[start:].strip()
            for at in times:
                lines = by_time.setdefault(at, [])
                if lyric and lyric not in lines:
                    lines.append(lyric)
        elif not TAG.fullmatch(line):
            plain.append(line)
    if by_time:
        return {"timed": [{"at": at, "text": "\n".join(by_time[at])} for at in sorted(by_time)], "text": ""}
    return {"timed": [], "text": "\n".join(plain).strip()}


def track_lyrics(meta):
    supplied = parse_lyrics(str(meta.get("xesam:asText", "")))
    if supplied["timed"]:
        return supplied
    try:
        url = urlsplit(str(meta.get("xesam:url", "")))
        if url.scheme != "file" or url.netloc not in ("", "localhost"):
            return supplied
        track = Path(unquote(url.path))
        if not track.is_absolute() or not track.suffix:
            return supplied
        sidecar = track.with_suffix(".lrc")
        # Opening a named pipe beside a song must never stall a Plasma request.
        with os.fdopen(os.open(sidecar, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_LYRICS:
                return supplied
            data = stream.read(MAX_LYRICS + 1)
        if len(data) > MAX_LYRICS:
            return supplied
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        local = parse_lyrics(data.decode(encoding))
        return local if local["timed"] or not supplied["text"] else supplied
    except (OSError, ValueError):
        return supplied


def track_title(meta):
    title = meta.get("xesam:title")
    if title:
        return str(title)
    url = str(meta.get("xesam:url", ""))
    return unquote(url.rsplit("/", 1)[1]) if "/" in url else ""


def track_artist(meta):
    value = meta.get("xesam:artist") or meta.get("xesam:albumArtist") or []
    if isinstance(value, (list, tuple)):
        return ", ".join(map(str, value))
    return value if isinstance(value, str) else ""


def upcoming(obj, props, meta):
    import dbus
    try:
        ids = props.Get(TRACKS, "Tracks", timeout=1)
        if not isinstance(ids, (list, tuple)):
            return []
        current = meta.get("mpris:trackid")
        if not ids or current not in ids:
            return []
        start = ids.index(current) + 1
        ids = ids[start:start + 20]
        if not ids:
            return []
        rows = obj.GetTracksMetadata(dbus.Array(ids, signature="o"), dbus_interface=TRACKS, timeout=2)
        metadata = {entry["mpris:trackid"]: entry for entry in rows
                    if isinstance(entry, dict) and isinstance(entry.get("mpris:trackid"), str)}
        return [{"title": track_title(metadata[key]), "artist": track_artist(metadata[key])}
                for key in ids if key in metadata]
    except dbus.DBusException:
        return []


def snapshots(selection=None):
    """Match Plasma's active process. Disambiguate services sharing that PID before replying."""
    import dbus
    bus = dbus.SessionBus()
    daemon = dbus.Interface(bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                         introspect=False), "org.freedesktop.DBus")
    matches = []
    owners = set()
    selected_service = selection.get("service") if selection else None
    names = [selected_service] if selected_service else sorted(bus.list_names())
    for name in names:
        if not isinstance(name, str) or not name.startswith(MPRIS + "."):
            continue
        try:
            owner = bus.get_name_owner(name)
            if owner in owners or (selection and int(daemon.GetConnectionUnixProcessID(owner, timeout=1)) != selection["pid"]):
                continue
            obj = bus.get_object(owner, OBJECT, introspect=False)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            identity = str(props.Get(MPRIS, "Identity", timeout=1))
            meta = props.Get(PLAYER, "Metadata", timeout=1)
            if not isinstance(meta, dict):
                continue
            if selection and not selected_service and (identity != selection["identity"] or track_title(meta) != selection["title"]
                              or track_artist(meta) != selection["artist"]):
                continue
            playing = props.Get(PLAYER, "PlaybackStatus", timeout=1) == "Playing"
            owners.add(owner)
            matches.append((name, obj, props, meta, identity, playing))
        except dbus.DBusException:
            continue
    if selection and len(matches) != 1:
        return []
    return [{"service": name, "trackId": str(meta.get("mpris:trackid", "")), "identity": identity, "title": track_title(meta), "playing": playing,
             "lyrics": track_lyrics(meta), "queue": upcoming(obj, props, meta)}
            for name, obj, props, meta, identity, playing in matches]


if __name__ == "__main__":
    import json
    import sys
    import dbus
    try:
        selected = json.loads(bytes.fromhex(sys.argv[1]))
        result = snapshots(selected) if type(selected["pid"]) is int and selected["pid"] > 0 else []
        print(json.dumps(result[0] if result else {}))
    except (IndexError, KeyError, TypeError, ValueError, dbus.DBusException):
        print("{}")
