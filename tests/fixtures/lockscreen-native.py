"""Load the complete Monet screen in KDE's actual greeter, on a private bus."""
import json
import ctypes
import ctypes.util
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import select
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import stop


def send_input(env, name=None, point=None):
    x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
    xtst = ctypes.CDLL(ctypes.util.find_library('Xtst'))
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]; x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]; x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XFlush.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    display = x11.XOpenDisplay(env['DISPLAY'].encode()); assert display
    try:
        if point is not None:
            assert xtst.XTestFakeMotionEvent(display, -1, round(point[0]), round(point[1]), 0)
        else:
            code = x11.XKeysymToKeycode(display, x11.XStringToKeysym(name.encode())); assert code
            assert xtst.XTestFakeKeyEvent(display, code, 1, 0)
            assert xtst.XTestFakeKeyEvent(display, code, 0, 0)
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)


@contextmanager
def private_display(env, folder):
    read_fd, write_fd = os.pipe()
    with (folder / 'xvfb.log').open('w') as log:
        server = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0',
                                   '1920x1080x24', '-nolisten', 'tcp'], env=env,
                                  pass_fds=(write_fd,), stdout=log, stderr=log, start_new_session=True)
        os.close(write_fd)
        try:
            assert select.select([read_fd], [], [], 5)[0], 'Private X server did not start'
            number = os.read(read_fd, 32).decode().strip(); assert number.isdecimal(), number
            yield dict(env, DISPLAY=':' + number, QT_QPA_PLATFORM='xcb')
        finally:
            os.close(read_fd)
            stop(server)

