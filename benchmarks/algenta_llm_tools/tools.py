"""Five LLM tool-calling functions over the real, public Algenta Python SDK.

Every number these tools return came out of a compiled Mojo kernel, dispatched
through the exact same public surface any other ``pip install algenta`` caller
would use (``algenta.MojoRuntime``, ``algenta.CapabilityCatalog`` via
``MojoRuntime.capabilities()``). There is no Python-side recomputation anywhere in
this module: if the runtime is unavailable or a kernel call fails, every function
here raises ``AlgentaToolError`` rather than answering from pandas/numpy. Silently
falling back would make any benchmark built on top of these tools meaningless -- the
whole point is that the LLM's answer is only as good as the real compiled kernel it
calls.

Each tool is exposed two ways: a plain Python function you can call directly, and an
OpenAI-function-calling-compatible JSON schema (``*_SCHEMA``) in the
``{"type": "function", "function": {...}}`` shape this repo's own LLM benchmark code
already speaks (see ``benchmarks/optmodel_plane/llm_e2e.py``'s ``response_format``
usage for the same JSON-schema style, applied there to structured output instead of
tool calls). ``TOOL_SCHEMAS`` / ``TOOL_FUNCTIONS`` bundle all five for a
``client.chat.completions.create(tools=TOOL_SCHEMAS, ...)`` call plus dispatch.

Design notes worth reading before wiring this into an agent loop:

* ``list_capabilities`` is discovery-only: it reads ``CapabilityCatalog.search()`` and
  never executes anything, so exploring the catalog is free of the kernel-abort risk
  below.
* ``execute`` is the one tool that runs a kernel. Its arguments are the kernel's own
  parameter names (as reported by ``runtime_library_contract`` and ``explain``) -- this
  first version intentionally does not build a query-plan-authoring layer on top; the
  model calls the stats/etc. function directly, which is simpler and more honest about
  what actually ran.
* An LLM-supplied *element count* argument (a kernel parameter like ``n`` that must
  equal the length of some other list argument) is the single most dangerous kind of
  bad tool-call argument here: a kernel trusts the count it is given, and a count larger
  than the list backing it fires an uncatchable bounds assertion that kills the whole
  worker process outright (no exception to catch, no way to recover the process for the
  *next* call either). ``execute`` defends against this for every count relation the
  catalog has actually DECLARED (``_apply_count_relations`` below) by overwriting the
  supplied count with the real, measured length rather than trusting the model's
  arithmetic. Declaration coverage is not total across the kernel library (see
  ``CapabilityRecord``'s own "undeclared is not false" philosophy in
  ``algenta/capabilities.py``) -- callers passing a function whose count relation is
  undeclared must still supply a consistent count themselves.
* Every result is truncated for the model's context (see ``truncate.py``) before it
  comes back from ``execute``; the untruncated value stays retrievable via
  ``result_id``/``get_stored_result``.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from algenta import (
    UNDECLARED,
    CapabilityError,
    MojoExecutionError,
    MojoFunctionNotRegisteredError,
    MojoModuleNotRegisteredError,
    MojoRuntime,
)
from algenta.runtime_library_contract import RuntimeFunctionSpec, runtime_modules

from .truncate import get_stored_result, shape_for_model, store_result

__all__ = [
    "AlgentaToolError",
    "list_capabilities",
    "execute",
    "explain",
    "get_column",
    "group_by_aggregate",
    "configure_dataset",
    "get_stored_result",
    "LIST_CAPABILITIES_SCHEMA",
    "EXECUTE_SCHEMA",
    "EXPLAIN_SCHEMA",
    "GET_COLUMN_SCHEMA",
    "GROUP_BY_AGGREGATE_SCHEMA",
    "TOOL_SCHEMAS",
    "TOOL_FUNCTIONS",
]


class AlgentaToolError(RuntimeError):
    """One of the three tools could not be satisfied by the real Algenta runtime.

    Raised instead of returning a degraded/estimated answer. Callers (an LLM tool-call
    loop, or a human) should surface this to whoever is deciding what to do next -- it
    is never appropriate to catch this and substitute a Python-computed number.
    """


# ── runtime + contract access ────────────────────────────────────────────────────

_runtime: MojoRuntime | None = None


def _rt() -> MojoRuntime:
    """The one MojoRuntime this process uses, constructed lazily and reused.

    ``mode="local"`` is the only mode the public SDK supports today (see
    ``mojo_runtime._validate_runtime_config``); it dispatches to the bundled native
    worker, never to a Python fallback.
    """
    global _runtime
    if _runtime is None:
        _runtime = MojoRuntime(mode="local")
    return _runtime


@lru_cache(maxsize=1)
def _signature_index() -> dict[tuple[str, str], RuntimeFunctionSpec]:
    """(module, function) -> its real signature, straight from the shipped contract."""
    index: dict[tuple[str, str], RuntimeFunctionSpec] = {}
    for module in runtime_modules():
        for function_spec in module.functions:
            index[(module.import_path, function_spec.name)] = function_spec
    return index


def _render_signature(spec: RuntimeFunctionSpec | None) -> str:
    if spec is None:
        return "(signature unavailable)"
    params = ", ".join(
        f"{param.name}: {param.typ}{' = <default>' if param.has_default else ''}"
        for param in spec.params
    )
    return f"({params}) -> {spec.return_type}"


def _declared_bits(record: Any) -> list[str]:
    bits: list[str] = []
    for name in ("deterministic", "complexity", "backend", "seed_requirements"):
        value = getattr(record, name)
        if value is not UNDECLARED:
            bits.append(f"{name}={value}")
    return bits


# ── tool 1: list_capabilities ─────────────────────────────────────────────────────

LIST_CAPABILITIES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_capabilities",
        "description": (
            "Discover what Algenta's compiled Mojo kernel library can compute. Search "
            "by a module-name substring (e.g. 'stats') or a function-name substring "
            "(e.g. 'percentile') and get back matching module.function names with their "
            "real signatures and, where declared, a one-line note on determinism/cost. "
            "Call this before execute() so you use exact, real names -- it never "
            "executes anything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A substring to match against module names or function names, "
                        "case-insensitive, e.g. 'stats', 'percentile', 'optimiz'."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of matches to return (default 15).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def list_capabilities(query: str, limit: int = 15) -> list[dict[str, Any]]:
    """Matching module.function names + a one-line description, real signature included.

    Two matching modes, merged: every function of every module whose NAME contains
    `query`, and every function whose OWN name contains `query` (via
    ``CapabilityCatalog.search(function=...)``, which is a plain substring match and
    never raises for a query that matches nothing). A capability with no declared
    metadata still comes back -- with only its signature -- rather than being dropped;
    "nobody has said" is not the same as "this doesn't exist" anywhere in this catalog.
    """
    if not isinstance(query, str) or not query.strip():
        raise AlgentaToolError("query must be a non-empty string.")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise AlgentaToolError("limit must be a positive integer.")

    needle = query.strip().lower()
    catalog = _rt().capabilities()
    sig_index = _signature_index()

    candidates: dict[tuple[str, str], Any] = {}
    for module_name in catalog.modules():
        if needle in module_name.lower():
            for function_name in catalog.functions(module_name):
                candidates.setdefault((module_name, function_name), None)

    search_result = catalog.search(function=needle, limit=max(limit * 4, 60))
    for record in search_result.matches:
        candidates[(record.module, record.function)] = record
    for undeclared in search_result.undeclared:
        candidates.setdefault((undeclared.module, undeclared.function), None)

    out: list[dict[str, Any]] = []
    for module_name, function_name in sorted(candidates)[: limit * 4]:
        if len(out) >= limit:
            break
        record = candidates[(module_name, function_name)]
        if record is None:
            try:
                record = catalog.describe(module_name, function_name)
            except CapabilityError:
                continue
        signature = _render_signature(sig_index.get((module_name, function_name)))
        bits = _declared_bits(record)
        description = f"{module_name}.{function_name}{signature}"
        if bits:
            description += " -- " + ", ".join(bits)
        out.append(
            {
                "module": module_name,
                "function": function_name,
                "signature": signature,
                "description": description,
            }
        )
    return out


# ── tool 2: execute ───────────────────────────────────────────────────────────────

EXECUTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute",
        "description": (
            "Run one real, compiled Mojo kernel and return its answer -- the actual "
            "computation, never estimated or recomputed in Python. Call list_capabilities "
            "and/or explain first to get the exact module name, function name, and "
            "parameter names; args must use those exact parameter names as keys. Large "
            "results are truncated for context (see 'truncated'/'element_count'); the "
            "full result stays retrievable via 'result_id'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Exact module name, e.g. 'stats'."},
                "function": {
                    "type": "string",
                    "description": "Exact function name within that module, e.g. 'quantile'.",
                },
                "args": {
                    "type": "object",
                    "description": (
                        "Keyword arguments by the kernel's own parameter names, e.g. "
                        "{'v': [1.0, 2.0, 3.0], 'n': 3, 'q': 0.9} for stats.quantile. "
                        "Omit any parameter that is a declared element-count for another "
                        "list argument -- it is filled in from the real length "
                        "automatically."
                    ),
                },
            },
            "required": ["module", "function"],
            "additionalProperties": False,
        },
    },
}


def _apply_count_relations(module: str, function: str, args: dict[str, Any]) -> dict[str, Any]:
    """Overwrite every DECLARED single-factor element-count arg with the real length.

    A kernel's element-count parameter is not validated by the kernel itself -- passing
    one larger than the list it bounds aborts the whole worker process, uncatchably (see
    the module docstring). Every relation the catalog has declared with exactly one
    factor and one bound list is therefore enforced here from the measured length,
    regardless of what the caller supplied. A relation with more than one factor (e.g.
    matrix dimensions, which cannot be recovered from a single list length) or a function
    whose relation is undeclared is left untouched -- silently overwriting an unread
    declaration would be a guess, not an enforcement of a real contract.
    """
    try:
        record = _rt().capabilities().describe(module, function)
    except CapabilityError:
        return args
    relations = record.count_relations
    if relations is UNDECLARED:
        return args
    fixed = dict(args)
    for relation in relations:
        if len(relation.factors) != 1 or len(relation.bounds) != 1:
            continue
        bound_value = fixed.get(relation.bounds[0])
        if not isinstance(bound_value, list):
            continue
        fixed[relation.factors[0]] = max(0, len(bound_value) - relation.plus)
    return fixed


def _resolve_result_refs(args: dict[str, Any]) -> dict[str, Any]:
    """Let an ``args`` value stand in for a previously stored large result.

    A tool-calling model cannot literally retype a 29,000-element column back into a
    ``execute`` call's JSON arguments -- it never saw those values in the first place
    (only a truncated preview came back from ``get_column``/a prior ``execute``). The
    convention here mirrors the *output* side's existing "keep the full value, hand back
    a short id" discipline (``truncate.py``) and extends it to *inputs*: an argument
    value of the shape ``{"result_id": "<id>"}`` is swapped for the full stored value
    (via ``get_stored_result``) before dispatch, so a real, full-size array can move
    from one tool call to the next without ever being re-serialized into the model's
    context. A malformed/unknown ``result_id`` raises ``AlgentaToolError`` rather than
    silently passing the literal dict through to the kernel.
    """
    resolved: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, dict) and set(value.keys()) == {"result_id"}:
            try:
                resolved[key] = get_stored_result(value["result_id"])
            except KeyError as exc:
                raise AlgentaToolError(str(exc)) from exc
        else:
            resolved[key] = value
    return resolved


def execute(module: str, function: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call one real kernel through the real SDK and shape its result for a model.

    Raises ``AlgentaToolError`` for an unknown module/function or a kernel-reported
    failure -- never returns a guessed or Python-recomputed value. This is the tool that
    actually runs compute; ``list_capabilities``/``explain``/``get_column`` never do.
    """
    if not isinstance(module, str) or not module.strip():
        raise AlgentaToolError("module must be a non-empty string.")
    if not isinstance(function, str) or not function.strip():
        raise AlgentaToolError("function must be a non-empty string.")
    module = module.strip()
    function = function.strip()
    payload = _resolve_result_refs(dict(args or {}))
    payload = _apply_count_relations(module, function, payload)

    try:
        library_module = _rt().libraries()[module]
    except MojoModuleNotRegisteredError as exc:
        raise AlgentaToolError(str(exc)) from exc
    try:
        kernel = getattr(library_module, function)
    except MojoFunctionNotRegisteredError as exc:
        raise AlgentaToolError(str(exc)) from exc

    started = time.perf_counter()
    try:
        result = kernel(**payload) if payload else kernel()
    except MojoExecutionError as exc:
        raise AlgentaToolError(f"{module}.{function} failed on the real runtime: {exc}") from exc
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    shaped = shape_for_model(result)
    return {
        "module": module,
        "function": function,
        "value": shaped["value"],
        "truncated": shaped["truncated"],
        "element_count": shaped.get("element_count"),
        "result_id": store_result(result),
        "latency_ms": latency_ms,
        "engine": "mojo",
    }


