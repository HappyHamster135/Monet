#!/usr/bin/env bash
# Installs Monet on Bazzite or another Fedora Atomic KDE system.
#
#   ./install.sh              install for this PC (asks for your password)
#   ./install.sh --image      install into a system image (used by the Monet OS build)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGS=("$@")
PREFIX=/usr/local
IMAGE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --image) IMAGE=1; PREFIX=/usr; shift ;;
        --prefix) PREFIX="$2"; shift 2 ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

BINDIR="$PREFIX/bin"
DATADIR="$PREFIX/share"
LIBEXECDIR="$PREFIX/libexec"
if [ "$IMAGE" = 1 ]; then
    UNITDIR=/usr/lib/systemd/system
    USERUNITDIR=/usr/lib/systemd/user
else
    UNITDIR=/etc/systemd/system
    USERUNITDIR=/etc/systemd/user
fi

# Run the system part as root, then finish in the user's own session.
if [ "$(id -u)" -ne 0 ]; then
    if [ ! -d /sys/firmware/efi ]; then
        echo "This PC didn't start in UEFI mode. Monet needs UEFI to switch to Windows." >&2
        exit 1
    fi
    echo "Installing Monet. You may be asked for your password."
    sudo "$0" "${ARGS[@]}"
    "$LIBEXECDIR/monet-session" >/dev/null 2>&1 &
    disown || true
    cat <<EOF

Monet is installed. In a moment your desktop changes to Monet's look.

Next, open the app menu and choose "Windows". The first time Windows
starts, click Yes to finish setting up. Your PC then comes back to Monet,
and your Windows games show up in the Windows Games button in the panel.

EOF
    exit 0
fi

subst() {
    sed -e "s|@BINDIR@|$BINDIR|g" -e "s|@DATADIR@|$DATADIR|g" -e "s|@LIBEXECDIR@|$LIBEXECDIR|g" "$1"
}

put() { # put <mode> <source> <destination>, filling in paths
    install -d "$(dirname "$3")"
    subst "$2" > "$3.tmp"
    chmod "$1" "$3.tmp"
    mv -f "$3.tmp" "$3"
}

# Copies a folder of Monet's into place, replacing what was there.
tree() { # tree <source folder> <destination folder>
    rm -rf "$2"
    install -d "$(dirname "$2")"
    cp -r "$1" "$2"
    chmod -R u=rwX,go=rX "$2"
}

# Fills in paths in files that were copied as they are.
fill() {
    for f in "$@"; do
        sed -i -e "s|@BINDIR@|$BINDIR|g" -e "s|@DATADIR@|$DATADIR|g" -e "s|@LIBEXECDIR@|$LIBEXECDIR|g" "$f"
    done
}

install -D -m 755 "$SRC/monet" "$BINDIR/monet"
for tool in monet-session monet-look monet-light monet-quick; do
    put 755 "$SRC/libexec/$tool" "$LIBEXECDIR/$tool"
done
install -D -m 755 "$SRC/libexec/monet-prepare-windows" "$LIBEXECDIR/monet-prepare-windows"

install -D -m 644 "$SRC/icons/monet.svg" "$DATADIR/icons/hicolor/scalable/apps/monet.svg"
install -D -m 644 "$SRC/icons/monet-windows.svg" "$DATADIR/icons/hicolor/scalable/apps/monet-windows.svg"
install -D -m 644 "$SRC/icons/monet-quick-symbolic.svg" "$DATADIR/icons/hicolor/scalable/apps/monet-quick-symbolic.svg"
tree "$SRC/share/icons/Monet" "$DATADIR/icons/Monet"
put 644 "$SRC/share/applications/monet-windows.desktop" "$DATADIR/applications/monet-windows.desktop"
put 644 "$SRC/share/applications/monet-settings.desktop" "$DATADIR/applications/monet-settings.desktop"

