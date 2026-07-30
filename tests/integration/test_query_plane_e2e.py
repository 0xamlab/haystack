"""End-to-end: a query plan through the real compiled worker, on this device.

Not a unit test — it launches the bundled worker binary and sends real frames, so it
proves the whole path: builder -> JSON -> AF_UNIX frame -> Mojo operators -> columns
back. Skipped unless a runtime binary is present.

Point it at a binary with `ALGENTA_RUNTIME_WORKER`, or build one:

    BINARY_PATH=$PWD/mojo_build/simulate_queryplane \\
      MOJO_RUNTIME_MODULE_FILTER=stats,pandas_groupby,timeseries_stats \\
      bash scripts/build_mojo_binary.sh
    ALGENTA_RUNTIME_WORKER=$PWD/mojo_build/simulate_queryplane \\
      ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
      python3 -m pytest tests/integration/test_query_plane_e2e.py -q

A repo-dev binary is unsigned, so `ALGENTA_RUNTIME_FALLBACK_MODE=allow` is needed to
let an unverified worker run at all. That does not weaken what is proved: there is no
Python implementation of `query_execute`, and the fixture asserts the resolved worker
is the binary named above.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.mojo_runtime import MojoRuntime  # noqa: E402
from algenta.query import Query, QueryError, col, lit  # noqa: E402

_CANDIDATES = (
    os.environ.get("ALGENTA_RUNTIME_WORKER"),
    os.environ.get("ALGENTA_NATIVE_WORKER"),
    str(_REPO_ROOT / "mojo_build" / "simulate_queryplane"),
    str(_REPO_ROOT / "mojo_build" / "simulate"),
)


def _binary() -> str | None:
    for candidate in _CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


pytestmark = pytest.mark.skipif(
    _binary() is None,
    reason="no compiled runtime binary; see this module's docstring",
)


@pytest.fixture(scope="module")
def runtime():
    """A local runtime pointed at the compiled binary.

    A repo-dev build is unsigned, so it cannot pass the shard-map integrity check the
    packaged worker goes through, and the default `deny` fallback mode declines to run
    an unverified worker at all. This relaxes that to `allow`.

    `allow` here does NOT mean a Python path can answer a query: `query_execute` has no
    Python implementation, so an unavailable worker raises rather than substituting
    anything. To keep that honest rather than asserted, the fixture checks that worker
    resolution lands on exactly the binary we asked for — so if some other runtime
    served these tests, they fail here instead of passing quietly.
    """
    from algenta.native import worker

    binary = _binary()
    assert binary is not None
    os.environ["ALGENTA_RUNTIME_WORKER"] = binary
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    resolved = worker.resolve_worker(module_name="stats", require_verified=False)
    assert resolved is not None, "no worker resolved"
    assert Path(resolved.path).resolve() == Path(binary).resolve(), (
        f"resolved {resolved.path} but expected {binary}; these tests would be "
        "measuring a different runtime"
    )
    return MojoRuntime(mode="local")


SALES_COLUMNS = ["region", "month", "amount"]
SALES_ROWS = [
    [1, 1, 100.0],
    [2, 1, 999.0],
    [1, 2, 200.0],
    [1, 3, 200.0],
    [2, 2, 888.0],
    [1, 4, None],  # a real absence, all the way through
]


def _sales(**kwargs) -> Query:
    return Query(columns=SALES_COLUMNS, rows=[row[:] for row in SALES_ROWS], **kwargs)


def test_the_worker_is_actually_serving_mojo(runtime):
    """The compiled worker is up, and it is the bundled-worker transport serving it."""
    health = runtime.health()
    assert health.get("status") == "ok", health
    assert health.get("mode") == "bundled-worker", health


def test_an_empty_plan_returns_the_input_unchanged(runtime):
    result = _sales().run(runtime, routing_module="stats")
    assert result.columns == SALES_COLUMNS
    assert len(result) == 6
    assert result.ops == 0


def test_a_null_survives_the_whole_round_trip(runtime):
    """The single most important property: absent in, absent out, never 0.0."""
    result = _sales().run(runtime, routing_module="stats")
    amounts = result.column("amount")
    assert amounts[5] is None
    assert amounts[0] == 100.0


def test_filter_excludes_the_unknown_row(runtime):
    """`amount > 150` is unknown for the null row, and unknown does not pass."""
    result = _sales().filter(col("amount") > 150).run(runtime, routing_module="stats")
    assert sorted(result.column("amount")) == [200.0, 200.0, 888.0, 999.0]


def test_the_complement_filter_also_excludes_it(runtime):
    """Neither `> 150` nor `<= 150` claims the null row. That is what unknown means:
    the two filters do not partition the table."""
    above = _sales().filter(col("amount") > 150).run(runtime, routing_module="stats")
    below = _sales().filter(col("amount") <= 150).run(runtime, routing_module="stats")
    assert len(above) + len(below) == 5, "the null row must be in neither half"


def test_is_null_selects_the_unknown_row_deliberately(runtime):
    result = (
        _sales().filter(col("amount").is_null()).run(runtime, routing_module="stats")
    )
    assert len(result) == 1
    assert result.column("month") == [4.0]


def test_grouped_sum_and_the_empty_group_policy(runtime):
    """Region 1's live amounts are 100, 200, 200 -> 500. The null contributes nothing."""
    result = (
        _sales()
        .group_by("region", "amount", agg="sum")
        .sort("region")
        .run(runtime, routing_module="stats")
    )
    assert result.columns == ["region", "sum_amount"]
    assert result.rows == [[1.0, 500.0], [2.0, 1887.0]]


