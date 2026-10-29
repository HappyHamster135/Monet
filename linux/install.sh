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
and your Windows games show up in Games in the panel, beside the ones in Monet.

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

# More settings' pages kept out of sight: each one listed (a KDE page id a line) that the
# file's "KDE Control Module Restrictions" group doesn't have yet, as false.
hide_pages() { # hide_pages <kdeglobals> <list>
    local add="" kcm
    touch "$1"
    for kcm in $(grep -v '^#' "$2"); do
        grep -q "^$kcm\(\[\$i\]\)\?=" "$1" || add="$add$kcm=false
"
    done
    [ -n "$add" ] || return 0
    if grep -q '^\[KDE Control Module Restrictions\]' "$1"; then
        ADD="$add" awk '{ print } /^\[KDE Control Module Restrictions\]/ { printf "%s", ENVIRON["ADD"] }' "$1" > "$1.monet" &&
            cat "$1.monet" > "$1" && rm -f "$1.monet"
    else
        printf '\n[KDE Control Module Restrictions]\n%s' "$add" >> "$1"
    fi
}

# Fills in paths in files that were copied as they are.
fill() {
    for f in "$@"; do
        sed -i -e "s|@BINDIR@|$BINDIR|g" -e "s|@DATADIR@|$DATADIR|g" -e "s|@LIBEXECDIR@|$LIBEXECDIR|g" "$f"
    done
}

install -D -m 755 "$SRC/monet" "$BINDIR/monet"
for tool in monet-session monet-look monet-profile monet-light monet-quick monet-weather monet-resume monet-leave monet-files-session monet-browser-session monet-editor-session monet-pdf-session monet-bookmarks monet-fresh monet-widgets monet-apps monet-charge monet-paint monet-games monet-settings monet-store monet-store-jobs; do
    put 755 "$SRC/libexec/$tool" "$LIBEXECDIR/$tool"
done
install -D -m 755 "$SRC/libexec/monet-prepare-windows" "$LIBEXECDIR/monet-prepare-windows"
# Ready when you come back (Settings → Play on Windows): root's part.
put 755 "$SRC/libexec/monet-ready" "$LIBEXECDIR/monet-ready"
# Earlier versions of everyone's files (Settings → Backups): root's part.
put 755 "$SRC/libexec/monet-keep" "$LIBEXECDIR/monet-keep"
# A new Monet that doesn't start goes back by itself; Reset this PC; and an encrypted disk
# that unlocks with the PC's security chip. Root's, run by systemd (Reset after a password).
for tool in monet-boot monet-reset monet-seal; do
    put 755 "$SRC/libexec/$tool" "$LIBEXECDIR/$tool"
done
# A controller or headset paired in Windows works in Monet too: root's part.
put 755 "$SRC/libexec/monet-pairings" "$LIBEXECDIR/monet-pairings"
# Settings → Security's fixes: root's part, always after an administrator's password.
put 755 "$SRC/libexec/monet-secure" "$LIBEXECDIR/monet-secure"
# A guest who leaves nothing behind (Settings → Accounts): root's part, the same.
put 755 "$SRC/libexec/monet-guest" "$LIBEXECDIR/monet-guest"
# A guest's things go when they sign out: logind ends what they left running (only theirs),
# and su never becomes them (their empty password is for the sign-in screen).
if [ "$IMAGE" = 1 ]; then logind=/usr/lib/systemd/logind.conf.d; else logind=/etc/systemd/logind.conf.d; fi
install -D -m 644 "$SRC/systemd/logind-monet-guest.conf" "$logind/50-monet-guest.conf"
if [ -f /etc/pam.d/su ] && ! grep -q 'user != guest' /etc/pam.d/su; then
    sed -i '/^auth.*pam_rootok\.so/a auth            requisite       pam_succeed_if.so user != guest quiet' /etc/pam.d/su
