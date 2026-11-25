#!/bin/sh
# KDE's dpms.xml describes per-output power control (license in the XML).
set -eu
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
wayland-scanner client-header "$src/dpms.xml" "$tmp/dpms.h"
wayland-scanner private-code "$src/dpms.xml" "$tmp/dpms.c"
cc -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wno-unused-parameter -O2 -fPIC -shared \
    -Wl,-z,defs,-z,relro,-z,now -I"$tmp" "$src/display-power.c" "$tmp/dpms.c" -lwayland-client -o "$tmp/library"
install -Dm755 "$tmp/library" "$1"
