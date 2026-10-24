#!/bin/bash
# Builds Monet Setup's USB stick: a small live Fedora that starts straight into
# Monet Setup, with Fedora's signed shim, GRUB and kernel, so it starts with
# Secure Boot on. UEFI only (every PC that runs Windows 11 has it).
#
#   image/setup/build.sh VERSION IMAGE OUT.iso [BOOTC-SETTINGS.tar]
#
# BOOTC-SETTINGS.tar (bootc-settings.tar in the repository by default) holds the
# image's own install settings for bootc, which reads them from the system it runs
# on: .github/workflows/image.yml takes them out of the image it built.
#
# Runs as root in a Fedora container (.github/workflows/image.yml) with
# --privileged, for the chroot that makes the initramfs.
set -euo pipefail

VERSION=$1
IMAGE=$2
OUT=$3
SETTINGS=${4:-}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SETTINGS=${SETTINGS:-$REPO/bootc-settings.tar}
FEDORA=$(rpm -E %fedora)
LABEL="Monet-$VERSION"
W=/var/tmp/monet-live
ROOT=$W/root
ISO=$W/iso

rm -rf "$W"
mkdir -p "$ROOT" "$ISO/LiveOS" "$ISO/images/pxeboot" "$ISO/EFI/BOOT"

dnf -y -q install dracut squashfs-tools xorriso mtools dosfstools python3 >/dev/null

echo "== The live system (Fedora $FEDORA)"
dnf -y -q --installroot="$ROOT" --releasever="$FEDORA" --use-host-config \
    --setopt=install_weak_deps=False --setopt=tsflags=nodocs \
    install $(grep -v '^#' "$HERE/packages.txt" | xargs)

echo "== Monet Setup"
cp -a "$HERE/files/." "$ROOT/"
# bootc install reads prepare-root.conf and its install settings from here, as if
# this were the image: the image's own (bootc's issues 1410 and 1438; Anaconda does
# the same). The kernel arguments and the bootloader still come from the image.
tar -xf "$SETTINGS" -C "$ROOT"
if [ ! -e "$ROOT/usr/lib/ostree/prepare-root.conf" ] && [ ! -e "$ROOT/etc/ostree/prepare-root.conf" ]; then
    echo "$SETTINGS has no prepare-root.conf: bootc couldn't install from this stick" >&2
    exit 1
fi
APP=$ROOT/usr/share/monet-setup
mkdir -p "$APP" "$ROOT/usr/share/fonts/monet"
cp -a "$REPO/setup/monet-setup" "$REPO/setup/monet_setup" "$REPO/setup/qml" "$REPO/setup/art" "$REPO/setup/locale" "$APP/"
find "$APP" -name __pycache__ -prune -exec rm -rf {} +
echo "$VERSION" > "$APP/VERSION"
echo "$IMAGE" > "$APP/IMAGE"
ln -sf /usr/share/monet-setup/monet-setup "$ROOT/usr/bin/monet-setup"
cp "$REPO"/linux/share/fonts/monet/*.ttf "$REPO"/image/installer/product/usr/share/fonts/monet/Inter-*.otf \
   "$ROOT/usr/share/fonts/monet/"
cp "$REPO"/image/installer/product/usr/share/fonts/monet/OFL-*.txt "$ROOT/usr/share/fonts/monet/"
echo monet-setup > "$ROOT/etc/hostname"
sed -i 's/^SELINUX=.*/SELINUX=permissive/' "$ROOT/etc/selinux/config"
# Settled, so systemd's first-boot questions never stop the start on a console.
echo LANG=en_US.UTF-8 > "$ROOT/etc/locale.conf"
echo KEYMAP=us > "$ROOT/etc/vconsole.conf"
ln -sf ../usr/share/zoneinfo/UTC "$ROOT/etc/localtime"

for fs in proc sys dev; do mount --rbind "/$fs" "$ROOT/$fs"; done
trap 'for fs in dev sys proc; do umount -R "$ROOT/$fs" 2>/dev/null || :; done' EXIT
chroot "$ROOT" systemctl enable monet-setup.service NetworkManager.service
chroot "$ROOT" systemctl set-default multi-user.target
chroot "$ROOT" systemctl mask systemd-firstboot.service
chroot "$ROOT" fc-cache -f >/dev/null
chroot "$ROOT" plymouth-set-default-theme monet
KVER=$(ls "$ROOT/lib/modules" | sort -V | tail -1)
echo "== Starting up: kernel $KVER"
chroot "$ROOT" dracut --no-hostonly --force --quiet --add "dmsquash-live plymouth" \
    --omit "iscsi nfs nbd fcoe fcoe-uefi multipath" /boot/initramfs-live.img "$KVER"
cp "$ROOT/lib/modules/$KVER/vmlinuz" "$ISO/images/pxeboot/vmlinuz"
cp "$ROOT/boot/initramfs-live.img" "$ISO/images/pxeboot/initrd.img"
for fs in dev sys proc; do umount -R "$ROOT/$fs"; done
trap - EXIT

echo "== The USB stick's start: shim, GRUB (both signed by Fedora), Monet's menu"
EFI=$ROOT/boot/efi/EFI/fedora
sed "s|@LABEL@|$LABEL|g" "$HERE/grub.cfg" > "$W/grub.cfg"
cp "$EFI/shimx64.efi" "$ISO/EFI/BOOT/BOOTX64.EFI"
cp "$EFI/grubx64.efi" "$EFI/mmx64.efi" "$W/grub.cfg" "$ISO/EFI/BOOT/"
mkfs.fat -C -n MONETEFI "$W/efiboot.img" 8192 >/dev/null
mmd -i "$W/efiboot.img" ::/EFI ::/EFI/BOOT
mcopy -i "$W/efiboot.img" "$ISO"/EFI/BOOT/* ::/EFI/BOOT/

echo "== Squashing"
rm -rf "$ROOT"/var/cache/dnf/* "$ROOT"/var/log/dnf* "$ROOT"/boot/efi/EFI \
       "$ROOT"/boot/initramfs-* "$ROOT"/boot/vmlinuz-* "$ROOT"/boot/loader "$ROOT"/boot/System.map-*
mksquashfs "$ROOT" "$ISO/LiveOS/squashfs.img" -comp xz -Xbcj x86 -b 1M -noappend -quiet

echo "== $OUT"
xorriso -as mkisofs -o "$OUT" -V "$LABEL" -iso-level 3 -joliet -joliet-long -rational-rock \
    -partition_offset 16 \
    -append_partition 2 C12A7328-F81F-11D2-BA4B-00A0C93EC93B "$W/efiboot.img" -appended_part_as_gpt \
    -e --interval:appended_partition_2:all:: -no-emul-boot \
    "$ISO" 2>&1 | grep -v "^xorriso : UPDATE" || :

# Checks: the label, the menu in the EFI partition, the size GitHub allows.
xorriso -indev "$OUT" -pvd_info 2>/dev/null | grep -q "$LABEL"
rm -rf "$W/check" && mkdir "$W/check"
xorriso -osirrox on -indev "$OUT" -extract_boot_images "$W/check/" >/dev/null 2>&1
# Both the El Torito image and the GPT partition come out: check each.
for img in "$W"/check/*efi*; do
    mtype -i "$img" ::/EFI/BOOT/grub.cfg | grep -q "CDLABEL=$LABEL"
    mdir -i "$img" ::/EFI/BOOT | grep -qi bootx64
done
SIZE=$(stat -c %s "$OUT")
test "$SIZE" -lt 2000000000
echo "$OUT: $((SIZE / 1000000)) MB"