fi
# Windows' Games folder for Steam on both sides, and what's saved in Windows brought over.
put 755 "$SRC/libexec/monet-windows-drive" "$LIBEXECDIR/monet-windows-drive"
# The firewall's Monet zone: from the network, only what Monet uses comes in. A Monet image
# makes it the default and remembers the system's own to go back to (Settings → Security);
# added to an existing system it's only there for that switch, and nothing changes.
if [ "$IMAGE" = 1 ]; then
    install -D -m 644 "$SRC/firewalld/monet.xml" /usr/lib/firewalld/zones/monet.xml
    if command -v firewall-offline-cmd >/dev/null; then
        before="$(firewall-offline-cmd --get-default-zone 2>/dev/null || :)"
        if [ -n "$before" ] && [ "$before" != monet ]; then
            install -d "$DATADIR/monet"
            echo "$before" > "$DATADIR/monet/firewall-zone-before"
        fi
        firewall-offline-cmd --set-default-zone=monet >/dev/null \
            || echo "warning: the firewall keeps the system's own zone" >&2
    fi
else
    install -D -m 644 "$SRC/firewalld/monet.xml" /etc/firewalld/zones/monet.xml
fi

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
# Games, the app with every game (the panel's Games button and Windows+G open it).
put 644 "$SRC/share/applications/monet-games.desktop" "$DATADIR/applications/monet-games.desktop"
# The Store, Monet's own: Flathub's apps, and the Windows apps on the PC.
put 644 "$SRC/share/applications/monet-store.desktop" "$DATADIR/applications/monet-store.desktop"
# Windows+Alt+G: the last 30 seconds of a game, saved (its shortcut comes with Monet's look).
put 644 "$SRC/share/applications/monet-replay.desktop" "$DATADIR/applications/monet-replay.desktop"
put 644 "$SRC/share/applications/monet-windows-program.desktop" "$DATADIR/applications/monet-windows-program.desktop"
# Earlier versions, in Files' menu.
put 644 "$SRC/share/kio/servicemenus/monet-earlier.desktop" "$DATADIR/kio/servicemenus/monet-earlier.desktop"
put 644 "$SRC/share/kio/servicemenus/monet-windows-program.desktop" "$DATADIR/kio/servicemenus/monet-windows-program.desktop"

# The look: paintings, the Plasma style and global theme, Monet's widgets,
# colors, the glass app style, the terminal's colors and the fonts.
tree "$SRC/share/wallpapers/Monet" "$DATADIR/wallpapers/Monet"
tree "$SRC/share/plasma/wallpapers/org.monet.hours" "$DATADIR/plasma/wallpapers/org.monet.hours"
tree "$SRC/share/plasma/desktoptheme/monet" "$DATADIR/plasma/desktoptheme/monet"
tree "$SRC/share/plasma/desktoptheme/monet-matte" "$DATADIR/plasma/desktoptheme/monet-matte"
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
    org.monet.calendar org.monet.nowplaying org.monet.notes org.monet.frame org.monet.system org.monet.played \
    org.monet.timer org.monet.worldclock org.monet.batteries org.monet.sound; do
    tree "$SRC/share/plasma/plasmoids/$applet" "$DATADIR/plasma/plasmoids/$applet"
done
# The desktop widgets share one glass.
put 644 "$SRC/share/monet/bar-defaults.js" "$DATADIR/monet/bar-defaults.js"
for applet in org.monet.weather org.monet.calendar org.monet.nowplaying org.monet.notes org.monet.system \
    org.monet.played org.monet.timer org.monet.worldclock org.monet.batteries; do
    install -m 644 "$SRC/share/monet/widgets/Glass.qml" "$DATADIR/plasma/plasmoids/$applet/contents/ui/Glass.qml"
done
# The Calendar and the bar's clock share the month, the day's note and the notes themselves.
for applet in org.monet.calendar org.monet.clock; do
    for part in Month DayNotes NoteStore NotesPopup; do
        install -m 644 "$SRC/share/monet/widgets/$part.qml" "$DATADIR/plasma/plasmoids/$applet/contents/ui/$part.qml"
    done
done
# Screen-aware layout and shared calendar positioning.
for applet in org.monet.sound org.monet.quick; do
    install -m 644 "$SRC/share/monet/widgets/ActionButton.qml" "$DATADIR/plasma/plasmoids/$applet/contents/ui/ActionButton.qml"
done
for applet in "$DATADIR"/plasma/plasmoids/org.monet.*; do
    for part in LayoutGuard.qml LayoutMath.js NoteLogic.js PanelFit.qml ClockFormat.qml; do
        install -m 644 "$SRC/share/monet/widgets/$part" "$applet/contents/ui/$part"
    done
