#!/usr/bin/env bash
# Configure only disposable GitHub Ubuntu runners, never an installed Monet PC.
set -euo pipefail
if [[ ${GITHUB_ACTIONS:-} != true ]]; then
    echo 'This helper is only for GitHub Actions Ubuntu runners.' >&2
    exit 2
fi
. /etc/os-release
if [[ ${ID:-} != ubuntu || ! ${VERSION_ID:-} =~ ^(24\.04|26\.04)$ || $(uname -m) != x86_64 ]]; then
    echo 'This helper requires an Ubuntu 24.04 or 26.04 x86_64 CI runner.' >&2
    exit 2
fi

# Keep suites, components, Signed-By and normal apt signature/hash verification.
# The regional EC2/security mirrors repeatedly stalled or returned HTTP 503.
for monet_sources in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list /etc/apt/apt-mirrors.txt /etc/apt/apt-security-mirrors.txt; do
    [[ -f "$monet_sources" ]] || continue
    sudo sed -i -E \
        -e 's@https?://([A-Za-z0-9-]+\.)*archive\.ubuntu\.com/ubuntu/?@https://archive.ubuntu.com/ubuntu/@g' \
        -e 's@https?://security\.ubuntu\.com/ubuntu/?@https://archive.ubuntu.com/ubuntu/@g' \
        -e 's@mirror\+file:/etc/apt/(apt|apt-security)-mirrors\.txt@https://archive.ubuntu.com/ubuntu/@g' \
        "$monet_sources"
done
printf 'Acquire::Retries "3";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    | sudo tee /etc/apt/apt.conf.d/80-monet-ci-downloads >/dev/null
echo 'CI downloads use the primary Ubuntu HTTPS archive with bounded retries.'
