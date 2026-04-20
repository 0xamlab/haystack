"""
vector_kernels/meta_executor.py — Structured interpretation of META_QUERY results.

When the resolver returns outcome=META_QUERY, this module converts the raw result
into a typed MetaQueryOp that the planner can execute directly — no NLP fallback needed.

Decision tree (applied in order):
  1. Extract entity noun and aggregation intent from the hint
  2. Check resolver's best_score against COLUMN_SCORE_THRESHOLD:
       score ≥ threshold  → entity maps to a column → SUM_COLUMN (or COUNT_NON_NULL)
       score <  threshold → entity IS the row       → COUNT_ROWS
  3. Refine by aggregation intent:
       "how many" / "count" → COUNT_ROWS or COUNT_NON_NULL
       "total" / "sum"      → SUM_COLUMN when column exists, else COUNT_ROWS
       "max" / "min" / "avg"→ MAX_COLUMN / MIN_COLUMN / AVG_COLUMN

Public API:
  MetaOpType              — enum of structured operation types
  MetaQueryOp             — dataclass describing the operation
  interpret_meta_query()  — resolver result → MetaQueryOp
  meta_op_to_sql_fragment()  — MetaQueryOp → partial SQL expression

Self-test:
    python3 mojo/engine/vector_kernels/meta_executor.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from mojo.engine.vector_kernels.tokenizer import tokenize_name

if TYPE_CHECKING:
    from mojo.engine.vector_kernels.resolver import VectorResolverResult


# ── Operation types ────────────────────────────────────────────────────────────

class MetaOpType(Enum):
    """
    Structured aggregation operation types produced by the meta executor.

    COUNT_ROWS      — SELECT COUNT(*) FROM source
                      Entity = the row itself (e.g. "server count")
    SUM_COLUMN      — SELECT SUM(column) FROM source
                      Entity = a numeric column (e.g. "total guests" → SUM(Guests))
    COUNT_NON_NULL  — SELECT COUNT(column) FROM source
                      Counts populated rows, not total rows
    COUNT_DISTINCT  — SELECT COUNT(DISTINCT column) FROM source
    MAX_COLUMN      — SELECT MAX(column) FROM source
    MIN_COLUMN      — SELECT MIN(column) FROM source
    AVG_COLUMN      — SELECT AVG(column) FROM source
    UNKNOWN         — Unable to determine operation; fall through to NLP
    """
    COUNT_ROWS      = "count_rows"
    SUM_COLUMN      = "sum_column"
    COUNT_NON_NULL  = "count_non_null"
    COUNT_DISTINCT  = "count_distinct"
    MAX_COLUMN      = "max_column"
    MIN_COLUMN      = "min_column"
    AVG_COLUMN      = "avg_column"
    UNKNOWN         = "unknown"


# ── Operation dataclass ────────────────────────────────────────────────────────

@dataclass
class MetaQueryOp:
    """
    Structured representation of a meta-query, ready for SQL generation.

    Fields:
      op_type        — the aggregation operation to perform
      source         — source table name (None if unknown or unneeded)
      column         — column name for column-based ops (None for COUNT_ROWS)
      entity         — entity noun extracted from hint (e.g. "servers", "guests")
      agg_word       — aggregation word from hint (e.g. "count", "total", "how many")
      hint           — original user hint
      derivation     — "column_exists" | "row_entity" | "fallback"
      resolver_score — best_score from the resolver result
      group_by_hint  — extracted grouping phrase if present ("per customer" → "customer")
    """
    op_type:        MetaOpType
    source:         str | None
    column:         str | None
    entity:         str
    agg_word:       str
    hint:           str
    derivation:     str
    resolver_score: float
    group_by_hint:  str | None = None   # "per X" / "by X" extracted noun phrase


    def to_log_dict(self) -> dict:
        """Return a structured dict suitable for logging / audit trails."""
        col = self.column or "*"
        _sql_map = {
            MetaOpType.COUNT_ROWS:     "COUNT(*)",
            MetaOpType.SUM_COLUMN:     f"SUM({col})",
            MetaOpType.COUNT_NON_NULL: f"COUNT({col})",
            MetaOpType.COUNT_DISTINCT: f"COUNT(DISTINCT {col})",
            MetaOpType.MAX_COLUMN:     f"MAX({col})",
            MetaOpType.MIN_COLUMN:     f"MIN({col})",
            MetaOpType.AVG_COLUMN:     f"AVG({col})",
        }
        return {
            "op_type":        self.op_type.value,
            "source":         self.source,
            "column":         self.column,
            "entity":         self.entity,
            "agg_word":       self.agg_word,
            "derivation":     self.derivation,
            "resolver_score": round(self.resolver_score, 4),
            "group_by_hint":  self.group_by_hint,
            "sql_fragment":   _sql_map.get(self.op_type, "NULL"),
        }


# ── Aggregation intent classification ─────────────────────────────────────────

# Words that carry aggregation intent — stripped before entity extraction
_AGG_WORDS: frozenset[str] = frozenset({
    "count", "total", "sum", "how", "many", "number", "of",
    "max", "maximum", "min", "minimum", "avg", "average", "mean",
    "highest", "lowest", "top", "bottom",
    "unique", "distinct", "different",          # DISTINCT signals
})

# Patterns → (MetaOpType, agg_word)  — checked in priority order
_AGG_PATTERNS: list[tuple[re.Pattern, MetaOpType, str]] = [
    # DISTINCT must come before plain COUNT to avoid mis-match
    (re.compile(r'\b(unique|distinct|different)\b',                          re.I),  MetaOpType.COUNT_DISTINCT, "distinct"),
    (re.compile(r'\b(how many|number of|count of|row count|total count)\b',  re.I),  MetaOpType.COUNT_ROWS,     "count"),
    (re.compile(r'\bcount\b',                                                re.I),  MetaOpType.COUNT_ROWS,     "count"),
    (re.compile(r'\b(total|sum)\b',                                          re.I),  MetaOpType.SUM_COLUMN,     "total"),
    (re.compile(r'\b(max|maximum|highest|top)\b',                            re.I),  MetaOpType.MAX_COLUMN,     "max"),
    (re.compile(r'\b(min|minimum|lowest|bottom)\b',                          re.I),  MetaOpType.MIN_COLUMN,     "min"),
    (re.compile(r'\b(avg|average|mean)\b',                                   re.I),  MetaOpType.AVG_COLUMN,     "avg"),
]

# Group-by signal: "per X", "by X", "for each X", "grouped by X"
_GROUP_RE = re.compile(
    r'\b(?:per|by|for each|grouped by|group by)\s+([\w][\w\s]{0,30}?)(?:\s*$|\s+and\b)',
    re.I,
)

# Threshold: resolver score above this → entity probably maps to a column
_COLUMN_SCORE_THRESHOLD = 0.45


def _extract_agg_intent(hint: str) -> tuple[MetaOpType, str]:
    """Return (base_op_type, agg_word) from the hint, or (COUNT_ROWS, 'count') as default."""
    for pat, op, word in _AGG_PATTERNS:
        if pat.search(hint):
            return op, word
    return MetaOpType.COUNT_ROWS, "count"


def _extract_entity(hint: str) -> str:
    """
    Remove aggregation words and common stop-words; return remaining noun(s).
    Falls back to the full hint if nothing remains.
    """
    _STOPS = frozenset({"the", "a", "an", "of", "per", "by", "from", "in", "at"})
    tokens = tokenize_name(hint)
    noun_tokens = [t for t in tokens if t not in _AGG_WORDS and t not in _STOPS]
    return " ".join(noun_tokens) if noun_tokens else hint.strip()


# ── Main interpreter ───────────────────────────────────────────────────────────

def interpret_meta_query(
    hint: str,
    vr: VectorResolverResult,
    column_score_threshold: float = _COLUMN_SCORE_THRESHOLD,
) -> MetaQueryOp:
    """
    Convert a META_QUERY resolver result into a typed MetaQueryOp.

    Args:
        hint:                    the original user query string
        vr:                      VectorResolverResult with outcome == META_QUERY
        column_score_threshold:  resolver score above which we treat the best
                                 candidate as a column-backed entity

    Returns:
        MetaQueryOp ready for SQL generation or further planning.

    Example:
        # "server count" — no servers column, score 0.438 < threshold
        op = interpret_meta_query("server count", vr)
        assert op.op_type == MetaOpType.COUNT_ROWS
        assert op.column is None

        # "how many guests" — Guests column exists, score 0.63 > threshold
        op = interpret_meta_query("how many guests", vr)
        assert op.op_type == MetaOpType.COUNT_NON_NULL
        assert op.column == "Guests"
    """
    base_op, agg_word = _extract_agg_intent(hint)
    entity = _extract_entity(hint)
    has_column = vr.score >= column_score_threshold and vr.column is not None

    # Extract optional group-by hint ("per customer", "by region", "for each date")
    group_by_hint: str | None = None
    gm = _GROUP_RE.search(hint)
    if gm:
        group_by_hint = gm.group(1).strip()

    if has_column:
        # Entity maps to a real column — refine op based on aggregation intent
        if base_op == MetaOpType.COUNT_DISTINCT:
            # "unique X" where X is a column → COUNT(DISTINCT X)
            op_type = MetaOpType.COUNT_DISTINCT
        elif base_op == MetaOpType.COUNT_ROWS:
            # "how many X" where X is a column → COUNT(X) non-null
            op_type = MetaOpType.COUNT_NON_NULL
        elif base_op == MetaOpType.SUM_COLUMN:
            op_type = MetaOpType.SUM_COLUMN
        elif base_op in (MetaOpType.MAX_COLUMN, MetaOpType.MIN_COLUMN, MetaOpType.AVG_COLUMN):
            op_type = base_op
        else:
            op_type = MetaOpType.SUM_COLUMN
        return MetaQueryOp(
            op_type=op_type,
            source=vr.source,
            column=vr.column,
            entity=entity,
            agg_word=agg_word,
            hint=hint,
            derivation="column_exists",
            resolver_score=vr.score,
            group_by_hint=group_by_hint,
        )
    else:
        # Entity IS the row entity — COUNT_ROWS (or COUNT_DISTINCT for "unique X")
        op_type = MetaOpType.COUNT_DISTINCT if base_op == MetaOpType.COUNT_DISTINCT else MetaOpType.COUNT_ROWS
        return MetaQueryOp(
            op_type=op_type,
            source=vr.source,
            column=None,
            entity=entity,
            agg_word=agg_word,
            hint=hint,
            derivation="row_entity",
            resolver_score=vr.score,
            group_by_hint=group_by_hint,
        )


# ── SQL fragment generator ─────────────────────────────────────────────────────

def meta_op_to_sql_fragment(op: MetaQueryOp) -> str:
    """
    Convert a MetaQueryOp to a partial SQL SELECT expression.

    Returns only the expression, not the full statement — the caller provides
    FROM, WHERE, and GROUP BY clauses.

    Examples:
        COUNT_ROWS                      → "COUNT(*)"
        SUM_COLUMN   col=Guests         → "SUM(Guests)"
        COUNT_NON_NULL col=Guests       → "COUNT(Guests)"
        COUNT_DISTINCT col=Guests       → "COUNT(DISTINCT Guests)"
        MAX_COLUMN   col=Net_Sales      → "MAX(Net_Sales)"
        MIN_COLUMN   col=Net_Sales      → "MIN(Net_Sales)"
        AVG_COLUMN   col=Avg_Order_Time → "AVG(Avg_Order_Time)"
    """
    col = op.column or "*"
    if op.op_type == MetaOpType.COUNT_ROWS:
        return "COUNT(*)"
    if op.op_type == MetaOpType.SUM_COLUMN:
        return f"SUM({col})"
    if op.op_type == MetaOpType.COUNT_NON_NULL:
        return f"COUNT({col})"
    if op.op_type == MetaOpType.COUNT_DISTINCT:
        return f"COUNT(DISTINCT {col})"
    if op.op_type == MetaOpType.MAX_COLUMN:
        return f"MAX({col})"
    if op.op_type == MetaOpType.MIN_COLUMN:
        return f"MIN({col})"
    if op.op_type == MetaOpType.AVG_COLUMN:
        return f"AVG({col})"
    return "NULL  -- unknown meta op"


# ── Self-test ─────────────────────────────────────────────────────────────────

def _run_self_test():
    from mojo.engine.vector_kernels.resolver import ColumnVectorResolver, ResolverOutcome

    schema = {
        "Totals":   [("Net_Sales","derived_measure"),("Guests","base_measure"),
                     ("PPA","ratio"),("Tips","derived_measure"),("Sold","base_measure")],
        "Beverage": [("Beverage_Net_Sales","derived_measure"),("Beverage_Guests","base_measure")],
    }
    hosp = ColumnVectorResolver(schema)

    proc_schema = {
        "POS": [("UNIT_PRICE","unit_measure"),("EXT_PRICE","derived_measure"),
                ("QTY","base_measure"),("CUSTOMER_NAME","other"),("ORDER_DATE","other")],
    }
    proc = ColumnVectorResolver(proc_schema)

    cases = [
        # (resolver, hint, src, role, expected_op, expected_col_or_none)
        # "total guests" is intentionally omitted: "total" alone is a column prefix
        # in many schemas (Total_Guests), so it stays AMBIGUOUS — correct behavior.
        (hosp, "server count",      "Totals", "base_measure",  MetaOpType.COUNT_ROWS,      None),
        (hosp, "how many guests",   "Totals", None,            MetaOpType.COUNT_NON_NULL,  "Guests"),
        (hosp, "number of guests",  "Totals", None,            MetaOpType.COUNT_NON_NULL,  "Guests"),
        (hosp, "number of servers", "Totals", None,            MetaOpType.COUNT_ROWS,      None),
        (proc, "how many orders",   "POS",    None,            MetaOpType.COUNT_ROWS,      None),
    ]

    all_ok = True
    print("=== meta_executor self-test ===\n")
    for res, hint, src, role, exp_op, exp_col in cases:
        vr = res.resolve(hint, preferred_source=src, role_hint=role)
        if vr is None or vr.outcome != ResolverOutcome.META_QUERY:
            ok = False
            all_ok = False
            print(f"  FAIL  {hint!r} — resolver didn't return META_QUERY "
                  f"(outcome={vr.outcome.value if vr else 'None'})")
            continue
        op = interpret_meta_query(hint, vr)
        ok_op  = op.op_type == exp_op
        ok_col = op.column == exp_col
        ok = ok_op and ok_col
        if not ok: all_ok = False
        sym = "PASS" if ok else "FAIL"
        print(f"  {sym}  {hint!r}")
        print(f"        op={op.op_type.value}  col={op.column}  "
              f"entity={op.entity!r}  derivation={op.derivation}")
        print(f"        sql: {meta_op_to_sql_fragment(op)}")
        if not ok_op:  print(f"        !! expected op={exp_op.value}")
        if not ok_col: print(f"        !! expected col={exp_col}")

    print(f"\n{'All tests passed.' if all_ok else 'FAILURES above.'}")
    return all_ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_self_test() else 1)
