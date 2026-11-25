#!/usr/bin/env bash
# KWin reads the wheel's initial placement before mapping its first Wayland frame.
set -eu
rule="$(dirname "${BASH_SOURCE[0]}")/kwinrulesrc"
target=$2
case "$1" in
    install)
        if [ ! -f "$target" ]; then
            install -D -m 644 "$rule" "$target"
            exit 0
        fi
        ;;
    remove)
        [ -f "$target" ] || exit 0
        if cmp -s "$target" "$rule"; then
            rm -f "$target"
            exit 0
        fi
        ;;
    *) exit 2 ;;
esac
# A shared defaults file can also contain distribution or administrator rules.
while IFS='=' read -r key value; do
    case "$key" in ''|'['*) continue ;; esac
    if [ "$1" = install ]; then
        kwriteconfig6 --file "$target" --group org.monet.FavoritesWheel --key "$key" "$value"
    else
        kwriteconfig6 --file "$target" --group org.monet.FavoritesWheel --key "$key" --delete
    fi
done < "$rule"
