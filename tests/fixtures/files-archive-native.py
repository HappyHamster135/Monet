"""Exercise real Files archive activation on a private display and buses.

Usage: python3 tests/fixtures/files-archive-native.py DOLPHIN ARK OUTPUT
Only disposable ZIPs are opened; the extraction dialog is cancelled.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from tests.native_archive_session import desktop, install_archive_actions


def wait(check, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.03)
    raise AssertionError('Files archive activation timed out')


def main(dolphin, ark, output, package=None):
    assert dolphin.is_file() and ark.is_file()
    output.mkdir(parents=True, exist_ok=False)
    assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
    with private_session() as env, patch.dict(os.environ, env, clear=True), desktop():
        home = Path(os.environ['HOME']); config = Path(os.environ['XDG_CONFIG_HOME'])
        os.environ.update(LD_LIBRARY_PATH=str(dolphin.parent), TMPDIR=os.environ['XDG_RUNTIME_DIR'],
                          QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1', QT_ACCESSIBILITY='1', NO_AT_BRIDGE='0',
                          LANG='C.UTF-8', LC_ALL='C.UTF-8', LANGUAGE='en_US:en')
        assert home.is_relative_to('/tmp') and os.environ['DBUS_SYSTEM_BUS_ADDRESS'] == 'unix:path=/nonexistent'
        binaries = home/'bin'; binaries.mkdir(); (binaries/'ark').symlink_to(ark)
        os.environ['PATH'] = str(binaries)+os.pathsep+os.environ['PATH']
        data = Path(os.environ['XDG_DATA_HOME'])
        install_archive_actions(ROOT)
        (config/'mimeapps.list').write_text('[Default Applications]\napplication/zip=monet-archive.desktop;\napplication/x-rpm=monet-archive.desktop;\n')
        (config/'dolphinrc').write_text('[General]\nBrowseThroughArchives=false\n')
        (config/'kdeglobals').write_text('[KDE]\nSingleClick=false\n')
        subprocess.run(['kbuildsycoca6', '--noincremental'], check=True, capture_output=True)
        import dbus
        bus = dbus.SessionBus()
        with (output/'native.log').open('w') as log:
            bridge = subprocess.Popen(['/usr/libexec/at-spi-bus-launcher', '--launch-immediately'],
                                      stdout=log, stderr=log, start_new_session=True)
            try:
                wait(lambda: bus.name_has_owner('org.a11y.Bus'))
                os.environ['AT_SPI_BUS_ADDRESS'] = str(bus.get_object('org.a11y.Bus', '/org/a11y/bus').GetAddress(dbus_interface='org.a11y.Bus'))
                import pyatspi
                accessible = pyatspi.Registry.getDesktop(0)

                def find(name):
                    stack = [accessible]; seen = 0
                    while stack and seen < 1500:
                        node = stack.pop(); seen += 1
                        try:
                            if node.name == name and node.getState().contains(pyatspi.STATE_SHOWING):
                                bounds = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
                                if bounds.width > 0 and bounds.height > 0:
                                    return bounds
                            stack.extend(node[i] for i in reversed(range(min(node.childCount, 200))))
                        except Exception:
                            continue

                cases = []
                checks = [(8,'double-click'), (12000,'enter')]
                if package:
                    assert package.is_file()
                    checks.append((None,'double-click-rpm'))
                for count, activation in checks:
                    folder = home/f'Files-{count}'; folder.mkdir()
                    archive = folder/('Photos $(touch NO) %U å.zip' if count is not None else 'Application package.rpm')
                    if count is None:
                        archive.symlink_to(package)
                    else:
                        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
                            for i in range(count): target.writestr(f'photo-{i:05}.txt', 'fixture\n')
                    original = hashlib.sha256(archive.read_bytes()).hexdigest()
                    app = subprocess.Popen([str(dolphin), '--new-window', str(folder)], stdout=log, stderr=log, start_new_session=True)
                    try:
                        bounds = wait(lambda: find(archive.name))
                        windows = wait(lambda: subprocess.run(['xdotool','search','--onlyvisible','--pid',str(app.pid)], capture_output=True, text=True).stdout.splitlines())
                        subprocess.run(['xdotool','windowfocus','--sync',windows[0]], check=True)
                        started = time.monotonic()
                        if activation.startswith('double-click'):
                            subprocess.run(['xdotool','mousemove',str(bounds.x+bounds.width//2),str(bounds.y+bounds.height//2),
                                            'click','--repeat','2','--delay','80','1'], check=True)
                        else:
                            subprocess.run(['xdotool','key','--clearmodifiers','Home','Return'], check=True)
                        wait(lambda: find('Drop a destination folder here to extract'))
                        ready_ms = (time.monotonic()-started)*1000
                        window = wait(lambda: subprocess.run(['xdotool','search','--onlyvisible','--name','^Extract archive'], capture_output=True, text=True).stdout.splitlines())[0]
                        pid = int(subprocess.check_output(['xdotool','getwindowpid',window], text=True))
                        subprocess.run([sys.executable,'-c',
                            'from PySide6.QtGui import QGuiApplication;import sys;a=QGuiApplication([]);'
                            'assert a.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])',
                            window,str(output/f'{activation}.png')], check=True)
                        subprocess.run(['xdotool','windowfocus','--sync',window,'key','--clearmodifiers','Escape'], check=True)
                        def reaped():
                            try:
                                child,status = os.waitpid(pid,os.WNOHANG)
                            except ChildProcessError:
                                # Dolphin can remain the parent and reap the
                                # cancelled helper itself.
                                return not Path(f'/proc/{pid}').exists()
                            if child:
                                assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==1
                                return True
                        wait(reaped)
                        assert list(folder.iterdir()) == [archive]
                        assert hashlib.sha256(archive.read_bytes()).hexdigest() == original
                        assert not (home/'NO').exists()
                        cases.append(dict(entries=count, activation=activation, behavior='extraction-box', ready_ms=ready_ms,
                                          archive_unchanged=True, extracted=False, cancelled=True))
                    finally:
                        stop(app)
                result = dict(all_passed=True, cases=cases, scope='Actual paired Dolphin activation, private Xvfb and buses; no laptop windows or files touched.')
                (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps(result))
            finally:
                stop(bridge)


if __name__ == '__main__':
    main(*(Path(x).resolve() for x in sys.argv[1:]))