# The look: paintings, the Plasma style and global theme, Monet's widgets,
# colors, the glass app style, the terminal's colors and the fonts.
tree "$SRC/share/wallpapers/Monet" "$DATADIR/wallpapers/Monet"
tree "$SRC/share/plasma/wallpapers/org.monet.hours" "$DATADIR/plasma/wallpapers/org.monet.hours"
tree "$SRC/share/plasma/desktoptheme/monet" "$DATADIR/plasma/desktoptheme/monet"
tree "$SRC/share/plasma/desktoptheme/monet-solid" "$DATADIR/plasma/desktoptheme/monet-solid"
for theme in org.monet.desktop org.monet.smoke.desktop; do
    tree "$SRC/share/plasma/look-and-feel/$theme" "$DATADIR/plasma/look-and-feel/$theme"
done
for applet in org.monet.games org.monet.quick org.monet.placard; do
    tree "$SRC/share/plasma/plasmoids/$applet" "$DATADIR/plasma/plasmoids/$applet"
done
fill "$DATADIR/plasma/wallpapers/org.monet.hours/contents/ui/main.qml" \
    "$DATADIR"/plasma/plasmoids/org.monet.*/contents/ui/*.qml
install -d "$DATADIR/color-schemes" "$DATADIR/konsole"
install -m 644 "$SRC"/share/color-schemes/*.colors "$DATADIR/color-schemes/"
install -m 644 "$SRC"/share/konsole/* "$DATADIR/konsole/"
for theme in Monet MonetDark MonetSolid MonetDarkSolid; do
    tree "$SRC/share/Kvantum/$theme" "$DATADIR/Kvantum/$theme"
done
tree "$SRC/share/fonts/monet" "$DATADIR/fonts/monet"
command -v fc-cache >/dev/null && fc-cache -f "$DATADIR/fonts/monet" >/dev/null 2>&1 || true

put 644 "$SRC/systemd/monet-sync.service" "$UNITDIR/monet-sync.service"
put 644 "$SRC/systemd/monet-windows-setup.service" "$UNITDIR/monet-windows-setup.service"
put 644 "$SRC/systemd/user/monet-light.service" "$USERUNITDIR/monet-light.service"
put 644 "$SRC/systemd/user/monet-light.timer" "$USERUNITDIR/monet-light.timer"
put 644 "$SRC/systemd/user/monet-light-sync.service" "$USERUNITDIR/monet-light-sync.service"
put 644 "$SRC/systemd/user/monet-light-sync.path" "$USERUNITDIR/monet-light-sync.path"

# Updates happen only when you ask for them, in Settings → Updates: no
# background updates of Monet or its apps. Masked, because Bazzite turns some
# of these on from /usr, where disabling can't reach.
for unit in uupd.timer ublue-update.timer rpm-ostreed-automatic.timer bootc-fetch-apply-updates.timer \
    flatpak-system-update.timer; do
    systemctl mask "$unit" >/dev/null 2>&1 || true
done
systemctl --global mask flatpak-user-update.timer >/dev/null 2>&1 || true
if [ -f /etc/rpm-ostreed.conf ]; then
    if grep -q '^#\?AutomaticUpdatePolicy=' /etc/rpm-ostreed.conf; then
        sed -i 's/^#\?AutomaticUpdatePolicy=.*/AutomaticUpdatePolicy=none/' /etc/rpm-ostreed.conf
    else
        sed -i '/^\[Daemon\]/a AutomaticUpdatePolicy=none' /etc/rpm-ostreed.conf
    fi
fi

# The Windows half, which Monet copies into Windows by itself, and the
# scripts Monet uses to install a fresh Windows.
rm -rf "$DATADIR/monet/windows" "$DATADIR/monet/winpe" "$DATADIR/monet/textures" "$DATADIR/monet/settings" \
    "$DATADIR/monet/gtk"
