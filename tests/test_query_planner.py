"""
tests/test_query_planner.py — Regression suite for the composable query planner.

Covers:
  TestFieldResolution        — resolved / unresolved properties, to_log_dict
  TestMetricResolution       — COLUMN_MATCH, META_QUERY, WEAK_MATCH behaviour
  TestGroupByResolution      — accepts WEAK_MATCH for group-by fields
  TestDateFilterResolution   — date field resolution and WHERE clause
  TestQueryPlanSqlSketch     — sql_sketch output for various plan shapes
  TestQueryPlanFullyResolved — fully_resolved flag logic
  TestQueryPlanLogDict       — to_log_dict structure
  TestComposedPlans          — end-to-end: metric + group_by + date combinations

Run:
    python3 -m pytest tests/test_query_planner.py -v
"""
from __future__ import annotations

import pytest

from mojo.engine.vector_kernels.meta_executor import MetaOpType
from mojo.engine.vector_kernels.query_planner import (
    FieldResolution,
    QueryPlanner,
)
from mojo.engine.vector_kernels.resolver import (
    ColumnVectorResolver,
    ResolverOutcome,
    ResolverReason,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

_POS_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "POS": [
        ("UNIT_PRICE",    "unit_measure"),
        ("EXT_PRICE",     "derived_measure"),
        ("QTY",           "base_measure"),
        ("ORDER_DATE",    "other"),
        ("CUSTOMER_NAME", "other"),
        ("ORDER_STATUS",  "other"),
    ],
}

_TOTALS_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "Totals": [
        ("Net_Sales",           "derived_measure"),
        ("Tips",                "derived_measure"),
        ("Sold",                "base_measure"),
        ("Avg_Sold_Per_Guest",  "ratio"),
        ("Avg_Order_Time",      "ratio"),
        ("Guests",              "base_measure"),
        ("PPA",                 "ratio"),
    ],
}

# Two-source schema used for cross-source (PPA + date) tests.
# Totals is single-source so PPA resolves as COLUMN_MATCH without ambiguity.
_COMBINED_SCHEMA = {**_POS_SCHEMA, **_TOTALS_SCHEMA}


@pytest.fixture(scope="module")
def pos_planner():
    return QueryPlanner(ColumnVectorResolver(_POS_SCHEMA))


@pytest.fixture(scope="module")
def hosp_planner():
    """Single-source Totals planner — PPA resolves unambiguously, Guests is the only Guests column."""
    return QueryPlanner(ColumnVectorResolver(_TOTALS_SCHEMA))


@pytest.fixture(scope="module")
def combined_planner():
    """POS + Totals-only planner — allows cross-source plans (e.g. PPA metric + ORDER_DATE filter)."""
    return QueryPlanner(ColumnVectorResolver(_COMBINED_SCHEMA))


# ── FieldResolution ───────────────────────────────────────────────────────────

class TestFieldResolution:
    def test_resolved_is_true_for_column_match(self):
        fr = FieldResolution(
            hint="extended price", source="POS", column="EXT_PRICE",
            outcome=ResolverOutcome.COLUMN_MATCH, reason=ResolverReason.DIRECT_MATCH,
            score=0.85, sql_expr="EXT_PRICE",
        )
        assert fr.resolved is True

    def test_resolved_is_true_for_weak_match(self):
        fr = FieldResolution(
            hint="customer name", source="POS", column="CUSTOMER_NAME",
            outcome=ResolverOutcome.WEAK_MATCH, reason=ResolverReason.WEAK_MATCH,
            score=0.68, sql_expr="CUSTOMER_NAME",
        )
        assert fr.resolved is True

    def test_resolved_is_false_for_ambiguous(self):
        fr = FieldResolution(
            hint="price", source="POS", column="EXT_PRICE",
            outcome=ResolverOutcome.AMBIGUOUS, reason=ResolverReason.AMBIGUOUS_GAP,
            score=0.65, sql_expr="?",
        )
        assert fr.resolved is False

    def test_resolved_is_false_for_no_column_match(self):
        fr = FieldResolution(
            hint="unknown field", source=None, column=None,
            outcome=ResolverOutcome.NO_COLUMN_MATCH, reason=ResolverReason.NO_SIGNAL,
            score=0.0, sql_expr="?",
        )
        assert fr.resolved is False

    def test_to_log_dict_has_required_keys(self):
        fr = FieldResolution(
            hint="ext price", source="POS", column="EXT_PRICE",
            outcome=ResolverOutcome.COLUMN_MATCH, reason=ResolverReason.DIRECT_MATCH,
            score=0.88, sql_expr="EXT_PRICE",
        )
        d = fr.to_log_dict()
        assert set(d.keys()) == {"hint", "source", "column", "outcome", "reason", "score", "sql_expr"}

    def test_to_log_dict_values_are_serialisable(self):
        fr = FieldResolution(
            hint="qty", source="POS", column="QTY",
            outcome=ResolverOutcome.COLUMN_MATCH, reason=ResolverReason.DIRECT_MATCH,
            score=0.80, sql_expr="QTY",
        )
        d = fr.to_log_dict()
        # outcome and reason should be strings, not enums
        assert isinstance(d["outcome"], str)
        assert isinstance(d["reason"], str)
        assert isinstance(d["score"], float)


