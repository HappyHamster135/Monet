#!/usr/bin/env bash
# Released version tags stay fixed; rebuilt bases update only the rolling tag.
#
#   push-image.sh IMAGE VERSION [DIGEST_OUTPUT] [BETA_TAG]
set -euo pipefail
IMAGE=${1:?image name required}
VERSION=${2:?version required}
DIGEST_OUTPUT=${3:-}
BETA=${4:-}
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

# A beta (tools/beta-release.py): only its own tag, VERSION-beta.N, published once and never
# replaced. The version's tag and latest stay as they are, so no PC gets it by itself.
if [ -n "$BETA" ]; then
    number=${BETA#"$VERSION-beta."}
    if [ "$number" = "$BETA" ] || ! [[ $number =~ ^[1-9][0-9]{0,5}$ ]] || [ -z "$DIGEST_OUTPUT" ]; then
        echo "A beta needs its tag ($VERSION-beta.N) and a digest output." >&2
        exit 1
    fi
    if git ls-remote --exit-code --tags origin "refs/tags/v$VERSION" >/dev/null; then
        echo "v$VERSION is released; a beta needs a newer version." >&2
        exit 1
    else
        status=$?
        if [ "$status" != 2 ]; then
            echo "Could not determine whether v$VERSION is released." >&2
            exit "$status"
        fi
    fi
    if found=$(sudo skopeo inspect --raw "docker://$IMAGE:$BETA" 2>&1 >/dev/null); then
        echo "$IMAGE:$BETA is already published; a beta is never replaced." >&2
        exit 1
    elif [[ ${found,,} != *"manifest unknown"* ]]; then
        echo "Could not check whether $IMAGE:$BETA is published: $found" >&2
        exit 1
    fi
    sudo podman tag "$IMAGE:$VERSION" "$IMAGE:$BETA"
    digestfile=$(mktemp)
    trap 'rm -f -- "$digestfile"' EXIT
    push "$BETA" "$digestfile"
    digest=$(<"$digestfile")
    if ! [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]]; then
        echo "Could not record the published OCI digest for $IMAGE:$BETA." >&2
        exit 1
    fi
    printf 'digest=%s\n' "$digest" >> "$DIGEST_OUTPUT"
    exit 0
fi

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
