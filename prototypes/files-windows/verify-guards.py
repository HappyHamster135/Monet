"""Companion check after verify.py, in the same isolated compositor."""
from pathlib import Path
exec(Path(__file__).with_name('verify.py').read_text().split('assert not windows(),')[0])
close_all()
process = subprocess.Popen([str(root / 'monet_shared_files')], stdin=subprocess.DEVNULL,
                           stdout=(live / 'guard-files.log').open('w'), stderr=subprocess.STDOUT)
wait(lambda: len(windows()) == 3)
wait(lambda: len(states()) == 3)
try:
    r.dbus('org.kde.KWin', '/Plugins', 'org.kde.KWin.Plugins', 'UnloadPlugin', 'monet_window_identity')
    assert f.capture(process.pid, windows=True) is None
    refused = r.checkpoint([r.FILES], windows())
    assert len(refused['groups'][r.FILES]) == 3
    assert all(g['files'] is None for g in refused['groups'][r.FILES])
    assert f.capture(process.pid) is None
    refused.update(version=2, boot='controlled-previous-boot')
    path = live / 'refused.json'
    r.atomic_write(path, refused)
    assert restore(path) == [] and len(windows()) == 3
    assert all(g['status'] == 'unconfirmed' for g in r.read_state(path)['groups'][r.FILES])
    r.discard(path, r.read_state(path))
    for object_path in paths(process.pid)[:2]:
        action(process.pid, object_path, 'file_quit')
    wait(lambda: len(windows()) == 1)
    assert paths(process.pid) == ['/dolphin/Dolphin_3']
    current = wait(lambda: f.capture(process.pid))
    assert current['tabs'][0]['label'] == 'Late window'
    proof = {'missing_identity_leaves_shared_windows_unconfirmed': True,
             'no_ambiguous_single_window_fallback': True, 'refused_capture_does_not_duplicate_windows': True,
             'last_surviving_object_captured_without_identity_plugin': True}
    (live / 'guard-proof.json').write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof), flush=True)
finally:
    assert r.dbus('org.kde.KWin', '/Plugins', 'org.kde.KWin.Plugins', 'LoadPlugin', 'monet_window_identity')[0]
    close_all()