install -d "$DATADIR/monet"
cp -r "$SRC/share/monet/winpe" "$DATADIR/monet/winpe"
cp -r "$SRC/share/monet/textures" "$DATADIR/monet/textures"
# Pictures for Monet Settings, cut from the paintings.
cp -r "$SRC/share/monet/settings" "$DATADIR/monet/settings"
cp -r "$SRC/share/monet/gtk" "$DATADIR/monet/gtk"
# Windows games Monet always lists, even before Windows has found them.
install -m 644 "$SRC/share/monet/windows-games.json" "$DATADIR/monet/windows-games.json"
if [ -d "$SRC/windows" ]; then
    cp -r "$SRC/windows" "$DATADIR/monet/windows"
fi
chmod -R u=rwX,go=rX "$DATADIR/monet"
put 644 "$SRC/autostart/monet-session.desktop" /etc/xdg/autostart/monet-session.desktop

# Allow one-click switching without a password. /usr/local is a link to
# /var/usrlocal on Fedora Atomic, so allow both spellings of the path.
real_bin="$(readlink -f "$BINDIR/monet")"
programs="[\"$BINDIR/monet\", \"$real_bin\"]"
install -d -m 755 /etc/polkit-1/rules.d
sed -e "s|@PROGRAMS@|$programs|" "$SRC/polkit/49-monet.rules" > /etc/polkit-1/rules.d/49-monet.rules
chmod 644 /etc/polkit-1/rules.d/49-monet.rules

if [ "$IMAGE" = 1 ]; then
    systemctl enable monet-sync.service monet-windows-setup.service
    systemctl --global enable monet-light.timer monet-light-sync.path
    # Monet's name, mark and links where the system describes itself (KDE's
    # About page, the PC's name on the network). ID and VARIANT stay Bazzite's,
    # which its tools rely on.
    os_release=/usr/lib/os-release
    sed -i -e 's/^PRETTY_NAME=.*/PRETTY_NAME="Monet"/' \
        -e '/^LOGO=/d' -e '/^HOME_URL=/d' -e '/^SUPPORT_URL=/d' -e '/^BUG_REPORT_URL=/d' -e '/^DEFAULT_HOSTNAME=/d' \
        "$os_release"
    cat >> "$os_release" <<OSR
LOGO=monet
HOME_URL="https://github.com/HappyHamster135/Monet"
SUPPORT_URL="https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md"
BUG_REPORT_URL="https://github.com/HappyHamster135/Monet/issues"
DEFAULT_HOSTNAME="monet"
OSR
    # The PC's boot menu names Monet's entry from the text before "release".
    if grep -q " release " /etc/system-release 2>/dev/null; then
        release="$(sed 's/^.* release /Monet release /' /etc/system-release)"
        rm -f /etc/system-release
        echo "$release" > /etc/system-release
    fi
    # The sign-in screen: the harbor at night, and Monet's mark.
    for theme in /usr/share/sddm/themes/breeze /usr/share/sddm/themes/01-breeze-fedora; do
        [ -d "$theme" ] || continue
        printf '[General]\nbackground=%s\ntype=image\nshowlogo=shown\nlogo=%s\n' \
            "$DATADIR/wallpapers/Monet/contents/hours/night.jpg" \
            "$DATADIR/icons/hicolor/scalable/apps/monet.svg" > "$theme/theme.conf.user"
    done
else
    command -v restorecon >/dev/null && restorecon -R "$BINDIR/monet" "$LIBEXECDIR" "$DATADIR/monet" \
        "$UNITDIR/monet-sync.service" "$UNITDIR/monet-windows-setup.service" /etc/polkit-1/rules.d/49-monet.rules 2>/dev/null || true
    systemctl daemon-reload
    for unit in monet-sync.service monet-windows-setup.service; do
        systemctl enable --now "$unit" >/dev/null 2>&1 || systemctl enable "$unit"
    done
    systemctl --global enable monet-light.timer monet-light-sync.path >/dev/null 2>&1 || true
fi
