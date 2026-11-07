#!/usr/bin/python3
"""Load account-only native previews while their validated runtime still matches.

Installation performs package, ABI and complete bundle validation. At each
process start, check immutable runtime file identities and loaded payload hashes
without launching package-manager helpers. An OS update falls back to system code.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

MANIFEST = Path(__file__).with_name('native-preview.json')
_prepared = False
_dock_prepared = False


def identity(path):
    info = Path(path).stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def valid(component):
    try:
        runtime, files = component['runtime'], component['files']
        return (bool(runtime) and bool(files)
                and all(identity(path) == expected for path, expected in runtime.items())
                and all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
                        for path, expected in files.items()))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def read():
    try:
        data = json.loads(MANIFEST.read_text())
        if data.get('schema') == 1 and isinstance(data.get('components'), dict):
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return {'schema': 1, 'components': {}}


def prepend(name, paths, managed=()):
    previous = [p for p in os.environ.get(name, '').split(os.pathsep) if p not in managed]
    values = list(dict.fromkeys(str(p) for p in [*paths, *previous] if p))
    if values:
        os.environ[name] = os.pathsep.join(values)
    else:
        os.environ.pop(name, None)


def prepare(include_dock=False):
    global _prepared, _dock_prepared
    if _prepared and (not include_dock or _dock_prepared):
        return
    data = read()
    qml, plugins = [], []
    managed_qml, managed_plugins, managed_libraries = [], [], []
    for name, component in data['components'].items():
        if not isinstance(component, dict):
            continue
        if component.get('qml'): managed_qml.append(component['qml'])
        if component.get('plugins'): managed_plugins.append(component['plugins'])
        if component.get('libraries'): managed_libraries.append(component['libraries'])
        needed = component.get('qml') or include_dock and name == 'dock' and component.get('plugins')
        if needed and valid(component):
            if component.get('qml'):
                qml.append(component['qml'])
            if component.get('plugins'):
                plugins.append(component['plugins'])
    # Each module has its own import root, so a valid module never exposes a
    # second, mismatched native module to the QML loader.
    prepend('QML_IMPORT_PATH', qml, managed_qml)
    prepend('QML2_IMPORT_PATH', qml, managed_qml)
    prepend('QT_PLUGIN_PATH', plugins, managed_plugins)
    # A child of an older preview Files process can inherit its private library
    # directory. Remove it before either a guarded launch or system fallback.
    prepend('LD_LIBRARY_PATH', [], managed_libraries)
    if data.get('bin'):
        prepend('PATH', [data['bin']])
    _prepared = True
    _dock_prepared = include_dock


def launch(name, fallback, arguments):
    prepare()
    data = read()
    component = data['components'].get(name, {})
    if valid(component):
        if component.get('plugins'):
            prepend('QT_PLUGIN_PATH', [component['plugins']])
        if component.get('libraries'):
            prepend('LD_LIBRARY_PATH', [component['libraries']])
        os.execv(component['executable'], [name, *arguments])
    os.execv(fallback, [name, *arguments])


if __name__ == '__main__':
    prepare(include_dock=True)
    os.execv('/usr/bin/plasmashell', ['plasmashell', '--no-respawn'])
