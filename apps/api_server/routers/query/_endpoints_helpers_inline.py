"""Helpers extracted from query_sources endpoint — inline group.

Originally extracted into _endpoints_resolve_query_helpers.py then split per
logical group so each file stays under 1000 lines.
"""
from __future__ import annotations
import io
import re
import time
from datetime import date
from typing import Any, cast
from fastapi import HTTPException
from apps.api_server.routers.data_map import _call_mojo_column_profile
from apps.api_server.routers.query_contract import (
    _DECISION_AUTO_ACCEPT_CONFIDENCE, METRIC, TIME, CandidateColumn, QueryRequest, QueryResponse,
    _decision_contract_flags,
)
from apps.api_server.routers.query_response_helpers import _build_query_response, _dedupe_source_values
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.routers.query._cache_classes import _CachedSource, _get_registry_planner, _load_profiled_source
from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta
from apps.api_server.routers.query._resolvers import _call_mojo_source_score, _find_best_join_key
from apps.api_server.routers.query._execute_filters import _apply_filter_conditions, _resolve_filter_conditions
from apps.api_server.routers.query._signatures import _detect_relations, _inline_schema_revision

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

async def _resolve_inline_anchor_metric_group(
    payload: QueryRequest,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    target_role: str,
    cache_entries: dict[str, "_CachedSource"],
    cache_hits: set[str],
) -> tuple[
    QueryResponse | None,
    "SchemaGraph",
    str,
    str,
    str,
    "ColumnNode",
    float,
    list[dict[str, Any]],
    dict[str, float],
    bool,
    str | None,
    str,
    float,
]:
    """Inline-graph anchor/metric/group resolution stage.

    Builds the inline ``SchemaGraph``, runs Mojo source resolution (with the
    ``preferred_source`` hard-lock), resolves the metric column (with METRIC
    role fallback and global fallback), resolves the group column, and
    enforces decision-contract validation. When the metric is unresolvable
    or the decision contract rejects the request, the first tuple element
    is a short-circuit ``QueryResponse`` and the caller must return it
    immediately. Otherwise the first element is ``None`` and the remaining
    fields describe the resolved state for downstream execution.
    """
    # ── Assemble graph from cache entries ─────────────────────────────────────
    graph: SchemaGraph = {name: e.graph_nodes for name, e in cache_entries.items()}
    schema_revision_inline = _inline_schema_revision(graph)

    for src_name, nodes in graph.items():
        hit_label = "HIT" if src_name in cache_hits else "MISS"
        role_counts: dict[str, int] = {}
        for node in nodes.values():
            role_counts[node.role] = role_counts.get(node.role, 0) + 1
        plan.append(
            f"Graph [{src_name}] ({hit_label}): "
            + ", ".join(f"{r}:{n}" for r, n in sorted(role_counts.items()))
        )

    # ── SOURCE RESOLVER — runs before column resolution ───────────────────────
    #
    # Determine WHICH source this query is about before picking columns.
    # This prevents Bookings from winning every query just because it happens
    # to have the globally highest-confidence derived_measure column.
    #
    # Flow:
    #   1. Score all sources (metric role + hint overlap + group dimension overlap)
    #   2. Select the anchored source
    #   3. Resolve metric column WITHIN the anchored source
    #   4. If anchored source has no suitable metric → find globally, cross-source join
    #   5. Resolve group column (prefer anchored source, fall back to others → cross-source)
    #
    hint_tokens = set(re.findall(r"[a-z0-9]+", (payload.metric.hint or "").lower()))

    # Source resolver — Mojo-first, Python fallback
    mojo_src = await _call_mojo_source_score(
        target_role=target_role,
        metric_hint_tokens=hint_tokens,
        group_tokens=payload.group_by,
        preferred_source=payload.preferred_source,
        graph=graph,
    )
    if mojo_src:
        anchored_src, src_score, all_src_scores = mojo_src
        plan.append("Source resolver: mojo")
    else:
        anchored_src, src_score, all_src_scores = resolve_source(
            target_role=target_role,
            metric_hint_tokens=hint_tokens,
            group_tokens=payload.group_by,
            preferred_source=payload.preferred_source,
            graph=graph,
        )

    # Hard lock: when the LLM explicitly names a source it knows is right,
    # don't let the resolver override it. The score is kept for transparency.
    if payload.preferred_source and payload.preferred_source in graph:
        anchored_src = payload.preferred_source
        src_score = max(src_score, all_src_scores.get(payload.preferred_source, 0.50))
        plan.append(f"Source resolver: locked to preferred_source={anchored_src}")

    ambiguous = src_score < _DECISION_AUTO_ACCEPT_CONFIDENCE
    plan.append(
        f"Source resolver: {anchored_src} (score={src_score:.2f})"
        + ("  [AMBIGUOUS — low confidence]" if ambiguous else "")
        + f"  all={dict(sorted(all_src_scores.items(), key=lambda x: -x[1]))}"
    )

    # Resolve metric WITHIN the anchored source first
    src_name, metric_col, metric_conf, all_candidates = resolve_metric_column(
        target_role, hint_tokens, graph, preferred_source=anchored_src
    )

    # If anchored source has no suitable metric → try METRIC fallback within same source,
    # then (if preferred_source is NOT set) try global.
    # When preferred_source IS set, stay within that source even with METRIC fallback —
    # the user named this source intentionally.
    if not metric_col and anchored_src:
        plan.append(f"No {target_role} in {anchored_src} — trying METRIC fallback within source")
        _, mc2, mconf2, cands2 = resolve_metric_column(
            METRIC, hint_tokens, graph, preferred_source=anchored_src
        )
        if mc2:
            src_name, metric_col, metric_conf, all_candidates = (
                anchored_src,
                mc2,
                round(mconf2 * 0.5, 3),
                cands2,
            )

    # Last resort global fallback — only when no preferred_source lock
    if not metric_col and not payload.preferred_source:
        plan.append(f"No metric in {anchored_src} — global fallback")
        src_name, metric_col, metric_conf, all_candidates = resolve_metric_column(
            target_role, hint_tokens, graph
        )

    if not metric_col:
        return (_build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=0.0,
            plan=plan + [f"No column with role={target_role} found in any source"],
            resolved_column="",
            resolved_role="",
            resolved_source="",
            row_count=0,
            candidates=[],
            source_scores=all_src_scores,
            ambiguous=True,
            exact_spec=False,
            explanation=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision_inline,
            validated=False,
            confidence_source="min(source_resolver, metric_resolver, group_resolver)",
            clarification_required=False,
            rejection_reason="schema_incomplete",
            plan_basis={"reason": "metric_not_found", "aggregation": payload.aggregation},
            source_set=_dedupe_source_values([anchored_src]),
            planner_mode="inline_graph",
        ), cast("SchemaGraph", {}), "", "", "", cast("ColumnNode", None), 0.0, [], {}, False, None, "", 0.0)

    metric_node = graph[src_name][metric_col]
    if len(all_candidates) >= 2:
        metric_gap = all_candidates[0]["confidence"] - all_candidates[1]["confidence"]
        if metric_gap < 0.08:
            plan.append(
                "Metric ambiguity: "
                f"top={all_candidates[0]['column']} "
                f"second={all_candidates[1]['column']} gap={metric_gap:.3f}"
            )
    plan.append(
        f"Metric: `{metric_col}` in {src_name}  "
        f"role={metric_node.role}  magnitude={metric_node.magnitude_class}  "
        f"conf={metric_conf:.2f}"
        + (f"  formula={metric_node.formula}" if metric_node.formula else "")
    )

    # ── Group column — prefer anchored source, fall back to any source ────────
    group_col: str | None = None
    group_src: str = src_name
    gc_conf: float = 0.0

    if payload.group_by:
        group_src, group_col, gc_conf = resolve_group_column_graph(
            payload.group_by,
            src_name,
            graph,  # prefer metric's source first
        )
        if group_col:
            cross = group_src != src_name
            plan.append(
                f"Group-by: `{group_col}` in {group_src} (score={gc_conf:.2f})"
                + (" [cross-source join required]" if cross else "")
            )
        else:
            plan.append(f"Group-by {payload.group_by}: no matching column found")
            group_src = src_name

    group_confidence = gc_conf if payload.group_by else 1.0
    if payload.group_by and not group_col:
        group_confidence = 0.0
    decision_confidence = round(min(src_score, metric_conf, group_confidence), 3)
    contract_error_text = (
        "dimension metadata missing for requested group_by"
        if payload.group_by and not group_col
        else None
    )
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        decision_confidence,
        all_candidates,
        error_text=contract_error_text,
    )
    if not validated:
        if clarification_required:
            plan.append(
                "Clarification required: source, metric, or group resolution did not meet "
                "deterministic execution threshold."
            )
        else:
            plan.append(f"Rejected: {rejection_reason or 'schema_unresolved'} before execution")
        return (_build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=decision_confidence,
            plan=plan,
            resolved_column=metric_col,
            resolved_role=metric_node.role,
            resolved_source=src_name,
            row_count=0,
            candidates=all_candidates[:5],
            source_scores=all_src_scores,
            ambiguous=True,
            exact_spec=False,
            explanation=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision_inline,
            validated=False,
            confidence_source="min(source_resolver, metric_resolver, group_resolver)",
            clarification_required=clarification_required,
            rejection_reason=rejection_reason,
            plan_basis={
                "source": src_name,
                "metric_column": metric_col,
                "aggregation": payload.aggregation,
                "group_by": payload.group_by,
            },
            source_set=_dedupe_source_values([src_name, group_src]),
            planner_mode="inline_graph",
        ), cast("SchemaGraph", {}), "", "", "", cast("ColumnNode", None), 0.0, [], {}, False, None, "", 0.0)
    return (
        None,
        graph,
        schema_revision_inline,
        src_name,
        metric_col,
        metric_node,
        metric_conf,
        all_candidates,
        all_src_scores,
        ambiguous,
        group_col,
        group_src,
        decision_confidence,
    )