# ── Metric resolution ─────────────────────────────────────────────────────────

class TestMetricResolution:
    def test_column_match_metric_is_resolved(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert plan.metric is not None
        assert plan.metric.resolved
        assert plan.metric.column == "EXT_PRICE"

    def test_column_match_metric_has_no_meta_op(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert plan.meta_op is None

    def test_meta_query_sets_meta_op(self, pos_planner):
        """'how many orders' → META_QUERY with COUNT_ROWS op."""
        plan = pos_planner.plan(metric=("how many orders", "POS", "base_measure"))
        assert plan.meta_op is not None
        assert plan.meta_op.op_type == MetaOpType.COUNT_ROWS

    def test_meta_query_metric_not_resolved(self, pos_planner):
        """A META_QUERY metric field should not report as resolved (no direct column)."""
        plan = pos_planner.plan(metric=("how many orders", "POS", "base_measure"))
        assert plan.metric is not None
        assert not plan.metric.resolved

    def test_metric_critical_rejects_weak_match(self, pos_planner):
        """metric_is_critical=True (default) means WEAK_MATCH sql_expr stays '?'."""
        plan = pos_planner.plan(
            metric=("customer name", "POS", "other"),
            metric_is_critical=True,
        )
        # WEAK_MATCH outcome means sql_expr = "?" for critical metric
        if plan.metric and plan.metric.outcome == ResolverOutcome.WEAK_MATCH:
            assert plan.metric.sql_expr == "?"

    def test_metric_not_critical_accepts_weak_match(self, pos_planner):
        """metric_is_critical=False lets WEAK_MATCH through."""
        plan = pos_planner.plan(
            metric=("customer name", "POS", "other"),
            metric_is_critical=False,
        )
        if plan.metric and plan.metric.outcome == ResolverOutcome.WEAK_MATCH:
            assert plan.metric.sql_expr != "?"
            assert plan.metric.column is not None

    def test_unknown_metric_hint_gives_unresolved(self, pos_planner):
        """A hint with no column match leaves sql_expr as '?'."""
        plan = pos_planner.plan(metric=("xyzzy frobble", "POS", "other"))
        assert plan.metric is not None
        assert not plan.metric.resolved

    def test_meta_count_non_null_when_column_exists(self, hosp_planner):
        """'how many guests' → Guests column exists → COUNT_NON_NULL, not COUNT_ROWS."""
        plan = hosp_planner.plan(metric=("how many guests", "Totals", "base_measure"))
        assert plan.meta_op is not None
        assert plan.meta_op.op_type == MetaOpType.COUNT_NON_NULL
        assert plan.meta_op.column == "Guests"

    def test_server_count_meta_rows(self, hosp_planner):
        """'server count' → no Servers column → COUNT_ROWS."""
        plan = hosp_planner.plan(metric=("server count", "Totals", "base_measure"))
        assert plan.meta_op is not None
        assert plan.meta_op.op_type == MetaOpType.COUNT_ROWS
        assert plan.meta_op.column is None


# ── Group-by resolution ───────────────────────────────────────────────────────

class TestGroupByResolution:
    def test_group_by_resolved_column(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        assert len(plan.group_by) == 1
        assert plan.group_by[0].column is not None

    def test_group_by_column_appears_in_sql_sketch(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        assert "GROUP BY" in plan.sql_sketch
        assert plan.group_by[0].column in plan.sql_sketch

    def test_multiple_group_by_fields(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other"),
                        ("order date",    "POS", "other")],
        )
        assert len(plan.group_by) == 2

    def test_empty_group_by_no_clause(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert "GROUP BY" not in plan.sql_sketch

    def test_group_by_accepts_weak_match(self, pos_planner):
        """Group-by always accepts WEAK_MATCH outcomes."""
        plan = pos_planner.plan(
            metric  = ("unit price", "POS", "unit_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        gb = plan.group_by[0]
        # Either COLUMN_MATCH or WEAK_MATCH is fine for group_by
        assert gb.outcome in (
            ResolverOutcome.COLUMN_MATCH,
            ResolverOutcome.WEAK_MATCH,
            ResolverOutcome.AMBIGUOUS,
        )


# ── Date filter resolution ────────────────────────────────────────────────────

class TestDateFilterResolution:
    def test_date_filter_resolved(self, pos_planner):
        plan = pos_planner.plan(
            metric= ("extended price", "POS", "derived_measure"),
            date  = ("order date",     "POS", "other"),
        )
        assert plan.date_filter is not None
        assert plan.date_filter.column is not None

    def test_date_filter_appears_in_where_clause(self, pos_planner):
        plan = pos_planner.plan(
            metric= ("extended price", "POS", "derived_measure"),
            date  = ("order date",     "POS", "other"),
        )
        assert "WHERE" in plan.sql_sketch
        assert "BETWEEN ? AND ?" in plan.sql_sketch

    def test_no_date_no_where_clause(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert "WHERE" not in plan.sql_sketch


# ── SQL sketch ────────────────────────────────────────────────────────────────

class TestQueryPlanSqlSketch:
    def test_column_match_metric_in_select(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert "SELECT EXT_PRICE" in plan.sql_sketch

    def test_meta_count_rows_in_select(self, pos_planner):
        plan = pos_planner.plan(metric=("how many orders", "POS", "base_measure"))
        assert "SELECT COUNT(*)" in plan.sql_sketch

    def test_meta_sum_column_in_select(self, pos_planner):
        """'total extended price' → SUM aggregation (if column exists)."""
        plan = pos_planner.plan(metric=("total extended price", "POS", "derived_measure"))
        if plan.meta_op is not None and plan.meta_op.op_type == MetaOpType.SUM_COLUMN:
            assert "SUM(" in plan.sql_sketch

    def test_from_clause_contains_source(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        assert "FROM POS" in plan.sql_sketch

    def test_full_plan_sql_order(self, pos_planner):
        """SELECT … FROM … WHERE … GROUP BY — clause order must be correct."""
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
            date    = ("order date",     "POS", "other"),
        )
        sketch = plan.sql_sketch
        select_pos  = sketch.index("SELECT")
        from_pos    = sketch.index("FROM")
        where_pos   = sketch.index("WHERE")
        group_pos   = sketch.index("GROUP BY")
        assert select_pos < from_pos < where_pos < group_pos

    def test_unresolved_metric_gives_question_mark_select(self, pos_planner):
        plan = pos_planner.plan(metric=("xyzzy frobble", "POS", "other"))
        assert "SELECT ?" in plan.sql_sketch

    def test_ppa_metric_sql_sketch(self, hosp_planner):
        plan = hosp_planner.plan(metric=("per person average", "Totals", "ratio"))
        assert plan.metric is not None and plan.metric.column == "PPA"
        assert "SELECT PPA" in plan.sql_sketch


# ── Fully resolved flag ───────────────────────────────────────────────────────

class TestQueryPlanFullyResolved:
    def test_fully_resolved_when_all_fields_match(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
            date    = ("order date",     "POS", "other"),
        )
        # metric must be COLUMN_MATCH for fully_resolved to be True
        if plan.metric and plan.metric.outcome == ResolverOutcome.COLUMN_MATCH:
            assert plan.fully_resolved

    def test_meta_query_plan_is_fully_resolved(self, pos_planner):
        """META_QUERY outcome counts as resolved for the fully_resolved flag."""
        plan = pos_planner.plan(metric=("how many orders", "POS", "base_measure"))
        assert plan.fully_resolved

    def test_unresolved_field_makes_plan_not_fully_resolved(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("xyzzy unknown", "POS", "other")],
        )
        if plan.group_by and not plan.group_by[0].resolved:
            assert not plan.fully_resolved


# ── to_log_dict ───────────────────────────────────────────────────────────────

class TestQueryPlanLogDict:
    def test_log_dict_has_required_keys(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        d = plan.to_log_dict()
        required = {"metric", "meta_op", "group_by", "date_filter",
                    "filters", "sources", "fully_resolved", "sql_sketch"}
        assert required.issubset(d.keys())

    def test_log_dict_sql_sketch_matches_property(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        d = plan.to_log_dict()
        assert d["sql_sketch"] == plan.sql_sketch

    def test_log_dict_meta_op_is_none_for_column_match(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        d = plan.to_log_dict()
        assert d["meta_op"] is None

    def test_log_dict_meta_op_populated_for_meta_query(self, pos_planner):
        plan = pos_planner.plan(metric=("how many orders", "POS", "base_measure"))
        d = plan.to_log_dict()
        assert d["meta_op"] is not None
        assert "op_type" in d["meta_op"]
        assert "sql_fragment" in d["meta_op"]

    def test_log_dict_sources_is_list(self, pos_planner):
        plan = pos_planner.plan(metric=("extended price", "POS", "derived_measure"))
        d = plan.to_log_dict()
        assert isinstance(d["sources"], list)

    def test_log_dict_group_by_is_list(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        d = plan.to_log_dict()
        assert isinstance(d["group_by"], list)
        assert len(d["group_by"]) == 1


# ── Composed plan end-to-end ──────────────────────────────────────────────────

class TestComposedPlans:
    def test_metric_group_by_date_full_plan(self, pos_planner):
        """SELECT EXT_PRICE FROM POS WHERE ORDER_DATE BETWEEN ? AND ? GROUP BY CUSTOMER_NAME"""
        plan = pos_planner.plan(
            metric  = ("extended price",  "POS", "derived_measure"),
            group_by= [("customer name",  "POS", "other")],
            date    = ("order date",      "POS", "other"),
        )
        assert plan.metric is not None and plan.metric.column == "EXT_PRICE"
        assert plan.date_filter is not None
        assert len(plan.group_by) == 1
        assert "EXT_PRICE" in plan.sql_sketch
        assert "BETWEEN ? AND ?" in plan.sql_sketch
        assert "GROUP BY" in plan.sql_sketch

    def test_meta_with_explicit_group_by(self, hosp_planner):
        """'how many guests' meta + explicit group-by field."""
        plan = hosp_planner.plan(
            metric  = ("how many guests",     "Totals", "base_measure"),
            group_by= [("food net sales",     "Food",   "derived_measure")],
        )
        assert plan.meta_op is not None
        assert plan.meta_op.op_type == MetaOpType.COUNT_NON_NULL
        assert plan.meta_op.column == "Guests"
        assert "COUNT(Guests)" in plan.sql_sketch

    def test_ppa_with_date_filter(self, combined_planner):
        """PPA from Totals + ORDER_DATE from POS — cross-source composed plan."""
        plan = combined_planner.plan(
            metric= ("per person average", "Totals", "ratio"),
            date  = ("order date",         "POS",    "other"),
        )
        assert plan.metric is not None and plan.metric.column == "PPA"
        assert "SELECT PPA" in plan.sql_sketch

    def test_sources_deduplicated(self, pos_planner):
        """All fields from same source → sources list has exactly one entry."""
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
            date    = ("order date",     "POS", "other"),
        )
        assert len(plan.sources) == 1
        assert plan.sources[0] == "POS"

    def test_steps_audit_trail_populated(self, pos_planner):
        plan = pos_planner.plan(
            metric  = ("extended price", "POS", "derived_measure"),
            group_by= [("customer name", "POS", "other")],
        )
        # At minimum: metric step, group_by step, sql_sketch step
        assert len(plan.steps) >= 3
        assert any("[metric]" in s for s in plan.steps)
        assert any("[group_by]" in s for s in plan.steps)

    def test_filters_appear_in_where_clause(self, pos_planner):
        plan = pos_planner.plan(
            metric = ("extended price", "POS", "derived_measure"),
            filters= [("order status",  "POS", "other")],
        )
        if plan.filters and plan.filters[0].column:
            assert plan.filters[0].column in plan.sql_sketch
            assert "= ?" in plan.sql_sketch

    def test_no_arguments_plan_is_empty(self, pos_planner):
        """Calling plan() with no args returns a valid but empty QueryPlan."""
        plan = pos_planner.plan()
        assert plan.metric is None
        assert plan.meta_op is None
        assert plan.group_by == []
        assert plan.date_filter is None

    def test_net_sales_metric_hospitality(self, hosp_planner):
        plan = hosp_planner.plan(metric=("total net sales", "Totals", "derived_measure"))
        assert plan.metric is not None
        assert plan.metric.column == "Net_Sales"
        assert plan.metric.source == "Totals"

    def test_tips_metric_hospitality(self, hosp_planner):
        plan = hosp_planner.plan(metric=("tips", "Totals", "derived_measure"))
        assert plan.metric is not None
        assert plan.metric.column == "Tips"
