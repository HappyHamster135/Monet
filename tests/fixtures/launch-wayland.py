#!/usr/bin/python3
"""Real KWin/Wayland launch checks on an isolated bus and virtual display.

Run in the desktop test container with only a render node exposed. No host
session, display socket, user configuration or KMS card is used.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def client(name, folder):
    token = os.environ.get('XDG_ACTIVATION_TOKEN', '')
    startup = os.environ.get('DESKTOP_STARTUP_ID', '')
    with (folder/'calls.jsonl').open('a') as output:
        output.write(json.dumps(dict(app=name, pid=os.getpid(), token=token, startup=startup, arguments=sys.argv[4:]))+'\n')
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    app = QGuiApplication([])
    app.setDesktopFileName('monet-wayland-'+name)
    engine = QQmlApplicationEngine()
    engine.loadData(b'import QtQuick\nWindow { width: 320; height: 200; color: "#dbe8dc"; title: "Monet launch fixture" }')
    window = engine.rootObjects()[0]
    QTimer.singleShot(700, window.show)
    QTimer.singleShot(45000, app.quit)
    return app.exec()


def session(folder):
    import dbus
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QJSValue
    from PySide6.QtTest import QTest
    app = QGuiApplication([])
    app.setDesktopFileName('monet-wayland-controller')
    engine = QQmlApplicationEngine()
    engine.loadData(b'''import QtQuick
import org.monet.launcher 1.0
import org.kde.taskmanager as TaskManager
Window {
    id: root; width: 520; height: 300; visible: true; color: "#e8e2d5"; title: "Monet launcher controller"
    property var states: launch.states
    property bool folderBusy: folderOpen.busy
    property string folderError: folderOpen.error
    Launcher { id: launch }
    FolderOpener { id: folderOpen }
    TaskManager.TasksModel { id: tasks; groupMode: TaskManager.TasksModel.GroupDisabled }
    function go(id, extra) { return launch.open(id, root.contentItem, extra); }
    function openDirectory(url) { return folderOpen.open(url, true, root.contentItem); }
    function snapshot() {
        let result = [];
        for (let row = 0; row < tasks.rowCount(); row++) {
            const index = tasks.index(row, 0);
            result.push({row: row,
                id: tasks.data(index, TaskManager.AbstractTasksModel.StorageId),
                window: tasks.data(index, TaskManager.AbstractTasksModel.IsWindow),
                startup: tasks.data(index, TaskManager.AbstractTasksModel.IsStartup),
                active: tasks.data(index, TaskManager.AbstractTasksModel.IsActive),
                mapped: tasks.data(index, TaskManager.AbstractTasksModel.IsMapped),
                minimized: tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized)});
        }
        return result;
    }
    function minimize(row) { tasks.requestToggleMinimized(tasks.index(row, 0)); }
    function activate(row) { tasks.requestActivate(tasks.index(row, 0)); }
}
''', QUrl.fromLocalFile(str(folder/'controller.qml')))
    assert engine.rootObjects(), 'Wayland controller QML did not load'
    window = engine.rootObjects()[0]
    def plain(value): return value.toVariant() if isinstance(value, QJSValue) else value
    def snapshot(): return plain(window.snapshot())
    def calls(name):
        path = folder/'calls.jsonl'
        return [v for line in path.read_text().splitlines() if (v := json.loads(line))['app']==name] if path.exists() else []
    def tasks(name): return [v for v in snapshot() if v['id']=='monet-wayland-'+name+'.desktop' and v['window']]
    def state(name): return plain(window.property('states')).get('monet-wayland-'+name+'.desktop',{}).get('state')
    def until(predicate, description, seconds=8):
        end = time.monotonic()+seconds
        while time.monotonic()<end:
            if predicate(): return
            QTest.qWait(20)
        raise AssertionError(description+': '+json.dumps(dict(tasks=snapshot(),states=plain(window.property('states')))))
    info = str(dbus.SessionBus().get_object('org.kde.KWin','/KWin').supportInformation(dbus_interface='org.kde.KWin'))
    (folder/'support.txt').write_text(info)
    assert 'Compositing is active' in info and 'Compositing Type: OpenGL' in info, info
    until(lambda: window.isExposed(), 'controller not exposed')
    until(lambda: any(v['id']=='monet-wayland-controller.desktop' for v in snapshot()), 'real task model cannot see controller')
    assert window.go('monet-wayland-slow.desktop', False)
    assert state('slow')=='starting'
    for _ in range(8): assert window.go('monet-wayland-slow.desktop', False)
    assert window.go('monet-wayland-other.desktop', False)
    until(lambda: len(calls('slow'))==1 and len(calls('other'))==1, 'two real native app launches')
    until(lambda: state('slow')=='running' and state('other')=='running', 'native mapped windows not confirmed')
    assert len(calls('slow'))==len(calls('other'))==1
    until(lambda: len(tasks('slow'))==1, 'slow task missing')
    window.minimize(tasks('slow')[0]['row'])
    until(lambda: tasks('slow')[0]['minimized'], 'native minimize did not finish')
    assert window.go('monet-wayland-slow.desktop', False)
    until(lambda: tasks('slow')[0]['active'] and not tasks('slow')[0]['minimized'], 'existing app was not raised/restored')
    assert len(calls('slow'))==1
    assert window.go('monet-wayland-slow.desktop', True)
    until(lambda: len(calls('slow'))==2 and len(tasks('slow'))==2, 'intentional second window not opened')
    until(lambda: state('slow')=='running', 'second window not confirmed')
    until(lambda: any(v['active'] for v in tasks('slow')), 'new app did not activate')
    window.activate(tasks('controller')[0]['row'])
    until(lambda: window.isActive(), 'source window not activated before opening the folder')
    destination=folder/'Directory result';destination.mkdir()
    assert window.openDirectory(QUrl.fromLocalFile(str(destination)))
    until(lambda: len(calls('folder'))==1 and len(tasks('folder'))==1, 'native folder action did not open its file manager')
    until(lambda: tasks('folder')[0]['active'], 'folder file-manager window did not activate')
    assert not window.property('folderBusy') and not window.property('folderError')
    arguments=calls('folder')[0]['arguments'];assert len(arguments)==1
    assert (QUrl(arguments[0]).toLocalFile() if arguments[0].startswith('file:') else arguments[0])==str(destination),arguments
    launches=calls('slow')+calls('other')+calls('folder')
    assert all(v['token'] for v in launches), 'native Wayland token not forwarded to an app'
    assert len({v['token'] for v in launches})==4, 'Wayland activation tokens must not be reused'
    QTest.qWait(250)
    result = dict(ok=True, platform=app.platformName(), calls=launches, tasks=snapshot(),
                  checks=['real KWin renderer','native task discovery','immediate pending state','eight duplicate clicks',
                          'two apps concurrently','mapped window confirmation','minimized window restored and activated',
                          'deliberate new window','distinct native Wayland activation tokens',
                          'folder action activates its actual file-manager window','folder action forwards the correct directory'])
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result), flush=True)
    # Exit-with-session terminates only this private compositor and its clients.
    return 0


def parent(output):
    sys.path.insert(0,str(ROOT))
    from tools.test import private_session
    output.mkdir(parents=True,exist_ok=True)
    with private_session() as env:
        folder = Path(env['HOME']).parent
        binary = folder/'bin/kwin_wayland'; binary.parent.mkdir()
        # The distribution binary has CAP_SYS_NICE. A same-name copy without
        # xattrs can run in rootless containers without privileged capabilities.
        shutil.copyfile(shutil.which('kwin_wayland'),binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland',XDG_SESSION_TYPE='wayland',XDG_CURRENT_DESKTOP='KDE',WAYLAND_DISPLAY='monet-launch-test')
        env.pop('QT_QUICK_BACKEND',None)
        env['KWIN_DRM_DEVICES']='/dev/dri/renderD128'
        applications=Path(env['XDG_DATA_HOME'])/'applications'; applications.mkdir()
        for name in ('slow','other','controller','folder'):
            command=f'{sys.executable} {Path(__file__).resolve()} client {name} {folder}'
            if name=='folder':command+=' %U'
            interfaces='org_kde_plasma_window_management;org_kde_plasma_activation_feedback;'
            (applications/f'monet-wayland-{name}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName=Monet Wayland {name}\nExec={command}\nStartupNotify=true\n'
                f'X-KDE-Wayland-Interfaces={interfaces}\n'+('MimeType=inode/directory;\n' if name=='folder' else ''))
        (Path(env['XDG_CONFIG_HOME'])/'mimeapps.list').write_text('[Default Applications]\ninode/directory=monet-wayland-folder.desktop;\n')
        subprocess.run(['kbuildsycoca6','--noincremental'],env=env,check=True,stdout=subprocess.DEVNULL)
        session_file=folder/'session.sh'
        session_file.write_text(f'#!/bin/sh\nexec {sys.executable} {Path(__file__).resolve()} session {folder}\n')
        session_file.chmod(0o700)
        try:
            with (output/'kwin.log').open('w') as log:
                process=subprocess.Popen([str(binary),'--virtual','--socket','monet-launch-test','--width','1280','--height','900',
                    '--no-lockscreen','--no-global-shortcuts','--no-kactivities','--exit-with-session',str(session_file)],
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try: code=process.wait(timeout=45)
                finally:
                    from tools.test import stop
                    stop(process)
            assert code==0, f'KWin/session exit {code}'
            assert (folder/'result.json').exists(), 'session did not complete its checks'
            result=json.loads((folder/'result.json').read_text()); assert result['ok']
            print(json.dumps(result),flush=True)
        finally:
            for name in ('support.txt','result.json','calls.jsonl'):
                if (folder/name).exists(): shutil.copyfile(folder/name,output/name)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='client': sys.exit(client(sys.argv[2],Path(sys.argv[3])))
    if len(sys.argv)>1 and sys.argv[1]=='session': sys.exit(session(Path(sys.argv[2])))
    parent(Path(sys.argv[1]))
