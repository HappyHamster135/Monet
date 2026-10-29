#!/usr/bin/python3
"""Guard the paired Files executable/library and preserve their corresponding source."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packages(names):
    try:
        return sorted(run('rpm','-q','--qf','%{NEVRA}\n',*names).splitlines())
    except subprocess.CalledProcessError as error:
        raise ValueError('Files runtime changed: a required package is missing') from error


def capture():
    linked=run('ldd','/usr/bin/dolphin')
    if 'libwayland-client.so.0 => /' not in linked:
        raise ValueError('Files window identity requires the existing Wayland client runtime')
    paths=re.findall(r'libdolphinprivate\.so\.\S+ => (/\S+)',linked)
    if len(paths)!=1 or 'not found' in linked:
        raise ValueError('Expected the installed Files library and complete dependencies')
    library=Path(paths[0]).resolve()
    targets=['/usr/bin/dolphin',str(library)]
    names=set()
    for target in targets:
        linked=run('ldd',target)
        if 'not found' in linked: raise ValueError('Files runtime has missing dependencies')
        for path in {target,*re.findall(r'(?:=>\s+|^\s*)(/\S+)',linked,re.M)}:
            names.update(run('rpm','-qf','--qf','%{NAME}.%{ARCH}\n',str(Path(path).resolve())).splitlines())
    return {'schema':1,'targets':[{'path':p,'original_sha256':digest(p)} for p in targets],
            'package_names':sorted(names),'packages':packages(sorted(names))}


def verify(manifest):
    targets=manifest.get('targets')
    if (manifest.get('schema')!=1 or not isinstance(targets,list) or len(targets)!=2
            or any(not isinstance(t,dict) for t in targets)
            or targets[0].get('path')!='/usr/bin/dolphin'
            or not re.fullmatch(r'/usr/lib(?:64)?/libdolphinprivate\.so\.\d+(?:\.\d+)*',targets[1].get('path',''))):
        raise ValueError('Invalid Files destinations')
    names=manifest.get('package_names')
    if (not isinstance(names,list) or not 1<=len(names)<=512
            or any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*',n) for n in names)
            or packages(names)!=manifest['packages']):
        raise ValueError('Files runtime changed: rebuild for this image')
    for target in targets:
        if digest(target['path'])!=target['original_sha256']:
            raise ValueError('Base Files binary changed: rebuild for this image')


def compatible(original,replacement):
    def needed(path):
        dynamic=run('readelf','-d',str(path))
        if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
            raise ValueError('Files binary contains a build-time library path')
        return set(re.findall(r'\((?:NEEDED|SONAME)\).*\[([^\]]+)\]',dynamic))
    dependencies=needed(original)
    replacement_dependencies=needed(replacement)
    # Window identity directly uses the already captured transitive Wayland runtime.
    allowed=dependencies | {'libwayland-client.so.0'} if Path(original).name=='dolphin' else dependencies
    if not dependencies or replacement_dependencies not in (dependencies, allowed):
        raise ValueError('Files build features/dependencies differ from the runtime')
    if Path(original).name!='dolphin':
        def symbols(path):
            return {p[0]:p[1] for line in run('nm','--dynamic','--defined-only','--format=posix',str(path)).splitlines()
                    if len(p:=line.split())>=2}
        # Retain native functions, vtables and Qt metadata; template data may change with headers.
        exports={name for name,kind in symbols(original).items() if kind in {'T','V'} or 'staticMetaObject' in name}
        if not exports or not exports<=symbols(replacement).keys():
            raise ValueError('Files library lost exported symbols')


def atomic_copy(source,target,mode):
    fd,temporary=tempfile.mkstemp(prefix='.monet-',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as output,source.open('rb') as original:
            shutil.copyfileobj(original,output)
            output.flush(); os.fchmod(output.fileno(),mode); os.fsync(output.fileno())
        os.replace(temporary,target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def seal(bundle):
    manifest=json.loads((bundle/'runtime.json').read_text())
    verify(manifest)
    names=[Path(t['path']).name for t in manifest['targets']]
    for target,name in zip(manifest['targets'],names): compatible(target['path'],bundle/name)
    manifest['files']={n:digest(bundle/n) for n in (*names,'source.tar.xz')}
    (bundle/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')


def install(bundle):
    manifest=json.loads((bundle/'runtime.json').read_text())
    verify(manifest)
    names=[Path(t['path']).name for t in manifest['targets']]
    for name in (*names,'source.tar.xz'):
        if digest(bundle/name)!=manifest['files'][name]: raise ValueError('Damaged Files bundle: '+name)
    for target,name in zip(manifest['targets'],names):
        compatible(target['path'],bundle/name)
        if 'not found' in run('ldd',str(bundle/name)): raise ValueError('Files replacement has missing dependencies')
    for target,name in zip(manifest['targets'],names): atomic_copy(bundle/name,Path(target['path']),0o755)
    docs=Path('/usr/share/doc/monet-files-recovery'); docs.mkdir(parents=True,exist_ok=True)
    for name in ('runtime.json','source.tar.xz','README.md'): atomic_copy(bundle/name,docs/name,0o644)


if __name__=='__main__':
    command,path=sys.argv[1],Path(sys.argv[2])
    if command=='capture': path.write_text(json.dumps(capture(),indent=2)+'\n')
    elif command=='verify': verify(json.loads(path.read_text()))
    elif command=='seal': seal(path)
    elif command=='install': install(path)
    else: raise ValueError('Expected capture, verify, seal or install')