done
fill "$DATADIR/plasma/wallpapers/org.monet.hours/contents/ui/main.qml" \
    "$DATADIR"/plasma/plasmoids/org.monet.*/contents/ui/*.qml
install -d "$DATADIR/color-schemes" "$DATADIR/konsole"
install -m 644 "$SRC"/share/color-schemes/*.colors "$DATADIR/color-schemes/"
install -m 644 "$SRC"/share/konsole/* "$DATADIR/konsole/"
for theme in Monet MonetDark MonetMatte MonetDarkMatte MonetSolid MonetDarkSolid; do
    tree "$SRC/share/Kvantum/$theme" "$DATADIR/Kvantum/$theme"
done
# Window frames: glass title bars with dabs of paint for buttons.
for theme in Monet MonetMatte MonetSolid MonetSmoke MonetSmokeMatte MonetSmokeSolid; do
    tree "$SRC/share/aurorae/themes/$theme" "$DATADIR/aurorae/themes/$theme"
done
# Snap layouts, edges and corners, full height, Snap Assist (a KWin script), and windows
# gliding to where they're put (a KWin effect, in place of KWin's own Stretch).
tree "$SRC/share/kwin/scripts/monet-snap" "$DATADIR/kwin/scripts/monet-snap"
tree "$SRC/share/kwin/effects/monet-motion" "$DATADIR/kwin/effects/monet-motion"
tree "$SRC/share/fonts/monet" "$DATADIR/fonts/monet"
command -v fc-cache >/dev/null && fc-cache -f "$DATADIR/fonts/monet" >/dev/null 2>&1 || true
# The sounds, felt and glass; KDE's Ocean plays the few Monet leaves out.
tree "$SRC/share/sounds/monet" "$DATADIR/sounds/monet"
# Monet's words in other languages (tools/make-translations.py): one catalog, also
# under the names Plasma looks for a widget's and the painting's words by.
for catalog in "$SRC"/share/locale/*/LC_MESSAGES/monet.mo; do
    [ -f "$catalog" ] || continue
    words="$DATADIR/locale/${catalog#"$SRC/share/locale/"}"
    install -D -m 644 "$catalog" "$words"
    for applet in "$DATADIR"/plasma/plasmoids/org.monet.*; do
        ln -sfn monet.mo "${words%/*}/plasma_applet_${applet##*/}.mo"
    done
    ln -sfn monet.mo "${words%/*}/plasma_wallpaper_org.monet.hours.mo"
