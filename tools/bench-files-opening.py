#!/usr/bin/env python3
"""Measure mapped Files windows and completed listings on private Wayland outputs.

The baseline is the installed OS binary; the candidate is the account preview.
Only disposable folders/profiles/buses/compositors are used. Listing completion
does not imply thumbnail completion, physical-drive performance or sign-in.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def sample(program, workload, output, cache=None, timeout=15, library=None):
    import dbus
    with private_session() as env:
        folder = Path(env['HOME']).parent
        binary = folder / 'bin/kwin_wayland'; binary.parent.mkdir()
        shutil.copyfile(shutil.which('kwin_wayland'), binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland', XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE',
            WAYLAND_DISPLAY='monet-files-opening', KWIN_DRM_DEVICES='/dev/dri/renderD128',
            QT_FORCE_STDERR_LOGGING='1', QT_LOGGING_RULES='kwin_scripting.debug=true;js.debug=true;qml.debug=true', TMPDIR=env['XDG_RUNTIME_DIR'])
        for key in ('QT_QUICK_BACKEND','DISPLAY','QT_SCALE_FACTOR','QT_SCREEN_SCALE_FACTORS'):
            env.pop(key, None)
        if cache is not None: env['XDG_CACHE_HOME'] = str(cache)
        if library is not None: env['LD_LIBRARY_PATH'] = str(library)
        config = Path(env['XDG_CONFIG_HOME'])
        (config / 'kdeglobals').write_text('[General]\nColorScheme=MonetLight\nfont=Inter,10,-1,5,50,0,0,0,0,0\n[Icons]\nTheme=Monet\n[KDE]\nwidgetStyle=kvantum\n')
        (config / 'Kvantum').mkdir()
        (config / 'Kvantum/kvantum.kvconfig').write_text('[General]\ntheme=Monet\n')
        log_path = output / 'kwin.log'
        with log_path.open('w') as log, (output / 'files.log').open('w') as app_log:
            compositor = subprocess.Popen([str(binary), '--virtual', '--socket', env['WAYLAND_DISPLAY'],
                '--width','1280','--height','900','--no-lockscreen','--no-global-shortcuts','--no-kactivities'],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            app = None
            try:
                bus = dbus.bus.BusConnection(env['DBUS_SESSION_BUS_ADDRESS'])
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline and 'org.kde.KWin' not in bus.list_names():
                    if compositor.poll() is not None: raise RuntimeError(log_path.read_text())
                    time.sleep(.02)
                info = str(bus.get_object('org.kde.KWin','/KWin').supportInformation(dbus_interface='org.kde.KWin'))
                (output / 'support.txt').write_text(info)
                assert 'Compositing is active' in info and 'Compositing Type: OpenGL' in info, info
                script = folder / 'observe.js'
                script.write_text('workspace.windowAdded.connect(w => { if (String(w.resourceClass).includes("dolphin")) '
                    'console.log("MONET_FILES_MAPPED", JSON.stringify({pid:w.pid,wall:Date.now(),'
                    'ready:typeof w.readyForPainting === "boolean" ? w.readyForPainting : null})); });\nconsole.log("MONET_FILES_OBSERVER_READY");\n')
                scripting = dbus.Interface(bus.get_object('org.kde.KWin','/Scripting'),'org.kde.kwin.Scripting')
                ident = int(scripting.loadScript(str(script))); assert ident >= 0
                dbus.Interface(bus.get_object('org.kde.KWin','/Scripting/Script'+str(ident)),'org.kde.kwin.Script').run()
                deadline = time.monotonic() + 5
                while 'MONET_FILES_OBSERVER_READY' not in log_path.read_text():
                    assert time.monotonic() < deadline, 'Window observer did not become ready: '+log_path.read_text()
                    time.sleep(.01)
                wall = time.time() * 1000; started = time.monotonic()
                app = subprocess.Popen([str(program),'--new-window',str(workload)], env=env,
                    stdout=app_log, stderr=app_log, start_new_session=True)
                mapped = ready = None; service = None
                while time.monotonic() - started < timeout:
                    if app.poll() is not None: raise RuntimeError(app_log.name + ': ' + Path(app_log.name).read_text())
                    if mapped is None:
                        for line in log_path.read_text().splitlines():
                            if 'MONET_FILES_MAPPED ' in line:
                                value = json.loads(line.split('MONET_FILES_MAPPED ',1)[1])
                                if int(value['pid']) == app.pid:
                                    mapped = value; break
                    if ready is None:
                        service = service or next((str(n) for n in bus.list_names() if str(n).startswith('org.kde.dolphin-')), None)
                        if service:
                            try:
                                window = bus.get_object(service,'/dolphin/Dolphin_1')
                                state = json.loads(str(window.monetFilesState(dbus_interface='org.kde.dolphin.MainWindow',timeout=.5)))
                                if state and state['tabs'][state['active']]['folders'] == [str(workload)]:
                                    ready = round((time.monotonic()-started)*1000,3)
                            except (dbus.DBusException,ValueError,KeyError,TypeError): pass
                    if mapped is not None and ready is not None: break
                    time.sleep(.005)
                assert mapped is not None and ready is not None, (mapped,ready,app_log.name)
                assert abs((time.time()*1000-wall) - (time.monotonic()-started)*1000) < 50, 'Wall clock changed during mapping measurement'
                assert mapped['ready'] is not False, 'Mapped client was not ready for painting'
                mapped_ms = round(mapped['wall']-wall,3)
                return dict(mapped_window_ms=mapped_ms, listing_ready_ms=ready,
                    window_and_listing_ms=max(mapped_ms,ready), ready_for_painting=mapped['ready'],
                    executable=str(Path(f'/proc/{app.pid}/exe').resolve()))
            finally:
                if app is not None: stop(app)
                stop(compositor)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=Path('/usr/bin/dolphin'))
    parser.add_argument('--candidate',type=Path,default=Path.home()/'.local/bin/dolphin')
    parser.add_argument('--samples',type=int,default=3)
    parser.add_argument('--entries',type=int,default=1000)
    parser.add_argument('--native-pair',type=Path,help='Also measure the verified native pair directly, without account-wrapper startup')
    parser.add_argument('--reuse-cache',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.samples<=20 or not 1<=args.entries<=20000: parser.error('samples: 1–20; entries: 1–20000')
    for path in (args.baseline,args.candidate):
        if not path.is_file(): parser.error('Missing executable: '+str(path))
    if args.native_pair:
        spec=importlib.util.spec_from_file_location('opening_files_bundle',ROOT/'image/files-recovery/bundle.py')
        bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
        manifest=json.loads((args.native_pair/'runtime.json').read_text());bundle.verify(manifest)
        for name,expected in manifest['files'].items():
            assert hashlib.sha256((args.native_pair/name).read_bytes()).hexdigest()==expected,name
        for target in manifest['targets']:
            bundle.compatible(target['path'],args.native_pair/Path(target['path']).name)
    args.output.mkdir(parents=True,exist_ok=True)
    report=dict(schema=1,kernel=platform.release(),scope='Actual installed baseline/account candidate, private virtual Wayland output, mapped client and completed local listing; no thumbnail/physical-drive/sign-in claim',
        cache='OS page cache uncontrolled; '+('per-variant app cache shared after first sample' if args.reuse_cache else 'empty per-sample app cache'),entries=args.entries,samples={})
    with tempfile.TemporaryDirectory(prefix='monet-files-opening-') as temporary:
        folder=Path(temporary);workload=folder/'Listing';workload.mkdir()
        for i in range(args.entries): (workload/f'item-{i:05}.txt').write_text('Monet startup fixture\n')
        programs={'baseline':args.baseline,'candidate':args.candidate}
        if args.native_pair:programs['native']=args.native_pair/'dolphin'
        report['programs']={name:str(path) for name,path in programs.items()}
        caches={name:folder/(name+'-cache') for name in programs}
        for path in caches.values():path.mkdir(mode=0o700)
        readings={name:[] for name in programs}
        for index in range(args.samples):
            order=list(programs);order=order[index%len(order):]+order[:index%len(order)]
            if index%2:order.reverse()
            for variant in order:
                output=args.output/(variant+'-'+str(index));output.mkdir()
                reading=sample(programs[variant],workload,output,caches[variant] if args.reuse_cache else None,
                    library=args.native_pair if variant=='native' else None)
                readings[variant].append(reading)
        for variant,values in readings.items():
            report['samples'][variant]=dict(raw=values, medians={key:round(statistics.median(v[key] for v in values),3)
                for key in ('mapped_window_ms','listing_ready_ms','window_and_listing_ms')})
    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:value['medians'] for key,value in report['samples'].items()},indent=2))


if __name__=='__main__':main()
