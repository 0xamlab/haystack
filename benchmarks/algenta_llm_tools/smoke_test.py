"""Real, end-to-end smoke test for the Algenta LLM tool-calling wrapper.

No mocks and no LLM calls (those come in a later phase). This loads the real corpus
already in this repo (``test_files/Processed_Quotes.csv``), calls ``tools.execute``
-- the exact function an LLM tool call would invoke -- to compute a real percentile
over its ``UNIT_PRICE`` column through the real compiled Mojo kernel, and
independently cross-checks the number against pandas' own ``.quantile()`` on the
identical column. If the two ever disagree, this test fails loudly: there is no
Python-side recomputation fallback anywhere in ``tools.py`` that could paper over a
real mismatch, so a passing run here is real evidence the wrapper is wired correctly,
before anyone builds a benchmark on top of it.

This dev checkout ships no pip-installed runtime wheel, so the SDK's own
"repo development build output" / env-override resolver needs to be pointed at an
already-built Mojo worker binary (see ``make build-mojo`` in the main repo, or reuse
one already built there) and the strict signature-verification gate relaxed for that
dev binary. Both are the SDK's own documented dev knobs, not anything invented here:

    ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
    ALGENTA_MOJO_BINARY=/absolute/path/to/mojo_build/simulate \\
    PYTHONPATH=packages/algenta python3 -m benchmarks.algenta_llm_tools.smoke_test
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CSV_PATH = REPO_ROOT / "test_files" / "Processed_Quotes.csv"

sys.path.insert(0, str(REPO_ROOT))

from benchmarks.algenta_llm_tools import tools  # noqa: E402


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, low_memory=False)
    column = df["UNIT_PRICE"].dropna().astype(float)
    values = column.tolist()
    print(f"loaded {CSV_PATH.name}: {len(df)} rows, {len(values)} non-null UNIT_PRICE values")

    # --- tool 1: discovery -------------------------------------------------------
    matches = tools.list_capabilities("percentile")
    assert matches, "list_capabilities('percentile') found nothing"
    assert any(
        m["module"] == "stats" and m["function"] in ("percentile", "quantile") for m in matches
    ), matches
    print(f"\nlist_capabilities('percentile') -> {len(matches)} matches; first: {matches[0]}")

    # --- tool 3: explain (before running anything) --------------------------------
    doc = tools.explain("stats", "quantile")
    print(f"\nexplain('stats', 'quantile'):\n{doc}")

    # --- tool 2: execute the REAL kernel over the REAL column ----------------------
    q = 0.9
    result = tools.execute("stats", "quantile", {"v": values, "n": len(values), "q": q})
    print(f"\nexecute('stats', 'quantile', ...) -> {result}")
    assert result["engine"] == "mojo", "the smoke test must exercise the real Mojo engine"
    mojo_value = result["value"]

    pandas_value = float(column.quantile(q))
    print(f"\nmojo   p{int(q * 100)} (stats.quantile, compiled kernel) = {mojo_value}")
    print(f"pandas p{int(q * 100)} (Series.quantile, independent check) = {pandas_value}")
    assert abs(mojo_value - pandas_value) < 1e-9, (
        f"MISMATCH: mojo={mojo_value} pandas={pandas_value}"
    )
    print("MATCH: the real compiled Mojo kernel agrees with pandas' independent .quantile().")

    # --- the count-relation safety net, exercised for real ------------------------
    # stats.compute_mean declares n as an element count bounding v; omit n entirely and
    # confirm execute() fills it in from the real length rather than requiring (or
    # trusting) the model to compute it.
    mean_result = tools.execute("stats", "compute_mean", {"v": values})
    pandas_mean = float(column.mean())
    print(f"\nmojo   mean (n auto-filled from len(v)) = {mean_result['value']}")
    print(f"pandas mean                              = {pandas_mean}")
    assert abs(mean_result["value"] - pandas_mean) < 1e-6, (
        f"MISMATCH: mojo={mean_result['value']} pandas={pandas_mean}"
    )
    print("MATCH: compute_mean with an auto-filled count arg also agrees with pandas.")

    # --- no silent success for a made-up capability --------------------------------
    try:
        tools.execute("not_a_real_module", "not_a_real_function", {})
    except tools.AlgentaToolError as exc:
        print(f"\nexecute() on an unknown module raised as designed: {exc}")
    else:  # pragma: no cover - would mean the safety property regressed
        raise AssertionError("execute() must raise for an unknown module, not succeed silently")

    print("\nALL CHECKS PASSED.")


if __name__ == "__main__":
    main()
