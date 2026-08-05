"""Columnar queries on the local runtime — filter, group, sort, top-k, in one call.

Every operator runs as a compiled Mojo kernel on this device. Nothing leaves the
machine, and the whole plan crosses the boundary once rather than per operator:

    from algenta import MojoRuntime, Query, col

    rt = MojoRuntime(mode="local")
    result = (
        Query(columns=["region", "amount"], rows=[[1, 10.5], [2, 50], [1, 30]])
        .filter(col("amount") > 20)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .run(rt, routing_module="stats")
    )
    result.rows        # [[2.0, 50.0], [1.0, 30.0]]
    result.plan_hash   # identifies the computation, not the data

Why a builder rather than SQL
----------------------------
A plan is data — a list of ops and an expression tree — so it can be hashed,
compared, cached and shipped. SQL text would have to be parsed before any of that,
and two spellings of the same query would hash differently. `plan_hash` is over the
plan's VALUES, so whitespace and key order do not change it and a threshold does.

Nulls are absences, not zeros
-----------------------------
`None` in an input cell stays absent all the way through and comes back as `None`.
A predicate over an absent value is *unknown*, and unknown does not pass a filter —
so a row with a missing amount is neither kept nor counted, rather than silently
being treated as amount 0.

Joins and windows
-----------------
A join reads a NAMED SIDE TABLE declared once per request, never inside an op:

    result = (
        Query(columns=["order_id", "customer_id", "amount"], rows=orders)
        .with_table("customers", ["id", "tier"], rows=customers)
        .join("customers", left_on="customer_id", right_on="id", how="left")
        .running("amount", name="running_total",
                 partition_by="customers.tier", order_by="order_id")
        .run(rt, routing_module="stats")
    )

Tables live beside the plan because `plan_hash` is over `ops`: rows inside an op
would make the hash data-dependent, so two runs of the same computation over
different data would stop comparing — which is the one property the hash has. The
table's NAME, keys, `how`, `method` and `prefix` are in `ops` and so in the hash; its
body is not, exactly as the left side's `rows` are not.

A window function appends ONE column and does not reorder the rows. `partition_by`
and `order_by` are column names; the output name is required, because every default
either is ambiguous or shadows an existing column.

`routing_module` picks which shard binary serves the request. It exists because the
runtime is shipped as filtered shards — nobody installs all 495 modules — so the
call has to say which shard it belongs to. Any module in the installed shard works;
`"stats"` is a safe default for a query that calls no kernel by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Expr",
    "Query",
    "QueryError",
    "QueryResult",
    "case_when",
    "col",
    "lit",
    "run_query",
]

# Opcodes must match mojo/engine/query/ir.mojo. 0-38 are frozen and owned by
# expr.mojo; everything here is in the 100+ range this package allocated.
_OP_LITERAL = 0
_OP_ADD = 2
_OP_SUB = 3
_OP_MUL = 4
_OP_DIV = 5
_OP_NEG = 6
_OP_LT = 100
_OP_LE = 101
_OP_GT = 102
_OP_GE = 103
_OP_EQ = 104
_OP_NE = 105
_OP_AND = 110
_OP_OR = 111
_OP_NOT = 112
_OP_IS_NULL = 120
_OP_IS_NOT_NULL = 121
_OP_COALESCE = 122
_OP_COL_REF = 130
_OP_CASE_WHEN = 150

_ACCEPTED_AGGREGATIONS = ("sum", "avg", "mean", "min", "max", "count", "var", "std")

# ── join / window vocabularies, mirroring query/plan.mojo ─────────────────────
# Local tuples rather than a call to the engine: a typo caught here carries the
# caller's traceback, and a builder that can emit an op the kernel will reject is
# a bug. The engine's five resource bounds are deliberately NOT enforced here — a
# limit checked in two places at two strengths is worse than one, and only the
# engine knows the real row counts — but they ARE written down, in the docstrings
# of `with_table`, `join` and `window`, because a caller cannot plan around a limit
# nobody states. They are, in full:
#
#   MAX_TABLES              8 named side tables per request
#   MAX_MATERIALIZED_CELLS  32,000,000 cells, summed over every side table AND
#                           over a join's materialized output
#   MAX_JOIN_OUTPUT_ROWS    1,000,000 rows out of one join
#   MAX_WINDOW_ROWS         20,000 rows INTO a window op
#   MAX_COLUMNS             512 columns in any declared header, and the ceiling a
#                           window's appended column counts against
#
# The engine's message reports the number it measured, which is the reason the
# check belongs there and not here.
_ACCEPTED_JOIN_HOW = ("inner", "left", "semi", "anti")
_UNIMPLEMENTED_JOIN_HOW = ("right", "outer", "full", "cross")
_ACCEPTED_JOIN_METHODS = ("hash", "merge", "direct_address")
_JOIN_HOW_WITHOUT_RIGHT_COLUMNS = ("semi", "anti")

_ACCEPTED_WINDOW_FNS = (
    "row_number",
    "rank",
    "dense_rank",
    "lag",
    "lead",
    "cumulative",
    "framed",
    "partition_total",
)
# A window frame answers sum/avg/min/max/count. `parse_aggregation` also accepts
# var/std/median, but the frame kernels answer those with an all-null column and a
# success status, so they are rejected rather than shipped.
_ACCEPTED_WINDOW_AGGREGATIONS = ("sum", "avg", "mean", "min", "max", "count")
_WINDOW_FNS_TAKING_VALUE = ("lag", "lead", "cumulative", "framed", "partition_total")
_WINDOW_FNS_TAKING_AGG = ("cumulative", "framed", "partition_total")
_WINDOW_FNS_TAKING_OFFSET = ("lag", "lead")
# Every fn except partition_total needs an order: a running total with no order is
# not a defined answer. partition_total is order-independent by definition, so an
# order_by there is accepted and ignored — one spec can be shared across ops.
_WINDOW_FNS_NEEDING_ORDER = (
    "row_number",
    "rank",
    "dense_rank",
    "lag",
    "lead",
    "cumulative",
    "framed",
)
# A tie is defined by the single order column, so several would report ties that
# are not ties.
_WINDOW_FNS_NEEDING_ONE_ORDER = ("rank", "dense_rank")

# The widest integer the plan's JSON survives. Python's `int` is unbounded; the engine
# reads an integer with `value = value*10 + digit` in SIGNED 64-BIT arithmetic, which
# does not trap — it wraps. So an out-of-range `offset` or `preceding` would arrive as a
# different, small, entirely plausible number and be answered successfully. This builder
# is the last place the value the caller actually wrote still exists.
_WIRE_INT_MIN = -(2**63)
_WIRE_INT_MAX = 2**63 - 1


class QueryError(RuntimeError):
    """A query plan was rejected or an operator failed.

    `code` is the engine's error code (`query_op_failed`, `invalid_arguments`,
    `unknown_aggregation`, ...) and `op_index` names which operator failed, when the
    engine could tell. A failed plan returns NO result — a partial answer would be
    indistinguishable from a complete one.
    """

    def __init__(self, code: str, message: str, op_index: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.op_index = op_index


@dataclass(frozen=True)
class Expr:
    """An expression tree, flattened on demand into the wire node array.

    Built with operators (`col("a") > 20`) so a predicate reads like the condition it
    is. Immutable, so an expression can be reused across plans without one plan's
    later mutation changing another's meaning.
    """

    op: int
    column: str | None = None
    value: float | None = None
    children: tuple[Expr, ...] = ()

    # ── comparisons ───────────────────────────────────────────────────────────
    def __lt__(self, other: Any) -> Expr:
        return Expr(_OP_LT, children=(self, _coerce(other)))

    def __le__(self, other: Any) -> Expr:
        return Expr(_OP_LE, children=(self, _coerce(other)))

    def __gt__(self, other: Any) -> Expr:
        return Expr(_OP_GT, children=(self, _coerce(other)))

    def __ge__(self, other: Any) -> Expr:
        return Expr(_OP_GE, children=(self, _coerce(other)))

    def eq(self, other: Any) -> Expr:
        """Equality. Named rather than `__eq__` so `Expr` stays hashable and usable
        as a dataclass field; overriding `__eq__` to build a tree would break both."""
        return Expr(_OP_EQ, children=(self, _coerce(other)))

    def ne(self, other: Any) -> Expr:
        return Expr(_OP_NE, children=(self, _coerce(other)))

    # ── logical, three-valued over nulls ──────────────────────────────────────
    def __and__(self, other: Expr) -> Expr:
        return Expr(_OP_AND, children=(self, other))

    def __or__(self, other: Expr) -> Expr:
        return Expr(_OP_OR, children=(self, other))

    def __invert__(self) -> Expr:
        return Expr(_OP_NOT, children=(self,))

    # ── arithmetic ────────────────────────────────────────────────────────────
    def __add__(self, other: Any) -> Expr:
        return Expr(_OP_ADD, children=(self, _coerce(other)))

    def __sub__(self, other: Any) -> Expr:
        return Expr(_OP_SUB, children=(self, _coerce(other)))

    def __mul__(self, other: Any) -> Expr:
        return Expr(_OP_MUL, children=(self, _coerce(other)))

    def __truediv__(self, other: Any) -> Expr:
        return Expr(_OP_DIV, children=(self, _coerce(other)))

    def __neg__(self) -> Expr:
        return Expr(_OP_NEG, children=(self,))

    # ── null tests: the one place an absent input gives a known answer ────────
    def is_null(self) -> Expr:
        return Expr(_OP_IS_NULL, children=(self,))

    def is_not_null(self) -> Expr:
        return Expr(_OP_IS_NOT_NULL, children=(self,))

    def coalesce(self, other: Any) -> Expr:
        return Expr(_OP_COALESCE, children=(self, _coerce(other)))

    # ── conditional ────────────────────────────────────────────────────────────
    def if_else(self, then: Any, else_: Any) -> Expr:
        """`CASE WHEN self THEN then ELSE else_ END`, as one ternary node.

        `self` is the condition; an unknown (null) condition takes the `else_`
        branch, matching SQL — a `CASE` never turns null just because its
        condition was unknown. For more than one `WHEN`, chain via `case_when`.
        """
        return Expr(
            _OP_CASE_WHEN, children=(self, _coerce(then), _coerce(else_))
        )

    def to_plan(self) -> dict[str, Any]:
        """Flatten to `{"nodes": [...], "root": i}` with children before parents.

        Postorder, so a child's index is always lower than its parent's — the
        invariant the engine validates and the reason a plan cannot contain a cycle.
        """
        nodes: list[dict[str, Any]] = []
        root = self._flatten(nodes)
        return {"nodes": nodes, "root": root}

    def _flatten(self, nodes: list[dict[str, Any]]) -> int:
        child_indices = [child._flatten(nodes) for child in self.children]
        node: dict[str, Any] = {"op": self.op}
        if self.column is not None:
            node["column"] = self.column
        elif not self.children:
            node["value"] = self.value if self.value is not None else 0.0
        if len(child_indices) >= 1:
            node["left"] = child_indices[0]
        if len(child_indices) >= 2:
            node["right"] = child_indices[1]
        if len(child_indices) >= 3:
            node["extra"] = child_indices[2]
        nodes.append(node)
        return len(nodes) - 1


def col(name: str) -> Expr:
    """A reference to a column by NAME, resolved against the batch's header.

    By name rather than index so a plan does not silently target a different column
    when the caller reorders its `columns` list.
    """
    return Expr(_OP_COL_REF, column=name)


def lit(value: float) -> Expr:
    """A literal. Floats keep their fraction: 20.5 is 20.5, not 20."""
    return Expr(_OP_LITERAL, value=float(value))


def case_when(*branches: tuple[Any, Any], else_: Any) -> Expr:
    """`CASE WHEN c1 THEN v1 WHEN c2 THEN v2 ... ELSE else_ END`.

    `branches` is a sequence of `(condition, value)` pairs, evaluated in order —
    the first condition that is known-true wins. `else_` is required: this IR has
    no literal that means "null", so there is no way to build the SQL shorthand
    of an implicit `ELSE NULL` without one; a caller that wants that passes a
    column reference or expression that is actually null on the rows it should
    cover.

    Builds a chain of ternary nodes, innermost first — `case_when((c1, v1),
    (c2, v2), else_=v3)` becomes `if_else(c1, v1, if_else(c2, v2, v3))` — the
    same "chain of binary/ternary nodes" shape `__and__`/`__or__` already use for
    `a & b & c`; this IR has no N-ary node.

    An unknown (null) condition takes the NEXT branch (or `else_`), exactly like
    a single `if_else` — never mistaken for "no branch matched, so the whole
    CASE is null".
    """
    if not branches:
        raise ValueError("case_when needs at least one (condition, value) pair")
    result = _coerce(else_)
    for cond, then in reversed(branches):
        result = _coerce(cond).if_else(then, result)
    return result


def _coerce(value: Any) -> Expr:
    if isinstance(value, Expr):
        return value
    if isinstance(value, bool):
        # Before the int check: bool is a subclass of int, and a silent 1/0 here would
        # make `col("x") > True` mean `> 1`.
        return lit(1.0 if value else 0.0)
    if isinstance(value, (int, float)):
        return lit(float(value))
    raise TypeError(
        f"cannot use {type(value).__name__} in an expression; "
        "use a number, or col(name) for a column"
    )


@dataclass(frozen=True)
class QueryResult:
    """A query's output columns, its lineage and its plan hash."""

    columns: list[str]
    rows: list[list[float | None]]
    lineage: list[dict[str, Any]]
    plan_hash: str
    ops: int
    latency_ms: float
    non_finite_cells: int = 0
    """How many result cells held a value that is not a real number, and so arrive as `None`.

    The engine computes this and puts it on the wire specifically so a `None` is not ambiguous, and
    the SDK used to drop it — which threw away the only signal distinguishing an OVERFLOWED cell
    from a genuinely absent one. `[[1, 1e308], [1, 1e308]]` summed by `partition_total` overflows to
    infinity, which is not representable in JSON, so the cell is sent as null with this counter at
    1; without the counter that is indistinguishable from a row that simply had no value. A nonzero
    count means some `None` in `rows` is an arithmetic failure, not a missing datum.
    """

    def __len__(self) -> int:
        return len(self.rows)

    def column(self, name: str) -> list[float | None]:
        """One output column by name. Raises if the plan did not produce it."""
        try:
            index = self.columns.index(name)
        except ValueError:
            raise KeyError(
                f"the result has no column {name!r}; it has {self.columns}"
            ) from None
        return [row[index] for row in self.rows]

    def to_dicts(self) -> list[dict[str, float | None]]:
        """Rows as dicts. Convenience only — `rows` is the columnar-friendly form."""
        return [dict(zip(self.columns, row)) for row in self.rows]


