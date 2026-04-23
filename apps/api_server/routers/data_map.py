"""
routers/data_map.py — Instant Semantic Data Layer.

"Connect and understand any dataset instantly — no schema, no ETL, no manual mapping."

POST /v1/map

Finds relationships between data sources:
  - Exact field name matches
  - Fuzzy semantic matches (revenue ↔ sales, qty ↔ quantity)
  - Statistical similarity (same value distributions)
  - Value overlap detection (shared primary/foreign keys)

Powers the data funnel:
  Upload data → Auto-map → Query → Run decisions → Upgrade

Uses the Algenta string-distance and vector-similarity Mojo libraries for
fuzzy matching. Python fallback is available for all operations.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from apps.api_server.compute.mojo_errors import (
    MojoEngineError,
    build_mojo_engine_status,
    coerce_mojo_engine_error,
    is_global_optional_mojo_circuit_error,
    is_optional_mojo_circuit_error,
    mojo_failure_reason,
    validate_mojo_payload,
)
from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.schemas.common import ErrorDetail, ErrorResponse
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import parse_delimited_records
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.source_artifact_cache import (
    load_cached_arrow_table,
    source_content_artifact_key,
    store_cached_arrow_table,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Data Mapping"])
settings = get_settings()
_MOJO_WARNING_COOLDOWN_S = 60.0
_MOJO_WARNING_STATE: dict[tuple[str, str], float] = {}
_MOJO_OPTIONAL_ENGINE_COOLDOWN_S = 60.0
_MOJO_OPTIONAL_ENGINE_FAILURE_STATE: dict[str, tuple[float, str]] = {}
_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY = "__global__"
_OPTIONAL_MOJO_TIMEOUT_S = float(
    os.environ.get("ALGENTA_OPTIONAL_MOJO_TIMEOUT_S", "2.0"),
)
_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES = int(
    os.environ.get("ALGENTA_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES", "1048576"),
)

# ── Two-speed pipeline store ──────────────────────────────────────────────────
# Keyed by map_id. Each entry holds the completed deep-analysis payload.
# Simple in-process dict — survives for the process lifetime (fine for Phase 1).
_deep_store: dict[str, dict[str, Any]] = {}
_DEEP_BUDGET_S = 0.20  # seconds — if Phase 2 finishes within this, embed in response


class MojoInstrumentationError(RuntimeError):
    """Raised when strict runtime policy forbids degrading a Mojo profiling failure."""

    def __init__(self, engine_type: str, message: str) -> None:
        super().__init__(message)
        self.engine_type = engine_type


def _log_mojo_warning(event: str, *, reason: str, **kwargs: Any) -> None:
    cache_key = (event, reason)
    now = time.monotonic()
    last_warning_at = _MOJO_WARNING_STATE.get(cache_key)
    if last_warning_at is not None and now - last_warning_at < _MOJO_WARNING_COOLDOWN_S:
        logger.debug(
            f"{event}_suppressed",
            cooldown_s=_MOJO_WARNING_COOLDOWN_S,
            reason=reason,
            **kwargs,
        )
        return

    _MOJO_WARNING_STATE[cache_key] = now
    logger.warning(
        event,
        cooldown_s=_MOJO_WARNING_COOLDOWN_S,
        reason=reason,
        **kwargs,
    )


def _get_optional_mojo_engine_reason(cache_key: str) -> str | None:
    cached = _MOJO_OPTIONAL_ENGINE_FAILURE_STATE.get(cache_key)
    if cached is None:
        return None
    failed_at, reason = cached
    if time.monotonic() - failed_at < _MOJO_OPTIONAL_ENGINE_COOLDOWN_S:
        return reason
    _MOJO_OPTIONAL_ENGINE_FAILURE_STATE.pop(cache_key, None)
    return None


def _get_optional_mojo_engine_skip_reason(engine_type: str) -> str | None:
    global_reason = _get_optional_mojo_engine_reason(_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY)
    if global_reason is not None:
        return global_reason
    return _get_optional_mojo_engine_reason(engine_type)


def _record_optional_mojo_engine_failure(engine_type: str, reason: BaseException | str) -> None:
    normalized_reason = mojo_failure_reason(reason)
    if not is_optional_mojo_circuit_error(reason):
        return
    failure = (time.monotonic(), normalized_reason)
    _MOJO_OPTIONAL_ENGINE_FAILURE_STATE[engine_type] = failure
    if is_global_optional_mojo_circuit_error(reason):
        _MOJO_OPTIONAL_ENGINE_FAILURE_STATE[_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY] = failure


def _clear_optional_mojo_engine_failure(engine_type: str) -> None:
    _MOJO_OPTIONAL_ENGINE_FAILURE_STATE.pop(engine_type, None)
    _MOJO_OPTIONAL_ENGINE_FAILURE_STATE.pop(_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY, None)


def _http_error(
    status_code: int,
    *,
    code: str,
    message: str,
    details: list[tuple[str | None, str]] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse.make(
            code=code,
            message=message,
            details=[
                ErrorDetail(field=field, issue=issue)
                for field, issue in (details or [])
            ],
        ).model_dump(mode="python"),
    )


# ── Fuzzy field matching (Python — mirrors fuzzy.mojo + string_distance.mojo) ─

def _normalize(s: str) -> str:
    """Normalize field name for comparison: lowercase, remove symbols, expand abbreviations."""
    s = s.lower().strip()
    # Remove common prefixes/suffixes
    for ch in "_- ":
        s = s.replace(ch, "")
    # Expand common abbreviations
    abbrevs = {
        "qty": "quantity", "qnty": "quantity",
        "amt": "amount", "amnt": "amount",
        "rev": "revenue", "revs": "revenue",
        "cst": "cost", "cts": "cost",
        "cus": "customer", "cust": "customer",
        "ord": "order",
        "prc": "price", "pr": "price",
        "no": "number", "num": "number", "nbr": "number",
        "dt": "date", "ts": "timestamp",
    }
    return abbrevs.get(s, s)


def _ngrams(s: str, n: int = 2) -> set[str]:
    """Character n-grams for fuzzy matching."""
    padded = f"_{s}_"
    return {padded[i:i+n] for i in range(len(padded) - n + 1)}


def _dice_coefficient(a: str, b: str, n: int = 2) -> float:
    """Sørensen-Dice coefficient on character bigrams [0, 1]."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ng_a = _ngrams(a, n)
    ng_b = _ngrams(b, n)
    intersection = len(ng_a & ng_b)
    return 2 * intersection / (len(ng_a) + len(ng_b))


def _semantic_similarity(name_a: str, name_b: str) -> tuple[float, list[str]]:
    """
    Compute semantic similarity between two field names.
    Returns (score, reasons).
    """
    if not name_a or not name_b:
        return 0.0, []

    norm_a = _normalize(name_a)
    norm_b = _normalize(name_b)
    reasons: list[str] = []

    # Exact match after normalization
    if norm_a == norm_b:
        return 1.0, ["exact name match"]

    score = 0.0

    # Bigram similarity
    bigram_sim = _dice_coefficient(norm_a, norm_b)
    if bigram_sim > 0.5:
        score = max(score, bigram_sim)
        reasons.append(f"string similarity ({bigram_sim:.0%})")

    # Substring containment
    if norm_a in norm_b or norm_b in norm_a:
        score = max(score, 0.80)
        reasons.append("name substring match")

    # Semantic synonyms
    synonyms_map: dict[str, set[str]] = {
        "revenue":  {"sales", "income", "receipts", "turnover", "topline"},
        "cost":     {"expense", "expenditure", "spending", "payment"},
        "quantity": {"qty", "count", "units", "volume", "amount"},
        "price":    {"rate", "unitprice", "unitcost", "tariff"},
        "customer": {"client", "buyer", "account", "consumer"},
        "product":  {"item", "sku", "article", "good"},
        "date":     {"timestamp", "datetime", "period", "time"},
        "id":       {"key", "identifier", "number", "code", "ref"},
    }
    for canonical, synonyms in synonyms_map.items():
        all_terms = synonyms | {canonical}
        if norm_a in all_terms and norm_b in all_terms:
            score = max(score, 0.88)
            reasons.append(f"semantic synonym ({canonical})")
            break

    return min(score, 1.0), reasons


