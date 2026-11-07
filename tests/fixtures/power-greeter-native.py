"""Load the preview plan in Plasma's real greeter, then only press Escape.

Run in the native desktop test runtime (with Xvfb):
  python3 tests/fixtures/power-greeter-native.py OUTPUT positive|fallback
Both session and system buses are isolated from the laptop. --windowed itself
is not a sandbox; isolation here is mandatory even though no power action is used.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop
from tests.native_archive_session import desktop


def run(output, broken):
    output.mkdir(parents=True, exist_ok=False)
    with private_session() as env, patch.dict(os.environ, env, clear=True), desktop():
        assert os.environ['DBUS_SYSTEM_BUS_ADDRESS'] == 'unix:path=/nonexistent'
        assert os.environ['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:path=/tmp/monet-tests-')
        assert os.environ['HOME'].startswith('/tmp/monet-tests-')
        spec=importlib.util.spec_from_file_location('power_preview_plan',ROOT/'tools/install-desktop-preview.py')
        installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
        files=installer.plan()
        shell=installer.DATA/'plasma/shells/org.kde.plasma.desktop'
        shell_files={p:v for p,v in files.items() if p.is_relative_to(shell)}
        assert shell_files and shell/'metadata.json' in shell_files
        for path,(data,mode) in shell_files.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            assert isinstance(data,bytes)
            path.write_bytes(data);path.chmod(mode)
        ui=shell/'contents/logout'
        assert (ui/'Logout.qml').read_bytes()==(ROOT/'linux/share/monet/logout/ShellLogout.qml').read_bytes()
        assert (ui/'MonetLogout.qml').read_bytes()==(ROOT/'linux/share/monet/logout/Logout.qml').read_bytes()
        fallback_hash=hashlib.sha256((ui/'KdeLogout.qml').read_bytes()).hexdigest()
        if broken:(ui/'MonetLogout.qml').write_text('Deliberately invalid QML for the fallback check\n')
        shutil.copytree(ROOT/'linux/share/fonts/monet',installer.DATA/'fonts/monet')
        subprocess.run(['fc-cache','-f',str(installer.DATA/'fonts/monet')],check=True,stdout=subprocess.DEVNULL)
        (installer.CONFIG/'kdeglobals').write_text((ROOT/'linux/share/color-schemes/MonetDark.colors').read_text())
        source=(ui/'Logout.qml').read_text()
        probe='''
    property int probeStage: 0
    onLogoutRequested: console.log("UNEXPECTED_POWER_ACTION")
    onHaltRequested: console.log("UNEXPECTED_POWER_ACTION")
    onHaltUpdateRequested: console.log("UNEXPECTED_POWER_ACTION")
    onSuspendRequested: console.log("UNEXPECTED_POWER_ACTION")
    onRebootRequested: console.log("UNEXPECTED_POWER_ACTION")
    onRebootRequested2: console.log("UNEXPECTED_POWER_ACTION")
    onRebootUpdateRequested: console.log("UNEXPECTED_POWER_ACTION")
    onCancelRequested: console.log("MONET_POWER_NATIVE_CANCEL")
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (page.status !== Loader.Ready || !page.item || host.width < 100 || ++host.probeStage < 4) return;
            running = false;
            const state = {fallback:host.usingFallback, page:page.item.objectName,
                width:host.width, height:host.height};
            host.grabToImage(result => {
                state.saved = result.saveToFile(SNAPSHOT);
                console.log("MONET_POWER_NATIVE_READY", JSON.stringify(state));
            });
        }
    }
'''.replace('SNAPSHOT',json.dumps(str(output/'screen.png')))
        (ui/'Logout.qml').write_text(source[:source.rfind('}')]+probe+'}\n')
        env=dict(os.environ,PLASMA_DEFAULT_SHELL='org.kde.plasma.desktop',QT_QPA_PLATFORMTHEME='kde',
                 QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_RULES='qml.debug=true')
        with (output/'greeter.log').open('w') as log:
            process=subprocess.Popen(['/usr/libexec/ksmserver-logout-greeter','--windowed'],env=env,
                                     stdout=log,stderr=log,start_new_session=True)
            try:
                deadline=time.monotonic()+20;state=None
                while time.monotonic()<deadline:
                    text=(output/'greeter.log').read_text()
                    lines=[line.split('MONET_POWER_NATIVE_READY ',1)[1] for line in text.splitlines() if 'MONET_POWER_NATIVE_READY ' in line]
                    if lines:state=json.loads(lines[-1]);break
                    assert process.poll() is None,text
                    time.sleep(.05)
                assert state is not None,(output/'greeter.log').read_text()
                assert state['saved'] and state['fallback']==broken,state
                assert (state['page']=='MonetPowerScreen') != broken,state
                if not broken:
                    for bad in ['Trying default theme','ReferenceError:','TypeError:','is not a type','Unable to assign']:
                        assert bad not in text,text
                windows=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(process.pid)],env=env,text=True).splitlines()
                assert windows
                subprocess.run(['xdotool','windowfocus','--sync',windows[0]],env=env,check=True)
                subprocess.run(['xdotool','key','--clearmodifiers','Escape'],env=env,check=True)
                assert process.wait(timeout=5)==0
                text=(output/'greeter.log').read_text()
                assert 'MONET_POWER_NATIVE_CANCEL' in text and 'UNEXPECTED_POWER_ACTION' not in text,text
                state.update(native_exit=0,cancel_verified=True,power_actions=0,
                             plan_shell_files=len(shell_files),native_fallback_sha256=fallback_hash,
                             scope='Actual Plasma greeter and generated account-preview shell plan on private Xvfb, session bus and disconnected system bus. Only Escape is pressed; no laptop power/session action.')
                (output/'result.json').write_text(json.dumps(state,indent=2)+'\n')
                print(json.dumps(state),flush=True)
            finally:stop(process)


if __name__=='__main__':
    assert sys.argv[2] in ('positive','fallback')
    run(Path(sys.argv[1]).resolve(),sys.argv[2]=='fallback')
