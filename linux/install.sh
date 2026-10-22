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
for tool in monet-session monet-look monet-light monet-quick monet-fresh monet-widgets; do
    put 755 "$SRC/libexec/$tool" "$LIBEXECDIR/$tool"
done
install -D -m 755 "$SRC/libexec/monet-prepare-windows" "$LIBEXECDIR/monet-prepare-windows"

install -D -m 644 "$SRC/icons/monet.svg" "$DATADIR/icons/hicolor/scalable/apps/monet.svg"
install -D -m 644 "$SRC/icons/monet-windows.svg" "$DATADIR/icons/hicolor/scalable/apps/monet-windows.svg"
install -D -m 644 "$SRC/icons/monet-quick-symbolic.svg" "$DATADIR/icons/hicolor/scalable/apps/monet-quick-symbolic.svg"
tree "$SRC/share/icons/Monet" "$DATADIR/icons/Monet"
tree "$SRC/share/icons/Monet-cursors" "$DATADIR/icons/Monet-cursors"
# The other names programs ask for, linked to the paintings and cursors drawn for them.
while read -r link target; do
    ln -sfn "$target" "$DATADIR/icons/Monet/$link"
done < "$SRC/share/icons/Monet/aliases"
while read -r alias name; do
    ln -sfn "$name" "$DATADIR/icons/Monet-cursors/cursors/$alias"
done < "$SRC/share/icons/Monet-cursors/aliases"
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
    # The restart and shut-down screen, the same in both lights.
    tree "$SRC/share/monet/logout" "$DATADIR/plasma/look-and-feel/$theme/contents/logout"
done
# Account pictures: pieces of The Hours and small paintings, offered in
# Change Avatar (which lists every picture under plasma/avatars).
tree "$SRC/share/plasma/avatars/Monet" "$DATADIR/plasma/avatars/Monet"
for applet in org.monet.menu org.monet.games org.monet.quick org.monet.placard org.monet.clock org.monet.weather \
    org.monet.calendar org.monet.nowplaying org.monet.notes org.monet.frame; do
    tree "$SRC/share/plasma/plasmoids/$applet" "$DATADIR/plasma/plasmoids/$applet"
done
# The desktop widgets share one glass.
for applet in org.monet.weather org.monet.calendar org.monet.nowplaying org.monet.notes; do
    install -m 644 "$SRC/share/monet/widgets/Glass.qml" "$DATADIR/plasma/plasmoids/$applet/contents/ui/Glass.qml"