# ── tool 3: explain ────────────────────────────────────────────────────────────────

EXPLAIN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "explain",
        "description": (
            "Get the real signature and declared metadata for one capability -- exact "
            "parameter names/types, return type, and (where the kernel author declared "
            "them) determinism, cost, backend, seed requirements, and element-count "
            "relations between parameters. Use this to check how to call execute() "
            "correctly, or to answer a 'how/why does this work' question, without "
            "running anything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Exact module name, e.g. 'stats'."},
                "function": {
                    "type": "string",
                    "description": "Exact function name, e.g. 'quantile'.",
                },
            },
            "required": ["module", "function"],
            "additionalProperties": False,
        },
    },
}


def explain(module: str, function: str) -> str:
    """The real signature plus every declared capability field, as prose."""
    if not isinstance(module, str) or not module.strip():
        raise AlgentaToolError("module must be a non-empty string.")
    if not isinstance(function, str) or not function.strip():
        raise AlgentaToolError("function must be a non-empty string.")
    module = module.strip()
    function = function.strip()

    try:
        record = _rt().capabilities().describe(module, function)
    except CapabilityError as exc:
        raise AlgentaToolError(str(exc)) from exc

    signature = _render_signature(_signature_index().get((module, function)))
    lines = [f"{module}.{function}{signature}"]

    if record.docs is not UNDECLARED and record.docs and record.docs.lower() != "none":
        lines.append(record.docs)
    else:
        lines.append(
            "No prose docstring is declared for this kernel; the signature above is "
            "the whole public contract."
        )

    bits = _declared_bits(record)
    for name in ("stateful", "batch_capable", "stream_capable"):
        value = getattr(record, name)
        if value is not UNDECLARED:
            bits.append(f"{name}={value}")
    if bits:
        lines.append("Declared: " + ", ".join(bits))

    if record.count_relations is not UNDECLARED and record.count_relations:
        expressions = "; ".join(relation.expression for relation in record.count_relations)
        lines.append(f"Count relations: {expressions}")

    return "\n".join(lines)