assert os.environ['HOME'].startswith('/tmp/monet-tests-')
width, height = map(int, sys.argv[1:3])
consent = sys.argv[3] == 'consent'
prompt = sys.argv[3] != 'clock'
with tempfile.TemporaryDirectory(prefix='monet-lockscreen-') as temporary:
    folder = Path(temporary)
    shell_id = 'org.monet.lockscreen-test'
    shell = folder / 'data/plasma/shells' / shell_id
    shutil.copytree('/usr/share/plasma/shells/org.kde.plasma.desktop', shell)
    metadata = json.loads((shell / 'metadata.json').read_text())
    metadata['KPlugin']['Id'] = shell_id
    (shell / 'metadata.json').write_text(json.dumps(metadata))
    shutil.copytree(ROOT / 'linux/share/fonts/monet', folder / 'data/fonts/monet')
    ui = shell / 'contents/lockscreen'
    for name in ('LockScreen.qml', 'MonetLockScreen.qml'):
        shutil.copy2(ROOT / 'linux/share/monet/lockscreen' / name, ui / name)
    shutil.copy2(ROOT / 'linux/share/monet/widgets/ClockFormat.qml', ui / 'ClockFormat.qml')
    main = ui / 'MonetLockScreen.qml'
    source = main.read_text()
    instrumentation = '''
    property int fixtureStage: 0
    Timer {
        interval: 250; running: true; repeat: true
        onTriggered: {
            if (!monetLock.Window.window) return;
            if (fixtureStage === 0) {
                monetLock.Window.window.width = WIDTH;
                monetLock.Window.window.height = HEIGHT;
            }
            // Let native output/activation events settle before opening the prompt.
            if (fixtureStage === 3 && CONSENT) block.open = true;
            if (fixtureStage === 3 && PROMPT) console.log("MONET_LOCK_REQUEST_KEY");
            if (fixtureStage > 6) {
                console.log("MONET_LOCK_STATE", JSON.stringify({prompt:lockScreenRoot.uiVisible,
                    passwordFocus:passwordBox.activeFocus, passwordCursor:passwordBox.cursorVisible,
                    passwordLength:passwordBox.length}));
                return;
            }
            if (fixtureStage++ !== 5) return;
            const passwordPoint = passwordBox.mapToGlobal(passwordBox.width/2, passwordBox.height/2);
            const state = {width:monetLock.width, height:monetLock.height,
                prompt:lockScreenRoot.uiVisible, clockWidth:timeReadout.width,
                clockContentWidth:timeReadout.contentWidth, clockY:placard.y,
                readoutY:timeReadout.y, readoutHeight:timeReadout.height,
                readoutContentHeight:timeReadout.contentHeight,
                clockBottom:placard.y+placard.height,
                sheetY:rise.y, sheetHeight:sheet.height,
                passwordFocus:passwordBox.activeFocus, passwordCursor:passwordBox.cursorVisible,
                consentFocus:openButton.activeFocus,
                passwordX:passwordPoint.x, passwordY:passwordPoint.y, scale:monetLock.Screen.devicePixelRatio};
            monetLock.grabToImage(result => {
                state.saved = result.saveToFile(SNAPSHOT);
                console.log("MONET_LOCK_READY", JSON.stringify(state));
            });
        }
    }
'''.replace('WIDTH', str(width)).replace('HEIGHT', str(height)).replace('PROMPT', str(prompt).lower()).replace('CONSENT', str(consent).lower()).replace('SNAPSHOT', json.dumps(str(folder / 'screen.png')))
    main.write_text(source[:source.rfind('}')] + instrumentation + '}\n')
    env = dict(os.environ, XDG_DATA_HOME=str(folder / 'data'), QT_FORCE_STDERR_LOGGING='1',
               QT_LOGGING_RULES='kscreenlocker_greet.debug=true;qml.debug=true')
    subprocess.run(['fc-cache', '-f', str(folder / 'data/fonts')], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    assert 'Fraunces' in subprocess.check_output(['fc-match', '-f', '%{family}', 'Fraunces 72pt SuperSoft'], env=env, text=True)
    with private_display(env, folder) as env, (folder / 'greeter.log').open('w') as log:
        process = subprocess.Popen(['/usr/libexec/kscreenlocker_greet', '--testing', '--immediateLock', '--shell', shell_id],
                                   env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            state = None
            key_sent = False
            while time.monotonic() < deadline:
                text = (folder / 'greeter.log').read_text()
                if prompt and not key_sent and 'MONET_LOCK_REQUEST_KEY' in text:
                    send_input(env, 'Return'); key_sent = True
                lines = [line.split('MONET_LOCK_READY ', 1)[1] for line in text.splitlines() if 'MONET_LOCK_READY ' in line]
                if lines:
                    state = json.loads(lines[-1]); break
                assert process.poll() is None, text
                time.sleep(.05)
            assert state is not None, (folder / 'greeter.log').read_text()
            assert state['saved'] and state['width'] == width and state['height'] == height, state
            assert state['prompt'] == prompt, state
            if not prompt:
                assert state['clockY'] >= 0 and state['clockBottom'] <= height, state
                assert state['clockContentWidth'] <= state['clockWidth'] + 1, state
                assert not state['passwordFocus'] and not state['passwordCursor'], state
            else:
                assert state['sheetY'] >= 0 and state['sheetY'] + state['sheetHeight'] <= height, state
                assert key_sent, state
                if consent:
                    assert state['consentFocus'] and not state['passwordFocus'] and not state['passwordCursor'], state
                else:
                    assert state['passwordFocus'] and state['passwordCursor'], state
                    send_input(env, point=(state['passwordX']*state['scale'], state['passwordY']*state['scale']))
                    send_input(env, 'x')
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        text = (folder / 'greeter.log').read_text()
                        states = [json.loads(line.split('MONET_LOCK_STATE ', 1)[1]) for line in text.splitlines() if 'MONET_LOCK_STATE ' in line]
                        if states and states[-1]['prompt'] and states[-1]['passwordLength'] == 1: break
                        time.sleep(.04)
                    else: raise AssertionError(('Pointer movement interrupted password typing', text))
                send_input(env, 'Escape')
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    text = (folder / 'greeter.log').read_text()
                    states = [json.loads(line.split('MONET_LOCK_STATE ', 1)[1]) for line in text.splitlines() if 'MONET_LOCK_STATE ' in line]
                    if states and not any(states[-1].values()): break
                    time.sleep(.04)
                else: raise AssertionError(('Escape did not restore the idle clock', text))
            errors = ('is not a type', 'ReferenceError:', 'TypeError:', 'Unable to assign', 'Cannot assign to non-existent property')
            assert not any(error in text for error in errors), text
            if os.environ.get('MONET_LOCK_CAPTURE'):
                capture = Path(os.environ['MONET_LOCK_CAPTURE']); capture.mkdir(parents=True, exist_ok=True)
                stem = f'{width}x{height}-' + sys.argv[3]
                shutil.copy2(folder / 'screen.png', capture / (stem + '.png'))
                shutil.copy2(folder / 'greeter.log', capture / (stem + '.log'))
            print(json.dumps(state))
        finally:
            stop(process)
