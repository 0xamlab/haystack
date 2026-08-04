"""
query.plan — parse and run a whole query plan in one frame. Zero Python.

This is the reachability half of the query plane. `executor`, `join`, `window` and
`aggregate` are Mojo-only; nothing outside the worker can call them until a plan can
cross the frame boundary. That plan is JSON in, columns out, one dispatch.

Wire format
-----------
    {"type":"query_execute",
     "columns":["order_id","customer_id","amount"],
     "rows":[[1,7,10.0],[2,8,20.0]],         // or "dataset":"@ds_1"
     "tables":[                              // side tables for join, OUTSIDE ops
       {"name":"customers","columns":["id","tier"],"rows":[[7,1],[9,3]]},
       {"name":"regions","columns":["id","region"],"dataset":"@ds_2"}
     ],
     "ops":[
       {"op":"filter","predicate":{"nodes":[...],"root":2}},
       {"op":"join","table":"customers","left_on":"customer_id","right_on":"id",
        "how":"left","method":"hash","prefix":"customers."},
       {"op":"window","fn":"rank","partition_by":["region"],"order_by":["amount"],
        "desc":[true],"as":"rank_desc"},
       {"op":"aggregate","by":"region","value":"amount","agg":"sum"},
       {"op":"sort","by":"amount","desc":true,"nulls_last":true},
       {"op":"top_k","by":"amount","k":10,"desc":true}
     ],
     "strict":false}

Rows are row-major, matching how a caller already holds tabular data, and are
transposed once on ingest. Columns are addressed by NAME in a plan and resolved to
indices once, so a plan does not silently target the wrong column when the caller
reorders its `columns` list.

The response is
    {"result":{"columns":[...],"rows":[[...]]},"lineage":[...],"ops":N,"rows":N,
     "plan_hash":"...", "non_finite_cells":N}      // last key ONLY when N > 0

`non_finite_cells` counts cells whose value was not a real number — an overflowed sum, a
0/0 — and which are therefore `null` in `rows`. A Float64 reaches the wire in exactly one
place (`_cell_text`) and the policy there is ABSENT, never the bare tokens `inf` or `nan`:
neither is JSON, so emitting them turns a successful answer into a response the client
cannot parse. Counting them is what keeps the absence from being silent.

What the caller sends must be JSON, and `Infinity`, `-Infinity` and `NaN` are not
(`json.org` defines exactly three bare literals: `true`, `false`, `null`). They are
rejected by name, naming the row and column, BEFORE any value reaches `json/parser.mojo` —
which is frozen and ABORTS THE PROCESS on them. See `json_literal_problem`.

Two limits are about the RESPONSE rather than an allocation, and both fail with a typed
error before the response is built: a join that cannot fit the transport's 64 MB frame is
refused as `query_op_failed` before it materialises, and a plan whose final result cannot
fit is refused as `result_too_large`. See MAX_RESPONSE_BYTES.

`strict` governs EXPRESSION evaluation — `filter` and `project` — and nothing else.
Neither `join` nor `window` consults it, so it does not change null-key or null-partition
semantics.

Side tables live OUTSIDE `ops`
------------------------------
A join names a table (`"table":"customers"`); the table's HEADER and BODY are top-level.
Three reasons, and the first is disqualifying for the alternative: `plan_hash` is over
`ops`, so inlining a right table in the op would make the hash data-dependent and two
runs of the same computation over different data would stop comparing — destroying the
one property the hash exists for. Second, a table joined twice would be shipped and
PARSED twice. Third, a 20-op plan over one dimension table would ship it 20 times.

A table entry carries `name`, `columns`, and exactly one of `rows` (inline, reachable
from every SDK) or `dataset` (a handle, a payload optimisation for a caller holding a
connection). The op JSON is byte-identical either way. `tables` is an ARRAY, not an
object map, because `json/parser.mojo` has no object-key enumerator and the two passes
that must agree on ordering — `table_dataset_handles` in `algenta_runtime` and
`parse_named_tables` here — cannot disagree when both index the same array positionally.

The same table joined twice is ONE entry and TWO join ops with different `prefix`
values. Both prefixes are in `ops`, so `plan_hash` distinguishes the two joins. Reusing
the default prefix twice is REJECTED, because `Schema.index_of` returns the first match
and a silent collision would resolve every later reference to the wrong column.

Semantic divergences that look like bugs and are not
----------------------------------------------------
  * A null JOIN key matches nothing, while `distinct` treats two nulls as the same row.
    `join.mojo`'s header explains why both are right.
  * A null PARTITION key forms its own single partition, while a null group key in
    `aggregate` is counted separately.
  * `SUM` over an empty window frame is 0 here, not SQL's NULL: `numeric.contract`
    governs, and `window.mojo` says so explicitly.

Row order is never permuted by `window`
---------------------------------------
`partition_rows` computes an internal ordering and the window column is written back by
ORIGINAL row index, so the batch keeps its row order and the window value is appended as
one column. A caller wanting window order adds a `sort` op AFTER. Permuting here would
silently change what a following `limit` or `top_k` means.

Errors are up front and typed
-----------------------------
Every operator resolves its column names, and every expression is checked by
`executor.plan_problem`, BEFORE the first operator runs. A plan that references a
missing column or an unimplemented opcode is rejected whole. Failing partway through
would leave a response that is a correct answer to a prefix of the plan, which is worse
than no answer because it is indistinguishable from a complete one.

plan_hash
---------
SHA-256 over the canonically-encoded `ops` array with no data mixed in, via
`canonical.from_json.transcode` — so the hash is over the plan's VALUES, not its JSON
text. Reordering keys or changing whitespace does not change it; changing a threshold
does. Same rule as `algenta_runtime.pipeline.plan_hash`, and for the same reason: the
hash identifies the computation so two runs, machines or languages can be compared.

It identifies LESS than a reader might assume, and that is deliberate. A join's table
NAME, keys, `how`, `method` and `prefix` are in `ops` and so are hashed; the table's
BODY and HEADER are not — exactly as the left side's `rows` and `columns` are not today.
So two plans joining the same-named table with different headers hash identically. Do
not widen the ops hash to fix that: it would put rows in the hash. If header identity is
ever wanted it goes in as a separate `schema_hash` field.
"""
from std.math import isinf, isnan
from std.sys import info
from json.parser import (
    find_key,
    json_array_len,
    json_array_tokens,
    json_get_bool,
    json_get_int,
    json_parse_float64_list,
    skip_json_value,
    skip_whitespace,
)

# `json_get_array` and `json_get_object` are deliberately NOT imported: they rebuild their
# substring through `chr(Int(byte))`, which re-encodes every byte >= 0x80 and corrupts a
# raw-UTF-8 name. Every array and object read here goes through `json_raw_array` /
# `json_raw_object` instead. `json_array_tokens` survives in `parse_rows` alone, where the
# elements are numbers and `chr` is therefore the identity.

from canonical.from_json import transcode
from canonical.hash import hash_canonical_bytes
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_SUM,
    AGG_UNKNOWN,
    aggregation_token,
    parse_aggregation,
    unknown_aggregation_error,
)
from query.aggregate import MAX_FUSED_AGGS, ManyGroupedResult, planned_workers
from query.composed import group_by_composed_parallel
from query.executor import (
    describe_batch_shape,
    distinct_rows,
    filter_rows,
    limit_rows,
    plan_problem,
    project,
    select_columns,
    sort_rows,
    sort_rows_multi,
    top_k_rows,
)
from query.ir import binary, col_ref, literal, unary
from query.join import (
    JOIN_INNER,
    JOIN_LEFT,
    JoinResult,
    hash_join_indices,
    is_matchable_key,
    is_sorted_ascending,
    join_output_rows,
    materialize,
    merge_join_indices,
    semi_join_indices,
)
from query.window import (
    Partitions,
    cumulative,
    dense_rank,
    describe_partitions,
    framed_aggregate,
    lag_lead,
    partition_rows,
    partition_total,
    rank,
    row_number,
)
from columnar.batch import take
from types import ExprNode

# Bounds. Generous for real plans, but a single-threaded worker must not be pinnable by
# one malformed frame.
comptime MAX_OPS: Int = 64
comptime MAX_COLUMNS: Int = 512
comptime MAX_ROWS: Int = 1_000_000

# Side tables for `join`. Eight is more than any plan here has needed and keeps the
# worst-case parse bounded; the cell budget below is the bound that actually matters.
comptime MAX_TABLES: Int = 8

# Total cells across ALL side tables, and the ceiling on a join's materialized output.
# A per-table ceiling would not be a bound (rule 1c): eight tables each under a per-table
# cap allocate eight times it, so this is summed over every table in the request.
#
# BYTES PER CELL, corrected. The first version of this comment said "~288 MB at 8 bytes of
# value plus 1 byte of validity per cell", which understates the peak by about 2x:
#
#   parse_rows holds  List[Float64] values   8 bytes/cell
#                   + List[Bool]   mask      1 byte/cell
#   then float64_with_nulls is called as `float64_with_nulls(values[c].copy(), masks[c])`,
#   so the COPY                            + 8 bytes/cell   lives at the same time as the
#   original (the `values` list is still alive until the function returns)
#   plus the validity bitmap               + 0.125 bytes/cell
#                                          ------------------
#                                          ~17.1 bytes/cell
#
# `take_column` (join / sort / filter output) does not copy — it moves with `values^` — so
# its peak is ~9.1 bytes/cell. 32,000,000 cells is therefore ~544 MB on the INGEST path
# and ~292 MB on the take path, not 288 MB. That is at the session's 512 MiB residency
# budget rather than comfortably inside it; the number is left as it is because lowering it
# would reject requests accepted today, but the comment must not claim half the real cost.
#
# Judgement, not measurement: worst case is side tables plus a join output plus a window
# append, roughly 3x this transiently. The PRE-EXISTING left-batch bound is looser still
# (MAX_COLUMNS x MAX_ROWS x 17 bytes is ~8.7 GB, well past the session's 512 MiB residency
# budget) and is deliberately NOT tightened here, because that would reject requests that
# are accepted today.
comptime MAX_MATERIALIZED_CELLS: Int = 32_000_000

# ── the RESPONSE bound ────────────────────────────────────────────────────────
# Every bound above bounds an ALLOCATION. None of them bounds the SERIALIZED response
# against the transport's frame cap (`_MAX_FRAME_BYTES = 64 * 1024 * 1024` in
# `packages/algenta/algenta/native/worker.py`, enforced on both send and receive), and a
# join is the first op whose response can be ~1000x its request — so a plan inside every
# engine bound still produces a frame the transport refuses to carry, which presents to the
# caller as `NativeWorkerUnavailable` ("invalid response size") rather than as an error
# about the plan.
#
# THE ARITHMETIC, rows x cols -> bytes. `_batch_to_json` writes per cell the decimal text
# of one Float64 plus one separator byte:
#
#   narrowest  "0.0" + ','                       ->  4 bytes/cell
#   widest     "-1.7976931348623157e+308" + ','  -> 25 bytes/cell   (measured: 24 + 1)
#   per row    '[', ']' and the row's ','        ->  3 bytes/row
#
# so a rows x cols result serializes to between `rows * (4 * cols + 3)` and
# `rows * (25 * cols + 3)` bytes, plus the header (one quoted, escaped column name each)
# and the envelope. A 32,000,000-cell result — inside MAX_MATERIALIZED_CELLS — is therefore
# at least 128 MB and at most 800 MB: undeliverable either way.
#
# 56 MB, not 64: the frame also carries `lineage` (one object per op, which a join or window
# extends with a detail string), `plan_hash`, `ops`, `rows` and the JSON-RPC envelope the
# worker wraps around all of it. 8 MB of headroom for those is generous and keeps the check
# on the side of refusing rather than emitting an unsendable frame.
comptime MAX_RESPONSE_BYTES: Int = 56 * 1024 * 1024

# Measured above with `String(Float64)`: the widest Float64 text is 24 bytes
# ("-1.7976931348623157e+308"), the narrowest 3 ("0.0"). `null` for an absent or non-finite
# cell is 4, which is why the floor counts 4 rather than 3.
comptime MAX_VALUE_TEXT_BYTES: Int = 24
comptime MIN_VALUE_TEXT_BYTES: Int = 3

# A join's output row ceiling, symmetric with ingest: a plan may not produce more rows
# than a plan may send.
comptime MAX_JOIN_OUTPUT_ROWS: Int = MAX_ROWS

