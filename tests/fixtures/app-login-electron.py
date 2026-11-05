#!/usr/bin/python3
"""Electron uses its real accessibility bridge on a private bus/display."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import importlib.util

assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib
from app_detector import Detector

mode = sys.argv[-1]
seen, offered, password_events = [], [], []
def offer(identity, values):
    assert '|document:file://' in identity.scope
    assert values['username'] == 'fixture@example.invalid'
    offered.append(True)
def suggest(target):
    if seen: return
    assert '|document:file://' in target.identity.scope
    seen.append('pending')
    def choose():
        seen[-1] = target.apply(dict(username='fixture@example.invalid', password='synthetic-fill-only', service='server.example.invalid'))
        return False
    GLib.timeout_add(650, choose)
detector = Detector(Atspi, GLib, offer, lambda _: True, suggest=suggest if mode != 'save' else None)
original = detector._event
def observe(event):
    try:
        if event.source.get_role() == Atspi.Role.PASSWORD_TEXT:
            password_events.append(event.type)
        if os.environ.get('MONET_LOGIN_TRACE') == '1':
            print('EVENT',event.type,event.source.get_role_name(),event.source.get_process_id(),flush=True)
    except Exception:
        pass  # The object may have disappeared with its window.
    original(event)
detector._event = observe
detector.start()
args = [os.environ['MONET_ELECTRON_BINARY'], '--gtk-version=3', '--disable-gpu', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
        str(ROOT / 'tests/fixtures/electron-login/main.cjs'), '--fixture=' + mode]
# The disposable container cannot nest Chromium's renderer sandbox. Flatpak's
# outer sandbox and filtered buses remain active in the sandbox acceptance run.
args.insert(1, '--no-sandbox')
fixture = None
if os.environ.get('MONET_FLATPAK_FIXTURE') == '1':
    spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('flatpak-fixture.py'))
    sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
    fixture,args=sandbox.command(args[0],args[1:],(Path(args[0]).parent,ROOT/'tests/fixtures/electron-login'))
env = dict(os.environ)
if fixture is None:
    # Force the native ATK bridge as well as renderer accessibility. On a clean
    # CI session Chromium's startup probe can precede the accessibility daemon.
    # The Flatpak case deliberately obtains this through the app-support UI.
    env['ACCESSIBILITY_ENABLED'] = '1'
form = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
def finished():
    if form.poll() is not None: Atspi.event_quit(); return False
    return True
GLib.timeout_add(100, finished)
GLib.timeout_add_seconds(14, lambda: (Atspi.event_quit(), False)[1])
Atspi.event_main(); detector.clear()
if form.poll() is None: form.kill()
stderr = form.communicate(timeout=3)[1]
if fixture: fixture.cleanup()
if os.environ.get('MONET_LOGIN_TRACE') == '1': print(stderr.decode(errors='replace'))
assert form.returncode == 0, str(form.returncode) + ': ' + stderr[-2000:].decode(errors='replace')
assert password_events, 'Electron accessibility did not expose the password field'
if mode == 'save': assert offered == [True], 'Electron form was not offered'
else:
    assert not seen, 'Electron has no EditableText setter; no fill prompt should be offered'
    assert not offered, 'Filling must not create a save prompt'
print('PASS: electron ' + mode)
