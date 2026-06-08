from __future__ import annotations

from typing import Any

from apps.api_server.routers.query_contract import CATEGORY, IDENTIFIER, TEXT, TIME
from apps.api_server.services.auto_planner_dimensions import (
    apply_cardinality_filter as _apply_cardinality_filter_impl,
)
from apps.api_server.services.auto_planner_dimensions import (
    dimension_hint_words as _dimension_hint_words,
)
from apps.api_server.services.auto_planner_dimensions import (
    filter_initial_dimension_candidate as _filter_initial_dimension_candidate_impl,
)
from apps.api_server.services.auto_planner_dimensions import (
    resolve_preferred_exact_match as _resolve_preferred_exact_match_impl,
)
from apps.api_server.services.auto_planner_dimensions import (
    resolve_source_hint_match as _resolve_source_hint_match_impl,
)
from apps.api_server.services.auto_planner_dimensions import (
    same_source_dimension_candidate as _same_source_dimension_candidate_impl,
)
from apps.api_server.services.auto_planner_dimensions import (
    score_dimension_candidates as _score_dimension_candidates_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    field_map_hint as _field_map_hint_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    python_field_map as _python_field_map_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    resolve_from_query_hints as _resolve_from_query_hints_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    resolve_metric_column_match as _resolve_metric_column_match_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    resolve_metric_python_fallback as _resolve_metric_python_fallback_impl,
)
from apps.api_server.services.auto_planner_metrics import (
    resolve_metric_vector_short_circuit as _resolve_metric_vector_short_circuit_impl,
)


