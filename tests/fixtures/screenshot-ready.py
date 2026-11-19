"""Cold/warm region-overlay first buffers on a private virtual KWin display."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
import dbus


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        binary = Path(env['HOME'])/'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'), binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY='monet-screenshot-test',
                   XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE', PLASMA_SESSION_GUI_TEST='1')
        env.pop('QT_QUICK_BACKEND', None)
        children = []
        def start(args, name, child_env=env):
            with (output/name).open('w') as stream:
                child = subprocess.Popen(args, env=child_env, stdout=stream, stderr=stream, start_new_session=True)
            children.append(child); return child
        def until(check, message):
            deadline = time.monotonic()+15
            while time.monotonic()<deadline:
                if check(): return
                time.sleep(.01)
            raise AssertionError(message)
        bus = dbus.bus.BusConnection(env['DBUS_SESSION_BUS_ADDRESS'])
        try:
            kwin = start([str(binary),'--virtual','--width','1280','--height','800','--socket',env['WAYLAND_DISPLAY'],
                          '--no-lockscreen','--no-global-shortcuts','--no-kactivities'], 'kwin.log')
            until(lambda: bus.name_has_owner('org.kde.KWin'), 'Private compositor did not start')
            timings = {}
            for warm in (False, True):
                name = 'warm' if warm else 'cold'; log = output/(name+'.log')
                child_env = dict(env, WAYLAND_DEBUG='client')
                began = time.monotonic()
                process = start(['spectacle', '--dbus' if warm else '--region'], log.name, child_env)
                if warm:
                    until(lambda: bus.name_has_owner('org.kde.Spectacle'), 'Capture service did not register')
                    time.sleep(.6)
                    assert process.poll() is None and '.attach(' not in log.read_text(), 'Warming unexpectedly captured or displayed a window'
                    timings['warmIdleNoCapture'] = True
                    began = time.monotonic()
                    bus.get_object('org.kde.Spectacle','/').RectangularRegion(dbus.Int32(0), dbus_interface='org.kde.Spectacle')
                until(lambda: '.attach(' in log.read_text(), 'Region overlay did not submit a buffer: '+log.read_text()[-2000:])
                timings[name+'FirstBufferSeconds'] = round(time.monotonic()-began, 3)
                assert process.poll() is None, log.read_text()
                stop(process); children.remove(process)
                until(lambda: not bus.name_has_owner('org.kde.Spectacle'), 'Capture service did not stop')
            timings.update(passed=True, scope='Private software-rendered KWin, no host screen or input; time to first region-overlay buffer, not physical-machine latency')
            (output/'result.json').write_text(json.dumps(timings,indent=2)+'\n')
            print(json.dumps(timings))
        finally:
            for process in reversed(children): stop(process)


if __name__ == '__main__': run(Path(sys.argv[1]))
