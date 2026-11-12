"""Build a fully validated account installation plan for Monet native previews."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    info = Path(path).stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def bootstrap(source):
    """Keep docstrings and future imports before the native environment hook."""
    text = source.decode(); tree = ast.parse(text); after = 1 if text.startswith('#!') else 0
    for index, node in enumerate(tree.body):
        if ((index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
             and isinstance(node.value.value, str))
                or isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            after = node.end_lineno
        else:
            break
    lines = text.splitlines(keepends=True)
    lines[after:after] = ['import monet_native_preview\nmonet_native_preview.prepare()\n']
    return ''.join(lines).encode()


def checked(folder, module, names):
    manifest = json.loads((folder / 'runtime.json').read_text())
    module.verify(manifest)
    if set(manifest.get('files', {})) != set(names):
        raise ValueError('Incomplete native preview bundle: ' + folder.name)
    for name in names:
        if digest(folder / name) != manifest['files'][name]:
            raise ValueError('Damaged native preview bundle: ' + str(folder / name))
    return manifest


def extend(p, files, bundles):
    planned = {}
    components = {}
    native = p.PRIVATE / 'native'
    bindir = Path.home() / '.local/bin'

    def add(target, data, mode=0o644):
        planned[target] = (data, mode)

    def record(name, loaded, originals, extra_binaries=(), **options):
        paths = {str(Path(path).resolve()) for path in originals}
        for source in [*(source for source, _ in loaded), *extra_binaries]:
            with source.open('rb') as stream:
                if stream.read(4) != b'\x7fELF':
                    continue
            linked = subprocess.check_output(['ldd', str(source)], text=True)
            if 'not found' in linked:
                raise ValueError('Incomplete native preview dependencies: ' + name)
            paths.update(str(Path(path).resolve()) for path in
                         re.findall(r'(?:=>\s+|^\s*)(/\S+)', linked, re.M))
        components[name] = dict(runtime={path: identity(path) for path in sorted(paths)},
                                files={str(target): digest(source) for source, target in loaded}, **options)

    for name in ('activity', 'launcher'):
        folder = bundles / name
        module = load(p.ROOT / 'image' / name / 'bundle.py', 'preview_' + name)
        manifest = checked(folder, module, module.FILES)
        module.compatible(folder, manifest)
        destination = native / name
        qml = destination / 'qml'
        target = qml / 'org/monet' / name
        for filename in module.FILES:
            output = target / filename if filename in (module.PLUGIN, 'qmldir') else destination / filename
            add(output, (folder / filename).read_bytes(), 0o755 if filename == module.PLUGIN else 0o644)
        add(destination / 'runtime.json', (folder / 'runtime.json').read_bytes())
        add(destination / 'bundle.py', (p.ROOT / 'image' / name / 'bundle.py').read_bytes())
        record(name, [(folder / module.PLUGIN, target / module.PLUGIN), (folder / 'qmldir', target / 'qmldir')],
               manifest['originals'], qml=str(qml))
        if name == 'launcher':
            add(p.DATA / 'knotifications6/monet-launcher.notifyrc', (folder / 'monet-launcher.notifyrc').read_bytes())

    folder = bundles / 'dock'
    module = load(p.ROOT / 'image/dock/bundle.py', 'preview_dock')
    manifest = json.loads((folder / 'runtime.json').read_text())
    checked(folder, module, (*module.plugin_names(manifest), 'source.tar.xz'))
    plugins = module.verified_binaries(folder)
    destination = native / 'dock'
    loaded = []
    for source in plugins:
        target = destination / 'plugins/plasma/applets' / source.name
        add(target, source.read_bytes(), 0o755); loaded.append((source, target))
    for filename in ('runtime.json', 'source.tar.xz', 'README.md'):
        add(destination / filename, (folder / filename).read_bytes())
    record('dock', loaded, manifest['originals'], plugins=str(destination / 'plugins'))

    folder = bundles / 'session'
    if folder.exists():
        module = load(p.ROOT / 'image/session/bundle.py', 'preview_session')
        binaries = module.verified_binaries(folder)
        for filename in ('runtime.json', 'source.tar.xz', 'README.md'):
            add(native / 'logout' / filename, (folder / filename).read_bytes())
        for name, original, service_name in (
            ('logout', module.GREETER, 'org.kde.LogoutPrompt'),
            ('shutdown', module.SHUTDOWN, 'org.kde.Shutdown'),
        ):
            binary = binaries.get(original)
            if binary is None:
                continue
            target = native / name / binary.name
            add(target, binary.read_bytes(), 0o755)
            record(name, [(binary, target)], [original], executable=str(target))
            launcher = bindir / f'monet-{name}'
            wrapper = ('#!/usr/bin/python3\nimport sys\nsys.path.insert(0, ' + repr(str(p.HELPERS)) + ')\n'
                       'from monet_native_preview import launch\n'
                       f'launch({name!r}, {str(original)!r}, sys.argv[1:])\n')
            add(launcher, wrapper.encode(), 0o755)
            service = Path(f'dbus-1/services/{service_name}.service')
            source = p.DATA / service if (p.DATA / service).exists() else Path('/usr/share') / service
            text = re.sub(r'^Exec=.*$', 'Exec=' + str(launcher), source.read_text(), flags=re.M)
            add(p.DATA / service, text.encode())

    for name, folder_name, image_name in (('dolphin', 'files', 'files-recovery'), ('ark', 'archives', 'archive-recovery')):
        folder = bundles / folder_name
        module = load(p.ROOT / 'image' / image_name / 'bundle.py', 'preview_' + name)
        manifest = json.loads((folder / 'runtime.json').read_text())
        checked(folder, module, module.payload_names(manifest) if name == 'ark' else
                [Path(target['path']).name for target in manifest['targets']] + ['source.tar.xz'])
        destination = native / name
        loaded = []
        originals = manifest['originals'] if name == 'ark' else {r['path']: r['original_sha256'] for r in manifest['targets']}
        if name == 'ark':
            module.compatible(folder / name)
            plugins = module.plugin_paths(manifest)
            for filename, original in plugins.items():
                module.compatible(folder / filename, original)
            replacements = [name, *plugins]
        else:
            replacements = [Path(r['path']).name for r in manifest['targets']]
            for original in manifest['targets']:
                module.compatible(original['path'], folder / Path(original['path']).name)
        for filename in replacements:
            source, target = folder / filename, destination / filename
            if name == 'ark' and filename != name:
                target = destination / 'plugins/kerfuffle' / filename
            add(target, source.read_bytes(), 0o755); loaded.append((source, target))
            if filename.startswith('lib'):
                dynamic = subprocess.check_output(['readelf', '-d', str(source)], text=True)
                soname = re.search(r'\(SONAME\).*?\[([^]]+)\]', dynamic).group(1)
                if soname != filename:
                    add(destination / soname, target)
        for filename in ('runtime.json', 'source.tar.xz', 'README.md'):
            add(destination / filename, (folder / filename).read_bytes())
        options = {'executable': str(destination / name)}
        if name == 'dolphin': options['libraries'] = str(destination)
        if name == 'ark' and plugins:
            options.update(plugins=str(destination / 'plugins'), extra_binaries=[Path('/usr/bin/rpm')])
        record(name, loaded, originals, **options)
        wrapper = ('#!/usr/bin/python3\nimport sys\nsys.path.insert(0, ' + repr(str(p.HELPERS)) + ')\n'
                   'from monet_native_preview import launch\nlaunch(' + repr(name) + ', ' + repr('/usr/bin/' + name) + ', sys.argv[1:])\n')
        add(bindir / name, wrapper.encode(), 0o755)
        desktop_name = 'org.kde.' + name + '.desktop'
        desktop = p.DATA / 'applications' / desktop_name
        source = desktop if desktop.exists() else Path('/usr/share/applications') / desktop_name
        lines = source.read_text().splitlines()
        for i, line in enumerate(lines):
            if re.match(r'Exec=(?:/usr/bin/)?' + name + r'(?: |$)', line):
                command, space, arguments = line[5:].partition(' ')
                lines[i] = 'Exec=' + str(bindir / name) + space + arguments
        add(desktop, ('\n'.join(lines) + '\n').encode())
        if name == 'ark':
            # Open uses the guarded native browser. Leave the default archive
            # entry's extraction command intact when it does not invoke Ark.
            for relative in ('applications/monet-archive.desktop', 'kio/servicemenus/monet-archive-open.desktop'):
                target = p.DATA / relative
                data, mode = files[target]
                text = re.sub(r'^Exec=ark(?= )', 'Exec=' + str(bindir / 'ark'), data.decode(), flags=re.M)
                add(target, text.encode(), mode)
    service = Path('/usr/share/dbus-1/services/org.kde.dolphin.FileManager1.service')
    target = p.DATA / 'dbus-1/services' / service.name
    source = target if target.exists() else service
    add(target, source.read_text().replace('/usr/bin/dolphin', str(bindir / 'dolphin')).encode())
    service = Path('/usr/lib/systemd/user/plasma-dolphin.service')
    target = p.CONFIG / 'systemd/user' / service.name
    source = target if target.exists() else service
    add(target, source.read_text().replace('/usr/bin/dolphin', str(bindir / 'dolphin')).encode())
    add(p.HELPERS / 'monet_native_preview.py', (p.ROOT / 'tools/native-preview-runtime.py').read_bytes(), 0o755)
    add(p.HELPERS / 'native-preview.json', (json.dumps(dict(schema=1, components=components, bin=str(bindir)), indent=2) + '\n').encode(), 0o600)
    add(p.CONFIG / 'systemd/user/plasma-plasmashell.service.d/monet-native.conf',
        ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 "' + str(p.HELPERS / 'monet_native_preview.py') + '"\n').encode())
    for name in ('monet-settings', 'monet-store', 'monet-games', 'monet-files-tools', 'monet-file-jobs'):
        target = p.HELPERS / name
        data, mode = files[target]
        add(target, bootstrap(data), mode)
    # No partial plan escapes if any component fails verification above.
    files.update(planned)
