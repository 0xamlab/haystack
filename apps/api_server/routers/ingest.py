"""
routers/ingest.py — Instant data ingestion with zero configuration.

POST /v1/ingest

Drop in raw CSV, JSON, or multiple tables. Get back a ready-to-run
simulation payload with auto-detected distributions, objective function,
and engine selection. Optionally run it immediately.

Powered by the Codna FieldMapper (field_mapper.mojo via the Mojo binary) which:
  - Detects variable polarity from field names (revenue → positive, cost → negative)
  - Infers distribution shape from value statistics (skewed → lognormal, bounded → triangular)
  - Detects units (USD, %, count, rate)
  - Constructs objective function from polarity
  - Finds join keys when multiple tables are provided
  - Selects the best simulation engine for your data shape

Falls back to Python mirror of field_mapper.mojo logic when binary is unavailable.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Ingest"])


# ── Field Mapper (Python mirror of field_mapper.mojo) ────────────────────────

_POS_KEYWORDS = {
    "revenue",
    "profit",
    "income",
    "sales",
    "growth",
    "return",
    "gain",
    "value",
    "benefit",
    "savings",
    "yield",
    "appreciation",
    "upside",
    "margin",
    "throughput",
    "capacity",
    "output",
}
_NEG_KEYWORDS = {
    "cost",
    "expense",
    "loss",
    "risk",
    "churn",
    "debt",
    "liability",
    "depreciation",
    "penalty",
    "fee",
    "overhead",
    "downside",
    "deficit",
    "waste",
    "error",
    "failure",
    "delay",
    "attrition",
    "writeoff",
    "default",
    "shortage",
}
_UNIT_HINTS = {
    "price": "currency",
    "revenue": "currency",
    "cost": "currency",
    "salary": "currency",
    "budget": "currency",
    "sales": "currency",
    "rate": "rate",
    "percent": "percentage",
    "pct": "percentage",
    "ratio": "percentage",
    "yield": "percentage",
    "count": "count",
    "quantity": "count",
    "units": "count",
    "days": "time",
    "months": "time",
    "years": "time",
    "hours": "time",
    "weight": "weight",
    "mass": "weight",
}


def _detect_polarity(name: str) -> int:
    """Returns +1 (positive), -1 (negative), 0 (neutral)."""
    lower = name.lower()
    if any(kw in lower for kw in _NEG_KEYWORDS):
        return -1
    if any(kw in lower for kw in _POS_KEYWORDS):
        return 1
    return 0


def _detect_unit(name: str) -> str:
    lower = name.lower()
    for kw, unit in _UNIT_HINTS.items():
        if kw in lower:
            return unit
    return ""


def _infer_distribution(values: list[float]) -> tuple[str, dict[str, float]]:
    """
    Infer distribution type and parameters from observed values.
    Returns (distribution_name, params_dict).
    """
    if not values:
        return "fixed", {"value": 0.0}

    n = len(values)
    lo = min(values)
    hi = max(values)

    if lo == hi:
        return "fixed", {"value": lo}

    mean_v = statistics.mean(values)
    std_v = statistics.stdev(values) if n > 1 else 0.0

    # Bernoulli: only 0 and 1
    unique = set(values)
    if unique <= {0.0, 1.0}:
        p = sum(1 for v in values if v == 1.0) / n
        return "bernoulli", {"p": round(p, 4)}

    # Beta: all values in [0, 1]
    if lo >= 0.0 and hi <= 1.0 and mean_v > 0 and mean_v < 1:
        return "beta", {"alpha": 2.0, "beta": 2.0}

    # All positive: check for lognormal (positive skew, cv > 0.3)
    if lo > 0 and std_v > 0:
        cv = std_v / mean_v
        # Skewness approximation via (mean - median) / std
        median_v = statistics.median(values)
        skew_approx = (mean_v - median_v) / (std_v + 1e-9)
        if cv > 0.3 and skew_approx > 0.1:
            sigma2 = math.log(1 + cv**2)
            mu = math.log(mean_v + 1e-9) - sigma2 / 2
            return "lognormal", {
                "mean": round(mu, 6),
                "std": round(math.sqrt(sigma2), 6),
            }

    # Default: triangular with observed range
    mode_v = mean_v  # use mean as mode estimate
    # Clamp mode inside [lo, hi]
    mode_v = max(lo, min(hi, mode_v))
    return "triangular", {
        "low": round(lo, 6),
        "mode": round(mode_v, 6),
        "high": round(hi, 6),
    }


def _field_stats(values: list[float]) -> dict[str, float]:
    n = len(values)
    if n == 0:
        return {}
    return {
        "count": n,
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values) if n > 1 else 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "median": round(statistics.median(values), 4),
    }


_ID_KEYWORDS = {
    "id",
    "_id",
    "number",
    "no",
    "num",
    "code",
    "key",
    "ref",
    "order",
    "po",
    "sku",
    "upc",
    "serial",
    "barcode",
    "masked",
    "line",
    "sequence",
    "seq",
    "index",
}
_METRIC_KEYWORDS = (
    _POS_KEYWORDS
    | _NEG_KEYWORDS
    | {
        "quantity",
        "qty",
        "amount",
        "total",
        "avg",
        "average",
        "rate",
        "percent",
        "pct",
        "score",
        "count",
        "days",
        "hours",
        "weight",
    }
)


def _is_likely_id_field(name: str, values: list[Any]) -> bool:
    """True if this column looks like an ID/key, not a business metric."""
    lower = name.lower()

    # If the name contains a metric keyword, it's a metric even if numeric
    if any(kw in lower for kw in _METRIC_KEYWORDS):
        return False

    # If the name contains an ID keyword and not a metric keyword, it's an ID
    if any(kw in lower for kw in _ID_KEYWORDS):
        return True

    # High-cardinality numeric integers often encode IDs
    unique_ratio = len(set(values)) / max(len(values), 1)
    if unique_ratio > 0.9 and all(
        isinstance(v, int | float) and float(v) == int(float(v))
        for v in values[:20]
        if v is not None
    ):
        return True

    return False


def _is_likely_key(values: list[Any]) -> bool:
    """True if this column looks like a primary/foreign key (high cardinality)."""
    unique_ratio = len({str(v) for v in values}) / max(len(values), 1)
    return unique_ratio > 0.9


async def _map_via_mojo(
    numeric_fields: dict[str, list[float]],
) -> dict[str, Any] | None:
    """
    Route field mapping through the Mojo binary's field_map engine.
    Returns parsed result dict or None if binary call fails.
    """
    try:
        from apps.api_server.compute.mojo_adapter import invoke_engine

        data = dict(numeric_fields)
        payload = {"engine_type": "field_map", "data": data}
        result = await invoke_engine(payload)
        return result
    except Exception as exc:
        logger.debug("field_map_mojo_failed", error=str(exc))
        return None


def map_records(
    records: list[dict[str, Any]],
    *,
    max_rows_for_analysis: int = 2000,
) -> dict[str, Any]:
    """
    Auto-map a list of records to a simulation payload.

    Returns:
        {
          "variables": [...],
          "objective_function": "...",
          "engine": "...",
          "engine_reason": "...",
          "field_analysis": {field: {polarity, unit, distribution, stats, ...}},
          "join_key_candidates": [...],
        }
    """
    if not records:
        return {"variables": [], "objective_function": "", "field_analysis": {}}

    # Limit analysis rows for performance
    sample = records[:max_rows_for_analysis]
    all_field_names = list(sample[0].keys())

    # Collect numeric values per field
    numeric_fields: dict[str, list[float]] = {}
    all_field_values: dict[str, list[Any]] = {}
    for rec in sample:
        for k, v in rec.items():
            all_field_values.setdefault(k, []).append(v)
            try:
                numeric_fields.setdefault(k, []).append(float(v))
            except (TypeError, ValueError):
                pass

    variables: list[dict[str, Any]] = []
    positive_vars: list[str] = []
    negative_vars: list[str] = []
    field_analysis: dict[str, Any] = {}
    join_key_candidates: list[str] = []

    for field in all_field_names:
        all_vals = all_field_values.get(field, [])
        num_vals = numeric_fields.get(field, [])

        # Detect join keys (non-numeric high-cardinality fields or numeric ID fields)
        is_text_key = len(num_vals) < len(all_vals) * 0.5 and _is_likely_key(all_vals)
        is_numeric_id = num_vals and _is_likely_id_field(field, num_vals)
        if is_text_key or is_numeric_id:
            join_key_candidates.append(field)
            field_analysis[field] = {
                "type": "key",
                "unique_values": len({str(v) for v in all_vals}),
                "sample_values": [str(v) for v in all_vals[:3]],
            }
            continue

        if not num_vals:
            continue

        polarity = _detect_polarity(field)
        unit = _detect_unit(field)
        dist, params = _infer_distribution(num_vals)
        stats = _field_stats(num_vals)

        variables.append(
            {
                "name": field,
                "distribution": dist,
                "params": params,
                "unit": unit,
            }
        )

        field_analysis[field] = {
            "type": "numeric",
            "polarity": polarity,
            "unit": unit,
            "distribution": dist,
            "params": params,
            "stats": stats,
        }

        if polarity >= 0:
            positive_vars.append(field)
        else:
            negative_vars.append(field)

    # Build objective function
    if positive_vars and negative_vars:
        obj_fn = " + ".join(positive_vars) + " - " + " - ".join(negative_vars)
    elif positive_vars:
        obj_fn = " + ".join(positive_vars)
    elif variables:
        obj_fn = variables[0]["name"]
    else:
        obj_fn = ""

    # Auto-select engine
    from apps.api_server.services.engine_selector import select_engine

    sel = select_engine(variables, runs=10000, objective=obj_fn)

    return {
        "variables": variables,
        "objective_function": obj_fn,
        "engine": sel.engine,
        "engine_reason": sel.reason,
        "field_analysis": field_analysis,
        "join_key_candidates": join_key_candidates,
    }


def _find_join_keys(
    analysis_a: dict[str, Any],
    analysis_b: dict[str, Any],
    records_a: list[dict[str, Any]],
    records_b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Find potential join keys between two tables using:
    1. Exact name match
    2. Fuzzy name match (simple substring)
    3. Value overlap (same values appear in both)
    """
    keys_a = {f for f, info in analysis_a["field_analysis"].items() if info.get("type") == "key"}
    keys_b = {f for f, info in analysis_b["field_analysis"].items() if info.get("type") == "key"}

    # Also check all fields that look like IDs/codes
    numeric_a = {f for f in records_a[0].keys() if f not in keys_a}
    numeric_b = {f for f in records_b[0].keys() if f not in keys_b}

    join_suggestions: list[dict[str, Any]] = []

    # Exact name match — highest confidence
    exact = keys_a & keys_b
    for k in exact:
        join_suggestions.append(
            {
                "field_a": k,
                "field_b": k,
                "match_type": "exact_name",
                "confidence": 0.95,
            }
        )

    # Fuzzy name match — check if names share common root
    if not join_suggestions:
        for ka in keys_a | numeric_a:
            for kb in keys_b | numeric_b:
                ka_lower, kb_lower = ka.lower(), kb.lower()
                if ka_lower == kb_lower:
                    continue  # already in exact
                # Simple containment check
                if ka_lower in kb_lower or kb_lower in ka_lower:
                    join_suggestions.append(
                        {
                            "field_a": ka,
                            "field_b": kb,
                            "match_type": "fuzzy_name",
                            "confidence": 0.70,
                        }
                    )

    # Value overlap check for remaining candidates
    if not join_suggestions and records_a and records_b:
        for fa in list(records_a[0].keys())[:5]:
            vals_a = {str(r.get(fa, "")) for r in records_a[:100]}
            for fb in list(records_b[0].keys())[:5]:
                vals_b = {str(r.get(fb, "")) for r in records_b[:100]}
                overlap = len(vals_a & vals_b) / max(len(vals_a | vals_b), 1)
                if overlap > 0.3:
                    join_suggestions.append(
                        {
                            "field_a": fa,
                            "field_b": fb,
                            "match_type": "value_overlap",
                            "confidence": round(overlap, 2),
                        }
                    )

    # Sort by confidence
    join_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    return join_suggestions[:5]  # Top 5 candidates