# THE most important number here. `window` is the first op to run
# `partition_rows` -> `executor.sort_indices_multi` -> `_sort_pass` on the RAW row count,
# and that is a stable INSERTION sort: one O(n^2) pass per sort key. The existing `sort`
# op has only ever been exercised on small grouped results.
#
# MEASURED, one partition key plus one order key, `mojo run` (the JIT, so the compiled
# worker is faster; the SHAPE is what matters):
#
#     1,000 rows    0.9 ms
#     5,000 rows   20.2 ms      4x rows -> 23x time
#    10,000 rows   81.2 ms      4.0x
#    20,000 rows  326.7 ms      4.0x
#
# Exactly quadratic, so MAX_ROWS = 1,000,000 extrapolates to 327 ms x 2500 ~= 14 MINUTES,
# which presents to a client as a HANG with no diagnosis rather than as an error. 20,000
# is the last size that stays under a third of a second. A window op over more rows is
# REFUSED, with a message naming the ops that reduce rows first. An honest error beats a
# hang.
#
# The fix that would raise this cap is an additive merge sort — `executor.sort_indices`
# already anticipates one — which is a separate, non-wire change.
#
# ROWS ARE ONE FACTOR OF THE COST, NOT THE COST. Two corrections to the paragraph above,
# both of which were reachable over the wire while only `n_rows` was capped:
#
#  1. The measurement is "one partition key plus one order key", i.e. TWO stable insertion
#     passes over 20,000 rows. `sort_indices_multi` runs ONE pass PER KEY, and
#     `_resolve_column_list` puts no ceiling on how many names `partition_by` / `order_by`
#     may hold, so the real sort cost is `len(keys) x n^2`. REPRODUCED: 20,000 rows with
#     `partition_by = ["a","b"] * 128` — a 497 KB payload, every value inside every
#     documented bound — ran 60.6 s before the worker was killed. Capping `n` alone bounds
#     one factor of a product.
#  2. The measurement is of the SORT alone. `framed_aggregate` then re-walks the frame for
#     every row, so `cumulative` (an unbounded frame) is a SECOND quadratic pass whose
#     per-step constant is larger than a comparison — it runs the `numeric.contract`
#     aggregate updates. `cumulative` and `framed` are therefore the worst operators here,
#     not `row_number`, and the row cap alone said nothing about them.
#
# So the bound is on TOTAL WORK, in units of one key-row comparison:
#
#     sort      len(partition_by) + len(order_by)  passes x n^2      (at least one pass)
#     cumulative  sum_i (i+1) ~= n^2/2 frame steps, x2 for the heavier
#                 per-step constant                = n^2
#     framed      n x min(preceding+1, n) frame steps, x2            = 2n x (preceding+1)
#     row_number / rank / dense_rank / lag / lead / partition_total: one O(n) pass, free
#
# 1,600,000,000 units is 2x the measured 20,000-row two-key sort (2 x 20,000^2 = 8e8 units
# ~= 327 ms under the JIT, so the budget is ~650 ms JIT and less compiled). Calibrated to
# accept every shape accepted today at the row cap — 20,000 rows x 2 keys of `row_number`
# is 8e8, and a 20,000-row `cumulative` over those keys is 1.2e9 — while refusing the
# key-multiplied ones: the 256-key reproduction above is 1.02e11, sixty-four times over.
comptime MAX_WINDOW_ROWS: Int = 20_000
comptime MAX_WINDOW_WORK: Int = 1_600_000_000


fn _string_from_utf8(data: List[UInt8]) -> String:
    """A String OWNING a copy of raw UTF-8 bytes, byte for byte.

    Why not `chr`: accumulating `chr(Int(bytes[i]))` is what the rest of the tree does
    and it is NOT byte-exact — `chr` of a byte >= 0x80 emits a two-byte UTF-8 sequence,
    so round-tripping "café" (5 bytes) yields "cafÃ©" (7 bytes). Any column name outside
    ASCII is corrupted by that idiom.

    Why `+=` into an owned String rather than `String(StringSlice(unsafe_from_utf8=...))`:
    the direct form aliases `data`, which is a LOCAL of the caller and dies on return, so
    the String is left pointing at freed memory. That is unsound whatever it appears to
    do — and it did not merely appear to work. Under the JIT it survived; in the
    optimized worker binary the same code made `filter` CRASH the process and made
    `project` read a garbage op name, reported as `unknown op ''` for a plan that plainly
    said "project". `select` and `sort` happened to survive, which is exactly how
    use-after-free presents.

    `+=` on an owned String must copy into that String's own buffer, so there is no
    aliasing left to get lucky with.
    """
    var out = String("")
    out += StringSlice(unsafe_from_utf8=Span(data))
    return out


fn _append_code_point(mut out: List[UInt8], code_point: Int):
    """UTF-8 encode one code point. Used to decode a `\\uXXXX` escape."""
    var cp = code_point
    if cp < 0:
        return
    if cp < 0x80:
        out.append(UInt8(cp))
    elif cp < 0x800:
        out.append(UInt8(0xC0 | (cp >> 6)))
        out.append(UInt8(0x80 | (cp & 0x3F)))
    elif cp < 0x10000:
        out.append(UInt8(0xE0 | (cp >> 12)))
        out.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        out.append(UInt8(0x80 | (cp & 0x3F)))
    else:
        out.append(UInt8(0xF0 | (cp >> 18)))
        out.append(UInt8(0x80 | ((cp >> 12) & 0x3F)))
        out.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        out.append(UInt8(0x80 | (cp & 0x3F)))


fn _hex_nibble(c: UInt8) -> Int:
    """One hex digit's value, or -1. Used only by the `\\uXXXX` decoder."""
    if c >= UInt8(48) and c <= UInt8(57):
        return Int(c) - 48
    if c >= UInt8(97) and c <= UInt8(102):
        return Int(c) - 97 + 10
    if c >= UInt8(65) and c <= UInt8(70):
        return Int(c) - 65 + 10
    return -1


fn substring(value: String, start: Int, end: Int) -> String:
    """Bytes `[start, end)` as a String, clamped at both ends, byte-exact.

    `String` has no `[a:b]` slice in this Mojo version, but it does have a keyword byte
    form. Clamping rather than raising because every caller here is trimming a quote or
    reading a number it already located, so an out-of-range bound means "nothing left",
    not a bug worth unwinding a whole plan for.
    """
    var bytes = value.as_bytes()
    var begin = start if start > 0 else 0
    var finish = end if end < len(bytes) else len(bytes)
    if finish <= begin:
        return String("")
    var out = List[UInt8]()
    for i in range(begin, finish):
        out.append(bytes[i])
    return _string_from_utf8(out)


fn json_unescape(token: String) -> String:
    """Decode a JSON string body: `\\"`, `\\\\`, `\\n`, `\\t`, `\\r`, `\\/`, `\\b`, `\\f`
    and `\\uXXXX` including surrogate pairs.

    This exists because a non-ASCII column name is otherwise mangled in TWO different
    ways by two different paths, and they disagree, so the name stops resolving:

        header  (json_array_tokens + strip quotes) ->  "regi\\u00f3n"   backslash kept
        op      (frozen json_get_string)           ->  "regiu00f3n"    backslash eaten

    Python's `json.dumps` escapes non-ASCII by default, so `región` arrives as
    `regi\\u00f3n` and `group_by("región", ...)` then failed with "references group
    column 'regiu00f3n', which the batch does not have (available: regi\\u00f3n)". Every
    op referencing any non-ASCII column name was broken.

    Decoding here, on both paths, makes the two agree on the real name — and a client
    that sends raw UTF-8 instead of escapes also works, because the bytes pass through
    untouched.
    """
    var bytes = token.as_bytes()
    var out = List[UInt8]()
    var i = 0
    while i < len(bytes):
        var c = bytes[i]
        if c != UInt8(92) or i + 1 >= len(bytes):  # not a backslash, or a trailing one
            out.append(c)
            i += 1
            continue
        var next = bytes[i + 1]
        if next == UInt8(117) and i + 5 < len(bytes):  # 'u'
            var h0 = _hex_nibble(bytes[i + 2])
            var h1 = _hex_nibble(bytes[i + 3])
            var h2 = _hex_nibble(bytes[i + 4])
            var h3 = _hex_nibble(bytes[i + 5])
            if h0 >= 0 and h1 >= 0 and h2 >= 0 and h3 >= 0:
                var cp = (h0 << 12) | (h1 << 8) | (h2 << 4) | h3
                i += 6
                # A high surrogate must pair with the low one that follows, or the
                # astral character decodes to two replacement-ish halves.
                if cp >= 0xD800 and cp <= 0xDBFF and i + 5 < len(bytes):
                    if bytes[i] == UInt8(92) and bytes[i + 1] == UInt8(117):
                        var l0 = _hex_nibble(bytes[i + 2])
                        var l1 = _hex_nibble(bytes[i + 3])
                        var l2 = _hex_nibble(bytes[i + 4])
                        var l3 = _hex_nibble(bytes[i + 5])
                        if l0 >= 0 and l1 >= 0 and l2 >= 0 and l3 >= 0:
                            var low = (l0 << 12) | (l1 << 8) | (l2 << 4) | l3
                            if low >= 0xDC00 and low <= 0xDFFF:
                                cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00)
                                i += 6
                _append_code_point(out, cp)
                continue
            # Not four hex digits: keep the text as-is rather than inventing a value.
            out.append(c)
            i += 1
            continue

        if next == UInt8(34):
            out.append(UInt8(34))
        elif next == UInt8(92):
            out.append(UInt8(92))
        elif next == UInt8(47):
            out.append(UInt8(47))
        elif next == UInt8(110):
            out.append(UInt8(10))
        elif next == UInt8(116):
            out.append(UInt8(9))
        elif next == UInt8(114):
            out.append(UInt8(13))
        elif next == UInt8(98):
            out.append(UInt8(8))
        elif next == UInt8(102):
            out.append(UInt8(12))
        else:
            # An unknown escape keeps both characters, so nothing is silently dropped.
            out.append(c)
            out.append(next)
        i += 2
    return _string_from_utf8(out)


fn _unquote(token: String) -> String:
    """Strip one layer of quotes and decode JSON escapes — the caller's real name."""
    var bytes = token.as_bytes()
    if len(token) >= 2 and bytes[0] == 34 and bytes[len(token) - 1] == 34:
        return json_unescape(substring(token, 1, len(token) - 1))
    return json_unescape(token)


fn json_string_field(raw: String, key: String) -> String:
    """A TOP-LEVEL string field's value, byte-exact and fully unescaped.

    Structure comes from the frozen `find_key`, which walks the object and steps over
    nested objects and arrays with `skip_json_value`. Content extraction is done here,
    byte-exactly, because `json_get_string` accumulates `chr(Int(byte))` — which corrupts
    any byte >= 0x80 — and turns `\\uXXXX` into the literal text `uXXXX`. Both are fine
    for an ASCII token and wrong for a column called `región`.

    Using `find_key` rather than a plain `raw.find('"key"')` is not a detail. The worker's
    frame layer re-serializes the request with keys SORTED, so an op arrives as

        {"by":"amount","expressions":{"nodes":[{"column":"amount","op":130}],...},"op":"sort"}

    and a naive search for `"op"` finds the NESTED one inside `expressions.nodes` first,
    reads `130`, sees it is not a string, and returns "". That was a real regression: ops
    whose keys sort before any nested `op` worked (`filter`, `aggregate`, `select`,
    `distinct`, `top_k`) while `project` — and any op carrying `expressions` — failed with
    `unknown op ''` for a plan that plainly named its op. The failing set matched the
    alphabetical key order exactly, which is what identified it.
    """
    var pos = find_key(raw, key)
    if pos < 0:
        return String("")
    var bytes = raw.as_bytes()
    if pos >= len(bytes) or bytes[pos] != UInt8(34):
        return String("")  # present, but not a string value
    pos += 1
    var start = pos
    # Find the closing quote, honouring escapes so `\"` does not end the string early.
    while pos < len(bytes):
        if bytes[pos] == UInt8(92):
            pos += 2
            continue
        if bytes[pos] == UInt8(34):
            break
        pos += 1
    return json_unescape(substring(raw, start, pos))


fn json_raw_field(raw: String, key: String, opener: UInt8) -> String:
    """A top-level array or object field's raw TEXT, byte for byte.

    `json_get_array` and `json_get_object` rebuild their substring with
    `chr(Int(bytes[i]))`, which re-encodes every byte >= 0x80 — so a client sending raw
    UTF-8 (`ensure_ascii=False`) has `región` turned into `regiÃ³n` on any ARRAY-valued
    read. That silently applied to `columns`, `by`, `names` and `distinct`, so this
    module's claim that a client may send raw UTF-8 instead of escapes held only for
    `json_string_field` reads.

    Structure still comes from the frozen `find_key` + `skip_json_value`; only the byte
    extraction is done here, through `substring`. For ASCII input `chr` is the identity,
    so switching the existing reads to this changes nothing they did before.

    `opener` is the byte the value must start with — `[` for an array, `{` for an object —
    so a `"desc":false` where an array was expected reads as absent rather than as a
    number scraped out of the middle of a value.
    """
    var pos = find_key(raw, key)
    if pos < 0:
        return String("")
    var bytes = raw.as_bytes()
    if pos >= len(bytes) or bytes[pos] != opener:
        return String("")  # present, but not the shape asked for
    return substring(raw, pos, skip_json_value(raw, pos))


fn json_raw_array(raw: String, key: String) -> String:
    """A top-level array field's raw text, byte-exact. See `json_raw_field`."""
    return json_raw_field(raw, key, UInt8(91))  # '['


fn json_raw_object(raw: String, key: String) -> String:
    """A top-level object field's raw text, byte-exact. See `json_raw_field`."""
    return json_raw_field(raw, key, UInt8(123))  # '{'


fn json_raw_tokens(array: String) -> List[String]:
    """Split a JSON array into its element texts in ONE pass, byte for byte.

    The byte-exact counterpart of the frozen `json_array_tokens`, which accumulates
    `chr(Int(bytes[i]))` and therefore corrupts every element containing a byte >= 0x80.
    Fixing `json_raw_field` alone would not be enough: the array text can be byte-exact
    and still be split into mangled tokens.

    ONE pass, deliberately. `json_array_get(arr, i)` in a loop rescans from position 0 on
    every index, which is O(n^2) — that trap cost 1975 ms on 10,000 rows before it was
    found, and `json/parser.mojo` documents it on `json_array_tokens` itself.
    """
    var bytes = array.as_bytes()
    var n = len(array)
    var result = List[String]()
    var p = skip_whitespace(array, 0)
    if p >= n or bytes[p] != UInt8(91):  # '['
        return result^
    p += 1
    while p < n:
        p = skip_whitespace(array, p)
        if p >= n or bytes[p] == UInt8(93):  # ']'
            break
        var end = skip_json_value(array, p)
        result.append(substring(array, p, end))
        p = skip_whitespace(array, end)
        if p < n and bytes[p] == UInt8(44):  # ','
            p += 1
    return result^


