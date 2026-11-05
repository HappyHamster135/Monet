#!/bin/bash
# Finalize only a disposable OS image build, never a running installation.
set -euo pipefail

# Atomic images create root's home at boot. Dracut's directory/symlink copy
# needs its target during the build as well. Keep normal build log output, but
# don't ask for a host syslog socket inside this container.
install -d -m 0700 /var/roothome
printf 'sysloglvl=0\n' > /etc/dracut.conf.d/99-monet-container-build.conf
mapfile -t kernels < <(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core)
if [ "${#kernels[@]}" != 1 ]; then
    echo 'Expected exactly one installed kernel when building Monet.' >&2
    exit 1
fi
kernel=${kernels[0]}
dracut --no-hostonly --kver "$kernel" --reproducible --zstd \
    --add ostree --add fido2 --add tpm2-tss -f "/usr/lib/modules/$kernel/initramfs.img"
test -s "/usr/lib/modules/$kernel/initramfs.img"
chmod 0600 "/usr/lib/modules/$kernel/initramfs.img"
rm /etc/dracut.conf.d/99-monet-container-build.conf

# Preserve authselect's generated integrity state on first boot through the
# standard factory/tmpfiles mechanism. C never overwrites an existing account's
# state during an upgrade. This is data, not a secret or an authentication key.
if [ -f /var/lib/authselect/checksum ]; then
    install -D -m 0644 /var/lib/authselect/checksum /usr/share/monet/authselect-checksum
    printf 'C /var/lib/authselect/checksum 0644 root root - /usr/share/monet/authselect-checksum\n' \
        > /usr/lib/tmpfiles.d/monet-authselect.conf
    rm /var/lib/authselect/checksum
fi
# Package-manager scratch data and the linker cache are regenerated when needed.
rm -rf /run/dnf /var/cache/libdnf5 /var/lib/dnf/repos
rm -f /var/log/dnf5.log* /var/cache/ldconfig/aux-cache
