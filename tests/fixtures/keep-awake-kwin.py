"""A selected app already open at sign-in, minimized, closed and reopened on Wayland."""
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
from tools.test import private_session, stop


def exercise():
    import dbus
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QWidget

    assert os.environ['WAYLAND_DISPLAY'] == 'awake-private' and Path.home().parent.name.startswith('monet-tests-')
    bus = dbus.SessionBus()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setDesktopFileName('org.monet.KeepAwakeTestWindow')
    desktop = 'org.monet.KeepAwakeTestWindow.desktop'
    settings = QSettings('Monet', 'Utilities')
    settings.setValue('awakeRules', json.dumps(dict(enabled=True, apps={desktop: []})))
    settings.sync()
    window = QWidget()
    window.show()
    children = []

    def wait(condition):
        end = time.monotonic() + 7
        while time.monotonic() < end:
            app.processEvents()
            if condition():
                return
            time.sleep(.025)
        raise AssertionError('Private desktop did not reach the expected awake state')

    try:
        children.append(subprocess.Popen([sys.executable, str(Path(__file__).with_name('keep-awake-native.py')), 'fake'],
                                         start_new_session=True))
        wait(lambda: bus.name_has_owner('org.monet.KeepAwakeTest'))
        children.append(subprocess.Popen([sys.executable, str(ROOT / 'linux/libexec/monet-keep-awake')],
                                         start_new_session=True))
        service = 'org.monet.KeepAwake'
        wait(lambda: bus.name_has_owner(service))
        control = dbus.Interface(bus.get_object(service, '/org/monet/KeepAwake'), service)

        def state():
            return json.loads(control.GetStatus())

        wait(lambda: state()['reasons'] == [desktop])
        assert state()['active'] and not state()['display']
        second = QWidget()
        second.show()
        window.close()
        second.showMinimized()
        app.processEvents()
        assert state()['active']
        second.close()
        wait(lambda: not state()['active'])
        window.show()
        wait(lambda: state()['active'])
        settings.remove('awakeRules')
        settings.sync()
        control.ReloadRules()
        wait(lambda: children[-1].poll() == 0)
        scripting = dbus.Interface(bus.get_object('org.kde.KWin', '/Scripting'), 'org.kde.kwin.Scripting')
        assert not scripting.isScriptLoaded('monet-keep-awake-windows')
        (Path.home() / 'passed').touch()
    finally:
        for process in reversed(children):
            stop(process)


if __name__ == '__main__':
    if sys.argv[1:] == ['worker']:
        exercise()
    else:
        with private_session() as env:
            home = Path(env['HOME'])
            env.update(WAYLAND_DISPLAY='awake-private', QT_QPA_PLATFORM='wayland', XDG_CURRENT_DESKTOP='KDE',
                       XDG_SESSION_TYPE='wayland', LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='1',
                       MONET_KEEP_AWAKE_PRIVATE_BUS='1', DBUS_SYSTEM_BUS_ADDRESS=env['DBUS_SESSION_BUS_ADDRESS'])
            kwin = home / 'kwin_wayland'
            shutil.copy2(shutil.which('kwin_wayland'), kwin)
            script = home / 'worker'
            script.write_text('#!/bin/sh\nexec ' + shlex.join([sys.executable, __file__, 'worker']) + '\n')
            script.chmod(0o700)
            process = subprocess.Popen([kwin, '--virtual', '--width', '800', '--height', '600', '--no-lockscreen',
                                        '--no-kactivities', '--socket', 'awake-private', '--exit-with-session', script],
                                       env=env, start_new_session=True)
            try:
                assert process.wait(timeout=40) == 0 and (home / 'passed').is_file()
            finally:
                stop(process)
