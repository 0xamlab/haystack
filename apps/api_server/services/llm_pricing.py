"""LLM cost estimation — model → per-token price, used to meter managed (pooled-key) LLM spend.

Rates are list prices in **USD per 1,000,000 tokens** (approximate public pricing; edit as vendors
change them — they are an internal cost estimate for the managed-spend cap, not a billing contract).
Cost is returned in **micro-dollars** (1 USD = 1_000_000 µ$). Because cost_usd = tokens/1e6 · rate,
the micro-dollar amount is simply ``tokens · rate`` — no precision loss for fraction-of-a-cent calls.

CRITICAL: an unknown model must never be free. ``compute_cost_micros`` falls back to a deliberately
conservative rate so a mis-typed or newly-released model id still meters (and is capped) rather than
slipping through the spend gate at zero cost.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRate:
    """USD per 1,000,000 tokens for each token class."""

    input: float
    output: float
    cache_read: float = 0.0
    cache_write: float = 0.0


# Conservative catch-all: pricier than most mid-tier models so unknown ids never under-meter.
_FALLBACK = ModelRate(input=10.0, output=30.0, cache_read=1.0, cache_write=12.0)

# Matched in order against the lowercased model id (substring). First hit wins, so list the more
# specific ids (e.g. "-mini") before the broader family token.
_MODEL_RATES: tuple[tuple[str, ModelRate], ...] = (
    # Anthropic Claude
    ("claude-opus", ModelRate(15.0, 75.0, 1.5, 18.75)),
    ("claude-sonnet", ModelRate(3.0, 15.0, 0.3, 3.75)),
    ("claude-haiku", ModelRate(0.8, 4.0, 0.08, 1.0)),
    ("claude-3-opus", ModelRate(15.0, 75.0, 1.5, 18.75)),
    ("claude-3-5-sonnet", ModelRate(3.0, 15.0, 0.3, 3.75)),
    ("claude-3-5-haiku", ModelRate(0.8, 4.0, 0.08, 1.0)),
    ("claude-3-haiku", ModelRate(0.25, 1.25, 0.03, 0.3)),
    ("claude-instant", ModelRate(0.8, 2.4)),
    ("haiku", ModelRate(0.8, 4.0, 0.08, 1.0)),  # catch-all haiku id (else → conservative fallback)
    # OpenAI
    ("gpt-4o-mini", ModelRate(0.15, 0.6)),
    ("gpt-4.1-mini", ModelRate(0.4, 1.6)),
    ("gpt-4.1", ModelRate(2.0, 8.0)),
    ("gpt-4o", ModelRate(2.5, 10.0)),
    ("o3-mini", ModelRate(1.1, 4.4)),
    ("o1-mini", ModelRate(1.1, 4.4)),
    ("o1", ModelRate(15.0, 60.0)),
    # Google Gemini
    ("gemini-1.5-pro", ModelRate(1.25, 5.0)),
    ("gemini-1.5-flash", ModelRate(0.075, 0.3)),
    ("gemini-2.0-flash", ModelRate(0.1, 0.4)),
    ("gemini", ModelRate(1.25, 5.0)),
    # Mistral
    ("mistral-large", ModelRate(2.0, 6.0)),
    ("mistral", ModelRate(0.7, 0.7)),
)


def rate_for(model: str) -> ModelRate:
    """Resolve the per-Mtok rate for a model id, falling back to the conservative catch-all."""
    needle = (model or "").strip().lower()
    for substring, rate in _MODEL_RATES:
        if substring in needle:
            return rate
    return _FALLBACK


def compute_cost_micros(
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> int:
    """Estimate the platform cost of one LLM call in micro-dollars (1 USD = 1_000_000 µ$).

    cost_usd = tokens / 1e6 · rate(USD per Mtok)  ⇒  micros = tokens · rate. Never negative; unknown
    models use the conservative fallback rate (never free).
    """
    rate = rate_for(model)
    micros = (
        max(0, prompt_tokens) * rate.input
        + max(0, completion_tokens) * rate.output
        + max(0, cache_read_tokens) * rate.cache_read
        + max(0, cache_write_tokens) * rate.cache_write
    )
    return int(round(micros))