def _value_distribution_similarity(
    vals_a: list[float],
    vals_b: list[float],
) -> tuple[float, list[str]]:
    """
    Compare statistical distributions of two numeric field value sets.
    Returns (score, reasons).
    """
    if len(vals_a) < 3 or len(vals_b) < 3:
        return 0.0, []

    reasons: list[str] = []
    score = 0.0

    mean_a = statistics.mean(vals_a)
    mean_b = statistics.mean(vals_b)
    std_a = statistics.stdev(vals_a) if len(vals_a) > 1 else 0.0
    std_b = statistics.stdev(vals_b) if len(vals_b) > 1 else 0.0

    # Similar magnitude (within 2 orders of magnitude)
    if mean_a > 0 and mean_b > 0:
        mag_ratio = max(mean_a, mean_b) / max(min(mean_a, mean_b), 1)
        if mag_ratio < 3:
            magnitude_sim = 1 - (mag_ratio - 1) / 2
            score = max(score, magnitude_sim * 0.4)
            reasons.append(f"similar value range ({magnitude_sim:.0%})")

    # Similar coefficient of variation (same distributional shape)
    cv_a = std_a / max(abs(mean_a), 1)
    cv_b = std_b / max(abs(mean_b), 1)
    cv_diff = abs(cv_a - cv_b)
    if cv_diff < 0.2:
        score = max(score, 0.35)
        reasons.append("same spread pattern")

    # Value overlap (shared values → likely same data)
    set_a = {round(v, 2) for v in vals_a[:200]}
    set_b = {round(v, 2) for v in vals_b[:200]}
    if set_a and set_b:
        overlap = len(set_a & set_b) / max(len(set_a | set_b), 1)
        if overlap > 0.3:
            score = max(score, overlap)
            reasons.append(f"value overlap ({overlap:.0%})")

    return min(score, 1.0), reasons


# ── Data source models ────────────────────────────────────────────────────────

class DataSource(BaseModel):
    """
    A data source to map. Every format normalizes to list[dict] internally.

    Inline (no external dependency):
      `records`    — JSON array of objects (fastest)
      `csv`        — raw CSV text
      `json_str`   — raw JSON array/object text (nested JSON is auto-flattened)
      `url`        — HTTP(S) URL; format auto-detected from Content-Type / extension

    Binary files (base64-encoded for API transport):
      `excel_b64`  — Excel .xlsx file, base64-encoded
      `parquet_b64`— Parquet file, base64-encoded

    Connector config (routes through ConnectorRegistry):
      `connection` — dict with `type` + connector-specific keys:
        {"type": "sql",        "connection_string": "postgresql+asyncpg://...",
         "query": "SELECT ..."}
        {"type": "sql",        "connection_string": "sqlite+aiosqlite:///db.sqlite", "query": "..."}
        {"type": "rest_api",   "url": "https://...", "data_path": "data.items"}
        {"type": "s3",         "bucket": "my-bucket", "key": "data/sales.parquet"}
        {"type": "gcs",        "bucket": "my-bucket", "blob": "data/orders.csv"}
        {"type": "azure_blob", "connection_string": "DefaultEndpointsProtocol=...",
                               "container": "data", "blob": "sales.parquet"}
    """
    name: str = Field(
        ...,
        description="Label for this source (e.g., 'sales', 'orders')",
    )
    dataset_id: str | None = Field(
        None,
        description="Public dataset ID alias for a registered source.",
    )
    source_id: str | None = Field(
        None,
        description="Registered source ID; fastest path and avoids re-uploading data.",
    )
    records: list[dict[str, Any]] | None = Field(None, description="Inline JSON records")
    csv: str | None = Field(None, description="Raw CSV text")
    json_str: str | None = Field(
        None,
        description="Raw JSON array/object text (nested auto-flattened)",
    )
    url: str | None = Field(None, description="HTTP URL — format auto-detected")
    excel_b64: str | None = Field(None, description="Excel .xlsx file, base64-encoded")
    parquet_b64: str | None = Field(None, description="Parquet file, base64-encoded")
    connection: dict[str, Any] | None = Field(
        None,
        description="Connector config dict — see DataSource docstring for all types",
    )
    table: str | None = Field(None, description="Legacy field — use connection instead")

    @model_validator(mode="after")
    def _sync_registered_aliases(self) -> DataSource:
        if self.dataset_id and not self.source_id:
            self.source_id = self.dataset_id
        elif self.source_id and not self.dataset_id:
            self.dataset_id = self.source_id
        return self


class FieldMapping(BaseModel):
    source_field: str
    source: str
    target_field: str
    target: str
    confidence: float = Field(..., ge=0, le=1)
    reason: list[str]
    match_type: str  # "exact", "semantic", "statistical", "value_overlap"


class SchemaField(BaseModel):
    name: str
    sources: list[str]
    distribution: str | None = None
    unit: str | None = None
    polarity: int | None = None  # +1 positive, -1 negative, 0 neutral
    sample_values: list[Any] = []


class MapRequest(BaseModel):
    """
    Drop in any data sources. Get back semantic field mappings and a unified schema.

    No configuration required. The engine auto-detects:
    - Which fields represent the same concept across sources
    - Distribution shapes for numeric fields
    - Polarity (revenue → positive, cost → negative)
    - Primary/foreign keys for joins
    - Confidence and reasoning for every mapping
    """
    sources: list[DataSource] = Field(
        ...,
        min_length=1,
        description="Data sources to map (CSV, JSON records, or table name)",
    )
    min_confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for mappings (default: 0.5)",
    )
    include_statistics: bool = Field(
        True,
        description="Include value distribution statistics in response",
    )


class MapResponse(BaseModel):
    map_id: str
    sources_analyzed: int
    total_fields: int
    mappings: list[FieldMapping]
    unified_schema: list[SchemaField]
    # Phase 2 fields — populated immediately if analysis finishes within budget,
    # otherwise empty and deep_analysis_pending=True (poll GET /v1/map/{map_id}).
    join_keys: list[dict[str, Any]]
    derived_relationships: list[dict[str, Any]]
    simulation_ready: bool
    simulation_payload: dict[str, Any] | None
    deep_analysis_pending: bool = False
    latency_ms: float


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/v1/map/{map_id}",
    summary="Poll for deep analysis (join keys + derived relationships)",
    description=(
        "When `POST /v1/map` returns `deep_analysis_pending: true`, poll this "
        "endpoint with the `map_id` to retrieve join keys, derived relationships, "
        "and the simulation payload once Phase 2 analysis completes."
    ),
)
async def get_deep_analysis(
    map_id: str,
    auth: AuthContext = Depends(get_current_org),
) -> dict[str, Any]:
    if map_id not in _deep_store:
        raise HTTPException(status_code=404, detail="map_id not found or still processing")
    return _deep_store[map_id]


