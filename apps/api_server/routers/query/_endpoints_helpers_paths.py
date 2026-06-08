"""Helpers extracted from query_sources endpoint — paths group.

Originally extracted into _endpoints_resolve_query_helpers.py then split per
logical group so each file stays under 1000 lines.
"""
from __future__ import annotations
import asyncio
import hashlib
import io
import json
import time
from typing import Any, Callable
from fastapi import HTTPException
from apps.api_server.services import source_registry as _sreg_visible
from apps.api_server.routers.data_map import _call_mojo_column_profile
from apps.api_server.routers.query_contract import (
    _DECISION_AUTO_ACCEPT_CONFIDENCE, CandidateColumn, QueryRequest, QueryResponse, _decision_contract_flags, _http_error,
)
from apps.api_server.routers.query_response_helpers import _build_query_response, _dedupe_source_values, _normalize_filter_spec
from apps.api_server.schemas.data_map import DataSource
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_map_errors import MojoInstrumentationError
from apps.api_server.services.data_map_mojo_profiles import _build_mojo_column_profile_columns, _mojo_column_profile_sample_limits, _mojo_profiling_status_from_result
from apps.api_server.routers.query._state import (
    _CACHE_LOCK, _RESULT_CACHE, _RESULT_CACHE_MAX, _RESULT_CACHE_TTL, _SOURCE_CACHE, _run_cached_planner_method,
)
from apps.api_server.routers.query._cache_classes import (
    _CachedSource, _get_registry_planner, _load_profiled_source, _planner_load_bearing_validation_notes, _planner_metric_candidate_payloads, _planner_query_confidence,
    _raise_empty_source, _source_cache_key, _source_cache_put,
)
from apps.api_server.routers.query._schema_graph import _arrow_physical_types, _build_schema_metadata, _graph_nodes_from_meta
from apps.api_server.routers.query._signatures import _detect_relations

