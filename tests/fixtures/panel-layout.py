#!/usr/bin/env python3
"""Move real Plasma applets on a private virtual Wayland desktop; never the host."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session
from tests.test_look import quick_helper

with private_session() as env:
    assert env['HOME'].startswith('/tmp/monet-tests-')
    aliases = {name: 'org.monet.fixture.'+name.rsplit('.',1)[1] for name in ('org.kde.plasma.icontasks', 'org.kde.plasma.systemtray', 'org.kde.plasma.marginsseparator', 'org.kde.plasma.trash')}
    def inert(script):
        for original, substitute in aliases.items(): script=script.replace(original,substitute)
        return script
    env.update(KWIN_COMPOSE="O2", LIBGL_ALWAYS_SOFTWARE="1", QT_FORCE_STDERR_LOGGING="1")
    processes = []
    logpath = Path(env['HOME']) / 'panel-fixture.log'
    log = logpath.open('w')
    def launch(args):
        process = subprocess.Popen(args, env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(process)
        return process
    def evaluate(script):
        assert compositor_process.poll() is None, 'Private compositor stopped'
        result = subprocess.run(['busctl', '--address='+env['DBUS_SESSION_BUS_ADDRESS'], '--json=short',
            'call', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', 's', inert(script)],
            env=env, capture_output=True, text=True, timeout=10)
        if result.returncode: raise RuntimeError(result.stderr)
        return json.loads(result.stdout)['data']
    def state(script):
        return json.loads(evaluate('print(JSON.stringify('+script+'))')[0])
    def ready():
        for _ in range(100):
            try:
                if state('screenCount') > 0: return
            except (RuntimeError, ValueError): pass
            time.sleep(.1)
        raise AssertionError('Private Plasma did not start')
    try:
        # Keep widget faces inert so no session services are started. KDE plugin
        # aliases avoid loading compiled applets. Real Plasma containments and
        # applet objects still exercise ownership, ordering and KConfig persistence.
        for name in ('menu','games','weather','quick','sound','clock','custom', 'org.kde.plasma.icontasks', 'org.kde.plasma.systemtray', 'org.kde.plasma.marginsseparator', 'org.kde.plasma.trash'):
            plugin=inert(name) if name.startswith('org.') else 'org.monet.'+name
            package=Path(env['XDG_DATA_HOME'])/'plasma/plasmoids'/plugin
            (package/'contents/ui').mkdir(parents=True)
            (package/'metadata.json').write_text(json.dumps({'KPackageStructure':'Plasma/Applet',
                'KPlugin':{'Id':plugin,'Name':name,'Version':'1.0','License':'MIT'},'X-Plasma-API-Minimum-Version':'6.0'}))
            (package/'contents/ui/main.qml').write_text('import QtQuick\nimport org.kde.plasma.plasmoid\nPlasmoidItem { preferredRepresentation: fullRepresentation; fullRepresentation: Rectangle { implicitWidth:32; implicitHeight:32; color: "red" } }\n')
        Path(env['XDG_CONFIG_HOME'],'kdeglobals').write_text('[KDE]\nLookAndFeelPackage=org.kde.breeze.desktop\n')
        # Fedora marks KWin with CAP_SYS_NICE. A cap-drop=ALL test container
        # correctly refuses to execute that file. A byte copy has no file
        # capabilities and needs none for this virtual, software-only display.
        compositor = Path(env['HOME']) / 'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'), compositor)
        compositor.chmod(0o700)
        compositor_process=launch([str(compositor),'--virtual','--width','1280','--height','800','--no-lockscreen',
                '--no-global-shortcuts','--no-kactivities','--socket','monet-panel-test'])
        for _ in range(100):
            if Path(env['XDG_RUNTIME_DIR'],'monet-panel-test').exists(): break
            time.sleep(.1)
        env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY='monet-panel-test')
        launch(['/usr/libexec/kactivitymanagerd'])
        shell=launch(['plasmashell','--no-respawn']); ready()
        time.sleep(1)
        evaluate('panels().forEach(p=>p.remove());')
        time.sleep(.5)
        for align, body in [
            ('left', "p.addWidget('org.monet.menu'); p.addWidget('org.monet.games');"),
            ('center', "var t=p.addWidget('org.kde.plasma.icontasks'); t.currentConfigGroup=['General']; t.writeConfig('launchers',['applications:org.kde.konsole.desktop']);"),
            ('right', "p.addWidget('org.monet.quick'); p.addWidget('org.monet.sound'); p.addWidget('org.kde.plasma.systemtray'); var extra=p.addWidget('org.monet.custom'); extra.currentConfigGroup=['General']; extra.writeConfig('preserved','yes');")]:
            ident=json.loads(evaluate("var p=new Panel; p.location='bottom'; p.screen=0; p.alignment="+json.dumps(align)+"; p.height=60; p.lengthMode='fit'; print(JSON.stringify(p.id));")[0])
            time.sleep(.5)
            evaluate('var p=panelById('+str(ident)+'); '+body)
        time.sleep(.5)
        selected=state('panels().find(p=>p.widgets("org.monet.quick").length).id')
        original=state('[].concat.apply([],panels().map(p=>p.widgets().map(w=>w.id)))')
        q=quick_helper()
        def snapshot():
            return state('panels().map(p=>({id:p.id,mode:p.lengthMode,widgets:p.widgets().map(w=>({id:w.id,type:w.type,index:w.index})).sort((a,b)=>a.index-b.index)}))')
        with patch.object(q,'DATADIR',str(ROOT/'linux/share')), patch.object(q,'busjson',side_effect=lambda *args:evaluate(args[-1])):
            for choice in ('one','three','one'):
                result=q.panel_layout(str(selected),choice)
                assert result.get('ok'), result
                time.sleep(.4)
                data=snapshot(); assert len(data)==(1 if choice=='one' else 3), data
                widgets=[w for p in data for w in p['widgets']]
                assert all(w['index'] >= 0 for w in widgets), data
                assert all(any(w['id']==ident for w in widgets) for ident in original), data
                assert len([w for w in widgets if w['type']=='org.monet.sound'])==1, data
                if choice=='one': assert data[0]['widgets'][0]['type']=='org.monet.menu', data
            task='panels()[0].widgets("org.kde.plasma.icontasks")[0]'
            assert json.loads(evaluate('var t='+task+'; t.currentConfigGroup=["General"]; print(JSON.stringify(t.readConfig("launchers",[])));')[0])==['applications:org.kde.konsole.desktop']
            assert json.loads(evaluate('var w=panels()[0].widgets("org.monet.custom")[0]; w.currentConfigGroup=["General"]; print(JSON.stringify(w.readConfig("preserved","")));')[0])=='yes'
            # KConfig saves on shutdown; verify the selected layout survives login.
            shell.terminate(); shell.wait(timeout=5)
            shell=launch(['plasmashell','--no-respawn']); ready(); time.sleep(.4)
            assert q.panel_layout(str(selected))['layout']=='one'
            data=snapshot(); assert len(data)==1, data
            assert all(any(w['id']==ident for w in data[0]['widgets']) for ident in original), data
            assert q.panel_layout(str(selected),'three')['ok']
        print('Native panel round trip, pins, widget identity and restart: passed')
    except Exception:
        log.flush(); print(logpath.read_text()[-8000:],file=sys.stderr); raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
        log.close()
