#!/bin/sh
# Build only the native logout greeter from this image's distribution source.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' plasma-workspace)"
version="$(rpm -q --qf '%{VERSION}' plasma-workspace)"
dnf5 -y install --setopt=install_weak_deps=False cmake gcc-c++ make tar xz python3 rpm-build dnf5-plugins extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel plasma-workspace-devel libplasma-devel layer-shell-qt-devel kf6-ki18n-devel kf6-kpackage-devel kf6-kwindowsystem-devel kf6-kconfig-devel kf6-kdbusaddons-devel libX11-devel PackageKit-Qt6-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-session.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/plasma-workspace.spec"
source="$work/rpm/BUILD/plasma-workspace-$version-build/plasma-workspace-$version"
python3 "$here/patch.py" "$source"
cmake -S "$here" -B "$work/build" -DUPSTREAM_SOURCE="$source" -DCMAKE_BUILD_TYPE=Release -DCMAKE_SKIP_RPATH=ON -DCMAKE_EXE_LINKER_FLAGS=-Wl,--as-needed -DBUILD_TESTING=OFF
cmake --build "$work/build" --target ksmserver-logout-greeter --parallel 4
install -m 755 "$work/build/logout-greeter/ksmserver-logout-greeter" "$out/ksmserver-logout-greeter"
mkdir "$work/monet-session"
cp "$here/CMakeLists.txt" "$here/README.md" "$here/build.sh" "$here/bundle.py" "$here/patch.py" "$work/monet-session/"
tar -cJf "$out/source.tar.xz" -C "$work" "$release.src.rpm" rpm monet-session
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
