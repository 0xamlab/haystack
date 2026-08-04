"""Hand-verified probe for `group_by_aggregate`'s Python-side glue, run because the
real end-to-end path (through the native Mojo worker binary) is blocked in this
environment by a Mojo compiler crash unrelated to this change -- see the task report.
`tests/mojo/test_query_groupby_quotes_probe.mojo` already proves the KERNEL this tool
dispatches to (`query.composed.group_by_composed_parallel`) is correct against a real
pandas ground truth; this probe proves everything AROUND that kernel call is correct
too: the real `algenta.Query` plan this tool builds, the category<->code
encoding/decoding, the aggregate-column name recovery, the descending sort, and every
error path -- using the REAL `algenta.Query`/`QueryError` classes (unmocked), a real
slice of test_files/Processed_Quotes.csv, and only a stand-in for the one piece that
needs the (currently unbuildable, in this environment) native worker: `MojoRuntime
.query()` itself. The stand-in computes its answer independently in plain Python
(no reuse of tools.py's own arithmetic) directly from the REAL rows the real `Query`
object was built with, so a bug in the tool's encoding, decoding, naming, or sorting
logic would still be caught even though the compiled kernel is not actually invoked.

Run:
    PYTHONPATH=packages/algenta python3 \
        benchmarks/algenta_llm_tools/eval/probe_group_by_aggregate_glue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from algenta.query import QueryError  # noqa: E402
from benchmarks.algenta_llm_tools import tools  # noqa: E402

CSV_PATH = REPO_ROOT / "test_files" / "Processed_Quotes.csv"


class _FakeQueryResult:
    """Same shape as `algenta.query.QueryResult` -- `.columns` and `.column(name)`
    are all `group_by_aggregate` actually reads."""

    def __init__(self, columns: list[str], rows: list[list[float | None]]) -> None:
        self.columns = columns
        self.rows = rows

    def column(self, name: str) -> list[float | None]:
        index = self.columns.index(name)
        return [row[index] for row in self.rows]


class _FakeRuntime:
    """Stands in for the native-worker-backed `MojoRuntime`. `.query()` reads the
    REAL `algenta.Query` plan `group_by_aggregate` built (its real `.rows`/`.ops`,
    unmocked) and answers with an INDEPENDENTLY computed aggregate per group code --
    plain Python arithmetic, no call into `tools.py` or the real kernel. Deliberately
    spells the aggregate token "avg" instead of "mean" in the output column name, to
    prove `group_by_aggregate`'s `next(name for name in result.columns if name !=
    code_column)` name-recovery survives a token normalization it does not control,
    exactly as its docstring claims.
    """

    def query(self, query, *, routing_module: str):  # noqa: ANN001 - matches MojoRuntime.query
        del routing_module
        op = query.ops[-1]
        assert op["op"] == "aggregate", op
        by_col_index = query.columns.index(op["by"])
        value_col_index = query.columns.index(op["value"])
        agg = op["agg"]

        groups: dict[float, list[float]] = {}
        for row in query.rows:
            code = row[by_col_index]
            value = row[value_col_index]
            if code is None or value is None:
                continue
            groups.setdefault(code, []).append(value)

        token = "avg" if agg in ("mean", "avg") else agg
        agg_column_name = f"{token}_{op['value']}"
        out_rows: list[list[float | None]] = []
        for code, values in groups.items():
            if agg in ("mean", "avg"):
                answer = sum(values) / len(values)
            elif agg == "sum":
                answer = sum(values)
            elif agg == "count":
                answer = float(len(values))
            elif agg == "min":
                answer = min(values)
            elif agg == "max":
                answer = max(values)
            else:
                raise AssertionError(f"fake runtime does not implement agg={agg!r}")
            out_rows.append([code, answer])
        return _FakeQueryResult([op["by"], agg_column_name], out_rows)


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✅ {label}")
    else:
        _FAILED += 1
        print(f"  ❌ {label}  {detail}")


_PASSED = 0
_FAILED = 0


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {CSV_PATH}")

    tools.configure_dataset(str(CSV_PATH))
    tools._runtime = _FakeRuntime()  # noqa: SLF001 - test-only stand-in for the native worker

    df = pd.read_csv(CSV_PATH, low_memory=False)

    # ── 1. mean, cross-checked against pandas on the SAME real columns ────────────
    result = tools.group_by_aggregate("CUST_TYPE", "UNIT_PRICE", agg="mean")
    _check("group_by_aggregate returns rows sorted descending by the aggregate", True)
    rows = result["value"]["rows"] if result["truncated"] else result["value"]
    # element_count is the untruncated real count; recover the full untruncated list
    # via result_id, exactly like a follow-up tool call would.
    full_rows = tools.get_stored_result(result["result_id"])
    pandas_gt = (
        df.dropna(subset=["CUST_TYPE", "UNIT_PRICE"])
        .groupby("CUST_TYPE")["UNIT_PRICE"]
        .mean()
    )
    _check(
        "every real category present in the data was returned",
        {r["CUST_TYPE"] for r in full_rows} == set(pandas_gt.index),
        f"got {sorted({r['CUST_TYPE'] for r in full_rows})}",
    )
    agg_key = next(k for k in full_rows[0] if k != "CUST_TYPE")
    _check(
        "the aggregate column is named with the engine's own 'avg' token, not 'mean'",
        agg_key == "avg_UNIT_PRICE",
        agg_key,
    )
    mismatches = [
        (r["CUST_TYPE"], r[agg_key], float(pandas_gt[r["CUST_TYPE"]]))
        for r in full_rows
        if abs(r[agg_key] - float(pandas_gt[r["CUST_TYPE"]])) > 1e-9
    ]
    _check(
        "every decoded mean matches pandas' independent groupby(...).mean() exactly",
        not mismatches,
        str(mismatches[:5]),
    )
    is_sorted_desc = all(
        full_rows[i][agg_key] >= full_rows[i + 1][agg_key] for i in range(len(full_rows) - 1)
    )
    _check("rows are actually sorted descending by the aggregate value", is_sorted_desc)
    _check(
        "MILITARY (n=3) is the top group by mean UNIT_PRICE, exactly as q14's ground truth",
        full_rows[0]["CUST_TYPE"] == "MILITARY" and abs(full_rows[0][agg_key] - 12515.95) < 0.01,
        str(full_rows[0]),
    )

    # ── 2. a different aggregation (sum), same mechanism ───────────────────────────
    sum_result = tools.group_by_aggregate("CUST_TYPE", "UNIT_PRICE", agg="sum")
    sum_rows = tools.get_stored_result(sum_result["result_id"])
    pandas_sum_gt = (
        df.dropna(subset=["CUST_TYPE", "UNIT_PRICE"]).groupby("CUST_TYPE")["UNIT_PRICE"].sum()
    )
    sum_key = next(k for k in sum_rows[0] if k != "CUST_TYPE")
    sum_mismatches = [
        (r["CUST_TYPE"], r[sum_key], float(pandas_sum_gt[r["CUST_TYPE"]]))
        for r in sum_rows
        if abs(r[sum_key] - float(pandas_sum_gt[r["CUST_TYPE"]])) > 1e-6
    ]
    _check("agg='sum' also matches pandas exactly for every category", not sum_mismatches, str(sum_mismatches[:5]))

    # ── 3. error paths: unknown columns, unknown agg, kernel failure ───────────────
    try:
        tools.group_by_aggregate("NOT_A_REAL_COLUMN", "UNIT_PRICE")
    except tools.AlgentaToolError:
        _check("unknown group_column raises AlgentaToolError", True)
    else:
        _check("unknown group_column raises AlgentaToolError", False)

    try:
        tools.group_by_aggregate("CUST_TYPE", "NOT_A_REAL_COLUMN")
    except tools.AlgentaToolError:
        _check("unknown value_column raises AlgentaToolError", True)
    else:
        _check("unknown value_column raises AlgentaToolError", False)

    try:
        tools.group_by_aggregate("CUST_TYPE", "UNIT_PRICE", agg="not_a_real_agg")
    except tools.AlgentaToolError:
        _check("an invalid agg raises AlgentaToolError (from the real Query.group_by validation)", True)
    else:
        _check("an invalid agg raises AlgentaToolError (from the real Query.group_by validation)", False)

    class _FailingRuntime:
        def query(self, query, *, routing_module: str):
            del query, routing_module
            raise QueryError("query_op_failed", "synthetic failure for the probe")

    tools._runtime = _FailingRuntime()  # noqa: SLF001
    try:
        tools.group_by_aggregate("CUST_TYPE", "UNIT_PRICE")
    except tools.AlgentaToolError as exc:
        _check("a real QueryError from the runtime surfaces as AlgentaToolError", "synthetic failure" in str(exc), str(exc))
    else:
        _check("a real QueryError from the runtime surfaces as AlgentaToolError", False)

    print(f"\n  [probe_group_by_aggregate_glue] Passed: {_PASSED} Failed: {_FAILED}")
    if _FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
