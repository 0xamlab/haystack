"""test_query_plan.mojo — known-value tests for the JSON query-plan boundary.

Hand-written. This is the layer that makes the query plane reachable, so the assertions
cover the boundary failures rather than the arithmetic (which `test_query_executor` and
`test_query_aggregate` already pin):

  * a float threshold surviving the parse — `json_get_int` would turn 20.5 into 20 and
    quietly move a filter's boundary;
  * `null` in the input becoming an absence rather than 0.0;
  * a bad column name or unknown aggregation failing with a typed error naming the op
    index, instead of producing a correct answer to a prefix of the plan;
  * plan_hash being over the plan's VALUES, so whitespace and key order do not change
    it but a threshold does.
"""
from query.join import join_output_rows
from query.plan import (
    MAX_MATERIALIZED_CELLS,
    MAX_RESPONSE_BYTES,
    MAX_WINDOW_WORK,
    NamedBatches,
    apply_op,
    apply_op_detailed,
    build_batch,
    json_literal_problem,
    parse_column_names,
    parse_named_tables,
    parse_nodes,
    parse_rows,
    json_string_field,
    json_unescape,
    plan_hash,
    run_query_execute,
    substring,
    table_dataset_handles,
    table_names,
    _batch_to_json,
    _serialized_bytes_ceiling,
    _serialized_bytes_exact,
    _serialized_bytes_floor,
)


comptime OP_GT: Int = 102
comptime OP_LT: Int = 100
comptime OP_COL_REF: Int = 130
comptime OP_ADD: Int = 2

fn _head(value: String, n: Int) -> String:
    """The first `n` bytes, for error output. Uses the kernel's clamped substring."""
    return substring(value, 0, n)


comptime HEADER: String = '{"columns":["region","amount"]}'
comptime ROWS: String = "[[1,10.5],[2,50],[1,30],[3,null]]"

# ── join / window fixtures ────────────────────────────────────────────────────
# Orders, with one row whose join key is NULL (order 4) and one whose key has no partner
# (order 2). Both are the interesting cases: a null key matches nothing even under LEFT,
# and an inner join must drop them both.
comptime ORDERS_HEADER: String = (
    '{"columns":["order_id","customer_id","amount"]}'
)
comptime ORDERS_ROWS: String = "[[1,7,10.0],[2,8,20.0],[3,7,30.0],[4,null,40.0]]"
comptime CUSTOMERS: String = (
    '{"tables":[{"name":"customers","columns":["id","tier"],"rows":[[7,1],[9,3]]}]}'
)
# Two rows sharing key 7, so a join MULTIPLIES rather than collapsing.
comptime CUSTOMERS_DUP: String = (
    '{"tables":[{"name":"customers","columns":["id","tier"],'
    '"rows":[[7,1],[7,2],[9,3]]}]}'
)

# region, month, amount. Partition 1 has four rows with a TIE on amount (20 twice), which
# is the only data on which rank and dense_rank differ; partition 2 has exactly one row.
comptime WINDOW_HEADER: String = '{"columns":["region","month","amount"]}'
comptime WINDOW_ROWS: String = (
    "[[1,1,10.0],[1,2,20.0],[1,3,20.0],[1,4,30.0],[2,1,50.0]]"
)


fn _no_tables() -> NamedBatches:
    return NamedBatches()


fn _empty_strings() -> List[String]:
    return List[String]()


fn _same_key_left(n: Int) -> String:
    """`n` order rows all sharing customer_id 1 — the fan-out side of a blowup."""
    var out = String("[")
    for i in range(n):
        if i > 0:
            out += ","
        out += "[" + String(i) + ",1,1.0]"
    out += "]"
    return out


fn _same_key_table(n: Int) -> String:
    """A request whose one table holds `n` rows all sharing id 1."""
    var out = String('{"tables":[{"name":"big","columns":["id","tier"],"rows":[')
    for i in range(n):
        if i > 0:
            out += ","
        out += "[1," + String(i) + "]"
    out += "]}]}"
    return out


fn _wide_rows(n_rows: Int, n_columns: Int, key: Float64) -> String:
    """`n_rows` rows of `n_columns` values, column 0 holding `key` on every row."""
    var out = String("[")
    for r in range(n_rows):
        if r > 0:
            out += ","
        out += "["
        for c in range(n_columns):
            if c > 0:
                out += ","
            if c == 0:
                out += String(key)
            else:
                out += "1.0"
        out += "]"
    out += "]"
    return out


fn _wide_header_array(prefix: String, n_columns: Int) -> String:
    """Just the `columns` ARRAY, for embedding in a `tables` entry."""
    var out = String("[")
    for c in range(n_columns):
        if c > 0:
            out += ","
        out += '"' + prefix + String(c) + '"'
    out += "]"
    return out


fn _wide_header(prefix: String, n_columns: Int) -> String:
    return '{"columns":' + _wide_header_array(prefix, n_columns) + "}"


fn main() raises:
    var passed = 0
    var failed = 0

    # ── column names come back unquoted, in order ────────────────────────────
    var names = parse_column_names(HEADER)
    if len(names) == 2 and names[0] == "region" and names[1] == "amount":
        passed += 1
        print("  ✅ column names parse unquoted and in order")
    else:
        failed += 1
        print("  ❌ column names wrong:", len(names))

    # ── rows transpose, and `null` becomes an absence not a 0.0 ──────────────
    var batch = build_batch(HEADER, ROWS)
    if (
        batch.n_rows == 4
        and batch.width() == 2
        and batch.is_consistent()
        and batch.column(1).get(0) == 10.5   # the float survived
        and not batch.column(1).is_valid_at(3)
    ):
        passed += 1
        print("  ✅ 4x2 batch; 10.5 kept its fraction and null is absent, not 0.0")
    else:
        failed += 1
        print("  ❌ ingest wrong:", batch.n_rows, batch.column(1).get(0))

    # ── column names are addressable, so a plan targets by name ──────────────
    if batch.column_index("amount") == 1 and batch.column_index("nope") == -1:
        passed += 1
        print("  ✅ the schema carries the caller's names")
    else:
        failed += 1
        print("  ❌ schema names lost")

    # ── a short row is padded with absences ──────────────────────────────────
    var short = build_batch(HEADER, "[[1,10],[2]]")
    if short.n_rows == 2 and short.column(1).is_valid_at(0) and not short.column(
        1
    ).is_valid_at(1):
        passed += 1
        print("  ✅ a trailing missing field becomes a null rather than an error")
    else:
        failed += 1
        print("  ❌ short-row padding wrong")

    # ── a row LONGER than the header is rejected ─────────────────────────────
    # Guessing would silently drop the extra values.
    var too_wide_rejected = False
    try:
        var _bad = build_batch(HEADER, "[[1,10,999]]")
    except:
        too_wide_rejected = True
    if too_wide_rejected:
        passed += 1
        print("  ✅ a row with more values than columns is rejected, not truncated")
    else:
        failed += 1
        print("  ❌ over-wide row accepted")

    # ── an empty header is rejected ──────────────────────────────────────────
    var no_header_rejected = False
    try:
        var _bad2 = build_batch('{"columns":[]}', "[[1]]")
    except:
        no_header_rejected = True
    if no_header_rejected:
        passed += 1
        print("  ✅ an empty columns array is rejected")
    else:
        failed += 1
        print("  ❌ empty header accepted")

    # ── a FLOAT threshold survives the expression parse ──────────────────────
    # This is the assertion the second node parser was deleted for. json_get_int would
    # read 20.5 as 20 and move the filter's boundary by half a unit, silently.
    var predicate = (
        '{"nodes":['
        '{"op":130,"column":"amount"},'
        '{"op":0,"value":20.5},'
        '{"op":102,"left":0,"right":1}'
        '],"root":2}'
    )
    var nodes = parse_nodes(predicate, batch.schema)
    if len(nodes) == 3 and nodes[1].fval == 20.5 and nodes[0].var_idx == 1:
        passed += 1
        print("  ✅ literal 20.5 parses as 20.5, and the column name resolved to 1")
    else:
        failed += 1
        print("  ❌ expression parse wrong:", nodes[1].fval)

    # ── a negative literal and an exponent parse too ─────────────────────────
    var numeric_edge = (
        '{"nodes":[{"op":0,"value":-3.5},{"op":0,"value":1.5e2}],"root":1}'
    )
    var edge_nodes = parse_nodes(numeric_edge, batch.schema)
    if len(edge_nodes) == 2 and edge_nodes[0].fval == -3.5 and edge_nodes[
        1
    ].fval == 150.0:
        passed += 1
        print("  ✅ -3.5 and 1.5e2 both parse correctly")
    else:
        failed += 1
        print("  ❌ numeric edge cases wrong:", edge_nodes[0].fval, edge_nodes[1].fval)

    # ── an unknown column name in an expression is rejected by NAME ──────────
    var bad_column_rejected = False
    try:
        var _bad3 = parse_nodes(
            '{"nodes":[{"op":130,"column":"revenue"}],"root":0}', batch.schema
        )
    except e:
        bad_column_rejected = String(e).find("revenue") >= 0
    if bad_column_rejected:
        passed += 1
        print("  ✅ an unknown column name is rejected, and the error names it")
    else:
        failed += 1
        print("  ❌ unknown column not rejected by name")

    # ── filter through apply_op ──────────────────────────────────────────────
    var filtered = apply_op(
        batch, '{"op":"filter","predicate":' + predicate + "}", False
    )
    if filtered.n_rows == 2 and filtered.column(1).get(0) == 50.0:
        passed += 1
        print("  ✅ filter amount > 20.5 keeps the 50 and the 30, drops 10.5 and null")
    else:
        failed += 1
        print("  ❌ filter through apply_op wrong:", filtered.n_rows)

    # ── grouped aggregate through apply_op ───────────────────────────────────
    var grouped = apply_op(
        batch, '{"op":"aggregate","by":"region","value":"amount","agg":"sum"}', False
    )
    if (
        grouped.n_rows == 3
        and grouped.width() == 2
        and grouped.schema.name_at(0) == "region"
        and grouped.schema.name_at(1) == "sum_amount"
        and grouped.column(1).get(0) == 40.5   # region 1: 10.5 + 30
        and grouped.column(1).get(1) == 50.0
    ):
        passed += 1
        print("  ✅ aggregate by region yields region/sum_amount with 40.5 and 50")
    else:
        failed += 1
        print("  ❌ aggregate wrong:", grouped.n_rows, grouped.column(1).get(0))

    # ── region 3's only amount is null: sum 0 is an answer, mean is not ──────
    var mean_grouped = apply_op(
        batch, '{"op":"aggregate","by":"region","value":"amount","agg":"mean"}', False
    )
    if (
        grouped.column(1).is_valid_at(2)
        and grouped.column(1).get(2) == 0.0
        and not mean_grouped.column(1).is_valid_at(2)
    ):
        passed += 1
        print("  ✅ region 3: sum is a real 0, mean is absent — numeric.contract holds")
    else:
        failed += 1
        print("  ❌ empty-group policy did not survive the JSON boundary")

    # ── `mean` is accepted as an alias for `avg`, and echoed as avg ──────────
    if mean_grouped.schema.name_at(1) == "avg_amount":
        passed += 1
        print("  ✅ 'mean' is accepted and echoed back canonically as avg_amount")
    else:
        failed += 1
        print("  ❌ aggregation token not canonicalised:", mean_grouped.schema.name_at(1))

    # ── an unknown aggregation is an error listing the accepted set ──────────
    var unknown_agg_rejected = False
    try:
        var _bad4 = apply_op(
            batch, '{"op":"aggregate","by":"region","value":"amount","agg":"totl"}', False
        )
    except e:
        unknown_agg_rejected = String(e).find("unknown_aggregation") >= 0 and String(
            e
        ).find("count") >= 0
    if unknown_agg_rejected:
        passed += 1
        print("  ✅ a misspelled aggregation errors and lists what is accepted")
    else:
        failed += 1
        print("  ❌ unknown aggregation not rejected properly")

    # ── multi-column group-by keeps one column per key ───────────────────────
    var multi_grouped = apply_op(
        batch,
        '{"op":"aggregate","by":["region","amount"],"value":"amount","agg":"count"}',
        False,
    )
    if multi_grouped.width() == 3 and multi_grouped.schema.name_at(2) == "count_amount":
        passed += 1
        print("  ✅ grouping by two columns yields both key columns plus the aggregate")
    else:
        failed += 1
        print("  ❌ multi-column group-by wrong:", multi_grouped.width())

    # ── sort, top_k, distinct, limit, select through apply_op ────────────────
    var sorted_desc = apply_op(
        batch, '{"op":"sort","by":"amount","desc":true,"nulls_last":true}', False
    )
    if sorted_desc.column(1).get(0) == 50.0 and not sorted_desc.column(
        1
    ).is_valid_at(3):
        passed += 1
        print("  ✅ sort desc puts 50 first and the null last")
    else:
        failed += 1
        print("  ❌ sort through apply_op wrong")

    var topped = apply_op(batch, '{"op":"top_k","by":"amount","k":2,"desc":true}', False)
    if topped.n_rows == 2 and topped.column(1).get(0) == 50.0:
        passed += 1
        print("  ✅ top_k k=2 returns the two largest")
    else:
        failed += 1
        print("  ❌ top_k wrong:", topped.n_rows)

    var deduped = apply_op(batch, '{"op":"distinct","columns":["region"]}', False)
    if deduped.n_rows == 3:
        passed += 1
        print("  ✅ distinct on region yields 3 rows")
    else:
        failed += 1
        print("  ❌ distinct wrong:", deduped.n_rows)

    var windowed = apply_op(batch, '{"op":"limit","offset":1,"count":2}', False)
    if windowed.n_rows == 2 and windowed.column(0).get(0) == 2.0:
        passed += 1
        print("  ✅ limit offset 1 count 2 starts at region 2")
    else:
        failed += 1
        print("  ❌ limit wrong")

    var selected = apply_op(batch, '{"op":"select","columns":["amount"]}', False)
    if selected.width() == 1 and selected.schema.name_at(0) == "amount":
        passed += 1
        print("  ✅ select narrows to one named column")
    else:
        failed += 1
        print("  ❌ select wrong")

    # ── a bad column name in an op is rejected, and the error lists the schema ─
    var bad_op_rejected = False
    try:
        var _bad5 = apply_op(batch, '{"op":"sort","by":"revenue"}', False)
    except e:
        bad_op_rejected = String(e).find("revenue") >= 0 and String(e).find(
            "amount"
        ) >= 0
    if bad_op_rejected:
        passed += 1
        print("  ✅ a bad sort column errors, naming it and the available columns")
    else:
        failed += 1
        print("  ❌ bad op column not rejected helpfully")

    # ── an unknown op names the accepted set ─────────────────────────────────
    var unknown_op_rejected = False
    try:
        var _bad6 = apply_op(batch, '{"op":"pivot"}', False)
    except e:
        unknown_op_rejected = String(e).find("pivot") >= 0 and String(e).find(
            "aggregate"
        ) >= 0
    if unknown_op_rejected:
        passed += 1
        print("  ✅ an unknown op errors, naming it and the accepted ops")
    else:
        failed += 1
        print("  ❌ unknown op not rejected helpfully")

    # ── end to end: filter then aggregate then sort, one call ────────────────
    var request = (
        '{"type":"query_execute","columns":["region","amount"],"rows":'
        + ROWS
        + ',"ops":['
        + '{"op":"filter","predicate":' + predicate + "},"
        + '{"op":"aggregate","by":"region","value":"amount","agg":"sum"},'
        + '{"op":"sort","by":"sum_amount","desc":true}'
        + "]}"
    )
    var response = run_query_execute(request, ROWS)
    if (
        response.find('"error"') < 0
        and response.find('"ops":3') >= 0
        and response.find('"rows":2') >= 0
        and response.find('"plan_hash":"') >= 0
    ):
        passed += 1
        print("  ✅ filter -> aggregate -> sort runs in one call and reports 3 ops")
    else:
        failed += 1
        print("  ❌ end-to-end failed:", _head(response, 200))

    # ── the response carries the output column names ─────────────────────────
    if response.find('"region"') >= 0 and response.find('"sum_amount"') >= 0:
        passed += 1
        print("  ✅ the response names its output columns")
    else:
        failed += 1
        print("  ❌ output column names missing")

    # ── lineage reports a shape per op ───────────────────────────────────────
    if (
        response.find('"op":"filter"') >= 0
        and response.find('"op":"aggregate"') >= 0
        and response.find("rows x") >= 0
    ):
        passed += 1
        print("  ✅ lineage names each op and its output shape")
    else:
        failed += 1
        print("  ❌ lineage wrong")

    # ── a failing op reports its index, not a partial result ─────────────────
    var failing = (
        '{"columns":["region","amount"],"ops":['
        '{"op":"sort","by":"amount"},'
        '{"op":"sort","by":"revenue"}'
        "]}"
    )
    var failure = run_query_execute(failing, ROWS)
    if (
        failure.find('"error_code":"query_op_failed"') >= 0
        and failure.find('"op_index":1') >= 0
        and failure.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ a failing op returns an error naming index 1, and NO result")
    else:
        failed += 1
        print("  ❌ partial-result leak or bad error:", _head(failure, 200))

    # ── plan_hash is over VALUES: whitespace and key order do not matter ─────
    var ops_a = '[{"op":"top_k","by":"amount","k":10}]'
    var ops_b = '[ {"op":"top_k" ,  "by":"amount",  "k":10 } ]'
    var ops_reordered = '[{"k":10,"by":"amount","op":"top_k"}]'
    var ops_changed = '[{"op":"top_k","by":"amount","k":11}]'
    var hash_a = plan_hash(ops_a)
    if len(hash_a) == 64 and hash_a == plan_hash(ops_b):
        passed += 1
        print("  ✅ whitespace does not change plan_hash")
    else:
        failed += 1
        print("  ❌ plan_hash sensitive to whitespace")

    if hash_a == plan_hash(ops_reordered):
        passed += 1
        print("  ✅ key order does not change plan_hash")
    else:
        failed += 1
        print("  ❌ plan_hash sensitive to key order")

    if hash_a != plan_hash(ops_changed):
        passed += 1
        print("  ✅ changing k from 10 to 11 DOES change plan_hash")
    else:
        failed += 1
        print("  ❌ plan_hash blind to a threshold change — it identifies nothing")

    # ── the same plan hashes identically across runs ─────────────────────────
    if plan_hash(ops_a) == hash_a and run_query_execute(request, ROWS).find(
        '"plan_hash":"' + plan_hash(
            '[{"op":"filter","predicate":' + predicate + "},"
            '{"op":"aggregate","by":"region","value":"amount","agg":"sum"},'
            '{"op":"sort","by":"sum_amount","desc":true}]'
        ) + '"'
    ) >= 0:
        passed += 1
        print("  ✅ the plan hash in a response matches plan_hash over the same ops")
    else:
        failed += 1
        print("  ❌ response plan_hash does not match plan_hash()")

    # ── an empty ops list is a valid pass-through ───────────────────────────
    var passthrough = run_query_execute(
        '{"columns":["region","amount"],"ops":[]}', ROWS
    )
    if passthrough.find('"ops":0') >= 0 and passthrough.find('"rows":4') >= 0:
        passed += 1
        print("  ✅ an empty plan returns the input unchanged: 4 rows, 0 ops")
    else:
        failed += 1
        print("  ❌ empty plan wrong")

    # ── a bad header returns a typed error, not a crash ─────────────────────
    var header_error = run_query_execute('{"ops":[]}', ROWS)
    if header_error.find('"error_code":"invalid_arguments"') >= 0:
        passed += 1
        print("  ✅ a missing header returns invalid_arguments")
    else:
        failed += 1
        print("  ❌ missing header not reported:", _head(header_error, 120))

    # ── nulls round-trip out as `null`, not 0.0 ──────────────────────────────
    if passthrough.find("null") >= 0:
        passed += 1
        print("  ✅ an absent cell comes back as null, preserving the distinction")
    else:
        failed += 1
        print("  ❌ null lost on output")

    # ── parse_rows on an empty array is an empty batch, not an error ─────────
    var empty = parse_rows("[]", 2)
    if empty.n_rows == 0 and empty.width() == 2:
        passed += 1
        print("  ✅ zero rows still yields a 2-column batch")
    else:
        failed += 1
        print("  ❌ empty rows wrong")

    # ── a non-ASCII column name survives, and its ops still resolve ───────────
    # The bug this replaces: Python's json.dumps escapes non-ASCII by default, so
    # `región` arrived as `regi\u00f3n`. The header path kept the backslash and the op
    # path (frozen json_get_string) ate it, giving `regi\u00f3n` vs `regiu00f3n` — so
    # every op referencing any non-ASCII column failed with "which the batch does not
    # have", naming a column that WAS there.
    var accented_header = '{"columns":["regi\\u00f3n","importe"]}'
    var accented = build_batch(accented_header, "[[1,10.0],[2,20.0]]")
    if accented.schema.name_at(0) == "región":
        passed += 1
        print("  ✅ a \\uXXXX-escaped column name decodes to región")
    else:
        failed += 1
        print("  ❌ escaped name not decoded:", accented.schema.name_at(0))

    if accented.column_index("región") == 0:
        passed += 1
        print("  ✅ and it is addressable under the name the caller meant")
    else:
        failed += 1
        print("  ❌ región does not resolve")

    # ── the op path agrees with the header path ───────────────────────────────
    # This is the actual regression: both must decode identically or lookups fail.
    if json_string_field('{"by":"regi\\u00f3n"}', "by") == accented.schema.name_at(0):
        passed += 1
        print("  ✅ the op reader and the header reader agree on the decoded name")
    else:
        failed += 1
        print(
            "  ❌ op/header disagree:",
            json_string_field('{"by":"regi\\u00f3n"}', "by"),
        )

    # ── end to end: aggregate BY a non-ASCII column ───────────────────────────
    var accented_request = (
        '{"columns":["regi\\u00f3n","importe"],"rows":[[1,10.0],[2,20.0],[1,30.0]],'
        '"ops":[{"op":"aggregate","by":"regi\\u00f3n","value":"importe","agg":"sum"}]}'
    )
    var accented_response = run_query_execute(
        accented_request, "[[1,10.0],[2,20.0],[1,30.0]]"
    )
    if accented_response.find('"error"') < 0 and accented_response.find('"rows":2') >= 0:
        passed += 1
        print("  ✅ group_by on a non-ASCII column runs and yields 2 groups")
    else:
        failed += 1
        print("  ❌ non-ASCII group_by failed:", _head(accented_response, 220))

    # ── the name comes BACK correct, not re-corrupted on output ────────────────
    # Emitting each byte through chr(Int(c)) re-encodes bytes >= 0x80, so the caller
    # would receive a different name than it sent.
    if accented_response.find("regi\u00c3\u00b3n") < 0:
        passed += 1
        print("  ✅ the response does not contain a double-encoded name")
    else:
        failed += 1
        print("  ❌ the output name was re-encoded")

    # ── substring is byte-exact ───────────────────────────────────────────────
    var cafe = String("café")
    if substring(cafe, 0, 5) == cafe and len(substring(cafe, 0, 5).as_bytes()) == 5:
        passed += 1
        print("  ✅ substring round-trips café byte for byte (5 bytes, not 7)")
    else:
        failed += 1
        print("  ❌ substring corrupted café")

    # ── substring still clamps rather than crashing ──────────────────────────
    if (
        substring(cafe, 0, 999) == cafe
        and substring(cafe, 99, 200) == ""
        and substring(cafe, 3, 1) == ""
    ):
        passed += 1
        print("  ✅ substring clamps out-of-range bounds to an empty result")
    else:
        failed += 1
        print("  ❌ substring clamping wrong")

    # ── json_unescape handles the standard escapes ────────────────────────────
    if (
        json_unescape('a\\"b') == 'a"b'
        and json_unescape("a\\\\b") == "a\\b"
        and json_unescape("a\\nb") == "a\nb"
        and json_unescape("a\\tb") == "a\tb"
        and json_unescape("plain") == "plain"
    ):
        passed += 1
        print("  ✅ json_unescape decodes quote, backslash, newline and tab")
    else:
        failed += 1
        print("  ❌ json_unescape basic escapes wrong")

    # ── a surrogate pair becomes one astral character ─────────────────────────
    # An emoji in a column name is unusual but a Japanese or Chinese name is not, and
    # both go through this path. Decoding the halves separately yields mojibake.
    var astral = json_unescape("\\ud83d\\ude00")
    if len(astral.as_bytes()) == 4:
        passed += 1
        print("  ✅ a \\uD83D\\uDE00 surrogate pair decodes to one 4-byte character")
    else:
        failed += 1
        print("  ❌ surrogate pair wrong, bytes =", len(astral.as_bytes()))

    # ── a malformed escape keeps its text rather than inventing a value ───────
    if (
        json_unescape("\\uZZZZ") == "\\uZZZZ"
        and json_unescape("\\u00") == "\\u00"
        and json_unescape("trailing\\") == "trailing\\"
    ):
        passed += 1
        print("  ✅ a malformed escape is preserved, not guessed at")
    else:
        failed += 1
        print("  ❌ malformed escape mishandled:", json_unescape("\\uZZZZ"))

    # ── json_string_field finds a value past an escaped quote ─────────────────
    # A naive scan for the closing quote stops at the \" and truncates the name.
    if json_string_field('{"by":"a\\"b","other":"x"}', "by") == 'a"b':
        passed += 1
        print("  ✅ json_string_field does not stop at an escaped quote")
    else:
        failed += 1
        print(
            "  ❌ escaped quote truncated:",
            json_string_field('{"by":"a\\"b","other":"x"}', "by"),
        )

    # ── an absent or non-string field is "" rather than a guess ───────────────
    if (
        json_string_field('{"by":"x"}', "nope") == ""
        and json_string_field('{"by":42}', "by") == ""
    ):
        passed += 1
        print("  ✅ an absent or non-string field reads as empty")
    else:
        failed += 1
        print("  ❌ json_string_field wrong on absent/non-string")

    # ══ join ══════════════════════════════════════════════════════════════════
    var orders = build_batch(ORDERS_HEADER, ORDERS_ROWS)
    var customers = parse_named_tables(CUSTOMERS, _empty_strings(), _empty_strings())
    var detail = String("")

    # ── the tables array resolves once, positionally ──────────────────────────
    var handles = table_dataset_handles(
        '{"tables":[{"name":"customers","columns":["id"],"rows":[[1]]},'
        '{"name":"regions","columns":["id"],"dataset":"@ds_2"}]}'
    )
    var names_of_tables = table_names(
        '{"tables":[{"name":"customers","columns":["id"],"rows":[[1]]},'
        '{"name":"regions","columns":["id"],"dataset":"@ds_2"}]}'
    )
    if (
        len(handles) == 2
        and handles[0] == ""
        and handles[1] == "ds_2"
        and len(names_of_tables) == 2
        and names_of_tables[1] == "regions"
    ):
        passed += 1
        print("  ✅ table handles and names come back positionally, '@' stripped")
    else:
        failed += 1
        print("  ❌ table handle walk wrong:", len(handles))

    if (
        customers.count() == 1
        and customers.index_of("customers") == 0
        and customers.index_of("orders") < 0
        and customers.describe() == "customers"
        and _no_tables().describe() == "none"
    ):
        passed += 1
        print("  ✅ one named table registered, addressable by name")
    else:
        failed += 1
        print("  ❌ NamedBatches wrong:", customers.count())

    # ── inner join: known values, and the null-key row is GONE ────────────────
    var inner = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id"}',
        False,
        customers,
        detail,
    )
    if (
        inner.n_rows == 2
        and inner.width() == 5
        and inner.schema.name_at(3) == "customers.id"
        and inner.schema.name_at(4) == "customers.tier"
        and inner.column(0).get(0) == 1.0     # order 1
        and inner.column(0).get(1) == 3.0     # order 3
        and inner.column(4).get(0) == 1.0     # tier 1 for customer 7
        and inner.column(4).get(1) == 1.0
    ):
        passed += 1
        print("  ✅ inner join on customer_id yields orders 1 and 3 with tier 1")
    else:
        failed += 1
        print("  ❌ inner join wrong:", inner.n_rows, inner.width())

    if detail.find("2 joined rows") >= 0:
        passed += 1
        print("  ✅ the join reports its row count as lineage detail")
    else:
        failed += 1
        print("  ❌ join detail wrong:", detail)

    # ── left join: the unmatched row AND the null-key row survive, as nulls ───
    # A null key matches nothing, not even another null — the opposite of DISTINCT.
    detail = String("")
    var left_joined = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"how":"left"}',
        False,
        customers,
        detail,
    )
    if (
        left_joined.n_rows == 4
        and left_joined.column(4).is_valid_at(0)          # order 1 matched
        and not left_joined.column(4).is_valid_at(1)      # order 2, no partner
        and not left_joined.column(4).is_valid_at(3)      # order 4, null key
        and left_joined.column(2).get(3) == 40.0          # its own columns are intact
    ):
        passed += 1
        print("  ✅ left join keeps all 4 rows; unmatched and null-key rows are null")
    else:
        failed += 1
        print("  ❌ left join wrong:", left_joined.n_rows)

    if detail.find("2 left rows unmatched") >= 0 and detail.find(
        "1 left rows had a null key"
    ) >= 0:
        passed += 1
        print("  ✅ the detail distinguishes unmatched from null-key rows")
    else:
        failed += 1
        print("  ❌ left-join detail wrong:", detail)

    # ── duplicate keys MULTIPLY, and join_output_rows agrees exactly ──────────
    var customers_dup = parse_named_tables(
        CUSTOMERS_DUP, _empty_strings(), _empty_strings()
    )
    detail = String("")
    var fanned = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id"}',
        False,
        customers_dup,
        detail,
    )
    var counted = join_output_rows(orders, 1, customers_dup.batches[0], 0, 0)
    if fanned.n_rows == 4 and counted == 4:
        passed += 1
        print("  ✅ 2 left rows x 2 right rows = 4, and the pre-flight count agrees")
    else:
        failed += 1
        print("  ❌ fan-out wrong:", fanned.n_rows, counted)

    # A LEFT join counts one row for each unmatched and each null-key left row.
    if join_output_rows(orders, 1, customers_dup.batches[0], 0, 1) == 6:
        passed += 1
        print("  ✅ the count includes a LEFT join's unmatched rows (4 + 2)")
    else:
        failed += 1
        print("  ❌ left-join count wrong:", join_output_rows(
            orders, 1, customers_dup.batches[0], 0, 1
        ))

    # ── semi and anti never multiply, and emit LEFT columns only ─────────────
    detail = String("")
    var semi = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"how":"semi"}',
        False,
        customers_dup,
        detail,
    )
    if semi.n_rows == 2 and semi.width() == 3 and detail.find(
        "2 of 4 left rows matched"
    ) >= 0 and detail.find("1 left rows had a null key") >= 0:
        passed += 1
        print("  ✅ semi keeps 2 rows once each, 3 columns, and says so")
    else:
        failed += 1
        print("  ❌ semi wrong:", semi.n_rows, semi.width(), detail)

    detail = String("")
    var anti = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"how":"anti"}',
        False,
        customers,
        detail,
    )
    # Order 2 has a known key with no partner. Order 4's key is NULL, which satisfies
    # neither EXISTS nor NOT EXISTS, so it is in neither result — and the detail SAYS so.
    # The old text was "1 of 4 left rows unmatched", which is a false statement twice over:
    # the number printed is the number of rows KEPT, and the row excluded for a null key was
    # not counted anywhere at all.
    if anti.n_rows == 1 and anti.column(0).get(0) == 2.0 and detail.find(
        "1 of 4 left rows kept (unmatched, non-null key)"
    ) >= 0 and detail.find("1 left rows had a null key") >= 0:
        passed += 1
        print("  ✅ anti keeps only order 2; the null-key row is in neither result")
    else:
        failed += 1
        print("  ❌ anti wrong:", anti.n_rows, detail)

    # ── merge join over inputs that ARRIVED sorted ────────────────────────────
    var sorted_orders = build_batch(
        ORDERS_HEADER, "[[1,7,10.0],[3,7,30.0],[2,8,20.0],[4,null,40.0]]"
    )
    detail = String("")
    var merged = apply_op_detailed(
        sorted_orders,
        '{"op":"join","table":"customers","on":"id","how":"inner","method":"merge",'
        '"left_on":"customer_id","right_on":"id"}',
        False,
        customers,
        detail,
    )
    if merged.n_rows == 2 and merged.column(0).get(0) == 1.0:
        passed += 1
        print("  ✅ method merge joins two ascending inputs to the same 2 rows")
    else:
        failed += 1
        print("  ❌ merge join wrong:", merged.n_rows)

    # ── merge on an UNSORTED left input is refused, not silently partial ─────
    var unsorted_rejected = False
    try:
        var _m = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"id","method":"merge"}',
            False,
            customers,
            detail,
        )
    except e:
        unsorted_rejected = String(e).find("sorted ascending") >= 0 and String(e).find(
            "add a sort op"
        ) >= 0
    if unsorted_rejected:
        passed += 1
        print("  ✅ merge on an unsorted left input errors and says to sort first")
    else:
        failed += 1
        print("  ❌ unsorted merge accepted")

    # ── the shorthand `on` needs both sides to share the name ────────────────
    var accented_left = build_batch(
        '{"columns":["regi\\u00f3n","importe"]}', "[[7,10.0],[8,20.0]]"
    )
    var shorthand = apply_op_detailed(
        accented_left,
        '{"op":"join","table":"t","on":"regi\\u00f3n"}',
        False,
        parse_named_tables(
            '{"tables":[{"name":"t","columns":["regi\\u00f3n","valor"],'
            '"rows":[[7,1]]}]}',
            _empty_strings(),
            _empty_strings(),
        ),
        detail,
    )
    if shorthand.n_rows == 1 and shorthand.schema.name_at(2) == "t.región":
        passed += 1
        print("  ✅ 'on' shorthand resolves the same non-ASCII name on both sides")
    else:
        failed += 1
        print("  ❌ 'on' shorthand wrong:", shorthand.n_rows, shorthand.schema.name_at(2))

    # ── a RAW (unescaped) UTF-8 table, key, prefix and column all survive ────
    # json_get_array rebuilds its substring with chr(Int(byte)), which re-encodes every
    # byte >= 0x80, so `región` became `regiÃ³n` on any ARRAY-valued read. The new
    # json_raw_field / json_raw_tokens path is byte-exact, which is what makes a client
    # sending ensure_ascii=False work at all.
    var raw_utf8 = parse_named_tables(
        '{"tables":[{"name":"café_total","columns":["región","valor"],'
        '"rows":[[7,1],[9,3]]}]}',
        _empty_strings(),
        _empty_strings(),
    )
    var utf8_joined = apply_op_detailed(
        accented_left,
        '{"op":"join","table":"café_total","on":"región","prefix":"売上."}',
        False,
        raw_utf8,
        detail,
    )
    if (
        raw_utf8.index_of("café_total") == 0
        and utf8_joined.n_rows == 1
        and utf8_joined.schema.name_at(2) == "売上.región"
        and utf8_joined.schema.name_at(3) == "売上.valor"
    ):
        passed += 1
        print("  ✅ raw UTF-8 table name, join key and 売上. prefix all byte-identical")
    else:
        failed += 1
        print(
            "  ❌ raw UTF-8 join wrong:",
            raw_utf8.count(),
            utf8_joined.schema.name_at(2),
        )

    # ── a key column missing on ONE side names it and lists what IS there ────
    var missing_right_key = False
    try:
        var _j = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"nope"}',
            False,
            customers,
            detail,
        )
    except e:
        missing_right_key = String(e).find("nope") >= 0 and String(e).find("tier") >= 0
    var missing_left_key = False
    try:
        var _j2 = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"nope","right_on":"id"}',
            False,
            customers,
            detail,
        )
    except e:
        missing_left_key = String(e).find("nope") >= 0 and String(e).find(
            "customer_id"
        ) >= 0
    if missing_right_key and missing_left_key:
        passed += 1
        print("  ✅ a missing key column on either side names it and the schema")
    else:
        failed += 1
        print("  ❌ missing join key not reported by name")

    # ── an unknown table names what the plan DOES supply ────────────────────
    var unknown_table = False
    try:
        var _j3 = apply_op_detailed(
            orders, '{"op":"join","table":"orders","on":"id"}', False, customers, detail
        )
    except e:
        unknown_table = String(e).find("orders") >= 0 and String(e).find(
            "available: customers"
        ) >= 0
    if unknown_table:
        passed += 1
        print("  ✅ an unknown table errors, listing the available tables")
    else:
        failed += 1
        print("  ❌ unknown table not reported helpfully")

    # ── the required keys ───────────────────────────────────────────────────
    var no_table = False
    try:
        var _j4 = apply_op_detailed(orders, '{"op":"join"}', False, customers, detail)
    except e:
        no_table = String(e).find("join requires 'table'") >= 0
    var no_key = False
    try:
        var _j5 = apply_op_detailed(
            orders, '{"op":"join","table":"customers"}', False, customers, detail
        )
    except e:
        no_key = String(e).find("requires 'on'") >= 0
    var composite = False
    try:
        var _j5b = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":["customer_id","order_id"],'
            '"right_on":"id"}',
            False,
            customers,
            detail,
        )
    except e:
        composite = String(e).find("composite multi-column equality key") >= 0
    if no_table and no_key and composite:
        passed += 1
        print("  ✅ join without 'table', without a key, or with a composite key errors")
    else:
        failed += 1
        print("  ❌ join required-key errors wrong")

    # ── right/outer/full/cross are rejected BY NAME, never mapped onto left ──
    var bad_how = False
    try:
        var _j6 = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"id","how":"right"}',
            False,
            customers,
            detail,
        )
    except e:
        bad_how = String(e).find("right") >= 0 and String(e).find(
            "not implemented"
        ) >= 0
    var bad_method = False
    try:
        var _j7 = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"id","method":"sortmerge"}',
            False,
            customers,
            detail,
        )
    except e:
        bad_method = String(e).find("sortmerge") >= 0 and String(e).find(
            "hash or merge"
        ) >= 0
    var semi_merge = False
    try:
        var _j8 = apply_op_detailed(
            orders,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"id","how":"semi","method":"merge"}',
            False,
            customers,
            detail,
        )
    except e:
        semi_merge = String(e).find("not defined for how 'semi'") >= 0
    if bad_how and bad_method and semi_merge:
        passed += 1
        print("  ✅ how 'right', method 'sortmerge' and semi+merge are each refused")
    else:
        failed += 1
        print("  ❌ how/method validation wrong")

    # ── two joins over one table with the SAME prefix collide, loudly ────────
    # Schema.index_of returns the FIRST match, so a silent collision would resolve every
    # later reference to the wrong column.
    var once = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id"}',
        False,
        customers,
        detail,
    )
    var collided = False
    try:
        var _j9 = apply_op_detailed(
            once,
            '{"op":"join","table":"customers","left_on":"customer_id",'
            '"right_on":"id"}',
            False,
            customers,
            detail,
        )
    except e:
        collided = String(e).find("customers.id") >= 0 and String(e).find(
            "distinct 'prefix'"
        ) >= 0
    var twice_ok = apply_op_detailed(
        once,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"prefix":"seller."}',
        False,
        customers,
        detail,
    )
    if collided and twice_ok.schema.name_at(5) == "seller.id":
        passed += 1
        print("  ✅ a repeated default prefix collides; two prefixes are fine")
    else:
        failed += 1
        print("  ❌ prefix collision handling wrong")

    # ── the OUTPUT-ROW cap fires BEFORE the join allocates ──────────────────
    # 1200 x 1200 rows sharing one key is a small request asking for 1.44e6 output rows,
    # and hash_join_indices allocates two Ints per OUTPUT row — so checking the result
    # afterwards would be checking something that already crashed the worker.
    var big_left = build_batch(ORDERS_HEADER, _same_key_left(1200))
    var big_table = parse_named_tables(
        _same_key_table(1200), _empty_strings(), _empty_strings()
    )
    var row_cap_fired = False
    try:
        var _j10 = apply_op_detailed(
            big_left,
            '{"op":"join","table":"big","left_on":"customer_id","right_on":"id"}',
            False,
            big_table,
            detail,
        )
    except e:
        row_cap_fired = String(e).find("1440000 rows") >= 0 and String(e).find(
            "at most 1000000"
        ) >= 0
    if row_cap_fired:
        passed += 1
        print("  ✅ a 1.44e6-row join is refused before it allocates, with the count")
    else:
        failed += 1
        print("  ❌ join output-row cap did not fire")

    # ── the CELL cap fires on a join that is wide rather than tall ──────────
    var wide_left = build_batch(_wide_header("l", 17), _wide_rows(1000, 17, 1.0))
    var wide_table = parse_named_tables(
        '{"tables":[{"name":"wide","columns":["w0","w1","w2","w3","w4","w5","w6","w7",'
        '"w8","w9","w10","w11","w12","w13","w14","w15","w16"],"rows":'
        + _wide_rows(1000, 17, 1.0)
        + "}]}",
        _empty_strings(),
        _empty_strings(),
    )
    var cell_cap_fired = False
    try:
        var _j11 = apply_op_detailed(
            wide_left,
            '{"op":"join","table":"wide","left_on":"l0","right_on":"w0"}',
            False,
            wide_table,
            detail,
        )
    except e:
        cell_cap_fired = String(e).find("34000000 cells") >= 0 and String(e).find(
            "at most 32000000"
        ) >= 0
    if cell_cap_fired:
        passed += 1
        print("  ✅ 1e6 rows x 34 columns exceeds the cell budget and is refused")
    else:
        failed += 1
        print("  ❌ join cell cap did not fire")

    # ── a LEFT join against an EMPTY table still emits every left row ────────
    # The product of the row counts is zero here, which is why it cannot be the output
    # bound for a LEFT join: the widest case is every left row plus a null column per
    # right column.
    detail = String("")
    var empty_table = parse_named_tables(
        '{"tables":[{"name":"customers","columns":["id","tier"],"rows":[]}]}',
        _empty_strings(),
        _empty_strings(),
    )
    var against_empty = apply_op_detailed(
        orders,
        '{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"how":"left"}',
        False,
        empty_table,
        detail,
    )
    if (
        against_empty.n_rows == 4
        and against_empty.width() == 5
        and not against_empty.column(3).is_valid_at(0)
        and not against_empty.column(4).is_valid_at(3)
        and against_empty.column(2).get(0) == 10.0
    ):
        passed += 1
        print("  ✅ a left join against an empty table keeps all 4 rows, right all null")
    else:
        failed += 1
        print("  ❌ left join against empty table wrong:", against_empty.n_rows)

    # ── SORTED KEYS: a nested decoy must not be read as the op's own keys ────
    # The frame layer re-serialises with keys SORTED, so "decoy" arrives before "how",
    # "left_on", "on", "prefix", "right_on" and "table". A naive raw.find would read the
    # nested values and join the wrong thing.
    var decoy_join = apply_op_detailed(
        orders,
        '{"decoy":{"how":"cross","left_on":"nope","method":"sortmerge","on":"nope",'
        '"prefix":"WRONG.","right_on":"nope","table":"nope"},"how":"inner",'
        '"left_on":"customer_id","op":"join","right_on":"id","table":"customers"}',
        False,
        customers,
        detail,
    )
    if decoy_join.n_rows == 2 and decoy_join.schema.name_at(3) == "customers.id":
        passed += 1
        print("  ✅ a join reads its own keys past a nested decoy object")
    else:
        failed += 1
        print("  ❌ nested decoy read as the join's keys:", decoy_join.n_rows)

    # ── table-array validation, all before the first op runs ────────────────
    var too_many_tables = String('{"tables":[')
    for i in range(9):
        if i > 0:
            too_many_tables += ","
        too_many_tables += (
            '{"name":"t' + String(i) + '","columns":["id"],"rows":[[1]]}'
        )
    too_many_tables += "]}"
    var table_errors = 0
    try:
        var _t = parse_named_tables(
            too_many_tables, _empty_strings(), _empty_strings()
        )
    except e:
        if String(e).find("at most 8 named tables; got 9") >= 0:
            table_errors += 1
    try:
        var _t2 = parse_named_tables(
            '{"tables":[{"name":"a","columns":["id"],"rows":[[1]]},'
            '{"name":"a","columns":["id"],"rows":[[2]]}]}',
            _empty_strings(),
            _empty_strings(),
        )
    except e:
        if String(e).find("'a' is declared twice") >= 0:
            table_errors += 1
    try:
        var _t3 = parse_named_tables(
            '{"tables":[{"columns":["id"],"rows":[[1]]}]}',
            _empty_strings(),
            _empty_strings(),
        )
    except e:
        if String(e).find("table 0 has no 'name'") >= 0:
            table_errors += 1
    try:
        var _t4 = parse_named_tables(
            '{"tables":[{"name":"a","columns":["id"]}]}',
            _empty_strings(),
            _empty_strings(),
        )
    except e:
        if String(e).find("neither 'rows' nor 'dataset'") >= 0:
            table_errors += 1
    try:
        var _t5 = parse_named_tables(
            '{"tables":[{"name":"regions","columns":["id"],"dataset":"@ds_2"}]}',
            _empty_strings(),
            _empty_strings(),
        )
    except e:
        if String(e).find("has no session") >= 0 and String(e).find("ds_2") >= 0:
            table_errors += 1
    try:
        var _t6 = parse_named_tables(
            '{"tables":[{"name":"a","columns":["id"],"rows":[[1,2]]}]}',
            _empty_strings(),
            _empty_strings(),
        )
    except e:
        if String(e).find("table 'a': ") >= 0:
            table_errors += 1
    if table_errors == 6:
        passed += 1
        print("  ✅ table count, duplicate, missing name/body, handle-without-session"
              " and build errors all typed")
    else:
        failed += 1
        print("  ❌ table validation gaps:", table_errors, "of 6")

    # ── the table CELL budget is checked before anything is allocated ───────
    # 512 declared columns x 70,000 rows is 35.8e6 cells from a small payload: a header
    # plus empty rows, which parse_rows would happily pad. Rule 1c — validating a shape
    # and bounding an allocation are two different checks.
    var fat = String('{"tables":[{"name":"fat","columns":[')
    for c in range(512):
        if c > 0:
            fat += ","
        fat += '"c' + String(c) + '"'
    fat += '],"rows":['
    for r in range(70000):
        if r > 0:
            fat += ","
        fat += "[]"
    fat += "]}]}"
    var cells_capped = False
    try:
        var _t7 = parse_named_tables(fat, _empty_strings(), _empty_strings())
    except e:
        cells_capped = String(e).find("35840000 cells in total") >= 0 and String(
            e
        ).find("at most 32000000") >= 0
    if cells_capped:
        passed += 1
        print("  ✅ 512 x 70,000 cells across tables is refused before allocating")
    else:
        failed += 1
        print("  ❌ table cell budget did not fire")

    # ══ window ════════════════════════════════════════════════════════════════
    var wbatch = build_batch(WINDOW_HEADER, WINDOW_ROWS)

    # ── row_number, and ROW ORDER IS NOT CHANGED ─────────────────────────────
    detail = String("")
    var seq = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"row_number","partition_by":["region"],'
        '"order_by":["month"],"desc":[false],"nulls_last":true,"as":"seq"}',
        False,
        _no_tables(),
        detail,
    )
    if (
        seq.n_rows == 5
        and seq.width() == 4
        and seq.schema.name_at(3) == "seq"
        and seq.column(3).get(0) == 1.0
        and seq.column(3).get(1) == 2.0
        and seq.column(3).get(2) == 3.0
        and seq.column(3).get(3) == 4.0
        and seq.column(3).get(4) == 1.0    # region 2, its own partition
        and seq.column(1).get(0) == 1.0    # month column still in INPUT order
        and seq.column(1).get(4) == 1.0
        and seq.column(0).get(4) == 2.0
    ):
        passed += 1
        print("  ✅ row_number appends 1,2,3,4,1 and leaves row order untouched")
    else:
        failed += 1
        print("  ❌ row_number wrong:", seq.width(), seq.column(3).get(4))

    if detail == "2 partitions, largest 4 rows":
        passed += 1
        print("  ✅ the window reports its partitioning as lineage detail")
    else:
        failed += 1
        print("  ❌ window detail wrong:", detail)

    # ── rank vs dense_rank on the SAME tied data ─────────────────────────────
    # amounts 30,20,20,10 rank 1,2,2,4 and dense-rank 1,2,2,3. Swapping them is invisible
    # until two reports are compared.
    var ranked = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"rank","partition_by":["region"],"order_by":["amount"],'
        '"desc":[true],"as":"rank_desc"}',
        False,
        _no_tables(),
        detail,
    )
    var dense = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"dense_rank","partition_by":["region"],'
        '"order_by":["amount"],"desc":[true],"as":"dense_rank_desc"}',
        False,
        _no_tables(),
        detail,
    )
    if (
        ranked.column(3).get(3) == 1.0     # amount 30
        and ranked.column(3).get(1) == 2.0  # amount 20, tied
        and ranked.column(3).get(2) == 2.0
        and ranked.column(3).get(0) == 4.0  # amount 10 — the GAP
        and dense.column(3).get(0) == 3.0   # no gap
        and dense.column(3).get(1) == 2.0
        and ranked.column(3).get(4) == 1.0  # single-row partition
    ):
        passed += 1
        print("  ✅ rank gaps to 4 after the tie where dense_rank gives 3")
    else:
        failed += 1
        print(
            "  ❌ rank/dense_rank wrong:",
            ranked.column(3).get(0),
            dense.column(3).get(0),
        )

    # ── lag and lead STOP at the partition edge ───────────────────────────────
    var lagged = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"lag","partition_by":["region"],"order_by":["month"],'
        '"value":"amount","offset":1,"as":"prev_amount"}',
        False,
        _no_tables(),
        detail,
    )
    var led = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"lead","partition_by":["region"],"order_by":["month"],'
        '"value":"amount","as":"next_amount"}',
        False,
        _no_tables(),
        detail,
    )
    if (
        not lagged.column(3).is_valid_at(0)      # first row of partition 1
        and lagged.column(3).get(1) == 10.0
        and lagged.column(3).get(3) == 20.0
        and not lagged.column(3).is_valid_at(4)  # partition 2's only row
        and led.column(3).get(0) == 20.0
        and not led.column(3).is_valid_at(3)     # last row of partition 1
        and not led.column(3).is_valid_at(4)
    ):
        passed += 1
        print("  ✅ lag/lead are NULL at a partition boundary, never the neighbour's row")
    else:
        failed += 1
        print("  ❌ lag/lead wrong:", lagged.column(3).get(1), led.column(3).get(0))

    # ── cumulative, framed and partition_total against hand-computed values ──
    var running = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"cumulative","partition_by":["region"],'
        '"order_by":["month"],"value":"amount","agg":"sum","as":"running_total"}',
        False,
        _no_tables(),
        detail,
    )
    var rolling = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"framed","partition_by":["region"],"order_by":["month"],'
        '"value":"amount","agg":"avg","preceding":1,"as":"avg_2mo"}',
        False,
        _no_tables(),
        detail,
    )
    var totals = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"partition_total","partition_by":["region"],'
        '"value":"amount","agg":"sum","as":"region_total"}',
        False,
        _no_tables(),
        detail,
    )
    if (
        running.column(3).get(0) == 10.0
        and running.column(3).get(1) == 30.0
        and running.column(3).get(2) == 50.0
        and running.column(3).get(3) == 80.0
        and running.column(3).get(4) == 50.0
        and rolling.column(3).get(0) == 10.0     # frame clamps to the partition start
        and rolling.column(3).get(1) == 15.0     # (10 + 20) / 2
        and rolling.column(3).get(3) == 25.0     # (20 + 30) / 2
        and totals.column(3).get(0) == 80.0
        and totals.column(3).get(3) == 80.0
        and totals.column(3).get(4) == 50.0
    ):
        passed += 1
        print("  ✅ cumulative, a 2-row frame and partition_total all hand-check out")
    else:
        failed += 1
        print(
            "  ❌ frame aggregates wrong:",
            running.column(3).get(3),
            rolling.column(3).get(1),
            totals.column(3).get(0),
        )

    # ── no partition_by is ONE partition over everything ─────────────────────
    detail = String("")
    var global_running = apply_op_detailed(
        wbatch,
        '{"op":"window","fn":"cumulative","order_by":["month"],"value":"amount",'
        '"agg":"sum","as":"running_total"}',
        False,
        _no_tables(),
        detail,
    )
    # Ordered by month with a STABLE sort: r0(1), r4(1), r1(2), r2(3), r3(4).
    if (
        detail == "1 partitions, largest 5 rows"
        and global_running.column(3).get(0) == 10.0
        and global_running.column(3).get(4) == 60.0
        and global_running.column(3).get(1) == 80.0
        and global_running.column(3).get(3) == 130.0
    ):
        passed += 1
        print("  ✅ no partition_by is one partition of 5 rows, running to 130")
    else:
        failed += 1
        print("  ❌ single-partition window wrong:", detail)

    # ── a NON-ASCII partition column ─────────────────────────────────────────
    var accented_window_batch = build_batch(
        '{"columns":["regi\\u00f3n","importe"]}',
        "[[1,10.0],[1,20.0],[2,50.0]]",
    )
    var accented_window = apply_op_detailed(
        accented_window_batch,
        '{"op":"window","fn":"rank","partition_by":["regi\\u00f3n"],'
        '"order_by":["importe"],"desc":[true],"as":"regi\\u00f3n_rank"}',
        False,
        _no_tables(),
        detail,
    )
    if (
        accented_window.schema.name_at(2) == "región_rank"
        and accented_window.column(2).get(1) == 1.0   # 20 outranks 10 in partition 1
        and accented_window.column(2).get(0) == 2.0
        and accented_window.column(2).get(2) == 1.0
    ):
        passed += 1
        print("  ✅ a window partitions by región and names its output región_rank")
    else:
        failed += 1
        print("  ❌ non-ASCII window wrong:", accented_window.schema.name_at(2))

    # ── SORTED KEYS: a window reads its own keys past a nested decoy ─────────
    var decoy_window = apply_op_detailed(
        wbatch,
        '{"as":"seq","decoy":{"agg":"var","as":"WRONG","desc":[true,true],'
        '"fn":"ntile","offset":0,"op":130,"order_by":["nope"],'
        '"partition_by":["nope"],"preceding":-1,"value":"nope"},"fn":"row_number",'
        '"nulls_last":true,"op":"window","order_by":["month"],'
        '"partition_by":["region"]}',
        False,
        _no_tables(),
        detail,
    )
    if (
        decoy_window.schema.name_at(3) == "seq"
        and decoy_window.column(3).get(3) == 4.0
        and decoy_window.column(3).get(4) == 1.0
    ):
        passed += 1
        print("  ✅ a window reads fn/as/order_by past a nested decoy object")
    else:
        failed += 1
        print("  ❌ nested decoy read as the window's keys")

    # ── the wire gates, each one a kernel answer that would otherwise be wrong ─
    var window_errors = 0
    # var/std/median: framed_aggregate leaves the mask False, so this would be a full
    # column of NULLS carrying a SUCCESS status.
    try:
        var _w = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"cumulative","order_by":["month"],"value":"amount",'
            '"agg":"var","as":"v"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("'var'") >= 0 and String(e).find("median") >= 0:
            window_errors += 1
    # A short `desc` silently leaves the trailing keys ascending.
    try:
        var _w2 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","order_by":["region","month"],'
            '"desc":[true],"as":"s"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("2 expected, 1 given") >= 0:
            window_errors += 1
    # `"desc":false` is not an array, and json_raw_array reads it as absent.
    try:
        var _w3 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","order_by":["month"],"desc":false,'
            '"as":"s"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("1 expected, 0 given") >= 0:
            window_errors += 1
    # `as` is required, and must not shadow an existing column.
    try:
        var _w4 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","order_by":["month"]}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("requires 'as'") >= 0:
            window_errors += 1
    try:
        var _w5 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","order_by":["month"],"as":"region"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("already exists") >= 0 and String(e).find("amount") >= 0:
            window_errors += 1
    # rank defines a tie by ONE column.
    try:
        var _w6 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"rank","order_by":["region","month"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("exactly one 'order_by' column; got 2") >= 0:
            window_errors += 1
    # A running total with no order is not a defined answer.
    try:
        var _w7 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"cumulative","value":"amount","agg":"sum","as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("non-empty 'order_by'") >= 0:
            window_errors += 1
    # value: required where it means something, rejected where it does not.
    try:
        var _w8 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"lag","order_by":["month"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("'lag' requires 'value'") >= 0:
            window_errors += 1
    try:
        var _w9 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","order_by":["month"],"value":"amount",'
            '"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("'row_number' takes no 'value'") >= 0:
            window_errors += 1
    # framed needs an explicit frame; -1 is not spellable on the wire.
    try:
        var _w10 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"framed","order_by":["month"],"value":"amount",'
            '"agg":"sum","as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("requires 'preceding' >= 0") >= 0:
            window_errors += 1
    try:
        var _w11 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"framed","order_by":["month"],"value":"amount",'
            '"agg":"sum","preceding":-1,"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("use fn 'cumulative'") >= 0:
            window_errors += 1
    # A lag with offset 0 or -1 is not a lag.
    try:
        var _w12 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"lag","order_by":["month"],"value":"amount",'
            '"offset":0,"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("requires 'offset' >= 1") >= 0:
            window_errors += 1
    # An unknown fn lists the accepted set.
    try:
        var _w13 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"ntile","order_by":["month"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("ntile") >= 0 and String(e).find("partition_total") >= 0:
            window_errors += 1
    try:
        var _w14 = apply_op_detailed(
            wbatch, '{"op":"window","as":"r"}', False, _no_tables(), detail
        )
    except e:
        if String(e).find("window requires 'fn'") >= 0:
            window_errors += 1
    # An unknown partition column is a typed error naming what IS available.
    try:
        var _w15 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","partition_by":["nope"],'
            '"order_by":["month"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("nope") >= 0 and String(e).find("region") >= 0:
            window_errors += 1
    # A non-array partition_by would silently become ONE partition over everything.
    try:
        var _w17 = apply_op_detailed(
            wbatch,
            '{"op":"window","fn":"row_number","partition_by":"region",'
            '"order_by":["month"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        if String(e).find("'partition_by' must be an array") >= 0:
            window_errors += 1
    if window_errors == 16:
        passed += 1
        print("  ✅ all 16 window wire gates reject with a message naming the reason")
    else:
        failed += 1
        print("  ❌ window gate coverage:", window_errors, "of 16")

    # ── the quadratic partition sort is refused, not left to hang ────────────
    var over_cap = build_batch(ORDERS_HEADER, _same_key_left(20001))
    var window_capped = False
    try:
        var _w16 = apply_op_detailed(
            over_cap,
            '{"op":"window","fn":"row_number","order_by":["amount"],"as":"r"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        window_capped = String(e).find("window over 20001 rows") >= 0 and String(
            e
        ).find("quadratic") >= 0
    if window_capped:
        passed += 1
        print("  ✅ a window over 20,001 rows is refused with the reason, not a hang")
    else:
        failed += 1
        print("  ❌ window row cap did not fire")

    # ── the unknown-op message lists the two new ops ─────────────────────────
    var lists_new_ops = False
    try:
        var _bad7 = apply_op(batch, '{"op":"pivot"}', False)
    except e:
        lists_new_ops = String(e).find("join") >= 0 and String(e).find("window") >= 0
    if lists_new_ops:
        passed += 1
        print("  ✅ the accepted-op list names join and window")
    else:
        failed += 1
        print("  ❌ accepted-op list not updated")

    # ══ end to end, through run_query_execute ═════════════════════════════════
    var join_request = (
        '{"type":"query_execute","columns":["order_id","customer_id","amount"],'
        '"rows":' + ORDERS_ROWS + ","
        '"tables":[{"name":"customers","columns":["id","tier"],'
        '"rows":[[7,1],[9,3]]}],'
        '"ops":[{"op":"join","table":"customers","left_on":"customer_id",'
        '"right_on":"id","how":"left"},'
        '{"op":"window","fn":"row_number","partition_by":["customers.tier"],'
        '"order_by":["amount"],"as":"seq"}]}'
    )
    var join_response = run_query_execute(join_request, ORDERS_ROWS)
    if (
        join_response.find('"error"') < 0
        and join_response.find('"rows":4') >= 0
        and join_response.find('"ops":2') >= 0
        and join_response.find('"op":"join"') >= 0
        and join_response.find('"op":"window"') >= 0
    ):
        passed += 1
        print("  ✅ join then window runs in one call and echoes both op names exactly")
    else:
        failed += 1
        print("  ❌ join/window end-to-end failed:", _head(join_response, 260))

    if (
        join_response.find('"detail":"4 joined rows') >= 0
        and join_response.find("partitions, largest") >= 0
    ):
        passed += 1
        print("  ✅ lineage carries the join and window detail strings")
    else:
        failed += 1
        print("  ❌ lineage detail missing:", _head(join_response, 300))

    # ── a table error before the op loop is invalid_arguments, with no result ─
    var table_failure = run_query_execute(
        '{"columns":["order_id","customer_id","amount"],'
        '"tables":[{"name":"customers","columns":["id"]}],'
        '"ops":[{"op":"join","table":"customers","on":"id"}]}',
        ORDERS_ROWS,
    )
    if (
        table_failure.find('"error_code":"invalid_arguments"') >= 0
        and table_failure.find("neither 'rows' nor 'dataset'") >= 0
        and table_failure.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ a bad table is invalid_arguments before any op runs, with no result")
    else:
        failed += 1
        print("  ❌ table error path wrong:", _head(table_failure, 200))

    # ── an op-level join failure keeps its op_index and leaks no result ──────
    var join_failure = run_query_execute(
        '{"columns":["order_id","customer_id","amount"],'
        '"ops":[{"op":"limit","offset":0,"count":4},'
        '{"op":"join","table":"customers","on":"customer_id"}]}',
        ORDERS_ROWS,
    )
    if (
        join_failure.find('"error_code":"query_op_failed"') >= 0
        and join_failure.find('"op_index":1') >= 0
        and join_failure.find("available: ") >= 0
        and join_failure.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ a join naming no supplied table fails at op 1 with no result")
    else:
        failed += 1
        print("  ❌ join op failure wrong:", _head(join_failure, 220))

    # ── plan_hash is over `ops` ONLY, so the table body is not in it ─────────
    # Two requests differing only in the table's ROWS hash identically; changing the
    # join's prefix does change the hash. That is the same contract the left side's rows
    # have today, and folding `tables` in would put data in the hash.
    var ops_join = (
        '[{"op":"join","table":"customers","left_on":"customer_id","right_on":"id"}]'
    )
    var ops_join_prefixed = (
        '[{"op":"join","table":"customers","left_on":"customer_id","right_on":"id",'
        '"prefix":"buyer."}]'
    )
    if plan_hash(ops_join) != plan_hash(ops_join_prefixed) and len(
        plan_hash(ops_join)
    ) == 64:
        passed += 1
        print("  ✅ a different join prefix is a different plan_hash")
    else:
        failed += 1
        print("  ❌ plan_hash blind to the join prefix")

    # ══ adversarial regressions, one per reproduced defect ═════════════════════
    # Every request below is the reproduction verbatim. Two of them killed the worker
    # outright and one hung it for 60 s; the rest returned a wrong answer, or a right answer
    # with a lineage line that misdescribed it, under a SUCCESS status.

    # ── 1. a JSON extension literal must not reach the frozen tokenizer ──────
    # `json_array_tokens` runs off the end of `[Infinity]` and aborts the PROCESS with an
    # uncatchable List bounds assert (json/parser.mojo:572, "index 10 is out of bounds"),
    # taking every resident dataset with it. This exact call did that.
    var infinity_table = run_query_execute(
        '{"columns":["k"],"tables":[{"columns":["id"],"name":"t","rows":[[Infinity]]}],'
        '"ops":[{"how":"left","left_on":"k","op":"join","right_on":"id","table":"t"}],'
        '"rows":[[1]]}',
        "[[1]]",
    )
    if (
        infinity_table.find('"error_code":"invalid_arguments"') >= 0
        and infinity_table.find("table 't'") >= 0
        and infinity_table.find("row 0, column 0") >= 0
        and infinity_table.find("Infinity") >= 0
        and infinity_table.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ Infinity in a SIDE TABLE is a typed error naming row and column")
    else:
        failed += 1
        print("  ❌ side-table Infinity:", _head(infinity_table, 260))

    # NaN did not abort — it mis-tokenised into three cells and was reported as a WIDTH
    # error, sending the caller to look at their header. It must name the real problem.
    var nan_table = run_query_execute(
        '{"columns":["k"],"tables":[{"columns":["id"],"name":"t","rows":[[NaN]]}],'
        '"ops":[{"how":"left","left_on":"k","op":"join","right_on":"id","table":"t"}],'
        '"rows":[[1]]}',
        "[[1]]",
    )
    if (
        nan_table.find('"error_code":"invalid_arguments"') >= 0
        and nan_table.find("row 0, column 0") >= 0
        and nan_table.find("NaN") >= 0
        and nan_table.find("values but the header declares") < 0
    ):
        passed += 1
        print("  ✅ NaN is named as NaN, not misreported as a header WIDTH error")
    else:
        failed += 1
        print("  ❌ NaN misreported:", _head(nan_table, 260))

    # The LEFT rows are the same path, and the sign is quoted back with the name.
    var neg_infinity_left = run_query_execute(
        '{"columns":["k","v"],"rows":[[1,-Infinity]],"ops":[]}', "[[1,-Infinity]]"
    )
    if (
        neg_infinity_left.find('"error_code":"invalid_arguments"') >= 0
        and neg_infinity_left.find("row 0, column 1 is '-Infinity'") >= 0
        and neg_infinity_left.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ -Infinity in the left rows names row 0, column 1, sign included")
    else:
        failed += 1
        print("  ❌ left -Infinity:", _head(neg_infinity_left, 260))

    # The ops array reaches the frozen tokenizer twice: `plan_hash` transcodes it, and
    # `project` parses each `roots` token through json_parse_float64_list.
    var infinity_ops = run_query_execute(
        '{"columns":["k"],"rows":[[1]],"ops":[{"expressions":{"nodes":[{"column":"k",'
        '"op":130}],"roots":[Infinity]},"names":["x"],"op":"project"}]}',
        "[[1]]",
    )
    if (
        infinity_ops.find('"error"') >= 0
        and infinity_ops.find("Infinity") >= 0
        and infinity_ops.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ Infinity inside `ops` is refused before plan_hash transcodes it")
    else:
        failed += 1
        print("  ❌ ops Infinity:", _head(infinity_ops, 260))

    # A direct apply_op caller is guarded too, and `1e308` is a NUMBER, not a name.
    var literal_gate = 0
    try:
        var _bad_op = apply_op(batch, '{"op":"limit","count":NaN}', False)
    except e:
        if String(e).find("not a JSON value") >= 0:
            literal_gate += 1
    if len(json_literal_problem("[[1e308,-2.5E-7,null,true,false]]", True)) == 0:
        literal_gate += 1
    if len(json_literal_problem('[["NaN","Infinity"]]', True)) == 0:
        literal_gate += 1  # inside a string it is DATA, not a literal
    if json_literal_problem("[[1],[2,NaN]]", True).find("row 1, column 1") >= 0:
        literal_gate += 1
    if literal_gate == 4:
        passed += 1
        print("  ✅ the literal scanner accepts exponents and quoted names, rejects bare")
    else:
        failed += 1
        print("  ❌ literal scanner:", literal_gate, "of 4")

    # ── 2. the RESPONSE must fit the transport frame ─────────────────────────
    # Every other bound bounds an ALLOCATION. 400 x 400 rows sharing one key over 50 + 50
    # columns is 160,000 rows x 100 columns: inside MAX_JOIN_OUTPUT_ROWS and inside
    # MAX_MATERIALIZED_CELLS, and still at least 64 MB of JSON — a frame the transport
    # cannot send (worker.py caps it at 64 MB), so the plan must be refused before the join
    # is materialised rather than answered with an undeliverable response.
    var fanout_left = build_batch(_wide_header("l", 50), _wide_rows(400, 50, 1.0))
    var fanout_tables = parse_named_tables(
        '{"tables":[{"name":"big","columns":'
        + _wide_header_array("r", 50)
        + ',"rows":'
        + _wide_rows(400, 50, 1.0)
        + "}]}",
        _empty_strings(),
        _empty_strings(),
    )
    detail = String("")
    var response_capped = False
    try:
        var _huge = apply_op_detailed(
            fanout_left,
            '{"op":"join","table":"big","left_on":"l0","right_on":"r0"}',
            False,
            fanout_tables,
            detail,
        )
    except e:
        response_capped = String(e).find("serialise to at least") >= 0 and String(
            e
        ).find("64 MB") >= 0
    if response_capped:
        passed += 1
        print("  ✅ a 160,000 x 100 join is refused for BYTES, inside every other bound")
    else:
        failed += 1
        print("  ❌ response-size pre-flight did not fire")

    # The arithmetic the bound rests on, asserted rather than trusted: 4 bytes per cell is
    # the floor ("0.0" plus a separator) and 25 the ceiling (24-byte widest Float64 text
    # plus a separator), so a result at MAX_MATERIALIZED_CELLS cannot be delivered at all.
    if (
        _serialized_bytes_floor(160_000, 100) > MAX_RESPONSE_BYTES
        and _serialized_bytes_floor(MAX_MATERIALIZED_CELLS // 100, 100)
        > MAX_RESPONSE_BYTES
        and _serialized_bytes_ceiling(4, 3) < MAX_RESPONSE_BYTES
        and _serialized_bytes_floor(160_000, 100) == 160_000 * 403
        and _serialized_bytes_ceiling(160_000, 100) == 160_000 * 2503
    ):
        passed += 1
        print("  ✅ the rows x cols -> bytes arithmetic holds, and 32e6 cells cannot fit")
    else:
        failed += 1
        print("  ❌ serialized-size arithmetic wrong")

    # The measuring pass and the emitter must not be able to disagree: the whole point of
    # measuring is that the response is then KNOWN to fit, so an off-by-one here would be a
    # bound that lies. Asserted as an identity on a batch holding a null, a long decimal and
    # a non-finite cell — the three shapes whose text lengths differ.
    var byte_probe = build_batch(
        '{"columns":["a","b"]}', "[[1,null],[0.3333333333333333,2]]"
    )
    var probe_non_finite = 0
    var probe_body = _batch_to_json(byte_probe, probe_non_finite)
    detail = String("")
    var overflowed = apply_op_detailed(
        build_batch('{"columns":["g","v"]}', "[[1,1e308],[1,1e308]]"),
        '{"op":"window","fn":"partition_total","partition_by":["g"],"value":"v",'
        '"agg":"sum","as":"tot"}',
        False,
        _no_tables(),
        detail,
    )
    var overflow_non_finite = 0
    var overflow_body = _batch_to_json(overflowed, overflow_non_finite)
    if (
        _serialized_bytes_exact(byte_probe) == len(probe_body)
        and probe_non_finite == 0
        and _serialized_bytes_exact(overflowed) == len(overflow_body)
        and overflow_non_finite == 2
        and overflow_body.find("inf") < 0
    ):
        passed += 1
        print("  ✅ the measuring pass returns exactly what the emitter writes")
    else:
        failed += 1
        print(
            "  ❌ measure/emit disagree:",
            _serialized_bytes_exact(byte_probe),
            len(probe_body),
            _serialized_bytes_exact(overflowed),
            len(overflow_body),
        )

    # ── 3. a non-finite value is ABSENT on the wire, never the token `inf` ───
    # Ordinary finite input: two rows of 1e308 summed by partition_total overflow to +inf,
    # and `String(inf)` is "inf", which no JSON parser accepts — so the SDK failed to decode
    # a response the engine called successful. `strict` cannot prevent it: strict governs
    # EXPRESSION evaluation and this is an aggregate.
    var overflow_request = (
        '{"columns":["g","v"],"rows":[[1,1e308],[1,1e308]],'
        '"ops":[{"op":"window","fn":"partition_total","partition_by":["g"],"value":"v",'
        '"agg":"sum","as":"tot"}]}'
    )
    var overflow = run_query_execute(overflow_request, "[[1,1e308],[1,1e308]]")
    if (
        overflow.find('"error"') < 0
        and overflow.find(":inf") < 0
        and overflow.find(":nan") < 0
        and overflow.find(",inf") < 0
        and overflow.find('"tot"') >= 0
        and overflow.find('"non_finite_cells":2') >= 0
        and overflow.find("null") >= 0
    ):
        passed += 1
        print("  ✅ an overflowed sum is null on the wire and counted, never bare `inf`")
    else:
        failed += 1
        print("  ❌ non-finite serialization:", _head(overflow, 300))

    # And a response with nothing non-finite says nothing about it, so every existing
    # response stays byte-identical.
    if run_query_execute(
        '{"columns":["g","v"],"rows":[[1,2.0]],"ops":[]}', "[[1,2.0]]"
    ).find("non_finite_cells") < 0:
        passed += 1
        print("  ✅ a clean response carries no non_finite_cells field")
    else:
        failed += 1
        print("  ❌ non_finite_cells leaked into a clean response")

    # ── 4. the window bound covers KEYS x ROWS, not rows alone ──────────────
    # 20,000 rows with `partition_by = ["a","b"] * 128` — a 497 KB payload, every value
    # inside every documented bound — hung 60.6 s until the worker was terminated, because
    # sort_indices_multi runs one O(n^2) pass PER KEY and only `n` was capped.
    var at_cap = build_batch(ORDERS_HEADER, _same_key_left(20_000))
    var many_keys = String('{"op":"window","fn":"row_number","partition_by":[')
    for i in range(128):
        if i > 0:
            many_keys += ","
        many_keys += '"customer_id","amount"'
    many_keys += '],"order_by":["amount"],"as":"seq"}'
    detail = String("")
    var work_capped = False
    try:
        var _hang = apply_op_detailed(at_cap, many_keys, False, _no_tables(), detail)
    except e:
        work_capped = String(e).find("key-row comparisons") >= 0 and String(e).find(
            "257 ordering keys"
        ) >= 0
    if work_capped:
        passed += 1
        print("  ✅ 20,000 rows x 256 partition keys is refused, not left to hang 60 s")
    else:
        failed += 1
        print("  ❌ window work bound did not fire")

    # Not a wall: the shape the 20,000-row cap was MEASURED on still answers.
    detail = String("")
    var still_answers = apply_op_detailed(
        at_cap,
        '{"op":"window","fn":"row_number","partition_by":["customer_id"],'
        '"order_by":["amount"],"as":"seq"}',
        False,
        _no_tables(),
        detail,
    )
    # And the worst operator is bounded too: `cumulative` re-walks the frame per row, so a
    # 20,000-row cumulative over four ordering keys is past the budget even though the row
    # count is not.
    var frame_capped = False
    try:
        var _cum = apply_op_detailed(
            at_cap,
            '{"op":"window","fn":"cumulative","partition_by":["customer_id",'
            '"customer_id","amount"],"order_by":["amount"],"value":"amount",'
            '"agg":"sum","as":"run"}',
            False,
            _no_tables(),
            detail,
        )
    except e:
        frame_capped = String(e).find("key-row comparisons") >= 0
    if (
        still_answers.n_rows == 20_000
        and still_answers.width() == 4
        and frame_capped
        and MAX_WINDOW_WORK == 2 * 20_000 * 20_000 * 2
    ):
        passed += 1
        print("  ✅ 20,000 rows x 2 keys still answers; cumulative x 4 keys does not")
    else:
        failed += 1
        print("  ❌ window work bound is a wall or miscalibrated")

    # ── 5. anti must report the rows it silently discarded ───────────────────
    # 500 left rows, 480 with a null join key, against a table holding the one matching id:
    # `how = "anti"` answered {"rows":[]} with the lineage line "0 of 500 left rows
    # unmatched" — an EMPTY answer under a SUCCESS status whose lineage reads as "all 500
    # matched", for a dataset where 480 rows had no counterpart at all.
    var null_key_rows = String("[")
    for i in range(500):
        if i > 0:
            null_key_rows += ","
        null_key_rows += "[null]" if i < 480 else "[7]"
    null_key_rows += "]"
    var anti_request = (
        '{"columns":["cid"],"tables":[{"name":"t","columns":["id"],"rows":[[7]]}],'
        '"ops":[{"op":"join","table":"t","left_on":"cid","right_on":"id","how":"anti"}]}'
    )
    var anti_response = run_query_execute(anti_request, null_key_rows)
    if (
        anti_response.find('"error"') < 0
        and anti_response.find("0 of 500 left rows kept (unmatched, non-null key)") >= 0
        and anti_response.find("480 left rows had a null key") >= 0
        and anti_response.find("NEITHER half") >= 0
        and anti_response.find("left rows unmatched") < 0
    ):
        passed += 1
        print("  ✅ anti states the 480 null-key rows it excluded, and is labelled kept")
    else:
        failed += 1
        print("  ❌ anti null-key lineage:", _head(anti_response, 340))

    # ── 6. the prefix guard must compare right names against EACH OTHER ──────
    # One table declaring `id` twice emitted two columns called `t.id`; Schema.index_of
    # returns the FIRST match, so every later reference silently read one of the two.
    var dup_right = run_query_execute(
        '{"columns":["g"],"rows":[[1]],"tables":[{"name":"t","columns":["id","id"],'
        '"rows":[[1,99]]}],"ops":[{"op":"join","table":"t","left_on":"g",'
        '"right_on":"id"}]}',
        "[[1]]",
    )
    if (
        dup_right.find('"error_code":"query_op_failed"') >= 0
        and dup_right.find("two columns named 't.id'") >= 0
        and dup_right.find("rename") >= 0
        and dup_right.find('"result"') < 0
    ):
        passed += 1
        print("  ✅ two right columns of one name collide before the join materialises")
    else:
        failed += 1
        print("  ❌ right-vs-right prefix collision:", _head(dup_right, 300))

    # ── 7. join is the one op that can double the WIDTH ──────────────────────
    var wide_left_300 = build_batch(_wide_header("l", 300), _wide_rows(1, 300, 1.0))
    var wide_right_300 = parse_named_tables(
        '{"tables":[{"name":"w","columns":'
        + _wide_header_array("r", 300)
        + ',"rows":'
        + _wide_rows(1, 300, 1.0)
        + "}]}",
        _empty_strings(),
        _empty_strings(),
    )
    detail = String("")
    var width_capped = False
    try:
        var _too_wide = apply_op_detailed(
            wide_left_300,
            '{"op":"join","table":"w","left_on":"l0","right_on":"r0"}',
            False,
            wide_right_300,
            detail,
        )
    except e:
        width_capped = String(e).find("600 columns") >= 0 and String(e).find(
            "at most 512"
        ) >= 0
    if width_capped:
        passed += 1
        print("  ✅ a 300 + 300 column join is refused on width, as window already was")
    else:
        failed += 1
        print("  ❌ join width bound did not fire")

    # ── 8. the corrected byte-per-cell arithmetic, and the header check's gap ─
    # parse_rows holds values (8 B/cell) + mask (1 B) + the `.copy()` handed to
    # float64_with_nulls (8 B) + the bitmap (0.125 B) ~= 17.125 B/cell, so the ingest peak at
    # MAX_MATERIALIZED_CELLS is ~544 MB — past the 512 MiB residency budget, not the 288 MB
    # the comment used to claim. take_column moves instead of copying: ~9.125 B/cell.
    var residency_budget = 512 * 1024 * 1024
    if (
        MAX_MATERIALIZED_CELLS * 137 // 8 > residency_budget
        and MAX_MATERIALIZED_CELLS * 73 // 8 < residency_budget
    ):
        passed += 1
        print("  ✅ the cell budget's real peak is ~17 B/cell in, ~9 B/cell taken")
    else:
        failed += 1
        print("  ❌ MAX_MATERIALIZED_CELLS arithmetic no longer matches its comment")

    # The resident-header consistency check fires when a header EXISTS...
    var resident_raw = String('{"tables":[{"name":"t","columns":["id","tier"],'
        '"dataset":"@ds"}]}')
    var resident_rows = List[String]()
    resident_rows.append("[[7,1]]")
    var good_headers = List[String]()
    good_headers.append('["id","tier"]')
    var bad_headers = List[String]()
    bad_headers.append('["id"]')
    var no_headers = List[String]()
    no_headers.append("")  # a resident dataset stored as a BARE ROW ARRAY
    var header_checked = False
    try:
        var _mismatch = parse_named_tables(resident_raw, resident_rows, bad_headers)
    except e:
        header_checked = String(e).find(
            "resident dataset's header has 1 columns"
        ) >= 0
    var header_ok = parse_named_tables(resident_raw, resident_rows, good_headers)
    # ...and is SKIPPED, by construction, when the resident value is a bare row array:
    # there is no header to compare, and parse_rows PADS a short row, so nothing here can
    # tell a narrow row from an export with trailing missing fields. That gap is documented
    # at the check rather than left to be discovered.
    var uncovered = parse_named_tables(resident_raw, resident_rows, no_headers)
    if (
        header_checked
        and header_ok.count() == 1
        and header_ok.batches[0].width() == 2
        and uncovered.count() == 1
        and uncovered.batches[0].width() == 2
    ):
        passed += 1
        print("  ✅ the resident-header check fires with a header and is skipped without")
    else:
        failed += 1
        print("  ❌ resident-header check behaviour changed")

    print("  [query.plan] Passed:", passed, "Failed:", failed)
