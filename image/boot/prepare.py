#!/usr/bin/python3
"""Prepare graphics autoloading in a disposable image root, before dracut."""
from pathlib import Path
import re
import shutil
import sys

GRAPHICS = {"i915", "amdgpu", "nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm"}
ASSIGN = re.compile(r'^(\s*)force_drivers(\+?=)([\"\'])([^\"\']*)\3\s*(#.*)?$')
HARDWARE_WAIT = '# Monet: wait for setup dependencies only when hardware migration is needed.\n'


def hardware_config(script, unit):
    """Keep Bazzite's early-return check ahead of its slow daemon dependencies."""
    after = 'After=rpm-ostreed.service tuned.service\n'
    replacement = 'After=local-fs.target\n'
    if HARDWARE_WAIT in script and replacement in unit and after not in unit:
        return script, unit
    guard = ('if [[ "$KNOWN_IMAGE_NAME" == "$IMAGE_NAME" && \\\n'
             '    "$KNOWN_IMAGE_BRANCH" == "$IMAGE_BRANCH" && \\\n'
             '    "$KNOWN_FEDORA_VERSION" == "$FEDORA_VERSION" && \\\n'
             '    "$HWS_VER_RAN" == "$HWS_VER" ]]; then\n'
             '  echo "Hardware setup already ran for version $HWS_VER_RAN, skipping"\n'
             '  exit 0\nfi\n')
    if (script.count('# GLOBAL\n') != 1 or guard not in script.partition('# GLOBAL\n')[0]
            or unit.count(after) != 1 or HARDWARE_WAIT in script):
        raise ValueError('Unrecognized Bazzite hardware setup; review its startup prerequisites')
    # After= orders jobs even when they fail; it does not require success. Keep
    # that behavior and the original migration itself, including its own receipts.
    script = script.replace('# GLOBAL\n', HARDWARE_WAIT
        + 'systemctl start rpm-ostreed.service tuned.service || true\n\n# GLOBAL\n', 1)
    return script, unit.replace(after, replacement, 1)


def prepare_hardware(root):
    script = root / 'usr/libexec/bazzite-hardware-setup'
    unit = root / 'usr/lib/systemd/system/bazzite-hardware-setup.service'
    if script.is_symlink() or unit.is_symlink():
        raise ValueError('Refusing symlinked image hardware setup')
    if not script.exists() and not unit.exists():
        return
    before = script.read_text(), unit.read_text()
    after = hardware_config(*before)
    for path, old, new in zip((script, unit), before, after):
        if old != new:
            path.write_text(new)


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
    prepare_hardware(root)
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
