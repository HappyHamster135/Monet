"""Native greeter handoff/cancellation and an accessible unsaved-work prompt.

All buses/display/profile are disposable; GUI_TEST and a disconnected system
bus prevent actual power/session actions. The fake shutdown service only owns
its name, then disconnects to simulate cancellation.
"""
import importlib.util,json,os,select,shutil,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.test import private_session,stop
from tests.native_archive_session import desktop
binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
with private_session() as env,patch.dict(os.environ,env,clear=True),desktop():
 os.environ.update(PLASMA_SESSION_GUI_TEST='1',PLASMA_DEFAULT_SHELL='org.kde.plasma.desktop',QT_QPA_PLATFORMTHEME='kde',QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_RULES='qml.debug=true')
 spec=importlib.util.spec_from_file_location('handoff_plan',ROOT/'tools/install-desktop-preview.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
 files=p.plan();shell=p.DATA/'plasma/shells/org.kde.plasma.desktop'
 for path,(data,mode) in files.items():
  if path.is_relative_to(shell):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(mode)
 fonts=p.DATA/'fonts/monet';shutil.copytree(ROOT/'linux/share/fonts/monet',fonts)
 subprocess.run(['fc-cache','-f',str(fonts)],check=True,stdout=subprocess.DEVNULL)
 ui=shell/'contents/logout';source=(ui/'Logout.qml').read_text()
 injection='''
 property int fixtureTick: 0
 Timer {
  interval: 100; running: true; repeat: true
  onTriggered: {
   if (page.status !== Loader.Ready || !page.item) return;
   host.fixtureTick++;
   if (host.fixtureTick === 2) console.log("MONET_HANDOFF_READY");
   if (host.fixtureTick === 16) page.item.leave(() => page.item.rebootRequested(), "Restarting…");
   if (host.fixtureTick === 24) {
    console.log("MONET_HANDOFF_VISIBLE",JSON.stringify({leaving:page.item.leaving,message:host.transitionMessage}));
    host.grabToImage(image => image.saveToFile(SNAPSHOT));
   }
  }
 }
'''.replace('SNAPSHOT',json.dumps(str(out/'transition.png')))
 (ui/'Logout.qml').write_text(source[:source.rfind('}')]+injection+'}\n')
 process=server=prompt=None
 try:
  with (out/'greeter.log').open('w') as log:
   process=subprocess.Popen([str(binary),'--windowed'],stdout=log,stderr=log,start_new_session=True)
   def wait(condition):
    end=time.monotonic()+10
    while time.monotonic()<end:
     assert process.poll() is None,(out/'greeter.log').read_text()
     if condition():return
     time.sleep(.03)
    raise AssertionError((out/'greeter.log').read_text())
   wait(lambda:'MONET_HANDOFF_READY' in (out/'greeter.log').read_text())
   code='import dbus,dbus.service,time\nbus=dbus.SessionBus();name=dbus.service.BusName("org.kde.Shutdown",bus);print("READY",flush=True);time.sleep(60)\n'
   server=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   assert select.select([server.stdout],[],[],3)[0] and server.stdout.readline().strip()=='READY'
   wait(lambda:'MONET_HANDOFF_VISIBLE' in (out/'greeter.log').read_text())
   line=next(l.split('MONET_HANDOFF_VISIBLE ',1)[1] for l in (out/'greeter.log').read_text().splitlines() if 'MONET_HANDOFF_VISIBLE ' in l)
   data=json.loads(line);assert data==dict(leaving=True,message='Restarting…'),data
   code='from PySide6.QtWidgets import QApplication,QMessageBox\nfrom PySide6.QtCore import QTimer\na=QApplication([]);d=QMessageBox();d.setWindowTitle("Unsaved Work Test");d.setText("Your save prompt remains available.");d.show();QTimer.singleShot(10000,a.quit);a.exec()\n'
   with (out/'prompt.log').open('w') as log:
    prompt=subprocess.Popen([sys.executable,'-c',code],stdout=log,stderr=log,start_new_session=True)
    def prompt_window():
     result=subprocess.run(['xdotool','search','--onlyvisible','--name','^Unsaved Work Test$'],capture_output=True,text=True)
     return result.stdout.splitlines()
    wait(lambda:bool(prompt_window()));window=prompt_window()[0]
    subprocess.run(['xdotool','windowfocus','--sync',window],check=True)
    focused=subprocess.check_output(['xdotool','getwindowfocus'],text=True).strip();assert focused==window
    assert process.poll() is None
    stop(prompt);prompt=None
   stop(server);server=None
   assert process.wait(timeout=5)==0
   text=(out/'greeter.log').read_text();assert not any(s in text for s in ['TypeError:','ReferenceError:','No such method','Cannot open:']),text
   result=dict(passed=True,monet_transition_visible=True,native_surface_retained=True,unsaved_prompt_can_focus=True,cancel_closes_backdrop=True,actual_power_actions=0,scope='Native patched greeter in GUI_TEST mode on private X11, profile and buses; no laptop session or power call.')
   (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 finally:
  for child in [process,server,prompt]:
   if child is not None:stop(child)
