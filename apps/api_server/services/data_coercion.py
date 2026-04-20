from __future__ import annotations

import csv
import io
import re
from functools import lru_cache
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


def canonicalize_delimited_headers(headers: list[Any]) -> list[str]:
    counts: dict[str, int] = {}
    canonical: list[str] = []
    for header in headers:
        base_name = str(header or "").strip() or "Unnamed_Column"
        count = counts.get(base_name, 0) + 1
        counts[base_name] = count
        canonical.append(base_name if count == 1 else f"{base_name}__{count}")
    return canonical


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


def coerce_scalar(field_name: str, value: Any, preserve_identifiers: bool = True) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value

    raw = str(value).strip()
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
        number = float(normalized)
        return -number if negative else number

    return raw


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
    reader.fieldnames = canonicalize_delimited_headers(reader.fieldnames or [])
    records: list[dict[str, Any]] = []
    for row in reader:
        rec: dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                continue
            rec[key] = coerce_scalar(key or "", value, preserve_identifiers=True)
        records.append(rec)
    return records
