#!/bin/sh
set -eu
work="$(mktemp -d "${TMPDIR:-/tmp}/monet-launch-tests.XXXXXX")"
trap 'rm -rf "$work"' EXIT HUP INT TERM
export HOME="$work/home" XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data"
export XDG_STATE_HOME="$work/state" XDG_CACHE_HOME="$work/cache" XDG_RUNTIME_DIR="$work/runtime"
mkdir -m 700 "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent
unset DISPLAY WAYLAND_DISPLAY SESSION_MANAGER
# Do not activate unrelated desktop daemons in a native unit-test session.
# In particular, usage-history recording must not leave an activity daemon
# holding the test runner's output pipe open after the checks have finished.
cat > "$work/bus.conf" <<EOF
<busconfig><type>session</type><auth>EXTERNAL</auth>
<listen>unix:path=$XDG_RUNTIME_DIR/bus</listen>
<policy context="default"><allow send_destination="*"/>
<allow receive_sender="*"/><allow own="*"/></policy></busconfig>
EOF
dbus-run-session --config-file="$work/bus.conf" -- "$@"
