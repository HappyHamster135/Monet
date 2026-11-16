#!/bin/bash
# On the NVIDIA image Bazzite checks the Flatpak NVIDIA runtimes while the PC
# starts, and that took 7 s of the boot. Do it 30 s after startup instead.
# The AMD/Intel image has neither service, so this does nothing there.
set -euo pipefail
source_dir=$(dirname -- "${BASH_SOURCE[0]}")
root=${1:-/}
units=$root/usr/lib/systemd/system
sync=ublue-nvidia-flatpak-runtime-sync.service
verify=ublue-nvidia-flatpak-runtime-verify.service
if [ -f "$units/$sync" ] && [ -f "$units/$verify" ]; then
    systemctl --root="$root" disable "$sync" "$verify"
    install -Dm644 "$source_dir/monet-nvidia-flatpak.timer" "$units/monet-nvidia-flatpak.timer"
    install -Dm644 "$source_dir/10-monet-sync.conf" "$units/$verify.d/10-monet-sync.conf"
    systemctl --root="$root" enable monet-nvidia-flatpak.timer
fi
