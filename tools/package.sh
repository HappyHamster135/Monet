#!/usr/bin/env bash
# Assembles the downloadable folders for a release.
#
#   tools/package.sh linux   <monet binary> <output dir> [<monet-bridge.exe> <monet-setup-check.exe>]
#   tools/package.sh windows <monet-bridge.exe>    <output dir>
#
# With a monet-bridge.exe, the Linux package also carries the Windows files,
# so Monet can set up Windows by itself.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND="$1" BIN="$2" OUT="$3" BRIDGE="${4:-}" SETUP_CHECK="${5:-}"

if [ "$KIND" = linux ] && [ -n "$BRIDGE" ] && { [ -z "$SETUP_CHECK" ] || [ ! -f "$SETUP_CHECK" ]; }; then
    echo "Windows setup packaging requires monet-setup-check.exe." >&2
    exit 1
fi

# Refuse stale source or a missing/altered signed connector before replacing output.
if [ "$KIND" = linux ]; then
    python3 "$ROOT/browser/monet-passwords/package.py"
fi

rm -rf "$OUT"
mkdir -p "$OUT"
cp "$ROOT/LICENSE" "$OUT/LICENSE.txt"

case "$KIND" in
    linux)
        cp -r "$ROOT/linux/." "$OUT/"
        cp "$ROOT/setup/monet_setup/region.py" "$OUT/libexec/monet_region.py"
        # Local validation caches are not executable package content.
        find "$OUT" -type d -name __pycache__ -prune -exec rm -rf {} +
        mkdir -p "$OUT/share/doc/monet/passwords-connector"
        for source in README.md LICENSE.upstream build.py automatic-submit.js release.json; do
            cp "$ROOT/browser/monet-passwords/$source" "$OUT/share/doc/monet/passwords-connector/"
        done
        bash "$ROOT/tools/build-settings-style.sh" "$OUT/lib/monet/qt"
        # What's new, for Settings → Updates and the note after an update (monet-quick whats-new).
        cp "$ROOT/RELEASE_NOTES.md" "$OUT/share/monet/release-notes.md"
        mkdir -p "$OUT/icons"
        cp "$ROOT/branding/monet.svg" "$ROOT/branding/monet-windows.svg" "$ROOT/branding/monet-quick-symbolic.svg" "$OUT/icons/"
        install -m 755 "$BIN" "$OUT/monet"
        chmod 755 "$OUT/install.sh" "$OUT/uninstall.sh" "$OUT"/libexec/*
        if [ -n "$BRIDGE" ]; then
            "$0" windows "$BRIDGE" "$OUT/windows" >/dev/null
            install -m 644 "$SETUP_CHECK" "$OUT/share/monet/winpe/monet-setup-check.exe"
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