@router.post(
    "/v1/map",
    response_model=MapResponse,
    summary="Instantly map any dataset — no schema, no ETL",
    description=(
        "**Connect and understand any dataset instantly.**\n\n"
        "Drop in CSV files, JSON records, or table names from multiple sources. "
        "Get back a unified schema with every field mapped, explained, and ready "
        "to run decisions on.\n\n"
        "**What it detects:**\n"
        "- Matching fields across sources (revenue ↔ sales, qty ↔ quantity)\n"
        "- Value distributions (lognormal for prices, triangular for ranges)\n"
        "- Polarity (cost → negative, revenue → positive)\n"
        "- Join keys between tables (background if slow)\n"
        "- Derived formulas A×B≈C (background if slow)\n"
        "- Confidence and plain-English reasoning for every mapping\n\n"
        "**Two-speed pipeline:** Phase 1 (schema + column matches) returns in "
        "<300ms. Phase 2 (join detection + relation detection) is embedded in "
        "the response if it finishes within 200ms, otherwise `deep_analysis_pending: "
        "true` is set and results can be retrieved via `GET /v1/map/{map_id}`.\n\n"
        "**The data funnel:** Upload → Map → Query → Decide → Optimize"
    ),
)
async def map_sources(
    payload: MapRequest,
    auth: AuthContext = Depends(get_current_org),
) -> MapResponse:
    t0 = time.monotonic()
    map_id = str(uuid.uuid4())
    org_id = str(auth["org_id"])

    # ── Parse sources ─────────────────────────────────────────────────────────
    parsed: dict[str, list[dict[str, Any]]] = {}
    for src in payload.sources:
        parsed[src.name] = await _load_source(src, org_id=org_id)

    # ── Extract field profiles per source ────────────────────────────────────
    source_profiles: dict[str, dict[str, dict[str, Any]]] = {}
    for src_name, records in parsed.items():
        if not records:
            continue
        profile: dict[str, dict[str, Any]] = {}
        n_recs = len(records)
        step = max(1, n_recs // 50)  # sample ~50 points across full dataset

        for field in records[0].keys():
            numeric_vals: list[float] = []
            string_vals: list[str] = []
            seen_n: set[float] = set()
            seen_s: set[str] = set()

            # Evenly-spaced sample across full dataset (catches sparse columns)
            for idx in range(0, n_recs, step):
                v = records[idx].get(field)
                if v is None:
                    continue
                try:
                    fv = float(v)
                    if fv not in seen_n:
                        seen_n.add(fv)
                        numeric_vals.append(fv)
                except (TypeError, ValueError):
                    sv = str(v)
                    if sv not in seen_s:
                        seen_s.add(sv)
                        string_vals.append(sv)

            # Dense sample from first 2000 rows for statistics
            all_numeric: list[float] = []
            all_strings: list[str] = []
            for rec in records[:2000]:
                v = rec.get(field)
                if v is None:
                    continue
                try:
                    all_numeric.append(float(v))
                except (TypeError, ValueError):
                    all_strings.append(str(v))

            profile[field] = {
                "numeric": all_numeric,
                "strings": all_strings,
                "is_numeric": len(all_numeric) > len(all_strings),
                "unique_count": len({str(v) for v in (all_numeric or all_strings)[:200]}),
                "total_count": len(all_numeric) + len(all_strings),
                # Sparse-safe sample for Mojo profiler
                "sample_values": [str(v) for v in numeric_vals[:100]] + string_vals[:100],
            }
            if all_numeric:
                nn = len(all_numeric)
                mean = sum(all_numeric) / nn
                profile[field]["mean"] = mean
                profile[field]["std"] = math.sqrt(
                    sum((x - mean) ** 2 for x in all_numeric) / max(nn - 1, 1)
                )
                profile[field]["min"] = min(all_numeric)
                profile[field]["max"] = max(all_numeric)

        source_profiles[src_name] = profile

    source_names = list(source_profiles.keys())

    # ── Phase 1a: Mojo column profiler — run all sources concurrently ─────────
    def _make_profiler_input(profile: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return _build_mojo_column_profile_columns(
            profile,
            value_limit=200,
            string_limit=100,
        )

    try:
        profiler_results = await asyncio.gather(*[
            _call_mojo_column_profile(_make_profiler_input(profile))
            for profile in source_profiles.values()
        ])
    except MojoInstrumentationError as exc:
        raise _http_error(
            503,
            code="mojo_instrumentation_unavailable",
            message=(
                "Mojo column profiling is unavailable while strict runtime "
                "fallbacks are disabled."
            ),
            details=[("engine_type", exc.engine_type)],
        ) from exc
    source_mojo_profiles: dict[str, dict[str, Any]] = {
        name: (result or {})
        for name, result in zip(source_profiles.keys(), profiler_results, strict=False)
    }

    # ── Phase 1b: Mojo column_match — all pairs concurrently ─────────────────
    match_pairs = [
        (source_names[i], source_names[j])
        for i in range(len(source_names))
        for j in range(i + 1, len(source_names))
    ]

    match_results = await asyncio.gather(*[
        _call_mojo_column_match(
            src_a, src_b,
            _build_matcher_input(source_profiles[src_a], source_mojo_profiles.get(src_a, {})),
            _build_matcher_input(source_profiles[src_b], source_mojo_profiles.get(src_b, {})),
            min_confidence=payload.min_confidence,
        )
        for src_a, src_b in match_pairs
    ])

    mappings: list[FieldMapping] = []
    for (src_a, src_b), match_result in zip(match_pairs, match_results, strict=False):
        if match_result and "matches" in match_result:
            best = _hungarian_greedy(match_result["matches"])
            for m in best:
                tier = _match_tier(m["score"])
                if tier == "rejected":
                    continue
                mappings.append(FieldMapping(
                    source_field=m["field_a"],
                    source=src_a,
                    target_field=m["field_b"],
                    target=src_b,
                    confidence=round(m["score"], 3),
                    reason=_build_match_reasons(m),
                    match_type=m.get("match_type", "semantic"),
                ))
        else:
            # Python fallback
            prof_a = source_profiles[src_a]
            prof_b = source_profiles[src_b]
            py_pairs: list[tuple[float, FieldMapping]] = []
            for field_a, info_a in prof_a.items():
                for field_b, info_b in prof_b.items():
                    reasons: list[str] = []
                    best_score = 0.0
                    match_type = "no_match"
                    sem_score, sem_reasons = _semantic_similarity(field_a, field_b)
                    if sem_score > 0.5:
                        best_score = max(best_score, sem_score)
                        reasons.extend(sem_reasons)
                        match_type = "exact" if sem_score >= 1.0 else "semantic"
                    if info_a["is_numeric"] and info_b["is_numeric"]:
                        stat_score, stat_reasons = _value_distribution_similarity(
                            info_a["numeric"], info_b["numeric"]
                        )
                        if stat_score > 0.3:
                            best_score = max(best_score, min(best_score + stat_score * 0.3, 1.0))
                            reasons.extend(stat_reasons)
                            if match_type == "no_match":
                                match_type = "statistical"
                    if best_score >= payload.min_confidence and reasons:
                        py_pairs.append((best_score, FieldMapping(
                            source_field=field_a,
                            source=src_a,
                            target_field=field_b,
                            target=src_b,
                            confidence=round(best_score, 3),
                            reason=reasons[:3],
                            match_type=match_type,
                        )))
            used_a: set[str] = set()
            used_b: set[str] = set()
            for _, fm in sorted(py_pairs, key=lambda x: x[0], reverse=True):
                if fm.source_field not in used_a and fm.target_field not in used_b:
                    used_a.add(fm.source_field)
                    used_b.add(fm.target_field)
                    mappings.append(fm)

    # Sort by confidence descending
    mappings.sort(key=lambda m: m.confidence, reverse=True)

    # ── Build unified schema (Mojo profiler → semantic types) ─────────────────
    unified: dict[str, SchemaField] = {}
    all_fields_seen: set[str] = set()

    for src_name, profile in source_profiles.items():
        mojo_profiles = source_mojo_profiles.get(src_name, {}).get("profiles", {})
        numeric_arrays = {f: info["numeric"] for f, info in profile.items()
                         if info["is_numeric"] and info["numeric"]}
        mojo_field_result = await _call_mojo_field_map(numeric_arrays) if numeric_arrays else None

        for field, info in profile.items():
            canonical = field
            for existing_key in unified:
                sim, _ = _semantic_similarity(field, existing_key)
                if sim > 0.85:
                    canonical = existing_key
                    break

            if canonical not in unified:
                polarity = 0
                dist = None
                unit = None

                fp = mojo_profiles.get(field, {})
                if fp:
                    polarity = fp.get("polarity", 0)
                    dist = fp.get("distribution") or None
                    unit = fp.get("unit_hint") or None
                elif mojo_field_result and field in mojo_field_result.get("field_analysis", {}):
                    fa_info = mojo_field_result["field_analysis"][field]
                    polarity = fa_info.get("polarity", 0)
                    dist = fa_info.get("distribution")
                    unit = fa_info.get("unit", "") or None

                unified[canonical] = SchemaField(
                    name=canonical,
                    sources=[src_name],
                    distribution=dist,
                    unit=unit,
                    polarity=polarity,
                    sample_values=(
                        info["numeric"][:3]
                        if info["is_numeric"]
                        else info["strings"][:3]
                    ),
                )
            else:
                if src_name not in unified[canonical].sources:
                    unified[canonical].sources.append(src_name)

            all_fields_seen.add(canonical)

    # ── Phase 2: Join detection + Relation detection (background task) ───────
    # Kicked off concurrently. If it completes within _DEEP_BUDGET_S it is
    # embedded in the response; otherwise the client polls GET /v1/map/{map_id}.

    async def _run_deep_analysis() -> dict[str, Any]:
        # Join keys — all pairs concurrently
        def _join_col_input(src_a: str, src_b: str) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for src_n in (src_a, src_b):
                for field, info in source_profiles[src_n].items():
                    all_vals = [str(v) for v in info["numeric"][:100]] + info["strings"][:100]
                    ur = info["unique_count"] / max(info["total_count"], 1)
                    result[f"{src_n}.{field}"] = {
                        "values": all_vals[:200],
                        "unique_ratio": ur,
                        "sample_size": info["total_count"],
                    }
            return result

        join_results = await asyncio.gather(*[
            _call_mojo_join_detect(src_a, src_b, _join_col_input(src_a, src_b), min_confidence=0.4)
            for src_a, src_b in match_pairs
        ])

        join_keys: list[dict[str, Any]] = []
        for (src_a, src_b), jr in zip(match_pairs, join_results, strict=False):
            if jr and "join_keys" in jr:
                join_keys.extend(jr["join_keys"])
            elif not jr:
                # Python fallback
                for src_n in (src_a, src_b):
                    for field, info in source_profiles[src_n].items():
                        ur = info["unique_count"] / max(info["total_count"], 1)
                        if ur > 0.85:
                            for m in mappings:
                                if (m.source == src_n and m.source_field == field) or \
                                   (m.target == src_n and m.target_field == field):
                                    join_keys.append({
                                        "field": field,
                                        "source": src_n,
                                        "mapped_to": (
                                            m.target_field
                                            if m.source == src_n
                                            else m.source_field
                                        ),
                                        "in_source": m.target if m.source == src_n else m.source,
                                        "confidence": m.confidence,
                                    })
                                    break

        # Relation detection — all sources concurrently
        def _rel_cols(src_name: str, records: list[dict]) -> dict[str, list[float]]:
            profile = source_profiles.get(src_name, {})
            num_fields = [f for f, info in profile.items() if info["is_numeric"]]
            n_sample = min(len(records), 500)
            result: dict[str, list[float]] = {}
            for f in num_fields:
                vals: list[float] = []
                for idx in range(n_sample):
                    v = records[idx].get(f, 0)
                    try:
                        vals.append(float(v) if v else 0.0)
                    except (TypeError, ValueError):
                        vals.append(0.0)
                result[f] = vals
            return result

        rel_inputs = [(name, _rel_cols(name, recs)) for name, recs in parsed.items()]
        rel_results = await asyncio.gather(*[
            _call_mojo_relation_detect(name, cols)
            for name, cols in rel_inputs
        ])

        derived_relationships: list[dict[str, Any]] = []
        for (src_name, _mojo_cols), rel_result in zip(rel_inputs, rel_results, strict=False):
            if rel_result and "relationships" in rel_result:
                for r in rel_result["relationships"]:
                    r["source"] = src_name
                derived_relationships.extend(rel_result["relationships"])
            else:
                profile = source_profiles.get(src_name, {})
                num_fields = [f for f, info in profile.items() if info["is_numeric"]]
                derived_relationships.extend(
                    _detect_derived_relationships(parsed[src_name], num_fields, source=src_name)
                )
        derived_relationships.sort(key=lambda r: r["confidence"], reverse=True)

        # Simulation payload
        sim_payload_inner: dict[str, Any] | None = None
        simulation_ready_inner = False
        metric_fields = [
            field for field, schema in unified.items()
            if schema.distribution and schema.distribution != "fixed"
            and not any(kw in _normalize(field) for kw in {"id", "key", "number", "code", "ref"})
        ]
        if metric_fields:
            primary_recs = list(parsed.values())[0] if parsed else []
            primary_numeric = {
                f: [
                    float(r.get(f, 0))
                    for r in primary_recs[:2000]
                    if isinstance(r.get(f), int | float)
                ]
                for f in metric_fields
            }
            mojo_r = await _call_mojo_field_map(primary_numeric) if primary_numeric else None
            if mojo_r and mojo_r.get("variables"):
                sim_payload_inner = {
                    "mode": "expert",
                    "simulation_model": mojo_r.get("engine", "monte_carlo"),
                    "runs": 10000,
                    "simulation": {
                        "variables": mojo_r["variables"],
                        "objective_function": mojo_r["objective_function"],
                    },
                }
                simulation_ready_inner = True

        return {
            "map_id": map_id,
            "join_keys": join_keys,
            "derived_relationships": derived_relationships,
            "simulation_ready": simulation_ready_inner,
            "simulation_payload": sim_payload_inner,
        }

    # Try to complete Phase 2 within budget; otherwise return immediately
    deep_task = asyncio.create_task(_run_deep_analysis())
    try:
        deep = await asyncio.wait_for(asyncio.shield(deep_task), timeout=_DEEP_BUDGET_S)
        _deep_store[map_id] = deep
        deep_pending = False
    except TimeoutError:
        # Phase 2 still running — store result when it finishes
        deep_pending = True
        deep = {
            "join_keys": [],
            "derived_relationships": [],
            "simulation_ready": False,
            "simulation_payload": None,
        }

        async def _persist_deep() -> None:
            try:
                result = await deep_task
                _deep_store[map_id] = result
            except Exception as exc:
                logger.debug("deep_analysis_error", map_id=map_id, error=str(exc))

        asyncio.create_task(_persist_deep())

    return MapResponse(
        map_id=map_id,
        sources_analyzed=len(parsed),
        total_fields=len(all_fields_seen),
        mappings=mappings,
        unified_schema=list(unified.values()),
        join_keys=deep["join_keys"],
        derived_relationships=deep["derived_relationships"],
        simulation_ready=deep["simulation_ready"],
        simulation_payload=deep["simulation_payload"],
        deep_analysis_pending=deep_pending,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )


# ── Global matching helpers ────────────────────────────────────────────────────

def _match_tier(score: float) -> str:
    """Categorise a match score into action tiers."""
    if score >= 0.85:
        return "strong"
    if score >= 0.60:
        return "suggested"
    if score >= 0.40:
        return "weak"
    return "rejected"


def _build_match_reasons(match: dict[str, Any]) -> list[str]:
    """Convert Mojo sub-scores into human-readable reasons."""
    reasons: list[str] = []
    n = match.get("name_score", 0.0)
    t = match.get("type_score", 0.0)
    p = match.get("polarity_score", 0.0)
    d = match.get("dist_score", 0.0)
    if n >= 0.99:
        reasons.append("exact name match")
    elif n >= 0.70:
        reasons.append(f"name similarity ({n:.0%})")
    if t >= 0.90:
        reasons.append("same semantic type")
    elif t >= 0.50:
        reasons.append("compatible types")
    if d >= 0.50:
        reasons.append("similar distribution")
    if p >= 0.90 and not reasons:
        reasons.append("same polarity")
    return reasons or [f"combined score {match.get('score', 0):.2f}"]


def _build_matcher_input(
    py_profile: dict[str, dict[str, Any]],
    mojo_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build columns_a / columns_b list for Mojo column_matcher from profiler output."""
    mojo_fields = mojo_profile.get("profiles", {}) if mojo_profile else {}
    result: list[dict[str, Any]] = []
    for field, info in py_profile.items():
        mp = mojo_fields.get(field, {})
        result.append({
            "name": field,
            "semantic_type": mp.get(
                "semantic_type",
                "metric" if info["is_numeric"] else "category",
            ),
            "polarity": mp.get("polarity", 0),
            "distribution": mp.get("distribution", ""),
            "mean": info.get("mean", 0.0),
            "std": info.get("std", 0.0),
        })
    return result


def _hungarian_greedy(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Greedy bipartite matching: each column A and each column B gets at most one partner.
    Sorts by score descending and assigns first-come-first-served.
    O(n log n) — good approximation of optimal assignment for typical dataset sizes.
    """
    used_a: set[str] = set()
    used_b: set[str] = set()
    result: list[dict[str, Any]] = []
    for m in sorted(matches, key=lambda x: x["score"], reverse=True):
        fa, fb = m["field_a"], m["field_b"]
        if fa not in used_a and fb not in used_b:
            used_a.add(fa)
            used_b.add(fb)
            result.append(m)
    return result


# ── Derived relationship detection ────────────────────────────────────────────

def _pearson_correlation(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return 0.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    den_b = math.sqrt(sum((x - mean_b) ** 2 for x in b))
    if den_a < 1e-10 or den_b < 1e-10:
        return 0.0
    return num / (den_a * den_b)


def _check_approx(predicted: list[float], actual: list[float], threshold: float = 0.05) -> bool:
    """True if predicted ≈ actual in ≥ 85% of non-zero rows (relative error < threshold)."""
    n = min(len(predicted), len(actual))
    if n < 3:
        return False
    matches = 0
    valid = 0
    for i in range(n):
        if abs(actual[i]) < 1e-9:
            continue
        valid += 1
        if abs(predicted[i] - actual[i]) / abs(actual[i]) <= threshold:
            matches += 1
    return valid >= 3 and matches / valid >= 0.85


def _detect_derived_relationships(
    records: list[dict[str, Any]],
    numeric_fields: list[str],
    source: str = "",
    sample_size: int = 500,
    min_confidence: float = 0.70,
) -> list[dict[str, Any]]:
    """
    Detect A×B≈C and A+B≈C formulaic relationships between numeric columns.

    No arbitrary row cap — every relationship above min_confidence is returned.
    The O(n³) triple scan is bounded by numeric column count per source, not row
    count, so it stays tractable even for wide ERP tables (say 50 numeric cols →
    ~19,600 triples per source).

    Returns list sorted by confidence descending.
    """
    n = min(len(records), sample_size)
    if n < 3 or len(numeric_fields) < 3:
        return []

    cols: dict[str, list[float]] = {}
    for f in numeric_fields:
        vals: list[float] = []
        for i in range(n):
            v = records[i].get(f)
            try:
                vals.append(float(v))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                vals.append(0.0)
        cols[f] = vals

    seen: set[frozenset] = set()
    results: list[dict[str, Any]] = []

    for fc in numeric_fields:
        vals_c = cols[fc]
        if all(abs(v) < 1e-9 for v in vals_c):
            continue

        for i, fa in enumerate(numeric_fields):
            if fa == fc:
                continue
            vals_a = cols[fa]

            for j in range(i + 1, len(numeric_fields)):
                fb = numeric_fields[j]
                if fb == fc:
                    continue
                triple = frozenset([fa, fb, fc])
                if triple in seen:
                    continue
                seen.add(triple)

                vals_b = cols[fb]

                products = [vals_a[k] * vals_b[k] for k in range(n)]
                if _check_approx(products, vals_c):
                    conf = abs(_pearson_correlation(products, vals_c))
                    if conf >= min_confidence:
                        results.append({
                            "formula": f"{fc} = {fa} × {fb}",
                            "source": source,
                            "field_result": fc,
                            "field_a": fa,
                            "field_b": fb,
                            "operation": "multiply",
                            "confidence": round(conf, 3),
                        })

                sums = [vals_a[k] + vals_b[k] for k in range(n)]
                if _check_approx(sums, vals_c):
                    conf = abs(_pearson_correlation(sums, vals_c))
                    if conf >= min_confidence:
                        results.append({
                            "formula": f"{fc} = {fa} + {fb}",
                            "source": source,
                            "field_result": fc,
                            "field_a": fa,
                            "field_b": fb,
                            "operation": "add",
                            "confidence": round(conf, 3),
                        })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results


async def _call_mojo_field_map(
    numeric_fields: dict[str, list[float]],
) -> dict[str, Any] | None:
    """Call the Mojo field_map engine. Returns result dict or None."""
    if not numeric_fields:
        return None
    payload = {"engine_type": "field_map", "data": numeric_fields}
    result, engine_status = await _invoke_optional_mojo_engine(
        "field_map",
        payload,
    )
    if result is None:
        if engine_status["reason"] != "engine_circuit_open":
            logger.debug("field_map_mojo_error", engine_status=engine_status)
        return None
    return result


def _optional_mojo_payload_bytes(payload: dict[str, Any]) -> int:
    try:
        return len(
            json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise MojoEngineError(
            "Invalid Mojo payload: could not serialize engine payload to JSON.",
            code="invalid_payload",
            recoverable=False,
            engine_type=str(payload.get("engine_type") or "unknown"),
            stage="preflight",
        ) from exc


def _optional_mojo_preflight_status(
    engine_type: str,
    payload: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any] | None:
    validate_mojo_payload(payload)
    if reason is not None:
        return build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason=reason,
            message=f"Optional Mojo engine skipped during preflight: {reason}.",
            details={},
        )

    payload_bytes = _optional_mojo_payload_bytes(payload)
    if payload_bytes > _OPTIONAL_MOJO_MAX_PAYLOAD_BYTES:
        return build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason="preflight_payload_too_large",
            message=(
                "Optional Mojo payload exceeds configured limit and will use the "
                "deterministic fallback path instead."
            ),
            details={
                "payload_bytes": payload_bytes,
                "payload_limit_bytes": _OPTIONAL_MOJO_MAX_PAYLOAD_BYTES,
            },
        )
    return None


async def _invoke_optional_mojo_engine(
    engine_type: str,
    payload: dict[str, Any],
    *,
    preflight_reason: str | None = None,
    timeout_s: float = _OPTIONAL_MOJO_TIMEOUT_S,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    preflight_status = _optional_mojo_preflight_status(
        engine_type,
        payload,
        reason=preflight_reason,
    )
    if preflight_status is not None:
        logger.debug(
            f"{engine_type}_mojo_preflight_skip",
            engine_status=preflight_status,
        )
        return None, preflight_status

    skip_reason = _get_optional_mojo_engine_skip_reason(engine_type)
    if skip_reason is not None:
        engine_status = build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason="engine_circuit_open",
            message=skip_reason,
            details={"cooldown_s": _MOJO_OPTIONAL_ENGINE_COOLDOWN_S},
        )
        logger.debug(
            f"{engine_type}_mojo_circuit_open",
            engine_status=engine_status,
        )
        return None, engine_status

    try:
        from apps.api_server.compute.mojo_adapter import invoke_engine

        result = await invoke_engine(payload, timeout=timeout_s)
        _clear_optional_mojo_engine_failure(engine_type)
        return result, build_mojo_engine_status(
            engine_type=engine_type,
            status="enabled",
            reason=None,
            details={"timeout_s": timeout_s},
        )
    except Exception as exc:
        error = coerce_mojo_engine_error(
            exc,
            engine_type=engine_type,
            stage="optional_exec",
        )
        _record_optional_mojo_engine_failure(engine_type, error)
        return None, error.as_error_details()


def _mojo_profiling_enabled_status(
    engine_type: str,
    *,
    engine_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "enabled",
        "engine_type": engine_type,
        "reason": None,
        "message": None,
        "engine_status": engine_status
        or build_mojo_engine_status(
            engine_type=engine_type,
            status="enabled",
            reason=None,
        ),
    }


def _mojo_profiling_disabled_status(
    engine_type: str,
    reason: str,
    *,
    message: str | None = None,
    engine_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "disabled",
        "engine_type": engine_type,
        "reason": reason,
        "message": message,
        "engine_status": engine_status
        or build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason=reason,
            message=message,
        ),
    }


def _mojo_profiling_status_from_result(
    result: dict[str, Any] | None,
    *,
    engine_type: str = "column_profile",
) -> dict[str, Any]:
    if not result:
        return _mojo_profiling_disabled_status(engine_type, "no_result")
    status = result.get("_profiling_status")
    if isinstance(status, dict):
        return {
            "status": str(status.get("status") or "disabled"),
            "engine_type": str(status.get("engine_type") or engine_type),
            "reason": status.get("reason"),
            "message": status.get("message"),
        }
    return _mojo_profiling_enabled_status(engine_type)


def _finite_numeric_samples(values: list[Any] | None, *, limit: int) -> list[float]:
    """Return up to `limit` finite numeric samples in stable input order."""
    samples: list[float] = []
    for value in values or []:
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        samples.append(numeric)
        if len(samples) >= limit:
            break
    return samples


def _string_samples(values: list[Any] | None, *, limit: int) -> list[str]:
    """Return up to `limit` string samples in stable input order."""
    samples: list[str] = []
    for value in values or []:
        samples.append(str(value))
        if len(samples) >= limit:
            break
    return samples


def _build_mojo_column_profile_columns(
    profile: dict[str, dict[str, Any]],
    *,
    value_limit: int,
    string_limit: int,
    include_fill_rate: bool = False,
) -> dict[str, dict[str, Any]]:
    """
    Build a deterministic Mojo column-profile payload from profiled source metadata.

    `values` is restricted to finite numeric samples only. Mixed `sample_values`
    can contain identifier-like strings that begin with digits, which the Mojo
    numeric parser can interpret as numbers and turn into invalid JSON stats.
    """
    payload: dict[str, dict[str, Any]] = {}
    for field, info in profile.items():
        fill_rate = float(info.get("fill_rate", 1.0) or 0.0)
        if fill_rate <= 0.0:
            continue

        entry: dict[str, Any] = {
            "values": _finite_numeric_samples(info.get("numeric"), limit=value_limit),
            "strings": _string_samples(info.get("strings"), limit=string_limit),
            "sample_size": int(info.get("total_count", 0) or 0),
        }
        if include_fill_rate:
            entry["fill_rate"] = fill_rate
        payload[field] = entry
    return payload


def _mojo_column_profile_sample_limits(column_count: int) -> tuple[int, int]:
    """
    Bound Mojo profiling payload size deterministically for wide schemas.

    Wide sources do not need the same per-column sample budget as narrow ones.
    Keeping the budget proportional to schema width reduces registration latency
    without changing the set of profiled columns.
    """
    if column_count >= 192:
        return 12, 12
    if column_count >= 96:
        return 16, 12
    if column_count >= 48:
        return 24, 16
    return 50, 50


def _mojo_column_profile_preflight_skip_reason(
    columns: dict[str, dict[str, Any]],
) -> str | None:
    """
    Return a deterministic skip reason when Mojo profiling is not worthwhile.

    Very small sources provide too little signal for Mojo profiling while still
    paying the full engine startup / IPC boundary cost. Skipping these payloads
    keeps first-touch behavior stable and relies on the existing Python path for
    equivalent profiling semantics.
    """
    sample_sizes = [max(int(column.get("sample_size", 0) or 0), 0) for column in columns.values()]
    if not sample_sizes:
        return "preflight_no_samples"

    max_sample_size = max(sample_sizes)
    total_sample_size = sum(sample_sizes)
    minimum_total = max(8, len(sample_sizes) * 2)
    if max_sample_size < 4 or total_sample_size < minimum_total:
        return "preflight_insufficient_samples"
    return None


async def _call_mojo_column_profile(
    columns: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Call Mojo column_profiler engine.
    columns: {field_name: {values: [finite numerics], strings: [...], sample_size: N}}
    Returns: {profiles: {field: {semantic_type, polarity, unique_ratio, ...}}}
    """
    if not columns:
        return {
            "profiles": {},
            "_profiling_status": _mojo_profiling_disabled_status("column_profile", "no_columns"),
        }
    if not settings.mojo_profiling_enabled:
        return {
            "profiles": {},
            "_profiling_status": _mojo_profiling_disabled_status(
                "column_profile",
                "configured_disabled",
            ),
        }
    preflight_skip_reason = _mojo_column_profile_preflight_skip_reason(columns)
    if preflight_skip_reason is not None:
        return {
            "profiles": {},
            "_profiling_status": _mojo_profiling_disabled_status(
                "column_profile",
                preflight_skip_reason,
            ),
        }
    payload = {"engine_type": "column_profile", "columns": columns}
    result, engine_status = await _invoke_optional_mojo_engine(
        "column_profile",
        payload,
        timeout_s=_OPTIONAL_MOJO_TIMEOUT_S,
    )
    if result is not None:
        return {
            **result,
            "_profiling_status": _mojo_profiling_enabled_status(
                "column_profile",
                engine_status=engine_status,
            ),
        }

    if engine_status["reason"] == "engine_circuit_open":
        if settings.mojo_profiling_required:
            raise MojoInstrumentationError(
                "column_profile",
                "Mojo column profiling is temporarily disabled after a recent engine failure "
                "while profiling policy is required.",
            )
        return {
            "profiles": {},
            "_profiling_status": _mojo_profiling_disabled_status(
                "column_profile",
                "engine_error",
                message=str(engine_status.get("message") or ""),
                engine_status=engine_status,
            ),
        }

    if engine_status["reason"] == "preflight_payload_too_large":
        return {
            "profiles": {},
            "_profiling_status": _mojo_profiling_disabled_status(
                "column_profile",
                "preflight_payload_too_large",
                message=str(engine_status.get("message") or ""),
                engine_status=engine_status,
            ),
        }

    _log_mojo_warning(
        "column_profile_mojo_error",
        error=str(engine_status.get("message") or ""),
        profiling_policy=settings.normalized_mojo_profiling_policy,
        reason=mojo_failure_reason(str(engine_status.get("message") or engine_status["reason"])),
    )
    if settings.mojo_profiling_required:
        raise MojoInstrumentationError(
            "column_profile",
            "Mojo column profiling failed while profiling policy is required.",
        )
    return {
        "profiles": {},
        "_profiling_status": _mojo_profiling_disabled_status(
            "column_profile",
            "engine_error",
            message=str(engine_status.get("message") or ""),
            engine_status=engine_status,
        ),
    }


async def _call_mojo_column_match(
    source_a: str,
    source_b: str,
    columns_a: list[dict[str, Any]],
    columns_b: list[dict[str, Any]],
    min_confidence: float = 0.5,
) -> dict[str, Any] | None:
    """
    Call Mojo column_matcher engine for N×M cross-source scoring.
    Returns: {matches: [{field_a, field_b, score, match_type, ...}]}
    """
    if not columns_a or not columns_b:
        return None
    payload = {
        "engine_type": "column_match",
        "source_a": source_a,
        "source_b": source_b,
        "columns_a": columns_a,
        "columns_b": columns_b,
        "min_confidence": min_confidence,
    }
    result, engine_status = await _invoke_optional_mojo_engine(
        "column_match",
        payload,
        timeout_s=_OPTIONAL_MOJO_TIMEOUT_S,
    )
    if result is None:
        if engine_status["reason"] != "engine_circuit_open":
            logger.debug("column_match_mojo_error", engine_status=engine_status)
        return None
    return result


async def _call_mojo_join_detect(
    source_a: str,
    source_b: str,
    columns: dict[str, dict[str, Any]],
    min_confidence: float = 0.4,
) -> dict[str, Any] | None:
    """
    Call Mojo join_detector engine.
    columns: {"source.FIELD": {values: [...], unique_ratio: 0.9, sample_size: N}}
    Returns: {join_keys: [{field_a, source_a, field_b, source_b, overlap, ...}]}
    """
    if not columns:
        return None
    payload = {
        "engine_type": "join_detect",
        "source_a": source_a,
        "source_b": source_b,
        "min_confidence": min_confidence,
        "columns": columns,
    }
    result, engine_status = await _invoke_optional_mojo_engine(
        "join_detect",
        payload,
        timeout_s=_OPTIONAL_MOJO_TIMEOUT_S,
    )
    if result is None:
        if engine_status["reason"] != "engine_circuit_open":
            logger.debug("join_detect_mojo_error", engine_status=engine_status)
        return None
    return result


async def _call_mojo_relation_detect(
    source: str,
    columns: dict[str, list[float]],
    min_confidence: float = 0.70,
) -> dict[str, Any] | None:
    """
    Call Mojo relation_detector engine.
    columns: {field_name: [float values ...]}
    Returns: {relationships: [{formula, field_result, field_a, field_b, operation, confidence}]}
    """
    if len(columns) < 3:
        return None
    payload = {
        "engine_type": "relation_detect",
        "source": source,
        "min_confidence": min_confidence,
        "columns": columns,
    }
    result, engine_status = await _invoke_optional_mojo_engine(
        "relation_detect",
        payload,
        timeout_s=_OPTIONAL_MOJO_TIMEOUT_S,
    )
    if result is None:
        if engine_status["reason"] != "engine_circuit_open":
            logger.debug("relation_detect_mojo_error", engine_status=engine_status)
        return None
    return result


def _parse_csv(text: str) -> list[dict[str, Any]]:
    """Parse CSV text into list of dicts, auto-converting numerics."""
    return parse_delimited_records(text, delimiter=",", sniff=True)


def _parse_json_records(text: str) -> list[dict[str, Any]]:
    """Parse a JSON array string into list of dicts."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        # Wrapped object — look for a records array
        for key in ("data", "records", "rows", "results", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON source must be an array of objects")
    return [r for r in data if isinstance(r, dict)]


def _read_url_text(url: str) -> tuple[str, str]:
    """Fetch a text URL once and return ``(body, content_type)``."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL sources must use http or https.")
    req = urllib.request.Request(url, headers={"User-Agent": "algenta/1.0"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8", errors="replace")
        ct = resp.headers.get("Content-Type", "")
    return raw, ct


def _fetch_url(url: str) -> list[dict[str, Any]]:
    """Fetch URL and auto-detect CSV vs JSON."""
    raw, ct = _read_url_text(url)
    # Detect by content-type or URL extension
    if "json" in ct or url.rstrip("/").endswith(".json"):
        return _parse_json_records(raw)
    return _parse_csv(raw)  # default to CSV


def _load_registered_source_table(source_id: str, org_id: str | None) -> Any:
    """Load a registered source from the org registry as a columnar table."""
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "missing_org_context",
                    "message": (
                        f"Source '{source_id}' uses source_id and requires org "
                        "context."
                    ),
                }
            },
        )

    from apps.api_server.services import source_registry as _sreg

    parquet_path = _sreg.get_source_parquet_path(org_id, source_id)
    if parquet_path is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "unknown_source_id",
                    "message": (
                        f"Registered source '{source_id}' was not found for this org."
                    ),
                }
            },
        )

    import pyarrow.parquet as pq

    initialize_pyarrow_parquet_runtime()
    return pq.read_table(parquet_path)


async def _load_source(
    src: DataSource,
    *,
    org_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Universal source loader. Normalizes any source type to list[dict].

    Priority order:
    dataset_id/source_id > records > csv > json_str > excel_b64 >
    parquet_b64 > url > connection > table
    """
    try:
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            table = _load_registered_source_table(registered_id, org_id)
            return table.to_pylist()

        if src.records is not None:
            return src.records

        if src.csv:
            return _parse_csv(src.csv)

        if src.json_str:
            return _parse_json_records(src.json_str)

        if src.excel_b64:
            from apps.api_server.connectors import FileConnector
            fc = FileConnector({"file_type": "excel", "content": src.excel_b64})
            return await fc.fetch_data()

        if src.parquet_b64:
            from apps.api_server.connectors import FileConnector
            fc = FileConnector({"file_type": "parquet", "content": src.parquet_b64})
            return await fc.fetch_data()

        if src.url:
            return _fetch_url(src.url)

        if src.connection:
            from apps.api_server.connectors import ConnectorRegistry
            conn_type = src.connection.get("type", "")
            if not conn_type:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "invalid_connection",
                            "message": (
                                f"Source '{src.name}': connection dict must have "
                                "a 'type' key"
                            ),
                        }
                    },
                )
            connector = ConnectorRegistry.create(conn_type, src.connection)
            return await connector.fetch_data()

        if src.table:
            table_message = (
                f"Source '{src.name}': use a SQL connection with an explicit "
                "query instead of table."
            )
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "use_connection", "message": table_message}},
            )

        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "empty_source",
                               "message": f"Source '{src.name}' has no data. "
                                          "Provide one of: records, csv, json_str, excel_b64, "
                                          "parquet_b64, url, or connection."}},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "load_error",
                               "message": f"Source '{src.name}' failed to load: {exc}"}},
        ) from exc


