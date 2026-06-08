from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.api_server.services.auto_planner_semantics import (
    _semantic_token_set,
    _source_token_set,
)


@dataclass
class DimensionState:
    group_src: str = ""
    group_col: str | None = None
    group_conf: float = 0.0
    steps: list[str] = field(default_factory=list)


@dataclass
class PlanSelection:
    metric_src: str
    metric_col: str
    metric_conf: float
    metric_role: str
    group_src: str = ""
    group_col: str | None = None
    group_conf: float = 0.0


@dataclass
class JoinState:
    join_key_metric: str | None = None
    join_key_group: str | None = None
    join_conf: float = 0.0
    join_cardinality: str = ""
    join_hops: list[Any] = field(default_factory=list)
    path_confidence: float = 0.0
    intermediate_sources: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    join_steps: list[str] = field(default_factory=list)
    plan_error: str | None = None


def resolve_dimension_state(
    planner: Any,
    *,
    dim_hint: str | None,
    metric_src: str,
    preferred_source: str | None,
) -> DimensionState:
    dimension_state = DimensionState()
    if not dim_hint:
        return dimension_state

    d_src, d_col, d_conf, d_steps = planner.resolve_dimension(
        dim_hint,
        preferred_source or metric_src,
    )
    dimension_state.steps.extend(d_steps)
    if not d_src or not d_col:
        return dimension_state

    dimension_state.group_src = d_src
    dimension_state.group_col = d_col
    dimension_state.group_conf = d_conf

    hint_tokens = _semantic_token_set(dim_hint)
    hinted_sources = {src for src in planner.graph if hint_tokens & _source_token_set(src)}
    if hinted_sources or dimension_state.group_src == metric_src:
        return dimension_state

    fb_src, fb_col, fb_score, fb_steps = planner._same_source_dimension_candidate(
        metric_src,
        dim_hint,
    )
    current_tokens = _semantic_token_set(dimension_state.group_col or "")
    fallback_tokens = _semantic_token_set(fb_col or "")
    same_named_dimension = bool(fallback_tokens and fallback_tokens == current_tokens)
    if (
        fb_src
        and fb_col
        and (
            same_named_dimension
            or fb_score >= 0.95
            or fb_score + 0.02 >= dimension_state.group_conf
        )
    ):
        dimension_state.group_src = fb_src
        dimension_state.group_col = fb_col
        dimension_state.group_conf = fb_score
        dimension_state.steps.extend(fb_steps)
    return dimension_state


def build_join_state(
    planner: Any,
    *,
    current_metric_src: str,
    current_group_src: str,
    current_group_col: str | None,
    dim_hint: str | None,
    mojo_ops: list[str],
    max_join_hops: int = 4,
) -> JoinState:
    join_state = JoinState()

    if dim_hint and not current_group_col:
        join_state.plan_error = f"No supported dimension found for hint '{dim_hint}'"
        join_state.validation_notes.append(join_state.plan_error)
        return join_state

    if current_group_col and current_group_src and current_group_src != current_metric_src:
        join_state.join_steps.append(
            "[join_detect] "
            f"dimension in {current_group_src} ≠ metric in {current_metric_src} "
            f"→ discovering join path"
        )
        if "join_detect" in planner.mojo_engines:
            mojo_ops.append("join_detect")

        (
            join_state.join_hops,
            join_state.path_confidence,
            join_state.validation_notes,
            join_error,
        ) = planner._search_join_path(
            current_metric_src,
            current_group_src,
            current_group_col,
            max_hops=max_join_hops,
        )
        join_state.intermediate_sources = [hop.right_source for hop in join_state.join_hops[:-1]]
        if join_state.join_hops:
            join_state.join_key_metric = join_state.join_hops[0].left_key
            join_state.join_key_group = join_state.join_hops[-1].right_key
            join_state.join_conf = join_state.path_confidence
            join_state.join_cardinality = (
                join_state.join_hops[-1].cardinality or join_state.join_hops[0].cardinality
            )
            for index, hop in enumerate(join_state.join_hops, start=1):
                join_state.join_steps.append(
                    f"[join_path] hop {index}: {hop.left_source}.{hop.left_key}"
                    f" ↔ {hop.right_source}.{hop.right_key}"
                    f"  conf={hop.confidence:.3f}  card={hop.cardinality or '?'}"
                )
            join_state.join_steps.append(
                "[join_path] "
                f"SELECTED {len(join_state.join_hops)} hop path  "
                f"conf={join_state.path_confidence:.3f}"
            )
            if join_error:
                join_state.plan_error = join_error
        else:
            join_state.join_steps.append(
                f"[join_path] no path found between {current_metric_src} and {current_group_src}"
            )
            join_state.plan_error = (
                f"No join path from '{current_metric_src}' to '{current_group_src}' "
                f"for dimension '{current_group_col}'"
            )
            join_state.validation_notes = list(
                dict.fromkeys(join_state.validation_notes + [join_state.plan_error])
            )
    elif current_group_col and current_group_src == current_metric_src:
        join_state.path_confidence = 1.0

    join_state.validation_notes = list(dict.fromkeys(join_state.validation_notes))
    return join_state