def test_grouped_mean_skips_the_null_rather_than_zeroing_it(runtime):
    """500/3 = 166.67, not 500/4 = 125. Treating the absence as 0 gives the wrong
    average while leaving the sum identical — the silent divergence."""
    result = (
        _sales()
        .group_by("region", "amount", agg="mean")
        .sort("region")
        .run(runtime, routing_module="stats")
    )
    region_1 = result.rows[0][1]
    assert region_1 is not None
    assert abs(region_1 - 500.0 / 3.0) < 1e-9


def test_a_group_with_no_live_values_has_a_sum_but_no_mean(runtime):
    """count and sum of nothing are real answers; a mean of nothing does not exist."""
    plan = Query(columns=["g", "v"], rows=[[7, None], [7, None]])
    sums = plan.group_by("g", "v", agg="sum").run(runtime, routing_module="stats")
    means = (
        Query(columns=["g", "v"], rows=[[7, None], [7, None]])
        .group_by("g", "v", agg="mean")
        .run(runtime, routing_module="stats")
    )
    counts = (
        Query(columns=["g", "v"], rows=[[7, None], [7, None]])
        .group_by("g", "v", agg="count")
        .run(runtime, routing_module="stats")
    )
    assert sums.rows == [[7.0, 0.0]]
    assert counts.rows == [[7.0, 0.0]]
    assert means.rows == [[7.0, None]], "a mean of nothing must be absent, not 0.0"


def test_a_null_group_key_forms_no_group(runtime):
    """Row 3's key is unknown, so it belongs to no group and invents no category."""
    result = (
        Query(columns=["g", "v"], rows=[[1, 10], [1, 20], [None, 999]])
        .group_by("g", "v", agg="sum")
        .run(runtime, routing_module="stats")
    )
    assert result.rows == [[1.0, 30.0]]


def test_sort_is_stable_and_puts_nulls_last_in_both_directions(runtime):
    descending = _sales().sort("amount", desc=True).run(runtime, routing_module="stats")
    ascending = _sales().sort("amount", desc=False).run(runtime, routing_module="stats")
    assert descending.column("amount")[-1] is None
    assert ascending.column("amount")[-1] is None, "reversing must not surface unknowns"

    # The two 200s are tied; stability keeps month 2 ahead of month 3 either way.
    desc_months = [m for m, a in zip(descending.column("month"), descending.column("amount")) if a == 200.0]
    assert desc_months == [2.0, 3.0]


def test_nulls_first_is_available_when_asked_for(runtime):
    result = (
        _sales()
        .sort("amount", desc=False, nulls_last=False)
        .run(runtime, routing_module="stats")
    )
    assert result.column("amount")[0] is None


def test_multi_key_sort_composes(runtime):
    result = (
        _sales()
        .sort(["region", "amount"], desc=[False, True])
        .run(runtime, routing_module="stats")
    )
    regions = result.column("region")
    assert regions == [1.0, 1.0, 1.0, 1.0, 2.0, 2.0], "region must stay grouped"
    # Within region 1, descending amount with the null last.
    region_1_amounts = result.column("amount")[:4]
    assert region_1_amounts == [200.0, 200.0, 100.0, None]


def test_top_k_agrees_with_a_full_sort(runtime):
    """Not merely on the set — on which row is first."""
    full = _sales().sort("amount", desc=True).run(runtime, routing_module="stats")
    top2 = _sales().top_k("amount", 2).run(runtime, routing_module="stats")
    assert top2.rows == full.rows[:2]


def test_top_k_past_the_row_count_returns_everything_sorted(runtime):
    full = _sales().sort("amount", desc=True).run(runtime, routing_module="stats")
    everything = _sales().top_k("amount", 99).run(runtime, routing_module="stats")
    assert everything.rows == full.rows