# ── tool 4: get_column (added for the LLM-uplift eval; see module note below) ──────
#
# The three tools above wrap the compiled Mojo kernel library, but none of them can
# get a real dataset's values INTO a tool call in the first place: `execute`'s `args`
# are supplied by the calling model, and a model cannot type out 29,000 real CSV
# values it has never seen. The original three-tool harness had no data-ingestion path
# at all -- fine for the kernel-discovery smoke test it shipped with, but it means an
# LLM+tools benchmark run against a real CSV would have zero way to reach the data,
# collapsing to the same blind guess as the no-tools condition. `get_column` is the
# minimal fix: it reads the one fixture CSV this eval targets, optionally filters rows
# by an exact-match WHERE clause on another column, and returns the column's values
# (truncated for the model's context, full value retrievable by `result_id` exactly
# like an `execute` result -- see `_resolve_result_refs` above for feeding that id
# straight into a follow-up `execute` call). This is data ACCESS, analogous to a SQL
# SELECT/WHERE or the `database.table_where`/`table_select_column` kernels' own job --
# it never computes a statistic. Every actual number in an answer (mean, quantile, sum,
# unique-count, correlation, ...) still has to come from `execute` dispatching a real
# compiled kernel; nothing here computes an aggregate in Python.

_QUOTES_CSV = None  # set by eval/run_benchmark.py before first use; see get_column().


