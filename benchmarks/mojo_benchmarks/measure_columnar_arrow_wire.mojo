"""
measure_columnar_arrow_wire.mojo — does the Arrow layout actually beat JSON rows?

The plan deferred `columnar/arrow_wire.mojo` with a stated reason: *"The O(n²)→O(n)
ingest fix removed the pressure that motivated it; revisit when a measurement demands
it."* This file IS that measurement. It ingests the SAME table both ways at 1k, 16k and
128k rows and prints ns/cell for each, so the claim the module is allowed to make is
whatever comes out — including "no present speed advantage", which is a legitimate
outcome.

Named `measure_*` rather than `bench_*` on purpose: `tests/benchmark_mojo_vs_python.py`
writes `bench_{module}.mojo` in this directory from a generator, and a hand-written file
under that name is destroyed on the next run.

Compiled, not JIT. Rule 1b of docs/mojo/new-kernel-package-rules.md: `mojo run` cannot
prove memory soundness and its timings are not the worker's timings. Build it:

    cd mojo_env
    pixi run mojo build -I../mojo/engine \\
        ../benchmarks/mojo_benchmarks/measure_columnar_arrow_wire.mojo \\
        -o /tmp/measure_arrow_wire
    /tmp/measure_arrow_wire

What is being compared, precisely
--------------------------------
Every path starts from a `String` that arrived in a request frame and ends at a
`RecordBatch`, so the same work is charged to each:

  A. json today   : rows text -> `query.plan.parse_rows`               -> RecordBatch
  B. json lean    : rows text -> `parse_rows_lean` (below)             -> RecordBatch
  C. arrow full   : "@u8:.."  -> `json_parser.json_parse_float64_list`
                              -> `arrow_wire.packed_floats_to_bytes`
                              -> `arrow_wire.decode_batch_positional`  -> RecordBatch
  D. arrow layout : bytes     -> `arrow_wire.decode_batch_positional`  -> RecordBatch

**B exists so the comparison is not rigged.** `parse_rows` spends most of its per-cell
budget on `json_parse_float64_list("[" + cell + "]")` — a String concat, a `{"v":...}`
wrap, an array re-tokenize and then the float parse, four allocations to read one
number. Comparing a packed layout against that overstates what the LAYOUT bought. B is
the leanest text path reachable from existing public helpers (one pass per row, one
token per cell, `conv.parse_float64` directly) and it is the baseline the intrinsic
claim has to be made against. A is still reported because it is what ships today.

D is the layout decode with no transport cost at all. It is NOT reachable today — the
runtime widens every wire byte to a `Float64` before a kernel sees it, which is what C
pays for — and it is labelled on every line so nobody quotes it as a shipping number.

CORRECTNESS IS GATED FIRST. Every path must produce a batch identical to A's, bit for
bit, or the timings are not printed at all — a speed comparison between two different
answers is meaningless.
"""
from std.time import perf_counter_ns

from columnar.arrow_wire import (
    ARROW_OK,
    arrow_status_name,
    batches_identical,
    buffers_identical,
    decode_batch_positional,
    encode_batch,
    packed_floats_to_bytes,
    wire_arg,
)
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from conv import parse_float64
from json.parser import json_parse_float64_list
from query.plan import json_raw_tokens, parse_rows


def parse_rows_lean(rows_json: String, n_columns: Int) -> RecordBatch:
    """The leanest TEXT ingest reachable from existing public helpers.

    Not a kernel and not shipped: it lives in the measurement because a fair baseline is
    part of the measurement. It differs from `query.plan.parse_rows` in exactly one way
    — a cell is parsed with `conv.parse_float64` on its own token instead of being
    wrapped in `"[" + cell + "]"` and pushed through the whole array parser. Same
    tokenizer family (`json_raw_tokens`, one pass per level), same float parser
    (`parse_float64` is what `json_parse_float64_list` ends up calling), so it produces
    the same values bit for bit — which the gate asserts rather than assumes.

    Anything faster than this would need a float parser that reads digits out of the
    row buffer in place. That is a real optimisation and it is NOT done here, so the
    numbers below are an upper bound on what the layout beats, not a lower one.
    """
    var row_tokens = json_raw_tokens(rows_json)
    var n_rows = len(row_tokens)
    var values = List[List[Float64]]()
    var masks = List[List[Bool]]()
    for _ in range(n_columns):
        values.append(List[Float64]())
        masks.append(List[Bool]())
    for r in range(n_rows):
        var cells = json_raw_tokens(row_tokens[r])
        for c in range(n_columns):
            if c >= len(cells) or cells[c] == "null" or len(cells[c]) == 0:
                values[c].append(0.0)
                masks[c].append(False)
            else:
                values[c].append(parse_float64(cells[c]))
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


def _bytes_to_string(data: List[UInt8]) -> String:
    """Owned copy of raw bytes. See `arrow_wire.bytes_to_string` for why not `chr`."""
    var out = String("")
    out += StringSlice(unsafe_from_utf8=Span(data))
    return out


def _cell_value(index: Int, profile: Int) -> Float64:
    """The datum at flat position `index`.

    Two profiles, because the JSON path's cost is a function of TEXT LENGTH and the
    layout's is not, so one profile cannot answer "which is bigger on the wire":

      0 — short decimals (`index * 0.5`): 3-8 characters per cell, the friendliest case
          for a text encoding and the least friendly for a fixed 8-byte-per-cell layout.
      1 — full-precision doubles: 17-19 characters per cell, what a measurement, a rate
          or anything that has been through arithmetic actually looks like.
    """
    if profile == 0:
        return Float64(index) * 0.5
    return Float64(index) * 0.1 + 1.4142135623730951


def build_rows_json(n_rows: Int, n_columns: Int, profile: Int) -> String:
    """`[[..],[..]]` with a `null` every seventh cell, built in ONE pass.

    Accumulated into a `List[UInt8]` and converted once. Repeated `String +=` over half
    a million cells is the kind of quadratic input construction that would be charged to
    the JSON path's measurement rather than to the harness.
    """
    var out = List[UInt8]()
    out.append(UInt8(91))  # '['
    for r in range(n_rows):
        if r > 0:
            out.append(UInt8(44))  # ','
        out.append(UInt8(91))
        for c in range(n_columns):
            if c > 0:
                out.append(UInt8(44))
            var index = r * n_columns + c
            if index % 7 == 0:
                var null_text = String("null").as_bytes()
                for k in range(len(null_text)):
                    out.append(null_text[k])
            else:
                var text = String(_cell_value(index, profile)).as_bytes()
                for k in range(len(text)):
                    out.append(text[k])
        out.append(UInt8(93))  # ']'
    out.append(UInt8(93))
    return _bytes_to_string(out)


def _quote(body: String) -> String:
    var out = String("\"")
    out += body
    out += "\""
    return out




