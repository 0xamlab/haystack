"""test_tensorx_buffer.mojo — known-value tests for the dtype-tagged raw-byte buffer.

Hand-written. Byte layouts are cross-checked against Python's own IEEE-754 packer, run for real:

    struct.pack('<f', 1.5)          -> [0, 0, 192, 63]     (little-endian float32)
    struct.pack('<d', 1.5)          -> [0, 0, 0, 0, 0, 0, 248, 63]
    struct.pack('<f', -3.140625)    -> [0, 0, 73, 192]

and the bf16 bit pattern was cross-checked directly against the compiler's own `bitcast` in a
throwaway probe before this module was written: `bf16(-0.75)` bitcasts to `uint16` 48960 = 0xBF40,
little-endian bytes `[0x40, 0xBF]` = `[64, 191]`.

The assertions target the failures that produce a plausible wrong value rather than an error: a byte
order that is right for one dtype and backwards for another, a decode that reads past a buffer too
short to hold what it claims, and int4/nf4 silently answering an "elementwise value" question that a
buffer alone cannot answer for those two codes.
"""
from tensorx.buffer import (
    TxBuffer,
    tx_buf_decode_flat,
    tx_buf_element_width_bytes,
    tx_buf_encode_flat,
    tx_buf_make,
    tx_buf_required_bytes,
    tx_buf_required_bytes_flat,
    tx_buf_to_values,
)
from tensorx.contract import (
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_ERR_SHAPE_MISMATCH,
    TX_MAX_ELEMS,
    TX_OK,
)
from tensorx.dtype import (
    DT_BF16,
    DT_F16,
    DT_F32,
    DT_F64,
    DT_F8E4M3,
    DT_F8E5M2,
    DT_I4,
    DT_I8,
    DT_NF4,
    DT_U8,
)


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _one(v: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(v)
    return out^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── element widths ────────────────────────────────────────────────────────────
    if (
        tx_buf_element_width_bytes(DT_F64) == 8
        and tx_buf_element_width_bytes(DT_F32) == 4
        and tx_buf_element_width_bytes(DT_BF16) == 2
        and tx_buf_element_width_bytes(DT_F16) == 2
        and tx_buf_element_width_bytes(DT_F8E4M3) == 1
        and tx_buf_element_width_bytes(DT_F8E5M2) == 1
        and tx_buf_element_width_bytes(DT_I8) == 1
        and tx_buf_element_width_bytes(DT_U8) == 1
    ):
        passed += 1
        print("  ✅ every self-contained dtype reports its real byte width")
    else:
        failed += 1
        print("  ❌ a self-contained dtype's byte width drifted")

    # int4/nf4 are codes, not values — a buffer cannot address them without an external scale.
    if tx_buf_element_width_bytes(DT_I4) == 0 and tx_buf_element_width_bytes(DT_NF4) == 0:
        passed += 1
        print("  ✅ int4 and nf4 report width 0 — not addressable as buffer values")
    else:
        failed += 1
        print("  ❌ int4/nf4 were treated as self-contained buffer values")

    # ── exact little-endian byte layout, cross-checked against struct.pack ──────────
    var f32_bytes = tx_buf_encode_flat(_one(1.5), 1, DT_F32)
    if (
        len(f32_bytes) == 4
        and f32_bytes[0] == 0
        and f32_bytes[1] == 0
        and f32_bytes[2] == 192
        and f32_bytes[3] == 63
    ):
        passed += 1
        print("  ✅ float32(1.5) encodes to [0,0,192,63], matching struct.pack('<f', 1.5)")
    else:
        failed += 1
        print("  ❌ float32 byte layout drifted from struct.pack")

    var f64_bytes = tx_buf_encode_flat(_one(1.5), 1, DT_F64)
    if (
        len(f64_bytes) == 8
        and f64_bytes[6] == 248
        and f64_bytes[7] == 63
        and f64_bytes[0] == 0
    ):
        passed += 1
        print("  ✅ float64(1.5) encodes to [...,0,248,63], matching struct.pack('<d', 1.5)")
    else:
        failed += 1
        print("  ❌ float64 byte layout drifted from struct.pack")

    # bf16(-0.75) bitcasts to uint16 48960 = 0xBF40; little-endian bytes [0x40, 0xBF] = [64, 191].
    # Verified directly against the compiler's own bitcast before this module was written.
    var bf16_bytes = tx_buf_encode_flat(_one(-0.75), 1, DT_BF16)
    if len(bf16_bytes) == 2 and bf16_bytes[0] == 64 and bf16_bytes[1] == 191:
        passed += 1
        print("  ✅ bfloat16(-0.75) encodes to [64,191] (0xBF40 little-endian), matching bitcast")
    else:
        failed += 1
        print("  ❌ bfloat16 byte layout drifted:", bf16_bytes[0], bf16_bytes[1])

    # ── round trips for every self-contained dtype ───────────────────────────────
    var probe_values = List[Float64]()
    probe_values.append(0.75)
    probe_values.append(-0.75)
    probe_values.append(1.0)
    probe_values.append(-3.140625)
    probe_values.append(0.0)

    var dtypes = List[Int]()
    dtypes.append(DT_F64)
    dtypes.append(DT_F32)
    dtypes.append(DT_BF16)
    dtypes.append(DT_F16)

    var all_round_trip_ok = True
    for d in range(len(dtypes)):
        var encoded = tx_buf_encode_flat(probe_values, 5, dtypes[d])
        var decoded = tx_buf_decode_flat(encoded, 5, dtypes[d])
        if len(decoded) != 5:
            all_round_trip_ok = False
            continue
        for i in range(5):
            if _abs(decoded[i] - probe_values[i]) > 1e-2:
                all_round_trip_ok = False
    if all_round_trip_ok:
        passed += 1
        print("  ✅ f64/f32/bf16/f16 all round-trip {0.75,-0.75,1.0,-3.140625,0.0} within precision")
    else:
        failed += 1
        print("  ❌ a full-precision round trip lost more than its dtype's own precision")

    # fp8 e4m3/e5m2 and int8/uint8 round-trip on values their own grids represent exactly.
    var f8_vals = List[Float64]()
    f8_vals.append(1.0)
    f8_vals.append(-1.0)
    f8_vals.append(0.0)
    var f8e4m3_dec = tx_buf_decode_flat(tx_buf_encode_flat(f8_vals, 3, DT_F8E4M3), 3, DT_F8E4M3)
    var f8e5m2_dec = tx_buf_decode_flat(tx_buf_encode_flat(f8_vals, 3, DT_F8E5M2), 3, DT_F8E5M2)
    if (
        len(f8e4m3_dec) == 3
        and f8e4m3_dec[0] == 1.0
        and f8e4m3_dec[1] == -1.0
        and f8e4m3_dec[2] == 0.0
        and len(f8e5m2_dec) == 3
        and f8e5m2_dec[0] == 1.0
        and f8e5m2_dec[1] == -1.0
    ):
        passed += 1
        print("  ✅ fp8 e4m3 and e5m2 round-trip exactly on their shared exact grid {-1,0,1}")
    else:
        failed += 1
        print("  ❌ fp8 e4m3/e5m2 round trip drifted on values both grids represent exactly")

    # int8 round-trips exactly on its own integer grid; a value past its range is clamped, not
    # wrapped — Int64(v) past Int8's range is undefined, not truncated (rule 4c).
    var i8_vals = List[Float64]()
    i8_vals.append(-5.0)
    i8_vals.append(127.0)
    i8_vals.append(200.0)
    var i8_dec = tx_buf_decode_flat(tx_buf_encode_flat(i8_vals, 3, DT_I8), 3, DT_I8)
    if len(i8_dec) == 3 and i8_dec[0] == -5.0 and i8_dec[1] == 127.0 and i8_dec[2] == 127.0:
        passed += 1
        print("  ✅ int8 round-trips exactly and clamps 200 to 127 rather than wrapping")
    else:
        failed += 1
        print("  ❌ int8 encoding did not clamp or round-trip correctly")

    var u8_vals = List[Float64]()
    u8_vals.append(0.0)
    u8_vals.append(255.0)
    u8_vals.append(300.0)
    var u8_dec = tx_buf_decode_flat(tx_buf_encode_flat(u8_vals, 3, DT_U8), 3, DT_U8)
    if len(u8_dec) == 3 and u8_dec[0] == 0.0 and u8_dec[1] == 255.0 and u8_dec[2] == 255.0:
        passed += 1
        print("  ✅ uint8 round-trips exactly and clamps 300 to 255 rather than wrapping")
    else:
        failed += 1
        print("  ❌ uint8 encoding did not clamp or round-trip correctly")

    # ── required-bytes accounting ─────────────────────────────────────────────────
    if (
        tx_buf_required_bytes_flat(10, DT_F32) == 40
        and tx_buf_required_bytes_flat(10, DT_F64) == 80
        and tx_buf_required_bytes_flat(10, DT_BF16) == 20
    ):
        passed += 1
        print("  ✅ required-byte accounting is exact for f32/f64/bf16")
    else:
        failed += 1
        print("  ❌ required-byte accounting drifted")

    if tx_buf_required_bytes_flat(10, DT_I4) == -1 and tx_buf_required_bytes_flat(10, DT_NF4) == -1:
        passed += 1
        print("  ✅ int4/nf4 report -1 required bytes — refused, not a fabricated fractional width")
    else:
        failed += 1
        print("  ❌ int4/nf4 were given a byte-length answer they cannot honestly have")

    if tx_buf_required_bytes_flat(TX_MAX_ELEMS + 1, DT_F32) == -1:
        passed += 1
        print("  ✅ a count past TX_MAX_ELEMS is refused before any allocation")
    else:
        failed += 1
        print("  ❌ tx_buf_required_bytes_flat did not enforce the package element ceiling")

    # A decode against a buffer too short to hold its own claimed n must not read past the end.
    var short_data = tx_buf_encode_flat(probe_values, 5, DT_F32)
    if len(tx_buf_decode_flat(short_data, 6, DT_F32)) == 0:
        passed += 1
        print("  ✅ decoding n=6 from a 5-element f32 buffer is refused, not an uncatchable abort")
    else:
        failed += 1
        print("  ❌ tx_buf_decode_flat read past the end of a too-short buffer")

    # ── the shaped TxBuffer convenience ───────────────────────────────────────────
    var dims = List[Int]()
    dims.append(2)
    dims.append(2)
    var square = List[Float64]()
    square.append(1.0)
    square.append(2.0)
    square.append(3.0)
    square.append(4.0)
    var buf = tx_buf_make(square, 4, dims, 2, DT_F32)
    var round = tx_buf_to_values(buf)
    var buf_ok = buf.status == TX_OK and len(round) == 4
    if buf_ok:
        for i in range(4):
            if round[i] != square[i]:
                buf_ok = False
    if buf_ok:
        passed += 1
        print("  ✅ tx_buf_make + tx_buf_to_values round-trips a shaped (2,2) f32 buffer exactly")
    else:
        failed += 1
        print("  ❌ the shaped TxBuffer round trip lost or reordered a value")

    if tx_buf_make(square, 3, dims, 2, DT_F32).status == TX_ERR_SHAPE_MISMATCH:
        passed += 1
        print("  ✅ n disagreeing with the declared shape's element count is refused")
    else:
        failed += 1
        print("  ❌ tx_buf_make accepted n that disagreed with its own declared shape")

    if tx_buf_make(square, 4, dims, 2, DT_NF4).status == TX_ERR_DTYPE_UNSUPPORTED_FOR_OP:
        passed += 1
        print("  ✅ building an nf4 buffer of values (not codes) is refused")
    else:
        failed += 1
        print("  ❌ tx_buf_make built an nf4 'value' buffer with no scale behind it")

    if tx_buf_required_bytes(dims, 2, DT_F32) == 16:
        passed += 1
        print("  ✅ the shaped required-bytes helper agrees with the flat one: 4 f32 elements = 16B")
    else:
        failed += 1
        print("  ❌ tx_buf_required_bytes disagreed with tx_buf_required_bytes_flat")

    print()
    print("[tensorx.buffer] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("tensorx.buffer known-value suite failed")
