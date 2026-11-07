"""Virtual desktop groups: one shallow, bounded scan; files never move."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import time


def desktop_dir():
    result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, timeout=3)
    path = Path(result.stdout.strip())
    if result.returncode or not path.is_absolute():
        return Path.home() / 'Desktop'
    return path


def group_name(name, folder):
    if folder: return 'Folders'
    suffix = Path(name).suffix.lower()
    if suffix in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.avif', '.heic', '.bmp', '.tiff'}: return 'Images'
    if suffix in {'.zip', '.gz', '.tgz', '.tar', '.bz2', '.xz', '.7z', '.rar', '.zst'}: return 'Archives'
    if suffix in {'.pdf', '.doc', '.docx', '.odt', '.txt', '.md', '.rtf', '.xls', '.xlsx', '.ods', '.ppt', '.pptx'}: return 'Documents'
    if suffix in {'.mp4', '.mkv', '.webm', '.mov', '.avi'}: return 'Videos'
    if suffix in {'.mp3', '.ogg', '.flac', '.wav', '.m4a', '.opus'}: return 'Music'
    if suffix in {'.appimage', '.exe', '.msi', '.deb', '.rpm', '.flatpakref', '.desktop'}: return 'Applications'
    return 'Other files'


def stacks(mode='type', folder=None, limit=10000, visible=200):
    folder = Path(folder) if folder is not None else desktop_dir()
    now = datetime.now().astimezone()
    groups = {}
    limited = False
    deadline = time.monotonic() + 1.5
    with os.scandir(folder) as entries:
        for count, entry in enumerate(entries):
            if count >= limit or time.monotonic() > deadline:
                limited = True; break
            if entry.name.startswith('.'):
                continue
            try:
                info = entry.stat(follow_symlinks=False)
                directory = entry.is_dir(follow_symlinks=False)
                if mode == 'date':
                    modified = datetime.fromtimestamp(info.st_mtime, now.tzinfo).date()
                    days = (now.date() - modified).days
                    group = 'Today' if days <= 0 else 'Yesterday' if days == 1 else 'Last 7 days' if days < 7 else 'Older'
                else:
                    group = group_name(entry.name, directory)
                group_items = groups.setdefault(group, {'name': group, 'count': 0, 'items': []})
                group_items['count'] += 1
                if len(group_items['items']) < visible:
                    path = folder / entry.name
                    group_items['items'].append(dict(name=entry.name, url=path.as_uri(),
                        path=str(path).encode().hex(), folder=directory))
            except OSError:
                continue
    for group in groups.values():
        group['items'].sort(key=lambda item: item['name'].casefold())
        limited = limited or group['count'] > len(group['items'])
    order = ('Today', 'Yesterday', 'Last 7 days', 'Older') if mode == 'date' else ('Folders', 'Images', 'Documents', 'Archives', 'Applications', 'Videos', 'Music', 'Other files')
    return dict(groups=[groups[key] for key in order if key in groups], limited=limited, folder=folder.as_uri())


def activate(which, desktop=None):
    file = 'stacks.js' if which.startswith('stacks-') else 'transfers.js'
    script = (Path(__file__).resolve().parent.parent / file).read_text()
    if which == 'stacks-disable': script = 'var forceOff = true;\n' + script
    if which == 'stacks-enable': script = 'var forceOn = true;\n' + script
    if which == 'stacks-reconcile': script = 'var reconcile = true;\n' + script
    if desktop is not None: script = 'var targetDesktop = ' + str(int(desktop)) + ';\n' + script
    subprocess.run(['busctl', '--user', 'call', 'org.kde.plasmashell', '/PlasmaShell',
        'org.kde.PlasmaShell', 'evaluateScript', 's', script], check=True, timeout=10)