fn _saturating_product(a: Int, b: Int) -> Int:
    """`a * b`, clamped instead of wrapped.

    `rows * cols` is not a bound if the multiply can wrap: a wrapped product compares
    small and the check passes, which is exactly how an over-long read gets through — and
    a read past the end of a List is an UNCATCHABLE crash that takes the worker and every
    resident dataset with it.
    """
    comptime CEILING: Int = 1 << 62
    if a <= 0 or b <= 0:
        return 0
    if a > CEILING // b:
        return CEILING
    return a * b


fn _serialized_bytes_floor(n_rows: Int, n_columns: Int) -> Int:
    """The FEWEST bytes `_batch_to_json` can write for a rows x cols result.

    `rows * (4 * cols + 3)`: the narrowest cell text is `"0.0"` (3 bytes, measured) plus one
    separator, and every row costs its two brackets and one comma. A floor, not an estimate,
    so a refusal based on it has no false positives — if even the floor is past the frame
    cap, no data can make the response deliverable. That is what makes it safe to apply
    BEFORE the rows exist, which is the whole point: a response that cannot be delivered
    must not be computed.
    """
    var per_row = _saturating_product(n_columns, MIN_VALUE_TEXT_BYTES + 1) + 3
    return _saturating_product(n_rows, per_row)


fn _serialized_bytes_ceiling(n_rows: Int, n_columns: Int) -> Int:
    """The MOST bytes `_batch_to_json` can write for a rows x cols result.

    `rows * (25 * cols + 3)`: the widest cell text is 24 bytes
    (`-1.7976931348623157e+308`, measured) plus one separator. Used as a FAST PATH — when
    even the ceiling fits the budget, no measuring pass is needed, which is every ordinary
    response.
    """
    var per_row = _saturating_product(n_columns, MAX_VALUE_TEXT_BYTES + 1) + 3
    return _saturating_product(n_rows, per_row)


fn _saturating_sum(a: Int, b: Int) -> Int:
    """`a + b`, clamped instead of wrapped — the additive twin of `_saturating_product`.

    Same failure mode: a wrapped total compares SMALL, so the bound passes and the work the
    bound existed to refuse runs anyway. Used where two independently-bounded quadratic
    terms are added together, each of which may already have saturated.
    """
    comptime CEILING: Int = 1 << 62
    if a <= 0:
        return b if b > 0 else 0
    if b <= 0:
        return a
    if a > CEILING - b:
        return CEILING
    return a + b


fn _plan_error(code: String, message: String) -> String:
    return (
        '{"error":"'
        + code
        + ": "
        + message
        + '","error_code":"'
        + code
        + '","error_message":"'
        + message
        + '"}'
    )


fn _json_escape(value: String) -> String:
    """Escape a name for embedding in the response, preserving non-ASCII bytes exactly.

    Names come from the caller, so an unescaped quote would produce a malformed response
    — a parse error on the client for what is really a bad input name.

    Multi-byte UTF-8 is emitted RAW, which JSON permits and which is the only way a name
    survives: passing each byte through `chr(Int(c))` re-encodes bytes >= 0x80 and turns
    `región` into `regiÃ³n` on the way out, so a caller would get back a different name
    than it sent.

    Control bytes below 0x20 are escaped properly rather than replaced with a space,
    because a tab inside a name is data, not damage.
    """
    var out = List[UInt8]()
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        var c = bytes[i]
        if c == UInt8(34):  # "
            out.append(UInt8(92))
            out.append(UInt8(34))
        elif c == UInt8(92):  # backslash
            out.append(UInt8(92))
            out.append(UInt8(92))
        elif c == UInt8(10):
            out.append(UInt8(92))
            out.append(UInt8(110))
        elif c == UInt8(9):
            out.append(UInt8(92))
            out.append(UInt8(116))
        elif c == UInt8(13):
            out.append(UInt8(92))
            out.append(UInt8(114))
        elif c < UInt8(32):
            # Any other control byte as \u00XX, the only portable spelling.
            out.append(UInt8(92))
            out.append(UInt8(117))
            out.append(UInt8(48))
            out.append(UInt8(48))
            var hi = Int(c) >> 4
            var lo = Int(c) & 0xF
            out.append(UInt8(48 + hi) if hi < 10 else UInt8(97 + hi - 10))
            out.append(UInt8(48 + lo) if lo < 10 else UInt8(97 + lo - 10))
        else:
            out.append(c)
    return _string_from_utf8(out)


# ── validate before the frozen tokenizer ──────────────────────────────────────


fn _is_json_letter(c: UInt8) -> Bool:
    return (c >= UInt8(65) and c <= UInt8(90)) or (c >= UInt8(97) and c <= UInt8(122))


fn _is_json_number_start(c: UInt8) -> Bool:
    return (c >= UInt8(48) and c <= UInt8(57)) or c == UInt8(45) or c == UInt8(
        43
    ) or c == UInt8(46)


fn _spells_json_literal(text: String, start: Int, end: Int) -> Bool:
    """True if bytes `[start, end)` spell `true`, `false` or `null`.

    Byte comparison rather than `substring(...) == "null"` because this is on the ingest
    hot path: a rows payload is full of `null`, and allocating a 4-byte String per null
    cell to compare it is a cost per CELL, not per error. Only a token that turns out not
    to be a literal is ever materialised, and that token is on its way into an error
    message anyway.
    """
    var bytes = text.as_bytes()
    var length = end - start
    if length == 4:
        if (
            bytes[start] == UInt8(116)  # t
            and bytes[start + 1] == UInt8(114)  # r
            and bytes[start + 2] == UInt8(117)  # u
            and bytes[start + 3] == UInt8(101)  # e
        ):
            return True
        return (
            bytes[start] == UInt8(110)  # n
            and bytes[start + 1] == UInt8(117)  # u
            and bytes[start + 2] == UInt8(108)  # l
            and bytes[start + 3] == UInt8(108)  # l
        )
    if length == 5:
        return (
            bytes[start] == UInt8(102)  # f
            and bytes[start + 1] == UInt8(97)  # a
            and bytes[start + 2] == UInt8(108)  # l
            and bytes[start + 3] == UInt8(115)  # s
            and bytes[start + 4] == UInt8(101)  # e
        )
    return False


fn json_literal_problem(text: String, rows_shaped: Bool) -> String:
    """"" if every bare token in `text` is JSON; otherwise what is wrong and where.

    THIS RUNS BEFORE THE FROZEN TOKENIZER, AND IT HAS TO. `json/parser.mojo` is frozen and
    `json_array_tokens` aborts the PROCESS on a JSON extension literal — an uncatchable
    List bounds assert, so `try`/`except` around the call does not help and every resident
    dataset in the worker dies with it. The mechanism, for `[Infinity]`:

        skip_json_value sees 'I'  -> unknown byte, returns p+1
                         sees 'n' -> assumes the literal "null",  returns p+4
                         sees 'i' -> unknown byte, returns p+1
                         sees 't' -> assumes the literal "true",  returns p+4  == 11 > 10
        json_array_tokens then runs `for i in range(start, end)` over `bytes[i]`
        -> "index 10 is out of bounds", process gone.

    REPRODUCED, and it killed the worker:

        run_query_execute('{"columns":["k"],"tables":[{"columns":["id"],"name":"t",
          "rows":[[Infinity]]}],"ops":[{"how":"left","left_on":"k","op":"join",
          "right_on":"id","table":"t"}],"rows":[[1]]}', "[[1]]")

    `NaN` does not abort; it mis-tokenises (`skip_json_value` reads `NaN]` as one "null"),
    so a one-cell row is reported as a WIDTH error and the caller is sent to look at their
    header. Both outcomes are wrong for the same reason: `Infinity`, `-Infinity` and `NaN`
    are not JSON. `json.org`'s grammar has three bare literals — `true`, `false`, `null` —
    and no others, so anything else is rejected here BY NAME rather than parsed.

    Why a scanner rather than a parser: this must not itself be able to read past an end,
    so it is one linear pass with every index guarded, it allocates nothing per byte, and
    it never calls into `json/parser.mojo`. Numbers are consumed as a UNIT so that the `e`
    of `1e308` is not mistaken for the start of a name; strings are skipped whole (escapes
    honoured) so that a column literally called `"NaN"` is data, not an error.

    `rows_shaped` tracks bracket depth to name the offending ROW and COLUMN — depth 1 is
    the row array, depth 2 a row's cells — which is the difference between "your data is
    bad somewhere" and "row 7, column 2".
    """
    var bytes = text.as_bytes()
    var n = len(bytes)
    var i = 0
    var depth = 0
    var row_index = 0
    var column_index = 0
    while i < n:
        var c = bytes[i]

        if c == UInt8(34):  # '"' — a string body is data, whatever it spells
            i += 1
            while i < n:
                if bytes[i] == UInt8(92):  # backslash
                    i += 2
                    continue
                if bytes[i] == UInt8(34):
                    break
                i += 1
            i += 1
            continue

        if c == UInt8(91) or c == UInt8(123):  # '[' '{'
            depth += 1
            if depth == 2:
                column_index = 0
            i += 1
            continue

        if c == UInt8(93) or c == UInt8(125):  # ']' '}'
            if depth == 2:
                row_index += 1
            depth -= 1
            i += 1
            continue

        if c == UInt8(44):  # ','
            if depth == 2:
                column_index += 1
            i += 1
            continue

        if _is_json_number_start(c):
            # One number, consumed whole: its exponent letter is part of the number, and a
            # lone leading '-' (as in `-Infinity`) leaves the name to the branch below.
            i += 1
            while i < n:
                var d = bytes[i]
                if (
                    (d >= UInt8(48) and d <= UInt8(57))
                    or d == UInt8(46)
                    or d == UInt8(101)  # 'e'
                    or d == UInt8(69)  # 'E'
                    or d == UInt8(45)
                    or d == UInt8(43)
                ):
                    i += 1
                else:
                    break
            continue

        if _is_json_letter(c):
            var start = i
            while i < n and _is_json_letter(bytes[i]):
                i += 1
            if _spells_json_literal(text, start, i):
                continue
            # Report the sign with the name, so `-Infinity` is not quoted back as
            # `Infinity` and a reader cannot think the sign was accepted.
            var shown = substring(text, start, i)
            if start > 0 and (
                bytes[start - 1] == UInt8(45) or bytes[start - 1] == UInt8(43)
            ):
                shown = substring(text, start - 1, i)
            var where = String("")
            if rows_shaped:
                where = (
                    "row "
                    + String(row_index)
                    + ", column "
                    + String(column_index)
                    + " is "
                )
            else:
                where = "byte " + String(start) + " begins "
            return (
                where
                + "'"
                + shown
                + "', which is not a JSON value: the only bare literals JSON defines are"
                " true, false and null (Infinity, -Infinity and NaN are not JSON -- send"
                " null for a missing value, or a finite number)"
            )

        i += 1
    return String("")


fn reject_non_json_literals(text: String, rows_shaped: Bool) raises:
    """Raise if `text` holds a bare token JSON does not define. See `json_literal_problem`.
    """
    var problem = json_literal_problem(text, rows_shaped)
    if len(problem) > 0:
        raise Error(problem)


# ── ingest ────────────────────────────────────────────────────────────────────


fn parse_column_names(raw: String) raises -> List[String]:
    """The `columns` array as a name list."""
    var names = List[String]()
    var array = json_raw_array(raw, "columns")
    if len(array) == 0:
        return names^
    for token in json_raw_tokens(array):
        names.append(_unquote(token))
    return names^


fn parse_rows(
    rows_json: String, n_columns: Int
) raises -> RecordBatch:
    """Transpose a row-major `rows` array into columns, with `null` as absence.

    A row shorter than the header is padded with absences rather than rejected: a
    trailing missing field is a common shape in exported data and "this cell is
    missing" is exactly what a validity bitmap is for. A row LONGER than the header is
    an error, because the extra values have no column to belong to and guessing would
    silently drop them.

    Tokenized in ONE pass via `json_array_tokens`, at both levels. The obvious
    `for r in range(json_array_len(rows)): json_array_get(rows, r)` rescans the array
    from position 0 on every index, so it is O(n^2) — `bench_query_plane.py` measured
    the first version of this function at 1975 ms for 10,000 rows, essentially all of
    it in that rescan. `json/parser.mojo` documents the trap on `json_array_tokens`
    itself; I walked into it anyway.

    VALIDATED FIRST, because `json_array_tokens` is frozen and ABORTS the process on a JSON
    extension literal (`[[Infinity]]` -> "index 10 is out of bounds", worker gone, every
    resident dataset with it). Every row path in this module — the left batch, an inline
    side table, and a side table's rows resolved from a resident dataset — reaches the
    frozen tokenizer through this one function, so the guard belongs here and nowhere else.
    See `json_literal_problem`.
    """
    reject_non_json_literals(rows_json, True)
    var row_tokens = json_array_tokens(rows_json)
    var n_rows = len(row_tokens)
    var values = List[List[Float64]]()
    var masks = List[List[Bool]]()
    for _ in range(n_columns):
        values.append(List[Float64]())
        masks.append(List[Bool]())

    for r in range(n_rows):
        var cells = json_array_tokens(row_tokens[r])
        var width = len(cells)
        if width > n_columns:
            raise Error(
                "row "
                + String(r)
                + " has "
                + String(width)
                + " values but the header declares "
                + String(n_columns)
                + " columns"
            )
        for c in range(n_columns):
            if c >= width:
                values[c].append(0.0)
                masks[c].append(False)
                continue
            ref cell = cells[c]
            if cell == "null" or len(cell) == 0:
                values[c].append(0.0)
                masks[c].append(False)
            else:
                var parsed = json_parse_float64_list("[" + cell + "]")
                if len(parsed) == 0:
                    values[c].append(0.0)
                    masks[c].append(False)
                else:
                    values[c].append(parsed[0])
                    masks[c].append(True)

    var columns = List[Float64Array]()
    for c in range(n_columns):
        columns.append(float64_with_nulls(values[c].copy(), masks[c]))
    var names = List[String]()
    var dtypes = List[Int]()
    for c in range(n_columns):
        names.append("col_" + String(c))
        dtypes.append(0)
    return RecordBatch(Schema(names^, dtypes^), columns^, n_rows)