def _execute_inline_and_build_response(
    payload: QueryRequest,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    graph: "SchemaGraph",
    cache_entries: dict[str, "_CachedSource"],
    parsed_tables: dict[str, Any],
    _reg_connections: list[dict[str, Any]],
    src_name: str,
    metric_col: str,
    metric_node: "ColumnNode",
    metric_conf: float,
    all_candidates: list[dict[str, Any]],
    all_src_scores: dict[str, float],
    ambiguous: bool,
    group_col: str | None,
    group_src: str,
    decision_confidence: float,
    schema_revision_inline: str,
) -> QueryResponse:
    """Final inline-path execution + response assembly.

    Handles time-filter resolution, record loading, filter application,
    cross-source join key resolution (with rejection paths for ambiguous /
    missing joins), execute()/execute_cross_source() dispatch, and the
    final ``QueryResponse``. Raises ``HTTPException`` 422 on
    ``invalid_filter_condition``.
    """
    # ── Time filter ───────────────────────────────────────────────────────────
    date_col: str | None = None
    tr: tuple[date, date] | None = None
    if payload.filter and payload.filter.time_filter:
        date_col = find_time_column(src_name, graph)
        tr = time_range(payload.filter.time_filter)
        if date_col:
            plan.append(f"Time column: `{date_col}`  range: {payload.filter.time_filter}")
        else:
            plan.append("No TIME-role column found — time filter skipped")

    # ── Load records for execution (from cache or parsed) ────────────────────
    import pandas as pd

    def _load_records(name: str) -> list[dict[str, Any]]:
        if name in parsed_tables:
            records: list[dict[str, Any]] = parsed_tables[name].to_pylist()
            return records
        buf = io.BytesIO(cache_entries[name].parquet_bytes)
        initialize_pyarrow_parquet_runtime()
        records = pd.read_parquet(buf).to_dict(orient="records")
        return records

    exec_records = _load_records(src_name)
    try:
        resolved_filter_conditions = _resolve_filter_conditions(
            source_name=src_name,
            filter_spec=payload.filter,
            graph_nodes=graph.get(src_name, {}),
            records=exec_records,
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
    exec_records, filter_plan = _apply_filter_conditions(
        exec_records,
        resolved_filter_conditions,
    )
    plan.extend(filter_plan)

    # ── Execute (same-source or cross-source join) ────────────────────────────
    cross_source = bool(group_col and group_src != src_name)

    if cross_source:
        # Find the join key between metric source and group source (confidence-filtered)
        join_triplet = _find_best_join_key(src_name, group_src, _reg_connections)
        if join_triplet:
            join_metric_col, join_group_col, join_conf, join_card = join_triplet
            if join_conf < _DECISION_AUTO_ACCEPT_CONFIDENCE:
                plan.append(
                    f"Rejected: join confidence {join_conf:.2f} is below "
                    f"{_DECISION_AUTO_ACCEPT_CONFIDENCE:.2f}"
                )
                return _build_query_response(
                    query_id=query_id,
                    request_id=request_id,
                    result=None,
                    result_type="none",
                    confidence=round(min(decision_confidence, join_conf), 3),
                    plan=plan,
                    resolved_column=metric_col,
                    resolved_role=metric_node.role,
                    resolved_source=f"{src_name} ⋈ {group_src}",
                    row_count=0,
                    candidates=all_candidates[:5],
                    source_scores=all_src_scores,
                    ambiguous=True,
                    exact_spec=False,
                    explanation=[],
                    latency_ms=round((time.monotonic() - t0) * 1000, 1),
                    decision_path="planner_hint",
                    schema_revision=schema_revision_inline,
                    validated=False,
                    confidence_source=(
                        "min(source_resolver, metric_resolver, group_resolver, join_confidence)"
                    ),
                    clarification_required=False,
                    rejection_reason="join_ambiguity",
                    plan_basis={
                        "source": src_name,
                        "group_source": group_src,
                        "metric_column": metric_col,
                        "group_column": group_col,
                    },
                    source_set=_dedupe_source_values([src_name, group_src]),
                    join_path=[
                        {
                            "left_source": src_name,
                            "left_key": join_metric_col,
                            "right_source": group_src,
                            "right_key": join_group_col,
                            "confidence": round(join_conf, 3),
                            "cardinality": join_card,
                        }
                    ],
                    planner_mode="inline_graph",
                )
            plan.append(
                f"Join key: {src_name}.{join_metric_col} = {group_src}.{join_group_col}"
                f"  (conf={join_conf:.2f}  card={join_card or '?'})"
            )
            group_records = _load_records(group_src)
            assert group_col is not None
            result, row_count, exec_plan = execute_cross_source(
                metric_records=exec_records,
                metric_col=metric_col,
                group_records=group_records,
                group_col=group_col,
                join_metric_col=join_metric_col,
                join_group_col=join_group_col,
                agg=payload.aggregation,
                limit=payload.limit,
                order=payload.order,
                join_cardinality=join_card,
            )
        else:
            plan.append(
                f"Rejected: no deterministic join key found between {src_name} and {group_src}"
            )
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=decision_confidence,
                plan=plan,
                resolved_column=metric_col,
                resolved_role=metric_node.role,
                resolved_source=f"{src_name} ⋈ {group_src}",
                row_count=0,
                candidates=all_candidates[:5],
                source_scores=all_src_scores,
                ambiguous=True,
                exact_spec=False,
                explanation=[],
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision_inline,
                validated=False,
                confidence_source="min(source_resolver, metric_resolver, group_resolver)",
                clarification_required=False,
                rejection_reason="join_ambiguity",
                plan_basis={
                    "source": src_name,
                    "group_source": group_src,
                    "metric_column": metric_col,
                    "group_column": group_col,
                },
                source_set=_dedupe_source_values([src_name, group_src]),
                planner_mode="inline_graph",
            )
    else:
        join_conf = 1.0
        result, row_count, exec_plan = execute(
            records=exec_records,
            metric_col=metric_col,
            agg=payload.aggregation,
            group_col=group_col,
            date_col=date_col,
            tr=tr,
            limit=payload.limit,
            order=payload.order,
        )
    plan.extend(exec_plan)

    # ── Response ──────────────────────────────────────────────────────────────
    if result is None:
        result_type = "none"
    elif isinstance(result, list):
        result_type = "table"
    else:
        result_type = "scalar"

    # resolved_source: show both if cross-source join was used
    resolved_src_label = f"{src_name} ⋈ {group_src}" if cross_source and group_col else src_name
    final_confidence = round(min(decision_confidence, join_conf), 3)

    return _build_query_response(
        query_id=query_id,
        request_id=request_id,
        result=result,
        result_type=result_type,
        confidence=final_confidence,
        plan=plan,
        resolved_column=metric_col,
        resolved_role=metric_node.role,
        resolved_source=resolved_src_label,
        row_count=row_count,
        candidates=[CandidateColumn(**c) for c in all_candidates[:5]],
        source_scores=all_src_scores,
        ambiguous=ambiguous,
        exact_spec=False,
        explanation=[],
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        decision_path="planner_hint",
        schema_revision=schema_revision_inline,
        validated=True,
        confidence_source="min(source_resolver, metric_resolver, group_resolver, join_confidence)",
        plan_basis={
            "source": src_name,
            "metric_column": metric_col,
            "group_column": group_col,
            "aggregation": payload.aggregation,
        },
        deterministic_scope="planned_execution",
        source_set=_dedupe_source_values([src_name, group_src]),
        join_path=(
            [
                {
                    "left_source": src_name,
                    "left_key": join_metric_col,
                    "right_source": group_src,
                    "right_key": join_group_col,
                    "confidence": round(join_conf, 3),
                    "cardinality": join_card,
                }
            ]
            if cross_source
            else []
        ),
        planner_mode="inline_graph",
    )


