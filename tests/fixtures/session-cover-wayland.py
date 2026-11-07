"""Real layer-shell cover and native save-window detection on private KWin.

GUI_TEST, a disconnected system bus and a disposable session bus prohibit any
laptop power/session action. The fake Shutdown service never performs an action.
"""
import importlib.util,json,os,select,shlex,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.test import private_session,stop

if len(sys.argv)==3:
    binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
    with private_session() as env:
        directory=Path(env['HOME']).parent;kwin=directory/'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'),kwin);kwin.chmod(0o700)
        env.update(QT_QPA_PLATFORM='wayland',XDG_SESSION_TYPE='wayland',XDG_CURRENT_DESKTOP='KDE',WAYLAND_DISPLAY='monet-cover-test',PLASMA_SESSION_GUI_TEST='1',PLASMA_DEFAULT_SHELL='org.kde.plasma.desktop',QT_FORCE_STDERR_LOGGING='1',QT_QPA_PLATFORMTHEME='kde',QT_LOGGING_RULES='qml.debug=true')
        env.pop('KWIN_COMPOSE',None)
        script=directory/'run.sh';script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,__file__,str(binary),str(out),'child'])+'\n');script.chmod(0o700)
        with (out/'kwin.log').open('w') as log:
            p=subprocess.Popen([str(kwin),'--virtual','--width','1280','--height','800','--socket','monet-cover-test','--no-lockscreen','--no-global-shortcuts','--no-kactivities','--exit-with-session',str(script)],env=env,stdout=log,stderr=log,start_new_session=True)
            try:
                code=p.wait(timeout=65)
                assert code==0,(out/'kwin.log').read_text()
            finally:stop(p)
    print((out/'result.json').read_text())
else:
    import dbus
    binary=Path(sys.argv[1]);out=Path(sys.argv[2]);process=server=prompt=app=None
    spec=importlib.util.spec_from_file_location('cover_plan',ROOT/'tools/install-desktop-preview.py');installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
    shell=installer.DATA/'plasma/shells/org.kde.plasma.desktop'
    for path,(data,mode) in installer.plan().items():
        if path.is_relative_to(shell):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(mode)
    ui=shell/'contents/logout';source=(ui/'Logout.qml').read_text()
    mode=os.environ.get('MONET_COVER_ACTION','restart');assert mode in ['restart','shutdown']
    probe='''
 property int tick: 0
 function fixtureState() { return {leaving:handoffStarted,interactive:monetInteractionRequired,windows:windowState()} }
 onMonetInteractionRequiredChanged: console.log("COVER_STATE",JSON.stringify(fixtureState()))
 Timer { interval:100; running:true; repeat:true; onTriggered: {
  if (page.status !== Loader.Ready || !page.item) return;
  host.tick++;
  if (host.tick === 5) console.log("COVER_READY",JSON.stringify(host.fixtureState()));
  if (host.tick === 16) page.item.leave(() => page.item.rebootRequested(), "Restarting…");
  if (host.tick === 24) {
   console.log("COVER_LEAVING",JSON.stringify(host.fixtureState()));
   host.grabToImage(result => result.saveToFile(SNAPSHOT));
  }
 }}
'''.replace('SNAPSHOT',json.dumps(str(out/'transition.png')))
    if mode=='shutdown':probe=probe.replace('rebootRequested()','haltRequested()').replace('Restarting…','Shutting down…')
    (ui/'Logout.qml').write_text(source[:source.rfind('}')]+probe+'}\n')
    bus=dbus.SessionBus()
    def logs():return (out/'greeter.log').read_text()
    def wait(condition):
        end=time.monotonic()+12
        while time.monotonic()<end:
            if process is not None:assert process.poll() is None,logs()
            if condition():return
            time.sleep(.04)
        raise AssertionError(logs())
    def states():return [json.loads(line.split('COVER_STATE ',1)[1]) for line in logs().splitlines() if 'COVER_STATE ' in line]
    def window(title,fill=False):
        code='''from PySide6.QtWidgets import QApplication,QMessageBox,QWidget\nfrom PySide6.QtCore import QTimer\na=QApplication([]);d=QWidget() if FILL else QMessageBox();d.setWindowTitle(TITLE)\nif FILL:d.setStyleSheet("background:#d700a0");d.showFullScreen()\nelse:d.setText("Save your work before leaving.");d.show()\nQTimer.singleShot(30000,a.quit);a.exec()'''.replace('TITLE',repr(title)).replace('FILL',repr(fill))
        return subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    def screenshot(name):
        path=out/(name+'.png')
        p=subprocess.run(['spectacle','--background','--nonotify','--fullscreen','--output',str(path)],capture_output=True,text=True,timeout=10)
        assert p.returncode==0 and path.exists(),p.stdout+p.stderr
        from PySide6.QtGui import QImage
        image=QImage(str(path));assert not image.isNull()
        return image.pixelColor(10,10).name()
    try:
        app=window('Existing application',fill=True);time.sleep(.5)
        with (out/'greeter.log').open('w') as log:
            process=subprocess.Popen([str(binary)],stdout=log,stderr=log,start_new_session=True)
            wait(lambda:bus.name_has_owner('org.kde.LogoutPrompt'))
            bus.get_object('org.kde.LogoutPrompt','/LogoutPrompt').promptAll(dbus_interface='org.kde.LogoutPrompt')
            wait(lambda:'COVER_READY' in logs())
            code='import dbus,dbus.service,time\nbus=dbus.SessionBus();name=dbus.service.BusName("org.kde.Shutdown",bus);print("READY",flush=True);time.sleep(60)\n'
            server=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            assert select.select([server.stdout],[],[],3)[0] and server.stdout.readline().strip()=='READY'
            wait(lambda:'COVER_LEAVING' in logs())
            initial=json.loads(next(line.split('COVER_LEAVING ',1)[1] for line in logs().splitlines() if 'COVER_LEAVING ' in line))
            assert initial['leaving'] and not initial['interactive'] and initial['windows'],initial
            covered_pixel=screenshot('covered-desktop');assert covered_pixel!='#d700a0',covered_pixel
            prompt=window('Unsaved work prompt')
            wait(lambda:states() and states()[-1]['interactive'])
            time.sleep(.25)
            prompt_pixel=screenshot('revealed-save-prompt');assert prompt_pixel=='#d700a0',prompt_pixel
            stop(prompt);prompt=None
            wait(lambda:states() and not states()[-1]['interactive'])
            time.sleep(.25)
            restored_pixel=screenshot('restored-cover');assert restored_pixel==covered_pixel,(restored_pixel,covered_pixel)
            stop(server);server=None
            assert process.wait(timeout=5)==0
            assert not any(error in logs() for error in ['TypeError:','ReferenceError:','Unable to assign','No such method']),logs()
            result=dict(passed=True,mode=mode,native_layer_shell=True,existing_app_covered=True,new_native_prompt_revealed=True,cover_restored_after_prompt=True,cancellation_exits=True,actual_power_actions=0,rendered_pixels=dict(covered=covered_pixel,prompt=prompt_pixel,restored=restored_pixel),initial=initial,states=states())
            (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        for p in [process,server,prompt,app]:
            if p is not None:stop(p)
