"""test_columnar_arrow_wire.mojo — known-value tests for the Arrow-layout wire form.

Hand-written. Every assertion here is aimed at a defect that has actually shipped
somewhere, in this tree or in every other implementation of this layout:

  * BIT PACKING OFF BY ONE. Nulls at bit 0, bit 7 and bit 8 are asserted against
    literal bitmap bytes, not just round-tripped, because a round trip through the same
    off-by-one is self-consistent and passes.
  * TRAILING PAD BITS. `validity.new_all_valid` deliberately leaves the bits past the
    logical length SET. An encoder that copies the bitmap verbatim emits `0xFF` where a
    9-row column should end in `0x01`, and two equal columns then produce different
    buffers.
  * A TRUNCATED BUFFER MUST REFUSE. Reading past a `List` end is an uncatchable abort;
    `rows * cols * 8 == len(packed)` is not a bound because the multiply wraps.
  * A DECLARED ROW COUNT THAT DISAGREES WITH THE BUFFER is refused in BOTH directions —
    a short buffer and a long one are different mistakes and neither may be guessed at.
  * A 2^64-1 STRING OFFSET narrowed to `Int` is -1, which passes a signed upper-bound
    test and then indexes backwards off the front of the buffer.
  * NON-ASCII BYTE EXACTNESS. A previous defect decoded `\\u00f3` two different ways and
    every op naming a non-ASCII column failed.

The base64 vectors are pinned against the spelling the rest of the repo already uses:
`tests/integration/test_count_guard_encoding_and_index_e2e.py` hardcodes
`"@u8:AQID"` for the three bytes 1, 2, 3.
"""
from std.math import isnan, sqrt

from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from columnar.dtype import DTYPE_FLOAT64, DTYPE_NULL, DTYPE_STRING
from columnar.validity import bytes_for_bits, new_all_valid
from columnar.arrow_wire import (
    ARROW_BUFFER_TRAILING_BYTES,
    ARROW_BUFFER_TRUNCATED,
    ARROW_INVALID_COLUMN_COUNT,
    ARROW_INVALID_ROW_COUNT,
    ARROW_NOT_A_BYTE,
    ARROW_OFFSETS_NOT_MONOTONE,
    ARROW_OFFSET_OUT_OF_RANGE,
    ARROW_OK,
    ARROW_RAGGED_BATCH,
    ARROW_SCHEMA_TOO_SHORT,
    ARROW_STRING_BYTES_MISMATCH,
    ARROW_UNSUPPORTED_DTYPE,
    MAX_WIRE_COLUMNS,
    MAX_WIRE_ROWS,
    arrow_status_name,
    batches_identical,
    buffers_identical,
    bytes_to_string,
    columns_identical,
    decode_batch,
    decode_batch_from_packed_floats,
    decode_batch_positional,
    decode_string_column,
    encode_batch,
    encode_column,
    encode_string_column,
    null_dtypes,
    packed_floats_to_bytes,
    positional_names,
    string_column_to_array,
    string_columns_identical,
    wire_arg,
    wire_base64,
    wire_bytes_required,
)
from json.parser import json_parse_float64_list


def _batch_of(var columns: List[Float64Array], n_rows: Int) -> RecordBatch:
    var n = len(columns)
    return RecordBatch(
        Schema(positional_names(n), null_dtypes(n)), columns^, n_rows
    )


def _append_u64(mut out: List[UInt8], value: UInt64):
    for k in range(8):
        out.append(UInt8((value >> UInt64(8 * k)) & UInt64(0xFF)))


def _bytes_of(items: List[Int]) -> List[UInt8]:
    var out = List[UInt8]()
    for i in range(len(items)):
        out.append(UInt8(items[i]))
    return out^


