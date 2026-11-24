"""Exercise the actual editor and first-launch reset through native accessibility."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        children = []
        try:
            home, data = Path(env['HOME']), Path(env['XDG_DATA_HOME'])
            share = home/'share'; helpers = home/'libexec'; helpers.mkdir()
            env.update(DISPLAY=':92', QT_QPA_PLATFORM='xcb', QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1',
                       QT_FORCE_STDERR_LOGGING='1', LANG='C.UTF-8', LANGUAGE='en', XDG_DATA_DIRS=str(share)+':/usr/local/share:/usr/share')
            for name in ('plasma-systemmonitor','ksysguard/sensorfaces'):
                shutil.copytree(ROOT/'linux/share'/name, share/name)
            for source, destination in (('/usr/bin/plasma-systemmonitor', helpers/'plasma-systemmonitor'),
                                        ('/usr/lib64/libPlasmaSystemMonitorPage.so', helpers/'libPlasmaSystemMonitorPage.so')):
                shutil.copyfile(source, destination); destination.chmod(0o755)
            source = (ROOT/'linux/libexec/monet-quick').read_text().replace('@DATADIR@',str(ROOT/'linux/share')).replace('@LIBEXECDIR@',str(helpers))
            helper = helpers/'monet-quick'; helper.write_text(source); helper.chmod(0o755)
            profile = data/'plasma-systemmonitor'; profile.mkdir()
            (profile/'my-old.page').write_text('old customized page')
            config = Path(env['XDG_CONFIG_HOME'])/'systemmonitorrc'
            config.write_text('[General]\npageOrder=my-old.page\nstartPage=my-old.page\n')
            def start(argv, name):
                with (output/name).open('w') as stream:
                    child = subprocess.Popen(argv, env=env, stdout=stream, stderr=stream, start_new_session=True)
                children.append(child); return child
            start(['Xvfb',':92','-screen','0','1280x900x24'], 'display.log')
            start(['/usr/libexec/at-spi-bus-launcher','--launch-immediately'], 'accessibility.log')
            # The private bus has no systemd user manager to activate the registry.
            start(['/usr/libexec/at-spi2-registryd'], 'registry.log')
            app = start([str(helpers/'plasma-systemmonitor')], 'app.log')
            code = r'''
import json,time,pyatspi,subprocess
from pathlib import Path
root=pyatspi.Registry.getDesktop(0)
def nodes(n,depth=0):
    yield n
    if depth<25:
        for child in n:
            if child is not None: yield from nodes(child,depth+1)
def find(name,role=None):
    for node in nodes(root):
        if node.name==name and (not role or node.getRoleName()==role) and node.getState().contains(pyatspi.STATE_SHOWING): return node
def wait(check,description):
    end=time.monotonic()+15
    while time.monotonic()<end:
        value=check()
        if value: return value
        time.sleep(.05)
    raise AssertionError(description+'\n'+str([(n.name,n.getRoleName()) for n in nodes(root) if n.name]))
def press(name,role=None):
    node=wait(lambda:find(name,role),'Missing '+name)
    actions=node.queryAction()
    names=[actions.getName(i) for i in range(actions.nActions)]
    print('PRESS',name,names,flush=True)
    index=next((i for i,n in enumerate(names) if n.lower() in ('press','click')),None)
    if index is not None: assert actions.doAction(index), (name,names)
    else:
        bounds=node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        subprocess.run(['xdotool','mousemove',str(bounds.x+bounds.width//2),str(bounds.y+bounds.height//2),'click','1'],check=True)
    time.sleep(.3)
def has_graphics_header():
    expected = ['CPU', 'Memory', 'Graphics', 'Download']
    rows = {}
    for node in nodes(root):
        if node.name in expected and node.getRoleName() == 'label' and node.getState().contains(pyatspi.STATE_SHOWING):
            bounds = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
            rows.setdefault(bounds.y, []).append((bounds.x, node.name))
    return any([name for _, name in sorted(row)] == expected for row in rows.values())

wait(lambda:find('Applications','list item'),'Applications page missing')
assert not find('Graphics','list item'), 'Unexpected duplicate sidebar entry'
for page in ('Applications', 'Processes'):
    press(page,'list item')
    wait(has_graphics_header, page+' is missing Graphics beside Memory in the table header')
press('Performance','list item')
if not find('Edit Page','button'): press('More Actions','push button menu')
press('Edit Page')
wait(lambda:find('Add row','button'),'Editor help actions are missing')
press('Configure chart','button')
press('Chart preset','combo box')
press('CPU workload')
press('Save Changes','button')
print('NATIVE_EDITOR_OK',flush=True)
'''
            result = subprocess.run([sys.executable,'-c',code], env=env, capture_output=True,text=True,timeout=65)
            (output/'interaction.log').write_text(result.stdout+result.stderr)
            assert result.returncode==0, result.stdout+result.stderr+(output/'app.log').read_text()[-4000:]
            backup = data/'monet/task-manager-backups/0.9.8-8'
            assert (backup/'complete.json').exists(), 'Native first launch did not run the reset'
            assert (backup/'pages/my-old.page').read_text()=='old customized page'
            page = profile/'monet-performance.page'
            assert 'cpu/all/usage' in page.read_text(), page.read_text()
            before = page.read_bytes()
            stop(app); children.remove(app)
            app = start([str(helpers/'plasma-systemmonitor')], 'restart.log')
            import time
            time.sleep(1)
            assert app.poll() is None and page.read_bytes()==before, 'Restart discarded the new chart'
            for name in ('app.log','restart.log'):
                text=(output/name).read_text()
                assert not any(message in text for message in ('TypeError:','ReferenceError:','Error creating component:','Unable to assign')),text
            (output/'result.json').write_text(json.dumps(dict(passed=True, nativeEditor=True, nativeFirstLaunchReset=True,
                graphicsColumnsLoaded=True, presetSaved=True, restartPreservedCustomization=True, hostProfileChanged=False),indent=2)+'\n')
        finally:
            for process in reversed(children): stop(process)


if __name__ == '__main__': run(Path(sys.argv[1]))
