#!/usr/bin/env bash
# Removes Monet from this PC. Windows and your games are not touched.
set -euo pipefail

PREFIX=/usr/local

if [ "$(id -u)" -ne 0 ]; then
    # Remove this user's game shortcuts and settings, then the system part.
    rm -f "$HOME"/.local/share/applications/monet-game-*.desktop
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/monet"
    systemctl --user disable --now monet-light.timer monet-light-sync.path >/dev/null 2>&1 || true
    # Hand the desktop back to Breeze.
    command -v plasma-apply-lookandfeel >/dev/null && plasma-apply-lookandfeel --apply org.kde.breeze.desktop >/dev/null 2>&1
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Breeze
    echo "Removing Monet. You may be asked for your password."
    exec sudo "$0" "$@"
fi

systemctl disable --now monet-sync.service monet-windows-setup.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-sync.service /etc/systemd/system/monet-windows-setup.service
systemctl daemon-reload

systemctl --global disable monet-light.timer monet-light-sync.path >/dev/null 2>&1 || true
rm -f /etc/systemd/user/monet-light.service /etc/systemd/user/monet-light.timer \
    /etc/systemd/user/monet-light-sync.service /etc/systemd/user/monet-light-sync.path
# Background updates come back the way Bazzite has them.
systemctl unmask uupd.timer ublue-update.timer rpm-ostreed-automatic.timer bootc-fetch-apply-updates.timer \
    flatpak-system-update.timer >/dev/null 2>&1 || true
systemctl --global unmask flatpak-user-update.timer >/dev/null 2>&1 || true
rm -f /etc/polkit-1/rules.d/49-monet.rules /etc/xdg/autostart/monet-session.desktop
rm -f "$PREFIX/bin/monet"
for tool in monet-session monet-look monet-light monet-quick monet-prepare-windows; do
    rm -f "$PREFIX/libexec/$tool"
done
for icon in monet monet-windows monet-quick-symbolic; do
    rm -f "$PREFIX/share/icons/hicolor/scalable/apps/$icon.svg"
done
rm -f "$PREFIX/share/applications/monet-windows.desktop" "$PREFIX/share/applications/monet-settings.desktop"
rm -f "$PREFIX/share/color-schemes/MonetLight.colors" "$PREFIX/share/color-schemes/MonetDark.colors"
rm -f "$PREFIX"/share/konsole/Monet.profile "$PREFIX"/share/konsole/Monet.colorscheme "$PREFIX"/share/konsole/MonetDark.colorscheme
rm -rf "$PREFIX/share/plasma/plasmoids/org.monet.games" "$PREFIX/share/plasma/plasmoids/org.monet.quick" \
    "$PREFIX/share/plasma/plasmoids/org.monet.placard" "$PREFIX/share/plasma/wallpapers/org.monet.hours" \
    "$PREFIX/share/plasma/desktoptheme/monet" "$PREFIX/share/plasma/desktoptheme/monet-solid" \
    "$PREFIX/share/plasma/look-and-feel/org.monet.desktop" "$PREFIX/share/plasma/look-and-feel/org.monet.smoke.desktop" \
    "$PREFIX/share/icons/Monet" "$PREFIX/share/icons/Monet-cursors" \
    "$PREFIX/share/Kvantum/Monet" "$PREFIX/share/Kvantum/MonetDark" \
    "$PREFIX/share/Kvantum/MonetSolid" "$PREFIX/share/Kvantum/MonetDarkSolid" \
    "$PREFIX/share/aurorae/themes/Monet" "$PREFIX/share/aurorae/themes/MonetSolid" \
    "$PREFIX/share/aurorae/themes/MonetSmoke" "$PREFIX/share/aurorae/themes/MonetSmokeSolid" \
    "$PREFIX/share/fonts/monet" "$PREFIX/share/wallpapers/Monet" "$PREFIX/share/monet" /var/lib/monet

echo "Monet is removed. To also remove Monet Bridge, run \"Uninstall Monet\" in Windows."
