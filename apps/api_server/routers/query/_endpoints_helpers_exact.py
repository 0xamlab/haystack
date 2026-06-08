"""Helpers extracted from query_sources endpoint — exact group.

Originally extracted into _endpoints_resolve_query_helpers.py then split per
logical group so each file stays under 1000 lines.
"""
from __future__ import annotations
import io
import time
from typing import Any, Callable
from fastapi import HTTPException
from apps.api_server.services.data_visibility import get_visible_source_entry_by_name
from apps.api_server.routers.data_map import _call_mojo_column_profile
from apps.api_server.routers.query_contract import JoinEdgeSpec, QueryRequest, QueryResponse, ResolvedPlan
from apps.api_server.routers.query_resolve_fast_path import _resolved_plan_current_schema_revision
from apps.api_server.routers.query_response_helpers import _build_query_response, _compute_exact_confidence, _exact_plan_basis, _immutable_plan_hash
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.routers.query._state import _RESULT_CACHE, _RESULT_CACHE_MAX, _RESULT_CACHE_TTL, _SOURCE_CACHE
from apps.api_server.routers.query._cache_classes import (
    _df_cache_get, _df_cache_put, _df_cache_records, _get_registry_planner, _load_profiled_source,
)
from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta
from apps.api_server.routers.query._resolvers import _resolve_join_path
from apps.api_server.routers.query._execute_filters import _apply_filter_conditions, _resolve_filter_conditions
from apps.api_server.routers.query._signatures import _detect_relations, _exact_query_required_sources, _graph_nodes_from_cached_meta

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

