from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from apps.api_server.routers.query_contract import (
    JoinEdgeSpec,
    JoinPathSpec,
    ResolvedPlan,
    ResolveRequest,
    ResolveResponse,
)
from apps.api_server.services.auth_service import AuthContext


def _resolve_cache_key(*, org_id: str, scoped_dataset_id: str | None, signature: str) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "org": org_id,
                "scope": scoped_dataset_id or "__org__",
                "signature": signature,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:24]


def _empty_resolve_response(
    *,
    payload: ResolveRequest,
    request_id: str | None,
    scoped_dataset_id: str | None,
    schema_revision: str,
    started_at: float,
    intent_signature_payload_fn: Callable[..., dict[str, Any]],
    intent_signature_fn: Callable[[dict[str, Any]], str],
    build_resolve_response_fn: Callable[..., ResolveResponse],
) -> ResolveResponse:
    signature_payload = intent_signature_payload_fn(
        dataset_id=scoped_dataset_id,
        allow_org_scope=payload.allow_org_scope,
        metric_role=payload.metric.role,
        metric_hint=payload.metric.hint or "",
        group_by=payload.group_by,
        preferred_source=payload.preferred_source,
        aggregation=payload.aggregation,
        filter_spec=payload.filter,
        limit=payload.limit,
        order=payload.order,
        constraints=payload.constraints,
        raw_text=payload.raw_text,
        schema_revision=schema_revision,
    )
    signature = intent_signature_fn(signature_payload)
    return build_resolve_response_fn(
        resolved_plan=None,
        confidence=0.0,
        plan=["No ready registered sources found. Use POST /v1/sources/register first."],
        explanation=[],
        resolved_column="",
        resolved_role="",
        resolved_source="",
        candidates=[],
        source_scores={},
        latency_ms=round((time.monotonic() - started_at) * 1000, 1),
        schema_revision=schema_revision,
        validated=False,
        confidence_source="planner_query_confidence",
        request_id=request_id,
        intent_signature=signature,
        clarification_required=False,
        rejection_reason="schema_incomplete",
        source_set=[],
        join_path=[],
    )


def _resolve_metric_hints(
    *,
    payload: ResolveRequest,
    normalize_hint_text_fn: Callable[[str | None], str],
    weak_raw_text_intent_fn: Callable[[str | None], tuple[str, list[str]]],
    stable_list_fn: Callable[[list[str]], list[str]],
) -> tuple[str, list[str], str | None]:
    raw_metric_hint, raw_group_by = weak_raw_text_intent_fn(payload.raw_text)
    metric_hint = (
        normalize_hint_text_fn(payload.metric.hint)
        or raw_metric_hint
        or (payload.metric.role.replace("_", " "))
    )
    combined_group_by = payload.group_by or raw_group_by
    dim_hint = " ".join(stable_list_fn(combined_group_by)) or None
    return metric_hint, combined_group_by, dim_hint


def _planner_source_scores(qplan: Any, preferred_source: str | None) -> dict[str, float]:
    source_scores = {qplan.metric_src: round(qplan.metric_conf, 3)} if qplan.metric_src else {}
    if preferred_source and source_scores:
        source_scores[preferred_source] = max(
            source_scores.get(preferred_source, 0.0),
            source_scores.get(qplan.metric_src or "", 0.0),
        )
    return source_scores


def _planner_join_path_payload(
    *,
    qplan: Any,
    max_join_path_hops: int,
) -> list[dict[str, Any]]:
    return [
        {
            "left_source": hop.left_source,
            "left_key": hop.left_key,
            "right_source": hop.right_source,
            "right_key": hop.right_key,
            "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
            "cardinality": getattr(hop, "cardinality", None),
        }
        for hop in qplan.join_hops[:max_join_path_hops]
    ]


def _planner_explanation(
    *,
    payload: ResolveRequest,
    qplan: Any,
    metric_hint: str,
    confidence: float,
    max_join_path_hops: int,
) -> list[str]:
    if not payload.include_explanation:
        return []

    explanation = [
        f"Metric hint: {metric_hint}",
        (
            f"Resolved metric: {qplan.metric_src}.{qplan.metric_col}"
            if qplan.metric_src and qplan.metric_col
            else "Resolved metric: none"
        ),
        f"Aggregation: {payload.aggregation}",
    ]
    if qplan.group_col and qplan.group_src:
        explanation.append(f"Group by: {qplan.group_src}.{qplan.group_col}")
    if qplan.join_hops:
        explanation.append(
            "Join path: "
            + " -> ".join(
                f"{hop.left_source}.{hop.left_key}={hop.right_source}.{hop.right_key}"
                for hop in qplan.join_hops[:max_join_path_hops]
            )
        )
    explanation.append(f"Confidence: {confidence:.3f}")
    return explanation


