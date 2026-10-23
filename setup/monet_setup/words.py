"""Monet Setup's words in the language picked on its first page.

The translations are Monet's own (po/, built by tools/make-translations.py into
locale/<language>/LC_MESSAGES/monet-setup.mo). Until one is picked, and for a
language without them, the words stay English.
"""

import gettext
from pathlib import Path

LOCALE = Path(__file__).resolve().parent.parent / "locale"
_current = gettext.NullTranslations()


def use(locale):
    """Speak the language of a locale like "pt_BR.UTF-8" (its own words, else its family's, else English)."""
    global _current
    code = (locale or "").split(".")[0]
    _current = gettext.translation("monet-setup", localedir=LOCALE, languages=[code, code.split("_")[0]],
                                   fallback=True)


def _(text):
    return _current.gettext(text)


def N_(text):
    """Marks text to translate where it's shown (it's kept in English in tables)."""
    return text


def fill(said, values):
    # %2 before %1, so %1 never eats the start of %10.
    for i, value in reversed(list(enumerate(values, 1))):
        said = said.replace(f"%{i}", str(value))
    return said


def tr(text, *values):
    """text in the chosen language, its %1, %2... filled in."""
    return fill(_current.gettext(text), values)


def trc(context, text, *values):
    """The same, for text whose meaning needs a word for the translator."""
    return fill(_current.pgettext(context, text), values)


def ntr(one, many, n, *values):
    """Text with a count: the language's own plural for n, %1 is n."""
    return fill(_current.ngettext(one, many, n), (n,) + values)
