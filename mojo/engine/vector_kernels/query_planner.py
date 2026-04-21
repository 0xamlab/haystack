"""
vector_kernels/query_planner.py — Composable query planning layer.

Takes natural-language field hints and produces a structured QueryPlan that
can be directly rendered as SQL (SELECT … FROM … GROUP BY … WHERE …).

This is the final assembly layer above the resolver + meta executor:

  intent hints
      ↓
  QueryPlanner.plan()
      ↓ resolve_plan_fields()
  ColumnVectorResolver  ←  COLUMN_MATCH / WEAK_MATCH / META_QUERY / …
      ↓ interpret_meta_query()
  MetaExecutor          ←  COUNT_ROWS / SUM_COLUMN / COUNT_DISTINCT / …
      ↓
  QueryPlan
      ↓ sql_sketch
  "SELECT SUM(EXT_PRICE) FROM POS GROUP BY CUSTOMER_NAME"

Public API:
  FieldResolution     — single resolved field with outcome + sql_expr
  QueryPlan           — complete structured plan
  QueryPlanner        — plan() method
  QueryPlan.sql_sketch  — human-readable SQL sketch string

Self-test:
    python3 -m mojo.engine.vector_kernels.query_planner
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mojo.engine.vector_kernels.meta_executor import (
    MetaOpType,
    MetaQueryOp,
    interpret_meta_query,
    meta_op_to_sql_fragment,
)
from mojo.engine.vector_kernels.resolver import (
    ColumnVectorResolver,
    ResolverOutcome,
    ResolverReason,
)

if TYPE_CHECKING:
    pass


# ── Field resolution record ───────────────────────────────────────────────────

@dataclass
class FieldResolution:
    """
    One resolved field — wraps VectorResolverResult with a pre-built SQL expression.
    """
    hint:     str
    source:   str | None
    column:   str | None
    outcome:  ResolverOutcome
    reason:   ResolverReason
    score:    float
    sql_expr: str   # ready-to-embed SQL expression for this field

    @property
    def resolved(self) -> bool:
        """True if outcome is COLUMN_MATCH or WEAK_MATCH (has a usable column)."""
        return self.outcome in (ResolverOutcome.COLUMN_MATCH, ResolverOutcome.WEAK_MATCH)

    def to_log_dict(self) -> dict:
        return {
            "hint":     self.hint,
            "source":   self.source,
            "column":   self.column,
            "outcome":  self.outcome.value,
            "reason":   self.reason.value,
            "score":    round(self.score, 4),
            "sql_expr": self.sql_expr,
        }


# ── Query plan ────────────────────────────────────────────────────────────────

@dataclass
class QueryPlan:
    """
    Fully structured query plan ready for SQL generation.

    Attributes:
      metric        — resolved metric field (or None if not requested / not found)
      group_by      — list of resolved group-by fields
      date_filter   — resolved date field (None if not requested / not found)
      filters       — list of resolved filter fields
      meta_op       — MetaQueryOp when metric is META_QUERY (else None)
      sources       — distinct sources referenced in the plan
      fully_resolved — True when all requested fields have usable resolutions
      steps         — audit trail (list of resolver step strings)

    Use sql_sketch for a human-readable summary; use to_log_dict() for
    structured logging.
    """
    metric:         FieldResolution | None
    group_by:       list[FieldResolution] = field(default_factory=list)
    date_filter:    FieldResolution | None = None
    filters:        list[FieldResolution] = field(default_factory=list)
    meta_op:        MetaQueryOp | None = None
    sources:        list[str] = field(default_factory=list)
    fully_resolved: bool = False
    steps:          list[str] = field(default_factory=list)

    @property
    def sql_sketch(self) -> str:
        """
        Build a human-readable SQL sketch from the resolved plan.

        The sketch uses column names directly without quoting.  It is not
        intended to be execution-ready (no bindings, no schema qualifiers);
        its purpose is debugging, logging, and user-facing plan explanation.

        Examples:
            "SELECT COUNT(*) FROM Totals"
            "SELECT SUM(EXT_PRICE) FROM POS GROUP BY CUSTOMER_NAME"
            "SELECT Avg_Order_Time FROM Totals WHERE ORDER_DATE BETWEEN ? AND ?"
            "SELECT COUNT(*) FROM POS GROUP BY CUSTOMER_NAME WHERE ORDER_DATE BETWEEN ? AND ?"
        """
        # ── SELECT ────────────────────────────────────────────────────────────
        if self.meta_op is not None:
            select = meta_op_to_sql_fragment(self.meta_op)
        elif self.metric is not None and self.metric.resolved and self.metric.column:
            select = self.metric.column
        else:
            select = "?"

        # ── FROM ──────────────────────────────────────────────────────────────
        source = self.sources[0] if self.sources else "?"

        # ── WHERE ─────────────────────────────────────────────────────────────
        where_parts: list[str] = []
        if self.date_filter and self.date_filter.column:
            where_parts.append(f"{self.date_filter.column} BETWEEN ? AND ?")
        for f in self.filters:
            if f.column:
                where_parts.append(f"{f.column} = ?")

        # ── GROUP BY ──────────────────────────────────────────────────────────
        # Also pick up group-by embedded in meta_op ("per customer")
        group_cols: list[str] = [r.column for r in self.group_by if r.column]
        if self.meta_op and self.meta_op.group_by_hint:
            # group_by_hint is a raw noun — show as annotation, not a resolved column
            group_cols.append(f"<{self.meta_op.group_by_hint}>")

        sql = f"SELECT {select}\nFROM {source}"
        if where_parts:
            sql += f"\nWHERE {' AND '.join(where_parts)}"
        if group_cols:
            sql += f"\nGROUP BY {', '.join(group_cols)}"
        return sql

    def to_log_dict(self) -> dict:
        """Structured dict for logging / audit — includes all field details."""
        return {
            "metric":         self.metric.to_log_dict() if self.metric else None,
            "meta_op":        self.meta_op.to_log_dict() if self.meta_op else None,
            "group_by":       [r.to_log_dict() for r in self.group_by],
            "date_filter":    self.date_filter.to_log_dict() if self.date_filter else None,
            "filters":        [r.to_log_dict() for r in self.filters],
            "sources":        self.sources,
            "fully_resolved": self.fully_resolved,
            "sql_sketch":     self.sql_sketch,
        }


# ── QueryPlanner ──────────────────────────────────────────────────────────────

class QueryPlanner:
    """
    Composable query planner.  Wraps a ColumnVectorResolver and produces
    QueryPlan objects from natural-language field hints.

    Usage:
        planner = QueryPlanner(resolver)
        plan = planner.plan(
            metric    = ("total revenue",   "POS", "derived_measure"),
            group_by  = [("customer name",  "POS", "other")],
            date      = ("order date",      "POS", "other"),
        )
        print(plan.sql_sketch)

    Metric sem_type is used to decide whether WEAK_MATCH is acceptable:
        metric_is_critical=True  → only COLUMN_MATCH accepted (default)
        metric_is_critical=False → also accepts WEAK_MATCH
    """

    def __init__(self, resolver: ColumnVectorResolver):
        self._resolver = resolver

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve_field(
        self,
        hint: str,
        src:  str | None,
        role: str | None,
        accept_weak: bool = True,
    ) -> FieldResolution:
        """Resolve a single field and wrap the result in a FieldResolution."""
        vr = self._resolver.resolve(hint, preferred_source=src, role_hint=role)
        if vr is None:
            return FieldResolution(
                hint=hint, source=None, column=None,
                outcome=ResolverOutcome.NO_COLUMN_MATCH,
                reason=ResolverReason.NO_SIGNAL,
                score=0.0, sql_expr="?",
            )
        # Column expression for the field
        if vr.outcome in (ResolverOutcome.COLUMN_MATCH, ResolverOutcome.WEAK_MATCH):
            sql_expr = vr.column or "?"
        else:
            sql_expr = "?"
        return FieldResolution(
            hint=hint, source=vr.source, column=vr.column,
            outcome=vr.outcome, reason=vr.reason,
            score=vr.score, sql_expr=sql_expr,
        )

    def _resolve_metric(
        self,
        hint: str,
        src:  str | None,
        role: str | None,
        metric_is_critical: bool,
    ) -> tuple[FieldResolution, MetaQueryOp | None]:
        """
        Resolve a metric hint.  Returns (FieldResolution, MetaQueryOp | None).
        MetaQueryOp is non-None when the outcome is META_QUERY.
        """
        vr = self._resolver.resolve(hint, preferred_source=src, role_hint=role)
        if vr is None:
            fr = FieldResolution(
                hint=hint, source=None, column=None,
                outcome=ResolverOutcome.NO_COLUMN_MATCH,
                reason=ResolverReason.NO_SIGNAL,
                score=0.0, sql_expr="?",
            )
            return fr, None

        meta_op: MetaQueryOp | None = None

        if vr.outcome == ResolverOutcome.META_QUERY:
            meta_op = interpret_meta_query(hint, vr)
            sql_expr = meta_op_to_sql_fragment(meta_op)
        elif vr.outcome == ResolverOutcome.COLUMN_MATCH:
            sql_expr = vr.column or "?"
        elif vr.outcome == ResolverOutcome.WEAK_MATCH and not metric_is_critical:
            sql_expr = vr.column or "?"
        else:
            sql_expr = "?"

        fr = FieldResolution(
            hint=hint, source=vr.source, column=vr.column,
            outcome=vr.outcome, reason=vr.reason,
            score=vr.score, sql_expr=sql_expr,
        )
        return fr, meta_op

    # ── Public plan() ─────────────────────────────────────────────────────────

    def plan(
        self,
        *,
        metric:             tuple[str, str | None, str | None] | None = None,
        group_by:           list[tuple[str, str | None, str | None]] | None = None,
        date:               tuple[str, str | None, str | None] | None = None,
        filters:            list[tuple[str, str | None, str | None]] | None = None,
        metric_is_critical: bool = True,
    ) -> QueryPlan:
        """
        Resolve all field hints and build a QueryPlan.

        Args:
            metric:             (hint, preferred_source, role_hint) for the SELECT metric
            group_by:           list of (hint, source, role) for GROUP BY fields
            date:               (hint, source, role) for date / time filter
            filters:            list of (hint, source, role) for WHERE conditions
            metric_is_critical: if True (default), metric requires COLUMN_MATCH;
                                 WEAK_MATCH falls through to column_match engine.

        Returns:
            QueryPlan with all resolved fields, sql_sketch, and audit steps.
        """
        steps: list[str] = []

        # ── Metric ──────────────────────────────────────────────────────────
        metric_fr: FieldResolution | None = None
        meta_op:   MetaQueryOp | None = None
        if metric is not None:
            hint, src, role = metric
            metric_fr, meta_op = self._resolve_metric(hint, src, role, metric_is_critical)
            steps.append(
                f"[metric] {hint!r} → outcome={metric_fr.outcome.value}  "
                f"reason={metric_fr.reason.value}  score={metric_fr.score:.3f}"
                + (f"  sql={meta_op_to_sql_fragment(meta_op)}" if meta_op else
                   f"  col={metric_fr.column}")
            )

        # ── Group-by fields ─────────────────────────────────────────────────
        group_by_resolutions: list[FieldResolution] = []
        for hint, src, role in (group_by or []):
            fr = self._resolve_field(hint, src, role, accept_weak=True)
            group_by_resolutions.append(fr)
            steps.append(
                f"[group_by] {hint!r} → outcome={fr.outcome.value}  col={fr.column}"
            )

        # ── Date filter ─────────────────────────────────────────────────────
        date_fr: FieldResolution | None = None
        if date is not None:
            hint, src, role = date
            date_fr = self._resolve_field(hint, src, role, accept_weak=True)
            steps.append(
                f"[date] {hint!r} → outcome={date_fr.outcome.value}  col={date_fr.column}"
            )

        # ── Where filters ───────────────────────────────────────────────────
        filter_resolutions: list[FieldResolution] = []
        for hint, src, role in (filters or []):
            fr = self._resolve_field(hint, src, role, accept_weak=True)
            filter_resolutions.append(fr)
            steps.append(
                f"[filter] {hint!r} → outcome={fr.outcome.value}  col={fr.column}"
            )

        # ── Assemble sources ────────────────────────────────────────────────
        source_set: list[str] = []
        for fr in [metric_fr, date_fr] + group_by_resolutions + filter_resolutions:
            if fr and fr.source and fr.source not in source_set:
                source_set.append(fr.source)
        if meta_op and meta_op.source and meta_op.source not in source_set:
            source_set.append(meta_op.source)

        # ── Fully resolved check ────────────────────────────────────────────
        all_fields: list[FieldResolution | None] = (
            ([metric_fr] if metric_fr else [])
            + group_by_resolutions
            + ([date_fr] if date_fr else [])
            + filter_resolutions
        )
        fully_resolved = all(
            f.resolved or f.outcome == ResolverOutcome.META_QUERY
            for f in all_fields
        )

        plan = QueryPlan(
            metric=metric_fr,
            group_by=group_by_resolutions,
            date_filter=date_fr,
            filters=filter_resolutions,
            meta_op=meta_op,
            sources=source_set,
            fully_resolved=fully_resolved,
            steps=steps,
        )
        steps.append(f"[plan] sql_sketch:\n{plan.sql_sketch}")
        return plan


# ── Self-test ─────────────────────────────────────────────────────────────────

def _run_self_test():
    import sys

    def _emit(message: str = "") -> None:
        sys.stdout.write(f"{message}\n")

    schema = {
        "POS": [
            ("UNIT_PRICE",    "unit_measure"),
            ("EXT_PRICE",     "derived_measure"),
            ("QTY",           "base_measure"),
            ("ORDER_DATE",    "other"),
            ("CUSTOMER_NAME", "other"),
            ("ORDER_STATUS",  "other"),
        ],
        "Totals": [
            ("Net_Sales", "derived_measure"),
            ("Tips",      "derived_measure"),
            ("Guests",    "base_measure"),
            ("PPA",       "ratio"),
            ("Sold",      "base_measure"),
        ],
    }
    r = ColumnVectorResolver(schema)
    qp = QueryPlanner(r)

    _emit("=== query_planner self-test ===\n")
    all_ok = True

    # ── Case 1: metric + group_by + date ──────────────────────────────────────
    plan1 = qp.plan(
        metric=("extended price", "POS", "derived_measure"),
        group_by=[("customer name", "POS", "other")],
        date=("order date", "POS", "other"),
    )
    ok1 = (
        plan1.metric is not None and plan1.metric.column == "EXT_PRICE"
        and len(plan1.group_by) == 1
        and plan1.date_filter is not None
    )
    if not ok1:
        all_ok = False
    _emit(f"  {'PASS' if ok1 else 'FAIL'}  metric+group_by+date")
    _emit(f"  sql: {plan1.sql_sketch.replace(chr(10), ' | ')}\n")

    # ── Case 2: meta query (server count) ────────────────────────────────────
    plan2 = qp.plan(
        metric=("server count", "POS", "base_measure"),
        group_by=[],
    )
    ok2 = (
        plan2.meta_op is not None
        and plan2.meta_op.op_type == MetaOpType.COUNT_ROWS
    )
    if not ok2:
        all_ok = False
    _emit(f"  {'PASS' if ok2 else 'FAIL'}  meta COUNT_ROWS")
    _emit(f"  sql: {plan2.sql_sketch.replace(chr(10), ' | ')}\n")

    # ── Case 3: meta + group_by embedded ("number of orders per customer") ────
    plan3 = qp.plan(
        metric=("how many guests", "Totals", "base_measure"),
        group_by=[("per person average", "Totals", "ratio")],
    )
    ok3 = (
        plan3.meta_op is not None
        and plan3.meta_op.op_type == MetaOpType.COUNT_NON_NULL
        and plan3.meta_op.column == "Guests"
    )
    if not ok3:
        all_ok = False
    _emit(
        f"  {'PASS' if ok3 else 'FAIL'}  meta COUNT_NON_NULL(Guests) + group_by"
    )
    _emit(f"  sql: {plan3.sql_sketch.replace(chr(10), ' | ')}\n")

    # ── Case 4: per person average (PPA) with date filter ────────────────────
    plan4 = qp.plan(
        metric=("per person average", "Totals", "ratio"),
        date=("order date", "POS", "other"),
    )
    ok4 = plan4.metric is not None and plan4.metric.column == "PPA"
    if not ok4:
        all_ok = False
    _emit(f"  {'PASS' if ok4 else 'FAIL'}  PPA metric + date filter")
    _emit(f"  sql: {plan4.sql_sketch.replace(chr(10), ' | ')}\n")

    # ── Case 5: to_log_dict ───────────────────────────────────────────────────
    log = plan1.to_log_dict()
    ok5 = "metric" in log and "sql_sketch" in log and "sources" in log
    if not ok5:
        all_ok = False
    _emit(f"  {'PASS' if ok5 else 'FAIL'}  to_log_dict has expected keys")
    _emit(f"  keys: {sorted(log.keys())}\n")

    _emit(f"{'All tests passed.' if all_ok else 'FAILURES above.'}")
    return all_ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_self_test() else 1)
