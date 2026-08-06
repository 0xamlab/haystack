"""
columnar.arrow_wire — Arrow's memory LAYOUT over the existing packed-buffer arg. Zero Python.

What this is, and what it deliberately is not
---------------------------------------------
It is not a transport. `"@u8:<base64>"` already IS one: the runtime accepts that
spelling wherever a `List[Float64]` is expected, on both the SDK and server paths, and
`json/parser.json_parse_float64_list` decodes it in one O(n) pass without touching the
float tokenizer. There is no new message type here, no Arrow C data interface, no FFI,
no proto change.

What it adds is the LAYOUT carried inside that existing arg: the contiguous values
buffer plus validity bitmap that `columnar/array.mojo` and `columnar/validity.mojo`
already use — bit `i` in byte `i/8`, least-significant bit first, set means present,
Arrow's own convention. A batch therefore arrives as one flat byte range that a decoder
copies in bulk, instead of as JSON text that a decoder tokenizes cell by cell.

Buffer order is Arrow's, so the sub-ranges are the ones an Arrow consumer expects:

    for each column c in field order:
        validity  bytes_for_bits(n_rows) bytes   (LSB-first, set = present)
        values    8 * n_rows bytes               (little-endian IEEE-754 doubles)

Schema is NOT in the buffer. Arrow keeps schema out of the message body too, and the
existing `query_execute` frame already carries a `columns` array — so names and dtypes
stay where they are and this module takes them as parameters.

Honesty about the motivation, and WHAT WAS MEASURED
--------------------------------------------------
The plan deferred this file with a stated reason: *"The O(n²)→O(n) ingest fix removed
the pressure that motivated it; revisit when a measurement demands it."* That fix is
`query.plan.parse_rows`, which tokenizes rows in one pass. So the file was built
together with the measurement that decides what may be claimed:
`benchmarks/mojo_benchmarks/measure_columnar_arrow_wire.mojo` — same table, same
process, correctness gated first, compiled rather than JIT because rule 1b says a JIT
run cannot prove what the worker binary does.

Result, 4 columns x {1k, 16k, 128k} rows, one null in seven, `RecordBatch` byte-identical
on every path. Apple silicon, `mojo build`, min of 5 within a run, min across 3 runs, at
machine load < 20:

  ns/cell             1k      16k     128k       vs A ships     vs B lean
  short decimals
    A parse_rows     330      365      397          1.0x
    B lean text      305      342      363         1.07-1.09x      1.0x
    C arrow @u8      102      100      105         3.2-3.8x        3.0-3.5x
    D layout only    8.5      7.3      7.2         39-55x          36-50x
  full-precision doubles
    A parse_rows     728      784      792          1.0x
    B lean text      432      474      467         1.65-1.70x      1.0x
    C arrow @u8       98      103      105         7.4-7.6x        4.3-4.9x
    D layout only    8.5      7.3      7.2         86-110x         51-65x

ONLY THE RATIO COLUMNS ARE A PROPERTY OF THE CODE. The absolute ns/cell figures are
strongly load-dependent and must not be quoted as machine specs: on this same binary with
the machine at load ~100 (sibling builds running), every absolute number inflated 2-5x —
`A` reached 2167 ns/cell — while `C` stayed within 170-285. Direction never changed in 5
independent runs, and the C-vs-B ratio stayed inside 2.96x-5.96x throughout. Ratios are
quoted because both paths are timed in the same process against the same table, so the
load cancels; an absolute number does not have that property.

So the deferral's premise no longer holds: the one-pass ingest fix did NOT close the gap.
The layout wins at every size and both value profiles, in every run. The least favourable
cell measured anywhere is 1k rows of short decimals: 2.96x against the strongest text
baseline available (B) and 3.22x against what ships (A). Per-profile floors from 16k rows
up are 3.30x vs B / 3.63x vs A for short decimals, and 4.46x vs B / 7.57x vs A for
full-precision doubles. The advantage grows with the text length of a value,
which is the part that has nothing to do with row count: a 17-character double costs the
tokenizer 17 characters and costs this layout 8 bytes.

Three things that are NOT a win, stated because a one-sided report is the defect this
project has already paid for twice:

  * BYTES ON THE WIRE go the wrong way for short values. base64 of 8-byte doubles is
    10.67 bytes per cell flat: measured 43 340 vs 26 955 bytes at 1k rows of short
    decimals (1.61x LARGER), against 43 340 vs 66 932 for full-precision doubles (1.54x
    smaller). These byte counts are deterministic and reproduce exactly. This is a CPU
    optimisation that is also a bandwidth optimisation only for wide values.
  * MEMORY is worse on the way in, by construction: the runtime widens every wire byte
    to a `Float64` before a kernel sees the argument, so the `"@u8:"` spelling costs 8
    process bytes per wire byte. See the ceiling comment below.
  * THE BIG NUMBER IS NOT REACHABLE. Row D — decoding the layout from raw bytes, 7.2-8.5
    ns/cell, 36-65x the lean text path — is `decode_batch` with no transport cost, which
    is what a real byte-buffer arg would deliver. It is NOT reachable today:
    `packed_floats_to_bytes` sits in front of it and row C is the honest shipping figure.
    The file's remaining value beyond present speed is exactly that: the layout is in
    place, so the transport swap is a call-site change.

An earlier revision of this docstring carried a different table (A 516-669, C 143-161, D
10-13 ns/cell) and claimed a 3.2x floor against the lean baseline and 38-67x for D. None
of those three reproduced on re-measurement and all are withdrawn: the absolute figures
were taken at an unrecorded machine load and sit between the two load regimes above, the
3.2x floor is contradicted by the 2.96x cell, and D is faster than was claimed, not
slower. Re-measure with
`benchmarks/mojo_benchmarks/measure_columnar_arrow_wire.mojo` rather than trusting any
number here; the ratios are what survived three independent re-runs.

Refusal, not a partial answer
-----------------------------
A buffer shorter than the declared shape must be REFUSED. Reading past the end of a
`List` is an uncatchable abort that takes the worker and every resident dataset with it
(rule 1), and `n_rows * n_columns * 8 == len(packed)` is not a bound because the
multiply wraps. So `wire_bytes_required` saturates, the declared shape is compared
against WHAT THE BUFFER CONTAINS (exactly, in both directions), and a mismatch returns
an empty batch with a status. An empty batch is a real answer for `n_rows = 0`, which
is exactly why the status field exists rather than a length test at the call site
(rule 4).

Canonical bytes
---------------
`encode_column` writes `+0.0` in a slot whose validity bit is clear, never the value
stored underneath it. Two reasons, both load-bearing:

  * a slice shares its parent's values list (`array.mojo` makes that O(1) on purpose),
    so the payload under a null slot can be an unrelated row's datum — shipping it
    would put data on the wire that the logical column does not contain;
  * the encoding becomes canonical: two logically equal columns produce byte-identical
    buffers, so `encode(decode(bytes)) == bytes` and a byte comparison is a meaningful
    equality test.

Trailing bits past `n_rows` in the last validity byte are written as 0 for the same
reason — `validity.new_all_valid` leaves them SET, which would make two equal columns
encode differently.

Count relations, in prose because a block here would reach nothing
-----------------------------------------------------------------
`columnar/` is in `mojo_inventory._SKIP_RUNTIME_DIRS`, so this module is invisible to
the runtime contract and to `build_capability_manifest`; a `@capability` block would be
parsed by nothing and checked by nothing. The relations, in the grammar's style so they
stay greppable:

  decode_batch:    wire_bytes_required(n_rows, n_columns) == len(packed)  [kernel_validated]
                   n_columns <= len(names), n_columns <= len(dtypes)      [kernel_validated]
                   n_rows <= MAX_WIRE_ROWS, n_columns <= MAX_WIRE_COLUMNS [kernel_validated]
  decode_string_column:
                   bytes_for_bits(n_rows) + OFFSET_BYTES * (n_rows + 1) <= len(packed)
                                                                          [kernel_validated]
                   offsets are monotone and offsets[n_rows] == data length [kernel_validated]

Status codes
------------
`columnar/` allocates 300-309 to `columnar/dictionary.mojo` and 310-329 here (rule 4e).
"""
from std.math import floor

