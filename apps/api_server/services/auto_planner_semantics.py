from __future__ import annotations

import math
import re
from typing import Any

_SEMANTIC_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "amt": ("amount",),
    "bu": ("business", "unit"),
    "cat": ("category",),
    "cond": ("condition",),
    "cust": ("customer",),
    "dept": ("department",),
    "ext": ("extended",),
    "manuf": ("manufacturer",),
    "mfgr": ("manufacturer",),
    "mfg": ("manufacturer",),
    "pct": ("percent",),
    "prod": ("product",),
    "qty": ("quantity",),
}

_JOIN_KEY_ENTITY_TOKENS = {
    "booking",
    "catalog",
    "code",
    "customer",
    "id",
    "identifier",
    "invoice",
    "item",
    "key",
    "name",
    "number",
    "order",
    "part",
    "project",
    "quote",
    "request",
    "sku",
    "vendor",
}

_JOIN_KEY_MEASURE_TOKENS = {
    "amount",
    "cost",
    "extended",
    "margin",
    "percent",
    "price",
    "qty",
    "quantity",
    "rate",
    "ratio",
    "revenue",
    "sales",
    "total",
    "unit",
    "value",
}

_MEASURE_LIKE_ROLES = {
    "base_measure",
    "derived_measure",
    "metric",
    "ratio",
    "unit_measure",
}


def _semantic_token_set(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_SEMANTIC_TOKEN_ALIASES.get(token, ()))
    return expanded


def _fuzzy_token_sim(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if long.startswith(short):
        return len(short) / len(long)

    def _bigrams(value: str) -> set[str]:
        if len(value) < 2:
            return set()
        return {value[i : i + 2] for i in range(len(value) - 1)}

    bigrams_a = _bigrams(a)
    bigrams_b = _bigrams(b)
    if bigrams_a and bigrams_b:
        return 2 * len(bigrams_a & bigrams_b) / (len(bigrams_a) + len(bigrams_b))
    return 0.0


def _fuzzy_name_sim(hint_words: list[str], col_name: str) -> float:
    sym_map = {
        "%": " percent ",
        "$": " dollar ",
        "#": " number ",
        "€": " euro ",
        "£": " pound ",
    }
    col_norm = col_name.lower()
    for sym, word in sym_map.items():
        col_norm = col_norm.replace(sym, word)
    col_norm = re.sub(r"([a-z])([A-Z])", r"\1 \2", col_norm)
    col_toks = re.findall(r"[a-z0-9]+", col_norm)
    if not col_toks:
        return 0.0

    hint_sim_scores: list[float] = []
    for hint_word in hint_words:
        best = max((_fuzzy_token_sim(hint_word, col_token) for col_token in col_toks), default=0.0)
        hint_sim_scores.append(best)

    if not hint_sim_scores:
        return 0.0
    product = float(math.prod(max(score, 1e-6) for score in hint_sim_scores))
    return float(round(product ** (1.0 / len(hint_sim_scores)), 4))


def _acronym_score(hint_words: list[str], col_token: str) -> float:
    col_token = col_token.upper()
    if not col_token.isalpha() or len(col_token) < 2 or len(col_token) > 6:
        return 0.0
    stop_words = {
        "of",
        "the",
        "a",
        "an",
        "and",
        "or",
        "by",
        "in",
        "at",
        "for",
        "per",
    }
    content_words = [word for word in hint_words if word.lower() not in stop_words and word]
    if not content_words:
        return 0.0
    if len(col_token) > len(content_words):
        return 0.0
    initials = "".join(word[0].upper() for word in content_words)
    if col_token == initials:
        return 1.0
    matches = sum(
        1
        for index, char in enumerate(col_token)
        if index < len(initials) and initials[index] == char
    )
    return round(matches / max(len(col_token), len(initials)), 3)


def _value_semantic_score(hint_words: list[str], sample_values: list[str]) -> float:
    if not sample_values or not hint_words:
        return 0.0
    hint_set = {word.lower() for word in hint_words}
    val_tokens: set[str] = set()
    for value in sample_values[:30]:
        val_tokens.update(re.findall(r"[a-z]+", str(value).lower()))
    token_overlap = len(hint_set & val_tokens) / max(len(hint_set), 1)
    return round(min(token_overlap * 0.30, 0.30), 4)


def _hint_requests_time(hint_words: list[str]) -> bool:
    time_words = {
        "date",
        "day",
        "days",
        "week",
        "month",
        "quarter",
        "year",
        "ytd",
        "mtd",
        "qtd",
        "time",
        "timeline",
        "daily",
        "monthly",
        "yearly",
    }
    return any(word.lower() in time_words for word in hint_words)


def _dimension_semantic_evidence(
    hint_words: list[str],
    col_name: str,
    sample_values: list[str],
) -> tuple[float, float, float]:
    acro = 0.0
    for part in re.findall(r"[A-Za-z0-9]+", col_name):
        if part.isupper() and 2 <= len(part) <= 6:
            acro = max(acro, _acronym_score(hint_words, part))
    fuzzy = _fuzzy_name_sim(hint_words, col_name)
    val_sem = _value_semantic_score(hint_words, sample_values)
    return fuzzy, acro, val_sem


def _source_token_set(source_name: str) -> set[str]:
    source_norm = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", source_name)
    source_norm = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", source_norm)
    return set(re.findall(r"[a-z0-9]+", source_norm.lower()))


def _normalize_match_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
        return str(round(value, 6)).rstrip("0").rstrip(".")

    text = str(value).strip().lower()
    if not text or text in {"?", "none", "null", "nan", "n/a"}:
        return None
    text = re.sub(r"[_/\\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _tokenize_identifier(text: str) -> set[str]:
    return _semantic_token_set(text)
