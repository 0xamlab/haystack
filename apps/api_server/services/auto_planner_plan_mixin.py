from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.api_server.services.auto_planner_execute import (
    execute_query_plan as _execute_query_plan_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    build_source_distinctiveness as _build_source_distinctiveness_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    find_join_keys as _find_join_keys_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    join_candidates_for_source as _join_candidates_for_source_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    join_key_distinctiveness as _join_key_distinctiveness_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    python_join_keys as _python_join_keys_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    rank_fraction as _rank_fraction_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    rebuild_adaptive_context as _rebuild_adaptive_context_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    sample_edge_evidence as _sample_edge_evidence_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    sample_group_edge_evidence as _sample_group_edge_evidence_impl,
)
from apps.api_server.services.auto_planner_join_evidence import (
    source_distinctiveness_distribution as _source_distinctiveness_distribution_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    direct_join_candidates as _direct_join_candidates_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    group_dimension_join_key_multiplier as _group_dimension_join_key_multiplier_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    join_candidate_effective_conf as _join_candidate_effective_conf_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    join_key_semantic_multiplier as _join_key_semantic_multiplier_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    normalize_join_candidate as _normalize_join_candidate_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    registry_join_candidates as _registry_join_candidates_impl,
)
from apps.api_server.services.auto_planner_join_paths import (
    search_join_path as _search_join_path_impl,
)
from apps.api_server.services.auto_planner_plan import (
    PlanSelection as _PlanSelection,
)
from apps.api_server.services.auto_planner_plan import (
    apply_llm_review as _apply_llm_review_impl,
)
from apps.api_server.services.auto_planner_plan import (
    build_join_state as _build_join_state_impl,
)
from apps.api_server.services.auto_planner_plan import (
    build_query_plan as _build_query_plan_impl,
)
from apps.api_server.services.auto_planner_plan import (
    llm_review_decision as _llm_review_decision_impl,
)
from apps.api_server.services.auto_planner_plan import (
    prefer_same_source_metric_selection as _prefer_same_source_metric_selection_impl,
)
from apps.api_server.services.auto_planner_plan import (
    resolve_dimension_state as _resolve_dimension_state_impl,
)
from apps.api_server.services.auto_planner_types import (
    AdaptiveSourceContext,
    JoinHop,
    QueryPlan,
)