def _quotes_df():
    global _QUOTES_CSV
    if _QUOTES_CSV is None:
        raise AlgentaToolError(
            "get_column's dataset path was never configured "
            "(benchmarks.algenta_llm_tools.tools.configure_dataset(csv_path) first)."
        )
    return _QUOTES_CSV


def configure_dataset(csv_path: str) -> None:
    """Point ``get_column`` at a real CSV, loading it once (cached for the process)."""
    import pandas as pd  # local import: tools.py's other 3 tools have no pandas dependency

    global _QUOTES_CSV
    _QUOTES_CSV = pd.read_csv(csv_path, low_memory=False)


GET_COLUMN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_column",
        "description": (
            "Read one column's real values out of the dataset (optionally filtered to "
            "rows where another column exactly equals a given value, and/or restricted "
            "to that column's distinct values). This is plain data access -- like a SQL "
            "SELECT/WHERE -- never a computed statistic; to compute a mean/sum/quantile/"
            "unique-count/correlation/etc. over what this returns, pass its result_id "
            "into execute()'s args as {'result_id': '<id>'} for the corresponding "
            "kernel argument. Large columns are truncated for display here (see "
            "'truncated'/'element_count'); the full values are kept under 'result_id'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "Exact column name, e.g. 'UNIT_PRICE'.",
                },
                "filter_column": {
                    "type": "string",
                    "description": "Optional column to filter rows on (exact-match WHERE).",
                },
                "filter_value": {
                    "type": "string",
                    "description": "Value filter_column must exactly equal, as a string.",
                },
                "distinct": {
                    "type": "boolean",
                    "description": (
                        "If true, return the column's sorted distinct values (after any "
                        "filter/dropna) instead of every row -- for discovering what "
                        "categories exist before grouping by them."
                    ),
                },
                "dropna": {
                    "type": "boolean",
                    "description": "Drop null values before returning (default true).",
                },
            },
            "required": ["column"],
            "additionalProperties": False,
        },
    },
}


