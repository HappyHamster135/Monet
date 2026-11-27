"""Standard USD API equivalents, not a subscriber's bill.

Verified 2026-11-26 against:
https://developers.openai.com/api/docs/pricing
https://platform.claude.com/docs/en/about-claude/pricing
Rates per million tokens: input, cache read, output, short/long cache write.
Unknown models remain unpriced; never infer a price from a similar name.
"""
import re

VERIFIED = "2026-11-26"
RATES = {
    "gpt-6.2-astra": (8, .4, 40, 10, 20),
    "gpt-6.2-sol": (2, .1, 10, 2.5, 5),
    "gpt-6-astra": (10, 1, 50, 12.5, 25),
    "gpt-6.1-sol": (2, .1, 10, 2.5, 5),
    "claude-fable-5-2": (8, .2, 40, 10, 16),
    "claude-mythos-5-2": (8, .2, 40, 10, 16),
    "claude-fable-5-1": (10, .25, 50, 12.5, 20),
    "claude-mythos-5-1": (10, .25, 50, 12.5, 20),
    "claude-fable-5": (10, 1, 50, 12.5, 20),
    "claude-mythos-5": (10, 1, 50, 12.5, 20),
    "claude-opus-5-5": (4, .2, 20, 5, 8),
    "claude-opus-5": (5, .5, 25, 6.25, 10),
    "claude-opus-4-8": (5, .5, 25, 6.25, 10),
    "claude-opus-4-7": (5, .5, 25, 6.25, 10),
    "claude-opus-4-6": (5, .5, 25, 6.25, 10),
    "claude-opus-4-5": (5, .5, 25, 6.25, 10),
    "claude-sonnet-5-5": (2, .1, 10, 2.5, 4),
    "claude-sonnet-5": (2, .2, 10, 2.5, 4),
    "claude-sonnet-4-6": (3, .3, 15, 3.75, 6),
    "claude-sonnet-4-5": (3, .3, 15, 3.75, 6),
    "claude-haiku-4-5": (1, .1, 5, 1.25, 2),
}


def estimate(model, usage):
    model = re.sub(r"-\d{4}-?\d{2}-?\d{2}$", "", model)
    rates = RATES.get(model)
    if not rates:
        return None, None
    base, cached, output, short, long = rates
    # GPT-6.2 Astra's full-request long-context tariff (model documentation).
    if model == 'gpt-6.2-astra' and usage['input'] > 272000:
        base *= 2; cached *= 2; short *= 2; long *= 2; output *= 1.5
    # Input is normalized to include cache reads/writes for both providers.
    uncached = max(0, usage['input'] - usage['cached'] - usage['write'] - usage['long_write'])
    cost = (uncached * base + usage['cached'] * cached + usage['output'] * output
            + usage['write'] * short + usage['long_write'] * long) / 1_000_000
    savings = usage['cached'] * (base - cached) / 1_000_000
    return cost, savings
