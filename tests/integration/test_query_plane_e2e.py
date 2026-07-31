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


# ── join, through the compiled binary ─────────────────────────────────────────
#
# Rule 1b: the kernel suite for these ops runs under `mojo run`, which is more
# forgiving about freed memory than the optimized worker. `query/plan.mojo` once
# shipped a use-after-free that passed 46/46 under the JIT and then crashed `filter`
# and made `project` read a garbage op name in this binary. Every assertion below on
# an echoed op name or a returned column name is that tripwire, not decoration.

ORDER_COLUMNS = ["order_id", "customer_id", "amount"]
ORDER_ROWS = [
    [1, 7, 10.0],
    [2, 8, 20.0],
    [3, 7, 30.0],
    [4, None, 40.0],  # a null key: it matches nothing, not even another null
]
CUSTOMER_COLUMNS = ["id", "tier"]
CUSTOMER_ROWS = [[7, 1], [9, 3]]


def _orders() -> Query:
    return Query(
        columns=ORDER_COLUMNS, rows=[row[:] for row in ORDER_ROWS]
    ).with_table(
        "customers", CUSTOMER_COLUMNS, rows=[row[:] for row in CUSTOMER_ROWS]
    )


def test_an_inner_join_pairs_on_the_key_and_drops_the_rest(runtime):
    """Orders 1 and 3 have customer 7; order 2's customer 8 is absent from the table
    and order 4 has no customer at all. Neither survives an inner join."""
    result = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id")
        .run(runtime, routing_module="stats")
    )
    assert result.columns == [
        "order_id",
        "customer_id",
        "amount",
        "customers.id",
        "customers.tier",
    ]
    assert result.rows == [
        [1.0, 7.0, 10.0, 7.0, 1.0],
        [3.0, 7.0, 30.0, 7.0, 1.0],
    ]
    # The echoed op name is the use-after-free tripwire: a garbage name was the tell.
    assert [entry["op"] for entry in result.lineage] == ["join"]


def test_a_left_join_keeps_the_unmatched_row_with_nulls_not_zeros(runtime):
    """The most important join property: `null` across the right columns, never 0.0 —
    a zero tier is a real tier and would be indistinguishable from "no customer"."""
    result = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="left")
        .run(runtime, routing_module="stats")
    )
    assert result.rows == [
        [1.0, 7.0, 10.0, 7.0, 1.0],
        [2.0, 8.0, 20.0, None, None],
        [3.0, 7.0, 30.0, 7.0, 1.0],
        [4.0, None, 40.0, None, None],
    ]
    detail = result.lineage[0]["detail"]
    assert "4 joined rows" in detail
    assert "2 left rows unmatched" in detail, detail
    assert "1 left rows had a null key" in detail, detail


def test_a_null_key_is_dropped_by_inner_and_kept_once_by_left(runtime):
    """`null = null` is unknown, so order 4 joins nothing. Under inner it disappears;
    under left it emits exactly once, not once per right row."""
    inner = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="inner")
        .run(runtime, routing_module="stats")
    )
    left = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="left")
        .run(runtime, routing_module="stats")
    )
    assert 4.0 not in inner.column("order_id")
    assert left.column("order_id").count(4.0) == 1


def test_duplicate_keys_multiply_rather_than_collapse(runtime):
    """Two left rows and two right rows on key 7 -> four output rows. This is the usual
    source of a surprised row count, so the count is asserted, not the set."""
    result = (
        Query(columns=ORDER_COLUMNS, rows=[row[:] for row in ORDER_ROWS])
        .with_table("customers", CUSTOMER_COLUMNS, rows=[[7, 1], [7, 2], [9, 3]])
        .join("customers", left_on="customer_id", right_on="id")
        .run(runtime, routing_module="stats")
    )
    assert len(result) == 4
    assert result.column("customers.tier") == [1.0, 2.0, 1.0, 2.0]


def test_semi_and_anti_never_multiply_and_split_the_known_keys(runtime):
    """EXISTS and NOT EXISTS: left columns only, one row out per row in. The null key
    satisfies neither — it does not match, and it is not KNOWN not to match."""
    semi = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="semi")
        .run(runtime, routing_module="stats")
    )
    anti = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="anti")
        .run(runtime, routing_module="stats")
    )
    assert semi.columns == ORDER_COLUMNS, "semi emits no right columns"
    assert semi.rows == [[1.0, 7.0, 10.0], [3.0, 7.0, 30.0]]
    assert anti.rows == [[2.0, 8.0, 20.0]]
    assert len(semi) + len(anti) == 3, "the null-key row is in neither half"
    assert "left rows matched" in semi.lineage[0]["detail"]


def test_the_on_shorthand_equals_the_two_sided_form(runtime):
    """`on` is `left_on == right_on`, and the shorthand must not mean anything else.

    The `on` op is appended raw rather than through the builder, which always spells
    both sides out: otherwise the engine's shorthand branch would never be exercised by
    this suite even though every non-Python binding will use it.
    """
    shorthand_plan = Query(
        columns=["id", "amount"], rows=[[7, 10.0], [8, 20.0]]
    ).with_table("customers", ["id", "tier"], rows=[[7, 1]])
    shorthand_plan.ops.append({"op": "join", "table": "customers", "on": "id"})
    shorthand = shorthand_plan.run(runtime, routing_module="stats")
    explicit = (
        Query(columns=["id", "amount"], rows=[[7, 10.0], [8, 20.0]])
        .with_table("customers", ["id", "tier"], rows=[[7, 1]])
        .join("customers", left_on="id", right_on="id")
        .run(runtime, routing_module="stats")
    )
    assert shorthand.rows == explicit.rows == [[7.0, 10.0, 7.0, 1.0]]
    assert shorthand.columns == ["id", "amount", "customers.id", "customers.tier"]


def test_the_same_table_joined_twice_needs_two_prefixes(runtime):
    """One table entry, two joins, two prefixes — and the default prefix used twice is
    REJECTED rather than silently shadowing, because `Schema.index_of` returns the
    first match and every later reference would resolve to the wrong column."""
    plan = (
        Query(columns=["buyer_id", "seller_id"], rows=[[7, 9]])
        .with_table("people", ["id", "tier"], rows=[[7, 1], [9, 3]])
        .join("people", left_on="buyer_id", right_on="id", prefix="buyer.")
        .join("people", left_on="seller_id", right_on="id", prefix="seller.")
    )
    result = plan.run(runtime, routing_module="stats")
    assert result.columns == [
        "buyer_id",
        "seller_id",
        "buyer.id",
        "buyer.tier",
        "seller.id",
        "seller.tier",
    ]
    assert result.rows == [[7.0, 9.0, 7.0, 1.0, 9.0, 3.0]]

    collided = (
        Query(columns=["buyer_id", "seller_id"], rows=[[7, 9]])
        .with_table("people", ["id", "tier"], rows=[[7, 1], [9, 3]])
        .join("people", left_on="buyer_id", right_on="id")
        .join("people", left_on="seller_id", right_on="id")
    )
    with pytest.raises(QueryError) as caught:
        collided.run(runtime, routing_module="stats")
    assert caught.value.op_index == 1
    assert "people.id" in str(caught.value)


def test_a_merge_join_agrees_with_a_hash_join_on_sorted_input(runtime):
    """Same answer, no hash table. `merge` verifies its inputs are sorted rather than
    trusting the claim: an unsorted input silently returns a subset of the matches."""
    def plan(method):
        return (
            Query(columns=["id", "amount"], rows=[[7, 10.0], [8, 20.0], [9, 30.0]])
            .with_table("customers", ["id", "tier"], rows=[[7, 1], [9, 3]])
            .join("customers", on="id", method=method)
        )

    assert plan("merge").run(runtime, routing_module="stats").rows == plan("hash").run(
        runtime, routing_module="stats"
    ).rows == [[7.0, 10.0, 7.0, 1.0], [9.0, 30.0, 9.0, 3.0]]


def test_a_merge_join_on_unsorted_input_refuses_rather_than_dropping_matches(runtime):
    """A join that quietly drops matches is worse than one that refuses."""
    with pytest.raises(QueryError) as caught:
        (
            Query(columns=["id", "amount"], rows=[[9, 30.0], [7, 10.0]])
            .with_table("customers", ["id", "tier"], rows=[[7, 1], [9, 3]])
            .join("customers", on="id", method="merge")
            .run(runtime, routing_module="stats")
        )
    assert caught.value.code == "query_op_failed"
    assert "sort" in str(caught.value).lower()


def test_a_join_over_a_resident_table_matches_the_inline_form_exactly(runtime):
    """The `dataset` form of a table entry is a payload optimisation, nothing more: the
    op JSON is byte-identical, so the rows AND the plan hash must be identical too.
    A differing hash would mean the table body had leaked into the plan."""
    handle = runtime.open_dataset(
        [row[:] for row in CUSTOMER_ROWS], name="customers", routing_module="stats"
    )
    try:
        resident = (
            Query(columns=ORDER_COLUMNS, rows=[row[:] for row in ORDER_ROWS])
            .with_table("customers", CUSTOMER_COLUMNS, dataset=handle)
            .join("customers", left_on="customer_id", right_on="id", how="left")
            .run(runtime, routing_module="stats")
        )
        inline = (
            _orders()
            .join("customers", left_on="customer_id", right_on="id", how="left")
            .run(runtime, routing_module="stats")
        )
        assert resident.columns == inline.columns
        assert resident.rows == inline.rows
        assert resident.plan_hash == inline.plan_hash
    finally:
        runtime.close_dataset(handle, routing_module="stats")


def test_an_unknown_table_handle_errors_rather_than_joining_nothing(runtime):
    """An empty right side would look exactly like "no customer matched"."""
    with pytest.raises(QueryError) as caught:
        (
            Query(columns=ORDER_COLUMNS, rows=[row[:] for row in ORDER_ROWS])
            .with_table("customers", CUSTOMER_COLUMNS, dataset="ds_99999")
            .join("customers", left_on="customer_id", right_on="id")
            .run(runtime, routing_module="stats")
        )
    assert caught.value.code == "unknown_dataset"
    assert "ds_99999" in str(caught.value)
    assert "customers" in str(caught.value)


def test_an_undeclared_table_is_rejected_by_the_engine_too(runtime):
    """The builder catches this; this goes around it, because a caller on another
    binding has no builder. Sent as a raw frame for exactly that reason."""
    from algenta.native import worker

    response = worker.execute(
        {
            "type": "query_execute",
            "columns": ORDER_COLUMNS,
            "rows": [[1, 7, 10.0]],
            "tables": [
                {"name": "customers", "columns": CUSTOMER_COLUMNS, "rows": [[7, 1]]}
            ],
            "ops": [
                {"op": "join", "table": "orders", "left_on": "customer_id", "right_on": "id"}
            ],
            "strict": False,
        },
        timeout=60.0,
        require_verified=False,
        module_name="stats",
    )
    message = str(response.get("error_message") or response.get("error") or "")
    assert response.get("error_code"), response
    assert "orders" in message and "customers" in message, message


def test_a_join_key_and_a_prefix_survive_non_ascii_end_to_end(runtime):
    """A join key named `región`, a table named `café_total` and a prefix `売上.`, each
    asserted byte-identical on the way back. Every column name here crosses the wire
    twice — in the header and in the op — and the two paths used to disagree."""
    result = (
        Query(columns=["región", "importe"], rows=[[1, 10.0], [2, 20.0]])
        .with_table("café_total", ["región", "categoría"], rows=[[1, 5.0], [3, 7.0]])
        .join("café_total", on="región", prefix="売上.")
        .run(runtime, routing_module="stats")
    )
    assert result.columns == ["región", "importe", "売上.región", "売上.categoría"]
    assert result.rows == [[1.0, 10.0, 1.0, 5.0]]
    assert result.column("売上.categoría") == [5.0]


def test_a_join_composes_with_the_rest_of_the_plan(runtime):
    """The joined batch is an ordinary batch: filter, group and sort all follow."""
    result = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="left")
        .filter(col("amount") > 15)
        .group_by("customers.tier", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .run(runtime, routing_module="stats")
    )
    # Orders 2 (20, no tier) and 4 (40, no customer) have an absent group key and so
    # form no group; order 3 (30) is tier 1.
    assert result.rows == [[1.0, 30.0]]
    assert [entry["op"] for entry in result.lineage] == [
        "join",
        "filter",
        "aggregate",
        "sort",
    ]


# ── window, through the compiled binary ───────────────────────────────────────

WINDOW_COLUMNS = ["region", "month", "amount"]
WINDOW_ROWS = [
    [1, 1, 100.0],
    [1, 2, 200.0],
    [1, 3, 200.0],  # tied with the row above, which is where rank and dense_rank part
    [2, 1, 70.0],
    [2, 2, 30.0],
]


def _window_plan() -> Query:
    return Query(columns=WINDOW_COLUMNS, rows=[row[:] for row in WINDOW_ROWS])


def test_a_window_column_is_appended_and_row_order_is_unchanged(runtime):
    """The single most load-bearing window property. `partition_rows` computes an
    internal ordering, but permuting the batch into it would silently change what a
    following `limit` or `top_k` means — so the rows come back exactly as sent."""
    result = (
        _window_plan()
        .row_number(name="seq", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    assert result.columns == WINDOW_COLUMNS + ["seq"]
    assert result.rows == [
        [1.0, 1.0, 100.0, 1.0],
        [1.0, 2.0, 200.0, 2.0],
        [1.0, 3.0, 200.0, 3.0],
        [2.0, 1.0, 70.0, 1.0],
        [2.0, 2.0, 30.0, 2.0],
    ]
    assert [entry["op"] for entry in result.lineage] == ["window"]
    assert result.lineage[0]["detail"] == "2 partitions, largest 3 rows"


def test_rank_and_dense_rank_part_ways_on_the_same_tied_data(runtime):
    """Amounts 200, 200, 100 descending rank as 1, 1, 3 and dense-rank as 1, 1, 2.
    Both are standard, they differ only after a tie, and swapping them is invisible
    until someone compares two reports."""
    ranked = (
        _window_plan()
        .rank(name="r", partition_by="region", order_by="amount", desc=True)
        .run(runtime, routing_module="stats")
    )
    dense = (
        _window_plan()
        .dense_rank(name="r", partition_by="region", order_by="amount", desc=True)
        .run(runtime, routing_module="stats")
    )
    assert ranked.column("r") == [3.0, 1.0, 1.0, 1.0, 2.0]
    assert dense.column("r") == [2.0, 1.0, 1.0, 1.0, 2.0]


def test_lag_and_lead_stop_at_the_partition_edge(runtime):
    """Region 2's first month must be absent, NOT region 1's last amount. That bug
    produces a completely plausible number — last December's figure attributed to a
    different region — which is why the edge is asserted as null on both sides."""
    lagged = (
        _window_plan()
        .lag("amount", name="prev", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    led = (
        _window_plan()
        .lead("amount", name="next", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    assert lagged.column("prev") == [None, 100.0, 200.0, None, 70.0]
    assert led.column("next") == [200.0, 200.0, None, 30.0, None]


def test_a_running_total_and_a_rolling_average(runtime):
    """cumulative = the unbounded frame; framed(preceding=1) = a two-row frame that
    clamps at the partition start rather than borrowing the previous partition."""
    running = (
        _window_plan()
        .running("amount", name="running_total", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    rolling = (
        _window_plan()
        .rolling(
            "amount",
            name="avg_2mo",
            partition_by="region",
            order_by="month",
            preceding=1,
            agg="avg",
        )
        .run(runtime, routing_module="stats")
    )
    assert running.column("running_total") == [100.0, 300.0, 500.0, 70.0, 100.0]
    assert rolling.column("avg_2mo") == [100.0, 150.0, 200.0, 70.0, 50.0]


def test_a_partition_total_broadcasts_the_group_answer_to_every_row(runtime):
    """What `SUM(x) OVER (PARTITION BY g)` means — a share-of-total with no join back."""
    result = (
        _window_plan()
        .partition_total("amount", name="region_total", partition_by="region")
        .run(runtime, routing_module="stats")
    )
    assert result.column("region_total") == [500.0, 500.0, 500.0, 100.0, 100.0]


def test_no_partition_by_is_one_partition_over_everything(runtime):
    """`OVER (ORDER BY ...)` with no PARTITION BY. The running total crosses what were
    partition edges precisely because there are none."""
    result = (
        _window_plan()
        .running("amount", name="running_total", order_by=["region", "month"])
        .run(runtime, routing_module="stats")
    )
    assert result.column("running_total") == [100.0, 300.0, 500.0, 570.0, 600.0]
    assert result.lineage[0]["detail"] == "1 partitions, largest 5 rows"


def test_a_null_value_is_skipped_by_the_frame_rather_than_zeroed(runtime):
    """A running SUM steps over the absence and keeps its total; a running AVG divides
    by the live values only. Treating the absence as 0 leaves the sum identical and
    moves the average — the silent divergence."""
    rows = [[1, 1, 100.0], [1, 2, None], [1, 3, 200.0]]
    running = (
        Query(columns=WINDOW_COLUMNS, rows=[row[:] for row in rows])
        .running("amount", name="total", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    averaged = (
        Query(columns=WINDOW_COLUMNS, rows=[row[:] for row in rows])
        .running(
            "amount", name="avg", partition_by="region", order_by="month", agg="avg"
        )
        .run(runtime, routing_module="stats")
    )
    assert running.column("total") == [100.0, 100.0, 300.0]
    assert averaged.column("avg") == [100.0, 100.0, 150.0]


def test_a_null_partition_key_forms_its_own_partition(runtime):
    """Deliberately unlike `group_by`, where a null group key joins no group at all.
    Documented divergence: here the rows with no region are one partition, so a
    row_number over them is 1, 2 rather than absent."""
    result = (
        Query(
            columns=WINDOW_COLUMNS,
            rows=[[1, 1, 10.0], [None, 1, 20.0], [None, 2, 30.0]],
        )
        .row_number(name="seq", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    assert result.column("seq") == [1.0, 1.0, 2.0]
    assert result.lineage[0]["detail"].startswith("2 partitions")


def test_a_window_output_name_survives_non_ascii_end_to_end(runtime):
    """`as` crosses the wire as an op string and comes back as a header name, which are
    the two paths that used to decode `\\u00f3` differently."""
    result = (
        Query(columns=["región", "importe"], rows=[[1, 10.0], [1, 30.0], [2, 20.0]])
        .rank(name="región_rank", partition_by="región", order_by="importe", desc=True)
        .run(runtime, routing_module="stats")
    )
    assert result.columns == ["región", "importe", "región_rank"]
    assert result.column("región_rank") == [2.0, 1.0, 1.0]


def test_a_window_output_name_that_already_exists_is_rejected(runtime):
    """`Schema.index_of` returns the first match, so a duplicate name would silently
    shadow and every later reference would resolve to the wrong column."""
    with pytest.raises(QueryError) as caught:
        (
            _window_plan()
            .window(
                "row_number", name="amount", partition_by="region", order_by="month"
            )
            .run(runtime, routing_module="stats")
        )
    assert caught.value.code == "query_op_failed"
    assert "amount" in str(caught.value)


def test_a_window_aggregation_the_frame_cannot_answer_is_rejected(runtime):
    """`var` would come back as a full column of NULLS carrying a success status — an
    answer that does not exist, reported as one. The builder catches it; this goes
    around the builder, because another binding has none."""
    plan = _window_plan()
    plan.ops.append(
        {
            "op": "window",
            "fn": "cumulative",
            "as": "v",
            "partition_by": ["region"],
            "order_by": ["month"],
            "value": "amount",
            "agg": "var",
        }
    )
    with pytest.raises(QueryError) as caught:
        plan.run(runtime, routing_module="stats")
    assert caught.value.code == "query_op_failed"
    assert "var" in str(caught.value)


def test_a_short_desc_list_is_rejected_rather_than_silently_ascending(runtime):
    """`partition_rows` fills a missing entry with False, so a short list is a
    different ordering and hence different ranks — reported as success today."""
    plan = _window_plan()
    plan.ops.append(
        {
            "op": "window",
            "fn": "row_number",
            "as": "seq",
            "order_by": ["region", "month"],
            "desc": [True],
        }
    )
    with pytest.raises(QueryError) as caught:
        plan.run(runtime, routing_module="stats")
    assert caught.value.code == "query_op_failed"


def _window_row_cap() -> int | None:
    """MAX_WINDOW_ROWS, read from the kernel rather than hardcoded here.

    The cap is a measured number that a faster partition sort would raise, so a literal
    in this test would be a number needing a bump on a change that broke nothing.
    """
    source = _REPO_ROOT / "mojo" / "engine" / "query" / "plan.mojo"
    if not source.is_file():
        return None
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("comptime MAX_WINDOW_ROWS"):
            return int(line.split("=")[1].strip().replace("_", ""))
    return None


def test_a_window_over_too_many_rows_errors_instead_of_hanging(runtime):
    """`partition_rows` sorts with a stable INSERTION sort — one quadratic pass per key —
    and window is the first op to run it on the raw row count. Past the cap that is a
    hang with no diagnosis, so the engine refuses. An honest error beats a hang."""
    cap = _window_row_cap()
    if cap is None:
        pytest.skip("MAX_WINDOW_ROWS not found in query/plan.mojo")
    if cap > 100_000:
        pytest.skip(f"MAX_WINDOW_ROWS is {cap}; sending cap+1 rows here is not worth it")
    rows = [[float(i % 8), float(i % 12), float(i)] for i in range(cap + 1)]
    with pytest.raises(QueryError) as caught:
        (
            Query(columns=WINDOW_COLUMNS, rows=rows)
            .row_number(name="seq", partition_by="region", order_by="month")
            .run(runtime, routing_module="stats")
        )
    assert caught.value.code == "query_op_failed"
    assert str(cap) in str(caught.value), str(caught.value)
    # And one row under the cap still answers, so the cap is a limit and not a wall.
    ok = (
        Query(columns=WINDOW_COLUMNS, rows=rows[:cap])
        .row_number(name="seq", partition_by="region", order_by="month")
        .run(runtime, routing_module="stats")
    )
    assert len(ok) == cap


def test_a_window_and_a_join_compose_in_one_plan(runtime):
    """Both new ops in one dispatch, with the window computed over the joined batch."""
    result = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="left")
        .running(
            "amount",
            name="running_total",
            partition_by="customers.tier",
            order_by="order_id",
        )
        .run(runtime, routing_module="stats")
    )
    assert [entry["op"] for entry in result.lineage] == ["join", "window"]
    # Tier 1 holds orders 1 and 3 (10 then 30); the two tier-less rows are their own
    # partition, ordered by order_id: 20 then 60.
    assert result.column("running_total") == [10.0, 20.0, 40.0, 60.0]


def test_a_plan_with_a_join_hashes_the_computation_not_the_table(runtime):
    """`plan_hash` is over `ops` only, so the table BODY is not in it — exactly as the
    left side's rows are not. The table NAME, keys, how, method and prefix ARE, so the
    hash still identifies the computation."""
    def run(customer_rows):
        return (
            Query(columns=ORDER_COLUMNS, rows=[row[:] for row in ORDER_ROWS])
            .with_table("customers", CUSTOMER_COLUMNS, rows=customer_rows)
            .join("customers", left_on="customer_id", right_on="id", how="left")
            .run(runtime, routing_module="stats")
        )

    first = run([[7, 1], [9, 3]])
    second = run([[7, 2], [9, 9], [11, 4]])
    assert first.plan_hash == second.plan_hash, "the table body leaked into the hash"
    assert first.rows != second.rows

    inner = (
        _orders()
        .join("customers", left_on="customer_id", right_on="id", how="inner")
        .run(runtime, routing_module="stats")
    )
    assert inner.plan_hash != first.plan_hash, "'how' must be in the hash"


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
