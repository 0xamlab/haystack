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
import math
import re
import statistics
from dataclasses import dataclass
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


def _parse_source(src: str | Path | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accept a file path (str/Path) or pre-loaded records list."""
    if isinstance(src, str | Path):
        path = Path(src)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".csv":
            return _parse_csv(text)
        import json
        return json.loads(text)
    return list(src)


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    rows = []
    for row in reader:
        rec: dict[str, Any] = {}
        for k, v in row.items():
            v = (v or "").strip()
            try:
                rec[k] = int(v)
            except ValueError:
                try:
                    rec[k] = float(v.replace(",", "").lstrip("$£€¥"))
                except ValueError:
                    rec[k] = v
        rows.append(rec)
    return rows


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
    return f"source{idx}"
