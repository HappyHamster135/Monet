#!/bin/bash
# Packaging checks for the signed Fedora payloads installed by DNF. Firmware trust
# and revocations still need the Secure Boot VM test; a signature listing isn't that test.
set -euo pipefail
iso=$1
label=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
xorriso -indev "$iso" -pvd_info > "$work/volume" 2>/dev/null
grep -qF "$label" "$work/volume"
mkdir "$work/efi" "$work/boot"
xorriso -osirrox on -indev "$iso" \
    -extract /EFI/BOOT "$work/efi" \
    -extract /images/pxeboot/vmlinuz "$work/vmlinuz" \
    -extract_boot_images "$work/boot/" >/dev/null 2>&1

signature() {
    local file=$1 issuer=$2
    sbverify --list "$file" > "$work/signatures" 2>&1
    if ! grep -qE "$issuer" "$work/signatures"; then
        echo "Missing expected Secure Boot signer: $file" >&2
        cat "$work/signatures" >&2
        exit 1
    fi
}
signature "$work/efi/BOOTX64.EFI" 'CN=Microsoft (Corporation UEFI CA 2011|UEFI CA 2023)'
for file in "$work/efi/grubx64.efi" "$work/efi/mmx64.efi" "$work/vmlinuz"; do
    signature "$file" 'OU=Fedora Secure Boot CA'
done

# Optical and USB boot must carry the same, unmodified chain and menu.
images=("$work"/boot/*efi*)
test "${#images[@]}" -ge 2
for img in "${images[@]}"; do
    for name in BOOTX64.EFI grubx64.efi mmx64.efi grub.cfg; do
        mtype -i "$img" "::/EFI/BOOT/$name" > "$work/copied"
        cmp "$work/efi/$name" "$work/copied"
    done
done
grep -qF "CDLABEL=$label" "$work/efi/grub.cfg"
test "$(stat -c %s "$iso")" -lt 2000000000
echo "Secure Boot packaging checked: signed shim, GRUB, MokManager and kernel; matching optical/USB boot files."
