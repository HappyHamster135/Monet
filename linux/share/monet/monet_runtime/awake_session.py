"""Runtime files for a single desktop's manual Keep awake session."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


def marker_path():
    return Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'monet/keep-awake.json'


def timer_path():
    return marker_path().parents[1] / 'monet-keep-awake/manual.json'


@contextmanager
def startup_lock():
    # Serialize cancelling a timer without an owner with a new owner's claim.
    import fcntl
    marker = marker_path()
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with marker.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_record(path, record):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.awake-')
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(record, output, allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_timer(session, duration, end):
    path = timer_path()
    if duration:
        write_record(path, dict(session=session, duration=duration, end=end))
    else:
        path.unlink(missing_ok=True)


def saved_timer(session, now):
    path = timer_path()
    try:
        with path.open() as source:
            raw = source.read(2049)
            record = json.loads(raw) if len(raw) <= 2048 else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError):
        record = None
    if isinstance(record, dict) and record.get('session') == session:
        duration, end = record.get('duration'), record.get('end')
        if type(duration) is int and type(end) in (int, float):
            if (duration == -1 and end == 0) or (1 <= duration <= 86400 and now < end <= now + duration):
                return duration, end
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass  # An unreadable or invalid record cannot grant an inhibition.
    return None