class AutoPlannerResolutionMixin:
    graph: dict[str, Any]
    mojo_engines: list[str]
    _query_hints_by_src: dict[str, list[dict[str, Any]]]
    _metric_resolution_cache: dict[
        tuple[str, str | None, str],
        tuple[str, str, float, str, list[str]],
    ]
    _dimension_resolution_cache: dict[
        tuple[str, str | None],
        tuple[str, str, float, list[str]],
    ]

    def _resolve_from_query_hints(
        self,
        hint: str,
        preferred_source: str | None,
        agg: str,
    ) -> tuple[str, str, float, str] | None:
        from apps.api_server.routers.query import _metric_concepts, _metric_tokens

        return _resolve_from_query_hints_impl(
            self,
            hint=hint,
            preferred_source=preferred_source,
            agg=agg,
            metric_tokens_fn=_metric_tokens,
            metric_concepts_fn=_metric_concepts,
        )

    def _field_map_hint(
        self,
        hint: str,
        preferred_source: str | None = None,
    ) -> dict[str, Any]:
        return _field_map_hint_impl(
            self,
            hint=hint,
            preferred_source=preferred_source,
            python_field_map_fn=self._python_field_map,
        )

    @staticmethod
    def _python_field_map(hint: str) -> dict[str, Any]:
        return _python_field_map_impl(hint)

    def resolve_metric(
        self,
        hint: str,
        preferred_source: str | None = None,
        agg: str = "sum",
    ) -> tuple[str, str, float, str, list[str]]:
        from apps.api_server.routers.query import (
            _metric_candidate_score,
            resolve_metric_column,
        )
        from apps.api_server.routers.query_contract import (
            BASE_MEASURE,
            DERIVED_MEASURE,
            METRIC,
            RATIO,
            UNIT_MEASURE,
        )

        cache_key = (hint.strip().lower(), preferred_source, agg.strip().lower())
        cached = self._metric_resolution_cache.get(cache_key)
        if cached is not None:
            src, col, conf, role, cached_steps = cached
            return src, col, conf, role, list(cached_steps)

        steps: list[str] = []
        if self._query_hints_by_src:
            registry_result = self._resolve_from_query_hints(hint, preferred_source, agg)
            if registry_result:
                r_src, r_col, r_conf, r_role = registry_result
                steps.append(
                    f"[query_hints/registry] '{hint}' → {r_src}.{r_col}  "
                    f"conf={r_conf:.3f}  role={r_role}"
                )
                result = (r_src, r_col, r_conf, r_role, list(steps))
                self._metric_resolution_cache[cache_key] = result
                return r_src, r_col, r_conf, r_role, list(steps)

        analysis = self._field_map_hint(hint, preferred_source)
        sem_type = analysis.get("semantic_type") or analysis.get("unit", "unknown")
        polarity = analysis.get("polarity", 1)
        dist = analysis.get("distribution", "lognormal")
        fm_engine = "field_map" if "field_map" in self.mojo_engines else "python_field_map"
        steps.append(
            f"[field_map/{fm_engine}] hint='{hint}' → "
            f"unit={analysis.get('unit', '?')} sem={sem_type} polarity={polarity} dist={dist}"
        )

        vector_result = _resolve_metric_vector_short_circuit_impl(
            self,
            hint=hint,
            preferred_source=preferred_source,
            sem_type=sem_type,
            steps=steps,
            derived_measure_role=DERIVED_MEASURE,
        )
        if vector_result is not None:
            vr_src, vr_col, vr_conf, vr_role = vector_result
            result = (vr_src, vr_col, vr_conf, vr_role, list(steps))
            self._metric_resolution_cache[cache_key] = result
            return vr_src, vr_col, vr_conf, vr_role, list(steps)

        column_match_result = _resolve_metric_column_match_impl(
            self,
            hint=hint,
            sem_type=sem_type,
            polarity=polarity,
            dist=dist,
            preferred_source=preferred_source,
            steps=steps,
            metric_role=METRIC,
            derived_measure_role=DERIVED_MEASURE,
            base_measure_role=BASE_MEASURE,
            unit_measure_role=UNIT_MEASURE,
            ratio_role=RATIO,
        )
        if column_match_result is not None:
            best_src, best_col, best_conf, best_role = column_match_result
            result = (best_src, best_col, best_conf, best_role, list(steps))
            self._metric_resolution_cache[cache_key] = result
            return best_src, best_col, best_conf, best_role, list(steps)

        src, col, conf, role, final_steps = _resolve_metric_python_fallback_impl(
            self,
            hint=hint,
            sem_type=sem_type,
            preferred_source=preferred_source,
            agg=agg,
            steps=steps,
            metric_role=METRIC,
            derived_measure_role=DERIVED_MEASURE,
            base_measure_role=BASE_MEASURE,
            unit_measure_role=UNIT_MEASURE,
            ratio_role=RATIO,
            resolve_metric_column_fn=resolve_metric_column,
            metric_candidate_score_fn=_metric_candidate_score,
        )
        result = (src, col, conf, role, list(final_steps))
        self._metric_resolution_cache[cache_key] = result
        return src, col, conf, role, list(final_steps)

    def resolve_dimension(
        self,
        hint: str,
        preferred_source: str | None = None,
        pref_bonus: float = 0.12,
    ) -> tuple[str, str, float, list[str]]:
        from apps.api_server.routers.query import resolve_group_column, resolve_group_column_graph

        cache_key = (hint.strip().lower(), preferred_source)
        cached = self._dimension_resolution_cache.get(cache_key)
        if cached is not None:
            src, col, score, cached_steps = cached
            return src, col, score, list(cached_steps)

        steps: list[str] = []
        hint_words, hint_token_set = _dimension_hint_words(hint)
        dim_hints = hint_words
        hinted_sources, source_hint_match = _resolve_source_hint_match_impl(
            self,
            hint_words=hint_words,
            hint_token_set=hint_token_set,
            category_role=CATEGORY,
            identifier_role=IDENTIFIER,
            text_role=TEXT,
            time_role=TIME,
        )
        if source_hint_match is not None:
            g_src, g_col, g_score, step_name = source_hint_match
            steps.append(
                f"[resolve_group/{step_name}] '{hint}' → {g_src}.{g_col}  score={g_score:.3f}"
            )
            result = (g_src, g_col, g_score, list(steps))
            self._dimension_resolution_cache[cache_key] = result
            return g_src, g_col, g_score, list(steps)

        pref_exact = _resolve_preferred_exact_match_impl(
            self,
            hint_words=hint_words,
            preferred_source=preferred_source,
            pref_bonus=pref_bonus,
            category_role=CATEGORY,
            identifier_role=IDENTIFIER,
            text_role=TEXT,
            time_role=TIME,
        )
        if pref_exact is not None:
            g_src, g_col, g_score = pref_exact
            steps.append(
                f"[resolve_group/preferred_exact] '{hint}' → {g_src}.{g_col}  score={g_score:.3f}"
            )
            result = (g_src, g_col, g_score, list(steps))
            self._dimension_resolution_cache[cache_key] = result
            return g_src, g_col, g_score, list(steps)

        g_src, g_col, g_score = resolve_group_column_graph(
            dim_hints, preferred_source or "", self.graph
        )

        if preferred_source and preferred_source in self.graph:
            p_col, p_score = resolve_group_column(dim_hints, preferred_source, self.graph)
            if p_col and p_score + pref_bonus >= g_score:
                g_src, g_col, g_score = preferred_source, p_col, p_score + pref_bonus

        g_src, g_col, g_score = self._apply_cardinality_filter(
            g_src, g_col, g_score, dim_hints, preferred_source, pref_bonus
        )
        g_src, g_col, g_score = _filter_initial_dimension_candidate_impl(
            self,
            src=g_src,
            col=g_col,
            score=g_score,
            hint_words=hint_words,
            hint_token_set=hint_token_set,
            hinted_sources=hinted_sources,
            steps=steps,
            time_role=TIME,
        )
        g_src, g_col, g_score = _score_dimension_candidates_impl(
            self,
            src=g_src,
            col=g_col,
            score=g_score,
            hint_words=hint_words,
            hint_token_set=hint_token_set,
            hinted_sources=hinted_sources,
            preferred_source=preferred_source,
            pref_bonus=pref_bonus,
            steps=steps,
            category_role=CATEGORY,
            identifier_role=IDENTIFIER,
            text_role=TEXT,
            time_role=TIME,
        )
        g_src, g_col, g_score = self._apply_cardinality_filter(
            g_src, g_col, g_score, dim_hints, preferred_source, pref_bonus
        )

        if g_src:
            steps.append(f"[resolve_group] '{hint}' → {g_src}.{g_col}  score={g_score:.3f}")
        else:
            steps.append(f"[resolve_group] '{hint}' → no match")

        result = (g_src, g_col, g_score, list(steps))
        self._dimension_resolution_cache[cache_key] = result
        return g_src, g_col, g_score, list(steps)

    def _apply_cardinality_filter(
        self,
        src: str,
        col: str,
        score: float,
        dim_hints: list[str],
        preferred_source: str | None,
        pref_bonus: float,
    ) -> tuple[str, str, float]:
        from apps.api_server.routers.query import resolve_group_column, resolve_group_column_graph

        return _apply_cardinality_filter_impl(
            self,
            src,
            col,
            score,
            dim_hints=dim_hints,
            preferred_source=preferred_source,
            pref_bonus=pref_bonus,
            resolve_group_column_fn=resolve_group_column,
            resolve_group_column_graph_fn=resolve_group_column_graph,
        )

    def _same_source_dimension_candidate(
        self,
        source: str,
        hint: str,
    ) -> tuple[str, str, float, list[str]]:
        return _same_source_dimension_candidate_impl(
            self,
            source,
            hint,
            category_role=CATEGORY,
            identifier_role=IDENTIFIER,
            text_role=TEXT,
            time_role=TIME,
        )
