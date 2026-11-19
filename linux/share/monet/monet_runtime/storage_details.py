"""On-demand cleanup candidates; no personal file is deleted by a scan."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def unused_refs():
    try:
        import gi
        gi.require_version('Flatpak', '1.0')
        from gi.repository import Flatpak
        installations = [('user', Flatpak.Installation.new_user(None))]
        for installation in Flatpak.get_system_installations(None):
            ident = installation.get_id()
            installations.append(('system' if not ident or ident == 'default' else ident, installation))
        rows = []
        for name, installation in installations:
            for ref in installation.list_unused_refs(None, None):
                if ref.get_kind() != Flatpak.RefKind.RUNTIME: continue
                rows.append(dict(installation=name, ref=ref.format_ref(), name=ref.get_name(), size=ref.get_installed_size()))
        return rows
    except (ImportError, ValueError, RuntimeError):
        return None
    except Exception:
        # GError is not available without GI. Unknown is distinct from no candidates.
        return None


def token(rows):
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda row: (row['installation'], row['ref'])), sort_keys=True).encode()).hexdigest()


def scan(home, downloads, cache, now=None):
    home, downloads, cache = map(Path, (home, downloads, cache))
    rows = unused_refs()
    old = []
    now = time.time() if now is None else now
    try:
        with os.scandir(downloads) as entries:
            for index, entry in enumerate(entries):
                if index >= 5000: break
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False): continue
                stat = entry.stat(follow_symlinks=False)
                if now - stat.st_mtime >= 90 * 86400:
                    old.append(dict(name=entry.name, size=stat.st_size, url=Path(entry.path).absolute().as_uri()))
    except OSError:
        pass
    cache_size = None
    try:
        if cache.is_dir():
            out = subprocess.run(['nice', '-n', '15', 'du', '-sx', '-B1', '--', str(cache)],
                                 capture_output=True, text=True, timeout=4)
            if out.returncode == 0: cache_size = int(out.stdout.split()[0])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        pass
    return dict(ok=True, home=home.absolute().as_uri(), downloads=downloads.absolute().as_uri(), cache=cache.absolute().as_uri(),
                cacheSize=cache_size, oldDownloads=sorted(old, key=lambda item: -item['size'])[:30],
                unused=rows if rows is not None else [], unusedKnown=rows is not None,
                token=token(rows) if rows is not None else '')


def cleanup(expected, run):
    rows = unused_refs()
    if rows is None: return dict(ok=False, problem='unavailable')
    if token(rows) != expected: return dict(ok=False, problem='changed')
    for installation in sorted({row['installation'] for row in rows}):
        scope = '--' + installation if installation in ('user', 'system') else '--installation=' + installation
        # Let Flatpak re-evaluate usage within its own transaction. Never force
        # removal of a reviewed ref that an app started using since the scan.
        if run('flatpak', 'uninstall', scope, '--unused', '--noninteractive', '-y', timeout=600) is None:
            return dict(ok=False, problem='cleanup')
    after = unused_refs()
    remaining = {(row['installation'], row['ref']) for row in after} if after is not None else None
    return dict(ok=remaining is not None and not any((row['installation'], row['ref']) in remaining for row in rows))
