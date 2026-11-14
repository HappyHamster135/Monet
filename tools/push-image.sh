#!/usr/bin/env bash
# Released version tags stay fixed; rebuilt bases update only the rolling tag.
set -euo pipefail
IMAGE=${1:?image name required}
VERSION=${2:?version required}
DIGEST_OUTPUT=${3:-}
digest=

push() {
    local tag=$1
    shift
    case "$IMAGE" in
        ghcr.io/happyhamster135/monet|ghcr.io/happyhamster135/monet-amd)
            if [ -f image/monet-update.pub ]; then
                python3 tools/sign-release-image.py "containers-storage:$IMAGE:$tag" "$IMAGE:$tag" "$@"
                return
            fi
            ;;
    esac
    if [ "$#" -gt 0 ]; then
        sudo podman push --format oci --digestfile="$1" "$IMAGE:$tag"
    else
        sudo podman push "$IMAGE:$tag"
    fi
}

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
    if [ -f "image/releases/$VERSION.json" ]; then
        echo "v$VERSION has qualified images. Publish those through the qualified workflow." >&2
        exit 1
    fi
    if [ -n "$DIGEST_OUTPUT" ]; then
        digestfile=$(mktemp)
        trap 'rm -f -- "$digestfile"' EXIT
        push "$VERSION" "$digestfile"
        digest=$(<"$digestfile")
        if ! [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]]; then
            echo "Could not record the published OCI digest for $IMAGE:$VERSION." >&2
            exit 1
        fi
    else
        push "$VERSION"
    fi
fi
push latest
if [ -n "$digest" ]; then
    printf 'digest=%s\n' "$digest" >> "$DIGEST_OUTPUT"
fi