def test_distinct_and_its_null_rule(runtime):
    """Two rows absent in the key are the SAME row here — unlike `.eq()`."""
    result = (
        Query(columns=["v"], rows=[[None], [None], [0], [1]])
        .distinct("v")
        .run(runtime, routing_module="stats")
    )
    values = result.column("v")
    assert len(values) == 3, "the two nulls collapse; the real 0 stays separate"
    assert None in values and 0.0 in values and 1.0 in values


def test_projection_computes_new_columns_and_propagates_nulls(runtime):
    result = (
        _sales()
        .project(doubled=col("amount") * 2, plus_month=col("amount") + col("month"))
        .run(runtime, routing_module="stats")
    )
    assert result.columns == ["doubled", "plus_month"]
    assert result.column("doubled")[0] == 200.0
    assert result.column("doubled")[5] is None, "null * 2 is null, not 0"


def test_a_float_threshold_is_not_truncated(runtime):
    """20.5 must stay 20.5 across the boundary. Truncation to 20 would move the
    filter's boundary and change which rows survive, silently."""
    plan = Query(columns=["v"], rows=[[20.0], [20.4], [20.6], [21.0]])
    result = plan.filter(col("v") > 20.5).run(runtime, routing_module="stats")
    assert result.column("v") == [20.6, 21.0]


def test_three_valued_or_is_decided_when_either_side_is_true(runtime):
    """`region == 2 OR amount > 1e9`: the right side is unknown for the null row, but
    for region 2 the left side already decided it. Collapsing unknown to false would
    still work here; the point is that the row survives on the left alone."""
    plan = _sales().filter(col("region").eq(2) | (col("amount") > 1e9))
    result = plan.run(runtime, routing_module="stats")
    assert sorted(v for v in result.column("amount") if v is not None) == [888.0, 999.0]


def test_a_whole_multi_step_plan_runs_in_one_call(runtime):
    result = (
        _sales()
        .filter(col("amount") > 150)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .limit(1)
        .run(runtime, routing_module="stats")
    )
    assert result.ops == 4
    assert result.rows == [[2.0, 1887.0]]
    assert len(result.lineage) == 4
    assert [entry["op"] for entry in result.lineage] == [
        "filter",
        "aggregate",
        "sort",
        "limit",
    ]


def test_lineage_reports_each_step_shape(runtime):
    result = (
        _sales()
        .filter(col("amount") > 150)
        .group_by("region", "amount", agg="sum")
        .run(runtime, routing_module="stats")
    )
    assert result.lineage[0]["shape"].startswith("4 rows")
    assert result.lineage[1]["shape"].startswith("2 rows")


def test_plan_hash_is_stable_across_runs_and_blind_to_data(runtime):
    """It identifies the computation. Same plan over different rows -> same hash."""
    first = _sales().top_k("amount", 3).run(runtime, routing_module="stats")
    second = _sales().top_k("amount", 3).run(runtime, routing_module="stats")
    assert first.plan_hash == second.plan_hash
    assert len(first.plan_hash) == 64

    other_data = (
        Query(columns=SALES_COLUMNS, rows=[[9, 9, 9.0]])
        .top_k("amount", 3)
        .run(runtime, routing_module="stats")
    )
    assert other_data.plan_hash == first.plan_hash


def test_plan_hash_changes_when_the_plan_changes(runtime):
    three = _sales().top_k("amount", 3).run(runtime, routing_module="stats")
    four = _sales().top_k("amount", 4).run(runtime, routing_module="stats")
    assert three.plan_hash != four.plan_hash


def test_a_failing_op_reports_its_index_and_yields_no_rows(runtime):
    with pytest.raises(QueryError) as caught:
        _sales().sort("amount").sort("revenue").run(runtime, routing_module="stats")
    assert caught.value.code == "query_op_failed"
    assert caught.value.op_index == 1
    assert "revenue" in str(caught.value)


def test_a_misspelled_aggregation_is_rejected_by_the_engine(runtime):
    """The builder catches this too; this goes around it to prove the engine does,
    since a caller on another language binding has no builder."""
    plan = _sales()
    plan.ops.append(
        {"op": "aggregate", "by": "region", "value": "amount", "agg": "totl"}
    )
    with pytest.raises(QueryError) as caught:
        plan.run(runtime, routing_module="stats")
    assert "unknown_aggregation" in str(caught.value)


def test_a_resident_dataset_serves_many_queries(runtime):
    """Send the table once; per-query payload is then O(1) in rows."""
    handle = runtime.open_dataset(
        [row[:] for row in SALES_ROWS], name="sales", routing_module="stats"
    )
    try:
        totals = []
        for threshold in (50, 150, 500):
            result = (
                Query(columns=SALES_COLUMNS, dataset=handle)
                .filter(col("amount") > threshold)
                .group_by("region", "amount", agg="sum")
                .run(runtime, routing_module="stats")
            )
            totals.append(sum(v for _, v in result.rows if v is not None))
        assert totals == [2387.0, 2287.0, 1887.0]

        # And it agrees with the inline form exactly.
        inline = (
            _sales()
            .filter(col("amount") > 150)
            .group_by("region", "amount", agg="sum")
            .run(runtime, routing_module="stats")
        )
        resident = (
            Query(columns=SALES_COLUMNS, dataset=handle)
            .filter(col("amount") > 150)
            .group_by("region", "amount", agg="sum")
            .run(runtime, routing_module="stats")
        )
        assert resident.rows == inline.rows
        assert resident.plan_hash == inline.plan_hash
    finally:
        runtime.close_dataset(handle, routing_module="stats")


