"""Submodule _endpoints_resolve_query.py of apps.api_server.routers.query.

Extracted from apps/api_server/routers/query.py during modularization.
Items in this submodule are listed in /tmp/query_split_assignments.json.
"""
from __future__ import annotations
import math
import time
import uuid
from typing import Any, cast
from fastapi import Depends, Request
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers.data_map import _call_mojo_column_profile
from apps.api_server.routers.query_contract import (
    ALL_ROLES, DERIVED_MEASURE, QueryRequest, QueryResponse, ResolveRequest, ResolveResponse,
)
from apps.api_server.routers.query_response_helpers import _build_query_response
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.routers.query._cache_classes import _get_registry_planner, _load_profiled_source
from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta
from apps.api_server.routers.query._signatures import _detect_relations, _resolve_registered_intent
from apps.api_server.routers.query._endpoints_helpers_early import _apply_dataset_scope, _apply_legacy_planning_fallback, _apply_resolved_plan, _owner_resolved_plan_fast_path
from apps.api_server.routers.query._endpoints_helpers_exact import _run_exact_spec_path
from apps.api_server.routers.query._endpoints_helpers_paths import _ingest_and_profile_inline_sources, _run_registry_planner_hint_path
from apps.api_server.routers.query._endpoints_helpers_inline import _execute_inline_and_build_response, _resolve_inline_anchor_metric_group
from apps.api_server.routers.query._state import router  # shared APIRouter instance

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


# Helpers extracted from query_sources, split across multiple submodules so
# each helper file stays close to or under 1000 lines.
from apps.api_server.routers.query._endpoints_helpers_early import (  # noqa: E402
    _apply_dataset_scope,
    _apply_legacy_planning_fallback,
    _apply_resolved_plan,
    _owner_resolved_plan_fast_path,
)
from apps.api_server.routers.query._endpoints_helpers_exact import (  # noqa: E402
    _run_exact_spec_path,
)
from apps.api_server.routers.query._endpoints_helpers_paths import (  # noqa: E402
    _ingest_and_profile_inline_sources,
    _run_registry_planner_hint_path,
)
from apps.api_server.routers.query._endpoints_helpers_inline import (  # noqa: E402
    _execute_inline_and_build_response,
    _resolve_inline_anchor_metric_group,
)


@router.post(
    "/v1/resolve",
    response_model=ResolveResponse,
    summary="Resolve structured intent into an exact executable plan",
    description=(
        "**Bounded deterministic planner.**\n\n"
        "This endpoint resolves structured intent into an exact plan for `POST /v1/query`.\n"
        "It only uses registered-source metadata, join graph metadata, planner cache, and "
        "precomputed statistics. It does not scan datasets or execute queries.\n\n"
        "**Scope rules:**\n"
        "- Provide `dataset_id` for dataset-scoped planning, or\n"
        "- set `allow_org_scope=true` to plan across all visible datasets.\n\n"
        "**Deterministic guarantees:**\n"
        "- identical intent_signature + schema_revision + scope => identical output\n"
        "- ambiguity clarifies or rejects; it never expands search\n"
        "- no fallback to slower planning paths exists\n"
    ),
)
async def resolve_sources(
    payload: ResolveRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
) -> ResolveResponse:
    request_id = getattr(request.state, "request_id", None)
    return await _resolve_registered_intent(payload, auth=auth, request_id=request_id)

