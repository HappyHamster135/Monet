"""Time native Archives contents readiness on private X11/buses using an input RPM.

Usage: rpm-open-native.py ARK_BINARY PLUGIN_ROOT_OR_DASH INPUT_RPM OUTPUT
The input is opened read-only; the only UI action is Ctrl+Q after listing.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.test import private_session,stop
from tests.native_archive_session import desktop


def inspect(binary, plugins, source, output):
    output.mkdir(parents=True,exist_ok=False)
    initial=hashlib.sha256(source.read_bytes()).hexdigest()
    with private_session() as env,patch.dict(os.environ,env,clear=True),desktop():
        os.environ.update(QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1',QT_ACCESSIBILITY='1',NO_AT_BRIDGE='0',LANG='C.UTF-8',LC_ALL='C.UTF-8',LANGUAGE='en_US:en')
        if plugins!='-':os.environ['QT_PLUGIN_PATH']=plugins
        else:os.environ.pop('QT_PLUGIN_PATH',None)
        import dbus
        bus=dbus.SessionBus()
        with (output/'accessibility.log').open('w') as log:
            bridge=subprocess.Popen(['/usr/libexec/at-spi-bus-launcher','--launch-immediately'],stdout=log,stderr=log,start_new_session=True)
        process=None
        try:
            deadline=time.monotonic()+5
            while not bus.name_has_owner('org.a11y.Bus'):
                assert bridge.poll() is None and time.monotonic()<deadline
                time.sleep(.02)
            os.environ['AT_SPI_BUS_ADDRESS']=str(bus.get_object('org.a11y.Bus','/org/a11y/bus').GetAddress(dbus_interface='org.a11y.Bus'))
            import pyatspi
            accessible=pyatspi.Registry.getDesktop(0)
            def snapshot():
                stack=[accessible];names=[];extract=False;seen=0
                while stack and seen<500:
                    node=stack.pop();seen+=1
                    try:
                        name=node.name or '';names.append(name)
                        if name.replace('&','') in ('Extract', 'Extract All'):
                            states=node.getState();extract |= states.contains(pyatspi.STATE_ENABLED) and states.contains(pyatspi.STATE_SENSITIVE)
                        stack.extend(node[i] for i in reversed(range(min(node.childCount,150))))
                    except Exception:continue
                return names,extract
            before=sorted(p.name for p in Path(os.environ['HOME']).iterdir())
            with (output/'archives.log').open('w') as log:
                started=time.monotonic()
                process=subprocess.Popen([str(binary),str(source)],stdout=log,stderr=log,start_new_session=True)
                first=None;window=None
                while time.monotonic()-started<45:
                    assert process.poll() is None,(output/'archives.log').read_text()
                    found=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(process.pid)],capture_output=True,text=True)
                    if found.stdout and first is None:first=time.monotonic()-started
                    names,enabled=snapshot()
                    if found.stdout and 'etc' in names and 'usr' in names and enabled:
                        window=found.stdout.splitlines()[0];break
                    time.sleep(.025)
                else:raise AssertionError(('RPM contents did not become ready',names,enabled,(output/'archives.log').read_text()))
                ready=time.monotonic()-started
                (output/'accessible.json').write_text(json.dumps(names,indent=2)+'\n')
                subprocess.run([sys.executable,'-c','from PySide6.QtGui import QGuiApplication; import sys; a=QGuiApplication([]); assert a.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])',window,str(output/'ready.png')],check=True)
                subprocess.run(['xdotool','windowfocus','--sync',window],check=True)
                subprocess.run(['xdotool','key','--clearmodifiers','ctrl+q'],check=True)
                assert process.wait(timeout=5)==0
                assert sorted(p.name for p in Path(os.environ['HOME']).iterdir())==before
                result=dict(first_window_ms=first*1000,contents_ready_ms=ready*1000,extract_enabled=True,top_level=['etc','usr'],archive_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==initial,extracted=False,scope='Actual Archives window and accessible contents on private X11, session/accessibility buses and disconnected system bus; copied actual input RPM, warm local filesystem. Not reboot or cold-drive qualification.')
                assert result['archive_unchanged']
                (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps(result),flush=True)
        finally:
            if process is not None:stop(process)
            stop(bridge)

if __name__=='__main__':inspect(Path(sys.argv[1]).resolve(),sys.argv[2],Path(sys.argv[3]).resolve(),Path(sys.argv[4]).resolve())