def test_an_unknown_dataset_handle_errors_rather_than_returning_empty(runtime):
    """An empty answer to a query over data that is not there looks like a real one."""
    with pytest.raises(QueryError) as caught:
        Query(columns=SALES_COLUMNS, dataset="ds_99999").run(
            runtime, routing_module="stats"
        )
    assert caught.value.code == "unknown_dataset"
    assert "ds_99999" in str(caught.value)


def test_a_query_output_can_be_reopened_and_queried_again(runtime):
    """The response shape is accepted as dataset input, so a two-stage analysis needs
    no reshaping between stages."""
    first = (
        _sales()
        .group_by("region", "amount", agg="sum")
        .run(runtime, routing_module="stats")
    )
    handle = runtime.open_dataset(
        {"columns": first.columns, "rows": first.rows},
        name="totals",
        routing_module="stats",
    )
    try:
        second = (
            Query(columns=first.columns, dataset=handle)
            .filter(col("sum_amount") > 1000)
            .run(runtime, routing_module="stats")
        )
        assert second.rows == [[2.0, 1887.0]]
    finally:
        runtime.close_dataset(handle, routing_module="stats")


def test_a_larger_table_runs_and_stays_correct(runtime):
    """Enough rows and groups that the hash index is doing real work."""
    rows = [[float(i % 97), float(i % 13)] for i in range(5000)]
    result = (
        Query(columns=["g", "v"], rows=rows)
        .group_by("g", "v", agg="count")
        .run(runtime, routing_module="stats")
    )
    assert len(result) == 97
    assert sum(result.column("count_v")) == 5000.0


def test_query_does_not_disturb_a_plain_execute(runtime):
    """The new message type must not change the existing dispatch path."""
    before = runtime.execute("stats", "compute_mean", [[1.0, 2.0, 3.0], 3])
    _sales().group_by("region", "amount", agg="sum").run(
        runtime, routing_module="stats"
    )
    after = runtime.execute("stats", "compute_mean", [[1.0, 2.0, 3.0], 3])
    assert before["success"] and after["success"]
    assert before["result"] == after["result"] == 2.0


@pytest.mark.parametrize(
    "name",
    ["región", "café_total", "売上", "Umsatz_größe", "col with space", 'quote"inside'],
)
def test_a_non_ascii_column_name_works_end_to_end(runtime, name):
    """Regression: every op referencing a non-ASCII column name used to fail.

    `json.dumps` escapes non-ASCII by default, so `región` crossed the wire as
    `regi\\u00f3n`. The header path kept the backslash and the frozen `json_get_string`
    ate it, so the two disagreed — `regi\\u00f3n` vs `regiu00f3n` — and a group_by on
    that column failed with "which the batch does not have", naming a column that was
    right there. Spanish, French, German and Japanese column names were all broken.

    Asserts the name resolves AND comes back byte-identical: emitting it through
    `chr(Int(byte))` on the way out re-encodes bytes >= 0x80, so the caller would receive
    a different name than it sent even when the query worked.
    """
    result = (
        Query(columns=[name, "importe"], rows=[[1, 10.0], [2, 20.0], [1, 30.0]])
        .filter(col("importe") > 5)
        .group_by(name, "importe", agg="sum")
        .run(runtime, routing_module="stats")
    )
    assert result.columns[0] == name, "the name came back changed"
    assert result.columns[1] == "sum_importe"
    assert result.rows == [[1.0, 40.0], [2.0, 20.0]]
    # And it is addressable under the name the caller used.
    assert result.column(name) == [1.0, 2.0]


def test_a_non_ascii_name_does_not_change_the_plan_hash_semantics(runtime):
    """Two different non-ASCII names must give two different plan hashes.

    If the decoder collapsed distinct names to the same mangled string, two different
    plans would share a hash — and a cache keyed on it would serve one query's answer
    for another.
    """
    def run(name):
        return (
            Query(columns=[name, "v"], rows=[[1, 10.0]])
            .group_by(name, "v", agg="sum")
            .run(runtime, routing_module="stats")
        )

    a = run("región")
    b = run("regiön")
    assert a.plan_hash != b.plan_hash, "distinct names collapsed to one hash"
    assert len(a.plan_hash) == 64
