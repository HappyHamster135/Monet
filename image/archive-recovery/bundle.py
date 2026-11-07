#!/usr/bin/python3
"""Keep the Archives executable tied to its distribution libraries and sources."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

RPM_PLUGIN = 'kerfuffle_libarchive_readonly.so'


def payload_names(manifest):
    return ('ark', RPM_PLUGIN, 'source.tar.xz') if manifest['schema'] == 2 else ('ark', 'source.tar.xz')


def plugin_path(manifest):
    paths = [p for p in manifest['originals'] if p.endswith('/kerfuffle/' + RPM_PLUGIN)]
    if len(paths) != 1: raise ValueError('Missing native RPM plugin')
    return paths[0]


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packages(names):
    return sorted(run('rpm', '-q', '--qf', '%{NEVRA}\n', *names).splitlines())


def capture():
    # Include plugin dependencies as well as those linked by the executable.
    paths = {'/usr/bin/ark', '/usr/bin/rpm'}
    for path in run('rpm', '-ql', 'ark-libs').splitlines():
        if re.fullmatch(r'/usr/lib(?:64)?/(?:libkerfuffle\.so\.\d+(?:\.\d+)*|qt6/plugins/kerfuffle/kerfuffle_[a-z0-9_]+\.so)', path):
            paths.add(str(Path(path).resolve()))
    if len(paths) < 3: raise ValueError('Missing native Archives plugins')
    names = set()
    for path in paths:
        linked = run('ldd', path)
        if 'not found' in linked: raise ValueError('Incomplete Archives runtime')
        for dependency in {path, *re.findall(r'(?:=>\s+|^\s*)(/\S+)', linked, re.M)}:
            names.update(run('rpm', '-qf', '--qf', '%{NAME}.%{ARCH}\n', str(Path(dependency).resolve())).splitlines())
    return dict(schema=2, originals={p: digest(p) for p in sorted(paths)},
                package_names=sorted(names), packages=packages(sorted(names)))


def verify(manifest):
    originals = manifest.get('originals')
    names = manifest.get('package_names')
    if (manifest.get('schema') not in (1, 2) or not isinstance(originals, dict) or not 3 <= len(originals) <= 100
            or '/usr/bin/ark' not in originals
            or any(not isinstance(p, str) or not re.fullmatch(r'/usr/bin/ark|/usr/lib(?:64)?/(?:libkerfuffle\.so\.\d+(?:\.\d+)*|qt6/plugins/kerfuffle/kerfuffle_[a-z0-9_]+\.so)', p)
                   and not (manifest.get('schema') == 2 and p == '/usr/bin/rpm') for p in originals)
            or any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value) for value in originals.values())):
        raise ValueError('Invalid Archives runtime manifest')
    if manifest['schema'] == 2:
        plugin_path(manifest)
        if '/usr/bin/rpm' not in originals: raise ValueError('Missing RPM query runtime')
    if (not isinstance(names, list) or not 1 <= len(names) <= 512
            or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', n) for n in names)
            or packages(names) != manifest.get('packages')):
        raise ValueError('Archives runtime changed: rebuild for this image')
    if any(digest(path) != expected for path, expected in originals.items()):
        raise ValueError('Archives binaries changed: rebuild for this image')


def compatible(replacement, original='/usr/bin/ark'):
    def needed(path):
        output = run('readelf', '-d', str(path))
        if '(RPATH)' in output or '(RUNPATH)' in output:
            raise ValueError('Archives contains a build-time library path')
        return set(re.findall(r'\(NEEDED\).*\[([^\]]+)\]', output))
    required = needed(original)
    if not required or needed(replacement) != required or 'not found' in run('ldd', str(replacement)):
        raise ValueError('Archives build features differ from the installed runtime')


def atomic_copy(source, target, mode):
    fd, temporary = tempfile.mkstemp(prefix='.monet-archives-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as original:
            shutil.copyfileobj(original, output); output.flush()
            os.fchmod(output.fileno(), mode); os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def seal(folder):
    manifest = json.loads((folder / 'runtime.json').read_text())
    verify(manifest); compatible(folder / 'ark')
    if manifest['schema'] == 2: compatible(folder / RPM_PLUGIN, plugin_path(manifest))
    manifest['files'] = {name: digest(folder / name) for name in payload_names(manifest)}
    (folder / 'runtime.json').write_text(json.dumps(manifest, indent=2) + '\n')


def install(folder):
    manifest = json.loads((folder / 'runtime.json').read_text())
    verify(manifest)
    if (not isinstance(manifest.get('files'), dict) or set(manifest['files']) != set(payload_names(manifest))
            or any(digest(folder / name) != expected for name, expected in manifest['files'].items())):
        raise ValueError('Damaged Archives bundle')
    compatible(folder / 'ark')
    if manifest['schema'] == 2: compatible(folder / RPM_PLUGIN, plugin_path(manifest))
    docs = Path('/usr/share/doc/monet-archive-recovery'); docs.mkdir(parents=True, exist_ok=True)
    for name in ('runtime.json', 'source.tar.xz', 'README.md'):
        atomic_copy(folder / name, docs / name, 0o644)
    atomic_copy(folder / 'ark', Path('/usr/bin/ark'), 0o755)
    if manifest['schema'] == 2: atomic_copy(folder / RPM_PLUGIN, Path(plugin_path(manifest)), 0o755)


if __name__ == '__main__':
    command, path = sys.argv[1:]
    path = Path(path)
    if command == 'capture': path.write_text(json.dumps(capture(), indent=2) + '\n')
    elif command == 'verify': verify(json.loads(path.read_text()))
    elif command == 'seal': seal(path)
    elif command == 'install': install(path)
    else: raise SystemExit('Unknown Archives bundle command')
