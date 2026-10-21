#!/usr/bin/env bash
# Assembles the downloadable folders for a release.
#
#   tools/package.sh linux   <monet binary>        <output dir>
#   tools/package.sh windows <monet-bridge.exe>    <output dir>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND="$1" BIN="$2" OUT="$3"

rm -rf "$OUT"
mkdir -p "$OUT"
cp "$ROOT/LICENSE" "$OUT/LICENSE.txt"

case "$KIND" in
    linux)
        cp -r "$ROOT/linux/." "$OUT/"
        mkdir -p "$OUT/icons"
        cp "$ROOT/branding/monet.svg" "$ROOT/branding/monet-windows.svg" "$OUT/icons/"
        install -m 755 "$BIN" "$OUT/monet"
        chmod 755 "$OUT/install.sh" "$OUT/uninstall.sh" "$OUT/libexec/monet-session"
        ;;
    windows)
        cp "$ROOT"/windows/*.ps1 "$ROOT"/windows/*.cmd "$ROOT/windows/monet.ico" "$OUT/"
        cp "$BIN" "$OUT/monet-bridge.exe"
        ;;
    *)
        echo "Unknown kind: $KIND" >&2
        exit 1
        ;;
esac
echo "Packaged $KIND into $OUT"
