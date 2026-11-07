"""Actual Plasma menu, Kicker models, native KIO jobs and notification Retry."""
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import dbus
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[2]


def notification_server(log):
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus(); name = dbus.service.BusName('org.freedesktop.Notifications', bus)

    class Server(dbus.service.Object):
        next_id = 0
        @dbus.service.method('org.freedesktop.Notifications', in_signature='', out_signature='as')
        def GetCapabilities(self): return ['actions', 'body', 'body-markup', 'persistence']
        @dbus.service.method('org.freedesktop.Notifications', in_signature='', out_signature='ssss')
        def GetServerInformation(self): return ('Monet fixture', 'Monet', '1', '1.2')
        @dbus.service.method('org.freedesktop.Notifications', in_signature='susssasa{sv}i', out_signature='u')
        def Notify(self, app, replaces, icon, title, body, actions, hints, timeout):
            self.next_id += 1
            with open(log, 'a') as output:
                output.write(json.dumps(dict(id=self.next_id, title=str(title), body=str(body), actions=list(actions)))+'\n')
            return self.next_id
        @dbus.service.method('org.freedesktop.Notifications', in_signature='u', out_signature='')
        def CloseNotification(self, ident): self.NotificationClosed(ident, 3)
        @dbus.service.signal('org.freedesktop.Notifications', signature='uu')
        def NotificationClosed(self, ident, reason): pass
        @dbus.service.signal('org.freedesktop.Notifications', signature='us')
        def ActivationToken(self, ident, token): pass
        @dbus.service.signal('org.freedesktop.Notifications', signature='us')
        def ActionInvoked(self, ident, action): pass
        @dbus.service.method('org.monet.NotificationFixture', in_signature='us', out_signature='')
        def TriggerAction(self, ident, action):
            self.ActivationToken(ident, 'private-notification-test-token'); self.ActionInvoked(ident, action)

    server = Server(bus, '/org/freedesktop/Notifications')
    print('READY', flush=True); GLib.MainLoop().run()


def stop(process):
    process.terminate()
    try: process.wait(timeout=3)
    except subprocess.TimeoutExpired: process.kill(); process.wait()