done
fill "$DATADIR/plasma/wallpapers/org.monet.hours/contents/ui/main.qml" \
    "$DATADIR"/plasma/plasmoids/org.monet.*/contents/ui/*.qml
install -d "$DATADIR/color-schemes" "$DATADIR/konsole"
install -m 644 "$SRC"/share/color-schemes/*.colors "$DATADIR/color-schemes/"
install -m 644 "$SRC"/share/konsole/* "$DATADIR/konsole/"
for theme in Monet MonetDark MonetSolid MonetDarkSolid; do
    tree "$SRC/share/Kvantum/$theme" "$DATADIR/Kvantum/$theme"
done
# Window frames: glass title bars with dabs of paint for buttons.
for theme in Monet MonetSolid MonetSmoke MonetSmokeSolid; do
    tree "$SRC/share/aurorae/themes/$theme" "$DATADIR/aurorae/themes/$theme"
done
tree "$SRC/share/fonts/monet" "$DATADIR/fonts/monet"
command -v fc-cache >/dev/null && fc-cache -f "$DATADIR/fonts/monet" >/dev/null 2>&1 || true

put 644 "$SRC/systemd/monet-sync.service" "$UNITDIR/monet-sync.service"
put 644 "$SRC/systemd/monet-windows-setup.service" "$UNITDIR/monet-windows-setup.service"
put 644 "$SRC/systemd/user/monet-light.service" "$USERUNITDIR/monet-light.service"
put 644 "$SRC/systemd/user/monet-light.timer" "$USERUNITDIR/monet-light.timer"
put 644 "$SRC/systemd/user/monet-light-sync.service" "$USERUNITDIR/monet-light-sync.service"
put 644 "$SRC/systemd/user/monet-light-sync.path" "$USERUNITDIR/monet-light-sync.path"
put 644 "$SRC/systemd/user/monet-fresh.service" "$USERUNITDIR/monet-fresh.service"

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
    systemctl --global enable monet-light.timer monet-light-sync.path monet-fresh.service
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
    # KDE's About page reads Bazzite's name, mark, version and site from here,
    # over os-release: Monet's instead.
    cat > /etc/xdg/kcm-about-distrorc <<ABOUT
[General]
LogoPath=$DATADIR/icons/hicolor/scalable/apps/monet.svg
Name=Monet
Version=$("$BINDIR/monet" --version 2>/dev/null | cut -d' ' -f2)
Variant=
Website=https://github.com/HappyHamster135/Monet
ABOUT
    # New accounts start with Monet's look, so Plasma lays out Monet's islands
    # and widgets itself as it first starts, instead of KDE's to be replaced.
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage org.monet.desktop
    # Bazzite's greetings: its setup portal and announcements at the first
    # sign-in, and its welcome in every new terminal. Monet Setup and Monet
    # Settings have that covered.
    rm -f /etc/skel/.config/autostart/bazzite-portal.desktop /etc/xdg/autostart/bazzite-announcement.desktop \
        /etc/profile.d/user-motd.sh
    # And KDE's welcome, which Plasma starts at the first sign-in and after updates.
    printf '[General]\nLastSeenVersion=9999\nShowUpdatePage=false\n' > /etc/xdg/plasma-welcomerc
    # Change Avatar offers Monet's pictures alone, not KDE's dragon and photos.
    find "$DATADIR/plasma/avatars" -mindepth 1 -maxdepth 1 ! -name Monet -exec rm -rf {} +
    # The app menu's first favorites, over Bazzite's (KDE's settings, its portal).
    printf '[General]\nPrepend=%s\nIgnoreDefaults=true\n' \
        'preferred://browser;steam.desktop;org.kde.dolphin.desktop;org.kde.konsole.desktop;io.github.kolunmi.Bazaar.desktop;monet-settings.desktop;' \
        > /etc/xdg/kicker-extra-favoritesrc
    # The Store's front page (Bazaar reads these two files): Monet's picks under
    # strips of The Hours, without Bazzite's install notes.
    if [ -d /usr/share/ublue-os/bazaar ]; then
        tree "$SRC/share/monet/store" "$DATADIR/monet/store"
        rm -f "$DATADIR"/monet/store/*.yaml
        put 644 "$SRC/share/monet/store/main.yaml" /usr/share/ublue-os/bazaar/main.yaml
        put 644 "$SRC/share/monet/store/content.yaml" /usr/share/ublue-os/bazaar/content.yaml
    fi
    # The PC's boot menu names Monet's entry from the text before "release".
    if grep -q " release " /etc/system-release 2>/dev/null; then
        release="$(sed 's/^.* release /Monet release /' /etc/system-release)"
        rm -f /etc/system-release
        echo "$release" > /etc/system-release
    fi
    # Bazzite's own menu entries name their pictures by path, which the icon
    # theme can't paint over: point them at Monet's paintings.
    for entry in bazzite-documentation:monet-documentation discourse:monet-discourse bbrew:monet-bbrew; do
        desktop="/usr/share/applications/${entry%%:*}.desktop"
        [ -f "$desktop" ] && sed -i "s|^Icon=/.*|Icon=${entry#*:}|" "$desktop"
    done
    # The sign-in screen (KDE's Plasma Login Manager, which Bazzite's desktop
    # keeps): the harbor at night, over Bazzite's picture.
    if [ -d /usr/lib/plasmalogin ]; then
        printf '[Greeter]\nWallpaperPluginId=org.kde.image\n\n[Greeter][Wallpaper][org.kde.image][General]\nImage=file://%s\nPreviewImage=file://%s\n' \
            "$DATADIR/wallpapers/Monet/contents/hours/night.jpg" "$DATADIR/wallpapers/Monet/contents/hours/night.jpg" \
            > /usr/lib/plasmalogin/defaults.conf
        # Its fields, buttons and pointer are Monet's too: it draws them with
        # the colors, icons, Plasma style and pointer in its own home. Linked
        # afresh at every boot, so a new Monet reaches PCs that have one already.
        install -d "$DATADIR/monet/greeter"
        printf '[Theme]\nname=monet\n' > "$DATADIR/monet/greeter/plasmarc"
        { cat "$SRC/share/color-schemes/MonetDark.colors"
          printf '\n[General]\nfont=Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n\n[Icons]\nTheme=Monet\n'; } > "$DATADIR/monet/greeter/kdeglobals"
        printf '[Mouse]\ncursorTheme=Monet-cursors\n' > "$DATADIR/monet/greeter/kcminputrc"
        install -d /usr/lib/tmpfiles.d
        cat > /usr/lib/tmpfiles.d/monet-greeter.conf <<TMP
d /var/lib/plasmalogin/.config 0755 plasmalogin plasmalogin -
L+ /var/lib/plasmalogin/.config/plasmarc - - - - $DATADIR/monet/greeter/plasmarc
L+ /var/lib/plasmalogin/.config/kdeglobals - - - - $DATADIR/monet/greeter/kdeglobals
L+ /var/lib/plasmalogin/.config/kcminputrc - - - - $DATADIR/monet/greeter/kcminputrc
TMP
    fi
    # The lock screen: Plasma reads it from its desktop shell, not the global
    # theme. Monet's goes in beside KDE's files, and KDE's LockScreen.qml
    # becomes one that opens Monet's, or KDE's own if Monet's can't load.
    # Only where KDE keeps it as Plasma 6.7 does; otherwise KDE's stays.
    lock=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen
    if [ -f "$lock/LockScreenUi.qml" ] && [ -f "$lock/MediaControls.qml" ]; then
        install -m 644 "$SRC/share/monet/lockscreen/MonetLockScreen.qml" "$lock/MonetLockScreen.qml"
        install -m 644 "$SRC/share/monet/lockscreen/LockScreen.qml" "$lock/LockScreen.qml"
    fi
    # The widget gallery (Add Widgets…) lives in the desktop shell as well.
    # KDE's file is kept as KdeWidgetExplorer.qml, and WidgetExplorer.qml
    # becomes one that opens Monet's gallery, or KDE's if Monet's can't load.
    explorer=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/explorer
    if [ -f "$explorer/WidgetExplorer.qml" ] && [ -f "$explorer/AppletDelegate.qml" ]; then
        [ -f "$explorer/KdeWidgetExplorer.qml" ] || mv "$explorer/WidgetExplorer.qml" "$explorer/KdeWidgetExplorer.qml"
        install -m 644 "$SRC/share/monet/explorer/MonetWidgetExplorer.qml" "$explorer/MonetWidgetExplorer.qml"
        install -m 644 "$SRC/share/monet/explorer/WidgetExplorer.qml" "$explorer/WidgetExplorer.qml"
    fi
    # And edit mode, around the shrunken desktop while widgets are added or
    # moved: KDE's kept as KdeDesktopEditMode.qml, and DesktopEditMode.qml opens
    # Monet's lighter one, or KDE's if Monet's can't load.
    views=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/views
    if [ -f "$views/DesktopEditMode.qml" ] && [ -f "$views/Desktop.qml" ]; then
        [ -f "$views/KdeDesktopEditMode.qml" ] || mv "$views/DesktopEditMode.qml" "$views/KdeDesktopEditMode.qml"
        install -m 644 "$SRC/share/monet/editmode/MonetDesktopEditMode.qml" "$views/MonetDesktopEditMode.qml"
        install -m 644 "$SRC/share/monet/editmode/DesktopEditMode.qml" "$views/DesktopEditMode.qml"
    fi
    # The password prompt: KDE's agent built with Monet's page (image/password),
    # started instead of KDE's build. Without it, KDE's prompt stays.
    if [ -x "$SRC/password/monet-password" ]; then
        install -m 755 "$SRC/password/monet-password" "$LIBEXECDIR/monet-password"
        install -d "$USERUNITDIR/plasma-polkit-agent.service.d"
        printf '[Service]\nExecStart=\nExecStart=%s\n' "$LIBEXECDIR/monet-password" \
            > "$USERUNITDIR/plasma-polkit-agent.service.d/monet.conf"
    fi
else
    command -v restorecon >/dev/null && restorecon -R "$BINDIR/monet" "$LIBEXECDIR" "$DATADIR/monet" \
        "$UNITDIR/monet-sync.service" "$UNITDIR/monet-windows-setup.service" /etc/polkit-1/rules.d/49-monet.rules 2>/dev/null || true
    systemctl daemon-reload
    for unit in monet-sync.service monet-windows-setup.service; do
        systemctl enable --now "$unit" >/dev/null 2>&1 || systemctl enable "$unit"
    done
    systemctl --global enable monet-light.timer monet-light-sync.path monet-fresh.service >/dev/null 2>&1 || true
fi
