import os,subprocess,json,shutil,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
if (root/'nested.pid').exists():
    raise RuntimeError('Use a new fixture directory; an earlier compositor may still be running')
subprocess.run([sys.executable,str(Path(__file__).with_name('check-runtime.py')),str(root),sys.argv[2]],check=True)
plugins=root/'plugins/kwin/plugins';plugins.mkdir(parents=True,exist_ok=True)
shutil.copyfile(root/'build/monet_window_identity.so',plugins/'monet_window_identity.so')
config=root/'config';config.mkdir(exist_ok=True)
if not (config/'kwinrc').exists():
    (config/'kwinrc').write_text('')  # Exercise the shipped default without overriding the user's preference.
session=root/'session.py'
session.write_text('''#!/usr/bin/python3
import os,json,subprocess
from pathlib import Path
root=Path(__file__).parent
(root/'session-env.json').write_text(json.dumps({key:os.environ[key] for key in ('DBUS_SESSION_BUS_ADDRESS','WAYLAND_DISPLAY','XDG_RUNTIME_DIR')}))
raise SystemExit(subprocess.call([str(root/'build/identity_fixture'),str(root/'identity.json')]))
''');session.chmod(0o755)
runtime='/run/user/'+str(os.getuid())
env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path='+runtime+'/bus',XDG_RUNTIME_DIR=runtime,WAYLAND_DISPLAY='wayland-0',QT_PLUGIN_PATH=str(root/'plugins'),XDG_CONFIG_HOME=str(config),QT_LOGGING_RULES='kwin_core.debug=true')
p=subprocess.Popen(['dbus-run-session','--','kwin_wayland','--wayland-display','wayland-0','--socket','monet-identity','--width','1100','--height','650','--no-lockscreen','--no-global-shortcuts','--no-kactivities','--exit-with-session',str(session)],env=env,stdout=(root/'nested.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
(root/'nested.pid').write_text(str(p.pid));print('Nested KWin PID',p.pid)
