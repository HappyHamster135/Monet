#!/bin/sh
# Build this private-ABI plugin against the final image's exact compositor/runtime.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make tar xz python3 binutils extra-cmake-modules \
    kwin-devel qt6-qtbase-devel qt6-qtbase-private-devel \
    wayland-devel libepoxy-devel libdrm-devel vulkan-loader-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d /tmp/monet-window-identity.XXXXXX)"
cmake -S "$here" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON
cmake --build "$work/build" --parallel "$(nproc)"
install -m 755 "$work/build/monet_window_identity.so" "$out/monet_window_identity.so"
mkdir "$work/monet-window-identity"
for name in CMakeLists.txt identity.cpp metadata.json bundle.py build.sh README.md LICENSE; do
    cp "$here/$name" "$work/monet-window-identity/"
done
cp "$out/runtime.json" "$work/monet-window-identity/"
tar -cJf "$out/source.tar.xz" -C "$work" monet-window-identity
cp "$here/README.md" "$here/bundle.py" "$out/"
python3 "$here/bundle.py" seal "$out"
