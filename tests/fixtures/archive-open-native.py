"""Keep default ZIP extraction separate from right-click contents inspection.

Run in the matching native build/test runtime:
  python3 tests/fixtures/archive-open-native.py MENU_FIXTURE ARK_BINARY OUTPUT
Uses a private home, D-Bus, accessibility bus and Xvfb; never the host desktop.
"""
import hashlib
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from tests.native_archive_session import desktop, install_archive_actions


def inspect(menu_binary, ark_binary, output):
    output.mkdir(parents=True, exist_ok=False)
    # KIO's fallback launcher forks. Adopt its native app so this isolated
    # fixture can reap it and verify its exit code, even without systemd.
    assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
    with private_session() as env, patch.dict(os.environ, env, clear=True), desktop():
        home = Path(os.environ['HOME'])
        assert str(home).startswith('/tmp/monet-tests-')
        (home / 'Desktop').mkdir()
        os.environ.update(QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1', QT_ACCESSIBILITY='1', NO_AT_BRIDGE='0',
                          LANG='C.UTF-8', LC_ALL='C.UTF-8', LANGUAGE='en_US:en')
        binaries = home / 'bin'; binaries.mkdir()
        (binaries / 'ark').symlink_to(ark_binary)
        os.environ['PATH'] = str(binaries) + os.pathsep + os.environ['PATH']
        data = Path(os.environ['XDG_DATA_HOME'])
        install_archive_actions(ROOT)
        (Path(os.environ['XDG_CONFIG_HOME']) / 'mimeapps.list').write_text(
            '[Default Applications]\napplication/zip=monet-archive.desktop;\n')
        subprocess.run(['kbuildsycoca6', '--noincremental'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import dbus
        bus = dbus.SessionBus()
        with (output / 'accessibility.log').open('w') as log:
            bridge = subprocess.Popen(['/usr/libexec/at-spi-bus-launcher', '--launch-immediately'],
                                      stdout=log, stderr=log, start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not bus.name_has_owner('org.a11y.Bus'):
                    assert bridge.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(.02)
                os.environ['AT_SPI_BUS_ADDRESS'] = str(bus.get_object('org.a11y.Bus', '/org/a11y/bus').GetAddress(
                    dbus_interface='org.a11y.Bus'))
                import pyatspi
                accessible = pyatspi.Registry.getDesktop(0)

                def visible_names():
                    stack = [accessible]; names = []; seen = 0
                    while stack and seen < 500:
                        node = stack.pop(); seen += 1
                        try:
                            names.append(node.name or '')
                            stack.extend(node[i] for i in reversed(range(min(node.childCount, 150))))
                        except Exception:
                            continue  # A native accessible can disappear during a refresh.
                    return names

                results = []
                for count in (8, 12000):
                    # Shell metacharacters and field-code text must remain literal.
                    archive = home / f'Photos {count} $(touch NO) %U å.zip'
                    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
                        target.writestr('000README.txt', 'Inspect me without extracting.\n')
                        for index in range(count - 1): target.writestr(f'photo-{index:05}.txt', 'native archive fixture\n' * 4)
                    original = hashlib.sha256(archive.read_bytes()).hexdigest()
                    for mode in ('default', 'context'):
                        label = f'{count}-{mode}'
                        before = sorted(x.name for x in home.iterdir())
                        with (output / f'{label}.log').open('w') as log:
                            started = time.monotonic()
                            launcher = subprocess.Popen([str(menu_binary), mode, str(archive), str(output / f'{label}-menu.json')],
                                                        stdout=log, stderr=log, start_new_session=True)
                            window = None; pid = None; first_frame = None
                            try:
                                deadline = started + 12
                                while time.monotonic() < deadline:
                                    # KIO may finish its launcher successfully once
                                    # the independent native app has been started.
                                    assert launcher.poll() in (None, 0), (launcher.returncode, (output / f'{label}.log').read_text())
                                    search = ['--name', '^Extract archive'] if mode == 'default' else ['--class', '[Aa]rk']
                                    windows = subprocess.run(['xdotool', 'search', '--onlyvisible', *search], capture_output=True, text=True)
                                    for candidate in windows.stdout.splitlines():
                                        title = subprocess.run(['xdotool', 'getwindowname', candidate], capture_output=True, text=True)
                                        if (mode == 'default' and title.stdout.strip().startswith('Extract archive')) or (mode == 'context' and archive.name in title.stdout):
                                            window = candidate
                                            if first_frame is None: first_frame = time.monotonic() - started
                                            break
                                    names = visible_names()
                                    if mode == 'default':
                                        if window and 'Drop a destination folder here to extract' in names and str(archive) in names:
                                            assert '000README.txt' not in names, 'Default opening must show extraction, not the archive browser'
                                            break
                                    elif window and '000README.txt' in names: break
                                    time.sleep(.02)
                                else: raise AssertionError(('Expected archive action did not appear', mode, visible_names(), (output / f'{label}.log').read_text()))
                                ready = time.monotonic() - started
                                assert ready < 5, ('Archive action took too long', ready)
                                # Screenshot helper owns its own QGui app and private display.
                                subprocess.run([sys.executable, '-c',
                                    'from PySide6.QtGui import QGuiApplication; import sys; a=QGuiApplication([]); '
                                    'assert a.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])',
                                    window, str(output / f'{label}.png')], check=True)
                                pid = int(subprocess.check_output(['xdotool', 'getwindowpid', window], text=True))
                                subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True)
                                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'Escape' if mode == 'default' else 'ctrl+q'], check=True)
                                deadline = time.monotonic() + 5
                                status = None
                                while time.monotonic() < deadline:
                                    child, value = os.waitpid(pid, os.WNOHANG)
                                    if child:
                                        status = value; break
                                    time.sleep(.02)
                                expected_exit = 1 if mode == 'default' else 0  # Explicit extraction cancellation / normal browser quit.
                                assert status is not None and os.WIFEXITED(status) and os.WEXITSTATUS(status) == expected_exit, 'Archive window did not finish as expected'
                                assert sorted(x.name for x in home.iterdir()) == before, 'Inspection created extracted files'
                                assert hashlib.sha256(archive.read_bytes()).hexdigest() == original
                                menu = json.loads((output / f'{label}-menu.json').read_text())
                                assert menu['open'] and menu['extract'] and menu['preferred'] == 'monet-archive'
                                assert ' unpack %f' in menu['preferred_exec'], 'Double-click must keep the extraction route'
                                results.append(dict(entries=count, mode=mode, first_window_ms=first_frame*1000,
                                                    ready_ms=ready*1000, behavior='extraction-box' if mode == 'default' else 'inspect-contents',
                                                    inspected='000README.txt' if mode == 'context' else None, extracted=False,
                                                    archive_unchanged=True, shell_marker_created=False, native_exit=expected_exit, menu=menu))
                                (output / 'result.json').write_text(json.dumps({'cases': results, 'all_passed': len(results)==4,
                                    'scope': 'Matching native Ark, actual KIO default/service dispatch, private X11/software rendering; synthetic warm local ZIPs, not general laptop startup or slow-drive qualification'}, indent=2)+'\n')
                            finally:
                                stop(launcher)
            finally:
                stop(bridge)
    print(json.dumps({'all_passed': True, 'cases': len(results), 'maximum_ready_ms': max(x['ready_ms'] for x in results)}))


if __name__ == '__main__':
    inspect(*(Path(x).resolve() for x in sys.argv[1:]))