def _merge_records(
    records_a: list[dict[str, Any]],
    records_b: list[dict[str, Any]],
    key_a: str,
    key_b: str,
) -> list[dict[str, Any]]:
    """Inner join two record lists on key columns."""
    index: dict[str, list[dict[str, Any]]] = {}
    for r in records_b:
        k = str(r.get(key_b, ""))
        index.setdefault(k, []).append(r)

    merged: list[dict[str, Any]] = []
    for r in records_a:
        k = str(r.get(key_a, ""))
        for match in index.get(k, []):
            combined = {**r}
            for field, val in match.items():
                if field != key_b:
                    combined[f"b_{field}"] = val
            merged.append(combined)

    return merged


# ── Request / Response models ─────────────────────────────────────────────────


class IngestTable(BaseModel):
    """A single table of data."""

    name: str = Field("table", description="Label for this table")
    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array of records (list of dicts). Omit if providing csv.",
    )
    csv: str | None = Field(
        None,
        description="Raw CSV text. Parsed automatically.",
    )


class IngestRequest(BaseModel):
    """
    Drop in your data. Get back a ready-to-run simulation.

    Supports:
    - Single table: records or CSV text
    - Multiple tables: auto-detects join keys, merges, then analyzes

    No configuration required. The engine auto-detects everything.
    """

    tables: list[IngestTable] = Field(
        ...,
        min_length=1,
        description="One or more data tables. First table is primary.",
    )
    domain: str = Field(
        "",
        description=(
            "Optional domain hint (finance, supply_chain, hr, etc.) for better field mapping"
        ),
    )
    runs: int = Field(
        10000,
        ge=1000,
        le=1_000_000,
        description="Scenarios to evaluate",
    )
    auto_run: bool = Field(
        False,
        description="If true, run the simulation immediately and return results",
    )
    join_on: dict[str, str] | None = Field(
        None,
        description="Explicit join keys: {'table_a_field': 'table_b_field'}. "
        "If omitted, auto-detected.",
    )


