"""Hand-verified, real-runtime probe for the new `get_columns` tool, run before
spending any API budget on q16 of the uplift eval
(``benchmarks/algenta_llm_tools/eval/quotes_question_set.json``): the Pearson
correlation of UNIT_PRICE vs QUANTITY, restricted to rows where BOTH are non-null.

The root-cause bug this closes: `get_column` drops nulls PER COLUMN
INDEPENDENTLY, so `get_column("UNIT_PRICE", dropna=True)` and
`get_column("QUANTITY", dropna=True)` return two lists whose positions no longer
correspond to the same real row the moment a row is null in one column but not the
other -- feeding those two independently-filtered lists into
`stat_tests.pearson_r_strict` correlates mismatched pairs and returns a confidently
wrong number, with no error (unless the two happen to end up a different LENGTH, the
one case `pearson_r_strict` can actually detect and reject).

This probe proves, against the REAL compiled Mojo kernel (through the real, local
`MojoRuntime`/`execute()`, unmocked, same as ``smoke_test.py``) and the REAL
UNIT_PRICE/QUANTITY columns of ``test_files/Processed_Quotes.csv``:

  1. `get_columns(["UNIT_PRICE", "QUANTITY"])` returns two SAME-LENGTH lists whose
     row count matches q16's own recorded `n` (23269) -- the row-wise
     `dropna(subset=[...])` join, not either column's own null count.
  2. Feeding those two aligned lists into `execute("stat_tests",
     "pearson_r_strict", ...)` produces a real `r` that matches pandas' own,
     independently-computed `.corr()` on the identical jointly-aligned rows.
  3. That `r` matches q16's recorded ground truth (-0.071331) to its stated
     tolerance (0.001).
  4. The OLD, buggy path -- two independent `get_column(..., dropna=True)` calls,
     naively zipped together despite the mismatched lengths that per-column
     dropna actually produces on this real data -- is DIFFERENT from the correct
     answer, proving this is a real fix for a real, reproducible misalignment
     bug, not a defense against a hypothetical one.

Run (same dev knobs as smoke_test.py):

    ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
    ALGENTA_MOJO_BINARY=/absolute/path/to/mojo_build/simulate \\
    PYTHONPATH=packages/algenta python3 -m \\
        benchmarks.algenta_llm_tools.eval.probe_get_columns_correlation
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
CSV_PATH = REPO_ROOT / "test_files" / "Processed_Quotes.csv"

sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from benchmarks.algenta_llm_tools import tools  # noqa: E402

_PASSED = 0
_FAILED = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✅ {label}")
    else:
        _FAILED += 1
        print(f"  ❌ {label}  {detail}")


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {CSV_PATH}")

    tools.configure_dataset(str(CSV_PATH))
    df = pd.read_csv(CSV_PATH, low_memory=False)

    # --- discovery: get_columns is real and callable -------------------------------
    _check("get_columns is exported from tools.py", hasattr(tools, "get_columns"))
    _check(
        "get_columns is registered in TOOL_FUNCTIONS / TOOL_SCHEMAS",
        "get_columns" in tools.TOOL_FUNCTIONS
        and any(s["function"]["name"] == "get_columns" for s in tools.TOOL_SCHEMAS),
    )

    # --- 0. reproduce the OLD bug for real, on real data, before the fix matters ---
    old_unit_price = tools.get_column("UNIT_PRICE", dropna=True)
    old_quantity = tools.get_column("QUANTITY", dropna=True)
    old_up_values = tools.get_stored_result(old_unit_price["result_id"])
    old_qty_values = tools.get_stored_result(old_quantity["result_id"])
    print(
        f"\nOLD path: get_column('UNIT_PRICE', dropna=True) -> {len(old_up_values)} values"
        f"\nOLD path: get_column('QUANTITY', dropna=True)   -> {len(old_qty_values)} values"
    )
    _check(
        "the two independently-dropna'd columns are actually DIFFERENT lengths on real"
        " data (the bug is real, not hypothetical)",
        len(old_up_values) != len(old_qty_values),
        f"UNIT_PRICE={len(old_up_values)} QUANTITY={len(old_qty_values)}",
    )

    # --- 1. the NEW tool: jointly aligned, single dispatch --------------------------
    result = tools.get_columns(["UNIT_PRICE", "QUANTITY"])
    print(f"\nget_columns(['UNIT_PRICE', 'QUANTITY']) -> row_count={result['row_count']}")
    up_id = result["result_ids"]["UNIT_PRICE"]
    qty_id = result["result_ids"]["QUANTITY"]
    unit_price_values = tools.get_stored_result(up_id)
    quantity_values = tools.get_stored_result(qty_id)
    _check(
        "get_columns returns two SAME-length, jointly-aligned columns",
        len(unit_price_values) == len(quantity_values) == result["row_count"],
        f"UNIT_PRICE={len(unit_price_values)} QUANTITY={len(quantity_values)}"
        f" row_count={result['row_count']}",
    )

    q16_n = 23269
    _check(
        f"row_count matches q16's own recorded n ({q16_n}) -- the JOINT dropna, not"
        " either column's own null count",
        result["row_count"] == q16_n,
        f"got {result['row_count']}",
    )

    # Independently rebuild the same jointly-aligned rows straight from the real CSV
    # (no reuse of tools.py's own pandas calls) to prove get_columns' alignment itself
    # is correct, not just its row count.
    independent_aligned = df.dropna(subset=["UNIT_PRICE", "QUANTITY"])[["UNIT_PRICE", "QUANTITY"]]
    _check(
        "get_columns' aligned UNIT_PRICE values match an independent"
        " df.dropna(subset=[...]) rebuild, row for row",
        unit_price_values == [float(v) for v in independent_aligned["UNIT_PRICE"].tolist()],
    )
    _check(
        "get_columns' aligned QUANTITY values match an independent"
        " df.dropna(subset=[...]) rebuild, row for row",
        quantity_values == [float(v) for v in independent_aligned["QUANTITY"].tolist()],
    )

    # --- 2. feed the aligned lists into the REAL pearson_r_strict kernel ------------
    corr_result = tools.execute(
        "stat_tests",
        "pearson_r_strict",
        {
            "x": {"result_id": up_id},
            "y": {"result_id": qty_id},
        },
    )
    assert corr_result["engine"] == "mojo"
    r_value = corr_result["value"]
    if isinstance(r_value, dict):
        r_value = r_value.get("r", r_value)
    print(f"\nmojo   pearson_r_strict(UNIT_PRICE, QUANTITY) -> {corr_result['value']}")
    r_value = float(r_value)

    # --- oracle: pandas' OWN, independently-computed correlation on the same rows --
    pandas_r = float(
        df.dropna(subset=["UNIT_PRICE", "QUANTITY"])[["UNIT_PRICE", "QUANTITY"]].corr().iloc[0, 1]
    )
    print(f"pandas .corr() [independent oracle]           -> {pandas_r}")
    _check(
        "mojo pearson_r_strict matches pandas' independent .corr() on the SAME"
        " jointly-aligned rows",
        abs(r_value - pandas_r) < 1e-6,
        f"mojo={r_value} pandas={pandas_r}",
    )

    # --- q16's own recorded ground truth --------------------------------------------
    q16_ground_truth = -0.071331
    q16_tolerance = 0.001
    print(f"q16 ground truth (quotes_question_set.json)   -> {q16_ground_truth}")
    _check(
        f"mojo pearson_r_strict matches q16's ground truth to its stated tolerance"
        f" ({q16_tolerance})",
        abs(r_value - q16_ground_truth) <= q16_tolerance,
        f"mojo={r_value} ground_truth={q16_ground_truth} diff={abs(r_value - q16_ground_truth)}",
    )

    # --- 3. prove the OLD (misaligned) path gives a genuinely DIFFERENT answer -----
    n_common = min(len(old_up_values), len(old_qty_values))
    try:
        old_result = tools.execute(
            "stat_tests",
            "pearson_r_strict",
            {"x": old_up_values[:n_common], "y": old_qty_values[:n_common]},
        )
        old_r = float(old_result["value"].get("r", old_result["value"]))
        print(f"\nOLD (misaligned) pearson_r_strict(truncated-zip)    -> {old_r}")
        _check(
            "the OLD misaligned-zip path gives a DIFFERENT (wrong) answer than the"
            " correctly-aligned one -- proof this is a real fix, not a no-op",
            abs(old_r - r_value) > q16_tolerance,
            f"old={old_r} new={r_value}",
        )
    except tools.AlgentaToolError as exc:
        print(f"\nOLD (misaligned) path raised instead of silently answering: {exc}")
        _check("the OLD misaligned path is at least not silently identical to the fix", True)

    print(f"\n  [probe_get_columns_correlation] Passed: {_PASSED} Failed: {_FAILED}")
    if _FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
