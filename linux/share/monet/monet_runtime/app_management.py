"""Review and uninstall user applications through their installation owner."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil

APP_ID = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}')


def portable_running(target, proc=Path('/proc')):
    target = Path(target).resolve()
    try:
        for folder in proc.iterdir():
            if not folder.name.isdigit(): continue
            try:
                if folder.stat().st_uid != os.getuid(): continue
                if Path(os.readlink(folder / 'exe')) == target: return True
                command = (folder / 'cmdline').read_bytes()[:8192].split(b'\0')
                if os.fsencode(target) in command[:4]: return True
            except OSError:
                continue
    except OSError:
        return True
    return False


def flatpak_installation(path, app, data_home, run):
    """Resolve the selected export, including named system installations."""
    installed = run('flatpak', 'list', '--app', '--columns=application,installation')
    if installed is None: raise ValueError('cannot verify app installation')
    choices = {line.split('\t', 1)[1].strip() for line in installed.splitlines()
               if '\t' in line and line.split('\t', 1)[0].strip() == app}
    if not choices: raise ValueError('application is no longer installed')
    if path.is_relative_to(data_home / 'flatpak') and 'user' in choices: return 'user'
    if path.is_relative_to(Path('/var/lib/flatpak')) and 'system' in choices: return 'system'
    if len(choices) == 1: return choices.pop()
    # A local alias is ambiguous if the app exists in more than one installation.
    raise ValueError('ambiguous application installation')


def review(path, entry, home, data_home, run=None):
    path, home, data_home = Path(path), Path(home), Path(data_home)
    result = dict(ok=True, name=entry.get('Name', path.stem), entry=str(path), kind='system',
                  eraseSupported=False, data=[], program='', message='')
    flatpak = entry.get('X-Flatpak')
    if flatpak and APP_ID.fullmatch(flatpak):
        installation = flatpak_installation(path, flatpak, data_home, run) if run else ('user' if path.is_relative_to(data_home / 'flatpak') else 'system')
        result.update(kind='flatpak', app=flatpak, installation=installation,
                      eraseSupported=True, data=[str(home / '.var/app' / flatpak)])
    elif path.parent == data_home / 'applications' and path.name.startswith('monet-local-'):
        try:
            command = shlex.split(entry.get('Exec', ''))
            if len(command) not in (3, 4) or Path(command[0]).name != 'monet-quick' or command[1] != 'native-run':
                raise ValueError('not a registered native application')
            target = Path(bytes.fromhex(command[2]).decode('utf-8'))
            options = bytes.fromhex(command[3]).decode('utf-8') if len(command) == 4 else ''
            # Added applications name their launcher by the full executable path.
            identity = str(target) + ('\0' + options if options else '')
            ident = 'monet-local-' + hashlib.sha256(identity.encode()).hexdigest()[:24] + '.desktop'
            if path.name != ident or not target.is_absolute() or not target.is_file() or target.is_symlink() \
                    or target.stat().st_uid != os.getuid():
                raise ValueError('not an owned program')
            with target.open('rb') as binary: header = binary.read(11)
            appimage = header[8:11] in (b'AI\x01', b'AI\x02')
            sidecars = [str(Path(str(target) + suffix)) for suffix in ('.home', '.config')
                        if appimage and Path(str(target) + suffix).exists()]
            stat = target.stat()
            result.update(kind='portable', program=str(target), eraseSupported=bool(sidecars), data=sidecars,
                          identity=[stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns])
        except (ValueError, OSError, IndexError, UnicodeError):
            result.update(kind='shortcut', message='external-program')
    elif 'wine' in entry.get('Exec', '').lower() or 'X-Monet-Windows-Programs' in entry.get('Categories', ''):
        result.update(kind='wine', message='native-uninstaller')
    elif 'X-Monet-Windows-Apps' in entry.get('Categories', ''):
        result.update(kind='windows', message='manage-in-windows')
    with path.open() as stream: text = stream.read(65537)
    if len(text) > 65536: raise ValueError('oversized application entry')
    digest = hashlib.sha256((text + json.dumps(result, sort_keys=True)).encode()).hexdigest()
    result['token'] = digest
    return result


def uninstall(plan, expected, erase, run):
    if plan.get('token') != expected or type(erase) is not bool:
        return dict(ok=False, problem='changed')
    if plan['kind'] == 'flatpak':
        app, installation = plan['app'], plan['installation']
        running = run('flatpak', 'ps', '--columns=application')
        if running is None:
            return dict(ok=False, problem='unavailable')
        if app in running.splitlines():
            return dict(ok=False, problem='running')
        scope = '--' + installation if installation in ('user','system') else '--installation=' + installation
        args = ['flatpak', 'uninstall', scope, '--noninteractive', '-y']
        if erase: args.append('--delete-data')
        if run(*args, app, timeout=600) is None:
            return dict(ok=False, problem='uninstall')
        installed = run('flatpak', 'list', scope, '--app', '--columns=application')
        if installed is None or app in installed.splitlines():
            return dict(ok=False, problem='unconfirmed')
        # Flatpak removes its export. Also remove the selected local alias, if any.
        entry = Path(plan['entry'])
        if '/flatpak/exports/' not in str(entry) and entry.is_file() and entry.stat().st_uid == os.getuid():
            entry.unlink()
        return dict(ok=True, removed=True)
    if plan['kind'] == 'portable':
        target = Path(plan['program'])
        if portable_running(target): return dict(ok=False, problem='running')
        stat = target.stat()
        if target.is_symlink() or stat.st_uid != os.getuid() \
                or plan.get('identity') != [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]:
            return dict(ok=False, problem='changed')
        # Only the reviewed program file and its portable data, never its parent folder.
        if not os.access(target.parent, os.W_OK): return dict(ok=False, problem='permission')
        if erase:
            for value in plan['data']:
                folder = Path(value)
                if folder.is_symlink(): folder.unlink()
                elif folder.is_dir(): shutil.rmtree(folder)
        target.unlink()
        Path(plan['entry']).unlink(missing_ok=True)
        return dict(ok=True, removed=True)
    return dict(ok=False, problem=plan.get('message') or 'system-component')
