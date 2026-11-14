#!/usr/bin/env bash
set -euo pipefail
repo=$PWD
work=$repo/preview
assets=$work/assets
iso=Monet-0.9.8-5-Setup.iso
handoff=Monet-0.9.8-5-test-handoff.tar.gz

echo "c24ce9aa2f263d479b55e4fcdd26df15312306868fc2a81ab2ddd898b320f802  $assets/$handoff" | sha256sum --check
mkdir -p "$work/oci" "$work/tree" "$work/boot"
python3 - "$assets" "$work/oci" "$iso" <<'PY'
import json
import runpy
import sys
from pathlib import Path

verify = runpy.run_path("tools/publish-qualified.py")
record = json.loads(Path("image/releases/0.9.8-5.json").read_text())
assets, layout = map(Path, sys.argv[1:3])
iso = sys.argv[3]
verify["verify_file"](assets / iso, record["assets"][iso])
verify["unpack_images"](verify["verify_parts"](record, assets), layout, record["images"])
print("Verified the draft ISO, archive parts and both pinned manifests.")
PY
tar -xf "$assets/$handoff" -C "$work"
cmp image/releases/0.9.8-5.json "$work/handoff/0.9.8-5.json"
python3 "$work/handoff/prepare-registry.py" "$work/oci"
registry=$work/handoff/registry
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=Monet preview test registry' \
    -addext 'subjectAltName=IP:10.0.2.2,IP:127.0.0.1' -keyout "$registry/tls.key" \
    -out "$registry/tls.crt" 2>/dev/null
python3 "$registry/registry.py" > "$work/registry.log" 2>&1 &
registry_pid=$!
trap 'kill "$registry_pid" 2>/dev/null || true' EXIT
curl --fail --silent --show-error --retry 5 --retry-connrefused --cacert "$registry/tls.crt" \
    https://127.0.0.1:43895/v2/

# Keep the signed boot files and original pins, and add trust for this test registry only.
xorriso -osirrox on -indev "$assets/$iso" -extract / "$work/tree" -extract_boot_images "$work/boot/"
sudo unsquashfs -no-progress -d "$work/root" "$work/tree/LiveOS/squashfs.img"
sudo rm -- "$work/tree/LiveOS/squashfs.img"
app=$work/root/usr/share/monet-setup
sudo install -m 0644 setup/monet_setup/{app,cache,install,network,trust}.py "$app/monet_setup/"
sudo install -m 0644 setup/qml/Main.qml "$app/qml/"
sudo install -D -m 0644 "$registry/tls.crt" "$work/root/etc/containers/certs.d/10.0.2.2:43895/ca.crt"
sudo install -d "$work/root/etc/containers/registries.conf.d"
sudo tee "$work/root/etc/containers/registries.conf.d/99-monet-test.conf" >/dev/null <<'TOML'
[[registry]]
prefix = "ghcr.io/happyhamster135"
location = "10.0.2.2:43895/happyhamster135"
TOML
sudo mksquashfs "$work/root" "$work/tree/LiveOS/squashfs.img" -comp zstd -b 1M -noappend -no-progress
xorriso -as mkisofs -o "$work/test-setup.iso" -V Monet-0.9.8-5 -iso-level 3 -joliet -joliet-long -rational-rock \
    -partition_offset 16 \
    -append_partition 2 C12A7328-F81F-11D2-BA4B-00A0C93EC93B "$work/boot/gpt_part2_efi.img" -appended_part_as_gpt \
    -e --interval:appended_partition_2:all:: -no-emul-boot "$work/tree"

python3 tools/vm-test.py "$work/test-setup.iso" "$work/screens" --install | tee "$work/install.log"
grep -F 'skopeo copy docker://ghcr.io/happyhamster135/monet-amd@sha256:' "$work/vm-work/serial.log"
grep -E '"GET /v2/happyhamster135/monet-amd/manifests/sha256:[0-9a-f]+ HTTP/[0-9.]+" 200' "$work/registry.log"
test -n "$(find "$work/screens" -name '*-all-set.png' -print -quit)"
