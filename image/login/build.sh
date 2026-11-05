#!/bin/sh
# Build the greeter only; the distribution still owns the daemon, PAM and sessions.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{VERSION}' plasma-login-manager)"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' plasma-login-manager)"
dnf5 -y install --setopt=install_weak_deps=False cmake gcc-c++ make tar xz python3 rpm-build dnf5-plugins \
    extra-cmake-modules qt6-qtbase-devel qt6-qtdeclarative-devel qt6-qttools-devel qt6-qtshadertools-devel \
    kf6-kconfig-devel kf6-kpackage-devel kf6-kwindowsystem-devel kf6-ki18n-devel kf6-kdbusaddons-devel \
    kf6-kcmutils-devel kf6-kauth-devel kf6-kio-devel kf6-kcoreaddons-devel libplasma-devel \
    layer-shell-qt-devel plasma-workspace-devel libkscreen-devel pam-devel libX11-devel systemd-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-login.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/plasma-login-manager.spec"
source="$work/rpm/BUILD/plasma-login-manager-$version-build/plasma-login-manager-$version"
python3 "$here/patch.py" "$source"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_SKIP_RPATH=ON -DCMAKE_EXE_LINKER_FLAGS=-Wl,--as-needed -DBUILD_TESTING=OFF
cmake --build "$work/build" --target plasma-login-greeter --parallel 4
install -m 755 "$work/build/bin/plasma-login-greeter" "$out/plasma-login-greeter"
cp -r "$here" "$work/monet-login"
# Local test imports can leave bytecode beside these scripts. Ship source only.
tar --exclude=__pycache__ --exclude='*.pyc' -cJf "$out/source.tar.xz" -C "$work" "$release.src.rpm" monet-login
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
