#!/bin/sh
# Run in a disposable Fedora 44 build container. Neither the host nor OS image is installed to.
# Usage: sh build.sh EMPTY_WORK_DIRECTORY OUTPUT_PREFIX
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
work="$1"
out="$2"
mkdir -p "$work" "$out"
work="$(cd "$work" && pwd)"
out="$(cd "$out" && pwd)"
test ! -e "$work/source" || { echo 'Use a new work directory.' >&2; exit 1; }
dnf5 -y install --setopt=install_weak_deps=False gcc-c++ cmake ninja-build make git python3 curl-minimal xz \
    qt6-qtbase-devel qt6-qtsvg-devel qt6-qttools-devel qt6-qt5compat-devel \
    botan3-devel minizip-devel zlib-devel pcsc-lite-devel libargon2-devel \
    libXtst-devel libXi-devel libX11-devel libusb1-devel readline-devel \
    qrencode-devel libcurl-devel openssl-devel
python3 - "$here" "$work" <<'PY'
import hashlib, pathlib, sys, tarfile, urllib.request
sys.path.insert(0, sys.argv[1])
import apply
work = pathlib.Path(sys.argv[2])
archive = work / "source.tar.xz"
urllib.request.urlretrieve(apply.URL, archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != apply.SHA256:
    raise SystemExit("KeePassXC source checksum did not match")
with tarfile.open(archive) as source:
    source.extractall(work / "unpack", filter="data")
folders = list((work / "unpack").iterdir())
if len(folders) != 1 or not folders[0].is_dir():
    raise SystemExit("Unexpected source archive layout")
folders[0].rename(work / "source")
apply.apply(work / "source")
PY
cmake -S "$work/source" -B "$work/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$out" \
    -DWITH_TESTS=ON -DWITH_GUI_TESTS=ON \
    -DKPXC_FEATURE_BROWSER=ON -DKPXC_FEATURE_FDOSECRETS=OFF \
    -DKPXC_FEATURE_SSHAGENT=OFF -DKPXC_FEATURE_UPDATES=OFF -DKPXC_FEATURE_DOCS=OFF
cmake --build "$work/build" --parallel 4
QT_QPA_PLATFORM=offscreen ctest --test-dir "$work/build" --output-on-failure \
    -R '^(testmonetpasswords|testkdbx[234]|testkeys|testbrowser|testentry|testpasswordgenerator)$'
QT_QPA_PLATFORM=offscreen "$work/build/tests/gui/testgui" \
    testCreateDatabase testAddEntry testEditEntry testSearch testSave testSaveBackup \
    testDatabaseLocking testMenuActionStates
cmake --install "$work/build"
install -m 755 "$here/monet-passwords-preview" "$out/bin/monet-passwords-preview"
install -m 644 "$here/monet-passwords-preview.desktop" "$out/share/applications/monet-passwords-preview.desktop"
# Preserve the exact patched source and upstream notices beside the development build.
tar -cJf "$out/monet-passwords-source.tar.xz" -C "$work" source
