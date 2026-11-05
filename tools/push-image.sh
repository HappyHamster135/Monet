#!/usr/bin/env bash
# Released version tags stay fixed; rebuilt bases update only the rolling tag.
set -euo pipefail
IMAGE=${1:?image name required}
VERSION=${2:?version required}

if git ls-remote --exit-code --tags origin "refs/tags/v$VERSION" >/dev/null; then
    echo "v$VERSION is released; keeping its qualified image."
else
    status=$?
    # Git returns 2 only when the requested ref does not exist. Network or
    # authentication failures must not be mistaken for an unreleased version.
    if [ "$status" != 2 ]; then
        echo "Could not determine whether v$VERSION is released." >&2
        exit "$status"
    fi
    sudo podman push "$IMAGE:$VERSION"
fi
sudo podman push "$IMAGE:latest"
