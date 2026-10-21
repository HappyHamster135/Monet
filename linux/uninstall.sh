#!/usr/bin/env bash
# Removes Monet from this PC. Windows and your games are not touched.
set -euo pipefail

PREFIX=/usr/local

if [ "$(id -u)" -ne 0 ]; then
    # Remove this user's game shortcuts and settings, then the system part.
    rm -f "$HOME"/.local/share/applications/monet-game-*.desktop
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/monet"
    echo "Removing Monet. You may be asked for your password."
    exec sudo "$0" "$@"
fi

systemctl disable --now monet-sync.service monet-windows-setup.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-sync.service /etc/systemd/system/monet-windows-setup.service
systemctl daemon-reload

rm -f /etc/polkit-1/rules.d/49-monet.rules /etc/xdg/autostart/monet-session.desktop
rm -f "$PREFIX/bin/monet" "$PREFIX/libexec/monet-session"
rm -f "$PREFIX/share/icons/hicolor/scalable/apps/monet.svg" "$PREFIX/share/icons/hicolor/scalable/apps/monet-windows.svg"
rm -f "$PREFIX/share/applications/monet-windows.desktop"
rm -rf "$PREFIX/share/plasma/plasmoids/org.monet.games" "$PREFIX/share/wallpapers/Monet" "$PREFIX/share/monet" /var/lib/monet

echo "Monet is removed. To also remove Monet Bridge, run \"Uninstall Monet\" in Windows."
