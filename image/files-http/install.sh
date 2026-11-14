#!/bin/sh
set -eu

bundle=$1
if [ "${2:-}" = record-runtime ]; then
    rpm -q --qf '%{NEVRA}\n' kf6-kio-core kf6-kio-core-libs kf6-ki18n qt6-qtbase
    exit
fi

worker=$(rpm -ql kf6-kio-core | grep '/kf6/kio/kio_http\.so$')
test "$worker" = "$(cat "$bundle/worker-path")"
sh "$bundle/install.sh" "$bundle" record-runtime | cmp "$bundle/runtime" -
sha256sum -c "$bundle/original.sha256"
dependencies=$(ldd -r "$bundle/kio_http.so")
if printf '%s\n' "$dependencies" | grep -E 'not found|undefined symbol'; then
    exit 1
fi
install -m 755 "$bundle/kio_http.so" "$worker"
install -D -m 644 "$bundle/source.tar.xz" /usr/share/doc/monet-files-http/source.tar.xz
install -m 644 "$bundle/README.md" /usr/share/doc/monet-files-http/README.md
