#!/bin/sh
# Build the Files pair from the installed distribution's source RPM.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{VERSION}' dolphin)"
release="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' dolphin)"
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make curl tar xz python3 binutils rpm-build dnf5-plugins extra-cmake-modules redhat-rpm-config annobin-plugin-gcc \
    qt6-qtbase-devel qt6-qtbase-private-devel qt6-qtmultimedia-devel wayland-devel \
    kf6-kcmutils-devel kf6-knewstuff-devel kf6-kcoreaddons-devel kf6-ki18n-devel kf6-kdbusaddons-devel \
    kf6-kbookmarks-devel kf6-kconfig-devel kf6-kio-devel kf6-kparts-devel kf6-solid-devel kf6-kiconthemes-devel \
    kf6-kcompletion-devel kf6-ktextwidgets-devel kf6-knotifications-devel kf6-kcrash-devel kf6-kwindowsystem-devel \
    kf6-kwidgetsaddons-devel kf6-kcodecs-devel kf6-kguiaddons-devel kf6-kcolorscheme-devel \
    kf6-kuserfeedback-devel kf6-kfilemetadata-devel kf6-baloo-devel baloo-widgets-devel PackageKit-Qt6-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-files.XXXXXX")"
dnf5 download --srpm --destdir="$work" "$release"
rpm -i --define "_topdir $work/rpm" "$work/$release.src.rpm"
rpmbuild --nodeps -bp --define "_topdir $work/rpm" "$work/rpm/SPECS/dolphin.spec"
source="$(python3 -c 'from pathlib import Path; import sys; paths=[p.parent for p in Path(sys.argv[1]).rglob("CMakeLists.txt") if p.parent.name=="dolphin-"+sys.argv[2]]; assert len(paths)==1,paths; print(paths[0])' "$work/rpm/BUILD" "$version")"
python3 "$here/patch.py" "$source"
flags="$(rpm -q --qf '%{OPTFLAGS}' dolphin)"
linker_flags="$(rpm --eval '%{build_ldflags}')"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON \
    "-DCMAKE_C_FLAGS=$flags" "-DCMAKE_CXX_FLAGS=$flags" -DCMAKE_C_FLAGS_RELEASE=-DNDEBUG -DCMAKE_CXX_FLAGS_RELEASE=-DNDEBUG \
    "-DCMAKE_SHARED_LINKER_FLAGS=$linker_flags" "-DCMAKE_EXE_LINKER_FLAGS=$linker_flags" \
    -DBUILD_TESTING=OFF -DBUILD_QCH=OFF
cmake --build "$work/build" --target dolphin --parallel "$(nproc)"
install -m 755 "$work/build/bin/dolphin" "$out/dolphin"
library="$(python3 -c 'import json,sys; from pathlib import Path; print(Path(json.load(open(sys.argv[1]))["targets"][1]["path"]).name)' "$out/runtime.json")"
install -m 755 "$work/build/bin/$library" "$out/$library"
mkdir "$work/monet-build"
for name in build.sh bundle.py patch.py monetfiles.h view-state.cpp window-state.cpp README.md; do cp "$here/$name" "$work/monet-build/"; done
cp "$out/runtime.json" "$work/monet-build/"
tar -cJf "$out/source.tar.xz" -C "$work" rpm "$release.src.rpm" monet-build
cp "$here/bundle.py" "$here/README.md" "$out/"
python3 "$here/bundle.py" seal "$out"
python3 -c 'from pathlib import Path; import json,sys; Path(sys.argv[1]).write_text(json.dumps({"work":sys.argv[2],"source":sys.argv[3]}))' "$out/build-tree.json" "$work" "$source"
