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
import os
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from apps.api_server.compute.mojo_errors import MojoEngineError, mojo_failure_reason  # noqa: F401
from apps.api_server.config import SettingsProxy
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.schemas.data_map import (
    DataSource,
    FieldMapping,
    MapRequest,
    MapResponse,
    _LegacyQueryRequest,
    _LegacyQueryResponse,
)
from apps.api_server.services import data_map_sources
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.columnar_loader import delimited_text_to_arrow_table
from apps.api_server.services.data_map_deep_analysis import (
    deep_store_key,
    run_or_schedule_deep_analysis,
)
from apps.api_server.services.data_map_errors import (
    MojoInstrumentationError,
    http_error,
)
from apps.api_server.services.data_map_legacy_query import (
    _agg_vals,  # noqa: F401
    _execute_query,  # noqa: F401
    _find_best_field,  # noqa: F401
    _parse_query_intent,  # noqa: F401
    execute_legacy_query,
)
from apps.api_server.services.data_map_matching import (
    _build_match_reasons,
    _build_matcher_input,
    _detect_derived_relationships,
    _dice_coefficient,  # noqa: F401
    _hungarian_greedy,
    _match_tier,
    _ngrams,  # noqa: F401
    _normalize,
    _pearson_correlation,  # noqa: F401
    _semantic_similarity,
    _value_distribution_similarity,
)
from apps.api_server.services.data_map_mojo_profiles import (
    _build_mojo_column_profile_columns,
    _finite_numeric_samples,  # noqa: F401
    _mojo_column_profile_preflight_skip_reason,
    _mojo_column_profile_sample_limits,  # noqa: F401
    _mojo_profiling_disabled_status,
    _mojo_profiling_enabled_status,
    _mojo_profiling_status_from_result,  # noqa: F401
    _string_samples,  # noqa: F401
)
from apps.api_server.services.data_map_profiles import (
    build_source_profiles,
    build_unified_schema,
)
from apps.api_server.services.optional_mojo_policy import (
    GLOBAL_OPTIONAL_MOJO_ENGINE_KEY as _DEFAULT_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
)
from apps.api_server.services.optional_mojo_policy import (
    build_optional_mojo_preflight_status as _build_optional_mojo_preflight_status_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    clear_optional_mojo_engine_failure as _clear_optional_mojo_engine_failure_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    get_optional_mojo_engine_reason as _get_optional_mojo_engine_reason_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    get_optional_mojo_engine_skip_reason as _get_optional_mojo_engine_skip_reason_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    invoke_optional_mojo_engine as _invoke_optional_mojo_engine_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    optional_mojo_payload_bytes as _optional_mojo_payload_bytes_impl,
)
from apps.api_server.services.optional_mojo_policy import (
    record_optional_mojo_engine_failure as _record_optional_mojo_engine_failure_impl,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Data Mapping"])
settings = SettingsProxy()
_MOJO_WARNING_COOLDOWN_S = 60.0
_MOJO_WARNING_STATE: dict[tuple[str, str], float] = {}
_MOJO_OPTIONAL_ENGINE_COOLDOWN_S = 60.0
_MOJO_OPTIONAL_ENGINE_FAILURE_STATE: dict[str, tuple[float, str]] = {}
_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY = _DEFAULT_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY
_DEFAULT_OPTIONAL_MOJO_TIMEOUT_S = 2.0
_DEFAULT_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES = 1_048_576
_OPTIONAL_MOJO_TIMEOUT_S = _DEFAULT_OPTIONAL_MOJO_TIMEOUT_S
_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES = _DEFAULT_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES

# ── Two-speed pipeline store ──────────────────────────────────────────────────
# Keyed by map_id. Each entry holds the completed deep-analysis payload.
# Simple in-process dict — survives for the process lifetime (fine for Phase 1).
_deep_store: dict[str, dict[str, Any]] = {}
_DEEP_BUDGET_S = 0.20  # seconds — if Phase 2 finishes within this, embed in response


def _optional_mojo_timeout_seconds() -> float:
    if _OPTIONAL_MOJO_TIMEOUT_S != _DEFAULT_OPTIONAL_MOJO_TIMEOUT_S:
        return float(_OPTIONAL_MOJO_TIMEOUT_S)
    raw_value = os.environ.get("ALGENTA_OPTIONAL_MOJO_TIMEOUT_S", "2.0")
    try:
        return float(raw_value)
    except ValueError:
        return float(_OPTIONAL_MOJO_TIMEOUT_S)


def _optional_mojo_max_payload_bytes() -> int:
    if _OPTIONAL_MOJO_MAX_PAYLOAD_BYTES != _DEFAULT_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES:
        return int(_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES)
    raw_value = os.environ.get("ALGENTA_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES", "1048576")
    try:
        return int(raw_value)
    except ValueError:
        return int(_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES)


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
    return _get_optional_mojo_engine_reason_impl(
        failure_state=_MOJO_OPTIONAL_ENGINE_FAILURE_STATE,
        cache_key=cache_key,
        cooldown_s=_MOJO_OPTIONAL_ENGINE_COOLDOWN_S,
        monotonic_fn=time.monotonic,
    )


def _get_optional_mojo_engine_skip_reason(engine_type: str) -> str | None:
    reason, _ = _get_optional_mojo_engine_skip_reason_impl(
        failure_state=_MOJO_OPTIONAL_ENGINE_FAILURE_STATE,
        engine_type=engine_type,
        cooldown_s=_MOJO_OPTIONAL_ENGINE_COOLDOWN_S,
        monotonic_fn=time.monotonic,
        global_key=_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
    )
    return reason


def _record_optional_mojo_engine_failure(engine_type: str, reason: BaseException | str) -> None:
    _record_optional_mojo_engine_failure_impl(
        failure_state=_MOJO_OPTIONAL_ENGINE_FAILURE_STATE,
        engine_type=engine_type,
        reason=reason,
        monotonic_fn=time.monotonic,
        global_key=_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
    )


def _clear_optional_mojo_engine_failure(engine_type: str) -> None:
    _clear_optional_mojo_engine_failure_impl(
        failure_state=_MOJO_OPTIONAL_ENGINE_FAILURE_STATE,
        engine_type=engine_type,
        global_key=_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
    )


# ── Data source models ────────────────────────────────────────────────────────

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
    # Cross-tenant guard: look up under the org-scoped key so one org can never read another's
    # analysis by map_id. 404 (not 403) so a non-owner can't even probe existence.
    key = deep_store_key(str(auth["org_id"]), map_id)
    if key not in _deep_store:
        raise HTTPException(status_code=404, detail="map_id not found or still processing")
    return _deep_store[key]


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
    source_profiles = build_source_profiles(parsed)

    source_names = list(source_profiles.keys())

    # ── Phase 1a: Mojo column profiler — run all sources concurrently ─────────
    def _make_profiler_input(profile: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return _build_mojo_column_profile_columns(
            profile,
            value_limit=200,
            string_limit=100,
        )

    try:
        profiler_results = await asyncio.gather(
            *[
                _call_mojo_column_profile(_make_profiler_input(profile))
                for profile in source_profiles.values()
            ]
        )
    except MojoInstrumentationError as exc:
        raise http_error(
            503,
            code="mojo_instrumentation_unavailable",
            message=(
                "Mojo column profiling is unavailable while strict runtime fallbacks are disabled."
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

    match_results = await asyncio.gather(
        *[
            _call_mojo_column_match(
                src_a,
                src_b,
                _build_matcher_input(source_profiles[src_a], source_mojo_profiles.get(src_a, {})),
                _build_matcher_input(source_profiles[src_b], source_mojo_profiles.get(src_b, {})),
                min_confidence=payload.min_confidence,
            )
            for src_a, src_b in match_pairs
        ]
    )

    mappings: list[FieldMapping] = []
    for (src_a, src_b), match_result in zip(match_pairs, match_results, strict=False):
        if match_result and "matches" in match_result:
            best = _hungarian_greedy(match_result["matches"])
            for m in best:
                tier = _match_tier(m["score"])
                if tier == "rejected":
                    continue
                mappings.append(
                    FieldMapping(
                        source_field=m["field_a"],
                        source=src_a,
                        target_field=m["field_b"],
                        target=src_b,
                        confidence=round(m["score"], 3),
                        reason=_build_match_reasons(m),
                        match_type=m.get("match_type", "semantic"),
                    )
                )
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
                        py_pairs.append(
                            (
                                best_score,
                                FieldMapping(
                                    source_field=field_a,
                                    source=src_a,
                                    target_field=field_b,
                                    target=src_b,
                                    confidence=round(best_score, 3),
                                    reason=reasons[:3],
                                    match_type=match_type,
                                ),
                            )
                        )
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
    unified_schema_result = await build_unified_schema(
        source_profiles,
        source_mojo_profiles,
        semantic_similarity_fn=_semantic_similarity,
        call_mojo_field_map_fn=_call_mojo_field_map,
    )
    unified = unified_schema_result.unified_schema
    all_fields_seen = unified_schema_result.all_fields_seen

    # ── Phase 2: Join detection + Relation detection (background task) ───────
    # Kicked off concurrently. If it completes within _DEEP_BUDGET_S it is
    # embedded in the response; otherwise the client polls GET /v1/map/{map_id}.
    deep, deep_pending = await run_or_schedule_deep_analysis(
        org_id=org_id,
        map_id=map_id,
        parsed_sources=parsed,
        source_profiles=source_profiles,
        match_pairs=match_pairs,
        mappings=mappings,
        unified_schema=unified,
        deep_store=_deep_store,
        deep_budget_s=_DEEP_BUDGET_S,
        logger=logger,
        call_mojo_join_detect_fn=_call_mojo_join_detect,
        call_mojo_relation_detect_fn=_call_mojo_relation_detect,
        call_mojo_field_map_fn=_call_mojo_field_map,
        detect_derived_relationships_fn=_detect_derived_relationships,
        normalize_fn=_normalize,
    )

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
    return _optional_mojo_payload_bytes_impl(payload)


def _optional_mojo_preflight_status(
    engine_type: str,
    payload: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any] | None:
    return _build_optional_mojo_preflight_status_impl(
        engine_type=engine_type,
        payload=payload,
        max_payload_bytes=_optional_mojo_max_payload_bytes(),
        reason=reason,
    )


async def _invoke_optional_mojo_engine(
    engine_type: str,
    payload: dict[str, Any],
    *,
    preflight_reason: str | None = None,
    timeout_s: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    from apps.api_server.compute.mojo_adapter import invoke_engine
    effective_timeout_s = timeout_s if timeout_s is not None else _optional_mojo_timeout_seconds()

    engine_result, engine_status = await _invoke_optional_mojo_engine_impl(
        engine_type=engine_type,
        payload=payload,
        preflight_reason=preflight_reason,
        timeout_s=effective_timeout_s,
        max_payload_bytes=_optional_mojo_max_payload_bytes(),
        cooldown_s=_MOJO_OPTIONAL_ENGINE_COOLDOWN_S,
        failure_state=_MOJO_OPTIONAL_ENGINE_FAILURE_STATE,
        monotonic_fn=time.monotonic,
        invoke_engine=invoke_engine,
        global_key=_GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
    )
    if engine_result is None and engine_status["status"] == "disabled":
        event = (
            f"{engine_type}_mojo_circuit_open"
            if engine_status["reason"] == "engine_circuit_open"
            else f"{engine_type}_mojo_preflight_skip"
        )
        logger.debug(
            event,
            engine_status=engine_status,
        )
    return engine_result, engine_status


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
        timeout_s=_optional_mojo_timeout_seconds(),
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
        timeout_s=_optional_mojo_timeout_seconds(),
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
        timeout_s=_optional_mojo_timeout_seconds(),
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
        timeout_s=_optional_mojo_timeout_seconds(),
    )
    if result is None:
        if engine_status["reason"] != "engine_circuit_open":
            logger.debug("relation_detect_mojo_error", engine_status=engine_status)
        return None
    return result


def _parse_csv(text: str) -> list[dict[str, Any]]:
    """Parse CSV text into list of dicts, auto-converting numerics."""
    return data_map_sources.parse_csv_records(text)


def _parse_json_records(text: str) -> list[dict[str, Any]]:
    """Parse a JSON array string into list of dicts."""
    return data_map_sources.parse_json_records(text)


def _read_url_text(url: str) -> tuple[str, str]:
    """Fetch a text URL once and return ``(body, content_type)``."""
    return data_map_sources.read_url_text(url)


def _fetch_url(url: str) -> list[dict[str, Any]]:
    """Fetch URL and auto-detect CSV vs JSON."""
    return data_map_sources.fetch_url_records(
        url,
        parse_csv_fn=_parse_csv,
        parse_json_records_fn=_parse_json_records,
        read_url_text_fn=_read_url_text,
    )


def _load_registered_source_table(source_id: str, org_id: str | None) -> Any:
    """Load a registered source from the org registry as a columnar table."""
    return data_map_sources.load_registered_source_table(source_id, org_id)


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
    return await data_map_sources.load_source_records(
        src,
        org_id=org_id,
        parse_csv_fn=_parse_csv,
        parse_json_records_fn=_parse_json_records,
        fetch_url_fn=_fetch_url,
        load_registered_source_table_fn=_load_registered_source_table,
    )


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
    return await data_map_sources.load_source_table(
        src,
        org_id=org_id,
        parse_json_records_fn=_parse_json_records,
        read_url_text_fn=_read_url_text,
        load_registered_source_table_fn=_load_registered_source_table,
        delimited_text_to_arrow_table_fn=delimited_text_to_arrow_table,
    )


# ── Query Without SQL (removed — replaced by routers/query.py structured engine) ──


async def _legacy_query_data_unused(
    payload: _LegacyQueryRequest,
    auth: AuthContext = Depends(get_current_org),
) -> _LegacyQueryResponse:
    return await execute_legacy_query(
        payload,
        org_id=str(auth["org_id"]),
        load_source_fn=lambda src, org_id: _load_source(src, org_id=org_id),
        semantic_similarity_fn=_semantic_similarity,
    )
