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
from query.plan import (
    apply_op,
    build_batch,
    parse_column_names,
    parse_nodes,
    parse_rows,
    json_string_field,
    json_unescape,
    plan_hash,
    run_query_execute,
    substring,
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

    print("  [query.plan] Passed:", passed, "Failed:", failed)