def _run_exact_spec_path(
    payload: QueryRequest,
    auth: AuthContext,
    org_id: str,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    visible_registry_entries: list[dict[str, Any]] | None,
    resolved_plan_schema_revision: str | None,
    visible_registry_entries_loader: Callable[[], list[dict[str, Any]]],
) -> QueryResponse:
    """Run the exact-spec execution branch end-to-end.

    Always returns a ``QueryResponse``. Handles the pre-I/O result cache,
    the COUNT(*) metadata fast path, the post-load result cache, and the
    full execute/execute_join_path dispatch. Raises ``HTTPException``
    400/404/422 on validation/load/filter/constraint errors.
    """
    plan.append(
        f"Exact-spec: source={payload.source_name}  metric={payload.metric_column}"
        + (f"  group={payload.group_column}" if payload.group_column else "")
        + (f"  join_hops={len(payload.join_path.edges)}" if payload.join_path else "")
    )

    import pandas as pd

    from apps.api_server.services import source_registry as _sreg_ex

    if resolved_plan_schema_revision is not None:
        schema_revision_exact = resolved_plan_schema_revision
    elif payload.dataset_id and not payload.join_path:
        dataset_source_revision = ""
        if visible_registry_entries:
            dataset_source_revision = str(
                visible_registry_entries[0].get("source_schema_revision") or ""
            )
        schema_revision_exact = dataset_source_revision or _sreg_ex.source_schema_revision(
            org_id, str(payload.dataset_id)
        )
    elif payload.join_path:
        schema_revision_exact = _sreg_ex.schema_revision(org_id)
    else:
        exact_visible_entries = visible_registry_entries
        if exact_visible_entries is None and str(auth.get("role", "")).lower() != "owner":
            exact_visible_entries = visible_registry_entries_loader()
        schema_revision_exact = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=ResolvedPlan(
                source_name=payload.source_name,
                metric_column=payload.metric_column,
                aggregation=payload.aggregation,
                group_column=payload.group_column,
                join_path=payload.join_path,
                filter=payload.filter,
                limit=payload.limit,
                order=payload.order,
                constraints=payload.constraints,
                schema_revision="",
            ),
            dataset_id=payload.dataset_id,
            visible_entries=exact_visible_entries,
        )
    exact_plan_basis = _exact_plan_basis(
        source_name=payload.source_name,
        metric_column=payload.metric_column,
        aggregation=payload.aggregation,
        group_column=payload.group_column,
        join_path=payload.join_path,
        filter_spec=payload.filter,
        limit=payload.limit,
        order=payload.order,
        constraints=payload.constraints,
    )
    exact_plan_hash = _immutable_plan_hash(
        schema_revision=schema_revision_exact,
        basis=exact_plan_basis,
    )

    # ── Result cache check (BEFORE any I/O) ───────────────────────────────
    # Plan key is built from request payload — no source I/O needed.
    _plan_key_early = exact_plan_hash

    _cached_early = _RESULT_CACHE.get(_plan_key_early)
    if _cached_early and (time.monotonic() - _cached_early.get("_ts", 0)) < _RESULT_CACHE_TTL:
        plan.append(f"Result cache HIT [{_plan_key_early[:8]}] — zero I/O")
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=_cached_early["result"],
            result_type=_cached_early["result_type"],
            confidence=_cached_early["confidence"],
            plan=plan,
            resolved_column=payload.metric_column,
            resolved_role=_cached_early.get("resolved_role", ""),
            resolved_source=_cached_early.get("resolved_source", payload.source_name),
            row_count=_cached_early["row_count"],
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=_cached_early.get("explanation", []),
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=schema_revision_exact,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=exact_plan_basis,
            plan_hash_override=exact_plan_hash,
            log_response=False,
        )

    if payload.dataset_id and visible_registry_entries is not None:
        registered_ex = {
            str(entry.get("name") or ""): entry for entry in visible_registry_entries
        }
    elif str(auth.get("role", "")).lower() == "owner" and payload.source_name:
        # Workspace/visibility-gated by-name lookup (was an unscoped cross-tenant read).
        owner_entry = get_visible_source_entry_by_name(org_id, payload.source_name, auth)
        registered_ex = (
            {str(owner_entry.get("name") or ""): owner_entry} if owner_entry is not None else {}
        )
    else:
        registered_ex = {
            str(entry.get("name") or ""): entry for entry in visible_registry_entries_loader()
        }
    for exact_source_name in _exact_query_required_sources(payload):
        if exact_source_name in registered_ex:
            continue
        extra_entry = get_visible_source_entry_by_name(org_id, exact_source_name, auth)
        if extra_entry is not None:
            registered_ex[exact_source_name] = extra_entry
    if payload.source_name not in registered_ex:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "source_not_found",
                    "message": f"Source '{payload.source_name}' not registered. "
                    f"Available: {sorted(registered_ex)}",
                }
            },
        )

    metric_entry_meta = registered_ex[payload.source_name]
    metric_source_id = str(metric_entry_meta["id"])
    metric_cached_source = _SOURCE_CACHE.get(metric_source_id)
    metric_schema_meta = _sreg_ex.get_source_meta(org_id, metric_source_id) or {}
    if (
        metric_cached_source
        and metric_cached_source.is_fresh()
        and metric_cached_source.graph_nodes
    ):
        metric_cached_source.touch()
        metric_nodes = metric_cached_source.graph_nodes
    else:
        metric_nodes = _graph_nodes_from_cached_meta(
            org_id=org_id,
            dataset_id=metric_source_id,
            schema_revision=str(metric_entry_meta.get("schema_revision", "") or ""),
            schema_meta=metric_schema_meta,
        )

    # Validate metric column exists
    if payload.metric_column not in metric_nodes:
        available = sorted(metric_nodes.keys())
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "column_not_found",
                    "message": (
                        f"Column '{payload.metric_column}' not in "
                        f"'{payload.source_name}'. Available columns: {available[:20]}"
                    ),
                    "suggestions": [
                        c for c in available if payload.metric_column.lower() in c.lower()
                    ][:5],
                }
            },
        )

    metric_node = metric_nodes[payload.metric_column]

    # ── Constraint enforcement ────────────────────────────────────────────────
    if payload.constraints.requires_derived and metric_node.role != "derived_measure":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "constraint_violated",
                    "constraint": "requires_derived",
                    "reason": (
                        f"Column '{payload.metric_column}' has role "
                        f"'{metric_node.role}', not 'derived_measure'."
                    ),
                    "suggestion": (
                        "Use a column with role=derived_measure. "
                        f"Available in {payload.source_name}: "
                    )
                    + str(
                        [c for c, n in metric_nodes.items() if n.role == "derived_measure"][:5]
                    ),
                }
            },
        )

    if payload.constraints.no_cross_source and payload.join_path and payload.join_path.edges:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "constraint_violated",
                    "constraint": "no_cross_source",
                    "reason": "Cross-source join requested but no_cross_source=true.",
                }
            },
        )

    direct_count_fast_path = (
        payload.aggregation == "count"
        and payload.group_column is None
        and payload.join_path is None
        and not (payload.filter and (payload.filter.time_filter or payload.filter.conditions))
    )
    if direct_count_fast_path:
        row_count_exact = int(
            metric_entry_meta.get("row_count") or metric_schema_meta.get("row_count") or 0
        )
        result_ex = float(row_count_exact)
        result_type_ex = "scalar"
        computed_confidence, col_conf, agg_conf = _compute_exact_confidence(
            metric_node,
            payload.aggregation,
            1.0,
        )
        if col_conf < payload.constraints.min_column_confidence:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "min_column_confidence",
                        "reason": (
                            f"Column '{payload.metric_column}' has "
                            f"column_confidence={col_conf:.2f}, which is below "
                            "min_column_confidence="
                            f"{payload.constraints.min_column_confidence:.2f}."
                        ),
                    }
                },
            )

        explanation = [
            f"Source: {payload.source_name}",
            f"Column: {payload.metric_column}  role={metric_node.role}"
            + (f"  formula={metric_node.formula}" if metric_node.formula else ""),
            f"Aggregation: {payload.aggregation}",
            f"Result: {result_type_ex}  = {result_ex}",
            "Confidence: "
            f"{computed_confidence:.3f} = col({col_conf:.2f}) × agg({agg_conf:.2f})",
        ]
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            oldest = min(_RESULT_CACHE.items(), key=lambda x: x[1].get("_ts", 0))
            del _RESULT_CACHE[oldest[0]]
        _RESULT_CACHE[exact_plan_hash] = {
            "result": result_ex,
            "result_type": result_type_ex,
            "row_count": row_count_exact,
            "confidence": computed_confidence,
            "resolved_role": metric_node.role,
            "resolved_source": payload.source_name,
            "explanation": explanation,
            "_ts": time.monotonic(),
        }
        plan.append(f"COUNT: {row_count_exact:,} rows (metadata fast path)")
        plan.append(f"Result cache STORED [{exact_plan_hash[:8]}]")
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=result_ex,
            result_type=result_type_ex,
            confidence=computed_confidence,
            plan=plan,
            resolved_column=payload.metric_column,
            resolved_role=metric_node.role,
            resolved_source=payload.source_name,
            row_count=row_count_exact,
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=schema_revision_exact,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=exact_plan_basis,
            source_set=[payload.source_name],
            join_path=[],
            planner_mode="exact_spec",
            plan_hash_override=exact_plan_hash,
        )

    def _load_exact(name: str) -> tuple[list[dict[str, Any]], dict[str, ColumnNode]]:
        """Load records + graph nodes for an exact-spec source.
        Three-tier cache: DataFrame cache → Parquet bytes cache → disk.
        """
        entry_meta = registered_ex.get(name)
        if not entry_meta:
            raise ValueError(f"Source '{name}' not registered")
        src_id = entry_meta["id"]

        # Tier 1: DataFrame cache — fastest, no deserialization
        cached_df = _df_cache_get(src_id)
        if cached_df is not None:
            plan.append(f"DF cache HIT [{name}] — DataFrame hot")
            nodes = _SOURCE_CACHE[src_id].graph_nodes if src_id in _SOURCE_CACHE else {}
            if not nodes:
                schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
                nodes = _graph_nodes_from_cached_meta(
                    org_id=org_id,
                    dataset_id=src_id,
                    schema_revision=str(entry_meta.get("schema_revision", "") or ""),
                    schema_meta=schema_meta,
                )
            return _df_cache_records(src_id, cached_df), nodes

        # Tier 2: Parquet bytes in memory — parse once, store DataFrame
        cached = _SOURCE_CACHE.get(src_id)
        if cached and cached.is_fresh():
            cached.touch()
            plan.append(f"Parquet cache HIT [{name}] — parsing bytes")
            buf = io.BytesIO(cached.parquet_bytes)
            initialize_pyarrow_parquet_runtime()
            df = pd.read_parquet(buf)
            _df_cache_put(src_id, df)
            cached_frame = _df_cache_get(src_id)
            assert cached_frame is not None
            return _df_cache_records(src_id, cached_frame), cached.graph_nodes

        # Tier 3: Disk fallback
        plan.append(f"Cache MISS [{name}] — reading from disk")
        parquet_bytes = _sreg_ex.get_source_parquet(org_id, src_id)
        if not parquet_bytes:
            raise ValueError(f"No data for source '{name}'")
        schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
        nodes = _graph_nodes_from_cached_meta(
            org_id=org_id,
            dataset_id=src_id,
            schema_revision=str(entry_meta.get("schema_revision", "") or ""),
            schema_meta=schema_meta,
        )
        buf = io.BytesIO(parquet_bytes)
        initialize_pyarrow_parquet_runtime()
        df = pd.read_parquet(buf)
        _df_cache_put(src_id, df)
        cached_frame = _df_cache_get(src_id)
        assert cached_frame is not None
        return _df_cache_records(src_id, cached_frame), nodes

    try:
        metric_records, metric_nodes = _load_exact(payload.source_name)
    except ValueError as _e:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "load_error", "message": str(_e)}},
        ) from _e

    try:
        resolved_filter_conditions_ex = _resolve_filter_conditions(
            source_name=payload.source_name,
            filter_spec=payload.filter,
            graph_nodes=metric_nodes,
            records=metric_records,
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

    metric_records, filter_plan_ex = _apply_filter_conditions(
        metric_records,
        resolved_filter_conditions_ex,
    )
    plan.extend(filter_plan_ex)

    # Validate group column if given
    group_col_ex: str | None = payload.group_column
    cross_ex = False
    join_confidence_ex: float = 1.0
    join_path_edges_ex: list[JoinEdgeSpec] = []
    join_group_source_ex: str | None = None
    join_edge_meta_ex: list[tuple[float, str]] = []
    join_records_ex: dict[str, list[dict[str, Any]]] = {payload.source_name: metric_records}

    if group_col_ex:
        if group_col_ex in metric_nodes:
            # Same source — no join needed
            pass
        elif payload.join_path:
            try:
                _reg_conns_ex = _sreg_ex.get_connections(org_id)
                (
                    join_path_edges_ex,
                    join_group_source_ex,
                    join_confidence_ex,
                    join_edge_meta_ex,
                ) = _resolve_join_path(
                    payload.source_name,
                    payload.join_path,
                    _reg_conns_ex,
                )
            except ValueError as _e:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "join_path_invalid",
                            "message": str(_e),
                        }
                    },
                ) from _e

            for source_name in [edge.right_source for edge in join_path_edges_ex]:
                if source_name in join_records_ex:
                    continue
                try:
                    records_ex, _nodes_ex = _load_exact(source_name)
                except ValueError as _e:
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "error": {
                                "code": "join_source_error",
                                "message": str(_e),
                            }
                        },
                    ) from _e
                join_records_ex[source_name] = records_ex

            if join_group_source_ex is None:
                join_group_source_ex = payload.source_name
            terminal_nodes_ex = (
                metric_nodes
                if join_group_source_ex == payload.source_name
                else _graph_nodes_from_cached_meta(
                    org_id=org_id,
                    dataset_id=registered_ex[join_group_source_ex]["id"],
                    schema_revision=str(
                        registered_ex[join_group_source_ex].get("schema_revision", "") or ""
                    ),
                    schema_meta=_sreg_ex.get_source_meta(
                        org_id,
                        registered_ex[join_group_source_ex]["id"],
                    )
                    or {},
                )
            )
            if group_col_ex not in terminal_nodes_ex:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "group_column_not_found",
                            "message": (
                                f"Column '{group_col_ex}' not found in terminal "
                                f"join source '{join_group_source_ex}'."
                            ),
                        }
                    },
                )

            for idx, (edge_ex, (edge_conf_ex, edge_card_ex)) in enumerate(
                zip(join_path_edges_ex, join_edge_meta_ex, strict=False), start=1
            ):
                plan.append(
                    f"Join hop {idx}: {edge_ex.left_source}.{edge_ex.left_key} = "
                    f"{edge_ex.right_source}.{edge_ex.right_key} "
                    f"(conf={edge_conf_ex:.2f}  card={edge_card_ex or '?'})"
                )
            cross_ex = bool(join_path_edges_ex)
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "group_column_not_found",
                        "message": (
                            f"Column '{group_col_ex}' not found in '{payload.source_name}'. "
                            "Cross-source grouping now requires join_path."
                        ),
                    }
                },
            )

    if payload.join_path and not group_col_ex:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "join_path_requires_group_column",
                    "message": "join_path requires group_column for exact-spec execution.",
                }
            },
        )

    # Time filter
    date_col_ex: str | None = find_time_column(
        payload.source_name, {payload.source_name: metric_nodes}
    )
    tr_ex = (
        time_range(payload.filter.time_filter)
        if payload.filter and payload.filter.time_filter
        else None
    )

    # Build a stable plan key — content-keyed sources are permanent so hash is safe
    _plan_key = exact_plan_hash

    _cached_result = _RESULT_CACHE.get(_plan_key)
    if _cached_result and (time.monotonic() - _cached_result.get("_ts", 0)) < _RESULT_CACHE_TTL:
        plan.append(f"Result cache HIT [{_plan_key[:8]}]")
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=_cached_result["result"],
            result_type=_cached_result["result_type"],
            confidence=_cached_result["confidence"],
            plan=plan,
            resolved_column=payload.metric_column,
            resolved_role=_cached_result.get("resolved_role", ""),
            resolved_source=_cached_result.get("resolved_source", payload.source_name),
            row_count=_cached_result["row_count"],
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=_cached_result.get("explanation", []),
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=schema_revision_exact,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=exact_plan_basis,
            source_set=(
                [payload.source_name] + [edge.right_source for edge in join_path_edges_ex]
            ),
            join_path=[edge.model_dump(mode="python") for edge in join_path_edges_ex],
            planner_mode="exact_spec",
            plan_hash_override=exact_plan_hash,
            log_response=False,
        )

    # Execute
    if cross_ex and join_group_source_ex and group_col_ex:
        result_ex, row_count_ex, exec_plan_ex = execute_join_path(
            records_by_source=join_records_ex,
            base_source=payload.source_name,
            metric_col=payload.metric_column,
            group_source=join_group_source_ex,
            group_col=group_col_ex,
            ordered_edges=join_path_edges_ex,
            agg=payload.aggregation,
            limit=payload.limit,
            order=payload.order,
            reject_on_ambiguity=payload.join_path.reject_on_ambiguity
            if payload.join_path
            else True,
        )
        resolved_src_ex = " ⋈ ".join(
            [payload.source_name] + [edge.right_source for edge in join_path_edges_ex]
        )
    else:
        result_ex, row_count_ex, exec_plan_ex = execute(
            records=metric_records,
            metric_col=payload.metric_column,
            agg=payload.aggregation,
            group_col=group_col_ex,
            date_col=date_col_ex,
            tr=tr_ex,
            limit=payload.limit,
            order=payload.order,
        )
        resolved_src_ex = payload.source_name

    plan.extend(exec_plan_ex)
    result_type_ex = (
        "table"
        if isinstance(result_ex, list)
        else ("scalar" if result_ex is not None else "none")
    )

    # Compute confidence
    computed_confidence, col_conf, agg_conf = _compute_exact_confidence(
        metric_node, payload.aggregation, join_confidence_ex
    )

    # Constraint: min_column_confidence check
    if col_conf < payload.constraints.min_column_confidence:
        from fastapi import HTTPException as _HTTPExc

        raise _HTTPExc(
            status_code=400,
            detail={
                "error": {
                    "code": "constraint_violated",
                    "constraint": "min_column_confidence",
                    "reason": (
                        f"Column '{payload.metric_column}' has "
                        f"column_confidence={col_conf:.2f}, which is below "
                        "min_column_confidence="
                        f"{payload.constraints.min_column_confidence:.2f}."
                    ),
                }
            },
        )

    # Build explanation
    exact_explanation: list[str] = [
        f"Source: {payload.source_name}",
        f"Column: {payload.metric_column}  role={metric_node.role}"
        + (f"  formula={metric_node.formula}" if metric_node.formula else ""),
        f"Aggregation: {payload.aggregation}",
    ]
    if group_col_ex:
        if cross_ex:
            hop_text = " -> ".join(
                f"{edge.left_source}.{edge.left_key}={edge.right_source}.{edge.right_key}"
                for edge in join_path_edges_ex
            )
            exact_explanation.append(
                f"Group by: {group_col_ex} from {join_group_source_ex} "
                f"via join_path ({hop_text})"
            )
        else:
            exact_explanation.append(f"Group by: {group_col_ex} (same source)")
    if tr_ex:
        exact_explanation.append(
            f"Time filter: {payload.filter.time_filter if payload.filter else '?'} → {tr_ex}"
        )
    exact_explanation.append(
        f"Result: {result_type_ex}"
        + (f"  {row_count_ex} groups" if result_type_ex == "table" else f"  = {result_ex}")
    )
    exact_explanation.append(
        f"Confidence: {computed_confidence:.3f} = col({col_conf:.2f}) × agg({agg_conf:.2f})"
        + (f" × join({join_confidence_ex:.2f})" if cross_ex else "")
    )

    # Store in result cache
    if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
        oldest = min(_RESULT_CACHE.items(), key=lambda x: x[1].get("_ts", 0))
        del _RESULT_CACHE[oldest[0]]

    _RESULT_CACHE[_plan_key] = {
        "result": result_ex,
        "result_type": result_type_ex,
        "row_count": row_count_ex,
        "confidence": computed_confidence,
        "resolved_role": metric_node.role,
        "resolved_source": resolved_src_ex,
        "explanation": exact_explanation,
        "_ts": time.monotonic(),
    }
    plan.append(f"Result cache STORED [{_plan_key[:8]}]")

    return _build_query_response(
        query_id=query_id,
        request_id=request_id,
        result=result_ex,
        result_type=result_type_ex,
        confidence=computed_confidence,
        plan=plan,
        resolved_column=payload.metric_column,
        resolved_role=metric_node.role,
        resolved_source=resolved_src_ex,
        row_count=row_count_ex,
        candidates=[],
        source_scores={},
        ambiguous=False,
        exact_spec=True,
        explanation=exact_explanation,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        decision_path="exact_spec",
        schema_revision=schema_revision_exact,
        validated=True,
        confidence_source="exact_spec_validation",
        plan_basis=exact_plan_basis,
        source_set=([payload.source_name] + [edge.right_source for edge in join_path_edges_ex]),
        join_path=[edge.model_dump(mode="python") for edge in join_path_edges_ex],
        planner_mode="exact_spec",
        plan_hash_override=exact_plan_hash,
    )


