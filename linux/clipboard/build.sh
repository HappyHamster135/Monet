#!/bin/sh
# ext-data-control-v1.xml comes from wayland-protocols 1.43 (license in the XML).
set -eu
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
wayland-scanner client-header "$src/ext-data-control-v1.xml" "$tmp/control.h"
wayland-scanner private-code "$src/ext-data-control-v1.xml" "$tmp/control.c"
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Wno-unused-parameter -O2 -fPIC -shared \
    -Wl,-z,defs,-z,relro,-z,now -I"$tmp" "$src/clipboard.c" "$tmp/control.c" -lwayland-client -o "$tmp/library"
install -Dm755 "$tmp/library" "$1"
