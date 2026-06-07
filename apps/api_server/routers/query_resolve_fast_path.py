from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from apps.api_server.routers.query_contract import (
    CATEGORY,
    IDENTIFIER,
    TEXT,
    TIME,
    ResolvedPlan,
    ResolveRequest,
    ResolveResponse,
)
from apps.api_server.services.auth_service import AuthContext


def _resolve_entry_ready(entry: dict[str, Any]) -> bool:
    return bool(entry.get("schema_revision")) and bool(entry.get("decision_mode"))


def _resolve_scope_entries(
    *,
    org_id: str,
    auth: AuthContext,
    dataset_id: str | None,
    allow_org_scope: bool,
    request_id: str | None,
    http_error_fn: Callable[..., Exception],
) -> tuple[list[dict[str, Any]], str | None]:
    from apps.api_server.services import source_registry as _sreg_visible
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        get_visible_dataset_entry,
    )

    if dataset_id:
        dataset_entry = get_visible_dataset_entry(org_id, dataset_id, auth)
        if dataset_entry is None:
            raise http_error_fn(
                404,
                code="not_found",
                message=f"Dataset '{dataset_id}' not found.",
                request_id=request_id,
            )
        return [dataset_entry], dataset_id

    visible_entries = filter_visible_datasets(_sreg_visible.list_sources(org_id), auth)
    if allow_org_scope:
        return visible_entries, None
    if len(visible_entries) == 1:
        only_entry = visible_entries[0]
        return [only_entry], str(only_entry.get("id") or "")

    raise http_error_fn(
        422,
        code="dataset_scope_required",
        message=(
            "resolve requires dataset_id unless allow_org_scope=true "
            "or only one visible dataset exists."
        ),
        request_id=request_id,
    )


def _resolved_plan_current_schema_revision(
    *,
    org_id: str,
    resolved_plan: ResolvedPlan,
    dataset_id: str | None = None,
    visible_entries: list[dict[str, Any]] | None = None,
) -> str:
    from apps.api_server.services import source_registry as _sreg_resolved

    join_edges = getattr(resolved_plan.join_path, "edges", None)
    if join_edges:
        return _sreg_resolved.schema_revision(org_id)

    source_id = dataset_id
    if not source_id:
        matched_entry: dict[str, Any] | None = None
        if visible_entries is not None:
            matched_entry = next(
                (
                    entry
                    for entry in visible_entries
                    if str(entry.get("name") or "") == resolved_plan.source_name
                ),
                None,
            )
        else:
            # No workspace-filtered entry set supplied: do NOT resolve by name against the
            # org-wide registry (that would leak another workspace's per-source schema
            # revision). Fall through to the org-wide schema_revision below — coarser but
            # tenant-safe. Callers that pass visible_entries keep precise per-source resolution.
            matched_entry = None
        if matched_entry is not None:
            source_id = str(matched_entry.get("id") or "")

    if source_id:
        return _sreg_resolved.source_schema_revision(org_id, source_id)
    return _sreg_resolved.schema_revision(org_id)


def _dataset_candidate_payload(
    *,
    source_name: str,
    column_name: str,
    node: Any,
    confidence: float,
    notes: list[str],
    score_components: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "source": source_name,
        "column": column_name,
        "role": node.role,
        "magnitude": node.magnitude_class,
        "formula": node.formula,
        "confidence": round(confidence, 3),
        "score_components": score_components or {},
        "notes": list(dict.fromkeys(notes)),
    }