fn build_batch(raw: String, inline_rows: String) raises -> RecordBatch:
    """A named batch from `columns` + `rows`.

    `inline_rows` is passed separately so a resident dataset can supply the row array
    while the header still comes from the request — that is what lets `dataset_open`
    hold the data and a plan reference it without reshipping it.
    """
    var names = parse_column_names(raw)
    if len(names) == 0:
        raise Error("query_execute requires a non-empty 'columns' array")
    if len(names) > MAX_COLUMNS:
        raise Error(
            "query_execute accepts at most "
            + String(MAX_COLUMNS)
            + " columns; got "
            + String(len(names))
        )
    # Checked before transposing, not after: parsing a million rows and then
    # rejecting them costs the work the bound exists to avoid.
    if json_array_len(inline_rows) > MAX_ROWS:
        raise Error(
            "query_execute accepts at most " + String(MAX_ROWS) + " rows per frame"
        )
    var positional = parse_rows(inline_rows, len(names))

    var dtypes = List[Int]()
    for _ in range(len(names)):
        dtypes.append(0)
    var columns = List[Float64Array]()
    for c in range(positional.width()):
        columns.append(positional.column(c))
    return RecordBatch(Schema(names^, dtypes^), columns^, positional.n_rows)


# ── named side tables ─────────────────────────────────────────────────────────


struct NamedBatches(Copyable, Movable):
    """The request's `tables`, resolved ONCE before the op loop.

    Built once and borrowed by every op, so a table joined by twenty ops is parsed once,
    not twenty times. Callers bind with `ref right = tables.batches[idx]` so a join does
    not copy the table it is joining to.
    """

    var names: List[String]
    var batches: List[RecordBatch]

    fn __init__(out self):
        self.names = List[String]()
        self.batches = List[RecordBatch]()

    fn __init__(out self, var names: List[String], var batches: List[RecordBatch]):
        self.names = names^
        self.batches = batches^

    fn count(self) -> Int:
        return len(self.names)

    fn index_of(self, name: String) -> Int:
        for i in range(len(self.names)):
            if self.names[i] == name:
                return i
        return -1

    fn describe(self) -> String:
        """The available table names, for an error that names what IS there."""
        if len(self.names) == 0:
            # "available: )" would read as a truncated message rather than as the real
            # answer, which is that this request supplied no tables at all.
            return String("none")
        var out = String("")
        for i in range(len(self.names)):
            if i > 0:
                out += ", "
            out += self.names[i]
        return out


fn table_names(raw: String) -> List[String]:
    """Each `tables` entry's `name`, in DOCUMENT order. "" for an entry without one.

    Positional, like `table_dataset_handles`, so `algenta_runtime` can name the table a
    failing handle belongs to without re-deriving the ordering.
    """
    var out = List[String]()
    var tables = json_raw_array(raw, "tables")
    if len(tables) == 0:
        return out^
    for token in json_raw_tokens(tables):
        out.append(json_string_field(token, "name"))
    return out^


fn table_dataset_handles(raw: String) -> List[String]:
    """Each `tables` entry's resident-dataset handle, in DOCUMENT order.

    One entry per element of `tables`: the handle with a leading `@` stripped, or "" for a
    table that carries inline `rows`. This is the whole of the session coupling — the
    caller (`algenta_runtime.query`) owns the registry, resolves each non-empty handle and
    hands the rows back positionally, so `query/` never imports `algenta_runtime/` and the
    query plane stays testable without a worker loop or a session.

    Positional agreement is why `tables` is an array. Both this pass and
    `parse_named_tables` index the same array, so they cannot disagree about which entry
    is which — which an object-key enumerator (a scanner that does not exist in
    `json/parser.mojo`) would have made possible.
    """
    var out = List[String]()
    var tables = json_raw_array(raw, "tables")
    if len(tables) == 0:
        return out^
    for token in json_raw_tokens(tables):
        var handle = json_string_field(token, "dataset")
        if len(handle) > 1 and handle.as_bytes()[0] == 64:  # '@', optional
            handle = substring(handle, 1, len(handle))
        out.append(handle)
    return out^


fn parse_named_tables(
    raw: String, table_rows: List[String], table_headers: List[String]
) raises -> NamedBatches:
    """Resolve `tables` into batches, once, before any op runs.

    `table_rows[i]` / `table_headers[i]` are what a session resolved for entry `i` (empty
    for an inline table, and both lists empty when the request has no session at all).
    Two parallel positional lists rather than the resident VALUE, so the header-mismatch
    check below can live here with every other wire-level message while
    `algenta_runtime.query` stays a resolver that owns no validation.

    Each entry is built by the UNCHANGED `build_batch`, which already reads `columns` from
    an arbitrary object and takes its rows separately — which is exactly a table entry. No
    new row parsing exists anywhere in this path.

    The cell budget is checked BEFORE each table is built, from the declared header width
    and the row count, not after. Rule 1c: validating a dimension and bounding an
    allocation are two different checks, and checking after building is not a bound at
    all — the allocation has already happened.
    """
    var out_names = List[String]()
    var out_batches = List[RecordBatch]()
    var tables_json = json_raw_array(raw, "tables")
    if len(tables_json) == 0:
        return NamedBatches(out_names^, out_batches^)

    var tokens = json_raw_tokens(tables_json)
    if len(tokens) > MAX_TABLES:
        raise Error(
            "query_execute accepts at most "
            + String(MAX_TABLES)
            + " named tables; got "
            + String(len(tokens))
        )

    var total_cells = 0
    for i in range(len(tokens)):
        ref token = tokens[i]
        var name = json_string_field(token, "name")
        if len(name) == 0:
            raise Error("table " + String(i) + " has no 'name'")
        for j in range(len(out_names)):
            if out_names[j] == name:
                # Two entries answering to one name would make `"table":"customers"`
                # ambiguous, and index_of would silently pick the first.
                raise Error("table '" + name + "' is declared twice")

        var reference = json_string_field(token, "dataset")
        var inline_rows = json_raw_array(token, "rows")
        var rows_json = String("")
        if len(reference) > 0 and len(inline_rows) > 0:
            raise Error(
                "table '"
                + name
                + "' declares both 'rows' and 'dataset'; supply exactly one"
            )
        if len(reference) > 0:
            var handle = reference
            if len(handle) > 1 and handle.as_bytes()[0] == 64:  # '@'
                handle = substring(handle, 1, len(handle))
            if i >= len(table_rows) or len(table_rows[i]) == 0:
                # No session resolved this entry. The handle form is reachable only from a
                # caller holding a connection; a missing handle ON a connection is
                # reported by the resolver as unknown_dataset instead.
                raise Error(
                    "table '"
                    + name
                    + "' declares dataset '"
                    + handle
                    + "' but this request has no session; open the handle on a"
                    " connection or inline its rows"
                )
            rows_json = table_rows[i]
        elif len(inline_rows) > 0:
            rows_json = inline_rows
        else:
            raise Error(
                "table '" + name + "' declares neither 'rows' nor 'dataset'"
            )

        var declared = parse_column_names(token)
        # WHAT THIS CHECK DOES NOT COVER, stated because the guard reads like a null-check
        # and is really a capability test. `algenta_runtime.query` fills `table_headers[i]`
        # with `json_raw_array(value, "columns")`, which is "" for a resident dataset stored
        # as a BARE ROW ARRAY (`[[1,2],[3,4]]`) — the shape `dataset_open` accepts alongside
        # the object form. So for exactly those datasets there is no resident header to
        # compare and this check is SKIPPED, silently as far as the response is concerned.
        #
        # It cannot be made unconditional: an inline table also carries "" here (there is no
        # resident value at all), and comparing against "" would reject every inline table
        # with "the resident dataset's header has 0 columns". Nor can the gap be closed from
        # the row data, because `parse_rows` PADS a short row with nulls by design — a raw
        # row array whose rows are narrower than the declared header is indistinguishable
        # from an export with trailing missing fields, which is a shape this module
        # deliberately accepts. Closing it properly means storing the header with the
        # dataset at `dataset_open` time, which is a change to the registry, not to a check.
        #
        # So the covered case is the one where a header EXISTS, which is every dataset
        # written by `query_execute` itself.
        if len(reference) > 0 and i < len(table_headers) and len(
            table_headers[i]
        ) > 0:
            # The resident value is the object form `{"columns":[...],"rows":[...]}` that
            # query_execute itself returns, so its header must match. `parse_rows` PADS a
            # short row with nulls, so a header mismatch would produce all-null columns
            # under a success status rather than an error.
            var resident = json_raw_tokens(table_headers[i])
            if len(resident) != len(declared):
                raise Error(
                    "table '"
                    + name
                    + "': the resident dataset's header has "
                    + String(len(resident))
                    + " columns but the request declares "
                    + String(len(declared))
                )
            for c in range(len(resident)):
                var resident_name = _unquote(resident[c])
                if resident_name != declared[c]:
                    raise Error(
                        "table '"
                        + name
                        + "': the resident dataset's column "
                        + String(c)
                        + " is named '"
                        + resident_name
                        + "' but the request declares '"
                        + declared[c]
                        + "'"
                    )

        # Bound the allocation BEFORE making it, and sum over every table: eight tables
        # each under a per-table ceiling would allocate eight times that ceiling.
        # `_saturating_product` because a wrapped product compares small and passes.
        var cells = _saturating_product(len(declared), json_array_len(rows_json))
        if total_cells + cells > MAX_MATERIALIZED_CELLS:
            raise Error(
                "named tables hold "
                + String(total_cells + cells)
                + " cells in total; at most "
                + String(MAX_MATERIALIZED_CELLS)
            )
        total_cells += cells

        var built: RecordBatch
        try:
            built = build_batch(token, rows_json)
        except e:
            # build_batch owns the header/row messages, so they are not restated here —
            # only which table they came from.
            raise Error("table '" + name + "': " + String(e))
        out_names.append(name)
        out_batches.append(built^)

    return NamedBatches(out_names^, out_batches^)


# ── expression decoding ───────────────────────────────────────────────────────


fn parse_nodes(expr_json: String, schema: Schema) raises -> List[ExprNode]:
    """Decode a `{"nodes":[...]}` array into ExprNodes, resolving column NAMES.

    A node is `{"op":100,"left":0,"right":1}`, or `{"op":0,"value":3.5}`, or
    `{"op":130,"column":"amount"}`. Column references carry a NAME, resolved here
    against the schema, so a plan cannot drift onto the wrong column when the caller
    reorders its header. A numeric `"column"` index is also accepted for a caller that
    already knows the layout.

    Literals are read through `_number_token` rather than `json_get_int`, which
    truncates: a threshold of 20.5 would silently become 20, and a filter that quietly
    moved its own boundary is the exact class of bug this plane exists to remove.
    """
    var nodes = List[ExprNode]()
    var array = json_raw_array(expr_json, "nodes")
    if len(array) == 0:
        return nodes^
    var tokens = json_raw_tokens(array)
    for i in range(len(tokens)):
        ref token = tokens[i]
        var op = json_get_int(token, "op", -1)
        if op < 0:
            raise Error("expression node " + String(i) + " has no 'op'")

        var column_name = json_string_field(token, "column")
        if len(column_name) > 0:
            var index = schema.index_of(column_name)
            if index < 0:
                raise Error(
                    "expression node "
                    + String(i)
                    + " references column '"
                    + column_name
                    + "', which the batch does not have"
                )
            nodes.append(col_ref(index))
            continue

        var numeric_column = json_get_int(token, "column", -1)
        if numeric_column >= 0:
            nodes.append(col_ref(numeric_column))
            continue

        var left = json_get_int(token, "left", -1)
        var right = json_get_int(token, "right", -1)
        if left < 0 and right < 0:
            var parsed = json_parse_float64_list(
                "[" + _number_token(token, "value") + "]"
            )
            nodes.append(literal(parsed[0] if len(parsed) > 0 else 0.0))
            continue
        if right < 0:
            nodes.append(unary(op, left))
        else:
            nodes.append(binary(op, left, right))
    return nodes^


fn _number_token(raw: String, key: String) -> String:
    """The raw numeric TEXT for a top-level key, or "0". Keeps float precision intact.

    `find_key` for the same reason as `json_string_field`: keys arrive sorted, so a naive
    search can land inside a nested object and read the wrong number. Returning the text
    rather than a parsed Int is the point — `json_get_int` truncates, so a threshold of
    20.5 would become 20 and quietly move a filter's boundary.
    """
    var pos = find_key(raw, key)
    if pos < 0:
        return "0"
    var bytes = raw.as_bytes()
    var start = pos
    while pos < len(bytes):
        var c = bytes[pos]
        var numeric = (
            (c >= UInt8(48) and c <= UInt8(57))
            or c == UInt8(45)
            or c == UInt8(43)
            or c == UInt8(46)
            or c == UInt8(101)
            or c == UInt8(69)
        )
        if not numeric:
            break
        pos += 1
    if pos == start:
        return "0"
    return substring(raw, start, pos)


# ── column resolution ─────────────────────────────────────────────────────────


fn _resolve_column(schema: Schema, name: String, what: String) raises -> Int:
    var index = schema.index_of(name)
    if index < 0:
        raise Error(
            "op references "
            + what
            + " column '"
            + name
            + "', which the batch does not have (available: "
            + schema.describe()
            + ")"
        )
    return index


fn _resolve_column_list(
    schema: Schema, array: String, what: String
) raises -> List[Int]:
    var out = List[Int]()
    if len(array) == 0:
        return out^
    for token in json_raw_tokens(array):
        out.append(_resolve_column(schema, _unquote(token), what))
    return out^