async def _load_source_table(
    src: DataSource,
    *,
    org_id: str | None = None,
) -> Any:
    """
    Universal source loader with a columnar fast path.

    Returns a pyarrow.Table whenever a native table path exists.
    Returns ``None`` when the source should use the tolerant row path instead.
    """
    try:
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            return _load_registered_source_table(registered_id, org_id)

        artifact_cache_key = source_content_artifact_key(src)
        if artifact_cache_key is not None:
            cached_table = load_cached_arrow_table(artifact_cache_key)
            if cached_table is not None:
                return cached_table

        table = None

        if src.records is not None:
            table = records_to_arrow_table(src.records)

        elif src.csv:
            try:
                table = delimited_text_to_arrow_table(src.csv, delimiter=",", sniff=True)
            except Exception:
                return None

        elif src.json_str:
            table = records_to_arrow_table(_parse_json_records(src.json_str))

        elif src.excel_b64:
            from apps.api_server.connectors import FileConnector

            fc = FileConnector({"file_type": "excel", "content": src.excel_b64})
            table = await fc.fetch_table()
            if table is None:
                return None

        elif src.parquet_b64:
            from apps.api_server.connectors import FileConnector

            fc = FileConnector({"file_type": "parquet", "content": src.parquet_b64})
            table = await fc.fetch_table()
            if table is None:
                return None

        elif src.url:
            raw, ct = _read_url_text(src.url)
            if "json" in ct or src.url.rstrip("/").endswith(".json"):
                table = records_to_arrow_table(_parse_json_records(raw))
            else:
                try:
                    table = delimited_text_to_arrow_table(raw, delimiter=",", sniff=True)
                except Exception:
                    return None

        elif src.connection:
            from apps.api_server.connectors import ConnectorRegistry

            conn_type = src.connection.get("type", "")
            if not conn_type:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "invalid_connection",
                            "message": (
                                f"Source '{src.name}': connection dict must have "
                                "a 'type' key"
                            ),
                        }
                    },
                )
            connector = ConnectorRegistry.create(conn_type, src.connection)
            table = await connector.fetch_table()
            if table is None:
                return None

        elif src.table:
            table_message = (
                f"Source '{src.name}': use a SQL connection with an explicit "
                "query instead of table."
            )
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "use_connection", "message": table_message}},
            )

        if table is None:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "empty_source",
                                   "message": f"Source '{src.name}' has no data. "
                                              "Provide one of: records, csv, json_str, excel_b64, "
                                              "parquet_b64, url, or connection."}},
            )

        if artifact_cache_key is not None:
            store_cached_arrow_table(artifact_cache_key, table)

        return table
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "load_error",
                               "message": f"Source '{src.name}' failed to load: {exc}"}},
        ) from exc


