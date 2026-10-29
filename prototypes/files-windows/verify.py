"""Run only in the isolated VM runtime prepared by the Files build fixture."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

root = Path('/var/home/j/.local/monet-files-build')
home = root / 'fixture'
live = root / 'live'
os.environ.update(json.loads((live / 'nested-env.json').read_text()))
os.environ['TMPDIR'] = str(live)
loader = importlib.machinery.SourceFileLoader('resume', str(live / 'monet-resume'))
r = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(r)
f = r.files_helper()

def wait(check):
    for _ in range(100):
        value = check()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError('Live Files condition did not become true')

def windows():
    return [w for w in r.window_snapshot() if w['app'] == r.FILES]

def states():
    frames = windows()
    result = {}
    for pid in {w['pid'] for w in frames}:
        result.update(f.capture_windows(pid, [w for w in frames if w['pid'] == pid]))
    return result

def action(pid, object_path, name):
    try:
        r.dbus(f'org.kde.dolphin-{pid}', object_path, 'org.kde.KMainWindow', 'activateAction', name)
    except RuntimeError as error:
        if str(error) != 'org.freedesktop.DBus.Error.NoReply':
            raise

def paths(pid):
    from gi.repository import Gio, GLib
    return f.native_paths(pid, Gio.bus_get_sync(Gio.BusType.SESSION, None), Gio, GLib)

def close_all():
    for pid in {w['pid'] for w in windows()}:
        for path in paths(pid):
            action(pid, path, 'file_quit')
    wait(lambda: not windows())

def stable_frame(frame):
    return {k: v for k, v in frame.items() if k not in ('active', 'stack')}

def restore(path):
    return r.restore(path, live / 'off', lambda: [r.FILES] if windows() else [], lambda _: True,
                     lambda _: (_ for _ in ()).throw(AssertionError('Generic launch')))

def tab(folder, label, selected):
    return {'folders': [str(folder)], 'active': 0, 'label': label, 'sizes': [800],
            'views': [{'current': str(folder / selected), 'selected': [str(folder / selected)],
                       'expanded': [], 'scroll': [0, 80], 'maximum': [0, 10000]}]}

assert not windows(), 'This fixture requires its own empty compositor'
folders = [home / name for name in ('Shared folder', 'Late folder')]
for folder in folders:
    folder.mkdir(exist_ok=True)
    (folder / '.directory').write_text('[Dolphin]\nVersion=4\nViewMode=1\n')
    for i in range(90):
        (folder / f'file-{i:03d}.txt').write_text(f'Synthetic fixture {i}\n')
(home / '.config/dolphinrc').write_text('[General]\nRememberOpenedTabs=false\nConfirmClosingMultipleTabs=false\nGlobalViewProps=false\n')
seeds = [{'tabs': [tab(folders[0], 'First window', 'file-005.txt')], 'active': 0},
         {'tabs': [tab(folders[0], 'Surviving window', 'file-007.txt')], 'active': 0},
         {'tabs': [tab(folders[1], 'Late window', 'file-009.txt')], 'active': 0}]
session = home / '.config/session/dolphin_monet-shared-fixture_'
session.parent.mkdir(exist_ok=True)
text = '\n\n'.join(f.session_text(s).split('\n\n[Number]')[0].replace('[1]', f'[{i}]', 1)
                    for i, s in enumerate(seeds, 1))
text += '\n\n[Number]\nNumberOfWindows=3\n'
for i in range(1, 4):
    text += f'\n[WindowProperties{i}]\nClassName=DolphinMainWindow\nObjectName=Dolphin#{i}\n'
session.write_text(text)
process = subprocess.Popen([str(root / 'monet_shared_files')], stdin=subprocess.DEVNULL,
                           stdout=(live / 'files.log').open('w'), stderr=subprocess.STDOUT)
def seeded():
    assert process.poll() is None, (process.returncode, (live / 'files.log').read_text())
    return len(windows()) == 3
wait(seeded)
wait(lambda: len(states()) == 3 and all(f.valid(s) for s in states().values()))
before = windows()
assert {w['pid'] for w in before} == {process.pid}, before
for i, frame in enumerate(before):
    placed = copy.deepcopy(frame)
    placed['rect'].update(x=20 + i * 290, y=40 + i * 80, width=850, height=610)
    r.place_windows([placed], [frame], set())
time.sleep(1)
before = windows()
trip = r.checkpoint([r.FILES], before)
assert len(trip['groups'][r.FILES]) == 3
assert all(len(g['windows']) == 1 and f.valid(g['files']) for g in trip['groups'][r.FILES])
(live / 'shared-checkpoint.json').write_text(json.dumps(trip, indent=2))
original = states()
assert {s['tabs'][0]['label'] for s in original.values()} == {s['tabs'][0]['label'] for s in seeds}
assert f.capture(process.pid) is None, 'Single-window API must refuse sibling ambiguity'

# Closing object 1 must leave object 2/3 discoverable, with their newer choices intact.
objects = paths(process.pid)
assert '/dolphin/Dolphin_1' in objects
first_state = json.loads(r.dbus(f'org.kde.dolphin-{process.pid}', '/dolphin/Dolphin_1',
                        'org.kde.dolphin.MainWindow', 'monetFilesState')[0])
closed_id = next(ident for ident, state in original.items() if state == first_state)
action(process.pid, '/dolphin/Dolphin_1', 'file_quit')
wait(lambda: len(windows()) == 2)
assert '/dolphin/Dolphin_1' not in paths(process.pid)
action(process.pid, paths(process.pid)[0], 'edit_select_all')
wait(lambda: any(len(s['tabs'][0]['views'][0]['selected']) > 20 for s in states().values()))
survivors = states()
surviving_frames = {w['id']: stable_frame(w) for w in windows()}
trip['cancelled_boot'] = r.boot_id()
path = live / 'cancelled.json'
r.atomic_write(path, trip)
assert restore(path) == [r.FILES]
assert not path.exists()
after = states()
assert len(after) == 3
assert all(after[ident] == state for ident, state in survivors.items())
assert all(stable_frame(w) == surviving_frames[w['id']] for w in windows() if w['id'] in survivors)
returned = next(w for w in windows() if w['id'] not in survivors)
closed_frame = next(w for w in before if w['id'] == closed_id)
assert returned['rect'] == closed_frame['rect'], (returned, closed_frame)
assert f.restored(original[closed_id], after[returned['id']])
assert restore(path) == [] and len(windows()) == 3
proof = {'three_native_windows_one_process': True, 'exact_identity_capture': True,
         'first_object_closure_supported': True, 'changed_survivors_untouched': True,
         'closed_sibling_reopened_once_and_placed': True}
(live / 'cancelled-proof.json').write_text(json.dumps(proof, indent=2))

# A disconnected folder stays pending while the other windows return only once.
trip = r.checkpoint([r.FILES], windows())
trip.update(version=2, boot='controlled-previous-boot')
close_all()
hidden = folders[1].with_name('Temporarily disconnected')
folders[1].rename(hidden)
path = live / 'late.json'
r.atomic_write(path, trip)
assert restore(path) == []
assert len(windows()) == 2 and path.exists()
pending = r.read_state(path)['groups'][r.FILES]
assert sum(g['status'] == 'folders-restored' for g in pending) == 2
ids = {w['id'] for w in windows()}
hidden.rename(folders[1])
assert restore(path) == [r.FILES]
assert not path.exists() and len(windows()) == 3
assert ids <= {w['id'] for w in windows()}
for group in trip['groups'][r.FILES]:
    current = states()
    candidates = [ident for ident, state in current.items() if state['tabs'][0]['label'] == group['files']['tabs'][0]['label']]
    assert len(candidates) == 1 and f.restored(group['files'], current[candidates[0]])
assert restore(path) == [] and len(windows()) == 3
proof.update(missing_folder_retained=True, retry_only_opens_missing_window=True, repeated_retry_no_duplicates=True)
(live / 'proof.json').write_text(json.dumps(proof, indent=2))
print(json.dumps(proof), flush=True)
