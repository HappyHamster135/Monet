#!/usr/bin/python3
"""Keep Task Manager's Graphics column paired with its image's Qt/KDE process runtime."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = 'ksysguard_plugin_monetgraphics.so'
FILES = (PLUGIN, 'source.tar.xz', 'README.md')
FIXED = ('libQt6Core.so.6', 'libKF6CoreAddons.so.6', 'libKF6I18n.so.6')


def libraries(directory=None):
    """The libraries the plugin is built against: Qt's and KDE's, and KDE's process library by
    whichever major version this runtime has (libprocesscore.so.N)."""
    directory = directory or libdir()
    found = sorted(p.name for p in directory.glob('libprocesscore.so.*') if re.fullmatch(r'libprocesscore\.so\.\d+', p.name))
    if len(found) != 1:
        raise ValueError('No single KDE process library in this runtime')
    return (*FIXED, found[0])


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packages(names):
    return sorted(run('rpm', '-q', '--qf', '%{NEVRA}\n', *names).splitlines())


def libdir():
    path = run('rpm', '--eval', '%{_libdir}')
    if path not in ('/usr/lib', '/usr/lib64'):
        raise ValueError('Unsupported graphics column library directory')
    return Path(path)


def owners(paths):
    names = set()
    for path in paths:
        names.update(run('rpm', '-qf', '--qf', '%{NAME}.%{ARCH}\n', str(Path(path).resolve())).splitlines())
    return names


def linked_paths(path):
    output = run('ldd', str(path))
    if 'not found' in output or 'undefined symbol' in output:
        raise ValueError('Incomplete graphics column runtime')
    return set(re.findall(r'(?:=>\s+|^\s*)(/\S+)', output, re.M))


def capture():
    directory = libdir()
    originals = {str((directory / name).resolve()) for name in libraries(directory)}
    paths = set(originals)
    for path in originals:
        paths.update(linked_paths(path))
    names = sorted(owners(paths))
    return dict(schema=1, path=str(directory / 'qt6/plugins/ksysguard/process'),
                originals={p: digest(p) for p in sorted(originals)}, package_names=names, packages=packages(names))


def verify(manifest):
    directory = libdir()
    expected = {str((directory / name).resolve()) for name in libraries(directory)}
    originals = manifest.get('originals')
    names = manifest.get('package_names')
    if (manifest.get('schema') != 1 or manifest.get('path') != str(directory / 'qt6/plugins/ksysguard/process')
            or not isinstance(originals, dict) or set(originals) != expected
            or any(not isinstance(v, str) or not re.fullmatch('[a-f0-9]{64}', v) for v in originals.values())):
        raise ValueError('Invalid graphics column runtime manifest')
    if (not isinstance(names, list) or not 1 <= len(names) <= 512
            or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', n) for n in names)):
        raise ValueError('Invalid graphics column runtime package list')
    if packages(names) != manifest.get('packages') or any(digest(p) != value for p, value in originals.items()):
        raise ValueError('Graphics column runtime changed: rebuild for this image')


def compatible(folder, manifest):
    plugin = folder / PLUGIN
    dynamic = run('readelf', '-d', str(plugin))
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise ValueError('Graphics column contains a build-time library path')
    needed = set(re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic))
    if not set(libraries()).issubset(needed):
        raise ValueError('Graphics column is missing its native dependencies')
    # Check relocation errors too, then require every linked library to belong
    # to the runtime captured before development packages were installed.
    relocated = run('ldd', '-r', str(plugin))
    if 'undefined symbol' in relocated or 'not found' in relocated:
        raise ValueError('Graphics column has unresolved dependencies')
    if not owners(linked_paths(plugin)).issubset(set(manifest['package_names'])):
        raise ValueError('Graphics column gained an uncaptured runtime dependency')


def atomic_copy(source, target, mode):
    fd, temporary = tempfile.mkstemp(prefix='.monet-graphics-', dir=target.parent)
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
        raise ValueError('Damaged graphics column bundle')
    compatible(folder, manifest)
    docs = Path('/usr/share/doc/monet-graphics')
    docs.mkdir(parents=True, exist_ok=True)
    for name in ('runtime.json', 'source.tar.xz', 'README.md'):
        atomic_copy(folder / name, docs / name, 0o644)
    destination = Path(manifest['path']); destination.mkdir(parents=True, exist_ok=True)
    atomic_copy(folder / PLUGIN, destination / PLUGIN, 0o755)


if __name__ == '__main__':
    command, path = sys.argv[1:]; path = Path(path)
    if command == 'capture': path.write_text(json.dumps(capture(), indent=2) + '\n')
    elif command == 'verify': verify(json.loads(path.read_text()))
    elif command == 'seal': seal(path)
    elif command == 'install': install(path)
    else: raise SystemExit('Unknown graphics column bundle command')