# ── Query Without SQL (removed — replaced by routers/query.py structured engine) ──

class _LegacyQueryRequest(BaseModel):  # kept for import safety only, not routed
    """
    Natural language query over one or more data sources.

    Examples:
      "total revenue by customer"
      "average cost per product"
      "count orders where amount > 1000"
      "top 10 customers by revenue"
    """
    query: str = Field(..., description="Natural language query")
    sources: list[DataSource] = Field(..., min_length=1, description="Data sources to query")
    limit: int = Field(100, ge=1, le=10000, description="Max rows to return")


class _LegacyQueryResponse(BaseModel):
    query: str
    result: list[dict[str, Any]]
    row_count: int
    query_plan: str
    metric_field: str | None
    group_field: str | None
    aggregation: str
    confidence: float
    latency_ms: float


# Intent keywords — maps query terms to semantic intent
_AGG_KEYWORDS: dict[str, str] = {
    "total": "sum", "sum": "sum", "aggregate": "sum",
    "average": "mean", "avg": "mean", "mean": "mean",
    "count": "count", "number of": "count", "how many": "count",
    "max": "max", "maximum": "max", "highest": "max", "top": "max",
    "min": "min", "minimum": "min", "lowest": "min",
}

_METRIC_KEYWORDS: dict[str, list[str]] = {
    "revenue":   ["revenue", "sales", "income", "receipts", "turnover",
                  "ext_price", "extprice", "extended_price", "total_price"],
    "cost":      ["cost", "expense", "expenditure", "spending",
                  "ext_cost", "extcost", "extended_cost", "total_cost"],
    "quantity":  ["quantity", "qty", "units", "volume"],
    "price":     ["price", "rate", "unit_price", "unitprice", "list_price"],
    "amount":    ["amount", "total", "value"],
    "profit":    ["profit", "margin", "net"],
    "count":     ["count", "number"],
}