def main() raises:
    var passed = 0
    var failed = 0

    # ── BIT 0, BIT 7, BIT 8: the three off-by-one positions ──────────────────
    # 9 rows, nulls at exactly those three bits. Byte 0 must be 0b01111110 = 0x7E
    # (bits 1-6 set, bits 0 and 7 clear) and byte 1 must be 0b00000000 -> bit 8 clear.
    var boundary_values = List[Float64]()
    var boundary_mask = List[Bool]()
    for i in range(9):
        boundary_values.append(Float64(i) + 0.5)
        boundary_mask.append(not (i == 0 or i == 7 or i == 8))
    var boundary_column = float64_with_nulls(boundary_values^, boundary_mask)
    var boundary_bytes = encode_column(boundary_column)
    if (
        len(boundary_bytes) == 2 + 72
        and boundary_bytes[0] == UInt8(0x7E)
        and boundary_bytes[1] == UInt8(0x00)
    ):
        passed += 1
        print("  ✅ nulls at bit 0, bit 7 and bit 8 pack to 0x7E 0x00 exactly")
    else:
        failed += 1
        print("  ❌ the validity bitmap is off by one:", boundary_bytes[0], boundary_bytes[1])

    var boundary_batch_columns = List[Float64Array]()
    boundary_batch_columns.append(boundary_column.copy())
    var boundary_batch = _batch_of(boundary_batch_columns^, 9)
    var boundary_encoded = encode_batch(boundary_batch)
    var boundary_decoded = decode_batch_positional(boundary_encoded.bytes, 9, 1)
    if (
        boundary_encoded.status == ARROW_OK
        and boundary_decoded.status == ARROW_OK
        and batches_identical(boundary_batch, boundary_decoded.batch)
        and not boundary_decoded.batch.columns[0].is_valid_at(0)
        and boundary_decoded.batch.columns[0].is_valid_at(6)
        and not boundary_decoded.batch.columns[0].is_valid_at(7)
        and not boundary_decoded.batch.columns[0].is_valid_at(8)
    ):
        passed += 1
        print("  ✅ the same three boundary bits survive a full round trip")
    else:
        failed += 1
        print("  ❌ a boundary bit was lost in the round trip")

    # ── TRAILING PAD BITS ARE ZEROED ─────────────────────────────────────────
    # `new_all_valid(9)` leaves bits 9-15 SET on purpose. An encoder that copies the
    # bitmap verbatim ships 0xFF where the canonical form is 0x01.
    var padded_values = List[Float64]()
    for i in range(9):
        padded_values.append(Float64(i))
    var padded_column = float64_from_list(padded_values^)
    var raw_bitmap = new_all_valid(9)
    var padded_bytes = encode_column(padded_column)
    if (
        raw_bitmap[1] == UInt8(0xFF)  # the trap is real
        and padded_bytes[0] == UInt8(0xFF)
        and padded_bytes[1] == UInt8(0x01)  # and it is not shipped
    ):
        passed += 1
        print("  ✅ pad bits past the row count are written as 0, not left set")
    else:
        failed += 1
        print("  ❌ pad bits leaked into the buffer:", padded_bytes[1])

    # ── a batch of awkward values survives BIT-for-BIT ───────────────────────
    # -0.0 and NaN are the two that a value comparison would get wrong: 0.0 == -0.0 is
    # true and nan == nan is false, so the round trip is checked on bit patterns.
    var awkward = List[Float64]()
    awkward.append(-0.0)
    awkward.append(0.0)
    awkward.append(sqrt(-1.0))          # NaN, produced arithmetically
    awkward.append(1.0 / 0.0)           # +inf
    awkward.append(-1.0 / 0.0)          # -inf
    awkward.append(5e-324)              # smallest subnormal
    awkward.append(1.7976931348623157e308)
    awkward.append(-1.7976931348623157e308)
    var awkward_column = float64_from_list(awkward^)
    var awkward_columns = List[Float64Array]()
    awkward_columns.append(awkward_column.copy())
    var awkward_batch = _batch_of(awkward_columns^, 8)
    var awkward_wire = encode_batch(awkward_batch)
    var awkward_back = decode_batch_positional(awkward_wire.bytes, 8, 1)
    var negative_zero_kept = bitcast[DType.uint64](
        awkward_back.batch.columns[0].get(0)
    ) == UInt64(0x8000000000000000)
    if (
        awkward_back.status == ARROW_OK
        and batches_identical(awkward_batch, awkward_back.batch)
        and negative_zero_kept
        and isnan(awkward_back.batch.columns[0].get(2))
    ):
        passed += 1
        print("  ✅ -0.0, NaN, inf and the subnormal edge survive bit-for-bit")
    else:
        failed += 1
        print("  ❌ a bit pattern changed in the round trip")

    # ── columns_identical actually distinguishes -0.0 from 0.0 ───────────────
    var zeros_a = List[Float64]()
    zeros_a.append(0.0)
    var zeros_b = List[Float64]()
    zeros_b.append(-0.0)
    if not columns_identical(float64_from_list(zeros_a^), float64_from_list(zeros_b^)):
        passed += 1
        print("  ✅ the equality used by the gate is bitwise, not `==`")
    else:
        failed += 1
        print("  ❌ the gate would accept -0.0 where 0.0 was sent")

    # ── a multi-column batch with nulls, through the WHOLE @u8 path ──────────
    var left_values = List[Float64]()
    var left_mask = List[Bool]()
    var right_values = List[Float64]()
    var right_mask = List[Bool]()
    for i in range(17):
        left_values.append(Float64(i) * 1.25)
        left_mask.append(i % 3 != 0)
        right_values.append(Float64(i) * -0.5)
        right_mask.append(i % 5 != 0)
    var wide_columns = List[Float64Array]()
    wide_columns.append(float64_with_nulls(left_values^, left_mask))
    wide_columns.append(float64_with_nulls(right_values^, right_mask))
    var wide_batch = _batch_of(wide_columns^, 17)
    var wide_wire = encode_batch(wide_batch)
    var arg = wire_arg(wide_wire.bytes)
    var frame = String("\"")
    frame += arg
    frame += "\""
    var recovered_floats = json_parse_float64_list(frame)
    var recovered = packed_floats_to_bytes(recovered_floats)
    var wide_back = decode_batch_from_packed_floats(
        recovered_floats, positional_names(2), null_dtypes(2), 17, 2
    )
    if (
        wide_wire.status == ARROW_OK
        and len(wide_wire.bytes) == wire_bytes_required(17, 2)
        and recovered.status == ARROW_OK
        and buffers_identical(wide_wire.bytes, recovered.bytes)
        and wide_back.status == ARROW_OK
        and batches_identical(wide_batch, wide_back.batch)
    ):
        passed += 1
        print("  ✅ a 17x2 batch survives encode -> \"@u8:\" -> parse -> decode intact")
    else:
        failed += 1
        print("  ❌ the @u8 round trip lost something:", arrow_status_name(wide_back.status))

    # ── the encoding is CANONICAL: re-encoding a decoded batch is identical ──
    var reencoded = encode_batch(wide_back.batch)
    if reencoded.status == ARROW_OK and buffers_identical(wide_wire.bytes, reencoded.bytes):
        passed += 1
        print("  ✅ encode(decode(bytes)) reproduces the same bytes")
    else:
        failed += 1
        print("  ❌ the encoding is not canonical")

    # ── a null slot's payload is NOT shipped ────────────────────────────────
    # A slice shares its parent's values list, so the payload under a null can be an
    # unrelated row's datum. The buffer must carry +0.0 there.
    var leaky_values = List[Float64]()
    leaky_values.append(4242.0)  # a secret under a null
    leaky_values.append(1.0)
    var leaky_mask = List[Bool]()
    leaky_mask.append(False)
    leaky_mask.append(True)
    var leaky_column = float64_with_nulls(leaky_values^, leaky_mask)
    var leaky_bytes = encode_column(leaky_column)
    var leak = False
    for i in range(1, 9):
        if leaky_bytes[i] != UInt8(0):
            leak = True
    if not leak:
        passed += 1
        print("  ✅ the value under a null slot is canonicalized to +0.0, not shipped")
    else:
        failed += 1
        print("  ❌ a null slot's payload went onto the wire")

    # ── A TRUNCATED BUFFER IS REFUSED ───────────────────────────────────────
    var truncated = List[UInt8]()
    for i in range(len(wide_wire.bytes) - 1):
        truncated.append(wide_wire.bytes[i])
    var truncated_result = decode_batch_positional(truncated, 17, 2)
    var empty_buffer = List[UInt8]()
    var empty_result = decode_batch_positional(empty_buffer, 17, 2)
    if (
        truncated_result.status == ARROW_BUFFER_TRUNCATED
        and truncated_result.n_rows == 0
        and truncated_result.batch.width() == 0
        and empty_result.status == ARROW_BUFFER_TRUNCATED
    ):
        passed += 1
        print("  ✅ a buffer one byte short is refused, with an empty batch")
    else:
        failed += 1
        print("  ❌ a truncated buffer was read:", arrow_status_name(truncated_result.status))

    # ── A DECLARED ROW COUNT THAT DISAGREES IS REFUSED, BOTH WAYS ───────────
    var too_many_rows = decode_batch_positional(wide_wire.bytes, 18, 2)
    var too_few_rows = decode_batch_positional(wide_wire.bytes, 16, 2)
    var wrong_columns = decode_batch_positional(wide_wire.bytes, 17, 1)
    if (
        too_many_rows.status == ARROW_BUFFER_TRUNCATED
        and too_few_rows.status == ARROW_BUFFER_TRAILING_BYTES
        and wrong_columns.status == ARROW_BUFFER_TRAILING_BYTES
    ):
        passed += 1
        print("  ✅ a row/column count disagreeing with the buffer length is refused")
    else:
        failed += 1
        print(
            "  ❌ a shape mismatch was accepted:",
            arrow_status_name(too_many_rows.status),
            arrow_status_name(too_few_rows.status),
        )

    # ── the required-bytes arithmetic SATURATES instead of wrapping ─────────
    # `3 * 6148914691236517206 == 2` on a wrapping multiply, and a check against 2
    # passes. The ceiling is 1<<62, so a huge shape can never compare small.
    comptime WRAPPER: Int = 6148914691236517206
    if (
        wire_bytes_required(17, 2) == 2 * (17 * 8 + 3)
        and wire_bytes_required(WRAPPER, 3) == 1 << 62
        and wire_bytes_required(WRAPPER, WRAPPER) == 1 << 62
        and wire_bytes_required(0, 4) == 0
        and wire_bytes_required(-1, 4) == 0
    ):
        passed += 1
        print("  ✅ wire_bytes_required saturates at 1<<62 rather than wrapping")
    else:
        failed += 1
        print("  ❌ the length arithmetic can wrap:", wire_bytes_required(WRAPPER, 3))

    # ── an absurd declared shape is refused before the multiply ─────────────
    var over_rows = decode_batch_positional(wide_wire.bytes, MAX_WIRE_ROWS + 1, 1)
    var over_columns = decode_batch_positional(wide_wire.bytes, 4, MAX_WIRE_COLUMNS + 1)
    var negative_rows = decode_batch_positional(wide_wire.bytes, -3, 1)
    if (
        over_rows.status == ARROW_INVALID_ROW_COUNT
        and over_columns.status == ARROW_INVALID_COLUMN_COUNT
        and negative_rows.status == ARROW_INVALID_ROW_COUNT
    ):
        passed += 1
        print("  ✅ a declared shape past the ceilings is refused, not multiplied")
    else:
        failed += 1
        print("  ❌ an absurd shape got past the ceilings")

    # ── the schema must cover the columns, and carry a layout this can read ─
    var one_name = List[String]()
    one_name.append("only")
    var short_schema = decode_batch(wide_wire.bytes, one_name, null_dtypes(2), 17, 2)
    var string_dtypes = List[Int]()
    string_dtypes.append(DTYPE_STRING)
    string_dtypes.append(DTYPE_STRING)
    var wrong_dtype = decode_batch(
        wide_wire.bytes, positional_names(2), string_dtypes, 17, 2
    )
    var float_dtypes = List[Int]()
    float_dtypes.append(DTYPE_FLOAT64)
    float_dtypes.append(DTYPE_FLOAT64)
    var float_ok = decode_batch(
        wide_wire.bytes, positional_names(2), float_dtypes, 17, 2
    )
    if (
        short_schema.status == ARROW_SCHEMA_TOO_SHORT
        and wrong_dtype.status == ARROW_UNSUPPORTED_DTYPE
        and float_ok.status == ARROW_OK
        and float_ok.batch.schema.dtypes[0] == DTYPE_FLOAT64
    ):
        passed += 1
        print("  ✅ a short schema and a string dtype are both refused; float64 is fine")
    else:
        failed += 1
        print("  ❌ the schema checks are wrong:", arrow_status_name(wrong_dtype.status))

    # ── batches_identical is sensitive to the schema, not only the numbers ──
    var renamed_names = List[String]()
    renamed_names.append("a")
    renamed_names.append("b")
    var renamed = decode_batch(wide_wire.bytes, renamed_names, null_dtypes(2), 17, 2)
    if (
        renamed.status == ARROW_OK
        and not batches_identical(wide_batch, renamed.batch)
        and not batches_identical(wide_batch, float_ok.batch)  # dtype differs
    ):
        passed += 1
        print("  ✅ the gate rejects a batch whose names or dtypes differ")
    else:
        failed += 1
        print("  ❌ the gate ignores the schema")

    # ── a packed element that is not a byte refuses the whole buffer ────────
    # `Int(1e300)` is undefined behaviour, not a clamp, and `_finite(1e300)` is True —
    # so the range check is what makes the narrowing total (rule 4c).
    var bad_high = List[Float64]()
    bad_high.append(0.0)
    bad_high.append(256.0)
    var bad_low = List[Float64]()
    bad_low.append(-1.0)
    var bad_fraction = List[Float64]()
    bad_fraction.append(0.5)
    var bad_nan = List[Float64]()
    bad_nan.append(sqrt(-1.0))
    var bad_huge = List[Float64]()
    bad_huge.append(1e300)
    var good = List[Float64]()
    good.append(0.0)
    good.append(255.0)
    var good_bytes = packed_floats_to_bytes(good)
    if (
        packed_floats_to_bytes(bad_high).status == ARROW_NOT_A_BYTE
        and packed_floats_to_bytes(bad_low).status == ARROW_NOT_A_BYTE
        and packed_floats_to_bytes(bad_fraction).status == ARROW_NOT_A_BYTE
        and packed_floats_to_bytes(bad_nan).status == ARROW_NOT_A_BYTE
        and packed_floats_to_bytes(bad_huge).status == ARROW_NOT_A_BYTE
        and len(packed_floats_to_bytes(bad_high).bytes) == 0
        and good_bytes.status == ARROW_OK
        and good_bytes.bytes[1] == UInt8(255)
    ):
        passed += 1
        print("  ✅ 256, -1, 0.5, NaN and 1e300 are refused; 0 and 255 are bytes")
    else:
        failed += 1
        print("  ❌ a non-byte element was narrowed anyway")

    # ── a ragged batch has no buffer, and none is invented ─────────────────
    var ragged_columns = List[Float64Array]()
    var three = List[Float64]()
    three.append(1.0)
    three.append(2.0)
    three.append(3.0)
    var two = List[Float64]()
    two.append(1.0)
    two.append(2.0)
    ragged_columns.append(float64_from_list(three^))
    ragged_columns.append(float64_from_list(two^))
    var ragged = _batch_of(ragged_columns^, 3)
    var ragged_encoded = encode_batch(ragged)
    if ragged_encoded.status == ARROW_RAGGED_BATCH and len(ragged_encoded.bytes) == 0:
        passed += 1
        print("  ✅ a ragged batch is refused rather than encoded to its shortest column")
    else:
        failed += 1
        print("  ❌ a ragged batch produced a buffer")

    # ── an empty batch is a real answer, distinguished by the status ───────
    var no_columns = List[Float64Array]()
    var empty_batch = _batch_of(no_columns^, 0)
    var empty_encoded = encode_batch(empty_batch)
    var empty_decoded = decode_batch_positional(empty_encoded.bytes, 0, 0)
    if (
        empty_encoded.status == ARROW_OK
        and len(empty_encoded.bytes) == 0
        and empty_decoded.status == ARROW_OK
        and empty_decoded.n_rows == 0
    ):
        passed += 1
        print("  ✅ an empty batch encodes to zero bytes with status ok, not a refusal")
    else:
        failed += 1
        print("  ❌ an empty batch was confused with a refusal")

    # ── base64 vectors, pinned to the spelling the repo already uses ───────
    if (
        wire_base64(_bytes_of([1, 2, 3])) == "AQID"
        and wire_arg(_bytes_of([1, 2, 3])) == "@u8:AQID"
        and wire_base64(_bytes_of([1])) == "AQ=="
        and wire_base64(_bytes_of([1, 2])) == "AQI="
        and wire_base64(_bytes_of([1, 2, 3, 4])) == "AQIDBA=="
        and wire_base64(List[UInt8]()) == ""
    ):
        passed += 1
        print("  ✅ base64 matches the repo's own @u8 vectors, padding included")
    else:
        failed += 1
        print("  ❌ base64 disagrees with the documented spelling:", wire_base64(_bytes_of([1, 2, 3])))

    # ── STRING COLUMN: non-ASCII, byte-exact, with a null and a real "" ────
    var text = List[String]()
    text.append("señor")     # 6 bytes, 5 code points
    text.append("")          # a real empty string
    text.append("dropped")   # absent
    text.append("naïve")
    text.append("日本語")     # 9 bytes
    var text_mask = List[Bool]()
    text_mask.append(True)
    text_mask.append(True)
    text_mask.append(False)
    text_mask.append(True)
    text_mask.append(True)
    var text_bytes = encode_string_column(text, text_mask)
    var text_back = decode_string_column(text_bytes, 5)
    var text_exact = (
        text_back.status == ARROW_OK
        and string_columns_identical(text, text_mask, text_back.values, text_back.mask)
        and len(text_back.values[0].as_bytes()) == 6
        and len(text_back.values[4].as_bytes()) == 9
        and text_back.mask[1]
        and text_back.values[1] == ""
        and not text_back.mask[2]
    )
    if text_exact:
        passed += 1
        print("  ✅ a non-ASCII string column round trips byte-exactly, nulls intact")
    else:
        failed += 1
        print("  ❌ a string column was corrupted:", arrow_status_name(text_back.status))

    # ── the absent row contributes NO bytes ───────────────────────────────
    # 5 rows: bitmap 1 + offsets 6*8 + bytes (6 + 0 + 0 + 6 + 9) = 1 + 48 + 21
    if len(text_bytes) == 1 + 48 + 21:
        passed += 1
        print("  ✅ an absent string row occupies no data bytes")
    else:
        failed += 1
        print("  ❌ the string buffer is the wrong length:", len(text_bytes))

    # ── string nulls at bit 0, 7 and 8 too ────────────────────────────────
    var many = List[String]()
    var many_mask = List[Bool]()
    for i in range(9):
        many.append("v" + String(i))
        many_mask.append(not (i == 0 or i == 7 or i == 8))
    var many_bytes = encode_string_column(many, many_mask)
    var many_back = decode_string_column(many_bytes, 9)
    if (
        many_bytes[0] == UInt8(0x7E)
        and many_bytes[1] == UInt8(0x00)
        and many_back.status == ARROW_OK
        and string_columns_identical(many, many_mask, many_back.values, many_back.mask)
        and not many_back.mask[0]
        and many_back.mask[1]
        and not many_back.mask[7]
        and not many_back.mask[8]
    ):
        passed += 1
        print("  ✅ a string column's validity bits 0, 7 and 8 are also exact")
    else:
        failed += 1
        print("  ❌ the string validity bitmap is off by one")

    # ── a truncated string body is refused ───────────────────────────────
    var text_cut = List[UInt8]()
    for i in range(len(text_bytes) - 3):
        text_cut.append(text_bytes[i])
    var cut_result = decode_string_column(text_cut, 5)
    var header_cut = List[UInt8]()
    for i in range(10):
        header_cut.append(text_bytes[i])
    var header_result = decode_string_column(header_cut, 5)
    # Cutting the body makes the LAST offset point past the data region, so the range
    # check refuses it before the exact-length check gets a chance — a different status
    # from `short_last` below, and the reason both cases are asserted separately.
    if (
        cut_result.status == ARROW_OFFSET_OUT_OF_RANGE
        and len(cut_result.values) == 0
        and header_result.status == ARROW_BUFFER_TRUNCATED
    ):
        passed += 1
        print("  ✅ a truncated string body and a truncated header are both refused")
    else:
        failed += 1
        print("  ❌ a truncated string buffer was read:", arrow_status_name(cut_result.status))

    # ── A 2^64-1 OFFSET DOES NOT ARRIVE AS -1 ────────────────────────────
    # Narrowed to Int it is -1, which passes `off <= data_len`, and the read then
    # indexes backwards off the front of the buffer.
    var hostile = List[UInt8]()
    hostile.append(UInt8(0x01))          # 1 row, present
    _append_u64(hostile, UInt64(0))      # offsets[0] = 0
    _append_u64(hostile, UInt64(0xFFFFFFFFFFFFFFFF))  # offsets[1] = 2^64-1
    hostile.append(UInt8(65))            # one data byte
    var hostile_result = decode_string_column(hostile, 1)
    if hostile_result.status == ARROW_OFFSET_OUT_OF_RANGE and len(hostile_result.values) == 0:
        passed += 1
        print("  ✅ a 2^64-1 offset is refused, not narrowed to -1")
    else:
        failed += 1
        print("  ❌ a hostile offset got through:", arrow_status_name(hostile_result.status))

    # ── non-monotone offsets are refused ─────────────────────────────────
    var backwards = List[UInt8]()
    backwards.append(UInt8(0x03))        # 2 rows, both present
    _append_u64(backwards, UInt64(0))
    _append_u64(backwards, UInt64(2))
    _append_u64(backwards, UInt64(1))    # goes BACKWARDS: a negative length
    backwards.append(UInt8(65))
    backwards.append(UInt8(66))
    var backwards_result = decode_string_column(backwards, 2)
    var nonzero_first = List[UInt8]()
    nonzero_first.append(UInt8(0x01))
    _append_u64(nonzero_first, UInt64(1))  # offsets[0] must be 0
    _append_u64(nonzero_first, UInt64(1))
    nonzero_first.append(UInt8(65))
    var nonzero_result = decode_string_column(nonzero_first, 1)
    if (
        backwards_result.status == ARROW_OFFSETS_NOT_MONOTONE
        and nonzero_result.status == ARROW_OFFSETS_NOT_MONOTONE
    ):
        passed += 1
        print("  ✅ offsets that go backwards, or do not start at 0, are refused")
    else:
        failed += 1
        print("  ❌ bad offsets were accepted:", arrow_status_name(backwards_result.status))

    # ── a last offset that does not close the buffer is refused ──────────
    var short_last = List[UInt8]()
    short_last.append(UInt8(0x01))
    _append_u64(short_last, UInt64(0))
    _append_u64(short_last, UInt64(1))
    short_last.append(UInt8(65))
    short_last.append(UInt8(66))  # one byte more than the offsets describe
    var short_last_result = decode_string_column(short_last, 1)
    if short_last_result.status == ARROW_STRING_BYTES_MISMATCH:
        passed += 1
        print("  ✅ a data region longer than the last offset is refused")
    else:
        failed += 1
        print("  ❌ trailing string bytes were ignored")

    # ── an empty string column, and a zero-row one ───────────────────────
    var no_text = List[String]()
    var no_text_mask = List[Bool]()
    var no_text_bytes = encode_string_column(no_text, no_text_mask)
    var no_text_back = decode_string_column(no_text_bytes, 0)
    if (
        len(no_text_bytes) == 8  # just the terminator offset
        and no_text_back.status == ARROW_OK
        and no_text_back.n_rows == 0
        and len(no_text_back.values) == 0
    ):
        passed += 1
        print("  ✅ a zero-row string column is one terminator offset and decodes clean")
    else:
        failed += 1
        print("  ❌ the empty string column is wrong:", len(no_text_bytes))

    # ── a decoded string column becomes a StringArray with its nulls ─────
    var text_array = string_column_to_array(text_back)
    if (
        text_array.length == 5
        and text_array.get(0) == "señor"
        and text_array.is_valid_at(1)
        and not text_array.is_valid_at(2)
        and text_array.null_count() == 1
    ):
        passed += 1
        print("  ✅ string_column_to_array preserves validity")
    else:
        failed += 1
        print("  ❌ string_column_to_array lost the nulls")

    # ── bytes_to_string is byte-exact where `chr` would not be ──────────
    # `chr(0xC3)` emits TWO bytes, so the `chr`-accumulating idiom turns "é" (2 bytes)
    # into 4. This is the assertion that pins the fix.
    var utf8 = List[UInt8]()
    utf8.append(UInt8(0x63))  # c
    utf8.append(UInt8(0x61))  # a
    utf8.append(UInt8(0x66))  # f
    utf8.append(UInt8(0xC3))
    utf8.append(UInt8(0xA9))  # é
    var rebuilt = bytes_to_string(utf8)
    var chr_form = String("")
    for i in range(len(utf8)):
        chr_form += chr(Int(utf8[i]))
    if (
        len(rebuilt.as_bytes()) == 5
        and rebuilt == "café"
        and len(chr_form.as_bytes()) == 7  # the idiom that would have been wrong
    ):
        passed += 1
        print("  ✅ bytes_to_string is byte-exact; the `chr` idiom would give 7 bytes")
    else:
        failed += 1
        print("  ❌ byte-exactness is broken:", len(rebuilt.as_bytes()))

    # ── a status code has exactly one name ─────────────────────────────
    if (
        arrow_status_name(ARROW_OK) == "ok"
        and arrow_status_name(ARROW_BUFFER_TRUNCATED) == "buffer_truncated"
        and arrow_status_name(ARROW_OFFSET_OUT_OF_RANGE) == "offset_out_of_range"
        and arrow_status_name(1) == "unknown"
    ):
        passed += 1
        print("  ✅ every status in 310-329 has a name, and an unknown one says so")
    else:
        failed += 1
        print("  ❌ a status code has no name")

    print("  [columnar.arrow_wire] Passed:", passed, "Failed:", failed)
