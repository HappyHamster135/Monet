#!/usr/bin/env python3
"""Build/install guard for the native Task Manager executable and matching source."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def run(*args): return subprocess.check_output(args, text=True).strip()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def packages(names): return sorted(run('rpm','-q','--qf','%{NEVRA}\n',*names).splitlines())
def capture():
    binary=Path('/usr/bin/plasma-systemmonitor')
    linked=run('ldd',str(binary))
    if 'not found' in linked: raise ValueError('Task Manager runtime is incomplete')
    names=set()
    for path in {str(binary),*re.findall(r'(?:=>\s+|^\s*)(/\S+)',linked,re.M)}:
        names.update(run('rpm','-qf','--qf','%{NAME}.%{ARCH}\n',str(Path(path).resolve())).splitlines())
    return dict(original=digest(binary),originalPage=digest('/usr/lib64/libPlasmaSystemMonitorPage.so'),
                package_names=sorted(names),packages=packages(sorted(names)))
def verify(manifest):
    if packages(manifest['package_names'])!=manifest['packages'] or digest('/usr/bin/plasma-systemmonitor')!=manifest['original'] \
            or digest('/usr/lib64/libPlasmaSystemMonitorPage.so')!=manifest.get('originalPage'):
        raise ValueError('Task Manager runtime changed; rebuild this local preview')
def seal(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    manifest['binary']=digest(folder/'plasma-systemmonitor')
    manifest['source']=digest(folder/'source.tar.xz')
    manifest['page']=digest(folder/'libPlasmaSystemMonitorPage.so')
    (folder/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')
def verified_binary(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    if manifest['binary']!=digest(folder/'plasma-systemmonitor') or manifest['source']!=digest(folder/'source.tar.xz') \
            or manifest.get('page')!=digest(folder/'libPlasmaSystemMonitorPage.so'):
        raise ValueError('Task Manager bundle checksum mismatch')
    return folder/'plasma-systemmonitor'

if __name__=='__main__':
    command,path=sys.argv[1:];path=Path(path)
    if command=='capture': path.write_text(json.dumps(capture(),indent=2)+'\n')
    elif command=='verify': verify(json.loads(path.read_text()))
    elif command=='seal': seal(path)
    elif command=='install':
        import shutil
        shutil.copy2(verified_binary(path),'/usr/bin/plasma-systemmonitor')
        library = next(Path('/usr/lib64').glob('libPlasmaSystemMonitorPage.so'), None)
        if library is None: raise ValueError('Task Manager page runtime is missing')
        shutil.copy2(path/'libPlasmaSystemMonitorPage.so', library)
        target=Path('/usr/share/monet/task-manager');target.mkdir(parents=True,exist_ok=True)
        for name in ['source.tar.xz','runtime.json','README.md']: shutil.copy2(path/name,target/name)
    else: raise ValueError(command)
