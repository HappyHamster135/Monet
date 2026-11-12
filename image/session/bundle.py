#!/usr/bin/env python3
"""Build/install guard for the native session executables and matching source."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

GREETER = Path('/usr/libexec/ksmserver-logout-greeter')
SHUTDOWN = Path('/usr/bin/plasma-shutdown')


def run(*args): return subprocess.check_output(args, text=True).strip()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def packages(names): return sorted(run('rpm','-q','--qf','%{NEVRA}\n',*names).splitlines())
def window_library():
    for path in [Path('/usr/lib64/libtaskmanager.so.6'),Path('/usr/lib/libtaskmanager.so.6')]:
        if path.is_file():return path.resolve()
    raise ValueError('The native window model library is missing')
def capture():
    library=window_library()
    originals = (GREETER, SHUTDOWN, library)
    linked = '\n'.join(run('ldd', str(path)) for path in originals)
    if 'not found' in linked: raise ValueError('session transition runtime is incomplete')
    names=set()
    for path in {*originals, *re.findall(r'(?:=>\s+|^\s*)(/\S+)',linked,re.M)}:
        names.update(run('rpm','-qf','--qf','%{NAME}.%{ARCH}\n',str(Path(path).resolve())).splitlines())
    return dict(original=digest(GREETER), shutdown_original=digest(SHUTDOWN),
                package_names=sorted(names), packages=packages(sorted(names)))
def verify(manifest):
    names=manifest.get('package_names')
    if not isinstance(names,list) or not 1 <= len(names) <= 512 or any(
        not isinstance(n,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+~-]*',n) for n in names
    ): raise ValueError('Invalid greeter package names')
    if (packages(names) != manifest['packages'] or digest(GREETER) != manifest['original']
            or ('shutdown_original' in manifest and digest(SHUTDOWN) != manifest['shutdown_original'])):
        raise ValueError('session transition runtime changed; rebuild this image')
def compatible(binary, original=GREETER):
    def needed(path):
        dynamic=run('readelf','-d',str(path))
        if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic: raise ValueError(f'{path.name} contains a build search path')
        return set(re.findall(r'\(NEEDED\).*?\[([^]]+)\]',dynamic))
    # The sole additional direct dependency supplies unfiltered native window
    # metadata. capture() pins it and its complete linked package runtime too.
    extra = {'libtaskmanager.so.6'} if original == GREETER else set()
    if needed(binary) != needed(original) | extra:
        raise ValueError(f'{binary.name} linked libraries changed')
    linked=run('ldd','-r',str(binary))
    if 'not found' in linked or 'undefined symbol:' in linked:
        raise ValueError(f'{binary.name} has unresolved libraries or symbols')
def seal(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    if 'shutdown_original' not in manifest:
        raise ValueError('Missing original shutdown runtime checksum')
    for original, key in ((GREETER, 'binary'), (SHUTDOWN, 'shutdown_binary')):
        binary = folder / original.name
        compatible(binary, original)
        manifest[key] = digest(binary)
    manifest['source']=digest(folder/'source.tar.xz')
    (folder/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')
def verified_binaries(folder):
    manifest=json.loads((folder/'runtime.json').read_text());verify(manifest)
    if manifest['source'] != digest(folder / 'source.tar.xz'):
        raise ValueError('session source checksum mismatch')
    targets = {GREETER: 'binary'}
    if 'shutdown_original' in manifest:
        targets[SHUTDOWN] = 'shutdown_binary'
    verified = {}
    for original, key in targets.items():
        binary = folder / original.name
        if manifest[key] != digest(binary):
            raise ValueError(f'{binary.name} checksum mismatch')
        compatible(binary, original)
        verified[original] = binary
    return verified

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
    binaries = verified_binaries(folder)
    if SHUTDOWN not in binaries:
        raise ValueError('Missing verified shutdown executable')
    target=Path('/usr/share/monet/session');target.mkdir(parents=True,exist_ok=True)
    for name in ['source.tar.xz','runtime.json','README.md']: shutil.copy2(folder/name,target/name)
    for original, binary in binaries.items():
        atomic_copy(binary, original)

if __name__=='__main__':
    command,path=sys.argv[1:];path=Path(path)
    if command=='capture': path.write_text(json.dumps(capture(),indent=2)+'\n')
    elif command=='verify': verify(json.loads(path.read_text()))
    elif command=='seal': seal(path)
    elif command=='install': install(path)
    else: raise ValueError(command)
