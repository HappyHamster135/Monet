#!/usr/bin/env bash
# Build/test the private Qt style used only by More Settings. Qt 6 development
# packages and CMake are build dependencies; the installed OS needs only Qt.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:?destination plugin directory required}"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
cmake -S "$ROOT/linux/settings-style" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --parallel 2
ctest --test-dir "$BUILD" --output-on-failure
install -Dm755 "$BUILD/plugins/styles/libmonetsettings.so" "$DEST/styles/libmonetsettings.so"
