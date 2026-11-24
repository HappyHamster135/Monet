#!/bin/sh
# Build only the prompt owners from the signed source of the installed wallet.
set -eu
out=$1
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
mkdir -p "$out/bin" "$out/libexec" "$out/share/monet/wallet-source"
release=$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' kf6-kwallet)
version=$(rpm -q --qf '%{VERSION}' kf6-kwallet)
runtime() {
    { printf '%s\n' /usr/bin/ksecretd /usr/bin/kwalletd6
      ldd /usr/bin/ksecretd /usr/bin/kwalletd6 | awk '/=> \// {print $3}'; } |
        sort -u | xargs -r realpath | xargs -r rpm -qf --qf '%{NEVRA}\n' | sort -u
}
runtime > "$work/runtime"
dnf5 -y install --setopt=install_weak_deps=False gcc-c++ cmake ninja-build rpm-build patch \
    kf6-rpm-macros extra-cmake-modules qt6-qtbase-devel qt6-qt5compat-devel \
    kf6-kconfig-devel kf6-kcoreaddons-devel kf6-kdbusaddons-devel kf6-kio-devel \
    kf6-ki18n-devel kf6-knotifications-devel kf6-kwidgetsaddons-devel kf6-kwindowsystem-devel \
    kf6-kcrash-devel kf6-kcolorscheme-devel 'cmake(Gpgmepp)' 'cmake(Qca-qt6)' libgcrypt-devel libsecret-devel
runtime > "$work/build-runtime"
cmp "$work/runtime" "$work/build-runtime"
python3 "$here/download-source-rpm.py" kf6-kwallet "$work"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/kf6-kwallet.spec"
src="$work/rpm/BUILD/kf6-kwallet-$version-build/kwallet-$version"
patch --fuzz=0 -d "$src" -p1 < "$here/restored-prompts.patch"
cp "$here/restore-origin.h" "$src/src/runtime/"
cmake -G Ninja -S "$src" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
    -DKDE_INSTALL_LIBEXECDIR=libexec -DCMAKE_SKIP_RPATH=ON -DBUILD_TESTING=OFF \
    -DBUILD_KWALLET_QUERY=OFF -DCMAKE_REQUIRE_FIND_PACKAGE_Gpgmepp=TRUE
cmake --build "$work/build" --target ksecretd kwalletd6 --parallel 2
install -m755 "$work/build/bin/ksecretd" "$work/build/bin/kwalletd6" "$out/bin"
cmake -G Ninja -S "$here" -B "$work/launcher" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/launcher" --parallel 2
install -m755 "$work/launcher/monet-restore-launch" "$out/libexec/"
cp "$work/$release.src.rpm" "$here/"*.h "$here/"*.cpp "$here/"*.patch "$here/"*.sh \
    "$here/CMakeLists.txt" "$here/download-source-rpm.py" "$out/share/monet/wallet-source/"