fn _resolve_one_agg(
    schema: Schema,
    op_json: String,
    what: String,
    mut value_columns: List[Int],
    mut opcodes: List[Int],
    mut value_names: List[String],
) raises:
    """Resolve one `{"value":..., "agg":...}` pair and append it to the flat
    per-aggregate lists `group_by_composed_parallel`/`group_by_many_parallel`
    take. `what` names the entry in an error ("aggregate value" for the single
    top-level pair, "aggregate value at aggs[N]" for one drawn from the list).
    """
    var token = json_string_field(op_json, "agg")
    var opcode = parse_aggregation(token)
    if opcode == AGG_UNKNOWN:
        # numeric.contract owns the message, so the accepted set is listed in one
        # place and cannot drift from what parse_aggregation actually accepts.
        raise Error(unknown_aggregation_error(token))
    var value_name = json_string_field(op_json, "value")
    var value = _resolve_column(schema, value_name, what)
    value_columns.append(value)
    opcodes.append(opcode)
    value_names.append(aggregation_token(opcode) + "_" + value_name)


fn _resolve_aggs(
    schema: Schema,
    op_json: String,
    mut value_columns: List[Int],
    mut opcodes: List[Int],
    mut value_names: List[String],
) raises:
    """Read the `aggregate` op's (value, agg) pairs — one or many — off `op_json`.

    Two accepted shapes, mutually exclusive:
      * the ORIGINAL shape — top-level `"value"` and `"agg"` strings, exactly one
        pair. Kept byte-identical: an existing plan sending this shape resolves
        through the exact same branch it always has.
      * `"aggs":[{"value":...,"agg":...}, ...]` — one scan, several aggregate
        columns. `group_by_many`/`group_by_composed_parallel` already fuse any
        number of (value, opcode) pairs into one grouped pass (see
        `aggregate.mojo`'s `MAX_FUSED_AGGS`); only the JSON-level wiring for more
        than one pair was missing, which is what this adds.

    Sending both is rejected as ambiguous rather than silently preferring one —
    the same rule `_apply_join` uses for `on` vs `left_on`/`right_on` together.
    """
    var aggs_array = json_raw_array(op_json, "aggs")
    var has_aggs = len(aggs_array) > 0
    var has_single = find_key(op_json, "value") >= 0 or find_key(op_json, "agg") >= 0
    if has_aggs and has_single:
        raise Error(
            "aggregate accepts 'value'/'agg' (one pair) OR 'aggs' (a list of"
            " pairs), not both"
        )
    if not has_aggs:
        _resolve_one_agg(
            schema, op_json, "aggregate value", value_columns, opcodes, value_names
        )
        return
    var entries = json_raw_tokens(aggs_array)
    if len(entries) == 0:
        raise Error("aggregate 'aggs' must be a non-empty array")
    if len(entries) > MAX_FUSED_AGGS:
        raise Error(
            "aggregate 'aggs' has "
            + String(len(entries))
            + " pairs; at most "
            + String(MAX_FUSED_AGGS)
            + " are fused into one pass"
        )
    for i in range(len(entries)):
        _resolve_one_agg(
            schema,
            entries[i],
            "aggregate value at aggs[" + String(i) + "]",
            value_columns,
            opcodes,
            value_names,
        )


# ── execution ─────────────────────────────────────────────────────────────────


fn _many_single_to_batch(
    result: ManyGroupedResult, key_name: String, var value_names: List[String]
) -> RecordBatch:
    """A width-1 `ManyGroupedResult` as a batch: one key column, then one
    column per requested aggregate — the single-key `aggregate` op's output
    shape, whichever route (`query.composed`, falling back to the shipped
    `group_by_many_parallel`) answered the call.

    `len(value_names)` is `result.n_aggs`: the single-aggregate call this
    replaced is exactly this loop run once, so that shape is unchanged byte
    for byte. Not `GroupedResult`'s own accessors (`.keys`/`.values`/
    `.present` at a flat per-group index): `ManyGroupedResult` lays
    `values`/`present` out `group * n_aggs + agg`, and `value_at`/`present_at`
    are that indexing's only correct readers.
    """
    var n = result.n_groups()
    var n_aggs = len(value_names)
    var columns = List[Float64Array]()
    var names = List[String]()
    var dtypes = List[Int]()

    var keys = List[Float64]()
    var key_mask = List[Bool]()
    for i in range(n):
        keys.append(result.key_tuples[i])
        key_mask.append(True)
    columns.append(float64_with_nulls(keys^, key_mask))
    names.append(key_name)
    dtypes.append(0)

    for j in range(n_aggs):
        var values = List[Float64]()
        var present = List[Bool]()
        for i in range(n):
            values.append(result.value_at(i, j))
            present.append(result.present_at(i, j))
        columns.append(float64_with_nulls(values^, present))
        names.append(value_names[j])
        dtypes.append(0)

    return RecordBatch(Schema(names^, dtypes^), columns^, n)


fn apply_op(batch: RecordBatch, op_json: String, strict: Bool) raises -> RecordBatch:
    """Run one operator with no side tables and no lineage detail.

    A wrapper, not the implementation: `apply_op_detailed` grew two parameters and this
    signature is what every existing caller and assertion uses. Adding the parameters in
    place would have forced a pinned suite to move.
    """
    var empty = NamedBatches()
    var detail = String("")
    return apply_op_detailed(batch, op_json, strict, empty, detail)


fn apply_op_detailed(
    batch: RecordBatch,
    op_json: String,
    strict: Bool,
    tables: NamedBatches,
    mut detail: String,
) raises -> RecordBatch:
    """Run one operator. Raises with a message naming the op and the reason.

    Every branch resolves its columns by name first, so a bad reference fails before
    any row is touched rather than producing a partial result.

    `tables` holds the request's side tables, resolved once before the loop. `detail` is
    an OUT parameter carrying what only the operator knows — how many left rows a join
    dropped, how many partitions a window cut. An inner join that silently discarded 460
    of 500 rows looks exactly like a correct answer, and the count is already computed;
    refusing to surface it would be a rule-4 failure by omission. Ops with nothing to add
    leave it empty and their lineage stays byte-identical.

    Every key is read through the depth-aware `find_key` path — `json_string_field`,
    `json_raw_array`, `json_get_int`, `json_get_bool` — never `raw.find`. The frame layer
    re-serialises with keys SORTED, so `"expressions"` arrives before `"op"` and a naive
    search for `"op"` finds the one nested in `expressions.nodes`.

    A JSON extension literal anywhere in the op is rejected here, before any read, because
    `project` reaches the frozen `json_array_tokens` through
    `json_parse_float64_list("[" + root_token + "]")` — and `{"roots":[Infinity]}` splits
    into a token whose tokenisation runs off the end and ABORTS the worker. Same check, same
    function, same strength as the row path (rule 3: one definition, not a second looser
    copy); `run_query_execute_with_tables` applies it to the whole `ops` array as well,
    because `plan_hash` transcodes that text before the first op runs.
    """
    reject_non_json_literals(op_json, False)
    var op = json_string_field(op_json, "op")

    if op == "filter":
        var predicate = json_raw_object(op_json, "predicate")
        if len(predicate) == 0:
            raise Error("filter requires a 'predicate' object")
        var nodes = parse_nodes(predicate, batch.schema)
        var root = json_get_int(predicate, "root", len(nodes) - 1)
        var problem = plan_problem(batch.width(), nodes, root)
        if len(problem) > 0:
            raise Error("filter predicate: " + problem)
        return filter_rows(batch, nodes, root, strict)

    if op == "project":
        var expressions = json_raw_object(op_json, "expressions")
        if len(expressions) == 0:
            # No expressions: a plain column selection.
            var picked = _resolve_column_list(
                batch.schema, json_raw_array(op_json, "columns"), "projected"
            )
            return select_columns(batch, picked)
        var nodes = parse_nodes(expressions, batch.schema)
        var roots = List[Int]()
        var roots_json = json_raw_array(expressions, "roots")
        for token in json_raw_tokens(roots_json):
            var parsed_root = json_parse_float64_list("[" + token + "]")
            roots.append(Int(parsed_root[0]) if len(parsed_root) > 0 else -1)
        if len(roots) == 0:
            roots.append(len(nodes) - 1)
        for i in range(len(roots)):
            var problem = plan_problem(batch.width(), nodes, roots[i])
            if len(problem) > 0:
                raise Error("project expression " + String(i) + ": " + problem)
        var names = List[String]()
        var names_json = json_raw_array(op_json, "names")
        for token in json_raw_tokens(names_json):
            names.append(_unquote(token))
        return project(batch, nodes, roots, names, strict)

    if op == "select":
        var picked = _resolve_column_list(
            batch.schema, json_raw_array(op_json, "columns"), "selected"
        )
        return select_columns(batch, picked)

    if op == "sort":
        var nulls_last = json_get_bool(op_json, "nulls_last", True)
        var by_list = json_raw_array(op_json, "by")
        if len(by_list) > 0:
            var keys = _resolve_column_list(batch.schema, by_list, "sort")
            var desc_list = json_raw_array(op_json, "desc")
            var desc = List[Bool]()
            for token in json_raw_tokens(desc_list):
                desc.append(token == "true")
            return sort_rows_multi(batch, keys, desc, nulls_last)
        var key = _resolve_column(
            batch.schema, json_string_field(op_json, "by"), "sort"
        )
        return sort_rows(
            batch, key, json_get_bool(op_json, "desc", False), nulls_last
        )

    if op == "top_k":
        var key = _resolve_column(
            batch.schema, json_string_field(op_json, "by"), "top_k"
        )
        var k = json_get_int(op_json, "k", 0)
        return top_k_rows(
            batch,
            key,
            k,
            json_get_bool(op_json, "desc", True),
            json_get_bool(op_json, "nulls_last", True),
        )

    if op == "distinct":
        var keys = _resolve_column_list(
            batch.schema, json_raw_array(op_json, "columns"), "distinct"
        )
        return distinct_rows(batch, keys)

    if op == "limit":
        return limit_rows(
            batch,
            json_get_int(op_json, "offset", 0),
            json_get_int(op_json, "count", batch.n_rows),
        )

    if op == "aggregate":
        # One or many (value, agg) pairs — `_resolve_aggs` accepts the ORIGINAL
        # top-level `"value"`/`"agg"` shape (exactly one pair) or the additive
        # `"aggs":[{"value":...,"agg":...}, ...]` shape (one or more). Either way
        # the fused kernels below run the whole request in ONE grouped pass —
        # `group_by_many`'s entire point (aggregate.mojo) — rather than one
        # `aggregate` op per column, which is what made multiple aggregates cost
        # one full rescan each before this.
        var value_columns = List[Int]()
        var opcodes = List[Int]()
        var value_names = List[String]()
        _resolve_aggs(batch.schema, op_json, value_columns, opcodes, value_names)

        var by_array = json_raw_array(op_json, "by")
        if len(by_array) > 0:
            var key_columns = _resolve_column_list(batch.schema, by_array, "group")
            # Routed through the composed scan strategy (dense / packed / fused
            # radix — see query.composed), NOT re-implemented: at the SAME worker
            # count `group_by_multi` itself would pick, every route it can choose
            # is bit-identical to `group_by_many_parallel(..., workers)`, which is
            # bit-identical to `group_by_multi_parallel(..., workers)` in turn
            # (test_query_aggregate_fused's EQUIVALENCE suite, composite-key
            # case). A shape composed does not recognise falls through to
            # `group_by_many_parallel` itself — still that same equivalence, not
            # a third implementation. `value_columns`/`opcodes` are flat parallel
            # lists — one element for the original single-pair shape (unchanged
            # call), N for `"aggs"` (the new shape, same kernel).
            var workers = planned_workers(batch.n_rows, info.num_physical_cores())
            var multi = group_by_composed_parallel(
                batch, key_columns, value_columns, opcodes, workers
            )
            # Rebuild as a batch: one column per key, then one column per aggregate.
            var columns = List[Float64Array]()
            var names = List[String]()
            var dtypes = List[Int]()
            for c in range(len(key_columns)):
                var key_values = List[Float64]()
                var key_mask = List[Bool]()
                for g in range(multi.n_groups()):
                    key_values.append(multi.key_tuples[g * multi.key_width + c])
                    key_mask.append(True)
                columns.append(float64_with_nulls(key_values^, key_mask))
                names.append(batch.schema.name_at(key_columns[c]))
                dtypes.append(0)
            for j in range(len(value_names)):
                var agg_values = List[Float64]()
                var agg_mask = List[Bool]()
                for g in range(multi.n_groups()):
                    agg_values.append(multi.value_at(g, j))
                    agg_mask.append(multi.present_at(g, j))
                columns.append(float64_with_nulls(agg_values^, agg_mask))
                names.append(value_names[j])
                dtypes.append(0)
            # `n_groups()` reads 0 straight off `key_width <= 0` (a genuinely empty
            # `"by":[]`), but the whole-table aggregate that path answers with is
            # exactly 1 row — `multi.values` holds `n_aggs` slots for it, same as it
            # always has, so dividing back out the aggregate count recovers it
            # without special-casing width 0 a second time.
            var out_rows = multi.n_groups() if multi.key_width > 0 else (
                len(multi.values) // len(value_names) if len(value_names) > 0 else 0
            )
            return RecordBatch(Schema(names^, dtypes^), columns^, out_rows)

        var single_by = json_string_field(op_json, "by")
        if len(single_by) == 0:
            raise Error("aggregate requires 'by' (a column name or an array)")
        var key = _resolve_column(batch.schema, single_by, "group")
        # Same substitution as the multi-key branch above, at width 1: composed,
        # at the worker count `group_by` itself would use, is bit-identical to
        # `group_by_many_parallel(..., workers)` == `group_by_parallel(...,
        # workers)` (the fused suite's single-column EQUIVALENCE case).
        var single_key = List[Int]()
        single_key.append(key)
        var workers = planned_workers(batch.n_rows, info.num_physical_cores())
        var single_result = group_by_composed_parallel(
            batch, single_key, value_columns, opcodes, workers
        )
        return _many_single_to_batch(single_result, single_by, value_names^)

    if op == "join":
        return _apply_join(batch, op_json, tables, detail)

    if op == "union":
        return _apply_union(batch, op_json, tables, detail)

    if op == "window":
        return _apply_window(batch, op_json, detail)

    if len(op) == 0:
        # An empty op name means the op object could not be READ, not that the caller
        # sent an empty name. Echo what arrived so the difference is visible instead of
        # being reported as a bad plan.
        raise Error(
            "op object has no readable 'op' field; received: "
            + substring(op_json, 0, 120)
        )
    raise Error(
        "unknown op '"
        + op
        + "'; accepted: filter, project, select, sort, top_k, distinct, limit,"
        " aggregate, join, union, window"
    )


