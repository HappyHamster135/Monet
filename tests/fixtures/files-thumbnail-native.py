"""Black-box native Files check, with disposable photos/cache/display/bus only."""
import hashlib
import copy
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from gi.repository import Gio, GLib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop

bundle = Path(sys.argv[1]).resolve()
artifacts = Path(sys.argv[2]).resolve(); artifacts.mkdir(exist_ok=False)
metadata = json.loads((bundle/'runtime.json').read_text())
for target in metadata['targets']:
    path = bundle/Path(target['path']).name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata['files'][path.name]

def wait(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result: return result
        time.sleep(.02)
    raise AssertionError('Native thumbnail fixture timed out')

with private_session() as env:
    env.update(QT_QPA_PLATFORM='xcb', LD_LIBRARY_PATH=str(bundle), QT_FORCE_STDERR_LOGGING='1',
               QT_STYLE_OVERRIDE='kvantum', QT_QPA_PLATFORMTHEME='kde', XDG_CURRENT_DESKTOP='KDE')
    env['TMPDIR'] = env['XDG_RUNTIME_DIR']
    config = Path(env['XDG_CONFIG_HOME']); home = Path(env['HOME']); cache = Path(env['XDG_CACHE_HOME'])
    (config/'Kvantum').mkdir()
    shutil.copytree(ROOT/'linux/share/Kvantum/Monet', config/'Kvantum/Monet')
    (config/'Kvantum/kvantum.kvconfig').write_text('[General]\ntheme=Monet\n')
    (config/'kdeglobals').write_text('[KDE]\nwidgetStyle=kvantum\n[General]\nfont=Inter,10,-1,5,400,0,0,0,0,0\n')
    (config/'dolphinrc').write_text('[General]\nShowStatusBar=FullWidth\n')
    local = home/'Local'; local.mkdir(); marker = local/'keep.txt'; marker.write_text('Keep this selection')
    for i in range(400): (local/f'entry-{i:04}.txt').write_text('Disposable listing entry\n')
    (local/'.directory').write_text('[Dolphin]\nViewMode=0\nPreviewsShown=false\n')
    photos = home/'Photos'; photos.mkdir(); seeds = home/'fixture-seeds'; seeds.mkdir()
    assert shutil.disk_usage(home).free > 512*1024**2
    for i in range(4):
        data = np.random.default_rng(i).integers(0, 256, (3200, 4800, 3), dtype=np.uint8)
        Image.fromarray(data).save(seeds/f'{i}.jpg', quality=65)
    del data
    for i in range(2000): os.link(seeds/f'{i%4}.jpg', photos/f'Photo-{i:05}.jpg')
    (photos/'.directory').write_text('[Dolphin]\nViewMode=0\nPreviewsShown=true\nZoomLevel=7\n')
    expected = {hashlib.md5(p.as_uri().encode()).hexdigest()+'.png' for p in photos.glob('*.jpg')}
    def thumbnails(): return {p for p in cache.rglob('*.png') if p.name in expected}
    with (artifacts/'dolphin.log').open('w') as log:
        xvfb = subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1280x900x24','-nolisten','tcp'],
            env=env,stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
        app = None; snapshot = None
        try:
            assert select.select([xvfb.stdout], [], [], 10)[0]
            env['DISPLAY'] = ':'+xvfb.stdout.readline().strip()
            app = subprocess.Popen([str(bundle/'dolphin'),'--new-window',str(local)],env=env,
                stdout=log,stderr=log,start_new_session=True)
            bus = Gio.DBusConnection.new_for_address_sync(env['DBUS_SESSION_BUS_ADDRESS'],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,None,None)
            def call(name,path,interface,method,value=None,timeout=1500):
                return bus.call_sync(name,path,interface,method,value,None,Gio.DBusCallFlags.NONE,timeout,None).unpack()
            name = wait(lambda: next((n for n in call('org.freedesktop.DBus','/org/freedesktop/DBus',
                'org.freedesktop.DBus','ListNames')[0] if n.startswith('org.kde.dolphin-')),None))
            def find(parent='/dolphin'):
                raw = call(name,parent,'org.freedesktop.DBus.Introspectable','Introspect')[0]
                if 'monetFilesState' in raw: return parent
                for node in ET.fromstring(raw).findall('node'):
                    found = find(parent+'/'+node.attrib['name'])
                    if found: return found
            path = wait(find)
            def state(): return json.loads(call(name,path,'org.kde.dolphin.MainWindow','monetFilesState')[0])
            def ready(folder):
                s = state()
                return s if s and s['tabs'][s['active']]['folders'] == [str(folder)] else None
            wait(lambda: ready(local))
            window = subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(app.pid)],env=env,text=True).splitlines()[0]
            def xdo(*args): subprocess.run(['xdotool',*args],env=env,check=True,stdout=subprocess.DEVNULL)
            def key(*args): xdo('windowfocus','--sync',window,'key','--clearmodifiers',*args)
            def navigate(folder):
                key('ctrl+l','ctrl+a');xdo('type','--clearmodifiers','--delay','1','--',folder.as_uri());key('Return')
            xdo('windowsize','--sync',window,'1100','760')
            xdo('mousemove','--window',window,'600','500','click','1');key('End')
            wait(lambda: state()['tabs'][0]['views'][0]['selected'] == [str(marker)])
            wait(lambda: state()['tabs'][0]['views'][0]['scroll'][1] > 0)
            wait(lambda: not call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            before = state()['tabs'][0]
            key('ctrl+t');wait(lambda: len(state()['tabs']) == 2)
            assert not thumbnails()
            navigate(photos);wait(lambda: ready(photos))
            wait(lambda: len(thumbnails()) > 0)
            first = thumbnails(); first_path = sorted(first)[0]
            with Image.open(first_path) as thumb:
                assert thumb.info.get('Thumb::URI','').startswith(photos.as_uri()+'/'),thumb.info
                assert thumb.width > 16 and thumb.height > 16
                thumb.save(artifacts/'actual-thumbnail.png')
            timings = []; growth = [len(first)]; stop_enabled = []
            for i in range(60):
                started=time.monotonic();current=state();timings.append((time.monotonic()-started)*1000)
                assert current['tabs'][current['active']]['folders'] == [str(photos)]
                if i in (10,30): key('Next')
                growth.append(len(thumbnails()))
                stop_enabled.append(call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
                time.sleep(.02)
            assert max(growth) > growth[0], 'No thumbnail work progressed during responsiveness sampling'
            assert max(growth) < 2000, 'No remaining photo workload when leaving the view'
            assert max(timings) < 250, timings
            assert any(stop_enabled), 'Thumbnail generation has no active Stop/loading control'
            subprocess.run([sys.executable,'-c',
                'from PySide6.QtGui import QGuiApplication;import sys;app=QGuiApplication([]);'
                'assert app.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])',
                window,str(artifacts/'thumbnails.png')],env=env,check=True)
            # Moving to uncached items starts another real preview batch. Stop
            # belongs to the current tab, even when another tab has work.
            key('ctrl+End')
            wait(lambda: call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            key('ctrl+shift+Tab');wait(lambda: state()['active'] == 0)
            assert not call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0]
            key('ctrl+Tab');wait(lambda: state()['active'] == 1)
            key('Prior')
            wait(lambda: call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            selection_before_cancel=state()['tabs'][1]['views'][0]['selected']
            assert call(name,path,'org.kde.KMainWindow','activateAction',GLib.Variant('(s)',('stop',)))[0]
            wait(lambda: not call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            assert ready(photos) and state()['tabs'][1]['views'][0]['selected'] == selection_before_cancel
            # Allow an already-written thumbnail to settle, then force more
            # uncached items into view. Cancel must keep those jobs paused.
            time.sleep(.4); paused_count=len(thumbnails())
            key('ctrl+Home');time.sleep(.5);key('ctrl+End');time.sleep(.5)
            assert len(thumbnails()) == paused_count, 'New preview work started after Stop'
            assert 'PreviewsShown=true' in (photos/'.directory').read_text()
            # Refresh resumes the operation, retaining every completed cache
            # entry and the user's preview preference.
            before_refresh=state()['tabs'][1]['views'][0]
            key('F5')
            wait(lambda: ready(photos))
            wait(lambda: call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            wait(lambda: len(thumbnails()) > paused_count)
            wait(lambda: state()['tabs'][1]['views'][0]['selected'] == before_refresh['selected'])
            wait(lambda: state()['tabs'][1]['views'][0]['current'] == before_refresh['current'])
            assert thumbnails().issuperset(first)
            key('Escape')
            wait(lambda: not call(name,path,'org.kde.KMainWindow','actionIsEnabled',GLib.Variant('(s)',('stop',)))[0])
            assert ready(photos), 'Cancelling previews invalidated the completed directory listing'
            started=time.monotonic();navigate(local);wait(lambda: ready(local),5)
            navigation_ms=(time.monotonic()-started)*1000
            wait(lambda: ready(local))
            key('ctrl+w');wait(lambda: len(state()['tabs']) == 1)
            (artifacts/'original-before.json').write_text(json.dumps(before,indent=2)+'\n')
            (artifacts/'original-after.json').write_text(json.dumps(state()['tabs'][0],indent=2)+'\n')
            def original_preserved():
                actual=state()['tabs'][0];expected=copy.deepcopy(before)
                if len(actual['views']) != len(expected['views']): return False
                for saved,live in zip(expected['views'],actual['views']):
                    # The status bar/viewport can finish laying out while the
                    # other tab is open. Preserve offsets, clamped only to the
                    # current legal range, as the recovery contract specifies.
                    saved['scroll']=[min(value,limit) for value,limit in zip(saved['scroll'],live['maximum'])]
                    saved['maximum']=live['maximum']
                    if saved['scroll'][1] <= 0: return False
                return actual == expected
            wait(original_preserved)
            time.sleep(1);assert ready(local) and original_preserved()
            assert marker.read_text() == 'Keep this selection'
            snapshot=state()
            key('ctrl+q');wait(lambda: app.poll() is not None,5)
            assert app.returncode == 0, 'Native Files did not close cleanly'
            result={'pair':metadata['files'],'photos':2000,'dimensions':[4800,3200],
                'distinct_seed_images':4,'unique_photo_paths':True,'file_payloads_shared_by_hardlink':True,
                'native_thumbnail_uri_verified':True,'thumbnail_counts_during_rpc':growth,
                'rpc_ms':timings,'maximum_rpc_ms':max(timings),'navigation_ms_including_native_typing':navigation_ms,
                'stop_action_enabled_during_thumbnail_sampling':stop_enabled,
                'prior_tab_selection_and_scroll_preserved':True,'stale_reply_did_not_replace_local_view':True,
                'stop_and_escape_cancel_previews':True,'refresh_resumes_previews':True,
                'preview_setting_unchanged':True,'active_tab_stop_state':True,'native_window_quit_cleanly':True,
                'original_tab_nonzero_scroll':before['views'][0]['scroll'],
                'refresh_preserves_current_and_selection':True,
                'scope':'Verified paired native Files, real JPEG thumbnails, private Xvfb/software desktop; no physical removable-drive or user-session claim'}
            (artifacts/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({k:result[k] for k in ['photos','maximum_rpc_ms','navigation_ms_including_native_typing',
                'prior_tab_selection_and_scroll_preserved','scope']}),flush=True)
        finally:
            if app is not None and app.poll() is None and 'state' in locals():
                try:
                    (artifacts/'final-state.json').write_text(json.dumps(state(),indent=2)+'\n')
                except Exception as error:
                    (artifacts/'final-state-error.txt').write_text(repr(error)+'\n')
            if snapshot is not None: (artifacts/'last-state.json').write_text(json.dumps(snapshot,indent=2)+'\n')
            if app is not None: stop(app)
            stop(xvfb);xvfb.stdout.close()
