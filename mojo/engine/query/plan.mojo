"""
query.plan — parse and run a whole query plan in one frame. Zero Python.

This is the reachability half of the query plane. `executor`, `join`, `window` and
`aggregate` are Mojo-only; nothing outside the worker can call them until a plan can
cross the frame boundary. That plan is JSON in, columns out, one dispatch.

Wire format
-----------
    {"type":"query_execute",
     "columns":["region","amount"],
     "rows":[[1,10],[2,50],[1,30]],          // or "dataset":"@ds_1"
     "ops":[
       {"op":"filter","predicate":{"nodes":[...],"root":2}},
       {"op":"aggregate","by":"region","value":"amount","agg":"sum"},
       {"op":"sort","by":"amount","desc":true,"nulls_last":true},
       {"op":"top_k","by":"amount","k":10,"desc":true}
     ],
     "strict":false}

Rows are row-major, matching how a caller already holds tabular data, and are
transposed once on ingest. Columns are addressed by NAME in a plan and resolved to
indices once, so a plan does not silently target the wrong column when the caller
reorders its `columns` list.

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
"""
from json.parser import (
    find_key,
    json_array_len,
    json_array_tokens,
    json_get_array,
    json_get_bool,
    json_get_int,
    json_get_object,
    json_parse_float64_list,
)

from canonical.from_json import transcode
from canonical.hash import hash_canonical_bytes
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from numeric.contract import (
    AGG_UNKNOWN,
    aggregation_token,
    parse_aggregation,
    unknown_aggregation_error,
)
from query.aggregate import GroupedResult, group_by, group_by_multi
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
from types import ExprNode

# Bounds. Generous for real plans, but a single-threaded worker must not be pinnable by
# one malformed frame.
comptime MAX_OPS: Int = 64
comptime MAX_COLUMNS: Int = 512
comptime MAX_ROWS: Int = 1_000_000


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


# ── ingest ────────────────────────────────────────────────────────────────────


