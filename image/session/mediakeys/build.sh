#!/bin/sh
# Use the session stage's Fedora source, after rpmbuild has applied its patches.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source=$1
work=$2
out=$3
cmake -S "$here" -B "$work/build" -DUPSTREAM_SOURCE="$source" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON
cmake --build "$work/build" --parallel 2 --target mprisservice
install -m 755 "$work/build/bin/kf6/kded/mprisservice.so" "$out/mprisservice.so"
mkdir -p "$work/monet-session"
cp -r "$here" "$work/monet-session/mediakeys"
cp "$here/../bundle.py" "$work/monet-session/bundle.py"
tar -cJf "$out/source.tar.xz" -C "$source" libkmpris LICENSES -C "$work" monet-session
cp "$here/README.md" "$here/guard.py" "$out/"
python3 "$here/guard.py" seal "$out"
