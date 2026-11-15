#!/bin/sh
# Keep Task Manager's Graphics column paired with its image's Qt/KDE process runtime.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make tar xz python3 binutils extra-cmake-modules \
    qt6-qtbase-devel qt6-qtdeclarative-devel kf6-kcoreaddons-devel kf6-ki18n-devel \
    kf6-kservice-devel libksysguard-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
testing=OFF
[ "${MONET_GRAPHICS_TESTING:-0}" = 1 ] && testing=ON
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-graphics.XXXXXX")"
cmake -S "$here" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_SKIP_RPATH=ON "-DBUILD_TESTING=$testing"
cmake --build "$work/build" --parallel "$(nproc)"
cp "$work/build/plugins/ksysguard/process/ksysguard_plugin_monetgraphics.so" "$out/"
if [ "$testing" = ON ]; then
    ctest --test-dir "$work/build" --output-on-failure
    mkdir -p "$out/tests"
    install -m 755 "$work/build/tests/graphics-column-test" "$here/tests/run.sh" "$here/tests/fake-helper.sh" "$out/tests/"
fi
mkdir "$work/monet-graphics" "$work/monet-graphics/tests"
for name in CMakeLists.txt monetgraphics.cpp monetgraphics.h monetgraphics.json build.sh bundle.py README.md LICENSE; do
    cp "$here/$name" "$work/monet-graphics/"
done
for name in CMakeLists.txt graphics-column-test.cpp run.sh fake-helper.sh; do
    cp "$here/tests/$name" "$work/monet-graphics/tests/"
done
cp "$out/runtime.json" "$work/monet-graphics/"
tar -cJf "$out/source.tar.xz" -C "$work" monet-graphics
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