fn parse_column_names(raw: String) raises -> List[String]:
    """The `columns` array as a name list."""
    var names = List[String]()
    var array = json_get_array(raw, "columns")
    if len(array) == 0:
        return names^
    for token in json_array_tokens(array):
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
    """
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
    var array = json_get_array(expr_json, "nodes")
    if len(array) == 0:
        return nodes^
    var tokens = json_array_tokens(array)
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
    for token in json_array_tokens(array):
        out.append(_resolve_column(schema, _unquote(token), what))
    return out^


# ── execution ─────────────────────────────────────────────────────────────────


fn _grouped_to_batch(result: GroupedResult, key_name: String, value_name: String) -> RecordBatch:
    """A GroupedResult as a two-column batch, so it composes with other operators."""
    var keys = List[Float64]()
    var key_mask = List[Bool]()
    var values = List[Float64]()
    for i in range(result.n_groups()):
        keys.append(result.keys[i])
        key_mask.append(True)
        values.append(result.values[i])
    var present = List[Bool]()
    for i in range(result.n_groups()):
        present.append(result.present[i])

    var columns = List[Float64Array]()
    columns.append(float64_with_nulls(keys^, key_mask))
    columns.append(float64_with_nulls(values^, present))
    var names = List[String]()
    names.append(key_name)
    names.append(value_name)
    var dtypes = List[Int]()
    dtypes.append(0)
    dtypes.append(0)
    return RecordBatch(Schema(names^, dtypes^), columns^, result.n_groups())


fn apply_op(batch: RecordBatch, op_json: String, strict: Bool) raises -> RecordBatch:
    """Run one operator. Raises with a message naming the op and the reason.

    Every branch resolves its columns by name first, so a bad reference fails before
    any row is touched rather than producing a partial result.
    """
    var op = json_string_field(op_json, "op")

    if op == "filter":
        var predicate = json_get_object(op_json, "predicate")
        if len(predicate) == 0:
            raise Error("filter requires a 'predicate' object")
        var nodes = parse_nodes(predicate, batch.schema)
        var root = json_get_int(predicate, "root", len(nodes) - 1)
        var problem = plan_problem(batch.width(), nodes, root)
        if len(problem) > 0:
            raise Error("filter predicate: " + problem)
        return filter_rows(batch, nodes, root, strict)

    if op == "project":
        var expressions = json_get_object(op_json, "expressions")
        if len(expressions) == 0:
            # No expressions: a plain column selection.
            var picked = _resolve_column_list(
                batch.schema, json_get_array(op_json, "columns"), "projected"
            )
            return select_columns(batch, picked)
        var nodes = parse_nodes(expressions, batch.schema)
        var roots = List[Int]()
        var roots_json = json_get_array(expressions, "roots")
        for token in json_array_tokens(roots_json):
            var parsed_root = json_parse_float64_list("[" + token + "]")
            roots.append(Int(parsed_root[0]) if len(parsed_root) > 0 else -1)
        if len(roots) == 0:
            roots.append(len(nodes) - 1)
        for i in range(len(roots)):
            var problem = plan_problem(batch.width(), nodes, roots[i])
            if len(problem) > 0:
                raise Error("project expression " + String(i) + ": " + problem)
        var names = List[String]()
        var names_json = json_get_array(op_json, "names")
        for token in json_array_tokens(names_json):
            names.append(_unquote(token))
        return project(batch, nodes, roots, names, strict)

    if op == "select":
        var picked = _resolve_column_list(
            batch.schema, json_get_array(op_json, "columns"), "selected"
        )
        return select_columns(batch, picked)

    if op == "sort":
        var nulls_last = json_get_bool(op_json, "nulls_last", True)
        var by_list = json_get_array(op_json, "by")
        if len(by_list) > 0:
            var keys = _resolve_column_list(batch.schema, by_list, "sort")
            var desc_list = json_get_array(op_json, "desc")
            var desc = List[Bool]()
            for token in json_array_tokens(desc_list):
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
            batch.schema, json_get_array(op_json, "columns"), "distinct"
        )
        return distinct_rows(batch, keys)

    if op == "limit":
        return limit_rows(
            batch,
            json_get_int(op_json, "offset", 0),
            json_get_int(op_json, "count", batch.n_rows),
        )

    if op == "aggregate":
        var token = json_string_field(op_json, "agg")
        var opcode = parse_aggregation(token)
        if opcode == AGG_UNKNOWN:
            # numeric.contract owns the message, so the accepted set is listed in one
            # place and cannot drift from what parse_aggregation actually accepts.
            raise Error(unknown_aggregation_error(token))
        var value = _resolve_column(
            batch.schema, json_string_field(op_json, "value"), "aggregate value"
        )
        var value_name = aggregation_token(opcode) + "_" + json_string_field(
            op_json, "value"
        )

        var by_array = json_get_array(op_json, "by")
        if len(by_array) > 0:
            var key_columns = _resolve_column_list(batch.schema, by_array, "group")
            var multi = group_by_multi(batch, key_columns, value, opcode)
            # Rebuild as a batch: one column per key plus the aggregate.
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
            var agg_values = List[Float64]()
            var agg_mask = List[Bool]()
            for g in range(len(multi.values)):
                agg_values.append(multi.values[g])
                agg_mask.append(multi.present[g])
            columns.append(float64_with_nulls(agg_values^, agg_mask))
            names.append(value_name)
            dtypes.append(0)
            var out_rows = multi.n_groups() if multi.key_width > 0 else len(
                multi.values
            )
            return RecordBatch(Schema(names^, dtypes^), columns^, out_rows)

        var single_by = json_string_field(op_json, "by")
        if len(single_by) == 0:
            raise Error("aggregate requires 'by' (a column name or an array)")
        var key = _resolve_column(batch.schema, single_by, "group")
        return _grouped_to_batch(
            group_by(batch, key, value, opcode), single_by, value_name
        )

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
        " aggregate"
    )


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


fn _batch_to_json(batch: RecordBatch) -> String:
    """Columns out, `null` for absent — the mirror of the row-major input."""
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
                out += String(column.get(r))
            else:
                out += "null"
        out += "]"
    out += "]}"
    return out


fn run_query_execute(raw: String, rows_json: String) -> String:
    """Execute a whole query plan and return columns, lineage and a plan hash.

    `rows_json` is supplied by the caller so `main.mojo` can substitute a resident
    dataset's rows for an inline array without this module knowing about the registry.
    """
    var ops = json_get_array(raw, "ops")
    var op_tokens = List[String]()
    if len(ops) > 0:
        try:
            op_tokens = json_array_tokens(ops)
        except:
            return _plan_error("invalid_arguments", "the 'ops' array could not be parsed")
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

    var strict = json_get_bool(raw, "strict", False)
    var lineage = String("[")
    var hash_value = plan_hash(ops) if len(ops) > 0 else ""

    for i in range(op_count):
        ref op_json = op_tokens[i]
        var name = json_string_field(op_json, "op")
        var next_batch: RecordBatch
        try:
            next_batch = apply_op(batch, op_json, strict)
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
            + '"}'
        )
    lineage += "]"

    var body = _batch_to_json(batch)
    return (
        '{"result":'
        + body
        + ',"lineage":'
        + lineage
        + ',"ops":'
        + String(op_count)
        + ',"rows":'
        + String(batch.n_rows)
        + ',"plan_hash":"'
        + hash_value
        + '"}'
    )
