#!/usr/bin/env bash
# Assembles the downloadable folders for a release.
#
#   tools/package.sh linux   <monet binary>        <output dir> [<monet-bridge.exe>]
#   tools/package.sh windows <monet-bridge.exe>    <output dir>
#
# With a monet-bridge.exe, the Linux package also carries the Windows files,
# so Monet can set up Windows by itself.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND="$1" BIN="$2" OUT="$3" BRIDGE="${4:-}"

rm -rf "$OUT"
mkdir -p "$OUT"
cp "$ROOT/LICENSE" "$OUT/LICENSE.txt"

case "$KIND" in
    linux)
        cp -r "$ROOT/linux/." "$OUT/"
        # What's new, for Settings → Updates and the note after an update (monet-quick whats-new).
        cp "$ROOT/RELEASE_NOTES.md" "$OUT/share/monet/release-notes.md"
        mkdir -p "$OUT/icons"
        cp "$ROOT/branding/monet.svg" "$ROOT/branding/monet-windows.svg" "$ROOT/branding/monet-quick-symbolic.svg" "$OUT/icons/"
        install -m 755 "$BIN" "$OUT/monet"
        chmod 755 "$OUT/install.sh" "$OUT/uninstall.sh" "$OUT"/libexec/*
        if [ -n "$BRIDGE" ]; then
            "$0" windows "$BRIDGE" "$OUT/windows" >/dev/null
        fi
        ;;
    windows)
        cp "$ROOT"/windows/*.ps1 "$ROOT"/windows/*.cmd "$ROOT/windows/monet.ico" "$OUT/"
        # The painting a Windows that Monet installs wears (Install-Monet.ps1 -FromMonet), and
        # Monet Bridge's cover over Windows: that painting, the mark and Monet's serif.
        cp "$ROOT/linux/share/wallpapers/Monet/contents/hours/day.jpg" "$OUT/wallpaper.jpg"
        cp "$ROOT/linux/share/wallpapers/Monet/contents/hours/day.jpg" "$OUT/cover.jpg"
        cp "$ROOT/setup/art/mark.png" "$OUT/monet-mark.png"
        cp "$ROOT/linux/share/fonts/monet/Fraunces72ptSuperSoft-Light.ttf" "$OUT/Fraunces-Light.ttf"
        cp "$ROOT/linux/share/fonts/monet/Fraunces72ptSuperSoft-Regular.ttf" "$OUT/Fraunces-Regular.ttf"
        cp "$ROOT/linux/share/fonts/monet/OFL.txt" "$OUT/OFL-Fraunces.txt"
        sed -i "s/@VERSION@/$(cat "$ROOT/VERSION")/" "$OUT/Install-Monet.ps1"
        cp "$BIN" "$OUT/monet-bridge.exe"
        ;;
    *)
        echo "Unknown kind: $KIND" >&2
        exit 1
        ;;
esac
echo "Packaged $KIND into $OUT"
