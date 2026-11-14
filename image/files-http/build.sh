#!/bin/sh
set -eu

out=$1
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$out"

worker=$(rpm -ql kf6-kio-core | grep '/kf6/kio/kio_http\.so$')
test -f "$worker"
printf '%s\n' "$worker" >"$out/worker-path"
sha256sum "$worker" >"$out/original.sha256"
sh "$here/install.sh" "$out" record-runtime >"$out/runtime"
srpm=$(rpm -q --qf '%{SOURCERPM}' kf6-kio-core)

dnf5 -y install --setopt=install_weak_deps=False \
    cmake make extra-cmake-modules qt6-qtbase-devel kf6-kio-devel kf6-kcoreaddons-devel \
    kf6-ki18n-devel kf6-kconfig-devel gcc-c++ rpm-build dnf5-plugins binutils
sh "$here/install.sh" "$out" record-runtime >"$work/runtime"
cmp "$out/runtime" "$work/runtime"
sha256sum -c "$out/original.sha256"

dnf5 download --srpm --destdir="$work" "${srpm%.src.rpm}"
rpm -i --define "_topdir $work/rpm" "$work/$srpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/kf6-kio.spec"
source=$(find "$work/rpm/BUILD" -path '*/src/kioworkers/http/http.cpp' -type f)
test -f "$source"
root=${source%/src/kioworkers/http/http.cpp}
python3 "$here/patch.py" "$source"
cp "$here/CMakeLists.txt" "$(dirname "$source")"
cmake -S "$(dirname "$source")" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
    "-DKIO_CORE_SOURCE_DIR=$root/src/core"
cmake --build "$work/build" --parallel 3
install -m 755 "$work/build/plugins/kio_http.so" "$out/kio_http.so"
strip --strip-unneeded "$out/kio_http.so"
cp "$here/install.sh" "$here/README.md" "$out/"
tar -cJf "$out/source.tar.xz" -C "$work" "$srpm" -C "$here" CMakeLists.txt build.sh install.sh patch.py README.md
