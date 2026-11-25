#!/bin/sh
set -eu
out=$1
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out"
dnf5 -y install --setopt=install_weak_deps=False cmake gcc-c++ make tar xz python3 rpm-build \
    binutils extra-cmake-modules kwin-devel qt6-qtbase-devel qt6-qtbase-private-devel \
    qt6-qtdeclarative-devel qt6-qtwayland-devel kf6-kcoreaddons-devel kf6-ki18n-devel \
    pipewire-devel libdrm-devel wayland-devel libepoxy-devel libxkbcommon-devel vulkan-loader-devel pkgconf-pkg-config
python3 "$here/bundle.py" verify "$out"
work=$(mktemp -d)
helper="$here/download-source-rpm.py"
[ -f "$helper" ] || helper="$here/../download-source-rpm.py"
python3 "$helper" kwin-common "$work"
srpm=$(rpm -q --qf '%{SOURCERPM}' kwin-common)
version=$(rpm -q --qf '%{VERSION}' kwin-common)
rpm -i --define "_topdir $work/rpm" "$work/$srpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/kwin.spec"
source="$work/rpm/BUILD/kwin-$version-build/kwin-$version"
python3 "$here/patch.py" "$source"
cmake -S "$here" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DUPSTREAM_SOURCE="$source"
cmake --build "$work/build" --parallel "${MONET_BUILD_JOBS:-1}"
install -m 755 "$work/build/screencast.so" "$out/screencast.so"
cp -r "$here" "$work/monet-recording-clicks"
cp "$helper" "$work/monet-recording-clicks/download-source-rpm.py"
tar -cJf "$out/source.tar.xz" -C "$work" "$srpm" monet-recording-clicks
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
