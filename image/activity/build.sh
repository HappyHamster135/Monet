#!/bin/sh
# Build against the runtime that will load this QML extension.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make tar xz python3 binutils extra-cmake-modules \
    qt6-qtbase-devel qt6-qtdeclarative-devel kwayland-devel
testing=OFF
if [ "${MONET_ACTIVITY_TESTING:-0}" = 1 ]; then
    testing=ON
    dnf5 -y install --setopt=install_weak_deps=False wayland-devel plasma-wayland-protocols-devel dbus-daemon
fi
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-activity.XXXXXX")"
cmake -S "$here" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_SKIP_RPATH=ON "-DBUILD_TESTING=$testing"
cmake --build "$work/build" --parallel "$(nproc)"
cp "$work/build/qml/org/monet/activity/"* "$out/"
if [ "$testing" = ON ]; then
    ctest --test-dir "$work/build" --output-on-failure
    mkdir -p "$out/tests"
    install -m 755 "$work/build/tests/activity-test" "$out/tests/activity-test"
    install -m 755 "$here/tests/run.sh" "$out/tests/run.sh"
fi
mkdir "$work/monet-activity"
for name in CMakeLists.txt activity.cpp activity.h monitor.cpp monitor.h power.cpp power.h plugin.cpp qmldir build.sh bundle.py README.md LICENSE; do
    cp "$here/$name" "$work/monet-activity/"
done
mkdir "$work/monet-activity/tests"
for name in CMakeLists.txt activity-test.cpp fake-wayland.cpp fake-wayland.h run.sh; do
    cp "$here/tests/$name" "$work/monet-activity/tests/"
done
cp "$out/runtime.json" "$work/monet-activity/"
tar -cJf "$out/source.tar.xz" -C "$work" monet-activity
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
