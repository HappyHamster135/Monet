"""Close and reopen real Wayland windows in a disposable KWin session."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if len(sys.argv) > 1:
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QTimer
    app = QApplication([])
    app.setDesktopFileName(sys.argv[1])
    w = QWidget()
    w.setWindowTitle(sys.argv[2])
    w.setMinimumSize(230, 150)
    w.resize(470, 330)
    w.show()
    if sys.argv[2] == 'late geometry':
        QTimer.singleShot(140, lambda: w.resize(510, 350))
    sys.exit(app.exec())

from tools.test import private_session, stop
from tests.test_resume import r
from PySide6.QtCore import QCoreApplication

with private_session() as env:
    os.environ.update(env)
    app = QCoreApplication([])
    config = Path(env['XDG_CONFIG_HOME'])
    config.joinpath('kwinrc').write_text('[Plugins]\nmonet-workEnabled=true\n')
    shutil.copytree(ROOT/'linux/share/kwin/scripts/monet-work',
                    Path(env['XDG_DATA_HOME'])/'kwin/scripts/monet-work')
    kwin = Path(env['HOME'])/'kwin_wayland'
    shutil.copyfile(shutil.which('kwin_wayland'), kwin)
    kwin.chmod(0o700)
    env.update(KWIN_COMPOSE='O2', LIBGL_ALWAYS_SOFTWARE='1',
               QT_FORCE_STDERR_LOGGING='1')
    log = Path(env['HOME'])/'fixture.log'
    processes = []
    script = Path(__file__).resolve()

    def start(argv):
        with log.open('a') as stream:
            child = subprocess.Popen(argv, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(child)
        return child

    def until(check, description, timeout=8):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                if check():
                    return
            except RuntimeError as e:
                last = e
            time.sleep(.045)
        raise AssertionError((description, last))

    def server(outputs=1, width=1280, height=800):
        process = start([str(kwin), '--virtual', '--output-count', str(outputs),
                         '--width', str(width), '--height', str(height),
                         '--no-lockscreen', '--no-global-shortcuts', '--no-kactivities',
                         '--socket', 'monet-placement-fixture'])
        until(lambda: process.poll() is None and r.kwin_script('reply(workspace.screens.length)') == outputs,
              'Private compositor did not start')
        return process

    def state():
        return r.kwin_script('reply(windows().map(w => ({title:w.caption, rect:rect(w.frameGeometry), '
                             'screen:w.output.name, mode:Number(w.maximizeMode)})))')

    def window(title):
        return next((w for w in state() if w['title'] == title), {})

    def action(title, body):
        assert r.kwin_script('const w = windows().find(w => w.caption === '
                             + json.dumps(title) + ');\nif (w) {' + body + '}\nreply(!!w);')

    def open_client(title, app_id='org.example.Placement'):
        child = start([sys.executable, str(script), app_id, title])
        until(lambda: child.poll() is None and window(title), f'Map {title}')
        return child

    def close_client(child, title):
        action(title, 'w.closeWindow();')
        until(lambda: child.poll() is not None and not window(title), f'Close {title}')

    def expect(title, x, y, width, height):
        target = dict(x=x, y=y, width=width, height=height)
        try:
            until(lambda: window(title).get('rect') == target, (title, target), timeout=4)
        except AssertionError:
            print('Actual:', state(), flush=True)
            raise

    try:
        compositor = server()
        env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY='monet-placement-fixture')
        first = open_client('first')
        time.sleep(.4)
        action('first', 'w.frameGeometry = {x:207, y:121, width:676, height:467};')
        expect('first', 207, 121, 676, 467)
        close_client(first, 'first')
        other = open_client('other', 'org.example.Other')
        time.sleep(.35)
        assert window('other')['rect']['width'] != 676, state()
        close_client(other, 'other')
        fresh = open_client('late geometry')
        expect('late geometry', 207, 121, 676, 467)
        sibling = open_client('sibling')
        time.sleep(.5)
        assert window('sibling')['rect'] != window('late geometry')['rect'], state()
        expect('late geometry', 207, 121, 676, 467)
        close_client(sibling, 'sibling')
        action('late geometry', 'w.setMaximize(true, true);')
        until(lambda: window('late geometry').get('mode') == 3, 'maximize')
        close_client(fresh, 'late geometry')
        stop(compositor)
        compositor = server()
        reopened = open_client('reopened')
        until(lambda: window('reopened').get('mode') == 3, 'Restored maximized state')
        action('reopened', 'w.setMaximize(false, false);')
        expect('reopened', 207, 121, 676, 467)
        close_client(reopened, 'reopened')
        stop(compositor)
        compositor = server(outputs=2)
        second = open_client('on external display')
        expect('on external display', 207, 121, 676, 467)
        action('on external display', 'w.frameGeometry = {x:1500, y:270, width:1040, height:520};')
        expect('on external display', 1500, 270, 1040, 520)
        close_client(second, 'on external display')

        # Unplugged, the former rectangle doesn't fit the laptop screen.
        stop(compositor)
        compositor = server(width=960, height=600)
        laptop = open_client('laptop')
        expect('laptop', 0, 80, 960, 520)
        close_client(laptop, 'laptop')

        # Closing the clamped window must not forget the preferred display.
        stop(compositor)
        compositor = server(outputs=2)
        docked = open_client('docked')
        expect('docked', 1500, 270, 1040, 520)
        close_client(docked, 'docked')
        logs = log.read_text()
        assert not any(error in logs for error in ('TypeError:', 'ReferenceError:', 'Component failed to load:')), logs
        print('Native application placement verified')
    except Exception:
        print(log.read_text()[-12500:], file=sys.stderr)
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                stop(process)
