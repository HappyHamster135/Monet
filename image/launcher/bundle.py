#!/usr/bin/python3
"""Keep the native launcher module paired with its image's Qt/KWayland runtime."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = 'libmonetlauncherplugin.so'
FILES = (PLUGIN, 'qmldir', 'monet-launcher.notifyrc', 'source.tar.xz', 'README.md')
LIBRARIES = ('libQt6Core.so.6', 'libQt6DBus.so.6', 'libQt6Qml.so.6', 'libQt6Quick.so.6',
             'libKF6KIOGui.so.6', 'libKF6KIOCore.so.6', 'libKF6Service.so.6', 'libKF6WindowSystem.so.6',
             'libKF6Notifications.so.6', 'libKF6I18n.so.6', 'libtaskmanager.so.6', 'libPlasmaActivities.so.7')


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packages(names):
    return sorted(run('rpm', '-q', '--qf', '%{NEVRA}\n', *names).splitlines())


def libdir():
    path = run('rpm', '--eval', '%{_libdir}')
    if path not in ('/usr/lib', '/usr/lib64'):
        raise ValueError('Unsupported launcher module library directory')
    return Path(path)


def owners(paths):
    names = set()
    for path in paths:
        names.update(run('rpm', '-qf', '--qf', '%{NAME}.%{ARCH}\n', str(Path(path).resolve())).splitlines())
    return names


def linked_paths(path):
    output = run('ldd', str(path))
    if 'not found' in output or 'undefined symbol' in output:
        raise ValueError('Incomplete launcher module runtime')
    return set(re.findall(r'(?:=>\s+|^\s*)(/\S+)', output, re.M))


def capture():
    directory = libdir()
    originals = {str((directory / name).resolve()) for name in LIBRARIES}
    paths = set(originals)
    for path in originals:
        paths.update(linked_paths(path))
    names = sorted(owners(paths))
    return dict(schema=1, path=str(directory / 'qt6/qml/org/monet/launcher'),
                originals={p: digest(p) for p in sorted(originals)}, package_names=names, packages=packages(names))


def verify(manifest):
    directory = libdir()
    expected = {str((directory / name).resolve()) for name in LIBRARIES}
    originals = manifest.get('originals')
    names = manifest.get('package_names')
    if (manifest.get('schema') != 1 or manifest.get('path') != str(directory / 'qt6/qml/org/monet/launcher')
            or not isinstance(originals, dict) or set(originals) != expected
            or any(not isinstance(v, str) or not re.fullmatch('[a-f0-9]{64}', v) for v in originals.values())):
        raise ValueError('Invalid launcher module runtime manifest')
    if (not isinstance(names, list) or not 1 <= len(names) <= 512
            or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', n) for n in names)):
        raise ValueError('Invalid launcher runtime package list')
    if packages(names) != manifest.get('packages') or any(digest(p) != value for p, value in originals.items()):
        raise ValueError('Launcher runtime changed: rebuild for this image')


def compatible(folder, manifest):
    plugin = folder / PLUGIN
    dynamic = run('readelf', '-d', str(plugin))
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise ValueError('Launcher module contains a build-time library path')
    needed = set(re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic))
    if not set(LIBRARIES).issubset(needed):
        raise ValueError('Launcher module is missing its native dependencies')
    # Check relocation errors too, then require every linked library to belong
    # to the runtime captured before development packages were installed.
    relocated = run('ldd', '-r', str(plugin))
    if 'undefined symbol' in relocated or 'not found' in relocated:
        raise ValueError('Launcher module has unresolved dependencies')
    if not owners(linked_paths(plugin)).issubset(set(manifest['package_names'])):
        raise ValueError('Launcher module gained an uncaptured runtime dependency')
    if (folder / 'qmldir').read_text() != 'module org.monet.launcher\nplugin monetlauncherplugin\n':
        raise ValueError('Invalid launcher QML module metadata')


def atomic_copy(source, target, mode):
    fd, temporary = tempfile.mkstemp(prefix='.monet-launcher-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as original:
            shutil.copyfileobj(original, output)
            output.flush(); os.fchmod(output.fileno(), mode); os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def seal(folder):
    manifest = json.loads((folder / 'runtime.json').read_text())
    verify(manifest); compatible(folder, manifest)
    manifest['files'] = {name: digest(folder / name) for name in FILES}
    (folder / 'runtime.json').write_text(json.dumps(manifest, indent=2) + '\n')


def install(folder):
    manifest = json.loads((folder / 'runtime.json').read_text())
    verify(manifest)
    if (not isinstance(manifest.get('files'), dict) or set(manifest['files']) != set(FILES)
            or any(digest(folder / name) != expected for name, expected in manifest['files'].items())):
        raise ValueError('Damaged launcher module bundle')
    compatible(folder, manifest)
    docs = Path('/usr/share/doc/monet-launcher')
    docs.mkdir(parents=True, exist_ok=True)
    for name in ('runtime.json', 'source.tar.xz', 'README.md'):
        atomic_copy(folder / name, docs / name, 0o644)
    notifications = Path('/usr/share/knotifications6'); notifications.mkdir(parents=True, exist_ok=True)
    atomic_copy(folder / 'monet-launcher.notifyrc', notifications / 'monet-launcher.notifyrc', 0o644)
    destination = Path(manifest['path']); destination.mkdir(parents=True, exist_ok=True)
    for name in (PLUGIN, 'qmldir'):
        atomic_copy(folder / name, destination / name, 0o755 if name == PLUGIN else 0o644)


if __name__ == '__main__':
    command, path = sys.argv[1:]; path = Path(path)
    if command == 'capture': path.write_text(json.dumps(capture(), indent=2) + '\n')
    elif command == 'verify': verify(json.loads(path.read_text()))
    elif command == 'seal': seal(path)
    elif command == 'install': install(path)
    else: raise SystemExit('Unknown launcher module bundle command')