_GROUP_PREPOSITIONS = ["by ", "per ", "for each ", "grouped by ", "group by "]


def _parse_query_intent(query: str) -> dict[str, Any]:
    """
    Parse a natural language query into intent dict:
      {aggregation, metric_hint, group_hint, limit, confidence}
    """
    q = query.lower().strip()
    intent: dict[str, Any] = {
        "aggregation": "sum",
        "metric_hint": None,
        "group_hint":  None,
        "limit":       None,
        "confidence":  0.5,
    }

    # Aggregation
    for keyword, agg in _AGG_KEYWORDS.items():
        if keyword in q:
            intent["aggregation"] = agg
            intent["confidence"] = min(intent["confidence"] + 0.2, 1.0)
            break

    # "top N" → limit
    import re
    top_match = re.search(r'\btop\s+(\d+)\b', q)
    if top_match:
        intent["limit"] = int(top_match.group(1))
        intent["aggregation"] = "sum"  # "top N by X" → sum then sort

    # Metric hint
    for canonical, terms in _METRIC_KEYWORDS.items():
        if any(t in q for t in terms):
            intent["metric_hint"] = canonical
            intent["confidence"] = min(intent["confidence"] + 0.2, 1.0)
            break

    # Group by hint — extract word after "by"/"per"
    for prep in _GROUP_PREPOSITIONS:
        if prep in q:
            after = q.split(prep, 1)[1].strip()
            # Take first word
            group_word = re.split(r'[\s,]', after)[0].rstrip("s")  # simple depluralize
            intent["group_hint"] = group_word
            intent["confidence"] = min(intent["confidence"] + 0.15, 1.0)
            break

    return intent


