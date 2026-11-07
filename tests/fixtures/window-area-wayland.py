"""Private KWin virtual outputs: real Wayland moves, scale changes and output loss.

Expose only a render node to the disposable container, never the host session,
physical output-control devices or account. Hardware hotplug remains separate.
"""
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


def session(folder, output):
    import dbus
    from PySide6.QtCore import QMetaObject, QRect, QUrl
    from PySide6.QtGui import QGuiApplication, QWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from tests import native_window_area as cases

    def doctor(*arguments):
        result = subprocess.run(['kscreen-doctor', *arguments], capture_output=True, text=True, timeout=15)
        with (output/'doctor.log').open('a') as log: log.write(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    config = json.loads(doctor('-j'))
    (output/'initial-outputs.json').write_text(json.dumps(config, indent=2)+'\n')
    names = [item['name'] for item in config['outputs'] if item['connected']]
    assert len(names) == 2, names
    large, small = names
    doctor(f'output.{large}.scale.1.25', f'output.{large}.position.0,0',
           f'output.{small}.scale.2', f'output.{small}.position.1536,0')
    os.environ['QT_QUICK_BACKEND'] = 'software'
    applications = Path(os.environ['XDG_DATA_HOME'])/'applications'
    applications.mkdir(parents=True, exist_ok=True)
    for name in ('settings', 'store'):
        (applications/('monet-area-'+name+'.desktop')).write_text(
            '[Desktop Entry]\nType=Application\nName=Monet area '+name+'\nExec=/usr/bin/false\n')
    bus = dbus.SessionBus()
    scripting = dbus.Interface(bus.get_object('org.kde.KWin', '/Scripting'), 'org.kde.kwin.Scripting')
    info = str(bus.get_object('org.kde.KWin', '/KWin').supportInformation(dbus_interface='org.kde.KWin'))
    (output/'support.txt').write_text(info)
    assert 'Compositing is active' in info and 'Compositing Type: OpenGL' in info, info
    records = []; serial = 0
    observer = None

    def until(predicate, description):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate(): return
            QTest.qWait(20)
        raise AssertionError(description() if callable(description) else description)

    def move(app_id, name):
        nonlocal serial
        serial += 1; plugin = 'monet-area-move-' + str(serial)
        path = folder/(plugin+'.js')
        path.write_text('const w = workspace.stackingOrder.find(w => String(w.resourceClass) === '+json.dumps(app_id)+');\n'
                        'const o = workspace.screens.find(o => o.name === '+json.dumps(name)+');\n'
                        'if (!w || !o) throw new Error("Window or output missing");\n'
                        'workspace.sendClientToScreen(w, o);\n'
                        'console.log("AREA_MOVE", w.resourceClass, o.name, w.output.name, JSON.stringify(w.frameGeometry));\n')
        ident = int(scripting.loadScript(str(path)))
        assert ident >= 0, 'Script failed to load'
        dbus.Interface(bus.get_object('org.kde.KWin', '/Scripting/Script'+str(ident)), 'org.kde.kwin.Script').run()
        scripting.unloadScript(str(path))

    for name, cls in [('settings', cases.SettingsScreens), ('store', cases.StoreScreens)]:
        doctor(f'output.{large}.scale.1.25', f'output.{large}.position.0,0',
               f'output.{small}.scale.2', f'output.{small}.position.1536,0')
        case = cls('test_restored_geometry_and_screen_switch'); cls.setUpClass()
        app_id = 'monet-area-' + name
        QGuiApplication.instance().setDesktopFileName(app_id)
        os.environ['MONET_NAV_CAPTURE'] = str(output/name)
        try:
            case.setUp()
            window = case.window
            if observer is None:
                observer = QQmlApplicationEngine()
                observer.loadData(b'''import QtQuick
import org.kde.taskmanager as TaskManager
Window {
    visible: false
    property TaskManager.TasksModel tasks: TaskManager.TasksModel { groupMode: TaskManager.TasksModel.GroupDisabled }
    function snapshot() {
        let result = [];
        for (let row = 0; row < tasks.rowCount(); row++) {
            const index = tasks.index(row, 0);
            const frame = tasks.data(index, TaskManager.AbstractTasksModel.Geometry);
            if (tasks.data(index, TaskManager.AbstractTasksModel.IsWindow)) result.push({
                row: row, id: tasks.data(index, TaskManager.AbstractTasksModel.StorageId),
                frame: [frame.x, frame.y, frame.width, frame.height],
                minimized: tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized),
                maximized: tasks.data(index, TaskManager.AbstractTasksModel.IsMaximized),
                fullscreen: tasks.data(index, TaskManager.AbstractTasksModel.IsFullScreen)});
        }
        return result;
    }
    function activate(row) { tasks.requestActivate(tasks.index(row, 0)); }
}''', QUrl.fromLocalFile(str(folder/'observer.qml')))
                assert observer.rootObjects(), 'Native window-state observer did not load'
            tasks = observer.rootObjects()[0]
            def task():
                matches = [item for item in tasks.snapshot().toVariant() if item['id'] == app_id+'.desktop']
                return matches[0] if len(matches) == 1 else {}
            until(window.isExposed, 'Window did not map')
            until(lambda: bool(task()), lambda: 'Native task model did not see '+app_id+': '+str(tasks.snapshot().toVariant()))
            assert len(QGuiApplication.screens()) == 2
            assert max(s.availableVirtualGeometry().width() for s in QGuiApplication.screens()) > max(s.geometry().width() for s in QGuiApplication.screens())

            def check(label, target=None):
                def fitted():
                    state = task()
                    rect = window.screen().availableGeometry() if window.screen() else QRect()
                    return (window.screen() is not None and (target is None or window.screen().name() == target)
                            and case.area.geometry == rect and window.visibility() == QWindow.Windowed
                            and state and not any(state.get(key) for key in ('minimized', 'maximized', 'fullscreen'))
                            and rect.adjusted(-1, -1, 1, 1).contains(QRect(*state['frame']))
                            and abs(state['frame'][2] - window.width()) <= 1
                            and abs(state['frame'][3] - window.height()) <= 1
                            and window.width() <= case.area.width - 32 and window.height() <= case.area.height - 48)
                try:
                    until(fitted, name + ': ' + label)
                except AssertionError:
                    problem = dict(app=name, label=label, target=target,
                        screen=window.screen().name() if window.screen() else None,
                        area=[case.area.width, case.area.height], size=[window.width(), window.height()],
                        minimum=[window.minimumWidth(), window.minimumHeight()], visibility=str(window.visibility()), task=task())
                    raise AssertionError(problem)
                rect = case.area.geometry
                record = dict(app=name, label=label, screen=window.screen().name(),
                              available=[rect.x(), rect.y(), rect.width(), rect.height()],
                              virtual_width=window.screen().availableVirtualGeometry().width(),
                              size=[window.width(), window.height()], dpr=window.devicePixelRatio(), task=task())
                records.append(record); print(json.dumps(record), flush=True)

            move(app_id, large); check('large output', large)
            search_name = 'settingsSearch' if name == 'settings' else 'storeSearch'
            search = case.item(search_name)
            page = window.property('page') or window.property('section')
            move(app_id, small); check('small output', small)
            assert case.item(search_name) is search
            assert (window.property('page') or window.property('section')) == page
            case.capture('wayland-small')

            # xdg-shell has no minimized state in its configure event. Qt can
            # report Windowed while KWin still has the window minimized; use
            # the compositor's native task model as the authority here.
            window.showMinimized(); until(lambda: task().get('minimized') and not window.isExposed(), 'Did not minimize')
            move(app_id, large); QTest.qWait(100)
            assert task().get('minimized') and not window.isExposed(), task()
            tasks.activate(task()['row'])
            until(lambda: not task().get('minimized') and window.isExposed(), 'Did not restore')
            check('minimized move and restore', large)

            window.showMaximized(); until(lambda: window.visibility() == QWindow.Maximized, 'Did not maximize')
            move(app_id, small)
            until(lambda: window.screen().name() == small, 'Maximized move did not reach output')
            QMetaObject.invokeMethod(window, 'fitAvailableScreen')
            assert window.visibility() == QWindow.Maximized and task().get('maximized'), task()
            window.showNormal(); check('normal after maximized move')

            window.showFullScreen()
            until(lambda: task().get('fullscreen') and window.visibility() == QWindow.FullScreen, 'Did not enter fullscreen')
            move(app_id, large)
            until(lambda: window.screen().name() == large, 'Fullscreen move did not reach output')
            QMetaObject.invokeMethod(window, 'fitAvailableScreen')
            assert window.visibility() == QWindow.FullScreen and task().get('fullscreen'), task()
            window.showNormal(); check('normal after fullscreen move')
            move(app_id, small); check('small output after fullscreen', small)

            before_scale = window.screen().availableGeometry()
            doctor(f'output.{window.screen().name()}.scale.1.75')
            until(lambda: window.screen().availableGeometry() != before_scale, 'Scale did not change the logical screen area')
            check('live fractional-scale change')
            removed = window.screen().name()
            doctor(f'output.{removed}.disable')
            until(lambda: len(QGuiApplication.screens()) == 1, 'Output did not disappear')
            check('output disabled')
            doctor(f'output.{removed}.enable')
            until(lambda: len(QGuiApplication.screens()) == 2, 'Output did not return')
            check('output enabled')
            assert case.item(search_name) is search
            assert (window.property('page') or window.property('section')) == page
        finally:
            if hasattr(case, 'window'): case.tearDown()
            case.doCleanups(); cls.tearDownClass()

    result = dict(ok=True, records=records, checks=['two actual Wayland outputs', 'virtual desktop wider than one output',
        'native compositor window moves', 'mixed output scales', 'same app state and QObject tree',
        'minimized move and restore', 'maximized move remains maximized', 'live fractional scale',
        'fullscreen move remains fullscreen', 'output disable/re-enable', 'working OpenGL compositor'])
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0


def parent(output):
    from tools.test import private_session, stop
    output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        folder = Path(env['HOME']).parent
        binary = folder/'bin/kwin_wayland'; binary.parent.mkdir()
        shutil.copyfile(shutil.which('kwin_wayland'), binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland', XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE',
                   WAYLAND_DISPLAY='monet-area-test', KWIN_DRM_DEVICES='/dev/dri/renderD128', PYTHONFAULTHANDLER='1')
        for key in ('QT_QUICK_BACKEND', 'QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS'):
            env.pop(key, None)
        script = folder/'session.sh'
        script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable, str(Path(__file__).resolve()),
                                                       'session', str(folder), str(output)])+'\n')
        script.chmod(0o700)
        with (output/'kwin.log').open('w') as log:
            process = subprocess.Popen([str(binary), '--virtual', '--output-count', '2', '--socket', 'monet-area-test',
                '--width', '1920', '--height', '1080', '--no-lockscreen', '--no-global-shortcuts', '--no-kactivities',
                '--exit-with-session', str(script)], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try: code = process.wait(timeout=90)
            finally: stop(process)
        assert code == 0, 'KWin/session exit '+str(code)
        result = json.loads((output/'result.json').read_text()); assert result['ok']
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'session': sys.exit(session(Path(sys.argv[2]), Path(sys.argv[3])))
    parent(Path(sys.argv[1]).resolve())
