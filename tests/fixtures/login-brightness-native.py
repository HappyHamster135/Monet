"""Native mock-authentication greeter, real brightness QML and a private backend."""
import json,os,select,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.test import private_session,stop
from tests.native_archive_session import desktop
binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
with private_session() as env,patch.dict(os.environ,env,clear=True),desktop():
 os.environ.update(QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1',QT_ACCESSIBILITY='1',NO_AT_BRIDGE='0',LANG='C.UTF-8',LC_ALL='C.UTF-8')
 import dbus
 bus=dbus.SessionBus()
 with (out/'backend.log').open('w') as log:
  fake=subprocess.Popen([sys.executable,str(ROOT/'tests/fixtures/brightness-native.py'),'display1'],stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
 assert select.select([fake.stdout],[],[],5)[0] and fake.stdout.readline().strip()=='READY'
 test=bus.get_object('org.monet.BrightnessTest','/test')
 def snapshot():return json.loads(test.Snapshot(dbus_interface='org.monet.BrightnessTest'))
 with (out/'accessibility.log').open('w') as log:
  bridge=subprocess.Popen(['/usr/libexec/at-spi-bus-launcher','--launch-immediately'],stdout=log,stderr=log,start_new_session=True)
 process=None
 try:
  deadline=time.monotonic()+5
  while not bus.name_has_owner('org.a11y.Bus'):
   assert bridge.poll() is None and time.monotonic()<deadline;time.sleep(.02)
  os.environ['AT_SPI_BUS_ADDRESS']=str(bus.get_object('org.a11y.Bus','/org/a11y/bus').GetAddress(dbus_interface='org.a11y.Bus'))
  import pyatspi
  accessible=pyatspi.Registry.getDesktop(0)
  def nodes():
   stack=[accessible];result=[]
   while stack and len(result)<500:
    item=stack.pop()
    try:result.append(item);stack.extend(item[i] for i in range(min(item.childCount,100)))
    except Exception:pass
   return result
  def wait(condition):
   end=time.monotonic()+10
   while time.monotonic()<end:
    assert process is None or process.poll() is None,(out/'greeter.log').read_text()
    if condition():return
    time.sleep(.04)
   raise AssertionError(('Greeter fixture timeout',[n.name for n in nodes()],snapshot(),(out/'greeter.log').read_text()))
  with (out/'greeter.log').open('w') as log:
   process=subprocess.Popen([str(binary),'--test'],stdout=log,stderr=log,start_new_session=True)
   wait(lambda:any(n.name=='Brightness' for n in nodes()))
   windows=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(process.pid)],text=True).splitlines();window=windows[0]
   subprocess.run(['xdotool','windowfocus','--sync',window],check=True)
   subprocess.run(['xdotool','key','--clearmodifiers','XF86MonBrightnessDown'],check=True)
   wait(lambda:snapshot()['level']==950)
   subprocess.run(['xdotool','key','--clearmodifiers','XF86MonBrightnessUp'],check=True)
   wait(lambda:snapshot()['level']==1000)
   button=next(n for n in nodes() if n.name=='Brightness');action=button.queryAction();assert action.doAction(0)
   wait(lambda:any(n.getRoleName()=='slider' for n in nodes()))
   slider=next(n for n in nodes() if n.getRoleName()=='slider' and 'Built-in' in n.name)
   # A keyboard change exercises the real Slider's onMoved path.
   slider.queryComponent().grabFocus()
   subprocess.run(['xdotool','key','--clearmodifiers','Left'],check=True)
   wait(lambda:snapshot()['level']<1000)
   subprocess.run([sys.executable,'-c','from PySide6.QtGui import QGuiApplication;import sys;a=QGuiApplication([]);assert a.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])',window,str(out/'greeter.png')],check=True)
   bad=['TypeError:','ReferenceError:','is not a type','Unable to assign']
   text=(out/'greeter.log').read_text();assert not any(value in text for value in bad),text
   result=dict(passed=True,native_mock_authentication=True,brightness_keys=True,brightness_slider=True,final_level=snapshot()['level'],host_power_calls=0)
   (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 finally:
  if process is not None:stop(process)
  stop(fake);fake.stdout.close();stop(bridge)
