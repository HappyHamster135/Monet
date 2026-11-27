"""Incrementally index numeric local CLI usage; never persist conversation text.

No account credentials, network requests, or CLI conversations are involved.
The private SQLite cache keeps file cursors and usage events only. Growing logs
are tailed, rather than reread on each notch visit. Partial final lines wait for
the next refresh; file replacement/truncation rebuilds only that file.
"""
from contextlib import closing
from datetime import datetime, timedelta, time as day_time
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

from agent_pricing import estimate, VERIFIED

FIELDS = ('input', 'cached', 'write', 'long_write', 'output', 'reasoning')
MAX_LINE = 4 * 1024 * 1024
VERSION = 1


def count(value):
    return value if type(value) is int and 0 <= value < 2**53 else 0


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
        return result if math.isfinite(result) and result > 0 else 0
    except (ValueError, OverflowError, OSError):
        return 0


def codex_counts(value):
    if not isinstance(value, dict):
        return None
    if type(value.get('input_tokens')) is not int or type(value.get('output_tokens')) is not int:
        return None
    return dict(input=count(value.get('input_tokens')), cached=count(value.get('cached_input_tokens')),
                write=count(value.get('cache_write_input_tokens')), long_write=0,
                output=count(value.get('output_tokens')), reasoning=count(value.get('reasoning_output_tokens')))


def claude_counts(value, previous=None):
    if not isinstance(value, dict) or not any(k in value for k in ('input_tokens', 'output_tokens')):
        return None
    previous = previous or {k:0 for k in FIELDS}
    read = count(value['cache_read_input_tokens']) if 'cache_read_input_tokens' in value else previous['cached']
    creation = value.get('cache_creation') or {}
    long = count(creation.get('ephemeral_1h_input_tokens')) if creation and isinstance(creation, dict) else previous['long_write']
    short = max(0, count(value['cache_creation_input_tokens']) - long) if 'cache_creation_input_tokens' in value else previous['write']
    base = count(value['input_tokens']) if 'input_tokens' in value else max(0,previous['input']-previous['cached']-previous['write']-previous['long_write'])
    return dict(input=base + read + short + long, cached=read,
                write=short, long_write=long, output=count(value['output_tokens']) if 'output_tokens' in value else previous['output'], reasoning=0)