# ── join ──────────────────────────────────────────────────────────────────────


fn _apply_join(
    batch: RecordBatch, op_json: String, tables: NamedBatches, mut detail: String
) raises -> RecordBatch:
    """`{"op":"join","table":"customers","left_on":"customer_id","right_on":"id", ...}`.

    Wire keys: `table` (required, names a top-level `tables` entry); `on` (shorthand for
    equal names) or both `left_on` and `right_on`; `how` = inner | left | semi | anti
    (default inner); `method` = hash | merge (default hash); `prefix` for the right column
    names (default `<table>.`).

    ONE equality key per side. `hash_join_indices` takes one key column per side and a
    composite key would be a different algorithm, so the error says that rather than
    hinting at a workaround.

    `right`, `outer`, `full` and `cross` are rejected BY NAME. Mapping any of them onto
    `left` would answer a question the caller did not ask.

    Every kernel below is called UNCHANGED, and in its INDICES form rather than through
    the `hash_join` / `merge_join` convenience wrappers: the wrappers throw away the
    `JoinResult`, which is what carries the unmatched counts for lineage and what the
    output-size check needs. Do not "simplify" this back to the wrapper — it loses both.

    The left/streaming batch is never a right-hand side; there is no `"@left"`. A self-join
    supplies the rows as a named table.
    """
    var table_name = json_string_field(op_json, "table")
    if len(table_name) == 0:
        raise Error("join requires 'table'")
    var table_index = tables.index_of(table_name)
    if table_index < 0:
        raise Error(
            "join references table '"
            + table_name
            + "', which the plan does not supply (available: "
            + tables.describe()
            + ")"
        )
    # `ref`, not a copy: the table is borrowed for the join, not duplicated per op.
    ref right = tables.batches[table_index]

    var left_name = json_string_field(op_json, "left_on")
    var right_name = json_string_field(op_json, "right_on")
    var shared = json_string_field(op_json, "on")
    # A key PRESENT but not readable as a string is the composite case — `"on":["a","b"]`.
    # json_string_field reads a non-string as absent, so without this it would be reported
    # as a MISSING key, which sends the caller looking for the wrong mistake.
    if (
        (find_key(op_json, "left_on") >= 0 and len(left_name) == 0)
        or (find_key(op_json, "right_on") >= 0 and len(right_name) == 0)
        or (find_key(op_json, "on") >= 0 and len(shared) == 0)
    ):
        raise Error(
            "join keys must each be a single column name: 'on', or both 'left_on' and"
            " 'right_on'. A composite multi-column equality key is not implemented"
            " (hash_join_indices takes one key column per side)"
        )
    if len(left_name) == 0 or len(right_name) == 0:
        if len(shared) == 0:
            raise Error("join requires 'on', or both 'left_on' and 'right_on'")
        left_name = shared
        right_name = shared
    # Both sides resolve by NAME through the same path every other op uses, so an unknown
    # column is a typed error listing what IS available — never a crash, never a skip.
    var left_key = _resolve_column(batch.schema, left_name, "join left key")
    var right_key = _resolve_column(right.schema, right_name, "join right key")

    var how = json_string_field(op_json, "how")
    if len(how) == 0:
        how = "inner"
    var join_type = JOIN_INNER
    var semi = False
    var keep_matching = True
    if how == "inner":
        join_type = JOIN_INNER
    elif how == "left":
        join_type = JOIN_LEFT
    elif how == "semi":
        semi = True
        keep_matching = True
    elif how == "anti":
        semi = True
        keep_matching = False
    else:
        raise Error(
            "join 'how' must be inner, left, semi or anti; got '"
            + how
            + "' (right, outer, full and cross joins are not implemented)"
        )

    var method = json_string_field(op_json, "method")
    if len(method) == 0:
        method = "hash"
    if method != "hash" and method != "merge":
        raise Error("join 'method' must be hash or merge; got '" + method + "'")
    if semi and method == "merge":
        # There is no merge variant of semi_join_indices. Falling back to hash would hide
        # the mistake behind a right answer.
        raise Error(
            "join method 'merge' is not defined for how '" + how + "'"
        )

    if semi:
        # Semi and anti need no output-size pre-flight: one row out per row in, at most.
        var picked = semi_join_indices(batch, left_key, right, right_key, keep_matching)

        # The NULL COUNT is computed here and always stated, because `semi_join_indices`
        # SKIPS a null left key entirely (`join.mojo:449`: it does not match, and it is not
        # KNOWN not to match — SQL `NOT IN` semantics) and the old detail never mentioned
        # it. REPRODUCED: 500 left rows, 480 of them with a null join key, against a table
        # holding the one matching id, `how = "anti"` answered
        #   {"result":{"columns":["cid"],"rows":[]},
        #    "lineage":[{"op":"join","detail":"0 of 500 left rows unmatched"}]}
        # — an EMPTY result under a SUCCESS status, with a lineage line that reads as "all
        # 500 rows matched" for a dataset where 480 had no counterpart at all. Keeping the
        # NOT IN semantics is right (they are `join.mojo`'s documented contract); saying
        # nothing about them is the defect, so the count is reported whenever it is nonzero.
        # `join.is_matchable_key`, NOT `is_valid_at`: the count must be made by the SAME predicate
        # the join itself used, or the lineage describes a different set of rows than the one the
        # kernel actually discarded. A NaN key is present-but-unmatchable (NaN equals nothing, so it
        # cannot satisfy an equality join), so `is_valid_at` returns True for it and the row was
        # dropped from BOTH halves of a semi/anti join while being counted in neither — the same
        # misdescription as the original defect, one variant over. Reachable from ordinary finite
        # input: `1e300 * 1e300 - 1e300 * 1e300` projects a NaN key.
        var null_keys = 0
        for l in range(batch.n_rows):
            if not is_matchable_key(batch.columns[left_key], l):
                null_keys += 1

        var kept = String(len(picked)) + " of " + String(batch.n_rows) + " left rows "
        if keep_matching:
            kept += "matched"
        else:
            # NOT "unmatched": the number printed is the number of rows KEPT, and for anti a
            # null-key row is unmatched-but-dropped, so `len(picked)` is smaller than the
            # count of rows that did not match. Labelling it "unmatched" was a false
            # statement about exactly the rows this join discards.
            kept += "kept (unmatched, non-null key)"
        if null_keys > 0:
            kept += (
                ", "
                + String(null_keys)
                + " left rows had a null key and are in NEITHER half (SQL NOT IN"
                " semantics: a null key does not match, and is not known not to match)"
            )
        detail = kept
        return take(batch, picked)

    if method == "merge":
        # The SAME guard `merge_join_indices` applies internally, at the SAME strength and
        # through the SAME function — checked here only so the refusal precedes the
        # counting pass below. Rule 3: a duplicated guard that is weaker than the one it
        # duplicates reads as defence-in-depth while providing one arbitrary behaviour per
        # call site, so this must never become a second, looser sortedness test.
        if not is_sorted_ascending(batch, left_key):
            raise Error(
                "join method 'merge' requires the left input sorted ascending on '"
                + left_name
                + "' with nulls last; add a sort op before this join"
            )
        if not is_sorted_ascending(right, right_key):
            raise Error(
                "join method 'merge' requires table '"
                + table_name
                + "' sorted ascending on '"
                + right_name
                + "' with nulls last; a plan cannot sort a side table, so supply it"
                " sorted or use method 'hash'"
            )

    # Output-size pre-flight. THE unbounded path: 30,000 x 30,000 rows sharing one key is
    # a ~1 MB request asking for 9e8 output rows, and `hash_join_indices` allocates two
    # Ints per OUTPUT row — so the blowup happens before there is any result to inspect.
    # The 64 MB frame cap bounds the INPUT and says nothing about the product.
    #
    # Fast path: when an UPPER BOUND on the output is itself within both caps, the bound
    # alone proves safety and no counting pass runs. That is every small join. Otherwise
    # count exactly — the error then reports the real number rather than an upper bound,
    # and truncating instead of raising would be a wrong answer wearing a success status.
    #
    # The product of the two row counts is NOT that upper bound for a LEFT join: a left
    # join against an EMPTY table has a product of zero and still emits one row per left
    # row, so the product would prove nothing about the widest case there is (every left
    # row, every left column, plus a null column per right column).
    var out_columns = batch.width() + right.width()
    # WIDTH. `join` is the one operator that can DOUBLE the width — it emits every left
    # column plus every right column — and it was the one operator not checking it, while
    # `_apply_window` bounds its single appended column against the same ceiling.
    if out_columns > MAX_COLUMNS:
        raise Error(
            "join would produce "
            + String(out_columns)
            + " columns ("
            + String(batch.width())
            + " left plus "
            + String(right.width())
            + " right); at most "
            + String(MAX_COLUMNS)
            + " -- select fewer columns on either side first"
        )
    var row_bound = _saturating_product(batch.n_rows, right.n_rows)
    if join_type == JOIN_LEFT:
        row_bound += batch.n_rows
    if (
        row_bound > MAX_JOIN_OUTPUT_ROWS
        or _saturating_product(row_bound, out_columns) > MAX_MATERIALIZED_CELLS
        or _serialized_bytes_floor(row_bound, out_columns) > MAX_RESPONSE_BYTES
    ):
        var out_rows = join_output_rows(batch, left_key, right, right_key, join_type)
        if out_rows > MAX_JOIN_OUTPUT_ROWS:
            raise Error(
                "join would produce "
                + String(out_rows)
                + " rows; at most "
                + String(MAX_JOIN_OUTPUT_ROWS)
            )
        var out_cells = _saturating_product(out_rows, out_columns)
        if out_cells > MAX_MATERIALIZED_CELLS:
            raise Error(
                "join would produce "
                + String(out_cells)
                + " cells; at most "
                + String(MAX_MATERIALIZED_CELLS)
            )
        # BYTES, the bound none of the above is. Every check so far bounds an ALLOCATION;
        # the transport bounds the FRAME at 64 MB (see MAX_RESPONSE_BYTES), and a join is
        # the first op whose response can be ~1000x its request, so a plan inside every
        # engine bound still produces a frame that cannot be sent. Refused HERE, before
        # `materialize` runs, because a response that cannot be delivered must not be
        # computed. The floor (4 bytes per cell) is used rather than an estimate, so no
        # deliverable response is ever refused: if the SHORTEST possible text is over the
        # cap, no data makes it fit.
        var floor_bytes = _serialized_bytes_floor(out_rows, out_columns)
        if floor_bytes > MAX_RESPONSE_BYTES:
            raise Error(
                "join would produce "
                + String(out_rows)
                + " rows x "
                + String(out_columns)
                + " columns, which serialise to at least "
                + String(floor_bytes)
                + " bytes; a response may hold at most "
                + String(MAX_RESPONSE_BYTES)
                + " (the transport frame cap is 64 MB) -- reduce the result with select,"
                " aggregate, limit or top_k"
            )

    var prefix = json_string_field(op_json, "prefix")
    if len(prefix) == 0:
        # An empty prefix is not expressible: json_string_field cannot tell absent from
        # "", and a caller cannot ask for a name collision anyway.
        prefix = String("")
        prefix += table_name
        prefix += "."
    # Every name this join is about to emit, checked against the left schema AND against
    # each other. The right-vs-right half was missing, and it is reachable without any
    # prefix trickery: `tables:[{"name":"t","columns":["id","id"],"rows":[[1,99]]}]` joined
    # on `g` emitted TWO columns called `t.id`, and `Schema.index_of` returns the FIRST
    # match, so every later op resolving that name silently read column 1 of 2 — the hazard
    # `join.mojo`'s `materialize` docstring names explicitly. One entry plus two distinct
    # prefixes is how the same table is joined twice; two columns of one name is a mistake.
    var emitted = List[String]()
    for c in range(right.width()):
        # Built by += into an owned String. Never a Span over a local: that form aliases
        # memory that dies on return, survives the JIT, and in the optimized worker made
        # `filter` crash and `project` read a garbage op name.
        var candidate = String("")
        candidate += prefix
        candidate += right.schema.name_at(c)
        if batch.schema.index_of(candidate) >= 0:
            raise Error(
                "join produces two columns named '"
                + candidate
                + "'; give this join a distinct 'prefix'"
            )
        for e in range(len(emitted)):
            if emitted[e] == candidate:
                raise Error(
                    "join produces two columns named '"
                    + candidate
                    + "': table '"
                    + table_name
                    + "' declares column "
                    + String(e)
                    + " and column "
                    + String(c)
                    + " under the same name, and no 'prefix' can separate them -- rename"
                    " one of them in the table's 'columns'"
                )
        emitted.append(candidate)

    var result: JoinResult
    if method == "merge":
        result = merge_join_indices(batch, left_key, right, right_key, join_type)
    else:
        result = hash_join_indices(batch, left_key, right, right_key, join_type)
    detail = result.describe()
    return materialize(batch, right, result, prefix)


