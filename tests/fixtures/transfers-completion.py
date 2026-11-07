#!/usr/bin/python3
"""Actual KIO copy/download + native tracker, Ark queue and rendered Transfers."""
import http.server
import json
import os
import select
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tests.test_files_qol import jobs_module
from tools.test import private_session
if not sys.argv[1:]:
    # Earlier real extraction checks may leave Files owning FileManager1 on the
    # suite bus. This fixture must own its controlled endpoint, not queue behind
    # another file manager while accidentally dispatching actions to that app.
    with private_session() as env:
        subprocess.run([sys.executable, __file__, '--isolated-session'], env=env, check=True, timeout=60)
    raise SystemExit(0)
assert sys.argv[1:] == ['--isolated-session']
assert os.environ.get('QT_QPA_PLATFORM')=='offscreen'
assert os.environ['HOME'].startswith('/tmp/monet-tests-')
fixture=Path(os.environ['MONET_LAUNCHER_FIXTURE']).with_name('tracked-file-job')
with tempfile.TemporaryDirectory(prefix='monet-transfer-completion-') as temporary:
    folder=Path(temporary); processes=[];server=None
    actions=folder/'actions.jsonl';widgetlog=folder/'widget.log'
    directory_app=folder/'directory-app.py'
    directory_app.write_text('import json,sys\nwith open(sys.argv[1],"a") as f:f.write(json.dumps(dict(kind="directory",urls=sys.argv[2:]))+"\\n")\n')
    fm=folder/'filemanager.py'
    fm.write_text('''import dbus,dbus.service,dbus.mainloop.glib,json,sys
from gi.repository import GLib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
class FileManager(dbus.service.Object):
 @dbus.service.method('org.freedesktop.FileManager1',in_signature='ass',out_signature='')
 def ShowItems(self,urls,startup):
  with open(sys.argv[1],'a') as f:f.write(json.dumps(dict(kind='items',urls=list(map(str,urls))))+'\\n')
 @dbus.service.method('org.freedesktop.FileManager1',in_signature='ass',out_signature='')
 def ShowFolders(self,urls,startup):
  with open(sys.argv[1],'a') as f:f.write(json.dumps(dict(kind='directory',urls=list(map(str,urls))))+'\\n')
bus=dbus.SessionBus();name=dbus.service.BusName('org.freedesktop.FileManager1',bus,do_not_queue=True);obj=FileManager(name,'/org/freedesktop/FileManager1')
print(json.dumps(dict(expectedOwner=bus.get_unique_name(),actualOwner=str(bus.get_name_owner('org.freedesktop.FileManager1')))),flush=True)
GLib.MainLoop().run()
''')
    applications=Path(os.environ['XDG_DATA_HOME'])/'applications';applications.mkdir(parents=True,exist_ok=True)
    entry=applications/'monet-transfer-folder-fixture.desktop'
    entry.write_text(f'[Desktop Entry]\nType=Application\nName=Private folder fixture\nNoDisplay=true\nExec={sys.executable} {directory_app} {actions} %U\nMimeType=inode/directory;\nX-KDE-Protocols=file,webdav,webdavs\nStartupNotify=false\n')
    (applications/'monet-transfer-operation-fixture.desktop').write_text(
        f'[Desktop Entry]\nType=Application\nName=Private file operation fixture\nNoDisplay=true\nExec={fixture}\n')
    (Path(os.environ['XDG_CONFIG_HOME'])/'mimeapps.list').write_text('[Default Applications]\ninode/directory=monet-transfer-folder-fixture.desktop;\n')
    subprocess.run(['kbuildsycoca6','--noincremental'],check=True,stdout=subprocess.DEVNULL)
    package=Path(os.environ['XDG_DATA_HOME'])/'plasma/plasmoids/org.monet.transfers'
    shutil.copytree(ROOT/'linux/share/plasma/plasmoids/org.monet.transfers',package)
    ui=package/'contents/ui'
    for part in (ROOT/'linux/share/monet/widgets').iterdir():
        if part.is_file():shutil.copy2(part,ui/part.name)
    binary=folder/'bin';binary.mkdir()
    for name in ('monet-file-jobs','monet-store-jobs','monet-files-tools'):
        shutil.copy2(ROOT/'linux/libexec'/name,binary/name);(binary/name).chmod(0o700)
    for part in ui.glob('*.qml'):
        part.write_text(part.read_text().replace('@LIBEXECDIR@',str(binary)).replace('@DATADIR@','/usr/share').replace('@BINDIR@',str(binary)))
    main=ui/'main.qml';source=main.read_text();source=source[:source.rfind('}')]+'''
    property int fixturePhase: 0
    property int fixtureTicks: 0
    property int fixtureIndex: 0
    property bool fixtureWaiting: false
    property var fixtureButtons: []
    function allItems(item) {
        let result=[item];
        for(let child of item.children || []) result=result.concat(allItems(child));
        return result;
    }
    function fixtureVisible(item) {
        for(let node=item; node && node!==root.fullRepresentationItem; node=node.parent) if(!node.visible) return false;
        return true;
    }
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            if (root.fixturePhase===99 || root.fixturePhase===100) return;
            if(!folderOpen.nativeReady) { console.error("TRANSFER_NATIVE_MODULE_MISSING"); root.fixturePhase=99; return; }
            if(root.fixturePhase===0) {
                root.expanded=true;
                if(!root.fullRepresentationItem) return;
                const items=root.allItems(root.fullRepresentationItem);
                const frames=items.filter(item=>item.job !== undefined && item.job);
                const ready=frames.filter(item=>item.job.state===NotificationManager.Notifications.JobStateStopped && !item.job.error && root.fixtureVisible(item));
                if(++root.fixtureTicks%10===0) console.log("TRANSFER_COMPLETION_WAIT",JSON.stringify({ready:ready.length,count:nativeJobs.count,active:activity.active,local:root.localJobs,frames:frames.map(item=>({state:item.job.state,error:item.job.error,errorText:item.job.errorText,stopped:NotificationManager.Notifications.JobStateStopped,visible:root.fixtureVisible(item),url:String(item.job.destUrl)}))}));
                if(ready.length<2 || !root.localJobs.some(job=>job.owner==='files' && job.state==='done')) return;
                console.log("TRANSFER_COMPLETION_BEFORE_HIDE", JSON.stringify(frames.map(item=>({url:String(item.job.destUrl),effective:String(item.job.effectiveDestUrl),state:item.job.state,visible:root.fixtureVisible(item)}))));
                root.expanded=false; root.fixturePhase=1;root.fixtureTicks=0;
            } else if(root.fixturePhase===1) {
                if(++root.fixtureTicks<3) return;
                root.expanded=true;root.fixturePhase=2;
            } else if(root.fixturePhase===2) {
                const buttons=root.allItems(root.fullRepresentationItem).filter(item=>["openNativeTransferFolder","openLocalTransferFolder"].includes(item.objectName) && root.fixtureVisible(item));
                const native=buttons.filter(item=>item.objectName==='openNativeTransferFolder');
                const local=buttons.filter(item=>item.objectName==='openLocalTransferFolder');
                if(native.length!==2 || local.length!==1) { console.error("TRANSFER_WRONG_BUTTON_COUNT", native.length,local.length);root.fixturePhase=99;return; }
                const descriptions=root.allItems(root.fullRepresentationItem).filter(item=>item.objectName==='nativeTransferDescription' && root.fixtureVisible(item)).map(item=>item.text);
                if(descriptions.some(text=>text.includes('<a ') || text.includes('</a>') || text.includes('&amp;'))) {console.error('TRANSFER_DESCRIPTION_MARKUP',JSON.stringify(descriptions));root.fixturePhase=99;return;}
                console.log("TRANSFER_COMPLETION_BUTTONS",JSON.stringify(buttons.map(item=>({kind:item.objectName,url:String(item.destination),text:item.text}))));
                if(buttons.some(item=>item.text!=="Open folder")) {console.error("TRANSFER_WRONG_BUTTON_TEXT");root.fixturePhase=99;return;}
                root.fixtureButtons=buttons;root.fixturePhase=3;
            } else if(root.fixturePhase===3) {
                if(folderOpen.error!=="") {console.error("TRANSFER_OPEN_ERROR",folderOpen.error);root.fixturePhase=99;return;}
                if(folderOpen.busy) return;
                if(root.fixtureWaiting) {root.fixtureWaiting=false;root.fixtureIndex++;}
                if(root.fixtureIndex>=root.fixtureButtons.length) {
                    root.fullRepresentationItem.grabToImage(result=>{
                        result.saveToFile("@CAPTURE@");root.fixturePhase=4;
                    });
                    root.fixturePhase=100;return;
                }
                root.fixtureButtons[root.fixtureIndex].clicked();root.fixtureWaiting=true;
            } else if(root.fixturePhase===4) {
                const scroll=root.allItems(root.fullRepresentationItem).find(item=>item.objectName==='transferScroll');
                if(scroll && scroll.contentItem) scroll.contentItem.contentY=Math.max(0,scroll.contentItem.contentHeight-scroll.contentItem.height);
                root.fixturePhase=5;
            } else if(root.fixturePhase===5) {
                root.fullRepresentationItem.grabToImage(result=>{
                    result.saveToFile("@BOTTOM@");console.log("TRANSFER_OPEN_SUCCESS",root.fixtureIndex);root.fixturePhase=6;
                });
                root.fixturePhase=100;
            } else if(root.fixturePhase===6) {
                if(!root.localJobs.some(job=>job.fixtureMissing)) return;
                const button=root.allItems(root.fullRepresentationItem).find(item=>item.objectName==='openLocalTransferFolder' && root.fixtureVisible(item));
                if(!button) return;
                button.clicked();root.fixturePhase=7;
            } else if(root.fixturePhase===7) {
                if(folderOpen.busy) return;
                if(!folderOpen.error) {console.error('TRANSFER_EXPECTED_FOLDER_ERROR');root.fixturePhase=99;return;}
                root.fullRepresentationItem.grabToImage(result=>{result.saveToFile("@ERROR@");root.fixturePhase=8;});
                root.fixturePhase=100;
            } else if(root.fixturePhase===8) {
                const dismiss=root.allItems(root.fullRepresentationItem).find(item=>item.objectName==='dismissFolderMessage');
                if(!dismiss || !dismiss.visible) {console.error('TRANSFER_FOLDER_ERROR_NOT_DISMISSIBLE');root.fixturePhase=99;return;}
                dismiss.clicked();
                if(folderOpen.error) {console.error('TRANSFER_FOLDER_ERROR_NOT_CLEARED');root.fixturePhase=99;return;}
                console.log("TRANSFER_COMPLETION_DONE",root.fixtureIndex);root.fixturePhase=100;
            }
        }
    }
}'''.replace('@CAPTURE@',str(folder/'completed.png')).replace('@BOTTOM@',str(folder/'completed-bottom.png')).replace('@ERROR@',str(folder/'unavailable.png'))
    main.write_text(source)
    def until(condition,seconds=15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if condition():return
            if widgetlog.exists() and any(error in widgetlog.read_text() for error in ('TRANSFER_NATIVE_MODULE_MISSING','TRANSFER_WRONG_BUTTON_COUNT','TRANSFER_OPEN_ERROR','TRANSFER_WRONG_BUTTON_TEXT','TRANSFER_DESCRIPTION_MARKUP','TRANSFER_EXPECTED_FOLDER_ERROR','TRANSFER_FOLDER_ERROR_NOT')):
                raise AssertionError(widgetlog.read_text())
            time.sleep(.03)
        raise AssertionError(widgetlog.read_text() if widgetlog.exists() else 'Transfers did not start')
    def native_job(mode,source,destination):
        process=subprocess.Popen([str(fixture),mode,str(source),str(destination)],stdout=subprocess.PIPE,text=True,
                                 env=dict(os.environ,MONET_TRACKED_JOB_HOLD='1'))
        processes.append(process)
        assert select.select([process.stdout],[],[],15)[0], 'Native file operation did not finish'
        result=json.loads(process.stdout.readline());assert result['error']==0,result
    try:
        import dbus
        bus=dbus.SessionBus()
        fm_log=(folder/'filemanager.log').open('w')
        process=subprocess.Popen([sys.executable,str(fm),str(actions)],stdout=subprocess.PIPE,stderr=fm_log,text=True);processes.append(process)
        assert select.select([process.stdout],[],[],5)[0], 'Private file-manager endpoint did not become ready'
        ready=process.stdout.readline().strip()
        assert ready, (folder/'filemanager.log').read_text()
        ownership=json.loads(ready);fm_log.write(ready+'\n');fm_log.flush()
        assert ownership['expectedOwner']==ownership['actualOwner'], ownership
        log=widgetlog.open('w')
        process=subprocess.Popen(['plasmawindowed','org.monet.transfers'],stdout=log,stderr=log,
            env=dict(os.environ,QT_QPA_PLATFORMTHEME='kde',QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_RULES='qml.debug=true'))
        processes.append(process)
        until(lambda:'org.kde.JobViewServer' in bus.list_names())
        source_folder=folder/'Original folder';source_folder.mkdir()
        (source_folder/'one.txt').write_text('first copied file');(source_folder/'two.txt').write_text('second copied file')
        copies=folder/'Copies # å';copies.mkdir()
        native_job('copy',source_folder,copies)
        assert (copies/source_folder.name/'two.txt').read_text()=='second copied file'
        marker=folder/'SHOULD_NOT_EXECUTE'
        content=f'[Desktop Entry]\nType=Application\nName=Downloaded fixture\nExec=touch {marker}\n'.encode()
        class Download(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','application/x-desktop');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Download)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        download=folder/'Downloaded $(touch NO) # å.desktop'
        native_job('download',f'http://127.0.0.1:{server.server_port}/download.desktop',download)
        assert download.read_bytes()==content
        archive=folder/'archive.zip'
        with zipfile.ZipFile(archive,'w') as stream:stream.writestr('readme.txt','native extraction completion')
        queue=jobs_module().Queue();job=queue.submit(archive,folder/'Extracted # å')
        queue.run(job['token'],reveal=False)
        assert queue.read(job['token'])['state']=='done'
        # A fast Ark job need not register a progress view. Add a controlled
        # native view with KIO's display-form URL to exercise duplicate hiding.
        from PySide6.QtCore import QUrl
        views=bus.get_object('org.kde.JobViewServer','/JobViewServer')
        view_path=views.requestView('org.kde.ark',dbus.Int32(0),dbus.Dictionary({'immediate':True},signature='sv'),dbus_interface='org.kde.JobViewServerV2')
        view=bus.get_object('org.kde.JobViewServer',view_path)
        view.update(dbus.Dictionary({'destUrl':QUrl.fromLocalFile(job['destination']).toString(),'title':'Extracting archive','totalFiles':dbus.UInt64(1)},signature='sv'),dbus_interface='org.kde.JobViewV3')
        view.terminate(dbus.UInt32(0),'',dbus.Dictionary({},signature='sv'),dbus_interface='org.kde.JobViewV3')
        until(lambda:'TRANSFER_OPEN_SUCCESS 3' in widgetlog.read_text())
        retained=folder/'Retained extraction';Path(job['destination']).rename(retained)
        queue.change(job['token'],fixtureMissing=True)
        until(lambda:'TRANSFER_COMPLETION_DONE 3' in widgetlog.read_text())
        assert (retained/'readme.txt').read_text()=='native extraction completion'
        until(lambda:actions.exists() and len(actions.read_text().splitlines())>=3)
        values=[json.loads(line) for line in actions.read_text().splitlines()]
        assert len(values)==3,values
        from urllib.parse import urlsplit,unquote
        def path(url):return Path(unquote(urlsplit(url).path)) if url.startswith('file:') else Path(url)
        items=[path(value['urls'][0]) for value in values if value['kind']=='items']
        directories={path(value['urls'][0]) for value in values if value['kind']=='directory'}
        assert items==[download],values
        assert directories=={copies,Path(job['destination'])},values
        assert not marker.exists() and not (folder/'NO').exists()
        assert (folder/'completed.png').exists(),widgetlog.read_text()
        assert not any(error in widgetlog.read_text() for error in ('TypeError:','ReferenceError:','Cannot assign to non-existent property','is not a type')),widgetlog.read_text()
        report=dict(ok=True,actions=values,checks=['actual native KIO copy','actual HTTP download','native progress tracker',
            'actual Ark extraction queue','completed rows survive close/reopen','consistent Open folder buttons',
            'file selected in its parent','directory opened directly','downloaded desktop file never executed',
            'encoded archive destination is represented once','native descriptions show text without HTML markup',
            'unavailable destination has a dismissible error and keeps extracted files'])
        if os.environ.get('MONET_TRANSFER_CAPTURE'):
            output=Path(os.environ['MONET_TRANSFER_CAPTURE']);output.mkdir(parents=True,exist_ok=True)
            for name in ('widget.log','completed.png','completed-bottom.png','unavailable.png'):
                if (folder/name).exists():shutil.copyfile(folder/name,output/name)
            (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
    finally:
        if os.environ.get('MONET_TRANSFER_CAPTURE'):
            output=Path(os.environ['MONET_TRANSFER_CAPTURE']);output.mkdir(parents=True,exist_ok=True)
            if widgetlog.exists():shutil.copyfile(widgetlog,output/'widget.log')
            for name in ('actions.jsonl','filemanager.log'):
                if (folder/name).exists():shutil.copyfile(folder/name,output/name)
        if server:server.shutdown();server.server_close()
        for process in reversed(processes):
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            if process.stdout is not None:process.stdout.close()
        shutil.rmtree(package,ignore_errors=True)