def database(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    os.close(fd)
    db = sqlite3.connect(path, timeout=2)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA trusted_schema=OFF')
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version != VERSION:
        db.executescript('DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS events;')
    db.executescript('''CREATE TABLE IF NOT EXISTS files (
        key TEXT PRIMARY KEY, provider TEXT, device INTEGER, inode INTEGER, offset INTEGER,
        mtime INTEGER, size INTEGER, state TEXT);
        CREATE TABLE IF NOT EXISTS events (
        key TEXT PRIMARY KEY, file TEXT, session TEXT, provider TEXT, model TEXT, stamp REAL,
        input INTEGER, cached INTEGER, write INTEGER, long_write INTEGER, output INTEGER, reasoning INTEGER);
        CREATE INDEX IF NOT EXISTS event_time ON events(stamp);
        CREATE INDEX IF NOT EXISTS event_file ON events(file);''')
    db.execute(f'PRAGMA user_version={VERSION}')
    return db


def save_event(db, key, file, provider, state, stamp, usage):
    if not stamp or not usage or not usage['input'] + usage['output']:
        return
    db.execute('''INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET
        model=excluded.model, input=excluded.input,cached=excluded.cached,write=excluded.write,
        long_write=excluded.long_write,output=excluded.output,reasoning=excluded.reasoning''',
        (key, file, state.get('session', file), provider, state.get('model', ''), stamp, *(usage[k] for k in FIELDS)))


def consume(db, file, provider, state, event):
    kind = event.get('type')
    payload = event.get('payload')
    payload = payload if isinstance(payload, dict) else {}
    stamp = timestamp(event.get('timestamp'))
    if provider == 'codex':
        if kind == 'session_meta':
            session = str(payload.get('id') or payload.get('session_id') or file)
            state['session'] = hashlib.sha256(session.encode()).hexdigest()
            state['fork'] = bool(payload.get('history_base') or payload.get('forked_from_id'))
        elif kind == 'turn_context':
            state['model'] = str(payload.get('model') or '')[:100]
        elif kind == 'event_msg':
            tag = payload.get('type')
            if tag in ('task_started', 'task_complete', 'turn_aborted'):
                state.update(status='working' if tag == 'task_started' else 'idle', active=stamp)
            elif tag == 'token_count':
                info = payload.get('info')
                if not isinstance(info, dict):
                    return
                current = codex_counts(info.get('total_token_usage'))
                if current is None:
                    state['partial'] = True
                    return
                previous = state.get('previous')
                if previous == current:
                    return  # Quota-only events repeat the last token snapshot.
                if previous and current['input'] + current['output'] < previous['input'] + previous['output']:
                    state['epoch'] = state.get('epoch', 0) + 1
                    previous = None
                delta = {k:max(0, current[k] - previous[k]) for k in FIELDS} if previous else current
                if not previous and state.get('fork'):
                    # A fork's first cumulative total includes its parent's usage.
                    delta = codex_counts(info.get('last_token_usage'))
                    if delta is None:
                        state['partial'] = True
                state['previous'] = current
                key = file + ':' + str(state.get('epoch', 0)) + ':' + json.dumps(current, sort_keys=True)
                save_event(db, key, file, provider, state, stamp, delta)
                state.update(active=stamp, status='working')
    elif provider == 'claude' and kind == 'assistant':
        message = event.get('message')
        if not isinstance(message, dict) or not message.get('id'):
            return
        state['model'] = str(message.get('model') or '')[:100]
        session = str(event.get('sessionId') or file)
        state['session'] = hashlib.sha256(session.encode()).hexdigest()
        # Streaming fragments share a message ID: upsert its latest counters.
        key = file + ':' + str(message['id'])
        previous = db.execute('SELECT * FROM events WHERE key=?', (key,)).fetchone()
        save_event(db, key, file, provider, state, stamp, claude_counts(message.get('usage'), previous))
        state.update(active=stamp, status='idle' if message.get('stop_reason') == 'end_turn' else 'working')


def index_file(db, path, provider, deadline):
    key = hashlib.sha256(os.fsencode(path)).hexdigest()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode):
            return key, False
        previous = db.execute('SELECT * FROM files WHERE key=?', (key,)).fetchone()
        reset = not previous or previous['device'] != st.st_dev or previous['inode'] != st.st_ino or st.st_size < previous['size']
        if previous and st.st_size == previous['size'] and st.st_mtime_ns != previous['mtime']:
            reset = True
        if reset:
            db.execute('DELETE FROM events WHERE file=?', (key,))
        state = {} if reset else json.loads(previous['state'])
        offset = 0 if reset else previous['offset']
        stream.seek(offset)
        while stream.tell() < st.st_size and time.monotonic() < deadline:
            start = stream.tell()
            line = stream.readline(MAX_LINE + 1)
            prefix = line[:256]
            if len(line) > MAX_LINE:
                # Skip oversized content records without retaining their text.
                while line and not line.endswith(b'\n'):
                    line = stream.readline(MAX_LINE + 1)
                if not line.endswith(b'\n'):
                    stream.seek(start); break
                if any(tag in prefix for tag in (b'"turn_context"', b'"event_msg"', b'"assistant"')):
                    state['partial'] = True
                offset = stream.tell(); continue
            if not line.endswith(b'\n'):
                break
            offset = stream.tell()
            # Content-bearing records dominate large transcripts. Only decode
            # relevant top-level event kinds; nothing from prompts is stored.
            prefix = line[:256]
            wanted = (b'"session_meta"', b'"turn_context"', b'"event_msg"') if provider == 'codex' else (b'"assistant"',)
            if not any(tag in prefix for tag in wanted):
                continue
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    consume(db, key, provider, state, event)
            except (ValueError, TypeError, RecursionError):
                state['partial'] = True
        db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?,?)',
                   (key, provider, st.st_dev, st.st_ino, offset, st.st_mtime_ns, st.st_size, json.dumps(state)))
        return key, offset < st.st_size


def roots(home):
    codex = Path(os.environ.get('CODEX_HOME') or home / '.codex')
    claude = Path(os.environ.get('CLAUDE_CONFIG_DIR') or home / '.claude')
    return [('codex', codex / 'sessions'), ('codex', codex / 'archived_sessions'), ('claude', claude / 'projects')]


