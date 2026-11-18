#!/usr/bin/python3
"""Prepare graphics autoloading in a disposable image root, before dracut."""
from pathlib import Path
import re
import shutil
import sys

GRAPHICS = {"i915", "amdgpu", "nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm"}
ASSIGN = re.compile(r'^(\s*)force_drivers(\+?=)([\"\'])([^\"\']*)\3\s*(#.*)?$')


def autoload_config(text):
    lines = []
    for line in text.splitlines():
        match = ASSIGN.fullmatch(line)
        if not match:
            lines.append(line)
            continue
        indent, operation, quote, value, comment = match.groups()
        modules = value.split()
        automatic = [module for module in modules if module.replace("-", "_") in GRAPHICS]
        other = [module for module in modules if module not in automatic]
        if not automatic:
            lines.append(line)
            continue
        lines.append(indent + '# Monet: include graphics for every PC; let udev load matching hardware.')
        lines.append(indent + 'add_drivers+=" ' + ' '.join(automatic) + ' "')
        if other or operation == "=":
            lines.append(indent + 'force_drivers' + operation + quote + ' ' + ' '.join(other) + ' ' + quote)
        if comment:
            lines.append(indent + comment)
    return '\n'.join(lines) + '\n'


def prepare(root):
    root = Path(root)
    config = root / 'usr/lib/dracut/dracut.conf.d/99-nvidia.conf'
    if config.is_symlink():
        raise ValueError('Refusing a symlinked image graphics configuration')
    # Other images may already use udev and have no vendor preload file.
    if config.exists():
        before = config.read_text()
        after = autoload_config(before)
        if before != after:
            config.write_text(after)
    source = Path(__file__).with_name('99monet-graphics')
    destination = root / 'usr/lib/dracut/modules.d/99monet-graphics'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('module-setup.sh', '61-monet-nvidia-kms.rules'):
        shutil.copyfile(source / name, destination / name)
    (destination / 'module-setup.sh').chmod(0o755)


if __name__ == '__main__':
    prepare(sys.argv[1])