def get_column(
    column: str,
    filter_column: str | None = None,
    filter_value: str | None = None,
    distinct: bool = False,
    dropna: bool = True,
) -> dict[str, Any]:
    """Real column values (optionally WHERE-filtered / reduced to distinct), for use as
    ``execute`` args. Raises ``AlgentaToolError`` for an unknown column -- never returns
    a guessed/empty result for a typo'd name."""
    df = _quotes_df()
    if column not in df.columns:
        raise AlgentaToolError(f"Unknown column {column!r}. Known columns: {list(df.columns)}")
    series = df[column]
    where = None
    if filter_column is not None:
        if filter_column not in df.columns:
            raise AlgentaToolError(f"Unknown filter_column {filter_column!r}.")
        mask = df[filter_column].astype(str) == str(filter_value)
        series = series[mask]
        where = f"{filter_column} == {filter_value!r}"
    if dropna:
        series = series.dropna()

    if distinct:
        values = sorted(series.astype(str).unique().tolist())
        return {
            "column": column,
            "filter": where,
            "distinct_values": values,
            "count_distinct": len(values),
        }

    import pandas as pd  # local import, see configure_dataset()

    if pd.api.types.is_numeric_dtype(series):
        values = [float(x) for x in series.tolist()]
    else:
        values = [str(x) for x in series.tolist()]
    shaped = shape_for_model(values)
    return {
        "column": column,
        "filter": where,
        "value": shaped["value"],
        "truncated": shaped["truncated"],
        "element_count": shaped.get("element_count", len(values)),
        "result_id": store_result(values),
    }


