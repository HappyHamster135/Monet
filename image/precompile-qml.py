#!/usr/bin/python3
"""Generate Qt-validated bytecode in a disposable image, after all QML patches.

The source stays installed. Qt rejects incompatible or damaged bytecode and
compiles normally. Atomic checkouts give /usr files an Epoch timestamp; generate
source and bytecode together at that timestamp after every installed-source patch.
Adjacent build-time bytecode must be regenerated whenever its source changes.
Development tools are mounted from the matching native builder, never shipped.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess


PANEL_CONFIG = Path('plasma/shells/org.kde.plasma.desktop/contents/configuration')


def sources(share):
    roots = [share / 'monet']
    for kind in ('plasmoids', 'wallpapers', 'look-and-feel'):
        roots.extend(sorted((share / 'plasma' / kind).glob('org.monet.*')))
    roots.extend(sorted((share / 'kwin/scripts').glob('monet-*')))
    roots.extend(sorted((share / 'kwin/tabbox').glob('monet-*')))
    roots.extend(sorted((share / 'ksysguard/sensorfaces').glob('org.monet.*')))
    files = {path for root in roots for path in root.rglob('*.qml')
             if path.is_file() and not path.is_symlink()}
    panel = share / PANEL_CONFIG
    for page in ('explorer/MonetWidgetExplorer.qml', 'views/MonetDesktopEditMode.qml'):
        path = panel.parent / page
        if path.is_file():
            files.add(path)
    if (panel / 'MonetPanelConfiguration.qml').is_file():
        files.update(panel / name for name in ('MonetPanelConfiguration.qml', 'PanelConfiguration.qml',
                                                'monet-editor-entry/PanelConfiguration.qml') if (panel / name).is_file())
    # Only JavaScript imported by QML belongs to the Qt cache. Monet also ships
    # Node/browser code and dependencies, whose JavaScript uses other runtimes.
    pending = list(files)
    while pending:
        source = pending.pop()
        for name in re.findall(r'(?m)^\s*\.?import\s+"([^"\n]+\.(?:js|mjs))"', source.read_text()):
            imported = (source.parent / name).resolve()
            if (imported.is_relative_to(share.resolve()) and imported.is_file()
                    and imported not in files):
                files.add(imported)
                pending.append(imported)
    return sorted(files)


def compile_sources(share, compiler, extra_sources=()):
    from PySide6.QtCore import qVersion
    version = subprocess.run([str(compiler), '--version'], check=True,
                             capture_output=True, text=True).stdout.strip()
    if version != 'qmlcachegen ' + qVersion():
        raise RuntimeError(f'QML compiler/runtime mismatch: {version}, Qt {qVersion()}')
    files = sorted(set(sources(share)).union(extra_sources))
    if not files:
        raise RuntimeError(f'No installed Monet QML sources in {share}')
    # Normalize every source before compiling: imports may consult each other.
    for path in files:
        os.utime(path, ns=(0, 0))
    for path in files:
        target = Path(str(path) + 'c')
        temporary = target.with_name(target.stem + '.tmp' + target.suffix)
        try:
            subprocess.run([str(compiler), '--only-bytecode', '-o', str(temporary), str(path)], check=True)
            temporary.chmod(0o644)
            temporary.replace(target)
            os.utime(target, ns=(0, 0))
        finally:
            temporary.unlink(missing_ok=True)
            Path(str(temporary) + ".aotstats").unlink(missing_ok=True)
    # A running Plasma shell can keep an older versioned editor URL. Its QML
    # symlink already follows the current page. Its bytecode must follow too.
    panel = share / PANEL_CONFIG
    for alias in (panel / 'monet-editor').glob('*/MonetPanelConfiguration.qml'):
        if not alias.is_symlink() or alias.readlink() != Path('../../MonetPanelConfiguration.qml'):
            continue
        cache = alias.with_suffix('.qmlc')
        temporary = cache.with_suffix('.tmp-link')
        try:
            temporary.symlink_to('../../MonetPanelConfiguration.qmlc')
            temporary.replace(cache)
        finally:
            temporary.unlink(missing_ok=True)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--share', type=Path, default=Path('/usr/share'))
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--extra-source', type=Path, action='append', default=[])
    args = parser.parse_args()
    print(f'Precompiled {compile_sources(args.share, args.compiler, args.extra_source)} Monet QML/JavaScript files')


if __name__ == '__main__':
    main()