@dataclass
class Query:
    """A columnar query plan. Each method appends an operator and returns self.

    Mutable and chained rather than immutable-and-copied: a plan is built once and
    run once, and copying at every step would allocate a list per operator for no
    benefit a caller can observe.
    """

    columns: list[str]
    rows: list[list[Any]] | None = None
    dataset: str | None = None
    strict: bool = False
    ops: list[dict[str, Any]] = field(default_factory=list)
    # Side tables for `join`, alongside the plan rather than inside an op: `plan_hash`
    # is over `ops` only, so rows in an op would make the hash data-dependent and two
    # runs of the same computation over different data would stop comparing.
    tables: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("a query needs a non-empty columns list")
        if self.rows is None and self.dataset is None:
            raise ValueError("a query needs either rows or a dataset handle")
        if self.rows is not None and self.dataset is not None:
            raise ValueError(
                "pass rows OR dataset, not both — sending both would leave which one "
                "is authoritative up to the engine"
            )
        # Tables handed to the constructor go through the same normalisation as
        # `with_table`, so there is one definition of a valid table entry rather than
        # a validated path and an unvalidated one.
        if self.tables:
            supplied = list(self.tables)
            self.tables = []
            for entry in supplied:
                if not isinstance(entry, dict):
                    raise QueryError(
                        "invalid_arguments",
                        f"a table must be a dict, not {type(entry).__name__}",
                    )
                self.with_table(
                    entry.get("name"),
                    entry.get("columns"),
                    rows=entry.get("rows"),
                    dataset=entry.get("dataset"),
                )

    # ── operators ─────────────────────────────────────────────────────────────
    def filter(self, predicate: Expr) -> Query:
        """Keep rows where `predicate` is present AND true.

        A row whose predicate is *unknown* (any operand absent) does not pass. It is
        not false — the engine distinguished them — but it is not true either.
        """
        self.ops.append({"op": "filter", "predicate": predicate.to_plan()})
        return self

    def project(self, **expressions: Expr) -> Query:
        """Compute one output column per keyword argument.

        Expressions share one node array, so two outputs reusing a subexpression
        evaluate it once.
        """
        if not expressions:
            raise ValueError("project needs at least one expression")
        nodes: list[dict[str, Any]] = []
        roots: list[int] = []
        names: list[str] = []
        for name, expression in expressions.items():
            roots.append(expression._flatten(nodes))
            names.append(name)
        self.ops.append(
            {
                "op": "project",
                "expressions": {"nodes": nodes, "roots": roots},
                "names": names,
            }
        )
        return self

    def select(self, *names: str) -> Query:
        """Keep these columns, in this order. No expression evaluation."""
        if not names:
            raise ValueError("select needs at least one column name")
        self.ops.append({"op": "select", "columns": list(names)})
        return self

    def group_by(
        self,
        by: str | list[str],
        value: str,
        *,
        agg: str = "sum",
    ) -> Query:
        """Aggregate `value` grouped by `by`, in one pass.

        Rows whose GROUP KEY is absent join no group and are counted separately —
        folding them together would invent a category. A group with nothing to
        average has no mean (absent), while its count and sum are a real 0.
        """
        if agg not in _ACCEPTED_AGGREGATIONS:
            raise ValueError(
                f"unknown aggregation {agg!r}; accepted: {', '.join(_ACCEPTED_AGGREGATIONS)}"
            )
        self.ops.append({"op": "aggregate", "by": by, "value": value, "agg": agg})
        return self

    def group_by_many(
        self, by: str | list[str], aggs: list[tuple[str, str]]
    ) -> Query:
        """Aggregate SEVERAL `(value, agg)` pairs grouped by `by`, in ONE pass.

        A separate method rather than widening `group_by`'s own signature: every
        existing `group_by(by, value, agg=...)` caller passes `value` positionally
        as a single column name, so accepting a list there too would make the
        SAME argument mean two different shapes depending on its type — the same
        overload trap `sort`'s `desc` already avoids by keying off `by`'s type
        instead. This method exists for the new shape only.

        The engine runs every pair in the SAME grouped scan
        (`group_by_many`/`group_by_composed_parallel` in `aggregate.mojo`) rather
        than one full rescan per pair — the fix is one op emitting
        `"aggs":[{"value":...,"agg":...}, ...]` instead of N `group_by` calls, and
        it is why this exists as its own op payload rather than as sugar that
        expands into N `.group_by(...)` calls on this builder.

        Output columns are named `<agg>_<value>` per pair, same as `group_by`,
        in the order given — a duplicate `(value, agg)` pair is legal (two
        identical output columns) exactly as two chained `group_by` calls would
        be, and is not deduplicated here.
        """
        if not aggs:
            raise ValueError("group_by_many needs a non-empty list of (value, agg) pairs")
        resolved: list[dict[str, str]] = []
        for value, agg in aggs:
            if agg not in _ACCEPTED_AGGREGATIONS:
                raise ValueError(
                    f"unknown aggregation {agg!r}; accepted:"
                    f" {', '.join(_ACCEPTED_AGGREGATIONS)}"
                )
            resolved.append({"value": value, "agg": agg})
        self.ops.append({"op": "aggregate", "by": by, "aggs": resolved})
        return self

    def sort(
        self,
        by: str | list[str],
        *,
        desc: bool | list[bool] = False,
        nulls_last: bool = True,
    ) -> Query:
        """Stable sort. Ties keep their input order.

        `nulls_last` applies in BOTH directions: a null is not a large number, so
        `desc=True` must not answer with the rows that have no value.
        """
        op: dict[str, Any] = {"op": "sort", "by": by, "nulls_last": nulls_last}
        if isinstance(by, list):
            op["desc"] = desc if isinstance(desc, list) else [bool(desc)] * len(by)
        else:
            if isinstance(desc, list):
                raise ValueError("desc may only be a list when `by` is a list")
            op["desc"] = bool(desc)
        self.ops.append(op)
        return self

    def top_k(
        self, by: str, k: int, *, desc: bool = True, nulls_last: bool = True
    ) -> Query:
        """The k best rows without sorting the rest — O(n·k) and O(k) memory.

        Agrees with `sort` on ordering, not merely on the set.
        """
        op_index = len(self.ops)
        self.ops.append(
            {
                "op": "top_k",
                "by": by,
                "k": _wire_int(k, "top_k 'k'", op_index),
                "desc": desc,
                "nulls_last": nulls_last,
            }
        )
        return self

    def distinct(self, *names: str) -> Query:
        """First row of each distinct combination, in first-seen order.

        Two rows absent in the same column are the SAME row here — deliberately
        unlike `==`, where `null = null` is unknown. DISTINCT asks whether two rows
        are the same row.
        """
        self.ops.append({"op": "distinct", "columns": list(names)})
        return self

    def limit(self, count: int, *, offset: int = 0) -> Query:
        """A row window. Clamps; a window past the end is empty."""
        op_index = len(self.ops)
        self.ops.append(
            {
                "op": "limit",
                "offset": _wire_int(offset, "limit 'offset'", op_index),
                "count": _wire_int(count, "limit 'count'", op_index),
            }
        )
        return self

    # ── side tables, for join ──────────────────────────────────────────────────
    def with_table(
        self,
        name: str,
        columns: list[str],
        *,
        rows: list[list[Any]] | None = None,
        dataset: str | None = None,
    ) -> Query:
        """Declare a named table a later `join` can name. Sent once per request.

        A table lives beside the plan, not inside an op, for three reasons: `plan_hash`
        covers `ops`, so rows in an op would make the hash data-dependent; a table
        joined twice would otherwise be sent and parsed twice; and a 20-op plan over
        one dimension table would ship it 20 times.

        `rows` inlines the data — reachable from every binding. `dataset` references a
        handle from `open_dataset` instead, which makes the per-request payload O(1) in
        rows, and is a Python-side optimisation only: handles are scoped to a worker
        connection. The op JSON is byte-identical either way; it only ever says
        `"table": "<name>"`.

        Engine bounds, enforced there and reported with the number it measured: at most
        8 side tables per request (`MAX_TABLES`); at most 512 columns in a table's
        header (`MAX_COLUMNS`); and at most 32,000,000 cells — rows x columns —
        SUMMED over every side table in the request (`MAX_MATERIALIZED_CELLS`), a
        budget a join's own output draws on as well. A per-table ceiling would not be a
        bound: eight tables each under it allocate eight times it.
        """
        if not isinstance(name, str) or not name:
            raise QueryError("invalid_arguments", "a table needs a non-empty name")
        if any(table["name"] == name for table in self.tables):
            raise QueryError(
                "invalid_arguments", f"table {name!r} is declared twice"
            )
        if not columns or not isinstance(columns, (list, tuple)):
            raise QueryError(
                "invalid_arguments",
                f"table {name!r} needs a non-empty columns list",
            )
        if (rows is None) == (dataset is None):
            raise QueryError(
                "invalid_arguments",
                f"table {name!r} needs exactly one of rows or dataset; sending both "
                "would leave which one is authoritative up to the engine, and neither "
                "leaves the join with nothing to read",
            )
        entry: dict[str, Any] = {"name": name, "columns": [str(c) for c in columns]}
        if dataset is not None:
            if not isinstance(dataset, str) or not dataset:
                raise QueryError(
                    "invalid_arguments",
                    f"table {name!r} has an empty dataset handle",
                )
            entry["dataset"] = dataset
        else:
            entry["rows"] = _normalize_rows(rows or [], len(entry["columns"]))
        self.tables.append(entry)
        return self

    # ── join ──────────────────────────────────────────────────────────────────
    def join(
        self,
        table: str,
        *,
        on: str | None = None,
        left_on: str | None = None,
        right_on: str | None = None,
        how: str = "inner",
        method: str = "hash",
        prefix: str | None = None,
    ) -> Query:
        """Join a named side table on ONE equality key.

        `how`: `inner`, `left`, `semi` or `anti`. `semi` keeps a left row that has a
        partner and `anti` keeps one known to have none — left columns only, one row out
        per row in, so they cannot fan out. They are SQL's `IN` / `NOT IN`, not
        `EXISTS` / `NOT EXISTS`: a left row whose key is NULL is excluded from BOTH
        results, because it does not match and it is not *known* not to match either.
        `right`, `outer`, `full` and `cross` are rejected by name rather than quietly
        mapped to `left`.

        A null key matches nothing, deliberately unlike `distinct` where two rows
        missing the same field are the same row: a join is a sequence of equality tests
        and `null = null` is unknown. Under `inner` such a row disappears; under `left`
        it survives once with nulls across the right columns.

        Duplicate keys multiply: three left rows and two right rows sharing a key are
        six output rows, which is what a join means and the usual source of a surprise
        count. The engine bounds that product before allocating it — at most 1,000,000
        output rows (`MAX_JOIN_OUTPUT_ROWS`) and at most 32,000,000 output cells
        (`MAX_MATERIALIZED_CELLS`, the same budget the side tables draw on) — and
        refuses rather than truncating, since a truncated join is a wrong answer
        carrying a success status.

        `method="merge"` walks two already-sorted inputs with no hash table. A plan
        cannot sort a side table, so it is only usable when the table arrives sorted
        ascending with nulls last.

        `method="direct_address"` is a CALLER-DECLARED contract, not a hint: it asserts
        the right key is an integer inside one bounded range, present at most once per
        value (a bijection between the key and a right row) — e.g. a dense surrogate id.
        When that holds, the engine skips the hash table entirely and probes a flat
        array instead, which measured 1.88x faster end to end on the one real shape this
        was built for (see `benchmarks/h2o_join/RESULTS.md`'s Update #6). When it does
        NOT hold — a fractional key, or any duplicate — the engine RAISES rather than
        silently falling back to `method="hash"`, because a wrong guess here already
        did real, non-trivial wasted work (a full scatter and occupancy scan) finding
        that out; use `method="hash"` unless the right key's shape is actually known.

        `prefix` (default `"<table>."`) is prepended to every right column name.
        `Schema.index_of` returns the first match, so two columns answering to one name
        would silently resolve every later reference to the left one — which is why the
        engine rejects a collision instead of accepting it.
        """
        op_index = len(self.ops)
        if not isinstance(table, str) or not table:
            raise QueryError("invalid_arguments", "join requires 'table'", op_index)
        if how in _UNIMPLEMENTED_JOIN_HOW:
            raise QueryError(
                "invalid_arguments",
                f"join 'how' must be {_english(_ACCEPTED_JOIN_HOW)}; got {how!r} "
                "(right, outer, full and cross joins are not implemented)",
                op_index,
            )
        if how not in _ACCEPTED_JOIN_HOW:
            raise QueryError(
                "invalid_arguments",
                f"join 'how' must be {_english(_ACCEPTED_JOIN_HOW)}; got {how!r}",
                op_index,
            )
        if method not in _ACCEPTED_JOIN_METHODS:
            raise QueryError(
                "invalid_arguments",
                f"join 'method' must be {_english(_ACCEPTED_JOIN_METHODS)}; got "
                f"{method!r}",
                op_index,
            )
        if method != "hash" and how in _JOIN_HOW_WITHOUT_RIGHT_COLUMNS:
            raise QueryError(
                "invalid_arguments",
                f"join method {method!r} is not defined for how {how!r}",
                op_index,
            )
        if on is not None:
            if left_on is not None or right_on is not None:
                raise QueryError(
                    "invalid_arguments",
                    "join takes 'on', or both 'left_on' and 'right_on', not a mix — "
                    "which key applies would be left to the engine",
                    op_index,
                )
            left_key, right_key = on, on
        else:
            if left_on is None or right_on is None:
                raise QueryError(
                    "invalid_arguments",
                    "join requires 'on', or both 'left_on' and 'right_on'",
                    op_index,
                )
            left_key, right_key = left_on, right_on
        for label, key in (("left_on", left_key), ("right_on", right_key)):
            if not isinstance(key, str) or not key:
                raise QueryError(
                    "invalid_arguments",
                    f"join {label!r} must be a single column name (a composite key "
                    "would be a different algorithm and is not implemented)",
                    op_index,
                )
        if prefix is not None and how in _JOIN_HOW_WITHOUT_RIGHT_COLUMNS:
            raise QueryError(
                "invalid_arguments",
                f"join how {how!r} emits no right columns, so 'prefix' would have no "
                "effect; drop it or use how 'inner' or 'left'",
                op_index,
            )

        op: dict[str, Any] = {
            "op": "join",
            "table": table,
            "left_on": left_key,
            "right_on": right_key,
            "how": how,
            "method": method,
        }
        # Emitted only when asked for: the engine's default is `"<table>."`, and
        # spelling the default out here would make this builder's plan hash differ
        # from an equivalent plan built by another binding.
        if prefix is not None:
            if not isinstance(prefix, str) or not prefix:
                raise QueryError(
                    "invalid_arguments",
                    "an empty join prefix is not expressible — it can only ask for a "
                    "name collision; omit prefix for the default '<table>.'",
                    op_index,
                )
            op["prefix"] = prefix
        self.ops.append(op)
        return self

    def union(self, *tables: str) -> Query:
        """UNION ALL onto one or more named side tables (see `with_table`).

        Concatenates rows: the running plan's rows first, then each named table's,
        in the given order — no deduplication. `DISTINCT` is already its own
        operator (`Query` has none yet at the top level, but the engine's
        `distinct` op is reachable the same way `select`/`sort` are); chain one
        after `union` for UNION DISTINCT rather than asking this method to
        de-duplicate unconditionally, which would charge every already-unique
        union (the common case: TPC-DS's channel unions never need it) for a
        scan it does not want.

        Columns are matched BY NAME against this plan's own columns/output at the
        point `union` runs, not by position, so an operand may declare its columns
        in a different order and still union correctly. Column COUNT must match on
        every operand; the engine reports a mismatch by table name.

        A table is declared once with `with_table` and can be named here (and by
        `join`) any number of times — the same "table lives beside the plan"
        reason `join` already has: `plan_hash` is over `ops`, not table bodies, so
        the table is parsed once regardless of how many ops reference it.
        """
        op_index = len(self.ops)
        if not tables:
            raise QueryError(
                "invalid_arguments", "union needs at least one table name", op_index
            )
        for table in tables:
            if not isinstance(table, str) or not table:
                raise QueryError(
                    "invalid_arguments",
                    "union table names must be non-empty strings",
                    op_index,
                )
        self.ops.append({"op": "union", "tables": list(tables)})
        return self

    # ── window ────────────────────────────────────────────────────────────────
    def window(
        self,
        fn: str,
        *,
        name: str,
        partition_by: str | list[str] | None = None,
        order_by: str | list[str] | None = None,
        desc: bool | list[bool] | None = None,
        value: str | None = None,
        agg: str | None = None,
        offset: int | None = None,
        preceding: int | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """Append ONE window column, keeping row order exactly as it is.

        `name` becomes the wire key `"as"` (`as` is a Python keyword) and is REQUIRED:
        every default is either ambiguous — two frames over `amount` both wanting
        `sum_amount` — or collides with an existing column, and `Schema.index_of`
        returns the first match so a collision silently shadows.

        Row order is NOT changed. `partition_rows` computes an internal ordering but
        the batch is not permuted into it, because permuting would silently change what
        a following `limit` or `top_k` means. Add a `sort` op afterwards for window
        order.

        `partition_by` may be empty: one partition over everything, which is what
        `OVER (ORDER BY ...)` means. A null partition key forms its OWN single
        partition — unlike `group_by`, where a null group key joins no group.

        Offsets and frames stop at the partition edge and yield an absence there, never
        the neighbouring partition's row.

        Engine bounds: a window op accepts at most 20,000 input rows
        (`MAX_WINDOW_ROWS`) — it orders the RAW rows, and the cost of that grows
        quadratically, so a larger batch is REFUSED with a message naming the ops that
        reduce rows first, an honest error being better than a request that never
        returns. Reduce first with `filter`, `group_by`, `top_k` or `limit`. The
        appended column also counts against the 512-column ceiling (`MAX_COLUMNS`), so a
        batch already at 512 columns has no room for one.
        """
        op_index = len(self.ops)
        if fn not in _ACCEPTED_WINDOW_FNS:
            raise QueryError(
                "invalid_arguments",
                f"window 'fn' must be {_english(_ACCEPTED_WINDOW_FNS)}; got {fn!r}",
                op_index,
            )
        if not isinstance(name, str) or not name:
            raise QueryError(
                "invalid_arguments",
                "window requires 'as' (the output column name)",
                op_index,
            )

        partitions = _as_name_list(partition_by, "partition_by", op_index)
        orders = _as_name_list(order_by, "order_by", op_index)

        if fn in _WINDOW_FNS_NEEDING_ORDER and not orders:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} requires a non-empty 'order_by'",
                op_index,
            )
        if fn in _WINDOW_FNS_NEEDING_ONE_ORDER and len(orders) != 1:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} requires exactly one 'order_by' column; "
                f"got {len(orders)}",
                op_index,
            )

        desc_list: list[bool] | None = None
        if desc is not None:
            if isinstance(desc, bool):
                desc_list = [desc] * len(orders)
            elif isinstance(desc, (list, tuple)):
                desc_list = [bool(d) for d in desc]
            else:
                raise QueryError(
                    "invalid_arguments",
                    "window 'desc' must be a bool or a list of bools",
                    op_index,
                )
            # One boolean per order column. A short list silently leaves the trailing
            # keys ascending, which is a different ordering and hence different ranks.
            if len(desc_list) != len(orders):
                raise QueryError(
                    "invalid_arguments",
                    "window 'desc' must be an array of one boolean per 'order_by' "
                    f"column ({len(orders)} expected, {len(desc_list)} given)",
                    op_index,
                )

        if fn in _WINDOW_FNS_TAKING_VALUE:
            if not isinstance(value, str) or not value:
                raise QueryError(
                    "invalid_arguments",
                    f"window fn {fn!r} requires 'value'",
                    op_index,
                )
        elif value is not None:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} takes no 'value'",
                op_index,
            )

        if fn in _WINDOW_FNS_TAKING_AGG:
            if agg is None:
                raise QueryError(
                    "invalid_arguments",
                    f"window fn {fn!r} requires 'agg'",
                    op_index,
                )
            if agg not in _ACCEPTED_WINDOW_AGGREGATIONS:
                raise QueryError(
                    "invalid_arguments",
                    "window 'agg' must be sum, avg, min, max or count; "
                    f"got {agg!r} (var, std and median are not defined over a window "
                    "frame here)",
                    op_index,
                )
        elif agg is not None:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} takes no 'agg'",
                op_index,
            )

        offset_value = 1
        if fn in _WINDOW_FNS_TAKING_OFFSET:
            offset_value = (
                1
                if offset is None
                else _wire_int(offset, f"window fn {fn!r} 'offset'", op_index)
            )
            if offset_value < 1:
                # A signed offset is deliberately not the wire API: "lag" with -1 would
                # silently be a lead.
                raise QueryError(
                    "invalid_arguments",
                    f"window fn {fn!r} requires 'offset' >= 1",
                    op_index,
                )
        elif offset is not None:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} takes no 'offset'",
                op_index,
            )

        preceding_value = 0
        if fn == "framed":
            if preceding is None:
                raise QueryError(
                    "invalid_arguments",
                    "window fn 'framed' requires 'preceding' >= 0; use fn 'cumulative' "
                    "for an unbounded frame",
                    op_index,
                )
            preceding_value = _wire_int(
                preceding, "window fn 'framed' 'preceding'", op_index
            )
            if preceding_value < 0:
                # -1 is FRAME_UNBOUNDED inside the kernel and never appears on the
                # wire, so a stray -1 cannot turn a rolling frame into a cumulative one.
                raise QueryError(
                    "invalid_arguments",
                    "window fn 'framed' requires 'preceding' >= 0; use fn 'cumulative' "
                    "for an unbounded frame",
                    op_index,
                )
        elif preceding is not None:
            raise QueryError(
                "invalid_arguments",
                f"window fn {fn!r} takes no 'preceding'; use fn 'framed' for a rolling "
                "frame",
                op_index,
            )

        op: dict[str, Any] = {
            "op": "window",
            "fn": fn,
            "as": name,
            "nulls_last": bool(nulls_last),
        }
        if partitions:
            op["partition_by"] = partitions
        if orders:
            op["order_by"] = orders
        if desc_list is not None:
            op["desc"] = desc_list
        if value is not None:
            op["value"] = value
        if agg is not None:
            op["agg"] = agg
        if fn in _WINDOW_FNS_TAKING_OFFSET:
            op["offset"] = offset_value
        if fn == "framed":
            op["preceding"] = preceding_value
        self.ops.append(op)
        return self

    # ── window sugar: the same op, spelled as the function it computes ─────────
    def row_number(
        self,
        *,
        name: str,
        order_by: str | list[str],
        partition_by: str | list[str] | None = None,
        desc: bool | list[bool] | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """1-based position within the partition. Never null, never tied."""
        return self.window(
            "row_number",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            nulls_last=nulls_last,
        )

    def rank(
        self,
        *,
        name: str,
        order_by: str,
        partition_by: str | list[str] | None = None,
        desc: bool | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """Competition rank: 10,20,20,30 -> 1,2,2,4. Gaps after a tie."""
        return self.window(
            "rank",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            nulls_last=nulls_last,
        )

    def dense_rank(
        self,
        *,
        name: str,
        order_by: str,
        partition_by: str | list[str] | None = None,
        desc: bool | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """Dense rank: 10,20,20,30 -> 1,2,2,3. No gaps."""
        return self.window(
            "dense_rank",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            nulls_last=nulls_last,
        )

    def lag(
        self,
        value: str,
        *,
        name: str,
        order_by: str | list[str],
        partition_by: str | list[str] | None = None,
        offset: int = 1,
        desc: bool | list[bool] | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """The value `offset` rows earlier in the partition; absent at the edge."""
        return self.window(
            "lag",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            value=value,
            offset=offset,
            nulls_last=nulls_last,
        )

    def lead(
        self,
        value: str,
        *,
        name: str,
        order_by: str | list[str],
        partition_by: str | list[str] | None = None,
        offset: int = 1,
        desc: bool | list[bool] | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """The value `offset` rows later in the partition; absent at the edge."""
        return self.window(
            "lead",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            value=value,
            offset=offset,
            nulls_last=nulls_last,
        )

    def running(
        self,
        value: str,
        *,
        name: str,
        order_by: str | list[str],
        partition_by: str | list[str] | None = None,
        agg: str = "sum",
        desc: bool | list[bool] | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """A running aggregate over the partition so far — the unbounded frame."""
        return self.window(
            "cumulative",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            value=value,
            agg=agg,
            nulls_last=nulls_last,
        )

    def rolling(
        self,
        value: str,
        *,
        name: str,
        order_by: str | list[str],
        preceding: int,
        partition_by: str | list[str] | None = None,
        agg: str = "sum",
        desc: bool | list[bool] | None = None,
        nulls_last: bool = True,
    ) -> Query:
        """A trailing frame of `preceding + 1` rows, clamped at the partition start."""
        return self.window(
            "framed",
            name=name,
            partition_by=partition_by,
            order_by=order_by,
            desc=desc,
            value=value,
            agg=agg,
            preceding=preceding,
            nulls_last=nulls_last,
        )

    def partition_total(
        self,
        value: str,
        *,
        name: str,
        partition_by: str | list[str] | None = None,
        agg: str = "sum",
        nulls_last: bool = True,
    ) -> Query:
        """The partition's aggregate on every row of it — a share-of-total with no join.

        Order-independent, so no `order_by`: it would change nothing.
        """
        return self.window(
            "partition_total",
            name=name,
            partition_by=partition_by,
            value=value,
            agg=agg,
            nulls_last=nulls_last,
        )

    # ── execution ─────────────────────────────────────────────────────────────
    def to_request(self) -> dict[str, Any]:
        """The wire frame this plan will send. Useful for hashing or inspection."""
        declared = [table["name"] for table in self.tables]
        for index, op in enumerate(self.ops):
            if op.get("op") == "join":
                if op.get("table") not in declared:
                    raise QueryError(
                        "invalid_arguments",
                        f"join references table {op.get('table')!r}, which the plan"
                        f" does not supply (available: {', '.join(declared) or 'none'})",
                        index,
                    )
            elif op.get("op") == "union":
                for name in op.get("tables", []):
                    if name not in declared:
                        raise QueryError(
                            "invalid_arguments",
                            f"union references table {name!r}, which the plan does"
                            f" not supply (available: {', '.join(declared) or 'none'})",
                            index,
                        )
        request: dict[str, Any] = {
            "type": "query_execute",
            "columns": list(self.columns),
            "ops": list(self.ops),
            "strict": self.strict,
        }
        if self.dataset is not None:
            request["dataset"] = self.dataset
        else:
            request["rows"] = _normalize_rows(self.rows or [], len(self.columns))
        # Only when non-empty, so every request a plan without side tables sends is
        # byte-identical to what it sent before joins existed and no plan hash moves.
        if self.tables:
            request["tables"] = [dict(table) for table in self.tables]
        return request

    def run(self, runtime: Any, *, routing_module: str = "stats") -> QueryResult:
        """Execute the whole plan in one dispatch on this device."""
        return runtime.query(self, routing_module=routing_module)


def _english(accepted: tuple[str, ...]) -> str:
    """Join names as `a, b or c` — the engine's phrasing, so both messages match."""
    if len(accepted) == 1:
        return accepted[0]
    return ", ".join(accepted[:-1]) + " or " + accepted[-1]


def _wire_int(value: Any, label: str, op_index: int | None = None) -> int:
    """An integer the engine will read back as the SAME number, or a rejection.

    Python's `int` is unbounded and the engine's JSON reader is signed 64-bit and does
    not trap on overflow, so `preceding=2**64 + 3` would cross the wire and come back as
    a three-row frame — a real answer to a question nobody asked, which is exactly what
    a status cannot rescue because nothing failed. Rejected here, where the number the
    caller wrote is still available to quote back at them.
    """
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        raise QueryError(
            "invalid_arguments",
            f"{label} must be an integer; got {value!r}",
            op_index,
        ) from None
    if number < _WIRE_INT_MIN or number > _WIRE_INT_MAX:
        raise QueryError(
            "invalid_arguments",
            f"{label} must be within {_WIRE_INT_MIN}..{_WIRE_INT_MAX}; got {number} "
            "(a plan's integers are read as signed 64-bit, so a value past that range "
            "would arrive as a different, smaller number rather than as an error)",
            op_index,
        )
    return number


def _as_name_list(
    value: str | list[str] | None, label: str, op_index: int
) -> list[str]:
    """A single name, a list of names, or nothing — always out as a list.

    Names, not indices, for the same reason every other op uses names: a reordered
    header must not retarget the plan.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        for entry in value:
            if not isinstance(entry, str) or not entry:
                raise QueryError(
                    "invalid_arguments",
                    f"window {label!r} takes column names; got {entry!r}",
                    op_index,
                )
        return [str(entry) for entry in value]
    raise QueryError(
        "invalid_arguments",
        f"window {label!r} must be a column name or a list of them",
        op_index,
    )


def _normalize_rows(rows: list[list[Any]], width: int) -> list[list[Any]]:
    """Coerce cells to float or None, and check the width.

    Done here rather than in the kernel so a bad cell is reported with its row and
    column while the caller still has the original object to look at. A row wider
    than the header is an error: the extra values have no column to belong to and
    guessing would silently drop them.
    """
    out: list[list[Any]] = []
    for r, row in enumerate(rows):
        if len(row) > width:
            raise ValueError(
                f"row {r} has {len(row)} values but the header declares {width} columns"
            )
        cells: list[Any] = []
        for c, cell in enumerate(row):
            if cell is None:
                cells.append(None)
            elif isinstance(cell, bool):
                cells.append(1.0 if cell else 0.0)
            elif isinstance(cell, (int, float)):
                cells.append(float(cell))
            else:
                raise ValueError(
                    f"row {r} column {c} is {type(cell).__name__}; "
                    "query columns are numeric or None"
                )
        out.append(cells)
    return out


def run_query(
    query: Query,
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool,
) -> QueryResult:
    """Send a plan to the bundled worker and decode the response.

    Raises `QueryError` rather than returning a failure dict: a query that did not
    run has no rows, and returning an empty result would be a correct-looking answer
    to a question that was never asked.
    """
    from time import perf_counter

    from algenta.native import worker

    started = perf_counter()
    try:
        response = worker.execute(
            query.to_request(),
            timeout=timeout,
            require_verified=require_verified,
            module_name=routing_module,
        )
    except worker.NativeWorkerUnavailable as exc:
        raise QueryError("compute_runtime_unavailable", str(exc)) from exc

    code = response.get("error_code")
    if isinstance(code, str) and code:
        op_index = response.get("op_index")
        raise QueryError(
            code,
            str(response.get("error_message") or response.get("error") or ""),
            op_index if isinstance(op_index, int) else None,
        )

    result = response.get("result") or {}
    lineage = response.get("lineage")
    return QueryResult(
        columns=list(result.get("columns") or []),
        rows=[list(row) for row in (result.get("rows") or [])],
        lineage=list(lineage) if isinstance(lineage, list) else [],
        plan_hash=str(response.get("plan_hash") or ""),
        ops=int(response.get("ops") or 0),
        latency_ms=round((perf_counter() - started) * 1000, 3),
        # Absent from the envelope when zero — the engine only emits the key when N > 0.
        non_finite_cells=int(response.get("non_finite_cells") or 0),
    )
