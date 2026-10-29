#!/bin/sh
# Build Kate/KWrite's shared library against the final image's exact runtime.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
python3 "$here/bundle.py" capture "$out/runtime.json"
version="$(rpm -q --qf '%{version}' kate)"
engine_version="$(rpm -q --qf '%{version}' kf6-ktexteditor)"
printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
printf '%s\n' "$engine_version" | grep -Eq '^6\.[0-9]+\.[0-9]+$'
dnf5 -y install --setopt=install_weak_deps=False \
    cmake gcc-c++ make curl tar xz python3 binutils extra-cmake-modules redhat-rpm-config annobin-plugin-gcc \
    qt6-qtbase-devel qt6-qtbase-private-devel wayland-devel kf6-ktexteditor-devel \
    kf6-kdbusaddons-devel kf6-kcrash-devel kf6-kiconthemes-devel \
    kf6-kwindowsystem-devel kf6-kuserfeedback-devel editorconfig-devel \
    qt6-qtdeclarative-devel qt6-qtspeech-devel kf6-kauth-devel \
    kf6-karchive-devel kf6-kconfig-devel kf6-kguiaddons-devel kf6-ki18n-devel \
    kf6-kio-devel kf6-kparts-devel kf6-sonnet-devel kf6-syntax-highlighting-devel \
    kf6-kcolorscheme-devel
python3 "$here/bundle.py" verify "$out/runtime.json"
engine_flags="$(rpm -q --qf '%{OPTFLAGS}' kf6-ktexteditor)"
linker_flags="$(rpm --eval '%{build_ldflags}')"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-editor.XXXXXX")"
series="$(printf '%s' "$engine_version" | cut -d. -f1,2)"
curl --fail --location --retry 3 \
    "https://download.kde.org/stable/frameworks/$series/ktexteditor-$engine_version.tar.xz" -o "$work/texteditor.tar.xz"
tar -xJf "$work/texteditor.tar.xz" -C "$work"
engine_source="$work/ktexteditor-$engine_version"
python3 "$here/patch-texteditor.py" "$engine_source"
cmake -S "$engine_source" -B "$work/texteditor-build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_RPATH=ON \
    "-DCMAKE_CXX_FLAGS_RELEASE=$engine_flags -DNDEBUG" "-DCMAKE_SHARED_LINKER_FLAGS=$linker_flags" \
    -DBUILD_TESTING=ON -DBUILD_QCH=OFF -DENABLE_PCH=OFF -DENABLE_KAUTH=ON \
    -DCMAKE_REQUIRE_FIND_PACKAGE_EditorConfig=ON
cmake --build "$work/texteditor-build" --target KF6TextEditor katefoldingtest multicursortest --parallel "$(nproc)"
QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH="$work/texteditor-build/bin" \
    "$work/texteditor-build/bin/katefoldingtest"
QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH="$work/texteditor-build/bin" \
    "$work/texteditor-build/bin/multicursortest"
install -m 755 "$work/texteditor-build/bin/libKF6TextEditor.so.$engine_version" "$out/libKF6TextEditor.so.$engine_version"
curl --fail --location --retry 3 \
    "https://invent.kde.org/utilities/kate/-/archive/v$version/kate-v$version.tar.gz" -o "$work/upstream.tar.gz"
tar -xzf "$work/upstream.tar.gz" -C "$work"
source="$work/kate-v$version"
python3 "$here/patch.py" "$source"
cmake -S "$source" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON \
    -DBUILD_addons=OFF -DBUILD_doc=OFF -DBUILD_TESTING=OFF -DENABLE_PCH=OFF
cmake --build "$work/build" --target kateprivate --parallel "$(nproc)"
install -m 755 "$work/build/bin/libkateprivate.so.$version" "$out/libkateprivate.so.$version"
mkdir "$work/monet-build"
for name in build.sh bundle.py patch.py patch-texteditor.py textfolding-test.cpp multicursor.cpp multicursor-test.cpp monetselection.h monetdeparture.h monetdeparture.cpp README.md; do
    cp "$here/$name" "$work/monet-build/"
done
cp "$out/runtime.json" "$work/monet-build/"
tar -cJf "$out/source.tar.xz" -C "$work" "kate-v$version" "ktexteditor-$engine_version" monet-build
cp "$here/README.md" "$here/bundle.py" "$out/"
python3 "$here/bundle.py" seal "$out"
