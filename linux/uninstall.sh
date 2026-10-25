#!/usr/bin/env bash
# Removes Monet from this PC. Windows and your games are not touched.
set -euo pipefail

PREFIX=/usr/local

if [ "$(id -u)" -ne 0 ]; then
    # Remove this user's game shortcuts and settings, then the system part.
    rm -f "$HOME"/.local/share/applications/monet-game-*.desktop
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/monet"
    # Apps' own names and menu entries, KDE's settings pages and Help menus.
    grep -l -x 'X-Monet=true' "$HOME"/.local/share/applications/*.desktop \
        "${XDG_CONFIG_HOME:-$HOME/.config}"/autostart/*.desktop 2>/dev/null | xargs -r rm -f || true
    kdeglobals="${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"
    if [ -f "$kdeglobals" ]; then
        sed -i -e '/^\[KDE Control Module Restrictions\]$/,/^\[/{/^\[KDE Control Module Restrictions\]$/d;/^\[/!d}' \
            -e '/^\[KDE Action Restrictions\]$/,/^\[/{/^\[KDE Action Restrictions\]$/d;/^\[/!d}' "$kdeglobals"
    fi
    systemctl --user disable --now monet-light.timer monet-light-sync.path monet-fresh.service monet-names.path monet-frames.path monet-zen.path >/dev/null 2>&1 || true
    # The canvases Monet put under other apps' icons (monet-quick frames), and only those.
    grep -rl --include='*.svg' 'Monet frame:' "${XDG_DATA_HOME:-$HOME/.local/share}/icons/Monet" 2>/dev/null | xargs -r rm -f || true
    # Zen back to its own look (monet-quick zen): Monet's folder, its two imports and its part of user.js.
    for profile in "$HOME"/.var/app/app.zen_browser.zen/.zen/*/; do
        rm -rf "${profile}chrome/monet"
        sed -i '/^@import url("monet\/zen.css");$/d' "${profile}chrome/userChrome.css" 2>/dev/null || true
        sed -i '/^@import url("monet\/newtab.css");$/d' "${profile}chrome/userContent.css" 2>/dev/null || true
        sed -i '/^\/\/ Monet: begin/,/^\/\/ Monet: end$/d' "${profile}user.js" 2>/dev/null || true
    done
    # Hand the desktop back to Breeze, and the sounds to Ocean.
    command -v plasma-apply-lookandfeel >/dev/null && plasma-apply-lookandfeel --apply org.kde.breeze.desktop >/dev/null 2>&1
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Breeze
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file kdeglobals --group Sounds --key Theme ocean
    echo "Removing Monet. You may be asked for your password."
    exec sudo "$0" "$@"
fi

systemctl disable --now monet-sync.service monet-windows-setup.service monet-update.timer monet-apps.timer monet-charge.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-sync.service /etc/systemd/system/monet-windows-setup.service \
    /etc/systemd/system/monet-update.service /etc/systemd/system/monet-update.timer \
    /etc/systemd/system/monet-apps.service /etc/systemd/system/monet-apps.timer \
    /etc/systemd/system/monet-crash@.service /etc/systemd/system/systemd-coredump@.service.wants/monet-crash@.service \
    /etc/systemd/system/monet-charge.service
rmdir /etc/systemd/system/systemd-coredump@.service.wants 2>/dev/null || true
# Ready when you come back: off, and the sign-in screen asks for the password again.
systemctl disable monet-ready-leave.service monet-ready-boot.service >/dev/null 2>&1 || true
systemctl --global disable monet-ready-lock.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-ready-leave.service /etc/systemd/system/monet-ready-boot.service \
    /etc/systemd/user/monet-ready-lock.service /etc/plasmalogin.conf.d/zz-monet-ready.conf /run/monet/ready-auto \
    /etc/systemd/user/monet-replay.service
# Backups: no more earlier versions (the ones kept go, with Monet; the files themselves
# stay), and no more copies to a drive (what's on it stays there).
systemctl disable --now monet-keep.timer monet-keep-prepare.service >/dev/null 2>&1 || true
systemctl --global disable monet-backup.timer >/dev/null 2>&1 || true
[ -x "$PREFIX/libexec/monet-keep" ] && "$PREFIX/libexec/monet-keep" off >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-keep-prepare.service /etc/systemd/system/monet-keep.service \
    /etc/systemd/system/monet-keep.timer /etc/systemd/user/monet-backup.service /etc/systemd/user/monet-backup.timer
# No more trials for new Monets, resets or re-learning the security chip. An encrypted disk
# stays encrypted, and still unlocks by itself: that's systemd's part.
systemctl disable monet-boot-arm.service monet-boot-check.service monet-reset.service monet-seal.service \
    monet-seal-relearn.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-boot-arm.service /etc/systemd/system/monet-boot-check.service \
    /etc/systemd/system/monet-reset.service /etc/systemd/system/monet-seal.service \
    /etc/systemd/system/monet-seal-relearn.service /var/lib/monet/trial.json /var/lib/monet/reset
# Windows' Bluetooth pairings stay where they are.
systemctl disable monet-pairings.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/monet-pairings.service /var/lib/monet/pairings.json
systemctl daemon-reload