def prefer_same_source_metric_selection(
    planner: Any,
    *,
    selection: PlanSelection,
    join_state: JoinState,
    dim_hint: str | None,
    preferred_source: str | None,
    mojo_ops: list[str],
    max_join_hops: int = 4,
) -> tuple[PlanSelection, JoinState, list[str]]:
    if not dim_hint or not selection.group_src or selection.metric_src == selection.group_src:
        return selection, join_state, []
    if preferred_source != selection.group_src:
        return selection, join_state, []

    same_source_node = planner.graph.get(selection.group_src, {}).get(selection.metric_col)
    if same_source_node is None:
        return selection, join_state, []
    if not getattr(same_source_node, "is_numeric", False):
        return selection, join_state, []
    if float(getattr(same_source_node, "fill_rate", 1.0) or 0.0) < 0.02:
        return selection, join_state, []

    join_problem_reasons: list[str] = []
    join_threshold = max(float(getattr(planner, "_join_min_conf", 0.4) or 0.4), 0.35)
    if join_state.plan_error:
        join_problem_reasons.append("join_path_unavailable")
    if join_state.join_cardinality == "many_to_many":
        join_problem_reasons.append("many_to_many_join")
    if join_state.join_hops and join_state.path_confidence < join_threshold:
        join_problem_reasons.append(f"low_join_conf={join_state.path_confidence:.3f}")

    if not join_problem_reasons:
        return selection, join_state, []

    updated_metric_role = str(
        getattr(same_source_node, "role", selection.metric_role) or selection.metric_role
    )
    updated_selection = PlanSelection(
        metric_src=selection.group_src,
        metric_col=selection.metric_col,
        metric_conf=selection.metric_conf,
        metric_role=updated_metric_role,
        group_src=selection.group_src,
        group_col=selection.group_col,
        group_conf=selection.group_conf,
    )
    rebuilt_join_state = build_join_state(
        planner,
        current_metric_src=updated_selection.metric_src,
        current_group_src=updated_selection.group_src,
        current_group_col=updated_selection.group_col,
        dim_hint=dim_hint,
        mojo_ops=mojo_ops,
        max_join_hops=max_join_hops,
    )
    correction_steps = [
        "[metric/self_correct_same_source] "
        f"{selection.metric_src}.{selection.metric_col} → "
        f"{updated_selection.metric_src}.{updated_selection.metric_col}  "
        f"reason={','.join(join_problem_reasons)}"
    ]
    return updated_selection, rebuilt_join_state, correction_steps


