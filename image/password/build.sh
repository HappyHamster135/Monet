#!/bin/sh
# Monet's password prompt: KDE's polkit agent, the same version as the image's,
# built with Monet's page (QuickAuthDialog.qml) in place of KDE's. KDE's page
# stays in, and the agent shows it whenever Monet's can't load.
#
#   sh build.sh OUTDIR     (in a build stage of image/Containerfile)
#
# Leaves OUTDIR/monet-password, or fails and leaves nothing: then the image
# keeps KDE's own prompt.
set -eu
out="$1"
here="$(cd "$(dirname "$0")" && pwd)"
version="$(rpm -q --qf '%{version}' polkit-kde)"

dnf5 -y install --setopt=install_weak_deps=False git cmake gcc-c++ extra-cmake-modules \
    qt6-qtbase-devel qt6-qtdeclarative-devel polkit-qt6-1-devel kf6-ki18n-devel \
    kf6-kwindowsystem-devel kf6-knotifications-devel kf6-kdbusaddons-devel \
    kf6-kcoreaddons-devel kf6-kcrash-devel
git clone --quiet --depth 1 --branch "v$version" https://invent.kde.org/plasma/polkit-kde-agent-1.git /tmp/agent
cd /tmp/agent

mv qml/QuickAuthDialog.qml qml/KdeQuickAuthDialog.qml
cp "$here/QuickAuthDialog.qml" qml/QuickAuthDialog.qml
sed -i 's|<file>qml/QuickAuthDialog.qml</file>|&<file>qml/KdeQuickAuthDialog.qml</file>|' QuickAuthDialog.qrc
sed -i 's|engine->load("qrc:/qml/QuickAuthDialog.qml");|&\n        if (engine->rootObjects().isEmpty()) {\n            engine->load("qrc:/qml/KdeQuickAuthDialog.qml");\n        }|' QuickAuthDialog.cpp
# Both changes took, or KDE's code moved on: then no Monet prompt rather than a broken one.
grep -q 'qml/KdeQuickAuthDialog.qml</file>' QuickAuthDialog.qrc
grep -q 'engine->load("qrc:/qml/KdeQuickAuthDialog.qml")' QuickAuthDialog.cpp

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF >/dev/null
cmake --build build --parallel "$(nproc)" >/dev/null
agent="$(find build -type f -name polkit-kde-authentication-agent-1 -perm -u+x | head -n 1)"
install -D -m 755 "$agent" "$out/monet-password"
