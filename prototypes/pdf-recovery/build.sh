#!/bin/sh
# VM-only native capture fixture, using the distribution source and installed PDF plugin.
set -eu
work=/work
dnf5 -y install --setopt=install_weak_deps=False okular dnf5-plugins rpm-build cmake gcc-c++ binutils
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' okular)"
version="$(rpm -q --qf '%{VERSION}' okular)"
rpm -qa | sort > "$work/runtime-before.txt"
sha256sum /usr/bin/okular > "$work/original-shell.sha256"
ldd /usr/bin/okular > "$work/original-shell.ldd"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
dnf5 -y builddep "$work/rpm/SPECS/okular.spec"
dnf5 -y install --setopt=install_weak_deps=False qt6-qtbase-private-devel wayland-devel kwin python3-pyside6 dbus-daemon qt6-qtwayland
sha256sum --check "$work/original-shell.sha256"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/okular.spec"
source="$(python3 -c 'from pathlib import Path; import sys; roots=[p.parent for p in Path(sys.argv[1]).rglob("CMakeLists.txt") if p.parent.name=="okular-"+sys.argv[2]]; assert len(roots)==1,roots; print(roots[0])' "$work/rpm/BUILD" "$version")"
python3 "$work/inputs/patch.py" "$source"
flags="$(rpm -q --qf '%{OPTFLAGS}' okular)"
linker_flags="$(rpm --eval '%{build_ldflags}')"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON \
    "-DCMAKE_C_FLAGS=$flags" "-DCMAKE_CXX_FLAGS=$flags" -DCMAKE_C_FLAGS_RELEASE=-DNDEBUG -DCMAKE_CXX_FLAGS_RELEASE=-DNDEBUG \
    "-DCMAKE_SHARED_LINKER_FLAGS=$linker_flags" "-DCMAKE_EXE_LINKER_FLAGS=$linker_flags" -DBUILD_TESTING=OFF -DBUILD_QCH=OFF
cmake --build "$work/build" --target okular --parallel 2
python3 -c 'from pathlib import Path; import json,sys; Path("/work/build-tree.json").write_text(json.dumps({"source":sys.argv[1],"version":sys.argv[2]}))' "$source" "$version"
ldd "$work/build/bin/okular" > "$work/patched-shell.ldd"
rpm -qa | sort > "$work/runtime-after.txt"
