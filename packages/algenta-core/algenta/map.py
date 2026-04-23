"""
algenta.map — Instant local data mapping. Zero dependencies. No API key.

"Connect and understand any dataset instantly — no schema, no ETL."

Quick start:

  from algenta import map_data, query_data

  # Map two CSV files
  result = map_data("sales.csv", "orders.csv")
  print(result.mappings)     # [{"source": "sales.revenue", "target": "orders.amount", ...}]
  print(result.join_keys)    # [{"field": "customer_id", ...}]

  # Query any data in plain English
  rows = query_data("total revenue by customer", records)
  print(rows)                # [{"customer": "Acme", "revenue": 125000}, ...]

  # Cloud: same interface, unlimited scale
  from algenta import AlgentaClient
  client = AlgentaClient(api_key="de_live_...")
  result = client.map("sales.csv", "orders.csv")
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sqlite3
import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any


@dataclass
class FieldMapping:
    source_field: str
    source: str
    target_field: str
    target: str
    confidence: float
    reason: list[str]
    match_type: str  # "exact", "semantic", "statistical"


@dataclass
class MapResult:
    sources_analyzed: int
    total_fields: int
    mappings: list[FieldMapping]
    unified_schema: list[dict[str, Any]]
    join_keys: list[dict[str, Any]]
    simulation_ready: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

_ABBREVS = {
    "qty": "quantity", "qnty": "quantity",
    "amt": "amount", "amnt": "amount",
    "rev": "revenue", "revs": "revenue",
    "cst": "cost",
    "cust": "customer", "cus": "customer",
    "prc": "price",
    "num": "number", "no": "number", "nbr": "number",
    "dt": "date", "ts": "timestamp",
}

_SYNONYMS: dict[str, set[str]] = {
    "revenue":  {"sales", "income", "receipts", "turnover"},
    "cost":     {"expense", "expenditure", "spending", "payment"},
    "quantity": {"qty", "count", "units", "volume"},
    "price":    {"rate", "unitprice", "unitcost"},
    "customer": {"client", "buyer", "account", "consumer"},
    "product":  {"item", "sku", "article"},
    "date":     {"timestamp", "datetime", "period"},
    "id":       {"key", "identifier", "number", "code", "ref"},
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


def _normalize(s: str) -> str:
    s = s.lower().strip()
    for ch in "_- ":
        s = s.replace(ch, "")
    return _ABBREVS.get(s, s)


def _ngrams(s: str, n: int = 2) -> set[str]:
    padded = f"_{s}_"
    return {padded[i:i + n] for i in range(len(padded) - n + 1)}


def _dice(a: str, b: str) -> float:
    if a == b:
        return 1.0
    ng_a = _ngrams(a)
    ng_b = _ngrams(b)
    inter = len(ng_a & ng_b)
    return 2 * inter / (len(ng_a) + len(ng_b)) if (ng_a or ng_b) else 0.0


def _semantic_similarity(name_a: str, name_b: str) -> tuple[float, list[str]]:
    norm_a = _normalize(name_a)
    norm_b = _normalize(name_b)
    if norm_a == norm_b:
        return 1.0, ["exact name match"]
    reasons: list[str] = []
    score = 0.0
    bigram = _dice(norm_a, norm_b)
    if bigram > 0.5:
        score = max(score, bigram)
        reasons.append(f"string similarity ({bigram:.0%})")
    if norm_a in norm_b or norm_b in norm_a:
        score = max(score, 0.80)
        reasons.append("name substring match")
    for canonical, syns in _SYNONYMS.items():
        all_terms = syns | {canonical}
        if norm_a in all_terms and norm_b in all_terms:
            score = max(score, 0.88)
            reasons.append(f"semantic synonym ({canonical})")
            break
    return min(score, 1.0), reasons


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


def _looks_like_header_alias_row(
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
    except sqlite3.Error as exc:  # pragma: no cover - error path exercised through runtime tests
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
    """Accept a file path, a local source descriptor, or pre-loaded records."""
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
    rows = []
    for row in rows_iter:
        rec: dict[str, Any] = {}
        for k, v in row.items():
            if k is None:
                continue
            rec[k] = _coerce_csv_scalar(k, v)
        rows.append(rec)
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


def _profile_field(values: list[Any]) -> dict[str, Any]:
    nums = [v for v in values if isinstance(v, int | float)]
    strs = [str(v) for v in values if not isinstance(v, int | float)]
    is_num = len(nums) > len(strs)
    p: dict[str, Any] = {
        "is_numeric": is_num,
        "numeric": nums,
        "strings": strs,
        "unique_count": len({str(v) for v in values[:500]}),
        "total_count": len(values),
    }
    if nums and len(nums) > 1:
        float_nums = [float(x) for x in nums if math.isfinite(float(x))]
        if len(float_nums) > 1:
            p["mean"] = sum(float_nums) / len(float_nums)
            mean_v = p["mean"]
            p["std"] = math.sqrt(sum((x - mean_v) ** 2 for x in float_nums) / (len(float_nums) - 1))
    return p


# ── Public API ────────────────────────────────────────────────────────────────

def map_data(
    *sources: str | Path | list[dict[str, Any]],
    names: list[str] | None = None,
    min_confidence: float = 0.5,
) -> MapResult:
    """
    Instantly map field relationships between data sources.

    Args:
        *sources:        File paths (CSV/JSON) or pre-loaded record lists.
        names:           Optional labels for each source (auto-derived from filename if omitted).
        min_confidence:  Minimum confidence threshold [0, 1] (default: 0.5).

    Returns:
        MapResult with .mappings, .join_keys, .unified_schema, .simulation_ready

    Examples:
        result = map_data("sales.csv", "orders.csv")
        result = map_data(sales_records, orders_records, names=["sales", "orders"])
    """
    parsed: dict[str, list[dict[str, Any]]] = {}
    for i, src in enumerate(sources):
        label = (names[i] if names and i < len(names) else None) or _source_name(src, i)
        parsed[label] = _parse_source(src)

    # Build field profiles
    profiles: dict[str, dict[str, dict[str, Any]]] = {}
    for src_name, records in parsed.items():
        if not records:
            continue
        prof: dict[str, dict[str, Any]] = {}
        for f in records[0].keys():
            vals = [r.get(f) for r in records[:2000] if f in r]
            prof[f] = _profile_field(vals)
        profiles[src_name] = prof

    # Find mappings
    mappings: list[FieldMapping] = []
    src_names = list(profiles.keys())
    for i in range(len(src_names)):
        for j in range(i + 1, len(src_names)):
            sa, sb = src_names[i], src_names[j]
            for fa, ia in profiles[sa].items():
                for fb, ib in profiles[sb].items():
                    score, reasons = _semantic_similarity(fa, fb)
                    if score >= 1.0:
                        match_type = "exact"
                    elif score > 0.5:
                        match_type = "semantic"
                    else:
                        match_type = "no_match"

                    # Boost with statistical similarity for numeric fields
                    if ia["is_numeric"] and ib["is_numeric"] and ia["numeric"] and ib["numeric"]:
                        stat_score = _stat_similarity(ia["numeric"], ib["numeric"])
                        if stat_score > 0.3:
                            score = min(score + stat_score * 0.3, 1.0)
                            reasons.append(f"similar distribution ({stat_score:.0%})")
                            if match_type == "no_match":
                                match_type = "statistical"

                    if score >= min_confidence and reasons:
                        mappings.append(FieldMapping(
                            source_field=fa, source=sa,
                            target_field=fb, target=sb,
                            confidence=round(score, 3),
                            reason=reasons[:3],
                            match_type=match_type,
                        ))

    mappings.sort(key=lambda m: m.confidence, reverse=True)

    # Unified schema
    unified: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src_name, prof in profiles.items():
        for f, info in prof.items():
            norm = _normalize(f)
            if norm not in seen:
                seen.add(norm)
                unified.append({
                    "name": f,
                    "sources": [src_name],
                    "is_numeric": info["is_numeric"],
                    "unique_count": info["unique_count"],
                    "total_count": info["total_count"],
                })
            else:
                for u in unified:
                    if _normalize(u["name"]) == norm and src_name not in u["sources"]:
                        u["sources"].append(src_name)
                        break

    # Join keys: high unique ratio fields that appear in mappings
    join_keys: list[dict[str, Any]] = []
    for src_name, prof in profiles.items():
        for f, info in prof.items():
            ur = info["unique_count"] / max(info["total_count"], 1)
            if ur > 0.85:
                for m in mappings:
                    if (m.source == src_name and m.source_field == f) or \
                       (m.target == src_name and m.target_field == f):
                        join_keys.append({
                            "field": f, "source": src_name,
                            "maps_to": m.target_field if m.source == src_name else m.source_field,
                            "in_source": m.target if m.source == src_name else m.source,
                            "confidence": m.confidence,
                        })
                        break

    # Simulation ready = has at least 2 numeric metric fields
    num_metric_fields = sum(
        1 for prof in profiles.values()
        for f, info in prof.items()
        if info["is_numeric"]
        and not any(kw in _normalize(f) for kw in {"id", "key", "number", "code"})
    )
    simulation_ready = num_metric_fields >= 2

    return MapResult(
        sources_analyzed=len(parsed),
        total_fields=len(seen),
        mappings=mappings,
        unified_schema=unified,
        join_keys=join_keys,
        simulation_ready=simulation_ready,
    )


# ── Query Without SQL ─────────────────────────────────────────────────────────

_AGG_KEYWORDS: dict[str, str] = {
    "total": "sum", "sum": "sum",
    "average": "mean", "avg": "mean", "mean": "mean",
    "count": "count", "number of": "count", "how many": "count",
    "max": "max", "maximum": "max", "highest": "max",
    "min": "min", "minimum": "min", "lowest": "min",
}

_METRIC_SYNONYMS: dict[str, list[str]] = {
    "revenue":  ["revenue", "sales", "income", "receipts", "ext_price", "extprice",
                 "extended_price", "total_price", "invoice_amount"],
    "cost":     ["cost", "expense", "spending", "ext_cost", "extcost", "extended_cost",
                 "total_cost", "expenditure"],
    "quantity": ["quantity", "qty", "units", "volume"],
    "price":    ["price", "unit_price", "unitprice", "rate", "list_price"],
    "amount":   ["amount", "total", "value"],
    "profit":   ["profit", "margin", "net"],
    "count":    ["count", "number"],
}


def query_data(
    query: str,
    *sources: str | Path | list[dict[str, Any]],
    names: list[str] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Query any data in plain English. No SQL. No schema.

    Args:
        query:    Natural language query (e.g., "total revenue by customer")
        *sources: File paths or record lists to query
        limit:    Max rows to return (default: 100)

    Returns:
        List of result dicts

    Examples:
        rows = query_data("total revenue by customer", "sales.csv")
        rows = query_data("average cost per product", records)
        rows = query_data("top 10 orders by amount", "orders.csv")
    """
    all_records: list[dict[str, Any]] = []
    for _i, src in enumerate(sources):
        all_records.extend(_parse_source(src))

    if not all_records:
        return []

    q = query.lower()

    # Aggregation
    aggregation = "sum"
    for kw, agg in _AGG_KEYWORDS.items():
        if kw in q:
            aggregation = agg
            break

    # "top N [entity] by [metric]" — e.g. "top 10 customers by revenue"
    top_entity_match = re.search(r'\btop\s+(\d+)\s+(\w+)\s+by\s+(\w+)', q)
    if top_entity_match:
        limit = int(top_entity_match.group(1))
        group_hint_raw = top_entity_match.group(2).rstrip("s")
        metric_word = top_entity_match.group(3)
        aggregation = "sum"
        metric_hint = None
        for canonical, terms in _METRIC_SYNONYMS.items():
            if metric_word in terms or metric_word == canonical:
                metric_hint = canonical
                break
        metric_hint = metric_hint or metric_word
        group_hint = group_hint_raw

        fields = list(all_records[0].keys()) if all_records else []

        def _best_field(hint: str | None, numeric_only: bool) -> str | None:
            if hint is None:
                candidates = (
                    [f for f in fields if _is_numeric_field(f, all_records)]
                    if numeric_only
                    else fields
                )
                return candidates[0] if candidates else None
            best, best_score = None, -1.0
            for f in fields:
                if numeric_only and not _is_numeric_field(f, all_records):
                    continue
                score, _ = _semantic_similarity(f, hint)
                for canonical, terms in _METRIC_SYNONYMS.items():
                    if hint in terms or hint == canonical:
                        for t in terms:
                            s2, _ = _semantic_similarity(f, t)
                            score = max(score, s2)
                if score > best_score:
                    best_score = score
                    best = f
            return best

        metric_field = _best_field(metric_hint, numeric_only=True)
        group_field = _best_field(group_hint, numeric_only=False)
        if group_field == metric_field:
            group_field = None
        return _execute(all_records, metric_field, group_field, aggregation, limit)

    # Simple "top N"
    top_match = re.search(r'\btop\s+(\d+)\b', q)
    if top_match:
        limit = int(top_match.group(1))
        aggregation = "sum"

    # Metric field
    metric_hint = None
    for canonical, terms in _METRIC_SYNONYMS.items():
        if any(t in q for t in terms):
            metric_hint = canonical
            break

    # Group by field
    group_hint = None
    for prep in ["by ", "per ", "for each ", "group by ", "grouped by "]:
        if prep in q:
            after = q.split(prep, 1)[1].strip()
            group_hint = re.split(r'[\s,]', after)[0].rstrip("s")
            break

    # Resolve actual field names
    fields = list(all_records[0].keys()) if all_records else []

    def _best_field(hint: str | None, numeric_only: bool) -> str | None:
        if hint is None:
            candidates = (
                [f for f in fields if _is_numeric_field(f, all_records)]
                if numeric_only
                else fields
            )
            return candidates[0] if candidates else None
        best, best_score = None, -1.0
        for f in fields:
            if numeric_only and not _is_numeric_field(f, all_records):
                continue
            score, _ = _semantic_similarity(f, hint)
            for canonical, terms in _METRIC_SYNONYMS.items():
                if hint in terms or hint == canonical:
                    for t in terms:
                        s2, _ = _semantic_similarity(f, t)
                        score = max(score, s2)
            if score > best_score:
                best_score = score
                best = f
        return best

    metric_field = _best_field(metric_hint, numeric_only=True)
    group_field = _best_field(group_hint, numeric_only=False) if group_hint else None

    if group_field == metric_field:
        group_field = None

    # Execute
    return _execute(all_records, metric_field, group_field, aggregation, limit)