class AutoPlannerPlanMixin:
    mojo_engines: list[str]
    _llm_policy: str
    _join_min_conf: float
    _plan_cache: dict[tuple[str, str | None, str, str | None, int], QueryPlan]
    _join_probe_cache: dict[tuple[str, str], list[dict[str, Any]]]
    _planner_logger: Any

    def resolve_metric(
        self,
        hint: str,
        preferred_source: str | None = None,
        agg: str = "sum",
    ) -> tuple[str, str, float, str, list[str]]:
        raise NotImplementedError

    def find_join_keys(
        self,
        src_a: str,
        src_b: str,
    ) -> list[dict[str, Any]]:
        return _find_join_keys_impl(
            self,
            src_a,
            src_b,
            python_join_keys_fn=self._python_join_keys,
            join_candidates_for_source_fn=self._join_candidates_for_source,
        )

    def _probe_join_keys(
        self,
        src_a: str,
        src_b: str,
    ) -> list[dict[str, Any]]:
        cache_key = (src_a, src_b)
        cached = self._join_probe_cache.get(cache_key)
        if cached is not None:
            return [dict(candidate) for candidate in cached]
        candidates = self._python_join_keys(src_a, src_b)
        self._join_probe_cache[cache_key] = [dict(candidate) for candidate in candidates]
        return [dict(candidate) for candidate in candidates]

    def _join_candidates_for_source(self, src: str) -> dict[str, dict[str, Any]]:
        return _join_candidates_for_source_impl(self, src)

    def _sample_edge_evidence(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
        sample_limit: int = 400,
    ) -> dict[str, float]:
        return _sample_edge_evidence_impl(
            self,
            left_source,
            right_source,
            left_key,
            right_key,
            sample_limit=sample_limit,
        )

    def _sample_group_edge_evidence(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
        group_col: str,
        sample_limit: int = 400,
    ) -> dict[str, float]:
        return _sample_group_edge_evidence_impl(
            self,
            left_source,
            right_source,
            left_key,
            right_key,
            group_col,
            sample_limit=sample_limit,
        )

    def _build_source_distinctiveness(
        self,
        source: str,
        *,
        join_only: bool,
    ) -> list[tuple[float, int]]:
        return _build_source_distinctiveness_impl(
            self,
            source,
            join_only=join_only,
        )

    def _rebuild_adaptive_context(self) -> None:
        _rebuild_adaptive_context_impl(
            self,
            adaptive_source_context_cls=AdaptiveSourceContext,
            build_source_distinctiveness_fn=lambda source, join_only: (
                self._build_source_distinctiveness(source, join_only=join_only)
            ),
        )

    def _source_distinctiveness_distribution(
        self,
        source: str,
        *,
        join_only: bool,
    ) -> list[tuple[float, int]]:
        return _source_distinctiveness_distribution_impl(
            self,
            source,
            join_only=join_only,
            rebuild_adaptive_context_fn=self._rebuild_adaptive_context,
        )

    @staticmethod
    def _rank_fraction(value: float, population: list[float]) -> float:
        return _rank_fraction_impl(value, population)

    def _join_key_distinctiveness(
        self,
        source: str,
        key: str,
    ) -> tuple[float, int, float]:
        return _join_key_distinctiveness_impl(
            self,
            source,
            key,
            source_distinctiveness_distribution_fn=lambda src, join_only: (
                self._source_distinctiveness_distribution(src, join_only=join_only)
            ),
            rank_fraction_fn=self._rank_fraction,
        )

    def _python_join_keys(self, src_a: str, src_b: str) -> list[dict[str, Any]]:
        return _python_join_keys_impl(self, src_a, src_b)

    @staticmethod
    def _plan_cache_key(
        metric_hint: str,
        dim_hint: str | None,
        agg: str,
        preferred_source: str | None,
        max_join_hops: int,
    ) -> tuple[str, str | None, str, str | None, int]:
        return (
            metric_hint.strip().lower(),
            (dim_hint or "").strip().lower() or None,
            agg.strip().lower(),
            preferred_source,
            int(max_join_hops),
        )

    @staticmethod
    def _clone_plan(plan: QueryPlan) -> QueryPlan:
        cloned = replace(plan)
        cloned.join_hops = [replace(hop) for hop in plan.join_hops]
        cloned.intermediate_sources = list(plan.intermediate_sources)
        cloned.validation_notes = list(plan.validation_notes)
        cloned.mojo_ops = list(plan.mojo_ops)
        cloned.steps = list(plan.steps)
        return cloned

    @staticmethod
    def _reverse_join_cardinality(cardinality: str) -> str:
        if cardinality == "one_to_many":
            return "many_to_one"
        if cardinality == "many_to_one":
            return "one_to_many"
        return cardinality

    @staticmethod
    def _cardinality_penalty(cardinality: str) -> float:
        if cardinality in {"", "one_to_one", "many_to_one"}:
            return 1.0
        if cardinality == "one_to_many":
            return 0.82
        if cardinality == "many_to_many":
            return 0.62
        return 0.90

    @staticmethod
    def _group_dimension_join_key_multiplier(
        group_col: str | None,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
    ) -> float:
        return _group_dimension_join_key_multiplier_impl(
            group_col,
            left_source,
            right_source,
            left_key,
            right_key,
        )

    def _join_key_semantic_multiplier(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
    ) -> tuple[float, bool]:
        return _join_key_semantic_multiplier_impl(
            self,
            left_source,
            right_source,
            left_key,
            right_key,
        )

    def _join_candidate_effective_conf(
        self,
        candidate: dict[str, Any],
        group_col: str | None = None,
    ) -> float:
        return _join_candidate_effective_conf_impl(
            self,
            candidate,
            group_col=group_col,
            cardinality_penalty_fn=self._cardinality_penalty,
            group_dimension_join_key_multiplier_fn=self._group_dimension_join_key_multiplier,
            join_key_semantic_multiplier_fn=self._join_key_semantic_multiplier,
        )

    def _normalize_join_candidate(
        self,
        left_source: str,
        right_source: str,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        return _normalize_join_candidate_impl(
            left_source,
            right_source,
            candidate,
            reverse_join_cardinality_fn=self._reverse_join_cardinality,
        )

    def _registry_join_candidates(
        self,
        left_source: str,
        right_source: str,
    ) -> list[dict[str, Any]]:
        return _registry_join_candidates_impl(
            self,
            left_source,
            right_source,
            reverse_join_cardinality_fn=self._reverse_join_cardinality,
        )

    def _direct_join_candidates(self, left_source: str, right_source: str) -> list[dict[str, Any]]:
        return _direct_join_candidates_impl(
            self,
            left_source,
            right_source,
            registry_join_candidates_fn=self._registry_join_candidates,
            normalize_join_candidate_fn=self._normalize_join_candidate,
            find_join_keys_fn=self.find_join_keys,
            probe_join_keys_fn=self._probe_join_keys,
        )

    def _search_join_path(
        self,
        metric_src: str,
        group_src: str,
        group_col: str | None = None,
        max_hops: int = 4,
    ) -> tuple[list[JoinHop], float, list[str], str | None]:
        return _search_join_path_impl(
            self,
            metric_src,
            group_src,
            group_col=group_col,
            max_hops=max_hops,
            direct_join_candidates_fn=self._direct_join_candidates,
            join_candidate_effective_conf_fn=self._join_candidate_effective_conf,
            join_hop_cls=JoinHop,
        )

    def plan(
        self,
        metric_hint: str,
        dim_hint: str | None = None,
        agg: str = "sum",
        preferred_source: str | None = None,
        max_join_hops: int = 4,
    ) -> QueryPlan:
        cache_key = self._plan_cache_key(
            metric_hint,
            dim_hint,
            agg,
            preferred_source,
            max_join_hops,
        )
        cached_plan = self._plan_cache.get(cache_key)
        if cached_plan:
            self._planner_logger.debug(
                "auto_planner_plan_cache_hit",
                metric=metric_hint,
                dim=dim_hint,
                agg=agg,
                preferred_source=preferred_source,
            )
            return self._clone_plan(cached_plan)

        all_steps: list[str] = []
        mojo_ops: list[str] = []

        metric_src, metric_col, metric_conf, metric_role, m_steps = self.resolve_metric(
            metric_hint,
            preferred_source,
            agg,
        )
        all_steps.extend(m_steps)
        if "column_match" in self.mojo_engines:
            mojo_ops.append("column_match")
        if "field_map" in self.mojo_engines:
            mojo_ops.append("field_map")

        if not metric_src:
            return QueryPlan(
                metric_src="",
                metric_col="",
                metric_conf=0.0,
                metric_role="",
                agg=agg,
                error=f"No metric column found for hint='{metric_hint}'",
                steps=all_steps,
                mojo_ops=mojo_ops,
            )

        dimension_state = _resolve_dimension_state_impl(
            self,
            dim_hint=dim_hint,
            metric_src=metric_src,
            preferred_source=preferred_source,
        )
        group_src = dimension_state.group_src
        group_col = dimension_state.group_col
        group_conf = dimension_state.group_conf
        all_steps.extend(dimension_state.steps)

        if "column_profile" in self.mojo_engines:
            mojo_ops.append("column_profile")
        if "relation_detect" in self.mojo_engines:
            mojo_ops.append("relation_detect")

        join_state = _build_join_state_impl(
            self,
            current_metric_src=metric_src,
            current_group_src=group_src,
            current_group_col=group_col,
            dim_hint=dim_hint,
            mojo_ops=mojo_ops,
            max_join_hops=max_join_hops,
        )
        all_steps.extend(join_state.join_steps)

        selection = _PlanSelection(
            metric_src=metric_src,
            metric_col=metric_col,
            metric_conf=metric_conf,
            metric_role=metric_role,
            group_src=group_src,
            group_col=group_col,
            group_conf=group_conf,
        )
        selection, join_state, correction_steps = _prefer_same_source_metric_selection_impl(
            self,
            selection=selection,
            join_state=join_state,
            dim_hint=dim_hint,
            preferred_source=preferred_source,
            mojo_ops=mojo_ops,
            max_join_hops=max_join_hops,
        )
        all_steps.extend(correction_steps)

        should_review, review_reason = _llm_review_decision_impl(
            llm_policy=self._llm_policy,
            dim_hint=dim_hint,
            group_col=selection.group_col,
            group_src=selection.group_src,
            metric_src=selection.metric_src,
            metric_conf=selection.metric_conf,
            group_conf=selection.group_conf,
            join_state=join_state,
            join_min_confidence=self._join_min_conf,
        )
        if should_review:
            selection, join_state, review_steps = _apply_llm_review_impl(
                self,
                metric_hint=metric_hint,
                dim_hint=dim_hint,
                agg=agg,
                preferred_source=preferred_source,
                selection=selection,
                join_state=join_state,
                review_reason=review_reason,
                mojo_ops=mojo_ops,
                max_join_hops=max_join_hops,
            )
            all_steps.extend(review_steps)
        else:
            all_steps.append(f"[llm/skipped] {review_reason}")

        plan: QueryPlan = _build_query_plan_impl(
            query_plan_cls=QueryPlan,
            selection=selection,
            agg=agg,
            join_state=join_state,
            mojo_ops=mojo_ops,
            steps=all_steps,
        )
        self._plan_cache[cache_key] = self._clone_plan(plan)
        return plan

    def execute_plan(
        self,
        qplan: QueryPlan,
        limit: int | None = None,
        order: str = "desc",
        time_filter: str | None = None,
    ) -> tuple[Any, int, list[str]]:
        return _execute_query_plan_impl(
            self,
            qplan=qplan,
            limit=limit,
            order=order,
            time_filter=time_filter,
        )