class FieldInfo(BaseModel):
    type: str
    polarity: int | None = None
    unit: str | None = None
    distribution: str | None = None
    params: dict[str, float] | None = None
    stats: dict[str, float] | None = None
    unique_values: int | None = None


class IngestResponse(BaseModel):
    ingest_id: str
    records_analyzed: int
    fields_detected: int
    join_applied: bool
    join_key: dict[str, str] | None
    variables: list[dict[str, Any]]
    objective_function: str
    engine: str
    engine_reason: str
    field_analysis: dict[str, Any]
    simulation_payload: dict[str, Any]
    simulation_result: dict[str, Any] | None = None
    latency_ms: float


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/v1/ingest",
    response_model=IngestResponse,
    summary="Instant data ingestion — zero-config simulation from any table",
    description=(
        "**Drop in your data. Get back a ready-to-run simulation.**\n\n"
        "- Paste CSV text or send JSON records\n"
        "- Multiple tables: auto-detects join keys and merges\n"
        "- Auto-detects distributions, polarity, units, and objective function\n"
        "- Selects the best simulation engine for your data shape\n"
        "- Set `auto_run: true` to get simulation results immediately\n\n"
        "Powered by the Codna FieldMapper — same logic as `field_mapper.mojo`."
    ),
)
async def ingest(
    payload: IngestRequest,
    auth: AuthContext = Depends(get_current_org),
) -> IngestResponse:
    t0 = time.monotonic()
    ingest_id = str(uuid.uuid4())

    # ── Parse each table ──────────────────────────────────────────────────────
    parsed_tables: list[tuple[str, list[dict[str, Any]]]] = []
    for tbl in payload.tables:
        if tbl.csv:
            records = _parse_csv_text(tbl.csv)
        elif tbl.records:
            records = tbl.records
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "empty_table",
                        "message": f"Table '{tbl.name}' has neither records nor csv",
                    }
                },
            )
        if not records:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "empty_table",
                        "message": f"Table '{tbl.name}' parsed to 0 records",
                    }
                },
            )
        parsed_tables.append((tbl.name, records))

    # ── Auto-analyze each table via Mojo FieldMapper ─────────────────────────
    # Uses field_mapper.mojo through the binary for optimal detection.
    # Falls back to Python mirror if binary unavailable.
    table_analyses: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = []
    for name, recs in parsed_tables:
        py_analysis = map_records(recs)  # always compute Python version for join key detection

        # Collect numeric field arrays for Mojo field_map call
        numeric_for_mojo: dict[str, list[float]] = {}
        for field, info in py_analysis["field_analysis"].items():
            if info.get("type") == "numeric":
                # Rebuild numeric values list
                for rec in recs[:2000]:
                    try:
                        numeric_for_mojo.setdefault(field, []).append(float(rec.get(field, 0)))
                    except (TypeError, ValueError):
                        pass

        mojo_result = await _map_via_mojo(numeric_for_mojo) if numeric_for_mojo else None

        if mojo_result and mojo_result.get("variables"):
            # Merge Mojo result with Python analysis (Python has join key detection)
            merged_analysis = {
                **py_analysis,
                "variables": mojo_result["variables"],
                "objective_function": mojo_result["objective_function"],
                "engine": mojo_result.get("engine", py_analysis.get("engine", "monte_carlo")),
                "engine_reason": "Auto-detected via field_mapper.mojo",
            }
            # Merge field_analysis: Mojo has polarity/dist, Python has join key info
            for field, mojo_info in mojo_result.get("field_analysis", {}).items():
                if field in merged_analysis["field_analysis"]:
                    merged_analysis["field_analysis"][field].update(mojo_info)
            table_analyses.append((name, recs, merged_analysis))
            logger.info("field_map_mojo_used", table=name, fields=mojo_result.get("field_count", 0))
        else:
            table_analyses.append((name, recs, py_analysis))

    # ── Auto-join when multiple tables ───────────────────────────────────────
    join_applied = False
    join_key_used: dict[str, str] | None = None
    final_records: list[dict[str, Any]]
    final_analysis: dict[str, Any]

    if len(parsed_tables) == 1:
        final_records = parsed_tables[0][1]
        final_analysis = table_analyses[0][2]
    else:
        # Find best join key between first two tables
        name_a, recs_a, analysis_a = table_analyses[0]
        name_b, recs_b, analysis_b = table_analyses[1]

        if payload.join_on:
            key_a, key_b = list(payload.join_on.items())[0]
            join_key_used = {key_a: key_b}
        else:
            suggestions = _find_join_keys(analysis_a, analysis_b, recs_a, recs_b)
            if suggestions:
                best = suggestions[0]
                key_a, key_b = best["field_a"], best["field_b"]
                join_key_used = {key_a: key_b}
                logger.info(
                    "ingest_join_detected",
                    key_a=key_a,
                    key_b=key_b,
                    match_type=best["match_type"],
                    confidence=best["confidence"],
                )
            else:
                # No join key found — concatenate numeric fields from both
                key_a = key_b = None  # type: ignore[assignment]

        if key_a and key_b:
            merged = _merge_records(recs_a, recs_b, key_a, key_b)
            if merged:
                final_records = merged
                final_analysis = map_records(merged)
                join_applied = True
            else:
                logger.warning("ingest_join_no_matches", key_a=key_a, key_b=key_b)
                final_records = recs_a
                final_analysis = analysis_a
        else:
            final_records = recs_a
            final_analysis = analysis_a

    # ── Build simulation payload ──────────────────────────────────────────────
    sim_payload = {
        "mode": "expert",
        "simulation_model": final_analysis["engine"],
        "runs": payload.runs,
        "simulation": {
            "variables": final_analysis["variables"],
            "objective_function": final_analysis["objective_function"],
        },
    }

    # ── Auto-run simulation if requested ─────────────────────────────────────
    sim_result: dict[str, Any] | None = None
    if payload.auto_run and final_analysis["variables"]:
        try:
            from apps.api_server.schemas.simulate import SimulateRequestExpert
            from apps.api_server.services.simulation_service import run_simulation_fast

            req = SimulateRequestExpert.model_validate(sim_payload)
            envelope, _ = await run_simulation_fast(
                request=req,
                org_id=auth["org_id"],
                api_key_id=auth.get("key_id"),
            )
            m = envelope.metrics
            p = envelope.percentiles
            sim_result = {
                "run_id": str(envelope.run_id),
                "recommended_action": envelope.recommended_action,
                "confidence": envelope.confidence,
                "expected_value": m.expected_value,
                "std_deviation": m.std_deviation,
                "probability_of_loss": m.probability_of_loss,
                "percentiles": {"p5": p.p5, "p25": p.p25, "p50": p.p50, "p75": p.p75, "p95": p.p95},
                "scenarios_run": envelope.scenarios_run,
                "execution_ms": envelope.execution_ms,
            }
        except Exception as exc:
            logger.warning("ingest_auto_run_failed", error=str(exc))

    return IngestResponse(
        ingest_id=ingest_id,
        records_analyzed=len(final_records),
        fields_detected=len(final_analysis["variables"]),
        join_applied=join_applied,
        join_key=join_key_used,
        variables=final_analysis["variables"],
        objective_function=final_analysis["objective_function"],
        engine=final_analysis["engine"],
        engine_reason=final_analysis["engine_reason"],
        field_analysis=final_analysis["field_analysis"],
        simulation_payload=sim_payload,
        simulation_result=sim_result,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )


def _parse_csv_text(csv_text: str) -> list[dict[str, Any]]:
    """Parse CSV text into list of dicts. Auto-converts numeric strings."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    records: list[dict[str, Any]] = []
    for row in reader:
        record: dict[str, Any] = {}
        for k, v in row.items():
            v_stripped = v.strip() if v else ""
            # Try to parse as number
            try:
                record[k] = int(v_stripped)
            except ValueError:
                try:
                    # Remove currency symbols and commas
                    cleaned = v_stripped.replace(",", "").lstrip("$£€¥")
                    record[k] = float(cleaned)
                except ValueError:
                    record[k] = v_stripped
        records.append(record)
    return records