def _resolved_plan_from_query_plan(
    *,
    payload: ResolveRequest,
    qplan: Any,
    schema_revision: str,
    max_join_path_hops: int,
) -> ResolvedPlan | None:
    if not (qplan.metric_src and qplan.metric_col):
        return None

    join_path_spec = None
    if qplan.join_hops:
        planner_path_has_fanout = any(
            str(getattr(hop, "cardinality", "") or "").lower()
            in {"one_to_many", "many_to_many", "1:n", "n:n"}
            for hop in qplan.join_hops[:max_join_path_hops]
        )
        join_path_spec = JoinPathSpec(
            base_source=qplan.metric_src,
            group_source=qplan.group_src or qplan.metric_src,
            edges=[
                JoinEdgeSpec(
                    left_source=hop.left_source,
                    right_source=hop.right_source,
                    left_key=hop.left_key,
                    right_key=hop.right_key,
                    min_confidence=round(
                        float(getattr(hop, "confidence", 0.0) or 0.0),
                        3,
                    ),
                    expected_cardinality=(str(getattr(hop, "cardinality", "") or "") or None),
                    allow_many_to_many=(
                        str(getattr(hop, "cardinality", "") or "").lower() == "many_to_many"
                    ),
                )
                for hop in qplan.join_hops[:max_join_path_hops]
            ],
            max_hops=payload.constraints.max_join_hops,
            min_path_confidence=round(
                float(
                    getattr(qplan, "path_confidence", 0.0)
                    or getattr(qplan, "join_conf", 0.0)
                    or 0.0
                ),
                3,
            ),
            reject_on_ambiguity=True,
            reject_on_fanout=not planner_path_has_fanout,
        )

    return ResolvedPlan(
        source_name=qplan.metric_src,
        metric_column=qplan.metric_col,
        aggregation=payload.aggregation,
        group_column=qplan.group_col,
        join_path=join_path_spec,
        filter=payload.filter,
        limit=payload.limit,
        order=payload.order,
        constraints=payload.constraints,
        schema_revision=schema_revision,
    )


def _apply_count_anchor_override(
    *,
    payload: ResolveRequest,
    scoped_entries: list[dict[str, Any]],
    qplan: Any,
    org_id: str,
    combined_group_by: list[str],
    get_source_meta_fn: Callable[[str, str], dict[str, Any] | None],
    select_count_anchor_column_fn: Callable[[dict[str, Any]], tuple[str, str] | None],
    plan: list[str],
) -> None:
    if payload.aggregation != "count" or not payload.dataset_id or combined_group_by:
        return

    dataset_entry = scoped_entries[0] if scoped_entries else None
    dataset_meta = get_source_meta_fn(org_id, str(payload.dataset_id))
    count_anchor = (
        select_count_anchor_column_fn(dataset_meta) if isinstance(dataset_meta, dict) else None
    )
    source_name = str(dataset_entry.get("name", "") if dataset_entry else "")
    if not count_anchor or not source_name:
        return

    anchor_col, anchor_role = count_anchor
    qplan.metric_src = source_name
    qplan.metric_col = anchor_col
    qplan.metric_role = anchor_role
    qplan.metric_conf = 1.0
    qplan.error = None
    qplan.steps.append(f"COUNT anchor: {source_name}.{anchor_col} ({anchor_role})")
    plan.append(qplan.steps[-1])


