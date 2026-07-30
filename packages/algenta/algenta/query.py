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

_ACCEPTED_AGGREGATIONS = ("sum", "avg", "mean", "min", "max", "count", "var", "std")


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
        self.ops.append(
            {"op": "top_k", "by": by, "k": int(k), "desc": desc, "nulls_last": nulls_last}
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
        self.ops.append({"op": "limit", "offset": int(offset), "count": int(count)})
        return self

    # ── execution ─────────────────────────────────────────────────────────────
    def to_request(self) -> dict[str, Any]:
        """The wire frame this plan will send. Useful for hashing or inspection."""
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
        return request

    def run(self, runtime: Any, *, routing_module: str = "stats") -> QueryResult:
        """Execute the whole plan in one dispatch on this device."""
        return runtime.query(self, routing_module=routing_module)


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
    )
