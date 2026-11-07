#!/bin/sh
# Give both Qt bus connections a disposable bus; no access to the host services.
set -eu
exec dbus-run-session -- sh -c 'DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" exec "$@"' sh "$@"