# ── tool 5: group_by_aggregate (added for the LLM-uplift eval; see module note below) ──
#
# `execute` calls exactly one kernel by name, and `get_column` reads exactly one
# column -- neither can answer "grouping by CUST_TYPE, which value has the highest
# average UNIT_PRICE" without the model doing the grouping itself: one
# get_column(filter_column=..., filter_value=<category>) + one execute("stats",
# "mean", ...) PER DISTINCT CATEGORY, then comparing the results by hand. That is
# exactly the shape of two real benchmark misses from today's run: one question ran
# out of its 45-turn budget doing this one category at a time, and another found no
# correctly-shaped kernel and silently guessed. `group_by_aggregate` closes that gap
# with a real aggregate ACROSS EVERY CATEGORY IN ONE DISPATCH -- `algenta.Query(...)
# .group_by(...)`, the public SDK's columnar-query builder, which is a thin,
# plan-hashed wrapper over the compiled `query.composed.group_by_composed_parallel`
# kernel that `query.plan`'s "aggregate" op calls (see
# `tests/mojo/test_query_groupby_quotes_probe.mojo` for that kernel proven correct
# against an independently-computed pandas ground truth on a real CSV slice). Every
# number this returns is still real Mojo output; the only Python-side work is
# building the plan's input rows and mapping the group key back from an integer code
# to its original category label, because query columns are numeric-or-null only
# (see `algenta/query.py::_normalize_rows`) and this dataset's categories are strings.

GROUP_BY_AGGREGATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "group_by_aggregate",
        "description": (
            "Group the dataset by ONE categorical column and compute a real aggregate "
            "(mean, sum, count, min, max, var, or std) of a numeric column ACROSS EVERY "
            "CATEGORY IN A SINGLE COMPILED-KERNEL DISPATCH -- never one execute()/"
            "get_column() call per category. Use this for any 'grouping by X, which "
            "value of X has the highest/lowest average (or sum/count/...) Y' question, "
            "instead of discovering categories with get_column(distinct=True) and then "
            "computing each one's statistic separately. Rows where group_column or "
            "value_column is missing are excluded first, exactly like "
            "df.groupby(group_column)[value_column].agg(...) in pandas. Returns one row "
            "per real category present in the data, sorted by the aggregate value, "
            "descending."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "group_column": {
                    "type": "string",
                    "description": "Exact categorical column name to group by, e.g. 'CUST_TYPE'.",
                },
                "value_column": {
                    "type": "string",
                    "description": "Exact numeric column name to aggregate, e.g. 'UNIT_PRICE'.",
                },
                "agg": {
                    "type": "string",
                    "enum": ["mean", "avg", "sum", "count", "min", "max", "var", "std"],
                    "description": "Aggregation to compute per group (default 'mean').",
                },
            },
            "required": ["group_column", "value_column"],
            "additionalProperties": False,
        },
    },
}