from std.memory import ArcPointer, bitcast

from columnar.array import Float64Array, StringArray, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from columnar.dtype import DTYPE_FLOAT64, DTYPE_NULL
from columnar.validity import bytes_for_bits, is_valid, new_all_null, set_valid

# ── status codes: columnar.arrow_wire owns 310-329 ────────────────────────────
comptime ARROW_OK: Int = 310
comptime ARROW_INVALID_ROW_COUNT: Int = 311
comptime ARROW_INVALID_COLUMN_COUNT: Int = 312
comptime ARROW_SCHEMA_TOO_SHORT: Int = 313
comptime ARROW_UNSUPPORTED_DTYPE: Int = 314
comptime ARROW_BUFFER_TRUNCATED: Int = 315
comptime ARROW_BUFFER_TRAILING_BYTES: Int = 316
comptime ARROW_NOT_A_BYTE: Int = 317
comptime ARROW_RAGGED_BATCH: Int = 318
comptime ARROW_OFFSETS_NOT_MONOTONE: Int = 319
comptime ARROW_OFFSET_OUT_OF_RANGE: Int = 320
comptime ARROW_STRING_BYTES_MISMATCH: Int = 321

comptime VALUE_BYTES: Int = 8
comptime OFFSET_BYTES: Int = 8

