"""Private fake desktop services, plus the real independent Keep awake process."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

if os.environ.get('MONET_KEEP_AWAKE_PRIVATE_BUS') != '1':
    raise SystemExit('Run only on the private test bus')
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio, GLib
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'linux/share/monet'))
from monet_runtime.keep_awake import POWER, SCREEN, NAME, PATH

bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
def call(service,path,interface,method,signature='()',args=()):
    return bus.call_sync(service,path,interface,method,GLib.Variant(signature,args),None,
                         Gio.DBusCallFlags.NONE,2500,None).unpack()
def dbus(method, signature, args):
    return call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus',method,signature,args)
def owner(name): return dbus('NameHasOwner','(s)',(name,))[0]

TEST='org.monet.KeepAwakeTest'
TESTPATH='/org/monet/KeepAwakeTest'

if sys.argv[1]=='fake':
    cookies={}; counter=[0]; fail_screen=[False]
    xmls=[(POWER[1],'''<node><interface name="org.kde.Solid.PowerManagement.PolicyAgent">
    <method name="AddInhibition"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="out"/></method>
    <method name="ReleaseInhibition"><arg type="u" direction="in"/></method></interface></node>'''),
    (SCREEN[1],'''<node><interface name="org.freedesktop.ScreenSaver">
    <method name="Inhibit"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="out"/></method>
    <method name="UnInhibit"><arg type="u" direction="in"/></method></interface></node>'''),
    (TESTPATH,'''<node><interface name="org.monet.KeepAwakeTest">
    <method name="Snapshot"><arg type="s" direction="out"/></method>
    <method name="DropPower"/><method name="RestorePower"/>
    <method name="FailScreen"><arg type="b" direction="in"/></method></interface></node>''')]
    def method(connection,sender,path,interface,method,args,invocation):
        values=args.unpack()
        if method in ('AddInhibition','Inhibit'):
            if method=='Inhibit' and fail_screen[0]:
                invocation.return_dbus_error('org.monet.Test.Unavailable','Screen failure'); return
            if method=='AddInhibition': assert values[0]==5
            counter[0]+=1; cookies[counter[0]]=dict(owner=sender,kind='power' if method=='AddInhibition' else 'screen')
            invocation.return_value(GLib.Variant('(u)',(counter[0],))); return
        if method in ('ReleaseInhibition','UnInhibit'):
            record=cookies.get(values[0]); assert not record or record['owner']==sender
            cookies.pop(values[0],None)
        elif method=='Snapshot':
            invocation.return_value(GLib.Variant('(s)',(json.dumps(list(cookies.values())),))); return
        elif method=='DropPower': dbus('ReleaseName','(s)',(POWER[0],))
        elif method=='RestorePower': dbus('RequestName','(su)',(POWER[0],4))
        elif method=='FailScreen': fail_screen[0]=values[0]
        invocation.return_value(GLib.Variant('()',()))
    for path,xml in xmls:
        info=Gio.DBusNodeInfo.new_for_xml(xml)
        bus.register_object(path,info.interfaces[0],method,None,None)
    def changed(connection,sender,path,interface,signal,params):
        name,old,new=params.unpack()
        if name.startswith(':') and not new:
            for cookie in list(cookies):
                if cookies[cookie]['owner']==name: cookies.pop(cookie)
    bus.signal_subscribe('org.freedesktop.DBus','org.freedesktop.DBus','NameOwnerChanged',
        '/org/freedesktop/DBus',None,Gio.DBusSignalFlags.NONE,changed)
    for name in (POWER[0],SCREEN[0],TEST): assert dbus('RequestName','(su)',(name,4))[0]==1
    print('READY',flush=True)
    GLib.MainLoop().run()
else:
    from tests.test_look import quick_helper
    fake=subprocess.Popen([sys.executable,__file__,'fake'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    worker=None
    def wait(condition):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            if condition(): return
            time.sleep(.04)
        raise AssertionError('Private native condition did not arrive')
    def test_call(method, signature='()', args=()): return call(TEST,TESTPATH,TEST,method,signature,args)
    def snapshot(): return json.loads(test_call('Snapshot')[0])
    def status(): return json.loads(call(NAME,PATH,NAME,'GetStatus')[0])
    def set_duration(seconds): return json.loads(call(NAME,PATH,NAME,'SetDuration','(i)',(seconds,))[0])
    def start():
        wait(lambda: not owner(NAME))
        process=subprocess.Popen([sys.executable,str(ROOT/'linux/libexec/monet-keep-awake')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        wait(lambda: owner(NAME))
        return process
    try:
        assert select.select([fake.stdout],[],[],5)[0]
        assert fake.stdout.readline().strip()=='READY'
        worker=start()
        q=quick_helper()
        assert q.set_keep_awake('on')['ok']
        assert len(snapshot())==2
        assert q.set_keep_awake('60')['ok']; assert len(snapshot())==2
        assert q.set_keep_awake('30')['ok']; assert len(snapshot())==2
        end=status()['end']
        test_call('DropPower'); wait(lambda: status()['pending'])
        assert not snapshot()
        test_call('RestorePower'); wait(lambda: status()['active'])
        assert status()['end']==end; assert len(snapshot())==2
        assert q.set_keep_awake('off')['ok']; worker.wait(timeout=5); assert worker.returncode==0
        wait(lambda: not snapshot())
        worker=start(); test_call('FailScreen','(b)',(True,))
        assert not set_duration(1800)['ok']; assert not snapshot()
        test_call('FailScreen','(b)',(False,))
        assert set_duration(2)['ok']
        worker.wait(timeout=6); assert worker.returncode==0
        wait(lambda: not snapshot())
        worker=start(); assert set_duration(-1)['ok']; assert len(snapshot())==2
        worker.kill(); worker.wait(timeout=3)
        wait(lambda: not owner(NAME)); wait(lambda: not snapshot())
        q=quick_helper(); assert q.keep_awake_status()['error']=='interrupted'
        assert q.set_keep_awake('off')['ok']
        print('Native expiry, partial acquisition, owner restart and crash cleanup passed.')
    finally:
        if worker and worker.poll() is None: worker.terminate(); worker.wait(timeout=5)
        fake.terminate(); fake.wait(timeout=5)
