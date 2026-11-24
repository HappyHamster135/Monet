"""Exercise real dropdown-bar grabs using only a private compositor's fake input."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def client(platform, title, click_log):
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget
    app = QApplication([])
    app.setDesktopFileName("org.monet.TitleDragFixture")
    window = QWidget()
    window.setWindowTitle(title)
    window.resize(600, 420)
    button = QPushButton('Click inside the app', window)
    button.setGeometry(40, 100, 200, 44)
    def clicked():
        with Path(click_log).open('a') as log:
            log.write(json.dumps({'title':title})+'\n')
    button.clicked.connect(clicked)
    window.show()
    return app.exec()


def worker(output):
    from PySide6.QtCore import QCoreApplication
    from tests.test_resume import r
    from tools.test import stop
    app = QCoreApplication([])
    env = dict(os.environ)
    processes = []
    records = []
    closes = []
    body_clicks = []
    click_log = output/'clicks.jsonl'

    def click_count(title):
        return sum(json.loads(line)['title']==title for line in click_log.read_text().splitlines()) if click_log.exists() else 0

    def until(check, label, timeout=6):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if check(): return
            time.sleep(.015)
        raise AssertionError((label, scene()))

    def scene():
        return r.kwin_script('reply({p:{x:workspace.cursorPos.x,y:workspace.cursorPos.y}, '
            'stack:workspace.stackingOrder.filter(w=>!w.deleted).map(w => ({title:w.caption, active:w.active, '
            'rect:rect(w.frameGeometry), client:rect(w.clientGeometry), move:w.move, '
            'mode:Number(w.maximizeMode), minimized:w.minimized}))})')

    def window(title):
        return next((w for w in scene()['stack'] if w['title'] == title), {})

    def action(title, body):
        assert r.kwin_script('const w = windows().find(w => w.caption === '
                             + json.dumps(title) + '); if(w){' + body + '} reply(!!w);')

    def open_client(title, platform):
        with (output/'clients.log').open('a') as log:
            process = subprocess.Popen([sys.executable, __file__, 'client', platform, title, str(click_log)],
                env=dict(env, QT_QPA_PLATFORM=platform), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        until(lambda: process.poll() is None and window(title), 'Map ' + title)

    from wayland_pointer import Pointer
    pointer = Pointer(Path(env['XDG_RUNTIME_DIR'])/'monet-placement-fixture')
    try:
        for platform in ('wayland', 'xcb'):
            title = 'Title drag ' + platform
            other = 'Other ' + platform
            open_client(title, platform)
            open_client(other, platform)
            action(other, 'w.frameGeometry={x:980,y:620,width:280,height:150};')
            action(other, 'w.frameGeometry={x:950,y:550,width:260,height:210};')
            time.sleep(.35)  # The other window's introduction must finish mapping first.

            def reveal():
                bounds = window(title)['client']
                pointer.point(bounds['x']+150, bounds['y']+1)
                until(lambda: window('Monet title bar').get('rect') == dict(x=round(bounds['x']), y=round(bounds['y']),
                       width=round(bounds['width']), height=40), 'Reveal target bar')
                return bounds['x']+200, bounds['y']+15

            for iteration in range(6):
                print('DRAG',platform,iteration,flush=True)
                inactive = bool(iteration % 2)
                action(title, 'w.setMaximize(false,false); w.frameGeometry={x:180,y:150,width:680,height:480};')
                until(lambda: window(title)['rect'] == dict(x=180,y=150,width=680,height=480), 'Reset frame')
                action(other if inactive else title, 'workspace.activeWindow=w;')
                pointer.point(40,740)
                time.sleep(.05)
                x,y = reveal()
                before = window(title)['rect']
                pointer.point(x,y); time.sleep(.02)
                pointer.button(True); time.sleep(.01)
                pointer.point(x+24,y+3)
                until(lambda: window(title).get('move'), 'Start held drag', timeout=1)
                assert scene()['p'] == dict(x=x+24,y=y+3), 'Native move warped the pointer'
                pointer.point(x+110,y+60)
                until(lambda: window(title)['rect']['x'] == before['x']+110
                      and window(title)['rect']['y'] == before['y']+60, 'Follow pointer')
                pointer.button(False)
                until(lambda: not window(title).get('move'), 'Release native drag')
                after = window(title)['rect']
                pointer.point(x+150,y+100); time.sleep(.04)
                assert window(title)['rect'] == after, 'Window remained stuck to the pointer'
                # The first content click must reach an ordinary app after a
                # compositor move, including when it also activates the app.
                action(other if inactive else title, 'workspace.activeWindow=w;')
                client_bounds = window(title)['client']
                before_click = click_count(title)
                pointer.point(client_bounds['x']+140, client_bounds['y']+122)
                pointer.button(True); time.sleep(.005); pointer.button(False)
                until(lambda: click_count(title)==before_click+1, 'First app-content click was lost after moving')
                assert window(title)['active'], 'Content click failed to activate the target app'
                body_clicks.append(dict(platform=platform,inactive=inactive))
                records.append(dict(platform=platform, inactive=inactive, before=before, after=after))

            # A complete quick gesture must neither get lost nor leave a late move pending.
            x,y = reveal()
            quick_before = window(title)['rect']
            pointer.point(x,y); time.sleep(.02)
            pointer.button(True); pointer.point(x+25,y+3); pointer.point(x+75,y+40); pointer.button(False)
            time.sleep(.15)
            assert not window(title)['move'], 'Quick release left a pending move'
            after = window(title)['rect']
            assert after != quick_before, 'Quick drag was lost'
            pointer.point(x+120,y+90); time.sleep(.04)
            assert window(title)['rect'] == after

            # Native dragging must still restore a maximized window and keep snapping.
            action(title, 'workspace.activeWindow=w; w.setMaximize(true,true);')
            until(lambda: window(title)['mode'] == 3, 'Maximize')
            x,y = reveal(); pointer.point(x,y); time.sleep(.025)
            pointer.button(True); pointer.point(x+25,y+80); time.sleep(.04)
            pointer.point(x+80,y+160)
            until(lambda: window(title)['move'] and window(title)['mode'] == 0, 'Drag maximized window down')
            pointer.button(False)
            until(lambda: not window(title)['move'], 'Release restored window')
            x,y = reveal(); pointer.point(x,y); time.sleep(.025)
            pointer.button(True); pointer.point(x+24,y+3); time.sleep(.04)
            pointer.point(640,0); time.sleep(.25); pointer.button(False)
            until(lambda: window(title)['mode'] == 3 and not window(title)['move'], 'Snap to top')
            # Close must work immediately after dragging/maximizing, and on
            # inactive windows too. Exercise the first/last pixels, not only centres.
            for closing in range(6):
                if closing:
                    open_client(title, platform)
                    action(title, 'w.frameGeometry={x:180,y:150,width:680,height:480};')
                    time.sleep(.25)
                inactive = bool(closing % 2)
                action(other if inactive else title, 'workspace.activeWindow=w;')
                reveal()
                bounds = window('Monet title bar')['rect']
                dx,dy = ((-1,1),(-22,20),(-43,39))[closing % 3]
                pointer.point(bounds['x']+bounds['width']+dx,bounds['y']+dy)
                pointer.click()
                until(lambda: not window(title), 'First Close click did not register')
                closes.append(dict(platform=platform,inactive=inactive,offset=[dx,dy]))
                assert window(other), 'Close affected the wrong window'
            action(other, 'w.closeWindow();')
            until(lambda: not window(other), 'Close other client')
        result = dict(ok=True, drags=records, closes=closes, body_clicks=body_clicks, quick_release=True, restored_and_snapped=True,
                      scope='Private virtual KWin, CPU rendering, Wayland and XWayland clients; no host session or input')
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        return 0
    finally:
        pointer.button(False)
        for process in processes:
            if process.poll() is None: stop(process)


def parent(output):
    from tools.test import private_session, stop
    output.mkdir(parents=True,exist_ok=True)
    with private_session() as env:
        data = Path(env['XDG_DATA_HOME'])
        config = Path(env['XDG_CONFIG_HOME'])
        config.joinpath('kwinrc').write_text('[Plugins]\nmonet-titlesEnabled=true\n'
            '[org.kde.kdecoration2]\nlibrary=org.kde.kwin.aurorae\ntheme=__aurorae__svg__MonetBare\n')
        shutil.copytree(ROOT/'linux/share/aurorae/themes/MonetBare',data/'aurorae/themes/MonetBare')
        path = data/'kwin/scripts/monet-titles'
        shutil.copytree(ROOT/'linux/share/kwin/scripts/monet-titles',path)
        qml = path/'contents/ui/TitleBar.qml'
        source = qml.read_text().replace('@DATADIR@',str(ROOT/'linux/share'))
        qml.write_text(source)
        # Optional override is only for checking a just-built candidate plugin locally.
        if os.environ.get('MONET_TITLE_TEST_PLUGIN'):
            plugins = Path(env['HOME'])/'plugins/kwin/plugins'
            plugins.mkdir(parents=True)
            shutil.copyfile(os.environ['MONET_TITLE_TEST_PLUGIN'],plugins/'monet_window_identity.so')
            env['QT_PLUGIN_PATH'] = str(plugins.parents[1])
        binary = Path(env['HOME'])/'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'),binary); binary.chmod(0o700)
        env.update(KWIN_COMPOSE='O2',LIBGL_ALWAYS_SOFTWARE='1',QT_FORCE_STDERR_LOGGING='1',
                   WAYLAND_DISPLAY='monet-placement-fixture')
        script = Path(env['HOME'])/'session.sh'
        script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,__file__,'worker',str(output)])+'\n')
        script.chmod(0o700)
        with (output/'kwin.log').open('w') as log:
            server = subprocess.Popen([str(binary),'--virtual','--output-count','1','--width','1280','--height','800',
                '--xwayland','--no-lockscreen','--no-global-shortcuts','--no-kactivities',
                '--socket','monet-placement-fixture','--exit-with-session',str(script)],
                env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try: code = server.wait(timeout=100)
            finally: stop(server)
        assert code == 0, 'Private title-drag session failed: '+str(code)
        assert json.loads((output/'result.json').read_text())['ok']


if __name__ == '__main__':
    if sys.argv[1] == 'client': sys.exit(client(sys.argv[2],sys.argv[3],sys.argv[4]))
    if sys.argv[1] == 'worker': sys.exit(worker(Path(sys.argv[2])))
    parent(Path(sys.argv[1]))