def _build_query_response(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    return _facade._build_query_response(*args, **kwargs)


def _call_mojo_column_profile(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    return _facade._call_mojo_column_profile(*args, **kwargs)


def _detect_relations(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._detect_relations
    if fn is _detect_relations:
        from apps.api_server.routers.query._signatures import _detect_relations as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _get_registry_planner(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._get_registry_planner
    if fn is _get_registry_planner:
        from apps.api_server.routers.query._cache_classes import _get_registry_planner as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _graph_nodes_from_meta(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._graph_nodes_from_meta
    if fn is _graph_nodes_from_meta:
        from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _load_profiled_source(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._load_profiled_source
    if fn is _load_profiled_source:
        from apps.api_server.routers.query._cache_classes import _load_profiled_source as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute
    if fn is execute:
        from apps.api_server.routers.query._execute_main import execute as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute_cross_source(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute_cross_source
    if fn is execute_cross_source:
        from apps.api_server.routers.query._execute_main import execute_cross_source as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute_join_path(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute_join_path
    if fn is execute_join_path:
        from apps.api_server.routers.query._execute_main import execute_join_path as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def find_time_column(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.find_time_column
    if fn is find_time_column:
        from apps.api_server.routers.query._execute_filters import find_time_column as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def time_range(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.time_range
    if fn is time_range:
        from apps.api_server.routers.query._execute_filters import time_range as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)



# ════════════════════════════════════════════════════════════════════════
# Helpers extracted from ``query_sources`` (see _endpoints_resolve_query.py).
# Each helper preserves the original semantics; the endpoint dispatches into
# these in the same order as the original inline code.

async def _run_registry_planner_hint_path(
    payload: QueryRequest,
    auth: AuthContext,
    org_id: str,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    target_role: str,
    visible_registry_entries_loader: Callable[[], list[dict[str, Any]]],
) -> QueryResponse:
    """Run the registry-planner hint path used when ``payload.sources`` is empty.

    Always returns a ``QueryResponse``. Handles the empty-registry early
    return, planner acquisition, hint result-cache HIT, planner.plan +
    planner.execute_plan, decision-contract rejection/clarification, and
    final response assembly. Raises ``HTTPException`` 422 on
    ``invalid_filter_condition``.
    """
    registered = visible_registry_entries_loader()
    if not registered:
        empty_schema_revision = _sreg_visible.schema_revision(org_id)
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=0.0,
            plan=plan
            + [
                "No registered sources found for this org. Use POST /v1/sources/register first."
            ],
            resolved_column="",
            resolved_role="",
            resolved_source="",
            row_count=0,
            candidates=[],
            source_scores={},
            ambiguous=True,
            exact_spec=False,
            explanation=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=empty_schema_revision,
            validated=False,
            confidence_source="planner_query_confidence",
            clarification_required=False,
            rejection_reason="schema_incomplete",
            plan_basis={"reason": "no_registered_sources"},
        )

    planner, planner_cache_hit, schema_revision = await _get_registry_planner(
        org_id,
        llm_policy="never",
        auth=auth,
        visible_entries=registered,
    )
    metric_hint = (payload.metric.hint or "").strip() or target_role.replace("_", " ")
    dim_hint = (
        " ".join(part.strip() for part in payload.group_by if part and part.strip()) or None
    )
    normalized_filter_spec = _normalize_filter_spec(payload.filter)
    time_filter = payload.filter.time_filter if payload.filter else None

    hint_result_key = hashlib.sha256(
        json.dumps(
            {
                "org": org_id,
                "rev": schema_revision,
                "metric_hint": metric_hint,
                "dim_hint": dim_hint or "",
                "preferred_source": payload.preferred_source or "",
                "agg": payload.aggregation,
                "limit": payload.limit,
                "order": payload.order,
                "filter": normalized_filter_spec or {},
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:24]

    cached_hint = _RESULT_CACHE.get(hint_result_key)
    if cached_hint and (time.monotonic() - cached_hint.get("_ts", 0)) < _RESULT_CACHE_TTL:
        warm_plan = list(plan)
        warm_plan.append(
            f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
        )
        warm_plan.append(f"Hint result cache HIT [{hint_result_key[:8]}]")
        warm_plan.extend(cached_hint.get("plan_body", []))
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=cached_hint["result"],
            result_type=cached_hint["result_type"],
            confidence=cached_hint["confidence"],
            plan=warm_plan,
            resolved_column=cached_hint["resolved_column"],
            resolved_role=cached_hint["resolved_role"],
            resolved_source=cached_hint["resolved_source"],
            row_count=cached_hint["row_count"],
            candidates=[CandidateColumn(**cand) for cand in cached_hint.get("candidates", [])],
            source_scores=cached_hint.get("source_scores", {}),
            ambiguous=cached_hint.get("ambiguous", False),
            exact_spec=False,
            explanation=cached_hint.get("explanation", []),
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision,
            validated=True,
            confidence_source="planner_query_confidence",
            plan_basis={"cache_key": hint_result_key},
            deterministic_scope="planned_execution",
            source_set=cached_hint.get("source_set", []),
            join_path=cached_hint.get("join_path", []),
            planner_mode="registry_planner",
            log_response=False,
        )

    plan.append(f"Registry: {len(registered)} registered sources for org {org_id}")
    plan.append(
        f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
    )

    qplan = await _run_cached_planner_method(
        planner,
        "plan",
        metric_hint=metric_hint,
        dim_hint=dim_hint,
        agg=payload.aggregation,
        preferred_source=payload.preferred_source,
    )
    plan.extend(qplan.steps)

    confidence = _planner_query_confidence(qplan)
    ambiguous = bool(qplan.error) or confidence < _DECISION_AUTO_ACCEPT_CONFIDENCE
    metric_candidate_payloads = _planner_metric_candidate_payloads(
        plan=qplan,
        graph=planner.graph,
        metric_hint=metric_hint,
        target_role=qplan.metric_role or target_role,
        preferred_source=payload.preferred_source,
    )

    plan_error_text = (
        "; ".join(
            note
            for note in [qplan.error or "", *_planner_load_bearing_validation_notes(qplan)]
            if note
        )
        or None
    )
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        confidence,
        metric_candidate_payloads,
        error_text=plan_error_text,
    )
    source_scores_hint = (
        {qplan.metric_src: round(qplan.metric_conf, 3)} if qplan.metric_src else {}
    )
    if not validated:
        if clarification_required:
            plan.append(
                "Clarification required: planner confidence or candidate separation "
                "did not meet deterministic execution threshold."
            )
        else:
            plan.append(f"Rejected: {rejection_reason or 'schema_unresolved'} before execution")
        explanation = [
            f"Metric hint: {metric_hint}",
            f"Planner confidence: {confidence:.3f}",
        ]
        if plan_error_text:
            explanation.append(f"Planner note: {plan_error_text}")
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=confidence,
            plan=plan,
            resolved_column=qplan.metric_col or "",
            resolved_role=qplan.metric_role or "",
            resolved_source=qplan.metric_src or "",
            row_count=0,
            candidates=metric_candidate_payloads[:5],
            source_scores=source_scores_hint,
            ambiguous=True,
            exact_spec=False,
            explanation=explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision,
            validated=False,
            confidence_source="planner_query_confidence",
            clarification_required=clarification_required,
            rejection_reason=rejection_reason,
            plan_basis={
                "cache_key": hint_result_key,
                "metric_hint": metric_hint,
                "dim_hint": dim_hint or "",
                "aggregation": payload.aggregation,
            },
            source_set=_dedupe_source_values(
                [
                    qplan.metric_src or "",
                    qplan.group_src or "",
                    *[hop.right_source for hop in qplan.join_hops],
                ]
            ),
            join_path=[
                {
                    "left_source": hop.left_source,
                    "left_key": hop.left_key,
                    "right_source": hop.right_source,
                    "right_key": hop.right_key,
                    "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                    "cardinality": getattr(hop, "cardinality", None),
                }
                for hop in qplan.join_hops
            ],
            planner_mode="registry_planner",
        )

    try:
        result, row_count, exec_plan = await _run_cached_planner_method(
            planner,
            "execute_plan",
            qplan,
            limit=payload.limit,
            order=payload.order,
            time_filter=time_filter,
            filter_spec=payload.filter,
        )
    except ValueError as _e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_filter_condition",
                    "message": str(_e),
                }
            },
        ) from _e
    plan.extend(exec_plan)

    if result is None:
        result_type = "none"
    elif isinstance(result, list):
        result_type = "table"
    else:
        result_type = "scalar"

    resolved_source = (
        " ⋈ ".join([qplan.metric_src] + [hop.right_source for hop in qplan.join_hops])
        if qplan.join_hops
        else qplan.metric_src
    )
    metric_node = planner.graph.get(qplan.metric_src, {}).get(qplan.metric_col)
    candidates: list[CandidateColumn] = []
    for cand in metric_candidate_payloads[:5]:
        candidates.append(CandidateColumn(**cand))
    if not candidates and metric_node is not None and qplan.metric_src and qplan.metric_col:
        candidates.append(
            CandidateColumn(
                source=qplan.metric_src,
                column=qplan.metric_col,
                role=metric_node.role,
                magnitude=metric_node.magnitude_class,
                formula=metric_node.formula,
                confidence=qplan.metric_conf,
            )
        )

    explanation = [
        f"Metric hint: {metric_hint}",
        f"Resolved metric: {qplan.metric_src}.{qplan.metric_col}"
        if qplan.metric_src and qplan.metric_col
        else "Resolved metric: none",
        f"Aggregation: {payload.aggregation}",
    ]
    if qplan.group_col and qplan.group_src:
        explanation.append(f"Group by: {qplan.group_src}.{qplan.group_col}")
    if qplan.join_hops:
        hop_text = " -> ".join(
            f"{hop.left_source}.{hop.left_key}={hop.right_source}.{hop.right_key}"
            for hop in qplan.join_hops
        )
        explanation.append(f"Join path: {hop_text}")
    if time_filter:
        explanation.append(f"Time filter: {time_filter}")
    explanation.append(
        f"Confidence: {confidence:.3f}" + (f"  error={qplan.error}" if qplan.error else "")
    )

    plan_body = list(qplan.steps) + list(exec_plan)
    if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
        oldest = min(_RESULT_CACHE.items(), key=lambda item: item[1].get("_ts", 0))
        del _RESULT_CACHE[oldest[0]]
    _RESULT_CACHE[hint_result_key] = {
        "result": result,
        "result_type": result_type,
        "confidence": confidence,
        "resolved_column": qplan.metric_col or "",
        "resolved_role": qplan.metric_role or "",
        "resolved_source": resolved_source or "",
        "row_count": row_count,
        "candidates": [cand.model_dump() for cand in candidates],
        "source_scores": source_scores_hint,
        "ambiguous": ambiguous,
        "explanation": explanation,
        "source_set": _dedupe_source_values(
            [
                qplan.metric_src or "",
                qplan.group_src or "",
                *[hop.right_source for hop in qplan.join_hops],
            ]
        ),
        "join_path": [
            {
                "left_source": hop.left_source,
                "left_key": hop.left_key,
                "right_source": hop.right_source,
                "right_key": hop.right_key,
                "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                "cardinality": getattr(hop, "cardinality", None),
            }
            for hop in qplan.join_hops
        ],
        "plan_body": plan_body,
        "_ts": time.monotonic(),
    }
    plan.append(f"Hint result cache STORED [{hint_result_key[:8]}]")

    return _build_query_response(
        query_id=query_id,
        request_id=request_id,
        result=result,
        result_type=result_type,
        confidence=confidence,
        plan=plan,
        resolved_column=qplan.metric_col or "",
        resolved_role=qplan.metric_role or "",
        resolved_source=resolved_source or "",
        row_count=row_count,
        candidates=candidates,
        source_scores=source_scores_hint,
        ambiguous=ambiguous,
        exact_spec=False,
        explanation=explanation,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        decision_path="planner_hint",
        schema_revision=schema_revision,
        validated=True,
        confidence_source="planner_query_confidence",
        plan_basis={
            "cache_key": hint_result_key,
            "resolved_source": resolved_source or "",
            "resolved_column": qplan.metric_col or "",
            "aggregation": payload.aggregation,
        },
        deterministic_scope="planned_execution",
        source_set=_dedupe_source_values(
            [
                qplan.metric_src or "",
                qplan.group_src or "",
                *[hop.right_source for hop in qplan.join_hops],
            ]
        ),
        join_path=[
            {
                "left_source": hop.left_source,
                "left_key": hop.left_key,
                "right_source": hop.right_source,
                "right_key": hop.right_key,
                "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                "cardinality": getattr(hop, "cardinality", None),
            }
            for hop in qplan.join_hops
        ],
        planner_mode="registry_planner",
    )


async def _ingest_and_profile_inline_sources(
    payload: QueryRequest,
    org_id: str,
    plan: list[str],
    request_id: str | None,
) -> tuple[
    dict[str, "_CachedSource"],
    set[str],
    dict[str, Any],
    dict[str, dict[str, dict[str, Any]]],
    list[dict[str, Any]],
]:
    """Load and Mojo-profile every inline ``DataSource``.

    Concurrent Mojo column profiling + relation detection on cache misses;
    embeds derived schema metadata into Arrow tables; populates
    ``_SOURCE_CACHE``. Returns
    ``(cache_entries, cache_hits, parsed_tables, profiles, _reg_connections)``.
    Raises ``HTTPException`` 503 (MojoInstrumentationError) or 422 (empty source).
    """
    # ── Load + profile all sources (cache-aware) ─────────────────────────────
    parsed_tables: dict[str, Any] = {}
    profiles: dict[str, dict[str, dict[str, Any]]] = {}
    cache_hits: set[str] = set()
    cache_entries: dict[str, _CachedSource] = {}  # src.name → cached entry
    # Registry connections (populated when loading from registry; used for cross-source joins)
    _reg_connections: list[dict[str, Any]] = []

    for src in payload.sources:
        cache_key, content_keyed = _source_cache_key(src)
        async with _CACHE_LOCK:
            entry = _SOURCE_CACHE.get(cache_key)
            if entry and entry.is_fresh():
                entry.touch()
                cache_entries[src.name] = entry
                cache_hits.add(src.name)
                plan.append(f"Cache HIT [{src.name}] — skipping load+profile")
                continue
        # source_id miss — load from registry (parquet on disk)
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            from apps.api_server.services import source_registry as _sreg

            parquet_bytes = _sreg.get_source_parquet(org_id, registered_id)
            if parquet_bytes:
                schema_meta_dict = _sreg.get_source_meta(org_id, registered_id) or {}
                graph_nodes = _graph_nodes_from_meta(schema_meta_dict)
                reg_entry = _CachedSource(
                    parquet_bytes=parquet_bytes,
                    parquet_schema_meta=json.dumps(schema_meta_dict).encode(),
                    profile={},
                    mojo_profile={},
                    relations=schema_meta_dict.get("formulas", []),
                    graph_nodes=graph_nodes,
                    schema_meta=schema_meta_dict,
                    mojo_profiling_status=schema_meta_dict.get("mojo_profiling_status") or {},
                    content_keyed=True,
                )
                async with _CACHE_LOCK:
                    _source_cache_put(reg_entry, registered_id)
                cache_entries[src.name] = reg_entry
                plan.append(f"Registry HIT (dataset/source id) [{src.name}]")
                continue
            plan.append(
                f"WARNING: source_id={registered_id} not found in registry for [{src.name}]"
            )
        # Cache miss — adaptively load on the fastest safe path for this source
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            _raise_empty_source(src.name)
        profiles[src.name] = loaded.profile
        parsed_tables[src.name] = loaded.arrow_table
        plan.append(f"Ingest [{src.name}] mode={loaded.ingest_mode}")

    # ── Mojo: profiling + relation detection (concurrent, only for misses) ──
    miss_names = list(parsed_tables.keys())
    if miss_names:

        def _adaptive_profile_payload(name: str) -> dict[str, dict[str, Any]]:
            value_limit, string_limit = _mojo_column_profile_sample_limits(len(profiles[name]))
            return _build_mojo_column_profile_columns(
                profiles[name],
                value_limit=value_limit,
                string_limit=string_limit,
                include_fill_rate=True,
            )

        profiler_coros = [
            _call_mojo_column_profile(_adaptive_profile_payload(name)) for name in miss_names
        ]
        relation_coros = [_detect_relations(name, profiles) for name in miss_names]
        try:
            profiler_results, relation_results = await asyncio.gather(
                asyncio.gather(*profiler_coros),
                asyncio.gather(*relation_coros),
            )
        except MojoInstrumentationError as exc:
            raise _http_error(
                503,
                code="mojo_instrumentation_unavailable",
                message=(
                    "Mojo column profiling is unavailable while strict runtime "
                    "fallbacks are disabled."
                ),
                request_id=request_id,
                details=[("engine_type", exc.engine_type)],
            ) from exc
        for i, name in enumerate(miss_names):
            profiling_status = _mojo_profiling_status_from_result(profiler_results[i])
            mojo_prof = (profiler_results[i] or {}).get("profiles", {})
            rels = relation_results[i]
            if rels:
                plan.append(f"Formulas in {name}: {len(rels)} detected (top: {rels[0]['formula']})")
            if profiling_status.get("status") != "enabled":
                plan.append(
                    "Mojo profiling disabled "
                    f"[{name}] reason={profiling_status.get('reason') or 'unknown'}"
                )
            # Build graph nodes for this source
            src_graph = build_schema_graph(
                {name: profiles[name]},
                {name: mojo_prof},
                {name: rels},
            )
            import pyarrow.parquet as pq

            schema_meta = _build_schema_metadata(
                name,
                src_graph[name],
                rels,
                profiles[name],
                profiling_status,
                _arrow_physical_types(parsed_tables[name].schema),
            )
            arrow_table = parsed_tables[name]
            # Embed schema metadata in Arrow custom_metadata
            existing_meta = arrow_table.schema.metadata or {}
            new_meta = {
                **existing_meta,
                b"algenta_schema": json.dumps(schema_meta).encode(),
            }
            arrow_table = arrow_table.replace_schema_metadata(new_meta)
            buf = io.BytesIO()
            pq.write_table(arrow_table, buf)
            parquet_bytes = buf.getvalue()
            # Also store just the schema metadata bytes (cheap to extract)
            schema_meta_bytes = json.dumps(schema_meta).encode()

            # Find original DataSource to get cache key + content_keyed flag
            for src in payload.sources:
                if src.name == name:
                    ck, ck_content = _source_cache_key(src)
                    entry = _CachedSource(
                        parquet_bytes=parquet_bytes,
                        parquet_schema_meta=schema_meta_bytes,
                        profile=profiles[name],
                        mojo_profile=mojo_prof,
                        relations=rels,
                        graph_nodes=src_graph[name],
                        schema_meta=schema_meta,
                        mojo_profiling_status=profiling_status,
                        content_keyed=ck_content,
                    )
                    async with _CACHE_LOCK:
                        _source_cache_put(entry, ck)
                    cache_entries[name] = entry
                    break
    return cache_entries, cache_hits, parsed_tables, profiles, _reg_connections