# Ceilings, and the arithmetic behind them (rule 1c).
#
# `decode_batch` allocates, per column, one `List[Float64]` of `n_rows` (8 bytes/row),
# one `List[Bool]` of `n_rows` (1 byte/row) and one bitmap (1/8 byte/row) — about 9.1
# bytes per cell — against a buffer that must be EXACTLY 8.125 bytes per cell. So peak
# residency is ~2.1x the byte buffer, and that buffer IS the payload: these ceilings
# cannot be used to make a small request allocate a large amount, which is the failure
# mode rule 1c is about. They exist to refuse an absurd declared shape before the
# multiply, not as the operative memory bound.
#
# `decode_batch_from_packed_floats` is dearer, and the cost is the existing spelling's,
# not this module's: the runtime widens every wire byte to a `Float64` before a kernel
# sees the argument, so 8 bytes of process memory per byte on the wire. Peak for that
# entry point is ~9x the wire byte count. Worth knowing before shipping a large table
# through `"@u8:"`, and the reason `decode_batch` takes bytes directly — the day the
# runtime can hand a kernel a byte buffer, that path is already here.
#
# 2^24 rows x 512 columns would demand a 68 GB buffer, so the exact-length equality is
# what binds in practice. MAX_WIRE_COLUMNS matches `query.plan.MAX_COLUMNS` so a batch
# this module accepts is a batch that plane can also carry.
comptime MAX_WIRE_ROWS: Int = 1 << 24
comptime MAX_WIRE_COLUMNS: Int = 512

comptime _B64_ALPHABET: String = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _saturating_product(a: Int, b: Int) -> Int:
    """`a * b`, clamped instead of wrapped.

    `3 * 6148914691236517206` is 2 on a wrapping multiply, so a length check against a
    wrapped product passes and the read it was meant to refuse goes ahead. Same
    function, same reason, as `query.plan._saturating_product` — repeated here rather
    than imported because `query` depends on `columnar` and the reverse would be a
    dependency cycle.
    """
    comptime CEILING: Int = 1 << 62
    if a <= 0 or b <= 0:
        return 0
    if a > CEILING // b:
        return CEILING
    return a * b


def _saturating_sum(a: Int, b: Int) -> Int:
    """`a + b`, clamped instead of wrapped. See `_saturating_product`."""
    comptime CEILING: Int = 1 << 62
    if a < 0 or b < 0:
        return 0
    if a > CEILING - b:
        return CEILING
    return a + b


def bytes_to_string(data: List[UInt8]) -> String:
    """A String OWNING a copy of `data`, byte for byte.

    Two idioms are wrong here and both have cost this tree a defect:

      * `chr(Int(data[i]))` per byte is NOT byte-exact — `chr` of a byte >= 0x80 emits a
        two-byte UTF-8 sequence, so "café" (5 bytes) comes back as "cafÃ©" (7). That is
        the defect that made every op naming a non-ASCII column fail.
      * `String(StringSlice(unsafe_from_utf8=Span(data)))` returns a String aliasing a
        LOCAL that dies on return. It survives the JIT and misbehaves in the compiled
        worker (rule 1b) — `filter` crashed, `project` read a garbage op name.

    `+=` copies into the String's own buffer, so nothing aliases `data`.

    `query.plan._string_from_utf8` is the same three lines for the same reason. It is
    not imported: `query` imports `columnar`, so importing it back would be a cycle.
    The duplication is deliberate and recorded, per rule 3's requirement that a repeated
    helper be justified rather than accidental.
    """
    var out = String("")
    out += StringSlice(unsafe_from_utf8=Span(data))
    return out


def wire_bytes_required(n_rows: Int, n_columns: Int) -> Int:
    """Bytes a `n_rows x n_columns` Float64 batch occupies in this layout, saturating.

    `n_columns * (8 * n_rows + bytes_for_bits(n_rows))`. Every step saturates, so the
    result is never a small number standing in for a huge one.
    """
    if n_rows <= 0 or n_columns <= 0:
        return 0
    var per_column = _saturating_sum(
        _saturating_product(VALUE_BYTES, n_rows), bytes_for_bits(n_rows)
    )
    return _saturating_product(per_column, n_columns)


def _append_f64(mut out: List[UInt8], value: Float64):
    """Append `value` as 8 little-endian bytes of its IEEE-754 bit pattern."""
    var bits = bitcast[DType.uint64](value)
    for k in range(8):
        out.append(UInt8((bits >> UInt64(8 * k)) & UInt64(0xFF)))


def _read_f64(data: List[UInt8], at: Int) -> Float64:
    """The double at byte offset `at`, or 0.0 if the eight bytes are not all there.

    The guard is unreachable from every public entry point here — each validates the
    exact buffer length first — and it is present anyway, because the alternative to an
    unreachable branch is an uncatchable abort if someone ever makes it reachable.
    """
    if at < 0 or at + 8 > len(data):
        return 0.0
    var bits = UInt64(0)
    for k in range(8):
        bits = bits | (UInt64(data[at + k]) << UInt64(8 * k))
    return bitcast[DType.float64](bits)


def _read_u64(data: List[UInt8], at: Int) -> UInt64:
    """The little-endian UInt64 at `at`, or 0. Kept UNSIGNED on purpose.

    An offset of 0xFFFFFFFFFFFFFFFF converted straight to `Int` is -1, and a naive
    `off <= data_len` test passes for -1 — then the read indexes backwards off the
    front. Callers compare in UInt64 first and only narrow a value already known to be
    small.
    """
    if at < 0 or at + 8 > len(data):
        return UInt64(0)
    var bits = UInt64(0)
    for k in range(8):
        bits = bits | (UInt64(data[at + k]) << UInt64(8 * k))
    return bits


# ── encode ────────────────────────────────────────────────────────────────────


def encode_column(column: Float64Array) -> List[UInt8]:
    """One column as `[validity][values]`, canonical.

    A slot whose validity bit is clear is written as `+0.0`, and pad bits past the
    logical length are written as 0. See the module docstring: without both, two
    logically equal columns encode to different bytes and the shared-buffer payload
    under a null slot goes on the wire.
    """
    var n = column.length
    var out = List[UInt8]()
    var bitmap = new_all_null(n)
    for i in range(n):
        if column.is_valid_at(i):
            set_valid(bitmap, i)
    for i in range(len(bitmap)):
        out.append(bitmap[i])
    for i in range(n):
        _append_f64(out, column.get(i))  # get() is 0.0 exactly where validity is clear
    return out^


@fieldwise_init
struct WireEncoded(Copyable, Movable):
    """An encoded buffer, or an ABSENT one with the reason in `status`.

    `bytes` is EMPTY on refusal. A ragged batch has no single row count, so there is no
    buffer that represents it and none is invented (rule 4).
    """

    var status: Int
    var bytes: List[UInt8]
    var n_rows: Int
    var n_columns: Int


def encode_batch(batch: RecordBatch) -> WireEncoded:
    """Encode every column in field order. Refuses a ragged batch.

    `RecordBatch.is_consistent` is the existing check for "every column is exactly
    `n_rows` long and the schema matches"; it is called rather than re-derived, so this
    module and the executor cannot disagree about what a well-formed batch is.
    """
    var out = WireEncoded(ARROW_OK, List[UInt8](), 0, 0)
    if not batch.is_consistent():
        out.status = ARROW_RAGGED_BATCH
        return out^
    if batch.n_rows < 0 or batch.n_rows > MAX_WIRE_ROWS:
        out.status = ARROW_INVALID_ROW_COUNT
        return out^
    if batch.width() > MAX_WIRE_COLUMNS:
        out.status = ARROW_INVALID_COLUMN_COUNT
        return out^
    var packed = List[UInt8]()
    for c in range(batch.width()):
        var column_bytes = encode_column(batch.columns[c])
        for i in range(len(column_bytes)):
            packed.append(column_bytes[i])
    out.bytes = packed^
    out.n_rows = batch.n_rows
    out.n_columns = batch.width()
    return out^


# ── decode ────────────────────────────────────────────────────────────────────


@fieldwise_init
struct WireDecoded(Copyable, Movable):
    """A decoded batch, or an ABSENT one with the reason in `status`.

    On refusal `batch` is a zero-column, zero-row batch. That is also a legitimate
    successful answer for an empty request, which is precisely why the caller must read
    `status` and not `n_rows` (rule 4).
    """

    var status: Int
    var batch: RecordBatch
    var n_rows: Int
    var n_columns: Int


def _empty_batch() -> RecordBatch:
    var names = List[String]()
    var dtypes = List[Int]()
    var columns = List[Float64Array]()
    return RecordBatch(Schema(names^, dtypes^), columns^, 0)


def positional_names(n_columns: Int) -> List[String]:
    """`col_0 .. col_{n-1}` — the names `query.plan.parse_rows` gives a positional batch.

    Provided so the two ingest paths can be compared for byte-identity without a caller
    guessing at the naming convention; a comparison between two differently named
    batches would fail for a reason that has nothing to do with the layout.
    """
    var names = List[String]()
    if n_columns <= 0 or n_columns > MAX_WIRE_COLUMNS:
        return names^
    for c in range(n_columns):
        names.append("col_" + String(c))
    return names^


