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
else
    UNITDIR=/etc/systemd/system
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

Monet is installed.

Next, set up Windows:
  1. Open the app menu and choose "Windows".
  2. In Windows, download Monet for Windows and double-click "Install Monet".
  3. Start a game from the Windows Games widget in the panel.

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

install -D -m 755 "$SRC/monet" "$BINDIR/monet"
put 755 "$SRC/libexec/monet-session" "$LIBEXECDIR/monet-session"

install -D -m 644 "$SRC/icons/monet.svg" "$DATADIR/icons/hicolor/scalable/apps/monet.svg"
install -D -m 644 "$SRC/icons/monet-windows.svg" "$DATADIR/icons/hicolor/scalable/apps/monet-windows.svg"
put 644 "$SRC/share/applications/monet-windows.desktop" "$DATADIR/applications/monet-windows.desktop"

applet="$DATADIR/plasma/plasmoids/org.monet.games"
rm -rf "$applet"
put 644 "$SRC/share/plasma/plasmoids/org.monet.games/metadata.json" "$applet/metadata.json"
put 644 "$SRC/share/plasma/plasmoids/org.monet.games/contents/ui/main.qml" "$applet/contents/ui/main.qml"

rm -rf "$DATADIR/wallpapers/Monet"
install -d "$DATADIR/wallpapers"
cp -r "$SRC/share/wallpapers/Monet" "$DATADIR/wallpapers/Monet"
chmod -R u=rwX,go=rX "$DATADIR/wallpapers/Monet"

put 644 "$SRC/systemd/monet-sync.service" "$UNITDIR/monet-sync.service"
put 644 "$SRC/autostart/monet-session.desktop" /etc/xdg/autostart/monet-session.desktop

# Allow one-click switching without a password. /usr/local is a link to
# /var/usrlocal on Fedora Atomic, so allow both spellings of the path.
real_bin="$(readlink -f "$BINDIR/monet")"
programs="[\"$BINDIR/monet\", \"$real_bin\"]"
install -d -m 755 /etc/polkit-1/rules.d
sed -e "s|@PROGRAMS@|$programs|" "$SRC/polkit/49-monet.rules" > /etc/polkit-1/rules.d/49-monet.rules
chmod 644 /etc/polkit-1/rules.d/49-monet.rules

if [ "$IMAGE" = 1 ]; then
    systemctl enable monet-sync.service
    sed -i 's/^PRETTY_NAME=.*/PRETTY_NAME="Monet"/' /usr/lib/os-release
else
    command -v restorecon >/dev/null && restorecon -R "$BINDIR/monet" "$LIBEXECDIR/monet-session" "$UNITDIR/monet-sync.service" /etc/polkit-1/rules.d/49-monet.rules 2>/dev/null || true
    systemctl daemon-reload
    systemctl enable --now monet-sync.service >/dev/null 2>&1 || systemctl enable monet-sync.service
fi