done
# Monet's names for KDE's apps (Files, Terminal...) in their window titles: a language of
# Monet's own, which Plasma puts before yours as it starts (plasma-workspace/env).
for catalog in "$SRC"/share/locale/*@monet/LC_MESSAGES/*.mo; do
    [ -f "$catalog" ] || continue
    install -D -m 644 "$catalog" "$DATADIR/locale/${catalog#"$SRC/share/locale/"}"
done
install -D -m 644 "$SRC/share/plasma-workspace/env/monet-names.sh" /etc/xdg/plasma-workspace/env/monet-names.sh
# Animations where the processor draws the screen too (KWin leaves them out there).
install -D -m 644 "$SRC/share/plasma-workspace/env/monet-motion.sh" /etc/xdg/plasma-workspace/env/monet-motion.sh
install -D -m 644 "$SRC/share/plasma-workspace/env/monet-accessibility.sh" /etc/xdg/plasma-workspace/env/monet-accessibility.sh
# Monet's own partitions (boot, EFI) out of Files' Devices.
install -D -m 644 "$SRC/udev/90-monet-system.rules" /etc/udev/rules.d/90-monet-system.rules

put 644 "$SRC/systemd/monet-sync.service" "$UNITDIR/monet-sync.service"
put 644 "$SRC/systemd/monet-windows-setup.service" "$UNITDIR/monet-windows-setup.service"
for unit in monet-update.service monet-update.timer monet-apps.service monet-apps.timer monet-crash@.service monet-charge.service; do
    put 644 "$SRC/systemd/$unit" "$UNITDIR/$unit"
done
# When an app crashes, Monet's note instead of KDE's crash reporter: beside each
# crash systemd-coredump catches, linked by hand (systemctl enable can't).
install -d "$UNITDIR/systemd-coredump@.service.wants"
ln -sfn ../monet-crash@.service "$UNITDIR/systemd-coredump@.service.wants/monet-crash@.service"
put 644 "$SRC/systemd/user/monet-light.service" "$USERUNITDIR/monet-light.service"
put 644 "$SRC/systemd/user/monet-light.timer" "$USERUNITDIR/monet-light.timer"
put 644 "$SRC/systemd/user/monet-light-sync.service" "$USERUNITDIR/monet-light-sync.service"
put 644 "$SRC/systemd/user/monet-light-sync.path" "$USERUNITDIR/monet-light-sync.path"
put 644 "$SRC/systemd/user/monet-fresh.service" "$USERUNITDIR/monet-fresh.service"
put 644 "$SRC/systemd/user/monet-keys.service" "$USERUNITDIR/monet-keys.service"
put 644 "$SRC/systemd/user/monet-names.path" "$USERUNITDIR/monet-names.path"
put 644 "$SRC/systemd/user/monet-names.service" "$USERUNITDIR/monet-names.service"
put 644 "$SRC/systemd/user/monet-frames.path" "$USERUNITDIR/monet-frames.path"
put 644 "$SRC/systemd/user/monet-frames.service" "$USERUNITDIR/monet-frames.service"
put 644 "$SRC/systemd/user/monet-zen.path" "$USERUNITDIR/monet-zen.path"
put 644 "$SRC/systemd/user/monet-zen.service" "$USERUNITDIR/monet-zen.service"
# OneDrive in Files, for each person who connects it (Settings → Storage).
put 644 "$SRC/systemd/user/monet-onedrive.service" "$USERUNITDIR/monet-onedrive.service"
# Ready when you come back: armed on the way to Windows, decided before the sign-in
# screen, and locked before the desktop shows.
for unit in monet-ready-leave.service monet-ready-boot.service; do
    put 644 "$SRC/systemd/$unit" "$UNITDIR/$unit"
done
put 644 "$SRC/systemd/user/monet-ready-lock.service" "$USERUNITDIR/monet-ready-lock.service"
# The question, as in Windows, when a program starts accepting connections (Settings → Security).
put 644 "$SRC/systemd/user/monet-listening.service" "$USERUNITDIR/monet-listening.service"
# The last 30 seconds, kept while Games & Controllers' switch is on (each person turns it on).
put 644 "$SRC/systemd/user/monet-replay.service" "$USERUNITDIR/monet-replay.service"
# Windows' Games folder into Steam's libraries before Steam starts with the session.
put 644 "$SRC/systemd/user/app-steam@autostart.service.d/monet-steam-share.conf" \
    "$USERUNITDIR/app-steam@autostart.service.d/monet-steam-share.conf"
# Backups: earlier versions every hour (the homes made a subvolume of their own
# once, before the sign-in screen), and the copy on a drive when it's plugged in.
for unit in monet-keep-prepare.service monet-keep.service monet-keep.timer; do
    put 644 "$SRC/systemd/$unit" "$UNITDIR/$unit"
done
put 644 "$SRC/systemd/user/monet-backup.service" "$USERUNITDIR/monet-backup.service"
put 644 "$SRC/systemd/user/monet-backup.timer" "$USERUNITDIR/monet-backup.timer"
# Safety: a new Monet on trial at its first start, Reset this PC before the sign-in screen,
# and the encrypted disk's key into the security chip (at the first start, and again when needed).
for unit in monet-boot-arm.service monet-boot-check.service monet-reset.service monet-seal.service \
    monet-seal-relearn.service; do
    put 644 "$SRC/systemd/$unit" "$UNITDIR/$unit"
done
# Windows' Bluetooth pairings, taken at every start.
put 644 "$SRC/systemd/monet-pairings.service" "$UNITDIR/monet-pairings.service"
# Windows' drive, opened at every start when it's safe: its Games folder, then its captures.
for unit in monet-windows-drive.service monet-windows-files.service; do
    put 644 "$SRC/systemd/$unit" "$UNITDIR/$unit"
done
# The guest's home as new before every sign-in screen (while there's a guest).
put 644 "$SRC/systemd/monet-guest-wipe.service" "$UNITDIR/monet-guest-wipe.service"

# Monet updates itself, once a day (monet-update.timer: the new Monet starts at
# the next restart; Settings → Updates turns it off). Bazzite's and KDE's own
# updaters stay masked so only Monet's runs: masked, because Bazzite turns some
# of them on from /usr, where disabling can't reach.
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
    "$DATADIR/monet/gtk" "$DATADIR/monet/zen" "$DATADIR/monet/games" "$DATADIR/monet/settings-app" "$DATADIR/monet/store-app"
install -d "$DATADIR/monet"
cp -r "$SRC/share/monet/winpe" "$DATADIR/monet/winpe"
cp -r "$SRC/share/monet/textures" "$DATADIR/monet/textures"
# Pictures for Monet Settings, cut from the paintings.
cp -r "$SRC/share/monet/settings" "$DATADIR/monet/settings"
# Games' window (monet-games), and Settings' (monet-settings).
cp -r "$SRC/share/monet/games" "$DATADIR/monet/games"
tree "$SRC/share/monet/window-buttons" "$DATADIR/monet/window-buttons"
cp -r "$SRC/share/monet/settings-app" "$DATADIR/monet/settings-app"
# The Store's window (monet-store), and its front page: Monet's picks under strips of The Hours.
cp -r "$SRC/share/monet/store-app" "$DATADIR/monet/store-app"
tree "$SRC/share/monet/store" "$DATADIR/monet/store"
# The private layout style is built and tested when assembling the release.
if [ -d "$SRC/lib/monet/qt" ]; then
    tree "$SRC/lib/monet/qt" "$PREFIX/lib/monet/qt"
fi
rm -f "$DATADIR/monet/store/main.yaml"
cp -r "$SRC/share/monet/gtk" "$DATADIR/monet/gtk"
# Zen's look, which monet-quick zen puts into each Zen profile.
cp -r "$SRC/share/monet/zen" "$DATADIR/monet/zen"
# Windows games Monet always lists, even before Windows has found them.
install -m 644 "$SRC/share/monet/windows-games.json" "$DATADIR/monet/windows-games.json"
# Apps' menu names in each language, which monet-look gives the apps it renames.
install -m 644 "$SRC/share/monet/names.tsv" "$DATADIR/monet/names.tsv"
install -m 644 "$SRC/share/monet/hidden-settings-pages" "$DATADIR/monet/hidden-settings-pages"
# What's new in this Monet (tools/package.sh puts the release notes in the package).
if [ -f "$SRC/share/monet/release-notes.md" ]; then
    install -m 644 "$SRC/share/monet/release-notes.md" "$DATADIR/monet/release-notes.md"
fi
if [ -d "$SRC/windows" ]; then
    cp -r "$SRC/windows" "$DATADIR/monet/windows"
fi
chmod -R u=rwX,go=rX "$DATADIR/monet"
put 644 "$SRC/autostart/monet-session.desktop" /etc/xdg/autostart/monet-session.desktop

# Allow one-click switching without a password. /usr/local is a link to
# /var/usrlocal on Fedora Atomic, so allow both spellings of the path.
# Battery care's helper too: it only writes the battery's charge limit.
real_bin="$(readlink -f "$BINDIR/monet")"
programs="[\"$BINDIR/monet\", \"$real_bin\", \"$LIBEXECDIR/monet-charge\", \"$(readlink -f "$LIBEXECDIR/monet-charge")\", \"$LIBEXECDIR/monet-ready\", \"$(readlink -f "$LIBEXECDIR/monet-ready")\", \"$LIBEXECDIR/monet-keep\", \"$(readlink -f "$LIBEXECDIR/monet-keep")\", \"$LIBEXECDIR/monet-windows-drive\", \"$(readlink -f "$LIBEXECDIR/monet-windows-drive")\"]"
install -d -m 755 /etc/polkit-1/rules.d
sed -e "s|@PROGRAMS@|$programs|" "$SRC/polkit/49-monet.rules" > /etc/polkit-1/rules.d/49-monet.rules
chmod 644 /etc/polkit-1/rules.d/49-monet.rules

if [ "$IMAGE" = 1 ]; then
    systemctl enable monet-sync.service monet-windows-setup.service monet-update.timer monet-apps.timer monet-charge.service
    systemctl --global enable monet-light.timer monet-light-sync.path monet-fresh.service monet-keys.service monet-names.path monet-frames.path monet-zen.path
    systemctl enable monet-ready-leave.service monet-ready-boot.service
    systemctl --global enable monet-ready-lock.service monet-listening.service
    systemctl enable monet-keep-prepare.service monet-keep.timer
    systemctl --global enable monet-backup.timer
    systemctl enable monet-boot-arm.service monet-boot-check.service monet-reset.service monet-seal.service \
        monet-seal-relearn.service
    systemctl enable monet-pairings.service
    systemctl enable monet-windows-drive.service monet-windows-files.service
    systemctl enable monet-guest-wipe.service
    # Monet's name, version, mark and links where the system describes itself (KDE's
    # About page, system information, the PC's name on the network, new boot entries' names).
    # ID, VARIANT and the build's own ids stay Bazzite's, which its tools rely on.
    os_release=/usr/lib/os-release
    monet_version="$("$BINDIR/monet" --version 2>/dev/null | cut -d' ' -f2)"
    sed -i -e 's/^PRETTY_NAME=.*/PRETTY_NAME="Monet"/' -e 's/^NAME=.*/NAME="Monet"/' \
        -e "s/^VERSION=.*/VERSION=\"${monet_version:-0}\"/" -e 's/^BOOTLOADER_NAME=.*/BOOTLOADER_NAME="Monet"/' \
        -e '/^LOGO=/d' -e '/^HOME_URL=/d' -e '/^SUPPORT_URL=/d' -e '/^BUG_REPORT_URL=/d' -e '/^DEFAULT_HOSTNAME=/d' \
        -e '/^DOCUMENTATION_URL=/d' \
        "$os_release"
    cat >> "$os_release" <<OSR
