"""Exercise Alt+Tab selection and search in a disposable KWin session."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from wayland_pointer import Pointer


def client(app_id, titles):
    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication([])
    app.setDesktopFileName(app_id)
    class Target(QLabel):
        def record(self, event, edge):
            with (Path.home() / "clicks").open("a") as log:
                log.write(self.windowTitle() + " " + edge + "\n")
            event.accept()

        def mousePressEvent(self, event):
            self.record(event, "down")

        def mouseReleaseEvent(self, event):
            self.record(event, "up")

    windows = [Target(name) for name in titles]
    for label in windows:
        label.setWindowTitle(label.text())
        colors = {'Alpha brief': '#78bcb3', 'Copper tape': '#c98f5f', 'Delta notes': '#a698d8'}
        label.setStyleSheet('background-color: ' + colors[label.text()] + '; color: black; padding: 14px')
        label.resize(250, 160)
        label.show()
    sys.exit(app.exec())


def worker(compact, captures):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtDBus import QDBusPendingCallWatcher
    from window_switcher import WindowSwitcher
    from tests.test_resume import r
    app = QApplication([])
    prefs = WindowSwitcher()
    prefs.refresh()
    assert os.environ['WAYLAND_DISPLAY'] == 'monet-window-switcher-test'
    pointer = Pointer(Path(os.environ['XDG_RUNTIME_DIR']) / os.environ['WAYLAND_DISPLAY'], version=4)
    clients = []
    def wait(test):
        end = time.monotonic() + 4
        while time.monotonic() < end:
            app.processEvents()
            if test(): return
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            time.sleep(.04)
        raise AssertionError('Timed out waiting for window state')
    def active():
        return r.kwin_script('reply(workspace.activeWindow?.caption || "")')
    def choose(box, value):
        index = box.findData(value)
        assert index >= 0, value
        box.setCurrentIndex(index)
        box.activated.emit(index)
        wait(lambda: not prefs.findChildren(QDBusPendingCallWatcher))
        assert not prefs.status.text(), prefs.status.text()
        # KWin coalesces reconfigure requests on a 200 ms timer.
        time.sleep(.3)
    def key(code):
        pointer.key(code, True)
        pointer.key(code, False)
        time.sleep(.025)
    def open_switcher():
        pointer.key(56, True)
        key(15)
        time.sleep(.3)
    def release(expected):
        pointer.key(56, False)
        time.sleep(.12)
        assert active() == expected, (expected, active())
    def focus(name):
        assert r.kwin_script('const w=windows().find(w=>w.caption==='+repr(name)+'); workspace.activeWindow=w; reply(workspace.activeWindow===w)')
        time.sleep(.07)
    try:
        for app_id, titles in [('org.monet.Editor', ['Alpha brief','Delta notes']), ('org.monet.Player', ['Copper tape'])]:
            clients.append(subprocess.Popen([sys.executable, __file__, '--client', app_id, *titles]))
        wait(lambda: r.kwin_script('reply(windows().filter(w=>["Alpha brief","Delta notes","Copper tape"].includes(w.caption)).length)') == 3)
        assert r.kwin_script("""for (const w of windows())
            w.frameGeometry={x:365,y:269,width:270,height:170};
            reply(true)""")
        pointer.point(500, 335)
        focus('Copper tape')
        focus('Alpha brief')
        open_switcher()
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
            target = captures / ("icons.png" if compact else "previews.png")
            subprocess.run(["spectacle", "--new-instance", "-b", "-n", "-f", "-o", str(target)],
                           check=True, timeout=12)
        # Send the first click at the old switcher's location in the same
        # input burst as the modifier release.
        pointer.key(56, False)
        pointer.click()
        log = Path.home() / "clicks"
        wait(lambda: log.is_file() and log.read_text().endswith(" up\n"))
        assert log.read_text().splitlines() == ["Copper tape down", "Copper tape up"], log.read_text()
        assert active() == 'Copper tape'
        expected_clicks = log.read_text().splitlines()
        for expected in ['Alpha brief', 'Copper tape'] * 4:
            open_switcher()
            pointer.key(56, False)
            pointer.click()
            expected_clicks += [expected + ' down', expected + ' up']
            wait(lambda: len(log.read_text().splitlines()) >= len(expected_clicks))
            assert log.read_text().splitlines() == expected_clicks
            assert active() == expected
        focus('Alpha brief')
        open_switcher()
        for code in (32, 18, 38): key(code)  # del
        release('Delta notes')
        focus('Delta notes')
        open_switcher()
        for code in (25, 38, 30, 21): key(code)  # play, only in the application ID
        release('Copper tape')
        open_switcher()
        for code in (44, 44, 44): key(code)  # no matches
        release('Copper tape')
        open_switcher()
        for code in (32, 44, 14): key(code)  # dz, backspace to d
        key(1)  # Escape cancels the selection
        release('Copper tape')
        open_switcher()
        for code in (32, 18, 38): key(code)  # del
        key(28)
        release('Delta notes')
        # A click in a single filtered result uses its source row.
        open_switcher()
        for code in (25, 38, 30, 21): key(code)
        geometry = r.kwin_script('const g=workspace.activeScreen.geometry; reply([g.x,g.y,g.width,g.height])')
        pointer.point(geometry[0] + geometry[2] // 2, geometry[1] + geometry[3] // 2 + 25)
        pointer.click()
        release('Copper tape')
        # Alt+Tab and Shift+Tab must visit just the two matching editors.
        focus('Copper tape')
        open_switcher()
        for code in (18, 32, 23, 20): key(code)  # edit
        key(15)
        release('Alpha brief')
        focus('Copper tape')
        open_switcher()
        for code in (18, 32, 23, 20): key(code)
        pointer.key(42, True)
        key(15)
        pointer.key(42, False)
        release('Delta notes')

        # Place the player on a separate monitor, then change scopes through
        # the actual preferences widget while keeping this compositor alive.
        assert r.kwin_script("""for (const w of windows().filter(w=>['Alpha brief','Delta notes','Copper tape'].includes(w.caption))) {
                const output=workspace.screens[w.caption==='Copper tape' ? 1 : 0];
                const g=output.geometry;
                w.frameGeometry={x:g.x+120,y:g.y+120,width:250,height:160};
            }
            reply(workspace.screens.length===2)""")
        focus('Alpha brief')
        pointer.point(300, 300)
        choose(prefs.screens, "1")
        assert active() == "Alpha brief", active()
        open_switcher()
        for code in (25, 38, 30, 21): key(code)
        release('Alpha brief')
        choose(prefs.screens, "2")
        open_switcher()
        release('Copper tape')
        choose(prefs.screens, "0")
        focus('Alpha brief')
        focus('Delta notes')
        focus('Copper tape')
        choose(prefs.apps, "1")
        open_switcher()
        for code in (48, 19, 23, 18, 33): key(code)  # brief
        release('Copper tape')
        choose(prefs.apps, "0")
        open_switcher()
        for code in (48, 19, 23, 18, 33): key(code)
        release('Alpha brief')
        assert prefs.style.currentData() == ('list' if compact else 'grid')
        open_switcher()
        for code in (18, 32, 23, 20): key(code)
        assert r.kwin_script("windows().find(w=>w.caption==='Alpha brief').closeWindow(); reply(true)")
        wait(lambda: r.kwin_script("reply(!windows().some(w=>w.caption==='Alpha brief'))"))
        release('Delta notes')
        if os.environ.get('MONET_TEST_SWITCHER_ENTRY'):
            subprocess.run(['/usr/libexec/monet-quick', 'utilities', 'window-switcher'],
                           check=True, timeout=8, capture_output=True)
            wait(lambda: r.kwin_script("reply(windows().some(w=>w.caption==='Window switcher'))"))
        print('Verified', 'compact list' if compact else 'default view',
              'nine immediate post-switch clicks, cycling in both directions, title and app search, no matches, Escape, Enter, grouping and monitor scopes.', flush=True)
        (Path.home() / 'passed').touch()
    finally:
        for proc in clients:
            proc.terminate()
            proc.wait(timeout=5)


def run(args):
    from PySide6.QtCore import QSettings
    with private_session() as env:
        home = Path(env['HOME'])
        binary = home / 'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'), binary)
        binary.chmod(0o700)
        env["PYTHONPATH"] = str(Path("/usr/share/monet/utilities") if args.installed else ROOT/"linux/share/monet/utilities")
        env.update(QT_QPA_PLATFORM='wayland', XDG_CURRENT_DESKTOP='KDE', XDG_SESSION_TYPE='wayland',
                   WAYLAND_DISPLAY='monet-window-switcher-test', LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='1')
        if not args.software_view:
            env.pop('QT_QUICK_BACKEND', None)
        config = Path(env['XDG_CONFIG_HOME'])
        (config/'kwinrc').write_text('[TabBox]\nLayoutName=monet-switcher\nDelayTime=50\nHighlightWindows=false\n')
        settings = QSettings(str(config/'monet/window-switcher.ini'), QSettings.IniFormat)
        settings.setValue('View/compact', args.compact)
        settings.sync()
        if args.installed and not args.compact and not args.software_view:
            env['MONET_TEST_SWITCHER_ENTRY'] = '1'
        if not args.installed:
            src = ROOT/'linux/share/kwin/tabbox'
            shutil.copytree(src, Path(env['XDG_DATA_HOME'])/'kwin/tabbox')
        session = home/'session.sh'
        cmd = [sys.executable, __file__, '--worker']
        if args.compact: cmd.append('--compact')
        if args.captures: cmd.extend(['--captures',str(args.captures.resolve())])
        session.write_text('#!/bin/sh\nexec ' + shlex.join(cmd) + '\n')
        session.chmod(0o700)
        proc = subprocess.Popen([binary, '--virtual','--width','1000','--height','640','--no-lockscreen',
                                 '--output-count','2','--no-kactivities','--socket',env['WAYLAND_DISPLAY'],'--exit-with-session',session],
                                env=env, start_new_session=True)
        try:
            proc.wait(timeout=55)
            assert (home/'passed').is_file(), 'Private window switcher test failed'
        finally:
            stop(proc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', nargs='+', help=argparse.SUPPRESS)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--compact', action='store_true')
    parser.add_argument('--software-view', action='store_true', help='Use Qt Quick’s software renderer')
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--captures', type=Path, help='Save private desktop screenshots for visual review')
    args = parser.parse_args()
    if args.client: client(args.client[0], args.client[1:])
    elif args.worker: worker(args.compact, args.captures)
    else: run(args)