# ── union ─────────────────────────────────────────────────────────────────────


fn _concat_float64(a: Float64Array, b: Float64Array) -> Float64Array:
    """`a`'s rows then `b`'s, preserving each row's presence — UNION ALL's one
    primitive. `values_list`/`mask_list` copy (there is no in-place append on the
    shared `ArcPointer` buffer a slice reads from — see `columnar.array`), so this
    is O(len(a) + len(b)), the same order every other row-materializing op here
    already pays (`take_column`, `materialize`).
    """
    var values = a.values_list()
    var mask = a.mask_list()
    var b_values = b.values_list()
    var b_mask = b.mask_list()
    for i in range(len(b_values)):
        values.append(b_values[i])
        mask.append(b_mask[i])
    return float64_with_nulls(values^, mask)


fn _apply_union(
    batch: RecordBatch, op_json: String, tables: NamedBatches, mut detail: String
) raises -> RecordBatch:
    """`{"op":"union","tables":["sales_web","sales_catalog"]}` — UNION ALL: every
    row of the running batch, then every row of each named table in the given
    order, no deduplication. This is the minimum TPC-DS needs (it unions sales
    channels, never deduplicating) and the query plane's first UNION of any kind
    — see the discovery-sweep synthesis plan, section 2.3 / TPC-DS note in section 3.

    `tables` is plural and an ARRAY, unlike join's singular `table`: a union has no
    upper bound on operand count the way a join's two-sided key does, and chaining
    N `union` ops for N tables would repeat the schema-matching walk below N times
    over an already-growing batch instead of once over the ORIGINAL operands.

    Side tables, not prior pipeline stages, are how "another query's output"
    reaches this op — exactly the mechanism `join` already uses for the same
    reason (`plan_hash` covers `ops`, not table bodies; a table is parsed once,
    not once per reference). A caller wanting to union two DIFFERENT op-chains'
    results runs each chain as its own `query_execute` call, then hands the
    materialized result back as a named table here.

    Columns are matched BY NAME against the running batch's schema, not by
    position: an operand supplying the same columns in a different order still
    unions correctly, and a genuinely missing column is refused by name rather
    than silently zipping column `i` of one schema against column `i` of another
    (the mistake a positional union would make silently). Column COUNT must still
    match — an operand with an extra or a missing column cannot be reordered into
    correctness and is refused before any row is read.

    No `how` (this is UNION ALL, not the relational union operator most SQL
    engines default to) and no de-duplication: DISTINCT is already its own op,
    stackable after this one, and running it unconditionally here would charge
    every unique-by-construction union (the common case — TPC-DS's channel
    unions never need it) for a scan it does not want.
    """
    var names_array = json_raw_array(op_json, "tables")
    var operand_names = List[String]()
    for token in json_raw_tokens(names_array):
        operand_names.append(_unquote(token))
    if len(operand_names) == 0:
        raise Error("union requires 'tables' (a non-empty array of table names)")

    # Preflight the ROW count — union cannot blow up the way a join's key product
    # can (every operand row appears exactly once), but a long chain of large
    # tables can still exceed MAX_ROWS/MAX_MATERIALIZED_CELLS/the frame cap, and
    # that must be refused before any column is copied, not after.
    var out_rows = batch.n_rows
    for i in range(len(operand_names)):
        var name = operand_names[i]
        var table_index = tables.index_of(name)
        if table_index < 0:
            raise Error(
                "union references table '"
                + name
                + "', which the plan does not supply (available: "
                + tables.describe()
                + ")"
            )
        ref operand = tables.batches[table_index]
        if operand.width() != batch.width():
            raise Error(
                "union operand '"
                + name
                + "' has "
                + String(operand.width())
                + " columns; the batch being unioned onto has "
                + String(batch.width())
                + " -- every union operand must have the SAME columns (select"
                " first to drop or reorder any that differ)"
            )
        for c in range(batch.width()):
            var col_name = batch.schema.name_at(c)
            if operand.schema.index_of(col_name) < 0:
                raise Error(
                    "union operand '"
                    + name
                    + "' has no column '"
                    + col_name
                    + "' (available: "
                    + operand.schema.describe()
                    + ") -- union matches columns BY NAME, not position"
                )
        out_rows = _saturating_sum(out_rows, operand.n_rows)

    if out_rows > MAX_ROWS:
        raise Error(
            "union would produce " + String(out_rows) + " rows; at most " + String(
                MAX_ROWS
            )
        )
    var out_cells = _saturating_product(out_rows, batch.width())
    if out_cells > MAX_MATERIALIZED_CELLS:
        raise Error(
            "union would produce "
            + String(out_cells)
            + " cells; at most "
            + String(MAX_MATERIALIZED_CELLS)
        )
    var floor_bytes = _serialized_bytes_floor(out_rows, batch.width())
    if floor_bytes > MAX_RESPONSE_BYTES:
        raise Error(
            "union would produce "
            + String(out_rows)
            + " rows x "
            + String(batch.width())
            + " columns, which serialise to at least "
            + String(floor_bytes)
            + " bytes; a response may hold at most "
            + String(MAX_RESPONSE_BYTES)
            + " (the transport frame cap is 64 MB) -- reduce the result with select,"
            " aggregate, limit or top_k"
        )

    var out_columns = List[Float64Array]()
    for c in range(batch.width()):
        out_columns.append(batch.column(c))
    var operands_used = 0
    var total_rows = batch.n_rows
    for i in range(len(operand_names)):
        var table_index = tables.index_of(operand_names[i])
        ref operand = tables.batches[table_index]
        for c in range(batch.width()):
            var col_name = batch.schema.name_at(c)
            var operand_col = operand.schema.index_of(col_name)
            out_columns[c] = _concat_float64(out_columns[c], operand.column(operand_col))
        operands_used += 1
        total_rows += operand.n_rows

    var names = List[String]()
    var dtypes = List[Int]()
    for c in range(batch.schema.width()):
        names.append(batch.schema.names[c])
        dtypes.append(batch.schema.dtypes[c])

    detail = (
        String(total_rows)
        + " rows after UNION ALL over "
        + String(operands_used)
        + " table(s) ("
        + String(batch.n_rows)
        + " running + "
        + String(total_rows - batch.n_rows)
        + " unioned)"
    )
    return RecordBatch(Schema(names^, dtypes^), out_columns^, total_rows)


# ── window ────────────────────────────────────────────────────────────────────


fn _window_fn_is_known(name: String) -> Bool:
    return (
        name == "row_number"
        or name == "rank"
        or name == "dense_rank"
        or name == "lag"
        or name == "lead"
        or name == "cumulative"
        or name == "framed"
        or name == "partition_total"
    )


fn _apply_window(
    batch: RecordBatch, op_json: String, mut detail: String
) raises -> RecordBatch:
    """`{"op":"window","fn":"rank","partition_by":[...],"order_by":[...],"as":"..."}`.

    One op with a `fn` selector, a REQUIRED `as` output name, and the result APPENDED as
    one column with row order preserved.

    `lag_lead` is deliberately NOT a wire name: a signed offset is a worse API than two
    names, because `{"fn":"lag","offset":-1}` would silently compute a lead.
    `FRAME_UNBOUNDED` (-1) likewise never appears on the wire — `"fn":"cumulative"` IS the
    unbounded frame, so a stray -1 in `preceding` cannot turn a rolling frame into a
    cumulative one.

    `partition_by` and `order_by` are arrays of column NAMES, resolved by the same
    `_resolve_column_list` every other op uses: a reordered header must not retarget the
    plan. `desc` applies to the ORDER keys only — `partition_rows` sorts the partition keys
    ascending internally, which is what that parameter means.

    An empty `partition_by` is legal: one partition over everything, which is what
    `OVER (ORDER BY ...)` means. A null partition key forms its OWN single partition,
    because `partition_rows` cuts on a presence change — unlike `aggregate`, where a null
    group key is counted separately.

    Every gate below exists because the kernel would otherwise answer with nulls or an
    arbitrary key under a SUCCESS status, and the kernel semantics are pinned by existing
    assertions and must not change. The gate belongs here, at the wire.
    """
    var window_fn = json_string_field(op_json, "fn")
    if len(window_fn) == 0:
        raise Error("window requires 'fn'")
    if not _window_fn_is_known(window_fn):
        raise Error(
            "window 'fn' must be row_number, rank, dense_rank, lag, lead, cumulative,"
            " framed or partition_total; got '"
            + window_fn
            + "'"
        )

    # `as` is REQUIRED. Every default is either ambiguous (two different frames over
    # `amount` both wanting `sum_amount`) or a collision, and Schema.index_of returns the
    # first match so a collision SILENTLY shadows. Requiring it also puts the output name
    # in `ops`, hence in plan_hash — correct, since two plans producing differently-named
    # columns produce different results.
    var output_name = json_string_field(op_json, "as")
    if len(output_name) == 0:
        raise Error("window requires 'as' (the output column name)")
    if batch.schema.index_of(output_name) >= 0:
        raise Error(
            "window output column '"
            + output_name
            + "' already exists in the batch (available: "
            + batch.schema.describe()
            + ")"
        )
    if batch.width() + 1 > MAX_COLUMNS:
        raise Error(
            "window would append a "
            + String(batch.width() + 1)
            + "th column; at most "
            + String(MAX_COLUMNS)
        )
    if batch.n_rows > MAX_WINDOW_ROWS:
        raise Error(
            "window over "
            + String(batch.n_rows)
            + " rows; at most "
            + String(MAX_WINDOW_ROWS)
            + " (the partition sort is quadratic in rows -- reduce with filter,"
            " aggregate or limit first)"
        )

    var partition_array = json_raw_array(op_json, "partition_by")
    if find_key(op_json, "partition_by") >= 0 and len(partition_array) == 0:
        # `json_raw_array` reads a non-array as absent, and absent means ONE partition over
        # everything — so `"partition_by":"region"` would answer a different question under
        # a success status. `[]` is explicitly legal and reaches here as "[]", not "".
        raise Error("window 'partition_by' must be an array of column names")
    var partition_columns = _resolve_column_list(
        batch.schema, partition_array, "window partition"
    )
    var order_array = json_raw_array(op_json, "order_by")
    var order_columns = _resolve_column_list(
        batch.schema, order_array, "window order"
    )

    # `partition_total` is order-independent by definition, so an order spec there is
    # present-and-ignored — documented rather than rejected, so one spec can be shared
    # across several window ops. Every other fn NEEDS an order: a running total with no
    # order is not a defined answer (it is partition_total in disguise).
    if window_fn != "partition_total" and len(order_columns) == 0:
        raise Error(
            "window fn '" + window_fn + "' requires a non-empty 'order_by'"
        )
    if window_fn == "rank" or window_fn == "dense_rank":
        # `_rank_column` defines a tie by that ONE column; silently taking the first of
        # several would report ties that are not ties.
        if len(order_columns) != 1:
            raise Error(
                "window fn '"
                + window_fn
                + "' requires exactly one 'order_by' column; got "
                + String(len(order_columns))
            )

    var descending = List[Bool]()
    if find_key(op_json, "desc") >= 0:
        # `partition_rows` reads `descending[i] if i < len(descending) else False`, so a
        # SHORT list silently leaves the trailing keys ascending — a different ordering,
        # hence different ranks. And `json_raw_array` returns "" for a non-array, so a
        # bare `"desc":false` would otherwise be silently ignored.
        var desc_tokens = json_raw_tokens(json_raw_array(op_json, "desc"))
        if len(desc_tokens) != len(order_columns):
            raise Error(
                "window 'desc' must be an array of one boolean per 'order_by' column ("
                + String(len(order_columns))
                + " expected, "
                + String(len(desc_tokens))
                + " given)"
            )
        for i in range(len(desc_tokens)):
            descending.append(desc_tokens[i] == "true")
    else:
        for _ in range(len(order_columns)):
            descending.append(False)

    var needs_value = (
        window_fn == "lag"
        or window_fn == "lead"
        or window_fn == "cumulative"
        or window_fn == "framed"
        or window_fn == "partition_total"
    )
    var value_name = json_string_field(op_json, "value")
    var value_column = 0
    if needs_value:
        if len(value_name) == 0:
            raise Error("window fn '" + window_fn + "' requires 'value'")
        value_column = _resolve_column(batch.schema, value_name, "window value")
    elif len(value_name) > 0:
        # Rejected rather than ignored: a caller who thinks they are computing something
        # over `amount` is told they are not.
        raise Error("window fn '" + window_fn + "' takes no 'value'")

    var opcode = AGG_SUM
    if window_fn == "cumulative" or window_fn == "framed" or window_fn == (
        "partition_total"
    ):
        var agg_token = json_string_field(op_json, "agg")
        opcode = parse_aggregation(agg_token)
        if (
            opcode != AGG_SUM
            and opcode != AGG_AVG
            and opcode != AGG_MIN
            and opcode != AGG_MAX
            and opcode != AGG_COUNT
        ):
            # `parse_aggregation` also accepts var/std/median, but `framed_aggregate`
            # falls through its `elif seen:` chain without matching and leaves the mask
            # False — so `"agg":"var"` would return a FULL COLUMN OF NULLS carrying a
            # SUCCESS status. Absent everywhere, reported as success, is rule 4 inverted.
            raise Error(
                "window 'agg' must be sum, avg, min, max or count; got '"
                + agg_token
                + "' (var, std and median are not defined over a window frame here)"
            )

    var offset = 1
    if window_fn == "lag" or window_fn == "lead":
        offset = json_get_int(op_json, "offset", 1)
        if offset < 1:
            raise Error("window fn '" + window_fn + "' requires 'offset' >= 1")

    var preceding = 0
    if window_fn == "framed":
        preceding = json_get_int(op_json, "preceding", -1)
        if preceding < 0:
            raise Error(
                "window fn 'framed' requires 'preceding' >= 0; use fn 'cumulative' for"
                " an unbounded frame"
            )

    # ── TOTAL WORK, not one factor of it ─────────────────────────────────────
    # The row cap above bounds `n`. It does NOT bound `len(keys)`, and
    # `sort_indices_multi` runs one O(n^2) stable insertion pass PER KEY, so the sort alone
    # costs `len(keys) x n^2`. REPRODUCED: 20,000 rows with `partition_by = ["a","b"] * 128`
    # — a 497 KB payload, every value inside every documented bound — hung 60.6 s until the
    # worker was killed, which is the same outcome as an abort for the caller.
    #
    # `cumulative` and `framed` add a SECOND quadratic term: `framed_aggregate` re-walks the
    # frame for every row, and its per-step constant is larger than a comparison because it
    # runs the `numeric.contract` aggregate updates. So the worst operator here is not the
    # one the row cap was measured on. Both terms are counted, in units of one key-row
    # comparison, and weighted x2 for the frame walk. See MAX_WINDOW_WORK.
    var sort_keys = len(partition_columns) + len(order_columns)
    if sort_keys < 1:
        sort_keys = 1  # partition_rows always runs at least one ordering pass
    var square = _saturating_product(batch.n_rows, batch.n_rows)
    var work = _saturating_product(sort_keys, square)
    # `_saturating_sum`, not `+`: both terms are already clamped products, so a plain add
    # could wrap, compare small, and let the refusal through.
    if window_fn == "cumulative":
        # n^2/2 frame steps, x2 for the heavier per-step constant.
        work = _saturating_sum(work, square)
    elif window_fn == "framed":
        var span = preceding + 1
        if span > batch.n_rows:
            span = batch.n_rows
        work = _saturating_sum(
            work, _saturating_product(2, _saturating_product(batch.n_rows, span))
        )
    if work > MAX_WINDOW_WORK:
        raise Error(
            "window '"
            + window_fn
            + "' over "
            + String(batch.n_rows)
            + " rows with "
            + String(sort_keys)
            + " ordering keys would run "
            + String(work)
            + " key-row comparisons; at most "
            + String(MAX_WINDOW_WORK)
            + " (the partition sort is one quadratic pass PER partition_by/order_by key,"
            " and cumulative/framed re-walk the frame per row -- use fewer keys, or reduce"
            " rows with filter, aggregate or limit first)"
        )

    var nulls_last = json_get_bool(op_json, "nulls_last", True)
    var partitions = partition_rows(
        batch, partition_columns, order_columns, descending, nulls_last
    )

    var window_column: Float64Array
    if window_fn == "row_number":
        window_column = row_number(batch, partitions)
    elif window_fn == "rank":
        window_column = rank(batch, partitions, order_columns[0])
    elif window_fn == "dense_rank":
        window_column = dense_rank(batch, partitions, order_columns[0])
    elif window_fn == "lag":
        window_column = lag_lead(batch, partitions, value_column, -offset)
    elif window_fn == "lead":
        window_column = lag_lead(batch, partitions, value_column, offset)
    elif window_fn == "cumulative":
        window_column = cumulative(batch, partitions, value_column, opcode)
    elif window_fn == "framed":
        window_column = framed_aggregate(
            batch, partitions, value_column, opcode, preceding
        )
    else:
        window_column = partition_total(batch, partitions, value_column, opcode)

    # `window.mojo` guarantees the returned array is batch.n_rows long and indexed by
    # ORIGINAL row, so the whole conversion is an append and ROW ORDER IS UNCHANGED.
    # `describe_partitions` is O(partitions); `Partitions.partition_of` is
    # O(partitions x rows) and documented as being for tests and lineage only, so it is
    # never called on this path.
    var columns = List[Float64Array]()
    var names = List[String]()
    var dtypes = List[Int]()
    for c in range(batch.width()):
        columns.append(batch.column(c))
        names.append(batch.schema.name_at(c))
        dtypes.append(batch.schema.dtype_at(c))
    columns.append(window_column^)
    names.append(output_name)
    dtypes.append(0)
    detail = describe_partitions(partitions)
    return RecordBatch(Schema(names^, dtypes^), columns^, batch.n_rows)