def scan(db, locations, budget=6):
    deadline = time.monotonic() + budget
    found, partial = set(), False
    # Visit newest files first so the first response contains today's activity.
    files = []
    for provider, root in locations:
        if root.is_dir():
            for path in root.rglob('*.jsonl'):
                try:
                    if not path.is_symlink():
                        files.append((path.stat().st_mtime_ns, path, provider))
                except OSError:
                    partial = True
    for _, path, provider in sorted(files, reverse=True):
        key = hashlib.sha256(os.fsencode(path)).hexdigest()
        found.add(key)
        if time.monotonic() >= deadline:
            partial = True; continue
        try:
            _, unfinished = index_file(db, path, provider, deadline)
            partial |= unfinished
        except OSError:
            partial = True
    # Deleted/relocated sources must not keep contributing phantom usage.
    for row in db.execute('SELECT key FROM files').fetchall():
        if row['key'] not in found:
            db.execute('DELETE FROM files WHERE key=?', (row['key'],))
            db.execute('DELETE FROM events WHERE file=?', (row['key'],))
    db.commit()
    return partial


def empty():
    return dict(input=0, output=0, cached=0, write=0, long_write=0, reasoning=0,
                tokens=0, requests=0, cost=0.0, savings=0.0, unpriced=0)


def add(total, event, price):
    for key in FIELDS:
        total[key] += event[key]
    total['tokens'] += event['input'] + event['output']
    total['requests'] += 1
    cost, savings = price
    if cost is None:
        total['unpriced'] += 1
    else:
        total['cost'] += cost
        total['savings'] += savings


def overview(db, now=None, partial=False):
    now = now or time.time()
    today = datetime.fromtimestamp(now).date()
    cutoff = datetime.combine(today - timedelta(days=29), day_time()).timestamp()
    unique = {}
    for event in db.execute('SELECT * FROM events WHERE stamp>=? AND stamp<=? ORDER BY stamp', (cutoff, now)):
        # Moving/copying a session into the archive must not count it twice.
        identity = (event['provider'], event['session'], event['key'].partition(':')[2])
        previous = unique.get(identity)
        if previous is None or event['input'] + event['output'] >= previous['input'] + previous['output']:
            unique[identity] = event
    events = [(row, estimate(row['model'], row)) for row in unique.values()]
    periods = {}
    for key, days in (('today', 1), ('week', 7), ('month', 30)):
        start = today - timedelta(days=days-1)
        total, providers, models, sessions = empty(), {'codex':empty(), 'claude':empty()}, {}, set()
        buckets = [dict(label=f'{i:02}:00', **empty()) for i in range(24)] if days == 1 else [
            dict(label=(start+timedelta(days=i)).isoformat(), **empty()) for i in range(days)]
        for event, price in events:
            at = datetime.fromtimestamp(event['stamp'])
            if at.date() < start:
                continue
            model = event['model'] or 'Unknown model'
            for target in (total, providers[event['provider']], models.setdefault(model, empty()),
                           buckets[at.hour if days == 1 else (at.date()-start).days]):
                add(target, event, price)
            sessions.add(event['session'])
        total['sessions'] = len(sessions)
        total['cacheRate'] = total['cached'] / total['input'] if total['input'] else 0
        total['activeDays'] = sum(b['tokens'] > 0 for b in buckets) if days > 1 else int(total['tokens'] > 0)
        periods[key] = dict(total=total, providers=providers, models=[dict(name=m, **v) for m,v in sorted(models.items())], buckets=buckets)
    activity = []
    for provider in ('codex', 'claude'):
        distinct = {}
        for row in db.execute('SELECT key,state FROM files WHERE provider=?', (provider,)):
            state = json.loads(row['state']); session = state.get('session',row['key'])
            if state.get('active',0) >= distinct.get(session,{}).get('active',0): distinct[session] = state
        states = list(distinct.values())
        latest = max(states, key=lambda s:s.get('active', 0), default={})
        active = sum(s.get('status') == 'working' and 0 <= now-s.get('active', 0) < 120 for s in states)
        activity.append(dict(provider=provider, model=latest.get('model', ''), last=latest.get('active', 0), active=active))
        partial |= any(s.get('partial', False) for s in states)
    return dict(ok=True, checked=now, pricingDate=VERIFIED, partial=partial, periods=periods, activity=activity)


def snapshot(home=None, cache=None, now=None):
    home = Path(home or Path.home())
    cache = Path(cache or Path(os.environ.get('XDG_CACHE_HOME') or home / '.cache') / 'monet/agent-history.sqlite')
    with closing(database(cache)) as db:
        partial = scan(db, roots(home))
        return overview(db, now, partial)


if __name__ == '__main__':
    try:
        print(json.dumps(snapshot()))
    except (OSError, ValueError, sqlite3.Error):
        print(json.dumps({'ok':False}))