def _find_best_field(
    records: list[dict[str, Any]],
    hint: str | None,
    numeric_only: bool = True,
) -> str | None:
    """Find the best matching field name in records given a hint."""
    if not records:
        return None

    fields = list(records[0].keys())
    if not fields:
        return None

    # Filter to numeric fields if required
    if numeric_only:
        def _is_num(f: str) -> bool:
            vals = [records[i].get(f) for i in range(min(10, len(records)))]
            return any(isinstance(v, int | float) for v in vals)
        candidate_fields = [f for f in fields if _is_num(f)]
    else:
        candidate_fields = fields

    if not candidate_fields:
        return None

    if hint is None:
        return candidate_fields[0]

    # Score each field against hint
    best_field = None
    best_score = -1.0
    for f in candidate_fields:
        score, _ = _semantic_similarity(f, hint)
        # Also try hint synonyms
        for canonical, terms in _METRIC_KEYWORDS.items():
            if hint in terms or hint == canonical:
                for term in terms:
                    s2, _ = _semantic_similarity(f, term)
                    score = max(score, s2)
        if score > best_score:
            best_score = score
            best_field = f

    return best_field


def _execute_query(
    records: list[dict[str, Any]],
    metric_field: str | None,
    group_field: str | None,
    aggregation: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Execute aggregation query on records dict."""
    if not records:
        return []

    # No grouping — single aggregate
    if not group_field:
        if not metric_field:
            return [{"count": len(records)}]
        vals = [
            r.get(metric_field)
            for r in records
            if isinstance(r.get(metric_field), int | float)
        ]
        if not vals:
            return [{"result": None}]
        result_val = _agg_vals(vals, aggregation)
        return [{metric_field: round(result_val, 4), "count": len(vals)}]

    # Group by + aggregate
    groups: dict[Any, list[float]] = {}
    for rec in records:
        gk = rec.get(group_field, "__unknown__")
        val = rec.get(metric_field) if metric_field else 1
        if not isinstance(val, int | float):
            val = 1.0
        if gk not in groups:
            groups[gk] = []
        groups[gk].append(float(val))

    result_rows = []
    for gk, vals in groups.items():
        agg_val = _agg_vals(vals, aggregation)
        row: dict[str, Any] = {group_field: gk}
        if metric_field:
            row[metric_field] = round(agg_val, 4)
        row["count"] = len(vals)
        result_rows.append(row)

    # Sort descending by metric
    if metric_field:
        result_rows.sort(key=lambda r: r.get(metric_field, 0), reverse=True)

    if limit:
        result_rows = result_rows[:limit]

    return result_rows


def _agg_vals(vals: list[float], aggregation: str) -> float:
    if not vals:
        return 0.0
    if aggregation == "sum":
        return sum(vals)
    if aggregation == "mean":
        return statistics.mean(vals)
    if aggregation == "max":
        return max(vals)
    if aggregation == "min":
        return min(vals)
    if aggregation == "count":
        return float(len(vals))
    return sum(vals)


async def _legacy_query_data_unused(
    payload: _LegacyQueryRequest,
    auth: AuthContext = Depends(get_current_org),
) -> _LegacyQueryResponse:
    t0 = time.monotonic()
    org_id = str(auth["org_id"])

    # Parse sources
    all_records: list[dict[str, Any]] = []
    for src in payload.sources:
        all_records.extend(await _load_source(src, org_id=org_id))

    if not all_records:
        raise HTTPException(status_code=400,
                            detail={"error": {"code": "no_data", "message": "No records found"}})

    # Parse query intent
    intent = _parse_query_intent(payload.query)
    aggregation = intent["aggregation"]
    metric_hint = intent["metric_hint"]
    group_hint = intent["group_hint"]
    limit = intent.get("limit") or payload.limit

    # Resolve field names
    metric_field = _find_best_field(all_records, metric_hint, numeric_only=True)
    group_field = (
        _find_best_field(all_records, group_hint, numeric_only=False)
        if group_hint
        else None
    )

    # Don't group by a numeric field
    if group_field and metric_field and group_field == metric_field:
        group_field = None

    # Execute
    result = _execute_query(all_records, metric_field, group_field, aggregation, limit)

    # Build query plan explanation
    plan_parts = []
    if metric_field:
        plan_parts.append(f"{aggregation}({metric_field})")
    else:
        plan_parts.append("count(records)")
    if group_field:
        plan_parts.append(f"group by {group_field}")
    if limit and group_field:
        plan_parts.append(f"limit {limit}")
    query_plan = " → ".join(plan_parts) if plan_parts else "scan all records"

    confidence = intent["confidence"]
    if metric_field:
        confidence = min(confidence + 0.1, 1.0)
    if group_field:
        confidence = min(confidence + 0.1, 1.0)

    return _LegacyQueryResponse(
        query=payload.query,
        result=result[:payload.limit],
        row_count=len(result),
        query_plan=query_plan,
        metric_field=metric_field,
        group_field=group_field,
        aggregation=aggregation,
        confidence=round(confidence, 3),
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )
