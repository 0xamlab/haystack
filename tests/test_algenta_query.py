"""Query-builder tests: plan shape, expression flattening, input validation.

No worker here — these pin the parts that decide what the engine is asked to do. The
kernel side is covered by mojo/tests/libs/test_query_plan.mojo, and the round trip by
tests/integration/test_query_plane_e2e.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.native import worker as worker_mod  # noqa: E402
from algenta.query import (  # noqa: E402
    Expr,
    Query,
    QueryError,
    QueryResult,
    col,
    lit,
    run_query,
)


def _plan(**kwargs) -> Query:
    kwargs.setdefault("columns", ["region", "amount"])
    kwargs.setdefault("rows", [[1, 10.5], [2, 50], [1, 30], [3, None]])
    return Query(**kwargs)


# ── expression flattening ─────────────────────────────────────────────────────


def test_children_always_precede_parents():
    """The invariant the engine validates; it is what makes a cycle unrepresentable."""
    plan = ((col("amount") > 20) & (col("region") < 3)).to_plan()
    for index, node in enumerate(plan["nodes"]):
        for side in ("left", "right"):
            if side in node:
                assert node[side] < index, f"node {index} references {side}={node[side]}"
    assert plan["root"] == len(plan["nodes"]) - 1


def test_column_reference_carries_the_name_not_an_index():
    """By name, so reordering the header cannot silently retarget the plan."""
    (node,) = (col("amount")).to_plan()["nodes"]
    assert node == {"op": 130, "column": "amount"}


def test_float_literals_keep_their_fraction():
    """20.5 must not become 20 — a filter that moved its own boundary is silent."""
    plan = (col("amount") > 20.5).to_plan()
    literals = [n for n in plan["nodes"] if n.get("op") == 0]
    assert literals == [{"op": 0, "value": 20.5}]


def test_int_literal_becomes_a_float():
    plan = (col("amount") > 20).to_plan()
    assert [n for n in plan["nodes"] if n.get("op") == 0] == [{"op": 0, "value": 20.0}]


def test_bool_is_coerced_before_the_int_branch():
    """bool subclasses int, so an unguarded int check would make `> True` mean `> 1`
    silently. It still means 1.0 here, but by an explicit branch, not by accident."""
    plan = (col("flag") > True).to_plan()
    assert [n for n in plan["nodes"] if n.get("op") == 0] == [{"op": 0, "value": 1.0}]


def test_a_shared_subexpression_is_emitted_once_per_flatten_call():
    """Two projections over one node array: the array is shared, so a common child
    exists once and the evaluator computes it once."""
    shared = col("amount") * 2
    plan = _plan().project(a=shared + lit(1), b=shared + lit(2))
    expressions = plan.ops[0]["expressions"]
    assert len(expressions["roots"]) == 2
    # Two separate flattens of `shared` into one array: 2 roots, distinct.
    assert expressions["roots"][0] != expressions["roots"][1]
    for index, node in enumerate(expressions["nodes"]):
        for side in ("left", "right"):
            if side in node:
                assert node[side] < index


def test_unary_ops_emit_only_a_left_child():
    plan = (~(col("amount") > 1)).to_plan()
    root = plan["nodes"][plan["root"]]
    assert root["op"] == 112
    assert "left" in root and "right" not in root


def test_null_tests_are_the_one_place_absence_gives_a_known_answer():
    assert col("amount").is_null().to_plan()["nodes"][-1]["op"] == 120
    assert col("amount").is_not_null().to_plan()["nodes"][-1]["op"] == 121


def test_a_string_in_an_expression_is_a_typed_error():
    with pytest.raises(TypeError, match="cannot use str"):
        _ = col("region") > "north"


def test_expr_is_hashable_so_eq_stays_available_for_dicts():
    """`eq` is a method rather than __eq__ precisely so Expr keeps value equality and
    hashability; building a tree from __eq__ would break both."""
    assert hash(col("a")) == hash(col("a"))
    assert col("a") == col("a")
    assert col("a").eq(1).to_plan()["nodes"][-1]["op"] == 104


# ── plan construction ─────────────────────────────────────────────────────────


def test_ops_accumulate_in_order():
    plan = (
        _plan()
        .filter(col("amount") > 20)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .top_k("sum_amount", 5)
    )
    assert [op["op"] for op in plan.ops] == ["filter", "aggregate", "sort", "top_k"]


def test_request_declares_the_message_type_and_the_header():
    request = _plan().filter(col("amount") > 1).to_request()
    assert request["type"] == "query_execute"
    assert request["columns"] == ["region", "amount"]
    assert request["strict"] is False


def test_none_stays_none_through_normalization():
    """An absent cell must not become 0.0 on the way to the worker."""
    request = _plan().to_request()
    assert request["rows"][3] == [3.0, None]


def test_ints_become_floats_but_none_does_not():
    request = Query(columns=["a"], rows=[[1], [None], [2.5]]).to_request()
    assert request["rows"] == [[1.0], [None], [2.5]]


def test_a_row_wider_than_the_header_is_rejected():
    """Guessing would silently drop the extra values."""
    with pytest.raises(ValueError, match="row 0 has 3 values"):
        Query(columns=["a", "b"], rows=[[1, 2, 3]]).to_request()


def test_a_short_row_is_allowed_and_padded_by_the_engine():
    request = Query(columns=["a", "b"], rows=[[1]]).to_request()
    assert request["rows"] == [[1.0]]


def test_a_non_numeric_cell_names_its_row_and_column():
    with pytest.raises(ValueError, match="row 1 column 0 is str"):
        Query(columns=["a"], rows=[[1], ["x"]]).to_request()


def test_empty_columns_is_rejected():
    with pytest.raises(ValueError, match="non-empty columns"):
        Query(columns=[], rows=[[1]])


def test_neither_rows_nor_dataset_is_rejected():
    with pytest.raises(ValueError, match="either rows or a dataset"):
        Query(columns=["a"])


def test_both_rows_and_dataset_is_rejected():
    """Sending both leaves which one is authoritative up to the engine."""
    with pytest.raises(ValueError, match="not both"):
        Query(columns=["a"], rows=[[1]], dataset="ds_1")


def test_a_dataset_plan_sends_the_handle_and_no_rows():
    request = Query(columns=["region", "amount"], dataset="ds_1").to_request()
    assert request["dataset"] == "ds_1"
    assert "rows" not in request


# ── per-operator wire shape ───────────────────────────────────────────────────


def test_sort_defaults_nulls_last_in_both_directions():
    """A null is not a large number, so desc must not surface the unknowns."""
    plan = _plan().sort("amount", desc=True)
    assert plan.ops[0] == {
        "op": "sort",
        "by": "amount",
        "nulls_last": True,
        "desc": True,
    }


def test_multi_key_sort_broadcasts_a_scalar_desc():
    plan = _plan().sort(["region", "amount"], desc=True)
    assert plan.ops[0]["desc"] == [True, True]


def test_multi_key_sort_accepts_a_per_key_desc_list():
    plan = _plan().sort(["region", "amount"], desc=[False, True])
    assert plan.ops[0]["desc"] == [False, True]


def test_a_desc_list_with_a_single_key_is_rejected():
    with pytest.raises(ValueError, match="only be a list"):
        _plan().sort("amount", desc=[True])


def test_an_unknown_aggregation_is_caught_before_the_wire():
    with pytest.raises(ValueError, match="unknown aggregation 'totl'"):
        _plan().group_by("region", "amount", agg="totl")


def test_mean_is_accepted_as_an_alias_for_avg():
    assert _plan().group_by("region", "amount", agg="mean").ops[0]["agg"] == "mean"


def test_group_by_accepts_a_column_list():
    plan = _plan().group_by(["region", "amount"], "amount", agg="count")
    assert plan.ops[0]["by"] == ["region", "amount"]


# ── group_by_many: several aggregates, one op ──────────────────────────────────


def test_group_by_many_emits_one_aggregate_op_with_an_aggs_list():
    plan = _plan().group_by_many(
        "region", [("amount", "sum"), ("amount", "count")]
    )
    assert plan.ops == [
        {
            "op": "aggregate",
            "by": "region",
            "aggs": [
                {"value": "amount", "agg": "sum"},
                {"value": "amount", "agg": "count"},
            ],
        }
    ]


def test_group_by_many_accepts_a_composite_by():
    plan = _plan().group_by_many(["region", "amount"], [("amount", "sum")])
    assert plan.ops[0]["by"] == ["region", "amount"]


def test_group_by_many_rejects_an_empty_aggs_list():
    with pytest.raises(ValueError, match="non-empty list"):
        _plan().group_by_many("region", [])


def test_group_by_many_catches_an_unknown_aggregation_before_the_wire():
    with pytest.raises(ValueError, match="unknown aggregation 'totl'"):
        _plan().group_by_many("region", [("amount", "totl")])


def test_group_by_many_accepts_mean_as_an_alias_for_avg():
    plan = _plan().group_by_many("region", [("amount", "mean")])
    assert plan.ops[0]["aggs"][0]["agg"] == "mean"


def test_group_by_and_group_by_many_are_independent_of_each_other():
    """`group_by`'s existing single-pair call sites keep working byte for byte —
    `group_by_many` is an additive method, not a widened `group_by` signature."""
    single = _plan().group_by("region", "amount", agg="sum")
    assert single.ops[0] == {
        "op": "aggregate",
        "by": "region",
        "value": "amount",
        "agg": "sum",
    }
    assert "aggs" not in single.ops[0]


def test_project_requires_at_least_one_expression():
    with pytest.raises(ValueError, match="at least one expression"):
        _plan().project()


def test_select_requires_at_least_one_name():
    with pytest.raises(ValueError, match="at least one column name"):
        _plan().select()


def test_top_k_defaults_to_descending():
    """The k *best* rows; ascending would be the k worst."""
    assert _plan().top_k("amount", 3).ops[0]["desc"] is True


def test_limit_carries_offset_and_count():
    assert _plan().limit(5, offset=2).ops[0] == {
        "op": "limit",
        "offset": 2,
        "count": 5,
    }


# ── join and window wire shape ────────────────────────────────────────────────
#
# The engine owns the same checks — a caller on another binding has no builder — so
# these pin only that the builder cannot EMIT an op the kernel would reject, and that
# the request stays byte-identical for a plan with no side tables. Resource limits
# (table count, output rows, window rows) are deliberately absent here: only the engine
# knows the real counts, and one limit at two strengths is worse than one.


def test_a_plan_without_tables_sends_no_tables_key():
    """Byte-identical to what the same plan sent before joins existed, so no plan hash
    that a caller recorded moves."""
    assert "tables" not in _plan().sort("amount").to_request()


def test_a_table_travels_beside_the_plan_not_inside_the_op():
    """`plan_hash` is over `ops`; rows inside an op would make it data-dependent, and
    two runs of one computation over different data would stop comparing."""
    plan = (
        _plan()
        .with_table("customers", ["id", "tier"], rows=[[7, 1]])
        .join("customers", left_on="region", right_on="id", how="left")
    )
    request = plan.to_request()
    assert request["tables"] == [
        {"name": "customers", "columns": ["id", "tier"], "rows": [[7.0, 1.0]]}
    ]
    assert request["ops"] == [
        {
            "op": "join",
            "table": "customers",
            "left_on": "region",
            "right_on": "id",
            "how": "left",
            "method": "hash",
        }
    ]
    assert "rows" not in request["ops"][0]


def test_a_table_takes_rows_or_a_handle_but_not_both():
    with pytest.raises(QueryError, match="exactly one of rows or dataset"):
        _plan().with_table("customers", ["id"], rows=[[1]], dataset="ds_1")
    with pytest.raises(QueryError, match="exactly one of rows or dataset"):
        _plan().with_table("customers", ["id"])


def test_a_table_name_is_declared_once():
    """Two entries with one name would leave which body a join reads to the engine."""
    plan = _plan().with_table("customers", ["id"], rows=[[1]])
    with pytest.raises(QueryError, match="declared twice"):
        plan.with_table("customers", ["id"], rows=[[2]])


def test_the_on_shorthand_is_spelled_out_on_the_wire():
    plan = _plan().with_table("c", ["region"], rows=[[1]]).join("c", on="region")
    assert plan.ops[0]["left_on"] == plan.ops[0]["right_on"] == "region"


def test_a_mix_of_on_and_one_side_is_rejected():
    plan = _plan().with_table("c", ["id"], rows=[[1]])
    with pytest.raises(QueryError, match="not a mix"):
        plan.join("c", on="region", right_on="id")


def test_an_unimplemented_join_is_rejected_by_name():
    """Never silently mapped to `left`, which answers a different question."""
    for how in ("right", "outer", "full", "cross"):
        with pytest.raises(QueryError, match="not implemented"):
            _plan().join("c", on="region", how=how)


def test_a_merge_semi_join_is_rejected_rather_than_falling_back_to_hash():
    with pytest.raises(QueryError, match="not defined for how 'semi'"):
        _plan().join("c", on="region", how="semi", method="merge")


def test_a_prefix_on_a_semi_join_is_rejected_rather_than_ignored():
    """semi/anti emit no right columns, so a prefix would silently do nothing."""
    with pytest.raises(QueryError, match="no right columns"):
        _plan().join("c", on="region", how="anti", prefix="c.")


def test_an_undeclared_table_is_caught_before_the_wire():
    plan = _plan().with_table("customers", ["id"], rows=[[1]])
    plan.join("orders", on="region")
    with pytest.raises(QueryError, match="available: customers"):
        plan.to_request()


def test_a_join_error_carries_the_index_the_op_would_have_had():
    plan = _plan().sort("amount")
    with pytest.raises(QueryError) as caught:
        plan.join("c", on="region", how="cross")
    assert caught.value.op_index == 1


# ── union wire shape ────────────────────────────────────────────────────────────


def test_union_emits_a_tables_array_in_the_given_order():
    plan = (
        _plan()
        .with_table("a", ["region", "amount"], rows=[[1, 1.0]])
        .with_table("b", ["region", "amount"], rows=[[2, 2.0]])
        .union("a", "b")
    )
    assert plan.ops[-1] == {"op": "union", "tables": ["a", "b"]}


def test_union_needs_at_least_one_table_name():
    with pytest.raises(QueryError, match="at least one table name"):
        _plan().union()


def test_union_rejects_a_non_string_table_name():
    with pytest.raises(QueryError, match="non-empty strings"):
        _plan().union("")


def test_an_undeclared_union_table_is_caught_before_the_wire():
    """Same pre-flight `to_request` check `join` already has: only the engine
    knows the real table set, but a plan naming a table it never declared is a
    caller mistake catchable before a round trip."""
    plan = _plan().with_table("a", ["region"], rows=[[1]])
    plan.union("a", "b")
    with pytest.raises(QueryError, match="available: a"):
        plan.to_request()


def test_a_union_error_carries_the_index_the_op_would_have_had():
    plan = _plan().sort("amount")
    plan.union("nope")
    with pytest.raises(QueryError) as caught:
        plan.to_request()
    assert caught.value.op_index == 1


def test_union_composes_with_a_following_group_by_many():
    plan = (
        _plan()
        .with_table("b", ["region", "amount"], rows=[[2, 2.0]])
        .union("b")
        .group_by_many("region", [("amount", "sum"), ("amount", "count")])
    )
    assert [op["op"] for op in plan.ops] == ["union", "aggregate"]


def test_the_window_output_name_is_emitted_as_as():
    """`as` is a Python keyword, so the builder kwarg is `name=`."""
    plan = _plan().row_number(name="seq", partition_by="region", order_by="amount")
    assert plan.ops[0] == {
        "op": "window",
        "fn": "row_number",
        "as": "seq",
        "nulls_last": True,
        "partition_by": ["region"],
        "order_by": ["amount"],
    }


def test_a_window_needs_an_output_name():
    with pytest.raises(QueryError, match="requires 'as'"):
        _plan().window("row_number", name="", order_by="amount")


def test_an_unknown_window_fn_lists_the_accepted_set():
    with pytest.raises(QueryError, match="got 'ntile'"):
        _plan().window("ntile", name="x", order_by="amount")


def test_rank_needs_exactly_one_order_column():
    """`_rank_column` defines a tie by that one column; several would report ties that
    are not ties."""
    with pytest.raises(QueryError, match="exactly one 'order_by'"):
        _plan().window("rank", name="r", order_by=["region", "amount"])


def test_every_fn_but_partition_total_needs_an_order():
    with pytest.raises(QueryError, match="non-empty 'order_by'"):
        _plan().window("cumulative", name="t", value="amount", agg="sum")
    # Order-independent by definition, so its absence is not an error.
    assert "order_by" not in _plan().partition_total(
        "amount", name="total", partition_by="region"
    ).ops[0]


def test_a_desc_list_must_match_the_order_columns():
    with pytest.raises(QueryError, match="2 expected, 1 given"):
        _plan().window(
            "row_number", name="seq", order_by=["region", "amount"], desc=[True]
        )


def test_a_scalar_desc_is_broadcast_across_the_order_columns():
    plan = _plan().window(
        "row_number", name="seq", order_by=["region", "amount"], desc=True
    )
    assert plan.ops[0]["desc"] == [True, True]


def test_a_value_is_required_where_it_is_read_and_rejected_where_it_is_not():
    with pytest.raises(QueryError, match="requires 'value'"):
        _plan().window("lag", name="prev", order_by="amount")
    with pytest.raises(QueryError, match="takes no 'value'"):
        _plan().window("row_number", name="seq", order_by="amount", value="amount")


def test_a_window_aggregation_the_frame_cannot_answer_is_rejected():
    """`var` would come back as a full column of nulls carrying a success status."""
    for agg in ("var", "std", "median"):
        with pytest.raises(QueryError, match="not defined over a window frame"):
            _plan().running("amount", name="v", order_by="amount", agg=agg)


def test_a_lag_offset_must_be_at_least_one():
    """A signed offset is not the wire API: `lag` with -1 would silently be a lead."""
    with pytest.raises(QueryError, match="'offset' >= 1"):
        _plan().lag("amount", name="prev", order_by="amount", offset=0)
    assert _plan().lag("amount", name="prev", order_by="amount").ops[0]["offset"] == 1


def test_a_rolling_frame_needs_a_preceding_and_a_negative_one_is_rejected():
    """-1 is FRAME_UNBOUNDED inside the kernel and never crosses the wire, so a stray
    -1 cannot turn a rolling frame into a cumulative one."""
    with pytest.raises(QueryError, match="use fn 'cumulative'"):
        _plan().window("framed", name="a", order_by="amount", value="amount", agg="avg")
    with pytest.raises(QueryError, match="use fn 'cumulative'"):
        _plan().rolling(
            "amount", name="a", order_by="amount", preceding=-1, agg="avg"
        )
    assert _plan().rolling(
        "amount", name="a", order_by="amount", preceding=2, agg="avg"
    ).ops[0]["preceding"] == 2


def test_an_integer_the_wire_cannot_carry_is_rejected_not_wrapped():
    """The engine reads a plan's integers as signed 64-bit with `value*10 + digit`,
    which wraps instead of trapping — so `offset=2**64 + 3` would arrive as a lag of 3
    and be answered successfully. Every integer that reaches the wire is range-checked
    here, where the value the caller wrote still exists to quote back."""
    past = 2**63
    for build in (
        lambda v: _plan().lag("amount", name="p", order_by="amount", offset=v),
        lambda v: _plan().lead("amount", name="n", order_by="amount", offset=v),
        lambda v: _plan().rolling(
            "amount", name="r", order_by="amount", preceding=v
        ),
        lambda v: _plan().limit(v),
        lambda v: _plan().limit(10, offset=v),
        lambda v: _plan().top_k("amount", v),
    ):
        with pytest.raises(QueryError, match="signed 64-bit") as raised:
            build(past + 3)
        assert raised.value.code == "invalid_arguments"
        assert raised.value.op_index == 0
        # The boundary itself still crosses, so the check rejects only what wraps.
        build(past - 1)


def test_a_non_integer_offset_is_named_rather_than_crashing_the_builder():
    """`int(float('inf'))` raises OverflowError, `int('x')` a ValueError and
    `int(None)` a TypeError — three exception types for one caller mistake, so they
    are normalised into the QueryError the rest of this builder raises."""
    for value in (float("inf"), float("nan"), "seven", object()):
        with pytest.raises(QueryError, match="must be an integer"):
            _plan().lag("amount", name="p", order_by="amount", offset=value)


def test_the_sugar_emits_the_same_op_as_the_general_form():
    """One op vocabulary, several spellings — the sugar must not become a dialect."""
    sugar = _plan().running(
        "amount", name="t", partition_by="region", order_by="amount"
    )
    general = _plan().window(
        "cumulative",
        name="t",
        partition_by="region",
        order_by="amount",
        value="amount",
        agg="sum",
    )
    assert sugar.ops == general.ops


# ── result decoding ───────────────────────────────────────────────────────────


def _result() -> QueryResult:
    return QueryResult(
        columns=["region", "sum_amount"],
        rows=[[1.0, 40.5], [2.0, None]],
        lineage=[{"index": 0, "op": "aggregate", "shape": "2 rows x 2 cols"}],
        plan_hash="a" * 64,
        ops=1,
        latency_ms=0.4,
    )


def test_result_column_lookup_by_name():
    assert _result().column("sum_amount") == [40.5, None]


def test_an_absent_result_column_raises_naming_what_exists():
    with pytest.raises(KeyError, match="sum_amount"):
        _result().column("revenue")


def test_result_len_is_the_row_count():
    assert len(_result()) == 2


def test_to_dicts_preserves_none():
    assert _result().to_dicts() == [
        {"region": 1.0, "sum_amount": 40.5},
        {"region": 2.0, "sum_amount": None},
    ]


# ── transport error handling ──────────────────────────────────────────────────


class _Calls:
    """Records what reached the transport, so routing and timeout are checkable."""

    def __init__(self) -> None:
        self.calls: list[dict] = []


def _patch_worker(monkeypatch, response=None, *, raise_unavailable=False) -> _Calls:
    """Stub `worker.execute` on the real module, matching the batch/pipeline suites.

    Stubbing the module attribute rather than injecting a fake object keeps
    `worker.NativeWorkerUnavailable` the genuine exception type, so the except clause
    under test is the one that would run in production.
    """
    recorded = _Calls()

    def fake_execute(request, **kwargs):
        recorded.calls.append({"request": request, **kwargs})
        if raise_unavailable:
            raise worker_mod.NativeWorkerUnavailable("no runtime")
        return response

    monkeypatch.setattr(worker_mod, "execute", fake_execute)
    return recorded


def test_an_engine_error_raises_rather_than_returning_empty_rows(monkeypatch):
    """An empty result would be a correct-looking answer to a question never asked."""
    fake = _patch_worker(
        monkeypatch,
        {
            "error_code": "query_op_failed",
            "error_message": "op 1 (sort): no column 'revenue'",
            "op_index": 1,
        },
    )
    with pytest.raises(QueryError) as caught:
        run_query(
            _plan().sort("revenue"),
            routing_module="stats",
            timeout=5.0,
            require_verified=False,
        )
    assert caught.value.code == "query_op_failed"
    assert caught.value.op_index == 1
    assert fake.calls[0]["module_name"] == "stats"


def test_an_unavailable_runtime_becomes_a_typed_query_error(monkeypatch):
    _patch_worker(monkeypatch, raise_unavailable=True)
    with pytest.raises(QueryError) as caught:
        run_query(
            _plan(), routing_module="stats", timeout=5.0, require_verified=False
        )
    assert caught.value.code == "compute_runtime_unavailable"


def test_a_successful_response_is_decoded_into_a_result(monkeypatch):
    _patch_worker(
        monkeypatch,
        {
            "result": {"columns": ["region", "sum_amount"], "rows": [[1.0, 40.5]]},
            "lineage": [{"index": 0, "op": "aggregate", "shape": "1 rows x 2 cols"}],
            "plan_hash": "b" * 64,
            "ops": 1,
            "rows": 1,
        },
    )
    result = run_query(
        _plan().group_by("region", "amount"),
        routing_module="stats",
        timeout=5.0,
        require_verified=False,
    )
    assert result.columns == ["region", "sum_amount"]
    assert result.rows == [[1.0, 40.5]]
    assert result.plan_hash == "b" * 64
    assert result.ops == 1
    assert result.latency_ms >= 0.0


def test_the_routing_module_reaches_the_worker(monkeypatch):
    fake = _patch_worker(monkeypatch, {"result": {"columns": [], "rows": []}})
    run_query(
        _plan(), routing_module="timeseries_stats", timeout=3.0, require_verified=True
    )
    assert fake.calls[0]["module_name"] == "timeseries_stats"
    assert fake.calls[0]["require_verified"] is True
    assert fake.calls[0]["timeout"] == 3.0


def test_the_whole_plan_travels_in_one_call(monkeypatch):
    """Four operators, one dispatch — the property the plan layer exists for."""
    fake = _patch_worker(monkeypatch, {"result": {"columns": [], "rows": []}})
    run_query(
        _plan()
        .filter(col("amount") > 20)
        .group_by("region", "amount", agg="sum")
        .sort("sum_amount", desc=True)
        .limit(10),
        routing_module="stats",
        timeout=5.0,
        require_verified=False,
    )
    assert len(fake.calls) == 1
    assert len(fake.calls[0]["request"]["ops"]) == 4


def test_lazy_exports_reach_the_query_surface():
    import algenta

    assert algenta.Query is Query
    assert algenta.col is col
    assert algenta.lit is lit
    assert algenta.QueryError is QueryError
    for name in ("Query", "Expr", "col", "lit", "QueryError", "QueryResult"):
        assert name in algenta.__all__
