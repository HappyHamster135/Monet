"""Load the actual Plasma applet with a fake helper in a private desktop profile."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        home = Path(env['HOME']); helpers = home / 'libexec'; helpers.mkdir()
        helper = helpers / 'monet-quick'
        helper.write_text('''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['MONET_QUICK_CALLS'],'a') as stream: stream.write(json.dumps(args)+'\\n')
info=dict(wifi=True,bluetooth=True,night=False,quiet=False,quietUntil=0,quietIndefinite=False,lanConnected=False,
          brightness=60,volume=50,light='auto',battery=72,plugged=False,charging=False,minutes=90)
result={}
if args and args[0]=='status': result=info
elif args==['outputs']: result=[]
elif args and args[0]=='quick-options':
    result={'ok':True}
    if args[1] in ('wifi-list','wifi-scan'): result.update(enabled=True,networks=[
        dict(name='Home',secure=True,known=True,active=True,signal=90),
        dict(name='Coffee shop',secure=True,known=False,active=False,signal=65)])
    elif args[1]=='bluetooth-list': result.update(enabled=True,devices=[dict(name='Headphones',address='AA:BB:CC:DD:EE:FF',connected=True)])
    elif args[1]=='night': result.update(enabled=False,strength=36)
if args==['listen']: sys.exit(0)
print(json.dumps(result))
''')
        helper.chmod(0o755)
        package = Path(env['XDG_DATA_HOME']) / 'plasma/plasmoids/org.monet.quick'
        shutil.copytree(ROOT / 'linux/share/plasma/plasmoids/org.monet.quick', package)
        ui = package / 'contents/ui'
        for common in (ROOT / 'linux/share/monet/widgets').glob('*.qml'):
            shutil.copyfile(common, ui / common.name)
        for source in ui.glob('*.qml'):
            source.write_text(source.read_text().replace('@LIBEXECDIR@', str(helpers)).replace('@BINDIR@', str(helpers))
                              .replace('@DATADIR@', str(ROOT / 'linux/share')))
        calls = output / 'calls.jsonl'
        env.update(MONET_QUICK_CALLS=str(calls), QT_FORCE_STDERR_LOGGING='1')
        result = subprocess.run([os.environ['MONET_QUICK_FIXTURE'], str(output)], env=env,
                                capture_output=True, text=True, timeout=40)
        (output / 'native.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        recorded = [json.loads(line) for line in calls.read_text().splitlines()]
        assert not any(args and args[0] in ('open', 'wifi', 'bluetooth', 'night', 'quiet') for args in recorded), recorded
        (output / 'result.json').write_text(json.dumps(dict(ok=True, calls=recorded, scope='Actual Plasma applet/full representation with fake helper; no host session or wireless changes'), indent=2)+'\n')


if __name__ == '__main__': run(Path(sys.argv[1]))
