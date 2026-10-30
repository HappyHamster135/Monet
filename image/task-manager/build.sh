#!/bin/sh
# Build only the executable; continue using the distribution's native backend libraries.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{VERSION}' plasma-systemmonitor)"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' plasma-systemmonitor)"
dnf5 -y install --setopt=install_weak_deps=False cmake gcc-c++ make tar xz python3 rpm-build dnf5-plugins \
    extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel kf6-kconfig-devel kf6-kcoreaddons-devel \
    kf6-kcrash-devel kf6-kdbusaddons-devel kf6-kglobalaccel-devel kf6-ki18n-devel kf6-kiconthemes-devel \
    kf6-kio-devel kf6-knewstuff-devel kf6-kservice-devel kf6-kwindowsystem-devel kf6-kpackage-devel \
    kf6-kitemmodels-devel kf6-kirigami-devel kf6-kirigami-addons-devel libksysguard-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-task-manager.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/plasma-systemmonitor.spec"
source="$work/rpm/BUILD/plasma-systemmonitor-$version-build/plasma-systemmonitor-$version"
python3 "$here/patch.py" "$source"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_SKIP_RPATH=ON -DBUILD_TESTING=OFF
cmake --build "$work/build" --target plasma-systemmonitor --parallel 4
install -m 755 "$work/build/bin/plasma-systemmonitor" "$out/plasma-systemmonitor"
cp -r "$here" "$work/monet-task-manager"
tar -cJf "$out/source.tar.xz" -C "$work" "$release.src.rpm" monet-task-manager
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