def measure_one(n_rows: Int, n_columns: Int, profile: Int, repeats: Int) -> Int:
    """One (size, profile) cell of the matrix. Returns the number of failures.

    Correctness is gated BEFORE any timing is printed, and a failure returns early
    without printing timings at all. A timing comparison between two different answers
    is not a weaker result, it is not a result.
    """
    var cells = n_rows * n_columns
    var rows_json = build_rows_json(n_rows, n_columns, profile)

    var reference: RecordBatch
    try:
        reference = parse_rows(rows_json, n_columns)
    except:
        print("  ❌ parse_rows raised on generated input")
        return 1

    var encoded = encode_batch(reference)
    if encoded.status != ARROW_OK:
        print("  ❌ encode refused:", arrow_status_name(encoded.status))
        return 1
    var arg_body = wire_arg(encoded.bytes)
    var frame = _quote(arg_body)

    # ── GATE ──────────────────────────────────────────────────────────────────
    var packed_floats: List[Float64]
    try:
        packed_floats = json_parse_float64_list(frame)
    except:
        print("  ❌ json_parse_float64_list raised on the @u8 frame")
        return 1
    var recovered = packed_floats_to_bytes(packed_floats)
    if recovered.status != ARROW_OK:
        print("  ❌ packed floats refused:", arrow_status_name(recovered.status))
        return 1
    if not buffers_identical(encoded.bytes, recovered.bytes):
        print("  ❌ the base64 round trip is not byte-exact")
        return 1
    var decoded = decode_batch_positional(recovered.bytes, n_rows, n_columns)
    if decoded.status != ARROW_OK:
        print("  ❌ decode refused:", arrow_status_name(decoded.status))
        return 1
    if not batches_identical(reference, decoded.batch):
        print("  ❌ the arrow path produced a DIFFERENT batch — timings withheld")
        return 1
    if not batches_identical(reference, parse_rows_lean(rows_json, n_columns)):
        print("  ❌ the lean json baseline produced a DIFFERENT batch — timings withheld")
        return 1

    # ── timings ───────────────────────────────────────────────────────────────
    var json_ns = 0.0
    var lean_ns = 0.0
    var arrow_full_ns = 0.0
    var arrow_layout_ns = 0.0
    var wrong_rows = 0
    for _ in range(repeats):
        var t6 = perf_counter_ns()
        var d = parse_rows_lean(rows_json, n_columns)
        var t7 = perf_counter_ns()
        var elapsed_lean = Float64(Int(t7 - t6))
        if lean_ns == 0.0 or elapsed_lean < lean_ns:
            lean_ns = elapsed_lean
        if d.n_rows != n_rows:
            wrong_rows += 1

        try:
            var t0 = perf_counter_ns()
            var a = parse_rows(rows_json, n_columns)
            var t1 = perf_counter_ns()
            var elapsed_json = Float64(Int(t1 - t0))
            if json_ns == 0.0 or elapsed_json < json_ns:
                json_ns = elapsed_json
            if a.n_rows != n_rows:
                wrong_rows += 1

            var t2 = perf_counter_ns()
            var floats = json_parse_float64_list(frame)
            var narrowed = packed_floats_to_bytes(floats)
            var b = decode_batch_positional(narrowed.bytes, n_rows, n_columns)
            var t3 = perf_counter_ns()
            var elapsed_full = Float64(Int(t3 - t2))
            if arrow_full_ns == 0.0 or elapsed_full < arrow_full_ns:
                arrow_full_ns = elapsed_full
            if b.n_rows != n_rows:
                wrong_rows += 1
        except:
            print("  ❌ a timed call raised")
            return 1

        var t4 = perf_counter_ns()
        var c = decode_batch_positional(encoded.bytes, n_rows, n_columns)
        var t5 = perf_counter_ns()
        var elapsed_layout = Float64(Int(t5 - t4))
        if arrow_layout_ns == 0.0 or elapsed_layout < arrow_layout_ns:
            arrow_layout_ns = elapsed_layout
        if c.n_rows != n_rows:
            wrong_rows += 1
    if wrong_rows > 0:
        print("  ❌ a timed call returned the wrong row count")
        return 1
    if json_ns <= 0.0 or lean_ns <= 0.0 or arrow_full_ns <= 0.0 or arrow_layout_ns <= 0.0:
        # A zero elapsed time is not a fast measurement, it is no measurement (rule 4).
        print("  ⚠️  clock resolution too coarse at rows=" + String(n_rows) + "; no ratio reported")
        return 0

    print("  rows=" + String(n_rows) + " cols=" + String(n_columns) + " cells=" + String(cells))
    print("    batches identical ....... True (gate passed)")
    print(
        "    wire bytes: json rows "
        + String(len(rows_json.as_bytes()))
        + " | @u8 arg "
        + String(len(arg_body.as_bytes()))
        + " | raw layout "
        + String(len(encoded.bytes))
        + "   (json/@u8 = "
        + String(Float64(len(rows_json.as_bytes())) / Float64(len(arg_body.as_bytes())))
        + ")"
    )
    print(
        "    A json today (parse_rows) "
        + String(json_ns / 1000000.0)
        + " ms   "
        + String(json_ns / Float64(cells))
        + " ns/cell   (baseline that ships)"
    )
    print(
        "    B json lean ............. "
        + String(lean_ns / 1000000.0)
        + " ms   "
        + String(lean_ns / Float64(cells))
        + " ns/cell   xA "
        + String(json_ns / lean_ns)
        + "   (fair text baseline)"
    )
    print(
        "    C arrow full path ....... "
        + String(arrow_full_ns / 1000000.0)
        + " ms   "
        + String(arrow_full_ns / Float64(cells))
        + " ns/cell   xA "
        + String(json_ns / arrow_full_ns)
        + "   xB "
        + String(lean_ns / arrow_full_ns)
        + "   <- the claim"
    )
    print(
        "    D arrow layout only ..... "
        + String(arrow_layout_ns / 1000000.0)
        + " ms   "
        + String(arrow_layout_ns / Float64(cells))
        + " ns/cell   xA "
        + String(json_ns / arrow_layout_ns)
        + "   xB "
        + String(lean_ns / arrow_layout_ns)
        + "   (NOT reachable today: the runtime widens every wire byte to a Float64)"
    )
    return 0


def main():
    print("measure_columnar_arrow_wire — JSON rows vs Arrow layout, same table")
    print("compiled binary; both paths start from a wire String and end at a RecordBatch")
    print("")

    var sizes = List[Int]()
    sizes.append(1000)
    sizes.append(16000)
    sizes.append(128000)
    comptime N_COLUMNS: Int = 4
    comptime REPEATS: Int = 5

    var failures = 0
    for profile in range(2):
        if profile == 0:
            print("── value profile 0: short decimals, 3-8 chars/cell ──────────────")
        else:
            print("── value profile 1: full-precision doubles, 17-19 chars/cell ────")
        for s in range(len(sizes)):
            failures += measure_one(sizes[s], N_COLUMNS, profile, REPEATS)
            print("")

    if failures == 0:
        print("  [columnar.arrow_wire] correctness gate passed at every size and profile")
    else:
        print("  [columnar.arrow_wire] FAILURES:", failures)
