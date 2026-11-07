#!/usr/bin/env python3
"""Measure native Settings/Store first frames in isolated software-rendered sessions.

No installed files, real profiles, OS caches or running windows are changed.
These are clean-profile Qt startup timings, not full app readiness or laptop
cold-start measurements. MONET_STARTUP_TIMING is otherwise disabled by default.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import select
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def sample(app, env, helpers, timeout, verify_store_start=False):
    command = [sys.executable, str(helpers / ('monet-' + app))]
    if app == 'settings': command.append('power')
    started = time.monotonic()
    process = subprocess.Popen(command, env=dict(env, MONET_STARTUP_TIMING='1', TMPDIR=env['XDG_RUNTIME_DIR']),
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               start_new_session=True)
    events, messages = [], []
    first_frame_ms = None
    pending = ''
    deadline = started + timeout
    try:
        while time.monotonic() < deadline:
            if not select.select([process.stderr], [], [], min(.1, max(0, deadline - time.monotonic())))[0]:
                if process.poll() is not None: break
                continue
            chunk = os.read(process.stderr.fileno(), 65536)
            if not chunk:
                if process.poll() is not None: break
                continue
            pending += chunk.decode('utf-8', 'replace')
            lines = pending.split('\n'); pending = lines.pop()
            for line in lines:
                if line.startswith('MONET_STARTUP '):
                    event = json.loads(line[len('MONET_STARTUP '):])
                    events.append(event)
                    if event.get('phase') == 'first-frame':
                        first_frame_ms = round((time.monotonic()-started)*1000, 3)
                        if app != 'store' or not verify_store_start:
                            return dict(external_first_frame_ms=first_frame_ms, events=events)
                    if app == 'store' and verify_store_start and event.get('phase') == 'catalog-load-start':
                        if first_frame_ms is None:
                            return dict(error='catalog started before the first frame', events=events)
                        return dict(external_first_frame_ms=first_frame_ms, events=events)
                else:
                    messages.append(line.rstrip()); messages = messages[-12:]
        return dict(error='first-frame not observed', events=events, diagnostic=messages)
    finally:
        stop(process); process.stderr.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--apps', nargs='+', choices=('settings', 'store'), default=['settings', 'store'])
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--verify-store-start', action='store_true', help='Also verify the catalog worker starts after the Store first frame')
    parser.add_argument('--reuse-cache', action='store_true', help='Share a temporary Qt/app cache after the first sample; profiles stay isolated')
    parser.add_argument('--collect-host', action='store_true', help='Also collect read-only systemd startup traces')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.samples <= 30 or not 1 <= args.timeout <= 60: parser.error('samples: 1–30; timeout: 1–60 seconds')
    report = dict(schema=1, python=platform.python_version(), rendering='Qt offscreen/software',
                  cache_state=('Uncontrolled OS page cache; shared temporary app cache after the first sample' if args.reuse_cache
                               else 'Uncontrolled OS page cache; clean profile and empty app cache per sample'),
                  scope='First rendered frame only; initial data readiness and Files UI timing remain separate', apps={})
    if args.collect_host:
        report['host_startup'] = {}
        for name, command in [('system', ['systemd-analyze', 'time']),
                              ('user_critical_chain', ['systemd-analyze', '--user', 'critical-chain', 'plasma-workspace.target'])]:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                report['host_startup'][name] = dict(code=result.returncode, text=result.stdout.strip())
            except (OSError, subprocess.TimeoutExpired) as error:
                report['host_startup'][name] = dict(error=type(error).__name__)
    with tempfile.TemporaryDirectory(prefix='monet-startup-') as folder:
        helpers = Path(folder) / 'libexec'; helpers.mkdir()
        shared_cache = Path(folder) / 'cache'; shared_cache.mkdir(mode=0o700)
        for source in (ROOT / 'linux/libexec').iterdir():
            if not source.is_file(): continue
            text = source.read_text().replace('@BINDIR@', '/usr/bin').replace('@DATADIR@', str(ROOT / 'linux/share')).replace('@LIBEXECDIR@', str(helpers))
            target = helpers / source.name; target.write_text(text); target.chmod(0o700)
        (helpers / 'monet_region.py').write_bytes((ROOT / 'setup/monet_setup/region.py').read_bytes())
        for app in args.apps:
            readings = []
            for index in range(args.samples):
                with private_session() as env:
                    if args.reuse_cache: env['XDG_CACHE_HOME'] = str(shared_cache)
                    readings.append(sample(app, env, helpers, args.timeout, args.verify_store_start))
            values = [item['external_first_frame_ms'] for item in readings if 'external_first_frame_ms' in item]
            report['apps'][app] = dict(samples=readings, median_ms=round(statistics.median(values), 3) if values else None,
                                       min_ms=min(values) if values else None, max_ms=max(values) if values else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({app: {key: value for key, value in result.items() if key != 'samples'} for app, result in report['apps'].items()}, indent=2))
    return int(any('error' in item for result in report['apps'].values() for item in result['samples']))


if __name__ == '__main__':
    raise SystemExit(main())
