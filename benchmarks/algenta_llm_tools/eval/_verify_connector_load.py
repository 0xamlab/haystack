"""Ad hoc verification script (not part of the test suite) for the
Runtime(mode="local").connect()-backed configure_dataset() rewrite.

Loads the real corpus through the real local SDK connector, then recomputes a
sample of the 16 quotes_question_set.json ground truths purely through the tool
functions in benchmarks.algenta_llm_tools.tools (get_column / execute / group_by_aggregate)
-- never through a side-channel pandas read of the CSV.

Run with:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
    ALGENTA_MOJO_BINARY=/absolute/path/to/mojo_build/simulate \\
    PYTHONPATH=packages/algenta:packages/python-sdk python3 -m benchmarks.algenta_llm_tools.eval._verify_connector_load
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
CSV_PATH = REPO_ROOT / "test_files" / "Processed_Quotes.csv"

sys.path.insert(0, str(REPO_ROOT))

from benchmarks.algenta_llm_tools import tools  # noqa: E402


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {CSV_PATH}")

    # This is the one call under test: it must reach the CSV only through
    # algenta.Runtime(mode="local").connect(), never a bespoke pandas.read_csv.
    tools.configure_dataset(str(CSV_PATH))

    df = tools._quotes_df()
    print(f"connector-loaded row_count = {len(df)} (expected 33125)")
    assert len(df) == 33125, f"row count mismatch: {len(df)}"

    # q07: count of STATUS == 'LOST' (ground truth 14673) -- via get_column, no execute needed.
    status_col = tools.get_column("STATUS")
    count_lost = sum(1 for v in status_col["value"] if v == "LOST") if not status_col["truncated"] else None
    if status_col["truncated"]:
        full_status = tools.get_stored_result(status_col["result_id"])
        count_lost = sum(1 for v in full_status if v == "LOST")
    print(f"q07 count STATUS=='LOST' via get_column = {count_lost} (expected 14673)")
    assert count_lost == 14673, count_lost

    # q11: nunique CUSTOMER_NO (ground truth 2008) -- via get_column(distinct=True).
    distinct = tools.get_column("CUSTOMER_NO", distinct=True)
    print(f"q11 nunique CUSTOMER_NO via get_column(distinct=True) = {distinct['count_distinct']} (expected 2008)")
    assert distinct["count_distinct"] == 2008, distinct["count_distinct"]

    # q04: mean UNIT_PRICE (ground truth 779.182035) -- via get_column -> execute(stats.compute_mean).
    unit_price = tools.get_column("UNIT_PRICE")
    values = tools.get_stored_result(unit_price["result_id"])
    print(f"UNIT_PRICE non-null count = {len(values)} (expected 29204)")
    mean_result = tools.execute("stats", "compute_mean", {"v": {"result_id": unit_price["result_id"]}})
    print(f"q04 mean UNIT_PRICE via execute(stats.compute_mean) = {mean_result['value']} (expected 779.182035)")
    assert abs(mean_result["value"] - 779.182035) < 1e-4, mean_result["value"]

    # q06: min/max UNIT_PRICE (ground truth min=0.0, max=215000.0) -- via execute(stats.quantile)
    # at q=0.0/q=1.0 (no dedicated stats.min/max kernel is registered in this catalog).
    min_result = tools.execute(
        "stats",
        "quantile",
        {"v": {"result_id": unit_price["result_id"]}, "n": len(values), "q": 0.0},
    )
    max_result = tools.execute(
        "stats",
        "quantile",
        {"v": {"result_id": unit_price["result_id"]}, "n": len(values), "q": 1.0},
    )
    print(f"q06 min/max UNIT_PRICE via execute(stats.quantile) = {min_result['value']} / {max_result['value']} (expected 0.0 / 215000.0)")
    assert min_result["value"] == 0.0
    assert max_result["value"] == 215000.0

    # q14: top CUST_TYPE by avg UNIT_PRICE (ground truth MILITARY, 12515.95) -- via group_by_aggregate,
    # the real Query(...).group_by(...) dispatch of the compiled group_by_composed_parallel kernel.
    grouped = tools.group_by_aggregate("CUST_TYPE", "UNIT_PRICE", agg="mean")
    top_row = grouped["value"]["rows"][0]
    print(f"q14 top CUST_TYPE by avg UNIT_PRICE via group_by_aggregate = {top_row} (expected MILITARY / 12515.95)")
    assert top_row["CUST_TYPE"] == "MILITARY", top_row
    assert abs(top_row["avg_UNIT_PRICE"] - 12515.95) < 0.5, top_row

    print("\nALL SPOT-CHECKS PASSED via the real connector-loaded data + real tool functions.")


if __name__ == "__main__":
    main()