systemctl --global disable monet-light.timer monet-light-sync.path monet-fresh.service monet-names.path monet-frames.path monet-zen.path >/dev/null 2>&1 || true
rm -f /etc/systemd/user/monet-light.service /etc/systemd/user/monet-light.timer \
    /etc/systemd/user/monet-light-sync.service /etc/systemd/user/monet-light-sync.path /etc/systemd/user/monet-fresh.service \
    /etc/systemd/user/monet-names.path /etc/systemd/user/monet-names.service \
    /etc/systemd/user/monet-frames.path /etc/systemd/user/monet-frames.service \
    /etc/systemd/user/monet-zen.path /etc/systemd/user/monet-zen.service
# Background updates come back the way Bazzite has them.
systemctl unmask uupd.timer ublue-update.timer rpm-ostreed-automatic.timer bootc-fetch-apply-updates.timer \
    flatpak-system-update.timer >/dev/null 2>&1 || true
systemctl --global unmask flatpak-user-update.timer >/dev/null 2>&1 || true
rm -f /etc/polkit-1/rules.d/49-monet.rules /etc/xdg/autostart/monet-session.desktop
# The firewall goes back to the zone it had, before Monet's zone goes.
if command -v firewall-cmd >/dev/null && [ "$(firewall-cmd --get-default-zone 2>/dev/null)" = monet ]; then
    firewall-cmd --set-default-zone="$(cat /var/lib/monet/firewall-zone-before 2>/dev/null || echo public)" >/dev/null 2>&1 || true
fi
rm -f /etc/firewalld/zones/monet.xml /var/lib/monet/firewall-zone-before
# The battery charges to full again, as before battery care.
[ -e /var/lib/monet/charge-limit ] && "$PREFIX/libexec/monet-charge" 100 >/dev/null 2>&1 || true
rm -f "$PREFIX/bin/monet"
for tool in monet-session monet-look monet-light monet-quick monet-fresh monet-widgets monet-apps monet-charge monet-ready monet-keep monet-boot monet-reset monet-seal monet-pairings monet-secure monet-prepare-windows; do
    rm -f "$PREFIX/libexec/$tool"
done
for icon in monet monet-windows monet-quick-symbolic; do
    rm -f "$PREFIX/share/icons/hicolor/scalable/apps/$icon.svg"
done
rm -f "$PREFIX/share/applications/monet-windows.desktop" "$PREFIX/share/applications/monet-settings.desktop" \
    "$PREFIX/share/kio/servicemenus/monet-earlier.desktop" "$PREFIX/share/applications/monet-replay.desktop"
rm -f "$PREFIX/share/color-schemes/MonetLight.colors" "$PREFIX/share/color-schemes/MonetDark.colors"
rm -f "$PREFIX"/share/konsole/Monet.profile "$PREFIX"/share/konsole/Monet.colorscheme "$PREFIX"/share/konsole/MonetDark.colorscheme
rm -f "$PREFIX"/share/locale/*/LC_MESSAGES/monet.mo "$PREFIX"/share/locale/*/LC_MESSAGES/plasma_applet_org.monet.*.mo \
    "$PREFIX"/share/locale/*/LC_MESSAGES/plasma_wallpaper_org.monet.hours.mo
rm -rf "$PREFIX/share/plasma/plasmoids/org.monet.games" "$PREFIX/share/plasma/plasmoids/org.monet.quick" \
    "$PREFIX/share/plasma/plasmoids/org.monet.placard" "$PREFIX/share/plasma/wallpapers/org.monet.hours" \
    "$PREFIX/share/plasma/plasmoids/org.monet.weather" "$PREFIX/share/plasma/plasmoids/org.monet.calendar" \
    "$PREFIX/share/plasma/plasmoids/org.monet.clock" "$PREFIX/share/plasma/plasmoids/org.monet.menu" \
    "$PREFIX/share/plasma/plasmoids/org.monet.nowplaying" "$PREFIX/share/plasma/plasmoids/org.monet.notes" \
    "$PREFIX/share/plasma/plasmoids/org.monet.frame" "$PREFIX/share/plasma/avatars/Monet" \
    "$PREFIX/share/plasma/plasmoids/org.monet.system" "$PREFIX/share/plasma/plasmoids/org.monet.played" \
    "$PREFIX/share/plasma/plasmoids/org.monet.timer" "$PREFIX/share/plasma/plasmoids/org.monet.worldclock"     "$PREFIX/share/plasma/plasmoids/org.monet.batteries" \
    "$PREFIX/share/plasma/desktoptheme/monet" "$PREFIX/share/plasma/desktoptheme/monet-solid" \
    "$PREFIX/share/plasma/look-and-feel/org.monet.desktop" "$PREFIX/share/plasma/look-and-feel/org.monet.smoke.desktop" \
    "$PREFIX/share/icons/Monet" "$PREFIX/share/icons/Monet-cursors" \
    "$PREFIX/share/Kvantum/Monet" "$PREFIX/share/Kvantum/MonetDark" \
    "$PREFIX/share/Kvantum/MonetSolid" "$PREFIX/share/Kvantum/MonetDarkSolid" \
    "$PREFIX/share/aurorae/themes/Monet" "$PREFIX/share/aurorae/themes/MonetSolid" \
    "$PREFIX/share/aurorae/themes/MonetSmoke" "$PREFIX/share/aurorae/themes/MonetSmokeSolid" \
    "$PREFIX/share/fonts/monet" "$PREFIX/share/sounds/monet" "$PREFIX/share/wallpapers/Monet" "$PREFIX/share/monet" \
    /var/lib/monet

echo "Monet is removed. To also remove Monet Bridge, run \"Uninstall Monet\" in Windows."
