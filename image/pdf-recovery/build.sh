#!/bin/sh
# Replace only Okular's shell, retaining the distribution's document engines.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{VERSION}' okular)"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' okular)"
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
dnf5 -y install --setopt=install_weak_deps=False dnf5-plugins rpm-build cmake gcc-c++ make binutils tar xz \
    qt6-qtbase-private-devel wayland-devel
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-pdf.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
dnf5 -y builddep "$work/rpm/SPECS/okular.spec"
python3 "$here/bundle.py" verify "$out/runtime.json"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/okular.spec"
source="$(python3 -c 'from pathlib import Path; import sys; roots=[p.parent for p in Path(sys.argv[1]).rglob("CMakeLists.txt") if p.parent.name=="okular-"+sys.argv[2]]; assert len(roots)==1,roots; print(roots[0])' "$work/rpm/BUILD" "$version")"
python3 "$here/patch.py" "$source"
flags="$(rpm -q --qf '%{OPTFLAGS}' okular)"
linker_flags="$(rpm --eval '%{build_ldflags}')"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON \
    "-DCMAKE_C_FLAGS=$flags" "-DCMAKE_CXX_FLAGS=$flags" -DCMAKE_C_FLAGS_RELEASE=-DNDEBUG -DCMAKE_CXX_FLAGS_RELEASE=-DNDEBUG \
    "-DCMAKE_SHARED_LINKER_FLAGS=$linker_flags" "-DCMAKE_EXE_LINKER_FLAGS=$linker_flags" -DBUILD_TESTING=OFF -DBUILD_QCH=OFF
cmake --build "$work/build" --target okular --parallel "$(nproc)"
install -m 755 "$work/build/bin/okular" "$out/okular"
mkdir "$work/monet-build"
for name in build.sh bundle.py patch.py window-state.cpp departure.cpp restore.cpp retry.cpp README.md; do
    cp "$here/$name" "$work/monet-build/"
done
cp "$out/runtime.json" "$work/monet-build/"
tar -cJf "$out/source.tar.xz" -C "$work" rpm "$release.src.rpm" monet-build
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
python3 -c 'from pathlib import Path; import json,sys; Path(sys.argv[1]).write_text(json.dumps({"work":sys.argv[2],"source":sys.argv[3]}))' "$out/build-tree.json" "$work" "$source"