def null_dtypes(n_columns: Int) -> List[Int]:
    """`DTYPE_NULL` per column — what `query.plan.build_batch` writes today (`0`)."""
    var dtypes = List[Int]()
    if n_columns <= 0 or n_columns > MAX_WIRE_COLUMNS:
        return dtypes^
    for _ in range(n_columns):
        dtypes.append(DTYPE_NULL)
    return dtypes^


def decode_batch(
    packed: List[UInt8], names: List[String], dtypes: List[Int], n_rows: Int, n_columns: Int
) -> WireDecoded:
    """Rebuild a `RecordBatch` from the layout. Shape is validated before any read.

    Order: ceilings, then the schema lengths, then the dtypes, then the EXACT buffer
    length. Exact in both directions — a short buffer is `ARROW_BUFFER_TRUNCATED` and a
    long one is `ARROW_BUFFER_TRAILING_BYTES`, because a declared row count that
    disagrees with the buffer means one of the two is wrong and guessing which would
    silently drop or invent rows.

    Only `DTYPE_FLOAT64` and `DTYPE_NULL` are accepted: `RecordBatch` carries Float64
    columns, and `DTYPE_NULL` (0) is what the query plane writes for an untyped
    positional column. A `DTYPE_STRING` column has a different layout entirely — see
    `decode_string_column` — so accepting the tag here would decode 8 bytes of UTF-8 as
    a double and call it data.
    """
    var out = WireDecoded(ARROW_OK, _empty_batch(), 0, 0)
    if n_rows < 0 or n_rows > MAX_WIRE_ROWS:
        out.status = ARROW_INVALID_ROW_COUNT
        return out^
    if n_columns < 0 or n_columns > MAX_WIRE_COLUMNS:
        out.status = ARROW_INVALID_COLUMN_COUNT
        return out^
    if n_columns > len(names) or n_columns > len(dtypes):
        out.status = ARROW_SCHEMA_TOO_SHORT
        return out^
    for c in range(n_columns):
        var dtype = dtypes[c]
        if dtype != DTYPE_FLOAT64 and dtype != DTYPE_NULL:
            out.status = ARROW_UNSUPPORTED_DTYPE
            return out^

    var required = wire_bytes_required(n_rows, n_columns)
    if required > len(packed):
        out.status = ARROW_BUFFER_TRUNCATED
        return out^
    if required < len(packed):
        out.status = ARROW_BUFFER_TRAILING_BYTES
        return out^

    var bitmap_bytes = bytes_for_bits(n_rows)
    var stride = bitmap_bytes + VALUE_BYTES * n_rows
    var columns = List[Float64Array]()
    var out_names = List[String]()
    var out_dtypes = List[Int]()
    for c in range(n_columns):
        var base = c * stride
        var values = List[Float64]()
        var mask = List[Bool]()
        for r in range(n_rows):
            var present = is_valid_at_offset(packed, base, r)
            mask.append(present)
            if present:
                values.append(_read_f64(packed, base + bitmap_bytes + VALUE_BYTES * r))
            else:
                values.append(0.0)
        columns.append(float64_with_nulls(values^, mask))
        out_names.append(names[c])
        out_dtypes.append(dtypes[c])
    out.batch = RecordBatch(Schema(out_names^, out_dtypes^), columns^, n_rows)
    out.n_rows = n_rows
    out.n_columns = n_columns
    return out^


def is_valid_at_offset(packed: List[UInt8], base: Int, row: Int) -> Bool:
    """Validity bit `row` of the bitmap that starts at byte `base`.

    A thin adapter over `validity.is_valid`, which reads a bitmap starting at index 0.
    Slicing the bitmap out first would copy `n_rows/8` bytes per column for nothing; the
    bit arithmetic is not restated, only the base offset is added.
    """
    if base < 0 or row < 0:
        return False
    var byte = base + row // 8
    if byte >= len(packed):
        return False
    return (packed[byte] >> UInt8(row % 8)) & UInt8(1) == UInt8(1)


def decode_batch_positional(packed: List[UInt8], n_rows: Int, n_columns: Int) -> WireDecoded:
    """`decode_batch` with `col_0..` names and `DTYPE_NULL` dtypes.

    The shape `query.plan.parse_rows` produces, so the two ingest paths are directly
    comparable.
    """
    return decode_batch(
        packed, positional_names(n_columns), null_dtypes(n_columns), n_rows, n_columns
    )