def group_by_aggregate(
    group_column: str,
    value_column: str,
    agg: str = "mean",
) -> dict[str, Any]:
    """`agg` of `value_column`, grouped by EVERY distinct real `group_column` value,
    in ONE dispatch of the real compiled `group_by_composed_parallel` kernel via
    `algenta.Query(...).group_by(...)`.

    Rows where `group_column` or `value_column` is null are dropped first -- a null
    group key would join no group and a null value has nothing to average, matching
    `df.groupby(group_column)[value_column].agg(...)`'s own null handling. Categories
    are mapped to integer codes before crossing into the query plan (query columns
    are numeric-or-null only) and mapped back to their original labels on the way
    out, so the model never sees or has to reconstruct the encoding.

    Raises ``AlgentaToolError`` for an unknown column, an unrecognized `agg`, or a
    kernel/plan failure -- never a Python-recomputed aggregate.
    """
    from algenta import Query, QueryError

    df = _quotes_df()
    if group_column not in df.columns:
        raise AlgentaToolError(
            f"Unknown group_column {group_column!r}. Known columns: {list(df.columns)}"
        )
    if value_column not in df.columns:
        raise AlgentaToolError(
            f"Unknown value_column {value_column!r}. Known columns: {list(df.columns)}"
        )

    working = df[[group_column, value_column]].dropna()
    if working.empty:
        raise AlgentaToolError(
            f"No row has both {group_column!r} and {value_column!r} present; nothing to group."
        )

    categories = sorted(working[group_column].astype(str).unique().tolist())
    code_of = {category: float(index) for index, category in enumerate(categories)}
    code_column = "__group_code__"
    rows = [
        [code_of[str(category)], float(value)]
        for category, value in zip(working[group_column], working[value_column])
    ]

    started = time.perf_counter()
    try:
        query = Query(columns=[code_column, value_column], rows=rows).group_by(
            code_column, value_column, agg=agg
        )
        result = query.run(_rt(), routing_module="stats")
    except ValueError as exc:
        raise AlgentaToolError(str(exc)) from exc
    except QueryError as exc:
        raise AlgentaToolError(
            f"group_by({group_column!r}, {value_column!r}, agg={agg!r}) failed on the"
            f" real runtime: {exc}"
        ) from exc
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    # The aggregate column is named "{agg-token}_{value_column}" by query/plan.mojo
    # (see its "aggregate" op) -- read the name back from the result rather than
    # guessing the token, so a token normalization on the engine side (e.g. "mean"
    # rendered as "avg") can never desync this from the real output schema.
    agg_column = next(name for name in result.columns if name != code_column)
    decoded_rows: list[dict[str, Any]] = []
    for code_value, agg_value in zip(result.column(code_column), result.column(agg_column)):
        if code_value is None or agg_value is None:
            continue
        code_index = int(round(code_value))
        if not (0 <= code_index < len(categories)):
            raise AlgentaToolError(
                f"group_by returned an out-of-range group code {code_value!r}"
                f" for {len(categories)} known categories -- the code<->category"
                " mapping desynced."
            )
        decoded_rows.append({group_column: categories[code_index], agg_column: agg_value})
    decoded_rows.sort(key=lambda row: row[agg_column], reverse=True)

    shaped = shape_for_model(decoded_rows)
    return {
        "group_column": group_column,
        "value_column": value_column,
        "agg": agg,
        "value": shaped["value"],
        "truncated": shaped["truncated"],
        "element_count": shaped.get("element_count", len(decoded_rows)),
        "result_id": store_result(decoded_rows),
        "latency_ms": latency_ms,
        "engine": "mojo",
    }


# ── bundling for a tool-calling loop ────────────────────────────────────────────────

TOOL_SCHEMAS = [
    LIST_CAPABILITIES_SCHEMA,
    EXECUTE_SCHEMA,
    EXPLAIN_SCHEMA,
    GET_COLUMN_SCHEMA,
    GROUP_BY_AGGREGATE_SCHEMA,
]
TOOL_FUNCTIONS = {
    "list_capabilities": list_capabilities,
    "execute": execute,
    "explain": explain,
    "get_column": get_column,
    "group_by_aggregate": group_by_aggregate,
}
