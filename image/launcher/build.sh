#!/bin/sh
# Keep the launch controller paired with its image's Qt/KIO/task-model runtime.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make tar xz python3 binutils extra-cmake-modules \
    qt6-qtbase-devel qt6-qtdeclarative-devel plasma-workspace-devel plasma-activities-devel \
    kf6-kio-devel kf6-kservice-devel kf6-kwindowsystem-devel \
    kf6-knotifications-devel kf6-ki18n-devel kf6-kitemmodels-devel
testing=OFF
if [ "${MONET_LAUNCHER_TESTING:-0}" = 1 ]; then
    testing=ON
    dnf5 -y install --setopt=install_weak_deps=False dbus-daemon kf6-kjobwidgets-devel
fi
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-launcher.XXXXXX")"
cmake -S "$here" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_SKIP_RPATH=ON "-DBUILD_TESTING=$testing"
cmake --build "$work/build" --parallel "$(nproc)"
cp "$work/build/qml/org/monet/launcher/"* "$out/"
cp "$here/monet-launcher.notifyrc" "$out/"
if [ "$testing" = ON ]; then
    ctest --test-dir "$work/build" --output-on-failure
    mkdir -p "$out/tests"
    install -m 755 "$work/build/tests/launcher-test" "$out/tests/launcher-test"
    install -m 755 "$work/build/tests/folder-test" "$out/tests/folder-test"
    install -m 755 "$work/build/tests/tracked-file-job" "$out/tests/tracked-file-job"
    install -m 755 "$here/tests/run.sh" "$out/tests/run.sh"
fi
mkdir "$work/monet-launcher" "$work/monet-launcher/tests"
for name in CMakeLists.txt coordinator.cpp coordinator.h folderopener.cpp folderopener.h launcher.cpp launcher.h plugin.cpp qmldir monet-launcher.notifyrc build.sh bundle.py README.md LICENSE; do
    cp "$here/$name" "$work/monet-launcher/"
done
for name in CMakeLists.txt launcher-test.cpp folder-test.cpp tracked-file-job.cpp run.sh; do
    cp "$here/tests/$name" "$work/monet-launcher/tests/"
done
cp "$out/runtime.json" "$work/monet-launcher/"
tar -cJf "$out/source.tar.xz" -C "$work" monet-launcher
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
