"""Hand-verified, real-runtime probe for the new `stats.compute_std` kernel.

This is the "run before spending any API budget" check for q05 of the uplift eval
(``benchmarks/algenta_llm_tools/eval/quotes_question_set.json``): the sample standard
deviation (ddof=1) of ``UNIT_PRICE``. Before this kernel existed, a tool-calling model
had no way to get a standard deviation in one call -- it had to call
``execute(stats.compute_mean)`` then ``execute(stats.compute_variance)`` and take a
manual square root itself, which is exactly how the benchmark run landed on 2332.003
against a true value of 2331.963152.

Three real, independent things are checked here, against the REAL compiled Mojo
kernel (through the real, local `MojoRuntime`/`execute()` this repo ships, unmocked,
same as ``smoke_test.py``) and the REAL UNIT_PRICE column of
``test_files/Processed_Quotes.csv`` (not a synthetic fixture):

  1. ``execute("stats", "compute_std", ...)`` matches
     ``sqrt(execute("stats", "compute_variance", ...))`` computed via two SEPARATE
     kernel calls, to double-precision tolerance -- proving the new one-call kernel is
     not a different computation from the two-call path, just a faster/safer one.
  2. Both match numpy's own, independently-computed ``ddof=1`` standard deviation on
     the identical values -- an oracle this module never imports into the kernel path.
  3. The result matches q05's own recorded ground truth (2331.963152) to its stated
     tolerance (0.01), proving the kernel gap behind that benchmark miss is closed.

Run (same dev knobs as smoke_test.py -- a locally built worker and a relaxed
signature gate; this repo's own `make setup-mojo`/`build_mojo_binary.sh` produce the
former):

    ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
    ALGENTA_MOJO_BINARY=/absolute/path/to/mojo_build/simulate \\
    PYTHONPATH=packages/algenta python3 -m \\
        benchmarks.algenta_llm_tools.eval.probe_compute_std_kernel
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
CSV_PATH = REPO_ROOT / "test_files" / "Processed_Quotes.csv"

sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
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

    df = pd.read_csv(CSV_PATH, low_memory=False)
    column = df["UNIT_PRICE"].dropna().astype(float)
    values = column.tolist()
    n = len(values)
    print(f"loaded {CSV_PATH.name}: {len(df)} rows, {n} non-null UNIT_PRICE values")

    # --- discovery: compute_std is real and callable ------------------------------
    matches = tools.list_capabilities("compute_std")
    _check(
        "list_capabilities('compute_std') finds stats.compute_std",
        any(m["module"] == "stats" and m["function"] == "compute_std" for m in matches),
        str(matches),
    )
    doc = tools.explain("stats", "compute_std")
    print(f"\nexplain('stats', 'compute_std'):\n{doc}\n")

    # --- the real kernel, one call ------------------------------------------------
    mean_result = tools.execute("stats", "compute_mean", {"v": values, "n": n})
    mean_value = mean_result["value"]
    assert mean_result["engine"] == "mojo"

    variance_result = tools.execute(
        "stats", "compute_variance", {"v": values, "n": n, "mean": mean_value}
    )
    variance_value = variance_result["value"]
    assert variance_result["engine"] == "mojo"
    manual_sqrt = math.sqrt(variance_value)

    std_result = tools.execute("stats", "compute_std", {"v": values, "n": n, "mean": mean_value})
    std_value = std_result["value"]
    assert std_result["engine"] == "mojo"

    print(f"\nmojo   compute_mean                              = {mean_value}")
    print(f"mojo   compute_variance                          = {variance_value}")
    print(f"mojo   sqrt(compute_variance)  [manual, 2 calls]  = {manual_sqrt}")
    print(f"mojo   compute_std             [1 call]           = {std_value}")

    # --- oracle 1: the new kernel vs. the OLD two-call + manual-sqrt path ---------
    _check(
        "compute_std == sqrt(compute_variance(...)) to double-precision tolerance",
        abs(std_value - manual_sqrt) < 1e-9,
        f"compute_std={std_value} sqrt(variance)={manual_sqrt}",
    )

    # --- oracle 2: numpy's OWN, independently-computed ddof=1 std -----------------
    numpy_std = float(np.std(np.asarray(values, dtype=np.float64), ddof=1))
    print(f"numpy  std(ddof=1)   [independent oracle]        = {numpy_std}")
    _check(
        "compute_std matches numpy's independent ddof=1 standard deviation",
        abs(std_value - numpy_std) < 1e-6,
        f"mojo={std_value} numpy={numpy_std}",
    )
    _check(
        "pandas .std(ddof=1) agrees too (sanity cross-check of the oracle itself)",
        abs(float(column.std(ddof=1)) - numpy_std) < 1e-9,
    )

    # --- oracle 3: q05's own recorded ground truth from the eval question set -----
    q05_ground_truth = 2331.963152
    q05_tolerance = 0.01
    print(f"q05 ground truth (quotes_question_set.json)      = {q05_ground_truth}")
    std_diff = abs(std_value - q05_ground_truth)
    _check(
        f"compute_std matches q05's ground truth to its stated tolerance ({q05_tolerance})",
        std_diff <= q05_tolerance,
        f"mojo={std_value} ground_truth={q05_ground_truth} diff={std_diff}",
    )

    # --- the exact regression this kernel fixes: the OLD manual-sqrt error --------
    old_manual_answer = 2332.003  # what the benchmark actually got, per the task report
    old_diff = abs(old_manual_answer - q05_ground_truth)
    _check(
        "the NEW kernel is closer to ground truth than the OLD manual-sqrt answer was",
        std_diff < old_diff,
        f"new_diff={std_diff} old_diff={old_diff}",
    )

    print(f"\n  [probe_compute_std_kernel] Passed: {_PASSED} Failed: {_FAILED}")
    if _FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
