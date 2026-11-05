#!/bin/sh
# Build only Plasma's native dock applet, against the final image's
# runtime. A source/layout/ABI mismatch fails the image build visibly.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{version}' plasma-desktop)"
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'

dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make curl tar xz python3 binutils extra-cmake-modules \
    qt6-qtbase-devel qt6-qtdeclarative-devel qt6-qtwayland-devel \
    plasma-workspace-devel libplasma-devel plasma-activities-devel plasma-activities-stats-devel libksysguard-devel plasma-wayland-protocols-devel \
    kf6-kconfig-devel kf6-kcoreaddons-devel kf6-kservice-devel kf6-kglobalaccel-devel kf6-kitemmodels-devel \
    kf6-ki18n-devel kf6-kio-devel kf6-knotifications-devel kf6-kwindowsystem-devel kf6-kxmlgui-devel \
    wayland-devel libxkbcommon-devel
python3 "$here/bundle.py" verify "$out/runtime.json"

work="$(mktemp -d /tmp/monet-dock.XXXXXX)"
curl --fail --location --retry 3 \
    "https://invent.kde.org/plasma/plasma-desktop/-/archive/v$version/plasma-desktop-v$version.tar.gz" \
    -o "$work/upstream.tar.gz"
tar -xzf "$work/upstream.tar.gz" -C "$work"
source="$work/plasma-desktop-v$version"
python3 "$here/patch.py" "$source"
cmake -S "$here" -B "$work/build" \
    -DUPSTREAM_SOURCE="$source" -DUPSTREAM_VERSION="$version" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON
cmake --build "$work/build" --parallel "$(nproc)"
DESTDIR="$work/installed" cmake --install "$work/build"
for name in org.kde.plasma.taskmanager.so org.kde.plasma.trash.so; do
    plugin="$(find "$work/installed" -name "$name" -type f)"
    test "$(printf '%s\n' "$plugin" | wc -l)" -eq 1
    test -f "$plugin"
    install -m 755 "$plugin" "$out/$name"
done

# Ship the complete corresponding source, licenses and build instructions with
# the image. The archive contains the patched source plus Monet's build inputs.
mkdir "$work/monet-build"
for name in CMakeLists.txt MonetDockMotion.qml MonetDockHover.qml patch.py bundle.py build.sh README.md; do
    cp "$here/$name" "$work/monet-build/"
done
cp "$out/runtime.json" "$work/monet-build/runtime.json"
tar -cJf "$out/source.tar.xz" -C "$work" "plasma-desktop-v$version" monet-build
cp "$here/README.md" "$here/bundle.py" "$out/"
python3 "$here/bundle.py" seal "$out"
