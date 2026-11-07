#!/usr/bin/env python3
"""Compare Quick Settings idle work on private services and a disposable profile.

Run inside the desktop test image, which supplies MONET_ACTIVITY_FIXTURE.
The baseline is an actual Git revision; the candidate is the worktree. Helper
responses are controlled, so CPU/scheduler counts describe this Qt fixture,
not real hardware queries, whole-desktop wakeups or battery-life improvements.
"""
import argparse
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def stage(folder, revision=None):
    data = folder / 'data'; ui = data / 'plasma/plasmoids/org.monet.quick/contents/ui'
    if revision:
        for base in ('linux/share/plasma/plasmoids/org.monet.quick', 'linux/share/monet/widgets'):
            files = git('ls-tree', '-r', '--name-only', revision, '--', base).decode().splitlines()
            for name in files:
                relative = Path(name).relative_to(base)
                destination = data/'plasma/plasmoids/org.monet.quick'/relative if 'plasmoids' in base else ui/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(git('show', revision + ':' + name))
    else:
        shutil.copytree(ROOT/'linux/share/plasma/plasmoids/org.monet.quick', ui.parent.parent)
        for part in (ROOT/'linux/share/monet/widgets').iterdir():
            if part.is_file(): shutil.copy2(part, ui/part.name)
    for part in ui.glob('*.qml'):
        source = part.read_text().replace('@LIBEXECDIR@', str(folder)).replace('@BINDIR@', str(folder)).replace('@DATADIR@', '/usr/share')
        if part.name == 'SessionActivity.qml':
            source = source.replace('property string outputName: Screen.name', 'property string outputName: "eDP-1"')
        part.write_text(source)
    main = ui/'main.qml'; source = main.read_text()
    source = source[:source.rfind('}')] + '\n Timer { interval: 150; running: true; onTriggered: root.expanded = true }\n}\n'
    main.write_text(source)
    script = folder/'monet-quick'
    script.write_text('''#!/usr/bin/python3
import json, sys, time
with open(LOG, 'a') as output: output.write(json.dumps(sys.argv[1:])+'\\n')
command = sys.argv[1] if len(sys.argv)>1 else ''
if command == 'listen': time.sleep(60); raise SystemExit(0)
if command == 'outputs': result=[]
elif command == 'status': result=dict(wifi=True, network='', bluetooth=False,night=False,quiet=False,
    volume=40,mic=30,brightness=50,keyboard=None,light='mist',battery=80,plugged=True)
else: result={}
print(json.dumps(result))
'''.replace('LOG', repr(str(folder/'calls.jsonl'))))
    script.chmod(0o700)
    return data


def process_stats(pid):
    raw = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    # Fields after comm begin with state (3); utime/stime are fields 14/15.
    result = dict(cpu_ticks=int(raw[11])+int(raw[12]), threads={})
    for task in Path(f'/proc/{pid}/task').iterdir():
        try:
            status = task.joinpath('status').read_text()
            voluntary = re.search(r'^voluntary_ctxt_switches:\s+(\d+)$', status, re.M)
            result['threads'][task.name] = int(voluntary[1]) if voluntary else 0
        except FileNotFoundError: pass
    return result


def sample(revision, seconds, sample_index):
    import dbus
    with tempfile.TemporaryDirectory(prefix='monet-idle-') as temporary, private_session() as env:
        folder = Path(temporary); data = stage(folder, revision)
        env.update(XDG_DATA_HOME=str(data), DBUS_SYSTEM_BUS_ADDRESS=env['DBUS_SESSION_BUS_ADDRESS'],
                   WAYLAND_DISPLAY='monet-activity-test', QT_QPA_PLATFORMTHEME='kde')
        processes = []
        with (folder/'service.log').open('w') as service_log, (folder/'widget.log').open('w') as widget_log:
            service = subprocess.Popen([os.environ['MONET_ACTIVITY_FIXTURE'], '--fixture'], env=env,
                                       stdout=subprocess.PIPE, stderr=service_log, text=True, start_new_session=True)
            processes.append(service)
            try:
                if not select.select([service.stdout], [], [], 5)[0] or service.stdout.readline().strip() != 'READY':
                    raise RuntimeError('Private activity fixture failed to start')
                bus = dbus.bus.BusConnection(env['DBUS_SESSION_BUS_ADDRESS'])
                control = dbus.Interface(bus.get_object('org.monet.ActivityFixture', '/Fixture'), 'org.monet.ActivityFixture')
                widget = subprocess.Popen(['plasmawindowed', 'org.monet.quick'], env=env, stdout=widget_log,
                                          stderr=widget_log, start_new_session=True); processes.append(widget)
                time.sleep(2)

                def calls():
                    path = folder/'calls.jsonl'
                    values = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
                    return [v for v in values if v and v[0] in ('status','outputs')]

                report = dict(variant='baseline' if revision else 'candidate', sample=sample_index, phases={})
                for phase in ('visible', 'locked', 'display-off'):
                    if phase == 'locked': control.SetLocked(True)
                    elif phase == 'display-off':
                        control.SetMode('eDP-1', dbus.UInt32(3)); control.SetLocked(False)
                    time.sleep(.4)
                    if widget.poll() is not None: raise RuntimeError((folder/'widget.log').read_text())
                    before, count = process_stats(widget.pid), len(calls())
                    started = time.monotonic(); time.sleep(seconds); elapsed = time.monotonic()-started
                    after = process_stats(widget.pid)
                    report['phases'][phase] = dict(seconds=round(elapsed,3), helper_reads=len(calls())-count,
                        cpu_ms=round(1000*(after['cpu_ticks']-before['cpu_ticks'])/os.sysconf('SC_CLK_TCK'),3),
                        voluntary_context_switches=sum(max(0,value-before['threads'].get(tid,0))
                                                       for tid,value in after['threads'].items()))
                report['native_metrics'] = json.loads(str(control.Metrics()))
                report['diagnostics'] = [line for line in (folder/'widget.log').read_text().splitlines()
                                         if any(token in line for token in ('ReferenceError', 'TypeError', 'is not installed'))]
                if report['diagnostics']: raise RuntimeError(report['diagnostics'])
                return report
            finally:
                for process in reversed(processes): stop(process)
                service.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='HEAD')
    parser.add_argument('--seconds', type=float, default=12)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 3 <= args.seconds <= 30 or not 1 <= args.samples <= 10:
        parser.error('seconds: 3–30; samples: 1–10')
    if not os.environ.get('MONET_ACTIVITY_FIXTURE'): parser.error('Run inside the native desktop test image')
    revision = git('rev-parse', '--verify', '--end-of-options', args.baseline + '^{commit}').decode().strip()
    report = dict(schema=1, baseline=revision, rendering='Qt offscreen/software',
                  scope='Quick Settings process only, actual 3-second polling interval, controlled helper replies',
                  limits='CPU and voluntary context switches are fixture observations; not hardware wakeups or battery life', samples=[])
    for index in range(args.samples):
        for source in ((revision,None) if index % 2 == 0 else (None,revision)):
            result = sample(source, args.seconds, index)
            report['samples'].append(result); print(json.dumps(result), flush=True)
            args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__': main()
