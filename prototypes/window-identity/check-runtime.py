from pathlib import Path
import subprocess,hashlib,json,sys
root=Path(sys.argv[1]).resolve()
container=sys.argv[2]
def run(*args):return subprocess.check_output(args,text=True).strip()
names=[name+'.x86_64' for name in ('kwin-libs','qt6-qtbase','qt6-qtbase-gui','libwayland-client','libwayland-server')]
vm=run('rpm','-q','--qf','%{NEVRA}\n',*names)
built=run('podman','exec',container,'rpm','-q','--qf','%{NEVRA}\n',*names)
assert vm==built,(vm,built)
paths=list({Path(p).resolve() for p in run('rpm','-ql','kwin-libs').splitlines() if p.startswith('/usr/lib64/libkwin.so.')})
assert len(paths)==1,paths
path=Path(paths[0]);digest=hashlib.sha256(path.read_bytes()).hexdigest()
assert digest==run('podman','exec',container,'sha256sum',str(path)).split()[0]
runtime_hashes={}
for path in [Path('/usr/bin/kwin_wayland'),*(Path('/usr/lib64')/name for name in (
        'libQt6Core.so.6','libQt6Gui.so.6','libQt6DBus.so.6','libwayland-client.so.0','libwayland-server.so.0'))]:
 path=path.resolve();value=hashlib.sha256(path.read_bytes()).hexdigest()
 assert value==run('podman','exec',container,'sha256sum',str(path)).split()[0]
 runtime_hashes[str(path)]=value
for file in ('monet_window_identity.so','identity_fixture','collision_fixture'):
 linked=run('ldd','-r',str(root/'build'/file))
 assert 'not found' not in linked and 'undefined symbol' not in linked,linked
proof={'matching_runtime':vm.splitlines(),'kwin_library_sha256':digest,
       'runtime_binary_sha256':runtime_hashes,
       'plugin_sha256':hashlib.sha256((root/'build/monet_window_identity.so').read_bytes()).hexdigest()}
(root/'runtime-verified.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