async def resolve_registered_intent(
    payload: ResolveRequest,
    *,
    auth: AuthContext,
    request_id: str | None,
    resolve_scope_entries_fn: Callable[..., tuple[list[dict[str, Any]], str | None]],
    resolve_entry_ready_fn: Callable[[dict[str, Any]], bool],
    schema_revision_fn: Callable[[str], str],
    source_schema_revision_fn: Callable[[str, str], str],
    get_source_meta_fn: Callable[[str, str], dict[str, Any] | None],
    normalize_hint_text_fn: Callable[[str | None], str],
    stable_list_fn: Callable[[list[str]], list[str]],
    weak_raw_text_intent_fn: Callable[[str | None], tuple[str, list[str]]],
    intent_signature_payload_fn: Callable[..., dict[str, Any]],
    intent_signature_fn: Callable[[dict[str, Any]], str],
    prune_resolve_cache_fn: Callable[[str, str], None],
    resolve_cache_get_fn: Callable[[str], dict[str, Any] | None],
    resolve_cache_put_fn: Callable[[str, dict[str, Any]], None],
    get_resolve_dataset_meta_fn: Callable[
        ...,
        Awaitable[tuple[dict[str, Any] | None, dict[str, Any] | None]],
    ],
    resolve_single_dataset_fast_path_fn: Callable[..., ResolveResponse],
    get_registry_planner_fn: Callable[..., Awaitable[tuple[Any, bool, str]]],
    run_cached_planner_method_fn: Callable[..., Awaitable[Any]],
    planner_query_confidence_fn: Callable[[Any], float],
    planner_metric_candidate_payloads_fn: Callable[..., list[dict[str, Any]]],
    planner_load_bearing_validation_notes_fn: Callable[[Any], list[str]],
    decision_contract_flags_fn: Callable[..., tuple[bool, bool, str | None]],
    build_resolve_response_fn: Callable[..., ResolveResponse],
    dedupe_source_values_fn: Callable[[list[str]], list[str]],
    resolved_plan_current_schema_revision_fn: Callable[..., str],
    select_count_anchor_column_fn: Callable[[dict[str, Any]], tuple[str, str] | None],
    http_error_fn: Callable[..., Exception],
    max_resolve_candidates: int,
    max_join_path_hops: int,
    resolve_budget_ms: float,
) -> ResolveResponse:
    started_at = time.monotonic()
    org_id = str(auth["org_id"])

    scoped_entries, scoped_dataset_id = resolve_scope_entries_fn(
        org_id=org_id,
        auth=auth,
        dataset_id=payload.dataset_id,
        allow_org_scope=payload.allow_org_scope,
        request_id=request_id,
    )
    ready_entries = [entry for entry in scoped_entries if resolve_entry_ready_fn(entry)]
    if payload.dataset_id and not ready_entries:
        raise http_error_fn(
            409,
            code="source_not_ready",
            message=f"Dataset '{payload.dataset_id}' is not ready for resolve.",
            request_id=request_id,
        )
    if not payload.dataset_id:
        scoped_entries = ready_entries
    if not scoped_entries:
        return _empty_resolve_response(
            payload=payload,
            request_id=request_id,
            scoped_dataset_id=scoped_dataset_id,
            schema_revision=schema_revision_fn(org_id),
            started_at=started_at,
            intent_signature_payload_fn=intent_signature_payload_fn,
            intent_signature_fn=intent_signature_fn,
            build_resolve_response_fn=build_resolve_response_fn,
        )

    single_dataset_fast_path = bool(payload.dataset_id and len(scoped_entries) == 1)
    if single_dataset_fast_path:
        schema_revision = source_schema_revision_fn(
            org_id,
            scoped_dataset_id or str(payload.dataset_id),
        )
    else:
        schema_revision = schema_revision_fn(org_id)
        prune_resolve_cache_fn(org_id, schema_revision)

    metric_hint, combined_group_by, dim_hint = _resolve_metric_hints(
        payload=payload,
        normalize_hint_text_fn=normalize_hint_text_fn,
        weak_raw_text_intent_fn=weak_raw_text_intent_fn,
        stable_list_fn=stable_list_fn,
    )
    signature_payload = intent_signature_payload_fn(
        dataset_id=scoped_dataset_id,
        allow_org_scope=payload.allow_org_scope,
        metric_role=payload.metric.role,
        metric_hint=metric_hint,
        group_by=combined_group_by,
        preferred_source=payload.preferred_source,
        aggregation=payload.aggregation,
        filter_spec=payload.filter,
        limit=payload.limit,
        order=payload.order,
        constraints=payload.constraints,
        raw_text=payload.raw_text,
        schema_revision=schema_revision,
    )
    signature = intent_signature_fn(signature_payload)
    resolve_cache_key = _resolve_cache_key(
        org_id=org_id,
        scoped_dataset_id=scoped_dataset_id,
        signature=signature,
    )

    cached = resolve_cache_get_fn(resolve_cache_key)
    if cached is not None:
        cached_plan = list(cached.get("plan", []))
        cached_plan.insert(0, f"Resolve cache HIT [{resolve_cache_key[:8]}]")
        return ResolveResponse(
            **{
                **cached["response"],
                "plan": cached_plan,
                "latency_ms": round((time.monotonic() - started_at) * 1000, 1),
                "request_id": request_id,
            }
        )

    if single_dataset_fast_path:
        dataset_meta, cached_nodes = await get_resolve_dataset_meta_fn(
            org_id=org_id,
            dataset_id=str(payload.dataset_id),
            schema_revision=schema_revision,
        )
        dataset_response = resolve_single_dataset_fast_path_fn(
            org_id=org_id,
            payload=payload,
            dataset_entry=scoped_entries[0],
            dataset_id=scoped_dataset_id or payload.dataset_id,
            schema_meta=dataset_meta,
            cached_nodes=cached_nodes,
            schema_revision=schema_revision,
            metric_hint=metric_hint,
            combined_group_by=combined_group_by,
            request_id=request_id,
            intent_signature=signature,
            started_at=started_at,
        )
        resolve_cache_put_fn(
            resolve_cache_key,
            {
                "org_id": org_id,
                "schema_revision": schema_revision,
                "response": dataset_response.model_dump(mode="python"),
                "plan": list(dataset_response.plan),
            },
        )
        return dataset_response

    planner, planner_cache_hit, schema_revision = await get_registry_planner_fn(
        org_id,
        llm_policy="never",
        auth=auth,
        visible_entries=scoped_entries,
    )
    plan = [
        (
            f"Resolve scope: dataset={scoped_dataset_id}"
            if scoped_dataset_id
            else f"Resolve scope: org_visible={len(scoped_entries)}"
        ),
        f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]",
    ]

    qplan = await run_cached_planner_method_fn(
        planner,
        "plan",
        metric_hint=metric_hint,
        dim_hint=dim_hint,
        agg=payload.aggregation,
        preferred_source=payload.preferred_source,
        max_join_hops=payload.constraints.max_join_hops,
    )
    plan.extend(qplan.steps)
    _apply_count_anchor_override(
        payload=payload,
        scoped_entries=scoped_entries,
        qplan=qplan,
        org_id=org_id,
        combined_group_by=combined_group_by,
        get_source_meta_fn=get_source_meta_fn,
        select_count_anchor_column_fn=select_count_anchor_column_fn,
        plan=plan,
    )

    confidence = planner_query_confidence_fn(qplan)
    metric_candidate_payloads = planner_metric_candidate_payloads_fn(
        plan=qplan,
        graph=planner.graph,
        metric_hint=metric_hint,
        target_role=qplan.metric_role or payload.metric.role,
        preferred_source=payload.preferred_source,
    )
    plan_error_text = (
        "; ".join(
            note
            for note in [qplan.error or "", *planner_load_bearing_validation_notes_fn(qplan)]
            if note
        )
        or None
    )
    validated, clarification_required, rejection_reason = decision_contract_flags_fn(
        confidence,
        metric_candidate_payloads[:max_resolve_candidates],
        error_text=plan_error_text,
    )
    source_scores = _planner_source_scores(qplan, payload.preferred_source)

    if (time.monotonic() - started_at) * 1000 > resolve_budget_ms:
        raise http_error_fn(
            503,
            code="resolve_budget_exceeded",
            message="resolve exceeded the bounded 500ms planning budget.",
            request_id=request_id,
        )

    join_path_payload = _planner_join_path_payload(
        qplan=qplan,
        max_join_path_hops=max_join_path_hops,
    )
    resolved_plan = None
    if validated:
        resolved_plan = _resolved_plan_from_query_plan(
            payload=payload,
            qplan=qplan,
            schema_revision=schema_revision,
            max_join_path_hops=max_join_path_hops,
        )
    response_schema_revision = schema_revision
    if resolved_plan is not None:
        response_schema_revision = resolved_plan_current_schema_revision_fn(
            org_id=org_id,
            resolved_plan=resolved_plan,
            dataset_id=scoped_dataset_id,
            visible_entries=scoped_entries,
        )
        if resolved_plan.schema_revision != response_schema_revision:
            resolved_plan = resolved_plan.model_copy(
                update={"schema_revision": response_schema_revision}
            )

    response = build_resolve_response_fn(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=_planner_explanation(
            payload=payload,
            qplan=qplan,
            metric_hint=metric_hint,
            confidence=confidence,
            max_join_path_hops=max_join_path_hops,
        ),
        resolved_column=qplan.metric_col or "",
        resolved_role=qplan.metric_role or "",
        resolved_source=qplan.metric_src or "",
        candidates=metric_candidate_payloads[:max_resolve_candidates],
        source_scores=source_scores,
        latency_ms=round((time.monotonic() - started_at) * 1000, 1),
        schema_revision=response_schema_revision,
        validated=resolved_plan is not None,
        confidence_source="planner_query_confidence",
        request_id=request_id,
        intent_signature=signature,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        source_set=dedupe_source_values_fn(
            [
                qplan.metric_src or "",
                qplan.group_src or "",
                *[hop.right_source for hop in qplan.join_hops[:max_join_path_hops]],
            ]
        ),
        join_path=join_path_payload,
        planner_mode="registry_planner",
    )

    resolve_cache_put_fn(
        resolve_cache_key,
        {
            "org_id": org_id,
            "schema_revision": schema_revision,
            "response": response.model_dump(mode="python"),
            "plan": list(plan),
        },
    )
    return response


__all__ = ["resolve_registered_intent"]