def _is_numeric_field(f: str, records: list[dict[str, Any]]) -> bool:
    # Sample 50 evenly spaced rows across the full dataset to handle sparse fields
    n = len(records)
    if n == 0:
        return False
    step = max(1, n // 50)
    for i in range(0, n, step):
        if isinstance(records[i].get(f), int | float):
            return True
    return False


def _execute(
    records: list[dict[str, Any]],
    metric_field: str | None,
    group_field: str | None,
    aggregation: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not group_field:
        if not metric_field:
            return [{"count": len(records)}]
        vals = [
            r[metric_field]
            for r in records
            if isinstance(r.get(metric_field), int | float)
        ]
        return [{metric_field: round(_agg(vals, aggregation), 4), "count": len(vals)}]

    groups: dict[Any, list[float]] = {}
    for rec in records:
        gk = rec.get(group_field, "__unknown__")
        val = (
            float(rec.get(metric_field, 1))
            if metric_field and isinstance(rec.get(metric_field), int | float)
            else 1.0
        )
        groups.setdefault(gk, []).append(val)

    rows = []
    for gk, vals in groups.items():
        row: dict[str, Any] = {group_field: gk}
        if metric_field:
            row[metric_field] = round(_agg(vals, aggregation), 4)
        row["count"] = len(vals)
        rows.append(row)

    if metric_field:
        rows.sort(key=lambda r: r.get(metric_field, 0), reverse=True)
    return rows[:limit]


def _agg(vals: list[float], agg: str) -> float:
    if not vals:
        return 0.0
    return {"sum": sum, "mean": statistics.mean, "max": max,
            "min": min, "count": lambda v: float(len(v))}.get(agg, sum)(vals)


def _stat_similarity(a: list[float], b: list[float]) -> float:
    if len(a) < 3 or len(b) < 3:
        return 0.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    if ma > 0 and mb > 0:
        ratio = max(ma, mb) / max(min(ma, mb), 1)
        if ratio < 3:
            return 1 - (ratio - 1) / 2
    return 0.0


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
