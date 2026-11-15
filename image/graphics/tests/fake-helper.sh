#!/bin/sh
# Stands in for monet-graphics-use --watch: the process that started it (the test) at 42.5%.
[ "$1" = --watch ] || exit 2
[ -z "${MONET_GRAPHICS_PIDFILE:-}" ] || echo $$ > "$MONET_GRAPHICS_PIDFILE"
while :; do
    printf '{"version": 1, "ok": true, "pids": {"%s": 42.5, "999999999": 3.0}}\n' "$PPID" || exit 0
    sleep 0.3
done