def llm_review_decision(
    *,
    llm_policy: str,
    dim_hint: str | None,
    group_col: str | None,
    group_src: str,
    metric_src: str,
    metric_conf: float,
    group_conf: float,
    join_state: JoinState,
    join_min_confidence: float,
) -> tuple[bool, str]:
    if llm_policy == "never":
        return False, "policy=never"
    if llm_policy == "always":
        return True, "policy=always"
    if llm_policy != "auto":
        return False, f"policy={llm_policy}"
    if not dim_hint or not group_col or not group_src:
        return False, "no_dimension"

    if (
        group_src == metric_src
        and metric_conf >= 1.0
        and group_conf >= 0.9
        and not join_state.validation_notes
    ):
        return False, "confident_same_source"
    if any("ambiguous" in note for note in join_state.validation_notes):
        return True, "ambiguous_plan"
    if group_conf < 0.75:
        return True, "low_dimension_confidence"
    if group_src != metric_src:
        if not join_state.join_hops:
            return True, "missing_join_path"
        if join_state.join_cardinality == "many_to_many":
            return True, "many_to_many_join"
        if join_state.path_confidence < max(join_min_confidence, 0.65):
            return True, "low_join_confidence"
    return False, "confident_plan"


def apply_llm_review(
    planner: Any,
    *,
    metric_hint: str,
    dim_hint: str | None,
    agg: str,
    preferred_source: str | None,
    selection: PlanSelection,
    join_state: JoinState,
    review_reason: str,
    mojo_ops: list[str],
    max_join_hops: int = 4,
) -> tuple[PlanSelection, JoinState, list[str]]:
    review = planner._llm_confirm_plan(
        metric_hint=metric_hint,
        dim_hint=dim_hint,
        agg=agg,
        preferred_source=preferred_source,
        metric_src=selection.metric_src,
        metric_col=selection.metric_col,
        metric_conf=selection.metric_conf,
        metric_role=selection.metric_role,
        group_src=selection.group_src,
        group_col=selection.group_col,
        group_conf=selection.group_conf,
        join_state=join_state.__dict__,
        query_hints=planner._query_hints_by_src,
    )
    if not review:
        return selection, join_state, [f"[llm/skipped] {review_reason}"]

    reasoning = str(review.get("reasoning", "") or review_reason)
    group_override = review.get("group_col", selection.group_col)
    group_col = str(group_override) if group_override is not None else None
    updated_selection = PlanSelection(
        metric_src=str(review.get("metric_src", selection.metric_src) or selection.metric_src),
        metric_col=str(review.get("metric_col", selection.metric_col) or selection.metric_col),
        metric_conf=selection.metric_conf,
        metric_role=selection.metric_role,
        group_src=str(review.get("group_src", selection.group_src) or selection.group_src),
        group_col=group_col,
        group_conf=max(selection.group_conf, 1.0) if group_col else selection.group_conf,
    )
    metric_node = planner.graph.get(updated_selection.metric_src, {}).get(
        updated_selection.metric_col
    )
    if metric_node is not None:
        updated_selection.metric_role = metric_node.role

    rebuilt_join_state = build_join_state(
        planner,
        current_metric_src=updated_selection.metric_src,
        current_group_src=updated_selection.group_src,
        current_group_col=updated_selection.group_col,
        dim_hint=dim_hint,
        mojo_ops=mojo_ops,
        max_join_hops=max_join_hops,
    )
    review_steps = [f"[llm] {reasoning}", *rebuilt_join_state.join_steps]
    return updated_selection, rebuilt_join_state, review_steps


def build_query_plan(
    *,
    query_plan_cls: Any,
    selection: PlanSelection,
    agg: str,
    join_state: JoinState,
    mojo_ops: list[str],
    steps: list[str],
) -> Any:
    final_steps = list(steps)
    validation_notes = join_state.validation_notes
    for note in validation_notes:
        final_steps.append(f"[validation] {note}")
    return query_plan_cls(
        metric_src=selection.metric_src,
        metric_col=selection.metric_col,
        metric_conf=selection.metric_conf,
        metric_role=selection.metric_role,
        agg=agg,
        group_col=selection.group_col,
        group_src=selection.group_src if selection.group_col else None,
        group_conf=selection.group_conf,
        join_key_metric=join_state.join_key_metric,
        join_key_group=join_state.join_key_group,
        join_conf=join_state.join_conf,
        join_cardinality=join_state.join_cardinality,
        join_hops=join_state.join_hops,
        path_confidence=join_state.path_confidence,
        intermediate_sources=join_state.intermediate_sources,
        validation_notes=validation_notes,
        error=join_state.plan_error,
        mojo_ops=list(dict.fromkeys(mojo_ops)),
        steps=final_steps,
    )
