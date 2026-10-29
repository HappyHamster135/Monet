# Monet's names for KDE's apps (Files, Terminal, Photos...), wherever an app says its own name:
# its window titles, which Qt ends with it, and its About. Each app looks its name up in its
# translations, so Monet puts a language of its own (LANGUAGE@monet, share/locale/*@monet,
# made by tools/make-translations.py) before the session's: the names come from there, and
# every other word from the language as before. Sourced by Plasma as it starts.
monet_languages=""
for monet_language in $(printf '%s' "${LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" | tr ':' ' '); do
    monet_language="${monet_language%%.*}"
    case "$monet_language" in
        "" | C | POSIX | *@*) continue ;;
    esac
    monet_languages="$monet_languages:$monet_language@monet"
    # sv_SE as sv: Monet's names are by language.
    [ "${monet_language%%_*}" != "$monet_language" ] && monet_languages="$monet_languages:${monet_language%%_*}@monet"
    monet_languages="$monet_languages:$monet_language"
done
if [ -n "$monet_languages" ]; then
    LANGUAGE="${monet_languages#:}"
    export LANGUAGE
fi
unset monet_languages monet_language
