from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from collections.abc import Mapping
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any

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
_CSV_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CSV_INT_RE = re.compile(r"^[+-]?\d+$")
_CSV_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_CSV_LEADING_ZERO_INT_RE = re.compile(r"^[+-]?0\d+$")
_CSV_CURRENCY_PREFIX = "$£€¥"
_HEADER_ALIAS_MIN_COLUMNS = 3
_HEADER_ALIAS_MAX_COLUMNS = 8
_HEADER_ALIAS_MIN_MATCH_RATIO = 0.6
_HEADER_ALIAS_MATCH_SCORE = 0.34
_HEADER_ALIAS_AVG_SCORE = 0.45
_SQLITE_DSN_RE = re.compile(r"^sqlite(?:\+pysqlite)?:///(.+)$", re.IGNORECASE)


def _canonicalize_csv_headers(headers: list[Any]) -> list[str]:
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
def _csv_field_tokens(field_name: str) -> frozenset[str]:
    return frozenset(_CSV_TOKEN_RE.findall(field_name.lower()))


@lru_cache(maxsize=512)
def _csv_is_identifier_field(field_name: str) -> bool:
    tokens = _csv_field_tokens(field_name)
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


def _coerce_csv_scalar(field_name: str, value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value

    raw = str(value).strip()
    if raw == "":
        return ""
    if len(raw) >= 16 and _CSV_INT_RE.fullmatch(raw):
        return raw
    if _CSV_LEADING_ZERO_INT_RE.fullmatch(raw):
        return raw
    if _csv_is_identifier_field(field_name) and "%" not in raw:
        return raw

    normalized = raw.replace(",", "")
    negative = normalized.startswith("(") and normalized.endswith(")")
    if negative:
        normalized = normalized[1:-1].strip()
    normalized = normalized.lstrip(_CSV_CURRENCY_PREFIX)

    if _CSV_INT_RE.fullmatch(normalized):
        number = int(normalized)
        return -number if negative else number
    if normalized.endswith("%"):
        return raw
    if _CSV_FLOAT_RE.fullmatch(normalized):
        number = float(normalized)
        return -number if negative else number
    return raw


def _looks_like_header_alias_row(field_names: list[str], values: list[Any]) -> bool:
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
        value_tokens = _csv_field_tokens(raw)
        if not value_tokens:
            continue
        header_tokens = _csv_field_tokens(_base_header_name(field_name))
        if not header_tokens:
            continue
        if _csv_is_identifier_field(field_name):
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


def _sqlite_path_from_descriptor(descriptor: Mapping[str, Any]) -> Path:
    path_value = descriptor.get("path")
    if isinstance(path_value, str | Path) and str(path_value).strip():
        return Path(path_value).expanduser()

    connection_string = descriptor.get("connection_string")
    if not isinstance(connection_string, str) or not connection_string.strip():
        raise ValueError("SQLite descriptors require a local path or connection_string.")

    match = _SQLITE_DSN_RE.match(connection_string.strip())
    if not match:
        raise ValueError("Unsupported SQLite connection string.")
    return Path(match.group(1)).expanduser()


def _parse_sqlite_source(descriptor: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = _sqlite_path_from_descriptor(descriptor)
    table = descriptor.get("table")
    query = descriptor.get("query")
    if bool(table) == bool(query):
        raise ValueError("SQLite descriptors must include exactly one of table or query.")
    if query is not None and (
        not isinstance(query, str) or not query.strip().lower().startswith(("select", "with"))
    ):
        raise ValueError("SQLite query descriptors must use a read-only SELECT or WITH statement.")

    sql = (
        query.strip()
        if isinstance(query, str)
        else f'SELECT * FROM "{str(table).replace(chr(34), chr(34) * 2)}"'  # noqa: S608
    )
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(sql).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:  # pragma: no cover
        raise ValueError(f"Failed to read SQLite source: {exc}") from exc
    return [dict(row) for row in rows]


def _parse_source_descriptor(src: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "records" in src:
        records = src["records"]
        if not isinstance(records, list):
            raise ValueError("Local source descriptor 'records' must be a list of objects.")
        return [dict(record) for record in records if isinstance(record, Mapping)]

    provider = str(src.get("provider") or src.get("type") or "").strip().lower()
    if provider in {"sqlite", "sqlite3"} or "connection_string" in src:
        return _parse_sqlite_source(src)

    path_value = src.get("path")
    if isinstance(path_value, str | Path) and str(path_value).strip():
        return _parse_source(path_value)

    return [dict(src)]


def _parse_source(
    src: str | Path | list[dict[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(src, str | Path):
        path = Path(src)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            return _parse_csv(text)
        if suffix in {".xlsx", ".xls"}:
            return _parse_excel(path)
        if suffix in {".parquet", ".pq"}:
            return _parse_parquet(path)
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [dict(record) for record in parsed if isinstance(record, dict)]
        if isinstance(parsed, dict):
            return [dict(parsed)]
        raise ValueError(f"Unsupported source payload in {path}")
    if isinstance(src, Mapping):
        return _parse_source_descriptor(src)
    return list(src)


def _parse_csv(text: str) -> list[dict[str, Any]]:
    if not text or not text.strip():
        return []

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    reader.fieldnames = _canonicalize_csv_headers(reader.fieldnames or [])
    first_row = next(reader, None)
    if first_row is None:
        return []

    rows_iter = (
        reader
        if _looks_like_header_alias_row(
            reader.fieldnames,
            [first_row.get(field_name) for field_name in reader.fieldnames],
        )
        else chain((first_row,), reader)
    )
    rows: list[dict[str, Any]] = []
    for row in rows_iter:
        record: dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                continue
            record[key] = _coerce_csv_scalar(key, value)
        rows.append(record)
    return rows


def _parse_excel(path: Path) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Excel support requires openpyxl.") from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        row_iter = worksheet.values
        header_row = next(row_iter, None)
        if header_row is None:
            return []
        field_names = _canonicalize_csv_headers(list(header_row))
        first_row = next(row_iter, None)
        if first_row is None:
            return []

        rows_iter = (
            row_iter
            if _looks_like_header_alias_row(field_names, list(first_row))
            else chain((first_row,), row_iter)
        )
        rows: list[dict[str, Any]] = []
        for row in rows_iter:
            record: dict[str, Any] = {}
            for field_name, value in zip(field_names, row, strict=False):
                record[field_name] = _coerce_csv_scalar(field_name, value)
            rows.append(record)
        return rows
    finally:
        workbook.close()


def _parse_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Parquet support requires pyarrow.") from exc

    table = pq.read_table(path)
    return [
        {
            str(field_name): _coerce_csv_scalar(str(field_name), value)
            for field_name, value in record.items()
        }
        for record in table.to_pylist()
    ]


def _source_name(src: Any, idx: int) -> str:
    if isinstance(src, str | Path):
        return Path(src).stem
    if isinstance(src, Mapping):
        explicit_name = src.get("name")
        if isinstance(explicit_name, str) and explicit_name.strip():
            return explicit_name.strip()
        path_value = src.get("path")
        connection_string = src.get("connection_string")
        if isinstance(connection_string, str) and connection_string.strip():
            match = _SQLITE_DSN_RE.match(connection_string.strip())
            if match:
                path_value = match.group(1)
        if isinstance(path_value, str | Path) and str(path_value).strip():
            base_name = Path(path_value).stem
            table_name = src.get("table")
            if isinstance(table_name, str) and table_name.strip():
                return f"{base_name}_{table_name.strip()}"
            if isinstance(src.get("query"), str):
                return f"{base_name}_query"
            return base_name
    return f"source{idx}"
