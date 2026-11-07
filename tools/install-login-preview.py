#!/usr/bin/python3
"""Plan/install a root-owned, reversible greeter preview without restarting login.

The desktop account cannot write the separate plasmalogin account's startup
configuration. Default is read-only; --apply requires administrator execution.
"""
import argparse,datetime,hashlib,importlib.util,json,os,pwd,re,shutil,stat,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/var/lib/monet/login-preview')

def digest(path):
    if path.is_symlink():return 'link:'+str(path.readlink())
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def plan(bundle):
    spec=importlib.util.spec_from_file_location('login_preview_bundle',ROOT/'image/login/bundle.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    manifest=json.loads((bundle/'runtime.json').read_text())
    if any(b.digest(bundle/name)!=manifest[key] for name,key in [('plasma-login-greeter','binary'),('source.tar.xz','source')]):
        raise ValueError('Damaged login preview bundle')
    # The laptop's base greeter already has Monet's earlier visual patch. It
    # shares the distribution ABI/packages with the SDK; pin that actual base
    # for runtime fallback rather than pretending it is the stock binary.
    manifest=dict(manifest,build_original=manifest['original'],original=b.digest('/usr/libexec/plasma-login-greeter'))
    b.verify(manifest);b.compatible(bundle/'plasma-login-greeter')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    prefix=BASE/stamp;files={}
    def add(path,data,mode=0o644):files[path]=(data,mode)
    for name in ['plasma-login-greeter','source.tar.xz','README.md']:
        add(prefix/name,(bundle/name).read_bytes(),0o755 if name=='plasma-login-greeter' else 0o644)
    add(prefix/'build-runtime.json',(json.dumps(manifest,indent=2)+'\n').encode())
    add(prefix/'monet_native_preview.py',(ROOT/'tools/native-preview-runtime.py').read_bytes())
    paths={Path('/usr/libexec/plasma-login-greeter').resolve()}
    linked=subprocess.check_output(['ldd',str(bundle/'plasma-login-greeter')],text=True)
    if 'not found' in linked:raise ValueError('Missing login runtime')
    paths.update(Path(p).resolve() for p in re.findall(r'(?:=>\s+|^\s*)(/\S+)',linked,re.M))
    def identity(p):
        s=p.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    component=dict(runtime={str(p):identity(p) for p in sorted(paths)},files={str(prefix/'plasma-login-greeter'):manifest['binary']},executable=str(prefix/'plasma-login-greeter'))
    add(prefix/'native-preview.json',(json.dumps(dict(schema=1,components=dict(login=component)),indent=2)+'\n').encode())
    add(prefix/'start.py',b'from monet_native_preview import launch\nimport sys\nlaunch("login", "/usr/libexec/plasma-login-greeter", sys.argv[1:])\n')
    add(prefix/'monet-login-brightness',(ROOT/'linux/libexec/monet-login-brightness').read_bytes(),0o755)
    add(Path('/etc/systemd/user/plasma-login.service.d/monet-preview.conf'),('[Service]\nExecStart=\nExecStart=/usr/bin/python3 '+str(prefix/'start.py')+'\n').encode())
    for relative in ['plasma-login-wayland.target.d/monet-brightness.conf']:
        add(Path('/etc/systemd/user')/relative,(ROOT/'linux/systemd/user'/relative).read_bytes())
    unit=(ROOT/'linux/systemd/monet-login-brightness.service').read_text().replace('@LIBEXECDIR@',str(prefix))
    add(Path('/etc/systemd/system/monet-login-brightness.service'),unit.encode())
    add(Path('/etc/systemd/system/display-manager.service.wants/monet-login-brightness.service'),Path('/etc/systemd/system/monet-login-brightness.service'))
    return prefix,files

def apply(bundle):
    if os.geteuid()!=0:raise PermissionError('Administrator access is required for the separate login account')
    prefix,files=plan(bundle);prefix.mkdir(parents=True,mode=0o755)
    backups=prefix/'backups';backups.mkdir(mode=0o700)
    receipt=prefix/'receipt.json';rows=[]
    def before(path):
        row=dict(path=str(path),before=digest(path),backup=str(len(rows)))
        if row['before'] is not None:
            s=path.lstat();row.update(mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid)
            shutil.copy2(path,backups/row['backup'],follow_symlinks=False)
        rows.append(row);return row
    def save():
        receipt.write_text(json.dumps(dict(files=rows,prefix=str(prefix)),indent=2)+'\n');receipt.chmod(0o600)
    for path,(data,mode) in files.items():
        row=before(path);save();path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.monet-login-tmp')
        if temporary.exists() or temporary.is_symlink():raise FileExistsError(temporary)
        if isinstance(data,Path):temporary.symlink_to(data)
        else:temporary.write_bytes(data);temporary.chmod(mode)
        temporary.replace(path);row['after']=digest(path);save()
    account=pwd.getpwnam('plasmalogin')
    for name in ['kwinoutputconfig.json','powerdevilrc']:before(Path(account.pw_dir)/'.config'/name)
    save()
    subprocess.run([str(prefix/'monet-login-brightness')],check=True)
    for row in rows:
        if 'after' not in row:row['after']=digest(Path(row['path']))
    save()
    subprocess.run(['systemctl','daemon-reload'],check=True)
    # Do not restart display-manager or the greeter's user manager: that would
    # interrupt the user's live desktop. These files activate at the next login.
    return dict(receipt=str(receipt),installed_files=len(files),greeter_config_seeded=True,restart_performed=False)

def restore(receipt):
    if os.geteuid()!=0:raise PermissionError('Administrator access is required')
    receipt=receipt.resolve(strict=True)
    if not receipt.is_relative_to(BASE) or receipt.stat().st_uid!=0:raise ValueError('Use the root-owned preview receipt')
    data=json.loads(receipt.read_text());backups=receipt.parent/'backups';kept=[];restored=[]
    allowed={str(p) for p in [Path('/etc/systemd/user/plasma-login.service.d/monet-preview.conf'),Path('/etc/systemd/user/monet-login-power.service'),Path('/etc/systemd/user/plasma-login-wayland.target.d/monet-brightness.conf'),Path('/etc/systemd/system/monet-login-brightness.service'),Path('/etc/systemd/system/display-manager.service.wants/monet-login-brightness.service')]}
    account=pwd.getpwnam('plasmalogin');allowed.update(str(Path(account.pw_dir)/'.config'/n) for n in ['kwinoutputconfig.json','powerdevilrc'])
    for row in reversed(data['files']):
        path=Path(row['path'])
        if not path.is_relative_to(receipt.parent) and str(path) not in allowed:raise ValueError('Unexpected receipt target')
        if digest(path)!=row.get('after'):kept.append(str(path));continue
        if row['before'] is None:path.unlink(missing_ok=True)
        else:
            path.unlink(missing_ok=True);shutil.copy2(backups/row['backup'],path,follow_symlinks=False)
            if not path.is_symlink():os.chown(path,row['uid'],row['gid']);path.chmod(row['mode'])
        restored.append(str(path))
    subprocess.run(['systemctl','daemon-reload'],check=True)
    return dict(restored=restored,preserved_edits=kept,restart_performed=False)

def repair_power(receipt):
    """Repair the first local preview's duplicate bus owner, keeping its undo."""
    if os.geteuid()!=0:raise PermissionError('Administrator access is required')
    receipt=receipt.resolve(strict=True)
    if not receipt.is_relative_to(BASE) or receipt.stat().st_uid!=0:raise ValueError('Use the root-owned preview receipt')
    data=json.loads(receipt.read_text())
    legacy=Path('/etc/systemd/user/monet-login-power.service')
    dropin=Path('/etc/systemd/user/plasma-login-wayland.target.d/monet-brightness.conf')
    rows={row['path']:row for row in data['files']}
    replacement=(ROOT/'linux/systemd/user/plasma-login-wayland.target.d/monet-brightness.conf').read_bytes()
    if replacement!=b'[Unit]\nWants=plasma-powerdevil.service\n':raise ValueError('Unexpected login dependency')
    for path in (legacy,dropin):
        if str(path) not in rows or digest(path)!=rows[str(path)]['after']:raise ValueError('Preview changed since installation: '+str(path))
    # The original before/backup stays intact, so a full preview restore still
    # returns the pre-install configuration rather than the faulty intermediate.
    legacy.unlink(missing_ok=True);rows[str(legacy)]['after']=None
    temporary=dropin.with_name(dropin.name+'.monet-login-tmp')
    if temporary.exists():raise FileExistsError(temporary)
    temporary.write_bytes(replacement);temporary.chmod(0o644);temporary.replace(dropin)
    rows[str(dropin)]['after']=digest(dropin)
    data['power_unit_repair']='Reuse the native plasma-powerdevil.service; no second D-Bus owner'
    receipt.write_text(json.dumps(data,indent=2)+'\n');receipt.chmod(0o600)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    return dict(receipt=str(receipt),power_unit_repaired=True,restart_performed=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--restore',type=Path)
    parser.add_argument('--repair-power',type=Path,help='Repair the initial local preview while retaining its undo receipt')
    args=parser.parse_args()
    if args.repair_power:result=repair_power(args.repair_power)
    elif args.restore:result=restore(args.restore)
    else:
        if args.bundle is None:parser.error('--bundle is required')
        if args.apply:result=apply(args.bundle.resolve())
        else:
            prefix,files=plan(args.bundle.resolve());result=dict(prefix=str(prefix),targets=[str(p) for p in files],administrator_required=True,restart_performed=False)
    print(json.dumps(result,indent=2))
