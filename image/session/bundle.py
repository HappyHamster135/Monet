#!/usr/bin/env python3
"""Build/install guard for the native session transition executable and matching source."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args): return subprocess.check_output(args, text=True).strip()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def packages(names): return sorted(run('rpm','-q','--qf','%{NEVRA}\n',*names).splitlines())
def window_library():
    for path in [Path('/usr/lib64/libtaskmanager.so.6'),Path('/usr/lib/libtaskmanager.so.6')]:
        if path.is_file():return path.resolve()
    raise ValueError('The native window model library is missing')
def capture():
    binary=Path('/usr/libexec/ksmserver-logout-greeter')
    library=window_library()
    linked=run('ldd',str(binary))+'\n'+run('ldd',str(library))
    if 'not found' in linked: raise ValueError('session transition runtime is incomplete')
    names=set()
    for path in {str(binary),str(library),*re.findall(r'(?:=>\s+|^\s*)(/\S+)',linked,re.M)}:
        names.update(run('rpm','-qf','--qf','%{NAME}.%{ARCH}\n',str(Path(path).resolve())).splitlines())
    return dict(original=digest(binary),package_names=sorted(names),packages=packages(sorted(names)))
def verify(manifest):
    names=manifest.get('package_names')
    if not isinstance(names,list) or not 1 <= len(names) <= 512 or any(
        not isinstance(n,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+~-]*',n) for n in names
    ): raise ValueError('Invalid greeter package names')
    if packages(manifest['package_names'])!=manifest['packages'] or digest('/usr/libexec/ksmserver-logout-greeter')!=manifest['original']:
        raise ValueError('session transition runtime changed; rebuild this image')
def compatible(binary):
    def needed(path):
        dynamic=run('readelf','-d',str(path))
        if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic: raise ValueError('Greeter contains a build search path')
        return set(re.findall(r'\(NEEDED\).*?\[([^]]+)\]',dynamic))
    # The sole additional direct dependency supplies unfiltered native window
    # metadata. capture() pins it and its complete linked package runtime too.
    if needed(binary)!=needed('/usr/libexec/ksmserver-logout-greeter') | {'libtaskmanager.so.6'}:
        raise ValueError('Greeter linked libraries changed')
    linked=run('ldd','-r',str(binary))
    if 'not found' in linked or 'undefined symbol:' in linked:
        raise ValueError('Greeter has unresolved libraries or symbols')
def seal(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    compatible(folder/'ksmserver-logout-greeter')
    manifest['binary']=digest(folder/'ksmserver-logout-greeter')
    manifest['source']=digest(folder/'source.tar.xz')
    (folder/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')
def verified_binary(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    if manifest['binary']!=digest(folder/'ksmserver-logout-greeter') or manifest['source']!=digest(folder/'source.tar.xz'):
        raise ValueError('session transition bundle checksum mismatch')
    compatible(folder/'ksmserver-logout-greeter')
    return folder/'ksmserver-logout-greeter'

def atomic_copy(source,target):
    target=Path(target)
    fd,name=tempfile.mkstemp(prefix='.'+target.name,dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as dest, open(source,'rb') as src:
            shutil.copyfileobj(src,dest)
            dest.flush();os.fsync(dest.fileno())
        os.chmod(name,0o755)
        os.replace(name,target)
    finally:
        Path(name).unlink(missing_ok=True)

def install(folder):
    binary=verified_binary(folder)
    target=Path('/usr/share/monet/session');target.mkdir(parents=True,exist_ok=True)
    for name in ['source.tar.xz','runtime.json','README.md']: shutil.copy2(folder/name,target/name)
    atomic_copy(binary,'/usr/libexec/ksmserver-logout-greeter')

if __name__=='__main__':
    command,path=sys.argv[1:];path=Path(path)
    if command=='capture': path.write_text(json.dumps(capture(),indent=2)+'\n')
    elif command=='verify': verify(json.loads(path.read_text()))
    elif command=='seal': seal(path)
    elif command=='install': install(path)
    else: raise ValueError(command)
