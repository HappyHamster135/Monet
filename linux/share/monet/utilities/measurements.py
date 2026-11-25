"""Parse measurement shorthand before passing unit arithmetic to the offline calculator."""
import math
import os
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata

HELPER = Path(__file__).resolve().parents[3] / 'libexec/monet-measure'
NUMBER = re.compile(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
UNIT = re.compile(r'[A-Za-zµμ°Ω]+')
# A tight fraction before a unit is an amount (1/2 kg). Spaced division
# still divides by the whole following quantity (1 / 2 kg).
FRACTION = re.compile(r'(?:[0-9]+[ \t]+)?[0-9]+/[0-9]+')
TOKENS = re.compile(rf'{FRACTION.pattern}(?=\s*{UNIT.pattern})|{NUMBER.pattern}|{UNIT.pattern}|->|[^\s]')
CONNECTORS = {'to', 'into', 'as', 'in', 'till', '->', '→'}
SYMBOLS = str.maketrans({'×': '*', '÷': '/', '−': '-', '·': '*', '²': '^2', '³': '^3',
                          "'": ' ft ', '′': ' ft ', '"': ' inches ', '″': ' inches '})
ANSWER = re.compile(r'\bans\b', re.IGNORECASE)


def unit_at(tokens, start):
    """Read a unit or a product such as kg*m/s^2, stopping before the next amount."""
    parts = []
    i = start
    while i < len(tokens) and UNIT.fullmatch(tokens[i]):
        name = tokens[i]
        if name.casefold() in ('to', 'into', 'as', 'till', 'per'):
            break
        parts.append('inches' if name.casefold() == 'in' else name)
        i += 1
        if i < len(tokens) and tokens[i] == '^':
            parts.append('^')
            i += 1
            if i < len(tokens) and tokens[i] == '-':
                parts.append('-')
                i += 1
            if i == len(tokens) or not tokens[i].isdigit() or int(tokens[i]) > 12:
                raise ValueError
            parts.append(tokens[i])
            i += 1
        if i < len(tokens) and UNIT.fullmatch(tokens[i]) and tokens[i].casefold() not in CONNECTORS | {'per'}:
            parts.append('*')
            continue
        if i + 1 >= len(tokens) or tokens[i] not in ('*', '/', 'per') or not UNIT.fullmatch(tokens[i+1]):
            break
        parts.append('/' if tokens[i] == 'per' else tokens[i])
        i += 1
    return ''.join(parts), i


def amount(token):
    if NUMBER.fullmatch(token):
        return token
    if not FRACTION.fullmatch(token) or len(token) > 32:
        return ''
    whole, _, fraction = ' '.join(token.split()).rpartition(' ')
    if not int(fraction.split('/')[1]):
        return ''
    return '(' + (whole + '+' if whole else '') + fraction + ')'


def expression(text, *, scoped=False, answer='', decimal='.'):
    if len(text) > 256:
        return None
    raw = text.strip()
    explicit = raw.startswith('=')
    raw = raw.removeprefix('=').strip().translate(SYMBOLS)
    if not raw.isascii():
        raw = ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in raw)
    if decimal != '.':
        raw = raw.replace(decimal, '.')
    reuse = bool(ANSWER.search(raw))
    if reuse:
        if not answer:
            return None
        if len(answer) > 160 or not re.fullmatch(r'-?[0-9.][0-9A-Za-zµμ°Ω. *^()/+-]*', answer):
            return None
        raw = ANSWER.sub(lambda _: '(' + answer + ')', raw)
    tokens = TOKENS.findall(raw)
    if not tokens or len(tokens) > 100 or tokens.count('^') > 3:
        return None
    for i, token in enumerate(tokens):
        if NUMBER.fullmatch(token):
            _, exponent, magnitude = token.lower().partition('e')
            if len(token) > 32 or not math.isfinite(float(token)) or exponent and abs(int(magnitude)) > 308:
                return None
        if token == '^':
            power = i + 1
            if power < len(tokens) and tokens[power] == '-':
                power += 1
            if power == len(tokens) or not tokens[power].isdigit() or int(tokens[power]) > 12:
                return None
            if power + 1 < len(tokens) and tokens[power+1] == '^':
                return None

    # The final "in" can introduce a result unit or mean inches in the input.
    target = ''
    try:
        for i in reversed(range(1, len(tokens) - 1)):
            if tokens[i].casefold() in CONNECTORS:
                unit, end = unit_at(tokens, i + 1)
                if unit and end == len(tokens):
                    target, tokens = unit, tokens[:i]
                    break
        parts = []
        measured = mixed = False
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ('+', '-', '*', '/', '(', ')', '^'):
                parts.append(token)
                i += 1
                continue
            number = amount(token)
            if not number:
                return None
            unit, end = unit_at(tokens, i + 1)
            if not unit:
                parts.append(number)
                i += 1
                continue
            measured = True
            mixed |= '/' in token
            terms = [number + ' ' + unit]
            i = end
            while i < len(tokens) and (number := amount(tokens[i])):
                unit, end = unit_at(tokens, i + 1)
                if not unit:
                    return None
                terms.append(number + ' ' + unit)
                i = end
            mixed |= len(terms) > 1
            parts.append('(' + ' + '.join(terms) + ')')
    except ValueError:
        return None
    arithmetic = any(p in ('+', '-', '*', '/', '^') for p in parts[1:])
    if not reuse and (not measured or not (mixed or arithmetic or target and (explicit or scoped))):
        return None
    return ' '.join(parts) + (' to ' + target if target else '')


@lru_cache(maxsize=64)
def run_calculator(formula, helper):
    proc = subprocess.run([helper, formula], capture_output=True, text=True, timeout=.25, check=True)
    value = proc.stdout.rstrip('\n')
    numeric = value.removeprefix('approx. ').lstrip('-')
    return value if len(value) <= 160 and numeric and numeric[0] in '0123456789.' else ''


def evaluate(formula, helper):
    try:
        return run_calculator(formula, helper)
    except (OSError, subprocess.SubprocessError):
        # A transient launch failure can be retried with the same expression.
        return ''


def session_answer(value=None):
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        return ''
    path = Path(runtime) / 'monet' / 'measurement-answer'
    try:
        if value is None:
            with path.open() as stream:
                answer = stream.read(161)
            return answer if len(answer) <= 160 else ''
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as tmp:
            try:
                tmp.write(value.removeprefix('approx. '))
                tmp.flush()
                os.replace(tmp.name, path)
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    except (OSError, UnicodeError):
        pass
    return ''


def localized(value, decimal):
    return re.sub(r'(?<=[0-9])\.(?=[0-9])', decimal, value) if decimal != '.' else value
