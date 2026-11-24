#!/usr/bin/python3
"""Prepare graphics autoloading in a disposable image root, before dracut."""
from pathlib import Path
import re
import shutil
import sys

GRAPHICS = {"i915", "amdgpu", "nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm"}
ASSIGN = re.compile(r'^(\s*)force_drivers(\+?=)([\"\'])([^\"\']*)\3\s*(#.*)?$')
HARDWARE_WAIT = '# Monet: wait for setup dependencies only when hardware migration is needed.\n'
BLUETOOTH_DEFAULT = """if [[ ! $KARGS =~ "disable_ertm" ]]; then
  echo "Adding needed kargs for bluetooth"
  NEEDED_KARGS+=("--append-if-missing=bluetooth.disable_ertm=1")
fi"""
INSTALL_BLUETOOTH = """# Apply the hardware setup default when bootc creates the first boot entry.
[install]
kargs = ["bluetooth.disable_ertm=1"]
"""
TRUST_DROPIN = """# Match Fedora's atomic trust refresh lifecycle: first boot and deployments.
# https://gitlab.com/fedora/bootc/base-images/-/merge_requests/663
[Unit]
ConditionNeedsUpdate=/etc
Before=systemd-update-done.service systemd-resolved.service
"""
WIFI_NEEDED = ('test ! -e /var/lib/bazzite-iwd-migration.done'
    ' || test -e /etc/NetworkManager/conf.d/99-valve-wifi-backend.conf'
    ' || test -e /etc/NetworkManager/conf.d/iwd.conf'
    ' || { test -e /etc/systemd/system/wpa_supplicant.service'
    ' && test ! -s /etc/systemd/system/wpa_supplicant.service; }'
    ' || { test -e /run/systemd/system/wpa_supplicant.service'
    ' && test ! -s /run/systemd/system/wpa_supplicant.service; }')


def prepare_wifi(root):
    """Avoid a redundant systemd reload before NetworkManager on normal boots."""
    script = root / 'usr/libexec/bazzite-iwd-migration'
    unit = root / 'usr/lib/systemd/system/bazzite-iwd-migration.service'
    if script.is_symlink() or unit.is_symlink():
        raise ValueError('Refusing symlinked image Wi-Fi migration')
    if not script.exists() and not unit.exists():
        return
    expected = """systemctl unmask wpa_supplicant.service
if [ -f /etc/NetworkManager/conf.d/99-valve-wifi-backend.conf ]; then
rm -f /etc/NetworkManager/conf.d/99-valve-wifi-backend.conf
fi
if [ -f /etc/NetworkManager/conf.d/iwd.conf ]; then
rm -f /etc/NetworkManager/conf.d/iwd.conf
fi"""
    code = '\n'.join(line.strip() for line in script.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith('#'))
    commands = [line for line in unit.read_text().splitlines() if line.startswith('Exec')]
    if (code != expected or commands != ['ExecStart=/usr/libexec/bazzite-iwd-migration',
            'ExecStartPost=/usr/bin/touch /var/lib/bazzite-iwd-migration.done']
            or 'Before=NetworkManager.service' not in unit.read_text().splitlines()):
        raise ValueError('Unrecognized Wi-Fi migration; review before skipping routine cleanup')
    destination = unit.with_name(unit.name + '.d') / '50-monet-fast-start.conf'
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError('Refusing symlinked image Wi-Fi migration drop-in')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text('[Service]\nExecCondition=/bin/sh -c \'' + WIFI_NEEDED + '\'\n')


def prepare_trust(root):
    """Backport Fedora's deployment condition to the inherited legacy service."""
    unit = root / 'usr/lib/systemd/system/bootc-update-ca-trust.service'
    if unit.is_symlink():
        raise ValueError('Refusing symlinked image certificate-trust service')
    if not unit.exists():
        return
    text = unit.read_text()
    expected = ('DefaultDependencies=no', 'Requires=local-fs.target',
                'After=local-fs.target', 'Before=sysinit.target',
                'ConditionPathIsMountPoint=/sysroot',
                'ConditionPathExists=/usr/bin/update-ca-trust',
                'ExecStart=/usr/bin/update-ca-trust extract')
    if any(line not in text.splitlines() for line in expected):
        raise ValueError('Unrecognized legacy certificate-trust service; review its boot ordering')
    # A newer base may replace this service with Fedora's atomic service. Do not
    # allow two writers to race; review such a transition rather than guessing.
    for name in ('atomic-update-ca-trust.service', 'coreos-update-ca-trust.service'):
        if unit.with_name(name).exists():
            raise ValueError('Multiple certificate-trust refresh services need review')
    destination = unit.with_name(unit.name + '.d') / '50-monet-deployment.conf'
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError('Refusing symlinked image certificate-trust drop-in')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(TRUST_DROPIN)


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
    # Monet Setup takes usr/lib/bootc/install from this image. This setting
    # applies at installation only. Later deployments keep the owner's kargs.
    # Keep hardware-specific setup and its real reboot decisions in Bazzite.
    install = root / 'usr/lib/bootc/install/00-monet-bluetooth.toml'
    if install.is_symlink() or install.parent.is_symlink():
        raise ValueError('Refusing symlinked bootc install configuration')
    if install.exists() and install.read_text() != INSTALL_BLUETOOTH:
        raise ValueError('Conflicting Monet Bluetooth install configuration')
    if '\n' + BLUETOOTH_DEFAULT + '\n' in before[0]:
        install.parent.mkdir(parents=True, exist_ok=True)
        install.write_text(INSTALL_BLUETOOTH)
    else:
        # If the base drops the old default, drop our copy of it as well.
        install.unlink(missing_ok=True)
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


def prepare_input_remapper(root):
    """Skip the per-device autoload client until its system bus exists."""
    rule = root / 'usr/lib/udev/rules.d/99-input-remapper.rules'
    if rule.is_symlink() or not rule.is_file():
        return
    original = ('ACTION=="add", SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_PATH}!="platform-sound", '
                'ATTRS{phys}!="input-remapper*", '
                'RUN+="/bin/input-remapper-control --command autoload --device $env{DEVNAME}"')
    lines = rule.read_text().splitlines(keepends=True)
    if [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')] == [original]:
        guarded = original.replace('RUN+=', 'TEST=="/run/dbus/system_bus_socket", RUN+=')
        rule.write_text(''.join(line.replace(original, guarded) if line.strip() == original else line
                                for line in lines))


def prepare(root):
    root = Path(root)
    # The NFS client gives its backing devices anonymous major:minor names.
    # Avoid launching nfsrahead for local disks and named Btrfs/EROFS devices.
    # Only narrow the known vendor rule; keep any future upstream rule intact.
    rule = root / 'usr/lib/udev/rules.d/99-nfs.rules'
    original = 'SUBSYSTEM=="bdi", ACTION=="add", PROGRAM="/usr/libexec/nfsrahead %k", ATTR{read_ahead_kb}="%c"'
    if not rule.is_symlink() and rule.is_file() and rule.read_text().strip() == original:
        rule.write_text(original.replace('PROGRAM=', 'KERNEL=="0:*", PROGRAM=') + '\n')
    prepare_input_remapper(root)
    prepare_trust(root)
    prepare_wifi(root)
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
