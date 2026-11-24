#!/bin/sh
# Build the native logout greeter and shutdown service from this image's distribution source.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
mkdir -p "$out/mediakeys"
python3 "$here/mediakeys/guard.py" capture "$out/mediakeys"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' plasma-workspace)"
version="$(rpm -q --qf '%{VERSION}' plasma-workspace)"
dnf5 -y install --setopt=install_weak_deps=False cmake gcc-c++ make tar xz python3 rpm-build dnf5-plugins \
    extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel plasma-workspace-devel libplasma-devel \
    layer-shell-qt-devel kf6-ki18n-devel kf6-kpackage-devel kf6-kwindowsystem-devel kf6-kconfig-devel \
    kf6-kcoreaddons-devel kf6-kitemmodels-devel kf6-kdbusaddons-devel kf6-kglobalaccel-devel kf6-kio-devel \
    kf6-kxmlgui-devel kf6-kservice-devel plasma-activities-devel kscreenlocker-devel libX11-devel PackageKit-Qt6-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-session.XXXXXX")"
helper="$here/download-source-rpm.py"
[ -f "$helper" ] || helper="$here/../download-source-rpm.py"
python3 "$helper" plasma-workspace "$work"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/plasma-workspace.spec"
source="$work/rpm/BUILD/plasma-workspace-$version-build/plasma-workspace-$version"
sh "$here/mediakeys/build.sh" "$source" "$work/media-keys" "$out/mediakeys"
python3 "$here/patch.py" "$source"
cmake -S "$here" -B "$work/build" -DUPSTREAM_SOURCE="$source" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DKDE_INSTALL_LIBEXECDIR=libexec -DCMAKE_SKIP_RPATH=ON \
    -DCMAKE_EXE_LINKER_FLAGS=-Wl,--as-needed -DBUILD_TESTING=OFF
cmake --build "$work/build" --target ksmserver-logout-greeter plasma-shutdown plasma_containmentactions_contextmenu --parallel 4
install -m 755 "$work/build/logout-greeter/ksmserver-logout-greeter" "$out/ksmserver-logout-greeter"
install -m 755 "$work/build/plasma-shutdown/plasma-shutdown" "$out/plasma-shutdown"
plugin="$(find "$work/build" -type f -name 'org.kde.contextmenu.so')"
test -f "$plugin"
install -m 755 "$plugin" "$out/org.kde.contextmenu.so"
mkdir "$work/monet-session"
cp -r "$here/mediakeys" "$work/monet-session/mediakeys"
cp "$helper" "$work/monet-session/download-source-rpm.py"
cp "$here/CMakeLists.txt" "$here/README.md" "$here/build.sh" "$here/bundle.py" "$here/patch.py" "$work/monet-session/"
tar -cJf "$out/source.tar.xz" -C "$work" "$release.src.rpm" rpm monet-session
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
