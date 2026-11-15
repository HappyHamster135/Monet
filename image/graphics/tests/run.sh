#!/bin/sh
# run.sh <graphics-column-test> [plugin folder]: the test with its stand-in helper, and the
# plugin from a build folder (holding ksysguard/process) when one is given.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-graphics-test.XXXXXX")"
trap 'rm -rf "$work"' EXIT
[ -z "${2:-}" ] || export QT_PLUGIN_PATH="$2${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
MONET_GRAPHICS_USE="$here/fake-helper.sh" MONET_GRAPHICS_PIDFILE="$work/helper.pid" QT_QPA_PLATFORM=offscreen "$1"
