#!/usr/bin/env python3
"""Compare real app first/ready frames against a Git revision on the same runtime.

Profiles and app caches are disposable. Cached system catalog/installed apps are
read, metadata refresh and optional Python network requests are suppressed. OS
page cache is not flushed. A common probe adds equal instrumentation overhead;
results describe these sessions, not sign-in, cold boot or remote artwork.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import select
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


@contextlib.contextmanager
def wayland_display(output):
    import dbus
    output.parent.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        folder = Path(env['HOME']).parent
        binary = folder / 'bin/kwin_wayland'; binary.parent.mkdir()
        shutil.copyfile(shutil.which('kwin_wayland'), binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland', XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE',
            WAYLAND_DISPLAY='monet-app-readiness', KWIN_DRM_DEVICES='/dev/dri/renderD128')
        env.pop('QT_QUICK_BACKEND', None)
        with output.with_suffix('.kwin.log').open('w') as log:
            process = subprocess.Popen([str(binary),'--virtual','--socket',env['WAYLAND_DISPLAY'],
                '--width','1280','--height','900','--no-lockscreen','--no-global-shortcuts','--no-kactivities'],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                bus = dbus.bus.BusConnection(env['DBUS_SESSION_BUS_ADDRESS'])
                deadline = time.monotonic() + 15
                while 'org.kde.KWin' not in bus.list_names():
                    assert process.poll() is None and time.monotonic() < deadline, 'Private compositor did not start'
                    time.sleep(.02)
                info = str(bus.get_object('org.kde.KWin','/KWin').supportInformation(dbus_interface='org.kde.KWin'))
                output.with_suffix('.kwin-support.txt').write_text(info)
                assert 'Compositing is active' in info and 'Compositing Type: OpenGL' in info, info
                yield str(Path(env['XDG_RUNTIME_DIR']) / env['WAYLAND_DISPLAY'])
            finally: stop(process)


def stage(destination, revision=None):
    destination.mkdir()
    if revision:
        archive = subprocess.check_output(['git', 'archive', revision, 'linux'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(destination, filter='data')
    else:
        shutil.copytree(ROOT / 'linux', destination / 'linux', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    helpers = destination / 'libexec'; helpers.mkdir()
    share = destination / 'linux/share'
    for source in (destination / 'linux/libexec').iterdir():
        if not source.is_file(): continue
        text = source.read_text().replace('@BINDIR@', '/usr/bin').replace('@DATADIR@', str(share)).replace('@LIBEXECDIR@', str(helpers))
        target = helpers / source.name; target.write_text(text); target.chmod(0o700)
    region = ROOT / 'setup/monet_setup/region.py'
    if region.exists(): shutil.copy2(region, helpers / 'monet_region.py')
    return helpers


def sample(app, helpers, env, timeout, probe=None):
    command = [sys.executable, str(probe or ROOT / 'tests/fixtures/app-readiness-probe.py'), app, str(helpers / ('monet-' + app))]
    await_cache = app == 'store' and 'CATALOG_CACHE_SCHEMA' in (helpers / 'monet-store').read_text()
    cache_settled = False
    capture_complete = not env.get('MONET_READINESS_CAPTURE')
    started = time.monotonic()
    process = subprocess.Popen(command, env=dict(env, TMPDIR=env['XDG_RUNTIME_DIR'], MONET_STARTUP_TIMING='1', QT_FORCE_STDERR_LOGGING='1'),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    events, diagnostic, pending = [], [], {'stdout': '', 'stderr': ''}
    result = {}
    try:
        deadline = started + timeout
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout, process.stderr], [], [], .05)
            for stream in readable:
                part = os.read(stream.fileno(), 65536)
                if not part: continue
                key = 'stdout' if stream is process.stdout else 'stderr'
                pending[key] += part.decode('utf-8', 'replace')
                lines = pending[key].split('\n'); pending[key] = lines.pop()
                for line in lines:
                    common = line.startswith('MONET_READINESS ')
                    internal = line.startswith('MONET_STARTUP ')
                    if common or internal:
                        event = json.loads(line[len('MONET_READINESS ' if common else 'MONET_STARTUP '):])
                        event['external_ms'] = round((time.monotonic() - started) * 1000, 3)
                        event['channel'] = 'probe' if common else 'app'
                        events.append(event)
                        if common and event['phase'] in ('first-frame', 'ready-frame'):
                            result[event['phase']] = event['external_ms']
                        if internal and event['phase'] == 'catalog-cache-settled': cache_settled = True
                        if common and event['phase']=='capture-complete':
                            if not event.get('ok'): return dict(result, error='ready-frame capture failed', events=events)
                            capture_complete = True
                        if 'ready-frame' in result and (not await_cache or cache_settled) and capture_complete:
                            return dict(result, events=events)
                    else:
                        diagnostic.append(line); diagnostic = diagnostic[-20:]
            if process.poll() is not None: break
        return dict(result, error='ready frame not observed', exit_code=process.poll(), events=events, diagnostic=diagnostic)
    finally:
        stop(process); process.stdout.close(); process.stderr.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='HEAD')
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--apps', nargs='+', choices=('settings', 'store'), default=['settings', 'store'])
    parser.add_argument('--reuse-cache', action='store_true')
    parser.add_argument('--wayland', action='store_true', help='Use a private virtual KWin/OpenGL display and native KDE controls')
    parser.add_argument('--candidate-helpers',type=Path,help='Measure already-installed helpers as the candidate, using a private profile')
    parser.add_argument('--capture',action='store_true',help='Retain a ready-frame image from the first sample of each app/variant')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if not 1 <= args.samples <= 30 or not 1 <= args.timeout <= 60: parser.error('samples: 1–30; timeout: 1–60')
    revision = subprocess.check_output(['git', 'rev-parse', args.baseline + '^{commit}'], cwd=ROOT, text=True).strip()
    report = {'schema': 1, 'baseline': revision, 'candidate': 'worktree', 'python': platform.python_version(),
        'scope': 'Source apps, common observation probe, first/initial-data-ready submitted frames; excludes remote artwork and whole-OS readiness',
        'rendering': 'offscreen/software', 'cache': 'OS cache uncontrolled; '+('per-variant app cache shared after first sample' if args.reuse_cache else 'empty per-sample app cache'),
        'services': 'private session/system buses; cached system catalog and installed Flatpaks read; refresh and optional Python network disabled', 'apps': {}}
    report['source_hashes'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        'tools/bench-app-readiness.py', 'tests/fixtures/app-readiness-probe.py', 'linux/libexec/monet-games',
        'linux/libexec/monet-settings', 'linux/libexec/monet-store', 'linux/share/monet/settings-app/MonetSettings.qml', 'linux/share/monet/store-app/Store.qml')}
    with tempfile.TemporaryDirectory(prefix='monet-readiness-') as temporary, contextlib.ExitStack() as stack:
        folder = Path(temporary)
        display = stack.enter_context(wayland_display(args.output)) if args.wayland else None
        if display: report['rendering'] = 'Native Wayland clients, KDE controls, private virtual KWin/OpenGL display; support information retained'
        probe = folder / 'app-readiness-probe.py'; shutil.copy2(ROOT / 'tests/fixtures/app-readiness-probe.py', probe)
        helpers = {'baseline': stage(folder / 'baseline', revision), 'candidate': args.candidate_helpers or stage(folder / 'candidate')}
        if args.candidate_helpers:
            import ast
            report['candidate']='installed helpers in '+str(args.candidate_helpers)
            report['installed_hashes']={}
            for name in ('monet-settings','monet-store','monet-games','monet-quick','monet_native_preview.py','native-preview.json'):
                path=args.candidate_helpers/name
                if path.is_file():report['installed_hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            for name in ('settings','store'):
                tree=ast.parse((args.candidate_helpers/('monet-'+name)).read_text())
                value=next(node.value for node in tree.body if isinstance(node,ast.Assign) and
                    any(isinstance(target,ast.Name) and target.id=='DATADIR' for target in node.targets))
                data=Path(ast.literal_eval(value))/'monet'
                for kind in (name+'-app','games'):
                    for path in (data/kind).rglob('*'):
                        if path.is_file() and path.suffix in ('.qml','.js'):
                            report['installed_hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        caches = {name: folder / (name + '-cache') for name in helpers}
        for path in caches.values(): path.mkdir(mode=0o700)
        for app in args.apps:
            readings = {name: [] for name in helpers}
            for index in range(args.samples):
                for variant in (['baseline', 'candidate'] if index % 2 == 0 else ['candidate', 'baseline']):
                    with private_session() as env:
                        if display:
                            env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY=display, QSG_RHI_BACKEND='opengl',
                                QT_QPA_PLATFORMTHEME='kde', QSG_INFO='1')
                            env.pop('QT_QUICK_BACKEND', None); env.pop('QT_QUICK_CONTROLS_STYLE', None)
                        if args.reuse_cache: env['XDG_CACHE_HOME'] = str(caches[variant])
                        if args.capture and index==0:
                            env['MONET_READINESS_CAPTURE']=str(args.output.with_name(args.output.stem+'-'+app+'-'+variant+'.png').resolve())
                        result = sample(app, helpers[variant], env, args.timeout, probe)
                        result.update(sample=index, variant=variant)
                        readings[variant].append(result)
            report['apps'][app] = {}
            for variant, values in readings.items():
                totals = {}
                for phase in ('first-frame', 'ready-frame'):
                    times = [item[phase] for item in values if phase in item]
                    totals[phase] = dict(median_ms=round(statistics.median(times), 3) if times else None,
                                         min_ms=min(times) if times else None, max_ms=max(times) if times else None)
                report['apps'][app][variant] = {'samples': values, 'timings': totals}
    report['worktree_changed_during_measurement'] = any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected
        for name, expected in report['source_hashes'].items())
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({app: {variant: values['timings'] for variant, values in variants.items()} for app, variants in report['apps'].items()}, indent=2))
    return int(any('error' in sample for variants in report['apps'].values() for values in variants.values() for sample in values['samples']))


if __name__ == '__main__': raise SystemExit(main())