def resolve_single_dataset_fast_path(
    *,
    org_id: str,
    payload: ResolveRequest,
    dataset_entry: dict[str, Any],
    dataset_id: str,
    schema_meta: dict[str, Any] | None,
    cached_nodes: dict[str, Any] | None,
    schema_revision: str,
    metric_hint: str,
    combined_group_by: list[str],
    request_id: str | None,
    intent_signature: str,
    started_at: float,
    graph_nodes_from_meta: Callable[[dict[str, Any]], dict[str, Any]],
    normalize_hint_text: Callable[[str | None], str],
    stable_list: Callable[[list[str]], list[str]],
    find_exact_dataset_column_cached: Callable[..., dict[str, Any] | None],
    select_count_anchor_column: Callable[[dict[str, Any]], tuple[str, str] | None],
    decision_contract_flags: Callable[..., tuple[bool, bool, str | None]],
    resolve_metric_column_fn: Callable[..., tuple[str, str, float, list[dict[str, Any]]]],
    resolve_group_column_graph_fn: Callable[..., tuple[str, str, float]],
    build_resolve_response_fn: Callable[..., ResolveResponse],
    http_error_fn: Callable[..., Exception],
    max_resolve_candidates: int,
    resolve_budget_ms: float,
) -> ResolveResponse:
    source_name = str(dataset_entry.get("name", "") or "")
    plan = [
        f"Resolve scope: dataset={dataset_id}",
        "Planner mode: dataset_meta_fast_path",
    ]

    if not source_name or not isinstance(schema_meta, dict):
        return build_resolve_response_fn(
            resolved_plan=None,
            confidence=0.0,
            plan=plan + ["Dataset metadata missing for single-source resolve."],
            explanation=[],
            resolved_column="",
            resolved_role="",
            resolved_source=source_name,
            candidates=[],
            source_scores={source_name: 1.0} if source_name else {},
            latency_ms=round((time.monotonic() - started_at) * 1000, 1),
            schema_revision=schema_revision,
            validated=False,
            confidence_source="dataset_metadata_confidence",
            request_id=request_id,
            intent_signature=intent_signature,
            clarification_required=False,
            rejection_reason="schema_incomplete",
            source_set=[source_name] if source_name else [],
            join_path=[],
            planner_mode="dataset_meta_fast_path",
        )

    graph_nodes = cached_nodes or graph_nodes_from_meta(schema_meta)
    graph = {source_name: graph_nodes}
    nodes = graph.get(source_name, {})
    if not nodes:
        return build_resolve_response_fn(
            resolved_plan=None,
            confidence=0.0,
            plan=plan + ["Dataset schema graph is empty."],
            explanation=[],
            resolved_column="",
            resolved_role="",
            resolved_source=source_name,
            candidates=[],
            source_scores={source_name: 1.0},
            latency_ms=round((time.monotonic() - started_at) * 1000, 1),
            schema_revision=schema_revision,
            validated=False,
            confidence_source="dataset_metadata_confidence",
            request_id=request_id,
            intent_signature=intent_signature,
            clarification_required=False,
            rejection_reason="schema_incomplete",
            source_set=[source_name],
            join_path=[],
            planner_mode="dataset_meta_fast_path",
        )

    normalized_metric_hint = normalize_hint_text(metric_hint)
    normalized_group_hints = stable_list(combined_group_by)
    metric_candidates: list[dict[str, Any]] = []
    validation_notes: list[str] = []

    metric_col = ""
    metric_role = payload.metric.role
    metric_conf = 0.0

    if payload.aggregation == "count":
        count_anchor = select_count_anchor_column(schema_meta)
        if count_anchor is None:
            validation_notes.append("Dataset metadata is missing a COUNT anchor column.")
        else:
            metric_col, metric_role = count_anchor
            metric_conf = 1.0
            metric_node = nodes.get(metric_col)
            if metric_node is not None:
                metric_candidates = [
                    _dataset_candidate_payload(
                        source_name=source_name,
                        column_name=metric_col,
                        node=metric_node,
                        confidence=1.0,
                        notes=["count-anchor", "dataset-scope"],
                        score_components={"count_anchor": 1.0},
                    )
                ]
            plan.append(f"COUNT anchor fallback: {source_name}.{metric_col} ({metric_role})")
    else:
        exact_metric = find_exact_dataset_column_cached(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
            normalized_hint=normalized_metric_hint,
        )
        if exact_metric is not None:
            exact_metric_name = str(exact_metric.get("name", "") or "")
            exact_metric_node = nodes.get(exact_metric_name)
            if exact_metric_node is None:
                validation_notes.append(
                    "Dataset metadata column "
                    f"'{exact_metric_name}' is not available in the schema graph."
                )
            elif not exact_metric_node.is_numeric:
                validation_notes.append(
                    f"Dataset column '{exact_metric_name}' is not numeric "
                    "and cannot be used as a metric."
                )
            else:
                metric_col = exact_metric_name
                metric_role = exact_metric_node.role
                metric_conf = 1.0
                metric_candidates = [
                    _dataset_candidate_payload(
                        source_name=source_name,
                        column_name=metric_col,
                        node=exact_metric_node,
                        confidence=1.0,
                        notes=["exact-column-match", "dataset-scope"],
                        score_components={"exact_match": 1.0},
                    )
                ]
                plan.append(f"Metric exact match: {source_name}.{metric_col} ({metric_role})")
        if not metric_col:
            hint_tokens = set(re.findall(r"[a-z0-9]+", normalized_metric_hint.lower()))
            metric_src, resolved_metric_col, resolved_metric_conf, metric_candidates = (
                resolve_metric_column_fn(
                    payload.metric.role,
                    hint_tokens,
                    graph,
                    source_name,
                )
            )
            if metric_src and resolved_metric_col:
                metric_col = resolved_metric_col
                metric_conf = resolved_metric_conf
                metric_role = (
                    str(metric_candidates[0]["role"]) if metric_candidates else payload.metric.role
                )
                plan.append(f"Metric resolved: {metric_src}.{metric_col} ({metric_role})")
            else:
                validation_notes.append(
                    "No dataset-scoped metric column found for "
                    f"hint='{metric_hint or payload.metric.role}'."
                )

    group_col: str | None = None
    group_conf = 1.0
    if normalized_group_hints:
        exact_group = find_exact_dataset_column_cached(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
            normalized_hint=normalized_group_hints[0],
        )
        if exact_group is not None:
            exact_group_name = str(exact_group.get("name", "") or "")
            exact_group_node = nodes.get(exact_group_name)
            allowed_group_roles = {CATEGORY, TEXT, TIME, IDENTIFIER}
            if exact_group_node is None or exact_group_node.role not in allowed_group_roles:
                validation_notes.append(
                    f"Dataset column '{exact_group_name}' is not a valid group-by dimension."
                )
            else:
                group_col = exact_group_name
                group_conf = 1.0
                plan.append(f"Group exact match: {source_name}.{group_col}")
        if group_col is None:
            group_src, resolved_group_col, resolved_group_conf = resolve_group_column_graph_fn(
                normalized_group_hints,
                source_name,
                graph,
            )
            if group_src and resolved_group_col:
                group_col = resolved_group_col
                group_conf = resolved_group_conf
                plan.append(f"Group resolved: {group_src}.{group_col}")
            else:
                validation_notes.append(
                    "No dataset-scoped group column found for the requested dimension hint."
                )

    confidence = round(
        min(
            metric_conf,
            group_conf if normalized_group_hints else 1.0,
        ),
        3,
    )
    plan_error_text = "; ".join(validation_notes) or None
    validated, clarification_required, rejection_reason = decision_contract_flags(
        confidence,
        metric_candidates[:max_resolve_candidates],
        error_text=plan_error_text,
    )

    if (time.monotonic() - started_at) * 1000 > resolve_budget_ms:
        raise http_error_fn(
            503,
            code="resolve_budget_exceeded",
            message="resolve exceeded the bounded 500ms planning budget.",
            request_id=request_id,
        )

    explanation: list[str] = []
    if payload.include_explanation:
        explanation = [
            f"Metric hint: {metric_hint}",
            (
                f"Resolved metric: {source_name}.{metric_col}"
                if metric_col
                else "Resolved metric: none"
            ),
            f"Aggregation: {payload.aggregation}",
        ]
        if group_col:
            explanation.append(f"Group by: {source_name}.{group_col}")
        explanation.append(f"Confidence: {confidence:.3f}")

    resolved_plan: ResolvedPlan | None = None
    if validated and metric_col:
        resolved_plan = ResolvedPlan(
            source_name=source_name,
            metric_column=metric_col,
            aggregation=payload.aggregation,
            group_column=group_col,
            join_path=None,
            filter=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
            schema_revision=schema_revision,
        )

    return build_resolve_response_fn(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=explanation,
        resolved_column=metric_col,
        resolved_role=metric_role if metric_col else "",
        resolved_source=source_name,
        candidates=metric_candidates[:max_resolve_candidates],
        source_scores={source_name: 1.0},
        latency_ms=round((time.monotonic() - started_at) * 1000, 1),
        schema_revision=schema_revision,
        validated=resolved_plan is not None,
        confidence_source="dataset_metadata_confidence",
        request_id=request_id,
        intent_signature=intent_signature,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        source_set=[source_name],
        join_path=[],
        planner_mode="dataset_meta_fast_path",
    )


__all__ = [
    "_dataset_candidate_payload",
    "_resolve_entry_ready",
    "_resolve_scope_entries",
    "_resolved_plan_current_schema_revision",
    "resolve_single_dataset_fast_path",
]