fn plan_hash(ops_json: String) -> String:
    """SHA-256 over the canonically-encoded ops array.

    Over VALUES, not JSON text: key order and whitespace do not change it, a threshold
    does. Same rule as `algenta_runtime.pipeline.plan_hash`.
    """
    try:
        return hash_canonical_bytes(transcode(ops_json))
    except:
        # A plan that will not transcode is a plan that will not run; the caller sees
        # the real error from execution. An empty hash is honest about not identifying
        # anything.
        return ""


fn _cell_text(value: Float64) -> String:
    """One cell's wire text. A value that is not a real number is ABSENT, never `inf`.

    THE POLICY, stated once and applied at the single point where a Float64 reaches the
    wire: a non-finite result is reported as `null` — absent — and counted, never emitted as
    a bare token. `String(inf)` is `"inf"` and `String(nan)` is `"nan"`, and NEITHER IS
    JSON: no JSON parser accepts them, so `json.loads` on the response raises and the SDK
    reports a transport failure for a response the engine considered successful.

    REACHED FROM ORDINARY FINITE INPUT — this is not a "who would send inf" case. Rows
    `[[1, 1e308], [1, 1e308]]` with `partition_total` / `agg = sum` overflow to +inf inside
    the aggregate and produced `"tot":inf`. `strict` cannot prevent it: `strict` governs
    EXPRESSION evaluation (`filter` and `project`), and an aggregate is neither.

    Absent rather than a typed error, deliberately, and this is the rule-4 reading: the sum
    of two finite numbers whose true value is not representable HAS no Float64 answer, which
    is exactly what "absent" means — while failing the whole plan would throw away the other
    columns and rows, which do have answers. The count is surfaced as `non_finite_cells` in
    the response so the absence is never silent, and the response is otherwise byte-identical
    to before when nothing overflowed.
    """
    if isnan(value) or isinf(value):
        return String("null")
    return String(value)


fn _serialized_bytes_exact(batch: RecordBatch) -> Int:
    """Exactly the byte length `_batch_to_json` will return, WITHOUT building it.

    Mirrors the emitter below term for term, so the two cannot disagree: the header's quoted
    escaped names, then per row two brackets, then per cell its text and one separator. Used
    only when `_serialized_bytes_ceiling` cannot already prove the response fits, so an
    ordinary response never pays for this pass.
    """
    var total = 12 + 10 + 2  # '{"columns":[' + '],"rows":[' + ']}'
    for c in range(batch.width()):
        if c > 0:
            total += 1
        total += 2 + len(_json_escape(batch.schema.name_at(c)))
    for r in range(batch.n_rows):
        if r > 0:
            total += 1
        total += 2
        for c in range(batch.width()):
            if c > 0:
                total += 1
            ref column = batch.columns[c]
            if column.is_valid_at(r):
                total += len(_cell_text(column.get(r)))
            else:
                total += 4  # null
    return total


fn _batch_to_json(batch: RecordBatch, mut non_finite: Int) -> String:
    """Columns out, `null` for absent — the mirror of the row-major input.

    `non_finite` counts the cells whose value was not a real number and is therefore
    reported absent; see `_cell_text`. An OUT parameter rather than a silent drop, because a
    response that quietly replaced an overflowed sum with `null` would be indistinguishable
    from one whose input was missing.
    """
    var out = String('{"columns":[')
    for c in range(batch.width()):
        if c > 0:
            out += ","
        out += '"' + _json_escape(batch.schema.name_at(c)) + '"'
    out += '],"rows":['
    for r in range(batch.n_rows):
        if r > 0:
            out += ","
        out += "["
        for c in range(batch.width()):
            if c > 0:
                out += ","
            ref column = batch.columns[c]
            if column.is_valid_at(r):
                var value = column.get(r)
                if isnan(value) or isinf(value):
                    non_finite += 1
                out += _cell_text(value)
            else:
                out += "null"
        out += "]"
    out += "]}"
    return out


fn run_query_execute(raw: String, rows_json: String) -> String:
    """Execute a whole query plan with no side tables.

    A two-argument wrapper, kept because every existing caller — the hand-written suite
    and `bench_query_plane.py` — uses this signature. Adding the table lists in place
    would have forced pinned assertions to move.
    """
    var no_rows = List[String]()
    var no_headers = List[String]()
    return run_query_execute_with_tables(raw, rows_json, no_rows, no_headers)


fn run_query_execute_with_tables(
    raw: String,
    rows_json: String,
    table_rows: List[String],
    table_headers: List[String],
) -> String:
    """Execute a whole query plan and return columns, lineage and a plan hash.

    `rows_json` is supplied by the caller so `main.mojo` can substitute a resident
    dataset's rows for an inline array without this module knowing about the registry.
    `table_rows` / `table_headers` are the same substitution for each `tables` entry,
    positionally — see `table_dataset_handles`.

    Side tables are resolved ONCE, here, before the op loop. So a table joined by twenty
    ops is parsed once and shipped once: payload is O(1) in ops, and O(1) in requests too
    when the entry uses the `dataset` form.
    """
    var ops = json_raw_array(raw, "ops")
    # BEFORE `plan_hash`, which hands the ops text to the frozen `canonical.from_json`
    # transcoder, and before any op is read. A JSON extension literal in the ops array is
    # rejected as a plan error rather than reaching a frozen parser that can abort the
    # process. `apply_op_detailed` applies the same check, through the same function, to each
    # op it is handed directly.
    var ops_problem = json_literal_problem(ops, False)
    if len(ops_problem) > 0:
        return _plan_error("invalid_arguments", "the 'ops' array: " + ops_problem)
    var op_tokens = List[String]()
    if len(ops) > 0:
        op_tokens = json_raw_tokens(ops)
    var op_count = len(op_tokens)
    if op_count > MAX_OPS:
        return _plan_error(
            "too_many_ops",
            "a plan may hold at most " + String(MAX_OPS) + " ops; got " + String(op_count),
        )

    var batch: RecordBatch
    try:
        batch = build_batch(raw, rows_json)
    except e:
        return _plan_error("invalid_arguments", String(e))

    # Table parsing and its limits are `invalid_arguments`, the code already in place, not
    # a new top-level code: a new code obliges docs regeneration and MEANINGS updates, and
    # nothing here is a failure a client would branch on.
    var tables: NamedBatches
    try:
        tables = parse_named_tables(raw, table_rows, table_headers)
    except e:
        return _plan_error("invalid_arguments", _json_escape(String(e)))

    var strict = json_get_bool(raw, "strict", False)
    var lineage = String("[")
    var hash_value = plan_hash(ops) if len(ops) > 0 else ""

    for i in range(op_count):
        ref op_json = op_tokens[i]
        var name = json_string_field(op_json, "op")
        var detail = String("")
        var next_batch: RecordBatch
        try:
            next_batch = apply_op_detailed(batch, op_json, strict, tables, detail)
        except e:
            return (
                '{"error":"query_op_failed: '
                + _json_escape(String(e))
                + '","error_code":"query_op_failed","error_message":"op '
                + String(i)
                + " ("
                + _json_escape(name)
                + "): "
                + _json_escape(String(e))
                + '","op_index":'
                + String(i)
                + ',"plan_hash":"'
                + hash_value
                + '"}'
            )
        batch = next_batch^
        if i > 0:
            lineage += ","
        lineage += (
            '{"index":'
            + String(i)
            + ',"op":"'
            + _json_escape(name)
            + '","shape":"'
            + describe_batch_shape(batch)
            + '"'
        )
        # Omitted when empty, so the eight ops that carry no detail emit byte-identical
        # lineage to before.
        if len(detail) > 0:
            lineage += ',"detail":"' + _json_escape(detail) + '"'
        lineage += "}"
    lineage += "]"

    # ── the response must FIT THE FRAME, and that is checked before it is built ──
    # Every bound in this module bounds an allocation; the transport bounds the FRAME at
    # 64 MB on both send and receive (see MAX_RESPONSE_BYTES). `_apply_join` refuses a join
    # whose output cannot fit before materialising it, but a join is not the only way to
    # arrive here oversized — a plain `select` over a million wide rows does it with no join
    # at all — so the whole response is bounded here too.
    #
    # Fast path first: when even the widest possible text fits, nothing is measured. Only if
    # the ceiling fails is the exact length computed, which is a scan with no big allocation
    # — so a response that cannot be delivered is never BUILT, and no deliverable response is
    # ever refused because a bound was pessimistic.
    if _serialized_bytes_ceiling(batch.n_rows, batch.width()) > MAX_RESPONSE_BYTES:
        var exact = _serialized_bytes_exact(batch)
        if exact + len(lineage) > MAX_RESPONSE_BYTES:
            return _plan_error(
                "result_too_large",
                "the result is "
                + String(batch.n_rows)
                + " rows x "
                + String(batch.width())
                + " columns, which serialises to "
                + String(exact)
                + " bytes; a response may hold at most "
                + String(MAX_RESPONSE_BYTES)
                + " (the transport frame cap is 64 MB) -- reduce the result with select,"
                " aggregate, limit or top_k. The plan itself was accepted and ran; only"
                " the response cannot be delivered",
            )

    var non_finite = 0
    var body = _batch_to_json(batch, non_finite)
    var out = String('{"result":')
    out += body
    out += ',"lineage":'
    out += lineage
    out += ',"ops":'
    out += String(op_count)
    out += ',"rows":'
    out += String(batch.n_rows)
    # Emitted ONLY when nonzero, so every response that overflowed nothing is byte-identical
    # to before. See `_cell_text`: a non-finite value is absent on the wire, and this is what
    # keeps that absence from being silent.
    if non_finite > 0:
        out += ',"non_finite_cells":'
        out += String(non_finite)
    out += ',"plan_hash":"'
    out += hash_value
    out += '"}'
    return out