@fieldwise_init
struct ByteBuffer(Copyable, Movable):
    """Raw bytes recovered from a packed `List[Float64]`, or the reason there are none."""

    var status: Int
    var bytes: List[UInt8]


def packed_floats_to_bytes(packed: List[Float64]) -> ByteBuffer:
    """The bytes behind a `"@u8:<base64>"` argument, validated element by element.

    The runtime hands a packed buffer to a kernel as a `List[Float64]` of byte values
    (`json_parser.json_parse_float64_list` widens each raw byte with
    `Float64(Int(raw[i]))`), so recovering the buffer means narrowing each element back
    to a `UInt8`. That widening costs 8 bytes of memory per byte on the wire and it
    happens before this function is called — it is the price of the existing arg
    spelling, and it is what the ingest measurement charges to the Arrow path.

    Every element is checked to be finite, integral and within `[0, 255]` BEFORE the
    conversion. `Int(v)` on a double outside `Int`'s range is undefined — `fptosi`
    yields an arbitrary value, not a clamped one, and `1e300` passes a finiteness test
    perfectly well (rule 4c) — so the range check is what makes the narrowing total.
    A non-byte element refuses the whole buffer rather than being clamped: a clamp would
    turn corrupt transport into plausible data.
    """
    var out = ByteBuffer(ARROW_OK, List[UInt8]())
    var bytes = List[UInt8]()
    for i in range(len(packed)):
        var v = packed[i]
        if v != v:  # NaN
            out.status = ARROW_NOT_A_BYTE
            return out^
        if v < 0.0 or v > 255.0:
            out.status = ARROW_NOT_A_BYTE
            return out^
        if floor(v) != v:
            out.status = ARROW_NOT_A_BYTE
            return out^
        bytes.append(UInt8(Int(v)))
    out.bytes = bytes^
    return out^


def decode_batch_from_packed_floats(
    packed: List[Float64], names: List[String], dtypes: List[Int], n_rows: Int, n_columns: Int
) -> WireDecoded:
    """`packed_floats_to_bytes` then `decode_batch` — the whole server-side path."""
    var recovered = packed_floats_to_bytes(packed)
    if recovered.status != ARROW_OK:
        return WireDecoded(recovered.status, _empty_batch(), 0, 0)
    return decode_batch(recovered.bytes, names, dtypes, n_rows, n_columns)


# ── equality, so a timing comparison is between two identical answers ─────────


def columns_identical(a: Float64Array, b: Float64Array) -> Bool:
    """Bit-for-bit column equality: same length, same validity, same value BITS.

    Bits, not `==`: `0.0 == -0.0` is true and `nan == nan` is false, so a value
    comparison would call two different buffers equal and one buffer unequal to itself.
    A round trip must preserve the exact bit pattern of every value, including which
    NaN it was.
    """
    if a.length != b.length:
        return False
    for i in range(a.length):
        if a.is_valid_at(i) != b.is_valid_at(i):
            return False
        if bitcast[DType.uint64](a.get(i)) != bitcast[DType.uint64](b.get(i)):
            return False
    return True


def batches_identical(a: RecordBatch, b: RecordBatch) -> Bool:
    """Same schema, same row count, same validity bits, same value bits.

    This is the gate a timing comparison has to pass first: two ingest paths that
    produce different answers cannot be compared for speed. Slot payloads under a null
    are compared too — `encode_column` canonicalizes them to `+0.0`, so this is a
    statement about the canonical form both paths must reach, not about whatever a
    caller happened to leave under a null.
    """
    if a.n_rows != b.n_rows:
        return False
    if a.width() != b.width():
        return False
    if a.schema.width() != b.schema.width():
        return False
    for i in range(a.schema.width()):
        if a.schema.names[i] != b.schema.names[i]:
            return False
        if a.schema.dtypes[i] != b.schema.dtypes[i]:
            return False
    for c in range(a.width()):
        if not columns_identical(a.columns[c], b.columns[c]):
            return False
    return True