@router.post(
    "/v1/query",
    response_model=QueryResponse,
    summary="Execute a structured query — schema-free, zero domain assumptions",
    description=(
        "**Structured query execution engine.**\n\n"
        "This endpoint takes structured intent — produced by an LLM from the user's "
        "natural-language question. It does NOT accept raw text.\n\n"
        "**Separation of concerns:**\n"
        "- LLM: language → structured intent, ambiguity resolution, user interaction\n"
        "- Algenta: schema understanding, math relationships, fast execution, correctness\n\n"
        "**Role resolution:**\n"
        "1. Detect derived formulas across all numeric column triples (Mojo, ~100ms)\n"
        "2. Assign structural roles: derived_measure, base_measure, unit_measure…\n"
        "3. Match requested role → best column\n"
        "4. Execute aggregation, return result + all candidates for LLM disambiguation\n\n"
        "**Ambiguity handling:**\n"
        "If confidence < 0.7, check `candidates` — multiple columns may match the role. "
        "The LLM can present options to the user or pick the most contextually appropriate one."
    ),
)
async def query_sources(
    payload: QueryRequest,
    request: Request = cast(Request, None),
    auth: AuthContext = Depends(get_current_org),
) -> QueryResponse:
    t0 = time.monotonic()
    query_id = str(uuid.uuid4())
    plan: list[str] = []
    org_id = str(auth["org_id"])
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    from apps.api_server.services import source_registry as _sreg_visible
    from apps.api_server.services.data_visibility import filter_visible_datasets

    visible_registry_entries: list[dict[str, Any]] | None = None
    resolved_plan_schema_revision: str | None = None

    def _visible_registry_entries() -> list[dict[str, Any]]:
        nonlocal visible_registry_entries
        if visible_registry_entries is None:
            visible_registry_entries = filter_visible_datasets(
                _sreg_visible.list_sources(org_id),
                auth,
            )
        return visible_registry_entries

    # ── Owner-only resolved_plan + result-cache fast path ─────────────────
    early, owner_schema_revision = _owner_resolved_plan_fast_path(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
    )
    if early is not None:
        return early
    if owner_schema_revision is not None:
        resolved_plan_schema_revision = owner_schema_revision

    # ── Dataset scope (mutates payload / seeds visible_registry_entries) ──
    scoped = _apply_dataset_scope(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        plan=plan,
    )
    if scoped is not None:
        visible_registry_entries = scoped

    # ── Resolved plan overlay ─────────────────────────────────────────────
    revision = _apply_resolved_plan(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        plan=plan,
        visible_registry_entries_loader=_visible_registry_entries,
    )
    if revision is not None:
        resolved_plan_schema_revision = revision

    # ── Legacy query-planning compatibility shim ──────────────────────────
    legacy_response = await _apply_legacy_planning_fallback(
        payload=payload,
        auth=auth,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
    )
    if legacy_response is not None:
        return legacy_response

    # ══════════════════════════════════════════════════════════════════════
    # EXACT-SPEC PATH — LLM supplied source_name + metric_column explicitly.
    # Mojo verifies and executes: no source resolver, no column resolver,
    # no semantic guessing. This is the correct production path.
    # ══════════════════════════════════════════════════════════════════════
    if payload.source_name and payload.metric_column:
        return _run_exact_spec_path(
            payload=payload,
            auth=auth,
            org_id=org_id,
            request_id=request_id,
            query_id=query_id,
            plan=plan,
            t0=t0,
            visible_registry_entries=visible_registry_entries,
            resolved_plan_schema_revision=resolved_plan_schema_revision,
            visible_registry_entries_loader=_visible_registry_entries,
        )

    # ══════════════════════════════════════════════════════════════════════
    # HINT PATH (fallback) — LLM did not supply exact column names.
    # Source resolver + column resolver run. Result has ambiguous flag.
    # Migrate to exact-spec once schema is known.
    # ══════════════════════════════════════════════════════════════════════

    # Validate role
    target_role = payload.metric.role
    if target_role not in ALL_ROLES:
        target_role = DERIVED_MEASURE
        plan.append(f"Unknown role '{payload.metric.role}' — defaulting to derived_measure")

    plan.append(
        f"Request: agg={payload.aggregation}  role={target_role}  "
        f"group_by={payload.group_by}  limit={payload.limit}  "
        f"time={payload.filter.time_filter if payload.filter else None}"
    )

    if not payload.sources:
        return await _run_registry_planner_hint_path(
            payload=payload,
            auth=auth,
            org_id=org_id,
            request_id=request_id,
            query_id=query_id,
            plan=plan,
            t0=t0,
            target_role=target_role,
            visible_registry_entries_loader=_visible_registry_entries,
        )

    # ── Load + profile all inline sources (cache-aware) ───────────────────
    (
        cache_entries,
        cache_hits,
        parsed_tables,
        profiles,
        _reg_connections,
    ) = await _ingest_and_profile_inline_sources(
        payload=payload,
        org_id=org_id,
        plan=plan,
        request_id=request_id,
    )

    # ── Inline-graph anchor / metric / group resolution ───────────────────
    (
        anchor_response,
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
    ) = await _resolve_inline_anchor_metric_group(
        payload=payload,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
        target_role=target_role,
        cache_entries=cache_entries,
        cache_hits=cache_hits,
    )
    if anchor_response is not None:
        return anchor_response

    # ── Final execution + response assembly ───────────────────────────────
    return _execute_inline_and_build_response(
        payload=payload,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
        graph=graph,
        cache_entries=cache_entries,
        parsed_tables=parsed_tables,
        _reg_connections=_reg_connections,
        src_name=src_name,
        metric_col=metric_col,
        metric_node=metric_node,
        metric_conf=metric_conf,
        all_candidates=all_candidates,
        all_src_scores=all_src_scores,
        ambiguous=ambiguous,
        group_col=group_col,
        group_src=group_src,
        decision_confidence=decision_confidence,
        schema_revision_inline=schema_revision_inline,
    )