def main():
    assert os.environ['HOME'].startswith('/tmp/monet-tests-')
    assert os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
    with tempfile.TemporaryDirectory(prefix='monet-launch-menu-') as temporary:
        folder = Path(temporary); data = folder/'data'; data.mkdir()
        env = dict(os.environ, XDG_DATA_HOME=str(data), QT_QPA_PLATFORMTHEME='kde', QT_FORCE_STDERR_LOGGING='1',
                   QT_LOGGING_RULES='qml.debug=true')
        package = data/'plasma/plasmoids/org.monet.menu'
        shutil.copytree(ROOT/'linux/share/plasma/plasmoids/org.monet.menu', package)
        ui = package/'contents/ui'
        for part in (ROOT/'linux/share/monet/widgets').iterdir():
            if part.is_file(): shutil.copy2(part, ui/part.name)
        for part in ui.glob('*.qml'):
            part.write_text(part.read_text().replace('@LIBEXECDIR@', str(ROOT/'linux/libexec')).replace('@DATADIR@', str(ROOT/'linux/share')))
        calls = folder/'calls.jsonl'; missing = folder/'missing-app'
        code = '''#!/usr/bin/python3
import json,os,sys,time
with open(LOG, 'a') as output: output.write(json.dumps(dict(app=sys.argv[1],pid=os.getpid()))+'\\n')
time.sleep(120)
'''.replace('LOG', repr(str(calls)))
        helper = folder/'app'; helper.write_text(code); helper.chmod(0o700)
        apps = data/'applications'; apps.mkdir()
        for kind in ('slow','other','missing'):
            command = str(missing if kind == 'missing' else helper) + ' ' + kind
            (apps/('monet-launch-ui-'+kind+'.desktop')).write_text('[Desktop Entry]\nType=Application\nName=AAA launch '+kind+
                '\nExec='+command+'\nIcon=application-x-executable\nStartupNotify=true\n')
        subprocess.run(['kbuildsycoca6','--noincremental'], env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        main = ui/'main.qml'; source = main.read_text()
        source = source.replace('        id: page\n', '        id: page\n        Rectangle { anchors.fill: parent; z: -1; color: Kirigami.Theme.backgroundColor; radius: 16 }\n')
        injection = '''
    property int fixturePhase: 0
    property bool fixturePendingSaved: false
    function fixtureFind(item, name) {
        if (!item) return null;
        if (item.name === name) return item;
        for (const child of item.children || []) {
            const found = fixtureFind(child, name);
            if (found) return found;
        }
        return null;
    }
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            root.expanded = true;
            const page = root.fullRepresentationItem;
            if (!page) return;
            page.everything = true;
            const slow = fixtureFind(page, "AAA launch slow");
            const other = fixtureFind(page, "AAA launch other");
            const missing = fixtureFind(page, "AAA launch missing");
            if (!slow || !other || !missing) return;
            if (fixturePhase === 0 && appLauncher.nativeReady) {
                slow.activated(); fixturePhase = 1;
            } else if (fixturePhase === 1 && slow.launching) {
                for (let i=0;i<5;i++) slow.activated();
                other.activated(); fixturePhase = 2;
            } else if (fixturePhase === 2 && slow.launching && other.launching) {
                console.log("LAUNCH_MENU_PENDING", JSON.stringify(appLauncher.states));
                fixturePhase = 20;
                page.grabToImage(result => { result.saveToFile(@PENDING@); root.fixturePendingSaved = true; });
            } else if (fixturePhase === 20 && fixturePendingSaved) {
                missing.activated(); fixturePhase = 3;
            } else if (fixturePhase === 3 && appLauncher.states["monet-launch-ui-missing.desktop"]?.state === "failed") {
                console.log("LAUNCH_MENU_FAILED", JSON.stringify(appLauncher.states));
                page.grabToImage(result => result.saveToFile(@FAILED@));
                fixturePhase = 4;
            } else if (fixturePhase === 4 && appLauncher.states["monet-launch-ui-missing.desktop"]?.state === "starting"
                    && appLauncher.states["monet-launch-ui-missing.desktop"].spawned) {
                console.log("LAUNCH_MENU_RETRIED", JSON.stringify(appLauncher.states)); fixturePhase = 5;
            } else if (fixturePhase === 5 && appLauncher.states["monet-launch-ui-missing.desktop"]?.state === "unconfirmed") {
                const retry = fixtureFindRetry(page);
                if (retry) { retry.clicked(); fixturePhase = 6; }
            } else if (fixturePhase === 6 && appLauncher.states["monet-launch-ui-missing.desktop"]?.state === "starting") {
                console.log("LAUNCH_MENU_BUTTON_RETRIED", JSON.stringify(appLauncher.states)); fixturePhase = 7;
            }
        }
    }
    function fixtureFindRetry(item) {
        if (!item) return null;
        if (item.text === "Retry" && typeof item.clicked === "function") return item;
        for (const child of item.children || []) {
            const found = fixtureFindRetry(child);
            if (found) return found;
        }
        return null;
    }
'''.replace('@PENDING@', json.dumps(str(folder/'pending.png'))).replace('@FAILED@', json.dumps(str(folder/'failed.png')))
        main.write_text(source[:source.rfind('}')]+injection+'}\n')
        notifications = folder/'notifications.jsonl'
        server = None; widget = None
        with (folder/'server.log').open('w') as server_log, (folder/'widget.log').open('w') as widget_log:
            try:
                server = subprocess.Popen([sys.executable, __file__, '--notifications', str(notifications)], env=env,
                    stdout=subprocess.PIPE, stderr=server_log, text=True)
                assert select.select([server.stdout], [], [], 5)[0] and server.stdout.readline().strip() == 'READY'
                widget = subprocess.Popen(['plasmawindowed','org.monet.menu'], env=env, stdout=widget_log, stderr=widget_log)

                def until(predicate, seconds=10):
                    deadline = time.monotonic()+seconds
                    while time.monotonic() < deadline:
                        if predicate(): return
                        assert widget.poll() is None, (folder/'widget.log').read_text()
                        time.sleep(.05)
                    raise AssertionError((folder/'widget.log').read_text())

                def launched(): return [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
                until(lambda: notifications.exists() and (folder/'failed.png').exists())
                self_calls = launched()
                assert sum(c['app']=='slow' for c in self_calls) == 1, self_calls
                assert sum(c['app']=='other' for c in self_calls) == 1, self_calls
                # A real monet-quick request reaches this same pending launch.
                subprocess.run([sys.executable,str(ROOT/'linux/libexec/monet-quick'),'launch','monet-launch-ui-slow.desktop'.encode().hex()],
                               env=env, check=True, timeout=5)
                time.sleep(.2); assert len(launched()) == 2, launched()
                missing.write_text(code); missing.chmod(0o700)
                notice = json.loads(notifications.read_text().splitlines()[-1])
                actions = dict(zip(notice['actions'][::2], notice['actions'][1::2]))
                retry = next(key for key,value in actions.items() if value == 'Retry')
                proxy = dbus.SessionBus().get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications')
                proxy.TriggerAction(dbus.UInt32(notice['id']),retry,dbus_interface='org.monet.NotificationFixture')
                until(lambda: any(c['app']=='missing' for c in launched()) and 'LAUNCH_MENU_RETRIED' in (folder/'widget.log').read_text())
                assert sum(c['app']=='missing' for c in launched()) == 1, launched()
                recovered = next(c for c in launched() if c['app']=='missing')
                fd = os.pidfd_open(recovered['pid'])
                try: signal.pidfd_send_signal(fd, signal.SIGTERM)
                finally: os.close(fd)
                until(lambda: sum(c['app']=='missing' for c in launched()) == 2 and 'LAUNCH_MENU_BUTTON_RETRIED' in (folder/'widget.log').read_text())
                log = (folder/'widget.log').read_text()
                assert not any(error in log for error in ('ReferenceError:', 'TypeError:', 'is not a type', 'Unable to assign', 'Cannot assign to non-existent property')), log
                for filename in ('pending.png','failed.png'):
                    image = QImage(str(folder/filename)); assert image.width() >= 400 and image.height() >= 300, image.size()
                print(json.dumps(dict(actualKickerModels=True, pendingFeedback=True, repeatedClicks=1,
                                      simultaneousApps=2, helperSharesPending=True, repairedNotificationRetry=True, menuButtonRetry=True)))
            finally:
                if widget is not None: stop(widget)
                if server is not None: stop(server); server.stdout.close()
                for call in launched() if calls.exists() else []:
                    try:
                        fd = os.pidfd_open(call['pid'])
                        try:
                            command = Path('/proc/'+str(call['pid'])+'/cmdline').read_bytes()
                            if str(folder).encode() in command: signal.pidfd_send_signal(fd, signal.SIGTERM)
                        finally: os.close(fd)
                    except (ProcessLookupError, FileNotFoundError): pass
                if os.environ.get('MONET_LAUNCHER_CAPTURE'):
                    destination = Path(os.environ['MONET_LAUNCHER_CAPTURE'])/'menu'; destination.mkdir(parents=True, exist_ok=True)
                    for filename in ('widget.log','server.log','pending.png','failed.png','notifications.jsonl','calls.jsonl'):
                        if (folder/filename).exists(): shutil.copy2(folder/filename, destination/filename)


if __name__ == '__main__':
    if sys.argv[1:] and sys.argv[1] == '--notifications': notification_server(sys.argv[2])
    else: main()
