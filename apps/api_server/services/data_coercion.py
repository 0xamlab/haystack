from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from functools import lru_cache
from itertools import chain
from typing import Any

_IDENTIFIER_TOKENS = {
    "id",
    "key",
    "code",
    "sku",
    "serial",
    "uuid",
    "guid",
    "zip",
    "postal",
    "part",
    "item",
    "account",
    "invoice",
    "order",
    "ref",
    "number",
    "num",
    "nbr",
    "cage",
}
_MEASURE_TOKENS = {
    "amount",
    "avg",
    "cost",
    "count",
    "days",
    "expense",
    "hours",
    "loss",
    "margin",
    "pct",
    "percent",
    "price",
    "profit",
    "qty",
    "quantity",
    "rate",
    "revenue",
    "sales",
    "score",
    "total",
    "value",
    "volume",
    "weight",
}
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_LEADING_ZERO_INT_RE = re.compile(r"^[+-]?0\d+$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CURRENCY_PREFIX = "$£€¥"
_NUMERIC_LIKE_CHARS = frozenset("0123456789+-.,()%$£€¥eE ")
_HEADER_ALIAS_MIN_COLUMNS = 3
_HEADER_ALIAS_MAX_COLUMNS = 8
_HEADER_ALIAS_MIN_MATCH_RATIO = 0.6
_HEADER_ALIAS_MATCH_SCORE = 0.34
_HEADER_ALIAS_AVG_SCORE = 0.45


def canonicalize_delimited_headers(headers: list[Any]) -> list[str]:
    counts: dict[str, int] = {}
    canonical: list[str] = []
    for header in headers:
        base_name = str(header or "").strip() or "Unnamed_Column"
        count = counts.get(base_name, 0) + 1
        counts[base_name] = count
        canonical.append(base_name if count == 1 else f"{base_name}__{count}")
    return canonical


def _base_header_name(field_name: str) -> str:
    return field_name.split("__", 1)[0]


@lru_cache(maxsize=512)
def field_tokens(field_name: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(field_name.lower()))


@lru_cache(maxsize=512)
def is_identifier_field(field_name: str) -> bool:
    tokens = field_tokens(field_name)
    if not tokens:
        return False
    if {"zip", "postal"} & tokens:
        return True
    if {"uuid", "guid", "serial", "sku", "cage"} & tokens:
        return True
    if {"id", "key", "ref"} & tokens:
        return True
    if "part" in tokens and ({"number", "num", "nbr", "code"} & tokens):
        return True
    if {"invoice", "account"} & tokens and not (tokens & _MEASURE_TOKENS):
        return True
    if "order" in tokens and not (tokens & _MEASURE_TOKENS):
        return True
    if "code" in tokens and not (tokens & _MEASURE_TOKENS):
        return True
    if "number" in tokens and not (tokens & _MEASURE_TOKENS):
        return True
    if "item" in tokens and not (tokens & _MEASURE_TOKENS):
        return True
    return False


def _coerce_text_scalar(
    field_name: str,
    raw: str,
    *,
    preserve_identifiers: bool = True,
) -> Any:
    if raw == "":
        return ""

    if preserve_identifiers:
        if len(raw) >= 16 and _INT_RE.fullmatch(raw):
            return raw
        if _LEADING_ZERO_INT_RE.fullmatch(raw):
            return raw
        if is_identifier_field(field_name) and "%" not in raw:
            return raw

    if any(char not in _NUMERIC_LIKE_CHARS for char in raw):
        return raw

    normalized = raw.replace(",", "")
    negative = normalized.startswith("(") and normalized.endswith(")")
    if negative:
        normalized = normalized[1:-1].strip()

    normalized = normalized.lstrip(_CURRENCY_PREFIX)

    if _INT_RE.fullmatch(normalized):
        number = int(normalized)
        return -number if negative else number

    if normalized.endswith("%"):
        return raw

    if _FLOAT_RE.fullmatch(normalized):
        float_number = float(normalized)
        return -float_number if negative else float_number

    return raw


def coerce_scalar(field_name: str, value: Any, preserve_identifiers: bool = True) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value

    raw = str(value).strip()
    return _coerce_text_scalar(
        field_name,
        raw,
        preserve_identifiers=preserve_identifiers,
    )


def looks_like_header_alias_row(
    field_names: list[str],
    values: list[Any],
) -> bool:
    comparable_threshold = min(
        _HEADER_ALIAS_MAX_COLUMNS,
        max(_HEADER_ALIAS_MIN_COLUMNS, len(field_names)),
    )
    if len(field_names) < _HEADER_ALIAS_MIN_COLUMNS:
        return False

    scores: list[float] = []
    for field_name, value in zip(field_names, values, strict=False):
        raw = str(value or "").strip()
        if raw == "":
            continue
        value_tokens = field_tokens(raw)
        if not value_tokens:
            continue
        header_tokens = field_tokens(_base_header_name(field_name))
        if not header_tokens:
            continue
        if is_identifier_field(field_name):
            unmatched_tokens = value_tokens - header_tokens
            if any(any(char.isdigit() for char in token) for token in unmatched_tokens):
                return False
        overlap = len(header_tokens & value_tokens) / len(value_tokens)
        scores.append(overlap)

    if len(scores) < comparable_threshold:
        return False

    matching = sum(score >= _HEADER_ALIAS_MATCH_SCORE for score in scores)
    return (
        matching / len(scores) >= _HEADER_ALIAS_MIN_MATCH_RATIO
        and (sum(scores) / len(scores)) >= _HEADER_ALIAS_AVG_SCORE
    )


def parse_delimited_records(
    content: str,
    delimiter: str | None = ",",
    sniff: bool = True,
) -> list[dict[str, Any]]:
    if not content or not content.strip():
        return []

    text = content.lstrip("\ufeff")
    chosen_delimiter = delimiter or ","
    if sniff and delimiter in (None, "", ","):
        try:
            sample = text[:4096]
            sniffed = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            chosen_delimiter = sniffed.delimiter
        except csv.Error:
            chosen_delimiter = delimiter or ","

    reader = csv.DictReader(io.StringIO(text), delimiter=chosen_delimiter)
    reader.fieldnames = canonicalize_delimited_headers(list(reader.fieldnames or []))
    records: list[dict[str, Any]] = []
    first_row = next(reader, None)
    if first_row is None:
        return records
    if looks_like_header_alias_row(
        reader.fieldnames,
        [first_row.get(field_name) for field_name in reader.fieldnames],
    ):
        rows_iter: Iterator[dict[str | Any, str | Any]] = reader
    else:
        rows_iter = chain((first_row,), reader)
    for row in rows_iter:
        rec: dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                continue
            rec[key] = coerce_scalar(key or "", value, preserve_identifiers=True)
        records.append(rec)
    return records
