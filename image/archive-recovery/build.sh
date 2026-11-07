#!/bin/sh
# Rebuild just Ark's executable against the exact installed distribution source.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{VERSION}' ark)"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' ark)"
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make curl tar xz python3 binutils rpm-build dnf5-plugins \
    extra-cmake-modules redhat-rpm-config annobin-plugin-gcc qt6-qtbase-devel \
    kf6-kconfig-devel kf6-kcrash-devel kf6-kdbusaddons-devel kf6-kfilemetadata-devel \
    kf6-ki18n-devel kf6-kio-devel kf6-kservice-devel kf6-kparts-devel kf6-kpty-devel \
    kf6-kwidgetsaddons-devel kf6-kwindowsystem-devel kf6-kiconthemes-devel \
    kf6-breeze-icons-devel libarchive-devel libzip-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-archives.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/ark.spec"
source="$(python3 -c 'from pathlib import Path; import sys; paths=[p.parent for p in Path(sys.argv[1]).rglob("CMakeLists.txt") if p.parent.name=="ark-"+sys.argv[2]]; assert len(paths)==1,paths; print(paths[0])' "$work/rpm/BUILD" "$version")"
python3 "$here/patch.py" "$source"
flags="$(rpm -q --qf '%{OPTFLAGS}' ark)"
linker_flags="$(rpm --eval '%{build_ldflags}')"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON \
    "-DCMAKE_C_FLAGS=$flags" "-DCMAKE_CXX_FLAGS=$flags" -DCMAKE_C_FLAGS_RELEASE=-DNDEBUG -DCMAKE_CXX_FLAGS_RELEASE=-DNDEBUG \
    "-DCMAKE_SHARED_LINKER_FLAGS=$linker_flags" "-DCMAKE_EXE_LINKER_FLAGS=$linker_flags" "-DCMAKE_MODULE_LINKER_FLAGS=$linker_flags" \
    -DBUILD_TESTING=OFF -DBUILD_DOC=OFF
cmake --build "$work/build" --target ark kerfuffle_libarchive_readonly --parallel "$(nproc)"
install -m 755 "$work/build/bin/ark" "$out/ark"
strip --strip-debug "$out/ark"
install -m 755 "$work/build/bin/kerfuffle/kerfuffle_libarchive_readonly.so" "$out/kerfuffle_libarchive_readonly.so"
strip --strip-debug "$out/kerfuffle_libarchive_readonly.so"
mkdir "$work/monet-build"
cp "$here/build.sh" "$here/patch.py" "$here/bundle.py" "$here/README.md" "$here/rpmheader.h" "$work/monet-build/"
cp "$out/runtime.json" "$work/monet-build/"
tar -cJf "$out/source.tar.xz" -C "$work" rpm "$release.src.rpm" monet-build
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