def buffers_identical(a: List[UInt8], b: List[UInt8]) -> Bool:
    """Byte equality of two buffers — used to assert the encoding is canonical."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


# ── string columns: Arrow's utf8 layout ──────────────────────────────────────


def encode_string_column(values: List[String], mask: List[Bool]) -> List[UInt8]:
    """A nullable string column as `[validity][offsets][utf8 bytes]`.

    `n_rows + 1` little-endian 8-byte offsets, Arrow's `LargeUtf8` width. 8 rather than
    4 because a 4-byte offset silently wraps at 4 GiB of values and the wrap is
    indistinguishable from a legitimate small offset — the same class of defect as a
    wrapping `rows * cols`.

    An absent row contributes no bytes and its offsets are equal, so a null is
    length-zero AND has its validity bit clear, while a real "" is length-zero with the
    bit SET. That is the whole distinction, and it survives because validity is a
    separate buffer.
    """
    var n = len(values)
    var out = List[UInt8]()
    var bitmap = new_all_null(n)
    for i in range(n):
        if i < len(mask) and mask[i]:
            set_valid(bitmap, i)
    for i in range(len(bitmap)):
        out.append(bitmap[i])

    var data = List[UInt8]()
    var offsets = List[Int]()
    offsets.append(0)
    for i in range(n):
        if i < len(mask) and mask[i]:
            var raw = values[i].as_bytes()
            for k in range(len(raw)):
                data.append(raw[k])
        offsets.append(len(data))
    for i in range(len(offsets)):
        var value = UInt64(offsets[i])
        for k in range(8):
            out.append(UInt8((value >> UInt64(8 * k)) & UInt64(0xFF)))
    for i in range(len(data)):
        out.append(data[i])
    return out^


@fieldwise_init
struct WireStrings(Copyable, Movable):
    """A decoded string column, or an ABSENT one with the reason in `status`."""

    var status: Int
    var values: List[String]
    var mask: List[Bool]
    var n_rows: Int


def decode_string_column(packed: List[UInt8], n_rows: Int) -> WireStrings:
    """Rebuild a nullable string column. Offsets are validated before any read.

    Four things are checked, in this order, and all four have to be:

      1. the header — bitmap plus `n_rows + 1` offsets — must be present in full;
      2. every offset must fit the data region, compared in UInt64 so a 2^64-1 offset
         cannot arrive as -1 and pass a signed test;
      3. offsets must be monotone non-decreasing, or a value's length is negative;
      4. the last offset must equal the data region's length EXACTLY, so a truncated or
         over-long body is refused rather than silently reinterpreted.

    Bytes are byte-exact: a value is rebuilt with `bytes_to_string`, never with `chr`
    per byte. That is what makes a non-ASCII value survive — the previous defect in this
    tree decoded `\\u00f3` two different ways and every op naming a non-ASCII column
    failed.
    """
    var out = WireStrings(ARROW_OK, List[String](), List[Bool](), 0)
    if n_rows < 0 or n_rows > MAX_WIRE_ROWS:
        out.status = ARROW_INVALID_ROW_COUNT
        return out^
    var bitmap_bytes = bytes_for_bits(n_rows)
    var header = _saturating_sum(
        bitmap_bytes, _saturating_product(OFFSET_BYTES, n_rows + 1)
    )
    if header > len(packed):
        out.status = ARROW_BUFFER_TRUNCATED
        return out^
    var data_base = header
    var data_len = len(packed) - header

    var previous = UInt64(0)
    for i in range(n_rows + 1):
        var offset = _read_u64(packed, bitmap_bytes + OFFSET_BYTES * i)
        if offset > UInt64(data_len):
            out.status = ARROW_OFFSET_OUT_OF_RANGE
            return out^
        if i > 0 and offset < previous:
            out.status = ARROW_OFFSETS_NOT_MONOTONE
            return out^
        if i == 0 and offset != UInt64(0):
            out.status = ARROW_OFFSETS_NOT_MONOTONE
            return out^
        previous = offset
    if previous != UInt64(data_len):
        out.status = ARROW_STRING_BYTES_MISMATCH
        return out^

    var values = List[String]()
    var mask = List[Bool]()
    for i in range(n_rows):
        var start = Int(_read_u64(packed, bitmap_bytes + OFFSET_BYTES * i))
        var end = Int(_read_u64(packed, bitmap_bytes + OFFSET_BYTES * (i + 1)))
        var present = is_valid_at_offset(packed, 0, i)
        mask.append(present)
        if not present:
            values.append("")  # never read: the mask says absent
            continue
        var raw = List[UInt8]()
        for k in range(start, end):
            raw.append(packed[data_base + k])
        values.append(bytes_to_string(raw))
    out.values = values^
    out.mask = mask^
    out.n_rows = n_rows
    return out^


def strings_identical(a: List[String], b: List[String]) -> Bool:
    """Byte-exact list equality, length compared first."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        var left = a[i].as_bytes()
        var right = b[i].as_bytes()
        if len(left) != len(right):
            return False
        for k in range(len(left)):
            if left[k] != right[k]:
                return False
    return True


