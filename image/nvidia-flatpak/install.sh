#!/bin/bash
# Keep the base image's check, retries, and notification off the boot path.
set -euo pipefail
source_dir=$(dirname -- "${BASH_SOURCE[0]}")
units=/usr/lib/systemd/system
sync=ublue-nvidia-flatpak-runtime-sync.service
verify=ublue-nvidia-flatpak-runtime-verify.service
if [ -f "$units/$sync" ] && [ -f "$units/$verify" ]; then
    systemctl --root=/ disable "$sync" "$verify"
    install -Dm644 "$source_dir/monet-nvidia-flatpak.timer" "$units/monet-nvidia-flatpak.timer"
    install -Dm644 "$source_dir/10-monet-sync.conf" "$units/$verify.d/10-monet-sync.conf"
    systemctl --root=/ enable monet-nvidia-flatpak.timer
fi