LOGO=monet
HOME_URL="https://github.com/HappyHamster135/Monet"
SUPPORT_URL="https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md"
BUG_REPORT_URL="https://github.com/HappyHamster135/Monet/issues"
DOCUMENTATION_URL="https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md"
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
    # And with Monet's sounds, from the first sign-in.
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file /etc/xdg/kdeglobals --group Sounds --key Theme monet
    # More settings' hidden pages, for everyone. Bazzite locks this group here ([$i], for its
    # updater), and KDE then ignores an account's own: monet-look's list never counted, and
    # KDE's Global Theme, colors, styles, frames and the rest stayed in reach (found in the test
    # VM). Into the group as it stands, locked or not.
    hide_pages /etc/xdg/kdeglobals "$SRC/share/monet/hidden-settings-pages"
    # Bazzite's greetings: its setup portal and announcements at the first
    # sign-in, and its welcome in every new terminal. Monet Setup and Monet
    # Settings have that covered.
    rm -f /etc/skel/.config/autostart/bazzite-portal.desktop /etc/xdg/autostart/bazzite-announcement.desktop \
        /etc/profile.d/user-motd.sh
    # Input Remapper, a tool for remapping keys, isn't started at every boot and sign-in (it
    # held the start up for 45 seconds before giving up, in a test VM); it's out of the menu
    # too (monet-look), as Monet's other power tools are.
    systemctl disable input-remapper.service >/dev/null 2>&1 || true
    rm -f /etc/xdg/autostart/input-remapper-autoload.desktop
    # And KDE's welcome, which Plasma starts at the first sign-in and after updates.
    printf '[General]\nLastSeenVersion=9999\nShowUpdatePage=false\n' > /etc/xdg/plasma-welcomerc
    # Zen is the browser (Monet Setup's everyday apps bring it): web links open
    # in it, unless someone picks another in Settings → Default Apps.
    browser=app.zen_browser.zen.desktop
    mimeapps=/etc/xdg/mimeapps.list
    touch "$mimeapps"
    sed -i -E '/^(x-scheme-handler\/https?|text\/html)=/d' "$mimeapps"
    grep -q '^\[Default Applications\]' "$mimeapps" || printf '\n[Default Applications]\n' >> "$mimeapps"
    sed -i "/^\[Default Applications\]/a x-scheme-handler/http=$browser\nx-scheme-handler/https=$browser\ntext/html=$browser" "$mimeapps"
    # Each kind of file opens in the app built in for it (Settings → Default
    # Apps changes it), not in whichever claims it first: the browser claims
    # pictures and PDFs too.
    while read -r app types; do
        for type in $types; do
            sed -i "\|^$type=|d" "$mimeapps"
            sed -i "/^\[Default Applications\]/a $type=$app" "$mimeapps"
        done
    done <<'DEFAULTS'