def string_columns_identical(
    a_values: List[String], a_mask: List[Bool], b_values: List[String], b_mask: List[Bool]
) -> Bool:
    """Column equality for a nullable string column: same absences, same present bytes.

    An absent row carries NO bytes in this layout — `encode_string_column` gives it a
    zero-length range, exactly as Arrow does — so its original text is not transported
    and cannot be compared. Comparing it anyway is how a round-trip test starts
    demanding that a null preserve a value it was never supposed to carry; comparing the
    MASK is what actually pins the null/"" distinction, and that is checked first here.
    """
    if len(a_mask) != len(b_mask):
        return False
    for i in range(len(a_mask)):
        if a_mask[i] != b_mask[i]:
            return False
    if len(a_values) != len(b_values):
        return False
    for i in range(len(a_values)):
        if i < len(a_mask) and not a_mask[i]:
            continue
        var left = a_values[i].as_bytes()
        var right = b_values[i].as_bytes()
        if len(left) != len(right):
            return False
        for k in range(len(left)):
            if left[k] != right[k]:
                return False
    return True


def string_column_to_array(decoded: WireStrings) -> StringArray:
    """A decoded string column as `columnar.array.StringArray`."""
    var n = len(decoded.values)
    var bitmap = new_all_null(n)
    for i in range(n):
        if i < len(decoded.mask) and decoded.mask[i]:
            set_valid(bitmap, i)
    var owned = decoded.values.copy()
    return StringArray(ArcPointer(owned^), bitmap^, 0, n)


# ── the wire spelling ────────────────────────────────────────────────────────


def wire_base64(data: List[UInt8]) -> String:
    """Standard base64 (RFC 4648, `=` padded) of a raw byte buffer.

    `crypto.base64.b64_encode` is NOT reused, for a measured reason rather than taste:
    it takes a `String`, and a values buffer is arbitrary bytes including 0x00 and
    invalid UTF-8 sequences, which is not text. Passing bytes through a String to reach
    it would be a lossy detour around the very thing being encoded. It also builds its
    output by concatenating a one-character String per output byte.

    Built into a `List[UInt8]` and converted once, so the cost is one allocation rather
    than one per character.
    """
    var out = List[UInt8]()
    var alphabet = _B64_ALPHABET.as_bytes()
    var n = len(data)
    var i = 0
    while i + 3 <= n:
        var triple = (Int(data[i]) << 16) | (Int(data[i + 1]) << 8) | Int(data[i + 2])
        out.append(alphabet[(triple >> 18) & 63])
        out.append(alphabet[(triple >> 12) & 63])
        out.append(alphabet[(triple >> 6) & 63])
        out.append(alphabet[triple & 63])
        i += 3
    var remaining = n - i
    if remaining == 1:
        var triple = Int(data[i]) << 16
        out.append(alphabet[(triple >> 18) & 63])
        out.append(alphabet[(triple >> 12) & 63])
        out.append(UInt8(61))  # '='
        out.append(UInt8(61))
    elif remaining == 2:
        var triple = (Int(data[i]) << 16) | (Int(data[i + 1]) << 8)
        out.append(alphabet[(triple >> 18) & 63])
        out.append(alphabet[(triple >> 12) & 63])
        out.append(alphabet[(triple >> 6) & 63])
        out.append(UInt8(61))
    return bytes_to_string(out)


def wire_arg(data: List[UInt8]) -> String:
    """The buffer as the `"@u8:<base64>"` argument body, without the JSON quotes.

    The existing spelling, unchanged: `json_parser.json_parse_float64_list` recognises
    `@u8:` inside a JSON string token and decodes the rest as raw bytes in one pass.
    Quoting is the frame's job, not this function's.
    """
    return "@u8:" + wire_base64(data)


def arrow_status_name(status: Int) -> String:
    """The vocabulary for 310-329. See rule 4e on per-package ranges."""
    if status == ARROW_OK:
        return "ok"
    if status == ARROW_INVALID_ROW_COUNT:
        return "invalid_row_count"
    if status == ARROW_INVALID_COLUMN_COUNT:
        return "invalid_column_count"
    if status == ARROW_SCHEMA_TOO_SHORT:
        return "schema_too_short"
    if status == ARROW_UNSUPPORTED_DTYPE:
        return "unsupported_dtype"
    if status == ARROW_BUFFER_TRUNCATED:
        return "buffer_truncated"
    if status == ARROW_BUFFER_TRAILING_BYTES:
        return "buffer_trailing_bytes"
    if status == ARROW_NOT_A_BYTE:
        return "not_a_byte"
    if status == ARROW_RAGGED_BATCH:
        return "ragged_batch"
    if status == ARROW_OFFSETS_NOT_MONOTONE:
        return "offsets_not_monotone"
    if status == ARROW_OFFSET_OUT_OF_RANGE:
        return "offset_out_of_range"
    if status == ARROW_STRING_BYTES_MISMATCH:
        return "string_bytes_mismatch"
    return "unknown"