org.kde.gwenview.desktop image/jpeg image/png image/gif image/webp image/avif image/heif image/bmp image/tiff image/svg+xml
org.kde.okular.desktop application/pdf application/epub+zip image/vnd.djvu application/postscript
org.kde.haruna.desktop video/mp4 video/x-matroska video/webm video/quicktime video/x-msvideo video/mpeg video/ogg
org.kde.elisa.desktop audio/mpeg audio/flac audio/ogg audio/x-vorbis+ogg audio/x-opus+ogg audio/x-wav audio/mp4 audio/aac
org.kde.ark.desktop application/zip application/x-7z-compressed application/vnd.rar application/x-tar application/x-compressed-tar application/x-xz-compressed-tar application/zstd
org.kde.kate.desktop;org.kde.kwrite.desktop text/plain text/markdown
monet-store.desktop x-scheme-handler/appstream
monet-windows-program.desktop application/x-ms-dos-executable application/x-msdownload application/vnd.microsoft.portable-executable application/x-msi application/x-ms-installer
DEFAULTS
    command -v kwriteconfig6 >/dev/null && kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key BrowserApplication "$browser"
    # Change Avatar offers Monet's pictures alone, not KDE's dragon and photos.
    find "$DATADIR/plasma/avatars" -mindepth 1 -maxdepth 1 ! -name Monet -exec rm -rf {} +
    # The app menu's first favorites, over Bazzite's (KDE's settings, its portal).
    printf '[General]\nPrepend=%s\nIgnoreDefaults=true\n' \
        'preferred://browser;steam.desktop;org.kde.dolphin.desktop;org.kde.konsole.desktop;monet-store.desktop;monet-settings.desktop;' \
        > /etc/xdg/kicker-extra-favoritesrc
    # Bazaar, Bazzite's store, out of sight (monet-look) but kept: its front page is Monet's
    # picks too, without Bazzite's install notes.
    if [ -d /usr/share/ublue-os/bazaar ]; then
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
        install -m 644 "$SRC/share/monet/widgets/ClockFormat.qml" "$lock/ClockFormat.qml"
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
    for unit in monet-sync.service monet-windows-setup.service monet-update.timer monet-apps.timer monet-charge.service; do
        systemctl enable --now "$unit" >/dev/null 2>&1 || systemctl enable "$unit"
    done
    systemctl --global enable monet-light.timer monet-light-sync.path monet-fresh.service monet-keys.service monet-names.path monet-frames.path monet-zen.path >/dev/null 2>&1 || true
    systemctl enable --now monet-ready-leave.service >/dev/null 2>&1 || true
    systemctl enable monet-ready-boot.service >/dev/null 2>&1 || true
    systemctl --global enable monet-ready-lock.service monet-listening.service >/dev/null 2>&1 || true
    # The homes become a subvolume at the next start, before anyone signs in.
    systemctl enable monet-keep-prepare.service >/dev/null 2>&1 || true
    systemctl enable --now monet-keep.timer >/dev/null 2>&1 || true
    systemctl --global enable monet-backup.timer >/dev/null 2>&1 || true
    # Started now, so the next shutdown already puts a staged update on trial.
    systemctl enable --now monet-boot-arm.service >/dev/null 2>&1 || true
    systemctl enable monet-boot-check.service monet-reset.service monet-seal.service monet-seal-relearn.service \
        >/dev/null 2>&1 || true
    systemctl enable monet-pairings.service >/dev/null 2>&1 || true
    systemctl enable monet-windows-drive.service monet-windows-files.service >/dev/null 2>&1 || true
    systemctl enable monet-guest-wipe.service >/dev/null 2>&1 || true
fi
