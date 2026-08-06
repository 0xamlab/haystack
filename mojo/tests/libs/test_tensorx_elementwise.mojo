"""test_tensorx_elementwise.mojo — known-value tests for broadcasting add/sub/mul/div and cast.

Hand-written. The broadcasting arithmetic is cross-checked against real numpy, run for real:

    a = [[1,2,3],[4,5,6]]  (float32, shape (2,3))
    b = [10,20,30]          (float32, shape (3,))
    a + b -> [[11,22,33],[14,25,36]]
    a - b -> [[-9,-18,-27],[-6,-15,-24]]
    a * b -> [[10,40,90],[40,100,180]]
    a / b -> [[0.1,0.1,0.1],[0.4,0.25,0.2]]   (float32 precision)

and the bf16 cast reference (`torch.float32(3.14159265).to(torch.bfloat16)` = `3.140625`) matches the
same native-cast path `tensorx.buffer` already uses.

The assertions target the failures that produce a plausible wrong tensor rather than an error: a
broadcast that pads on the wrong side, an implicit dtype promotion nobody asked for, and a
division-by-zero result that vanishes instead of being counted.
"""
from tensorx.contract import (
    TX_ERR_BROADCAST_INCOMPATIBLE,
    TX_ERR_DTYPE_MISMATCH,
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_OK,
)
from tensorx.buffer import tx_buf_decode_flat, tx_buf_encode_flat
from tensorx.dtype import DT_BF16, DT_F32, DT_F64, DT_NF4
from tensorx.elementwise import tx_ew_add, tx_ew_cast, tx_ew_div, tx_ew_mul, tx_ew_sub


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _vals6(v0: Float64, v1: Float64, v2: Float64, v3: Float64, v4: Float64, v5: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(v0)
    out.append(v1)
    out.append(v2)
    out.append(v3)
    out.append(v4)
    out.append(v5)
    return out^


def _dims2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


def _dims1(a: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    return out^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # a: (2,3) = [[1,2,3],[4,5,6]] ; b: (3,) = [10,20,30] — the numpy reference case.
    var a_vals = _vals6(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    var a_dims = _dims2(2, 3)
    var a_bytes = tx_buf_encode_flat(a_vals, 6, DT_F32)

    var b_vals = List[Float64]()
    b_vals.append(10.0)
    b_vals.append(20.0)
    b_vals.append(30.0)
    var b_dims = _dims1(3)
    var b_bytes = tx_buf_encode_flat(b_vals, 3, DT_F32)

    var add_r = tx_ew_add(a_bytes, a_dims, 2, DT_F32, b_bytes, b_dims, 1, DT_F32)
    var add_expected = _vals6(11.0, 22.0, 33.0, 14.0, 25.0, 36.0)
    var add_out = tx_buf_decode_flat(add_r.bytes, 6, DT_F32)
    var add_ok = add_r.status == TX_OK and len(add_r.dims) == 2 and add_r.dims[0] == 2 and add_r.dims[1] == 3
    if add_ok:
        for i in range(6):
            if add_out[i] != add_expected[i]:
                add_ok = False
    if add_ok:
        passed += 1
        print("  ✅ (2,3)+(3,) broadcasts to (2,3) matching numpy: [[11,22,33],[14,25,36]]")
    else:
        failed += 1
        print("  ❌ broadcasting add drifted from the numpy reference")

    var sub_r = tx_ew_sub(a_bytes, a_dims, 2, DT_F32, b_bytes, b_dims, 1, DT_F32)
    var sub_expected = _vals6(-9.0, -18.0, -27.0, -6.0, -15.0, -24.0)
    var sub_out = tx_buf_decode_flat(sub_r.bytes, 6, DT_F32)
    var sub_ok = sub_r.status == TX_OK
    if sub_ok:
        for i in range(6):
            if sub_out[i] != sub_expected[i]:
                sub_ok = False
    if sub_ok:
        passed += 1
        print("  ✅ (2,3)-(3,) matches numpy: [[-9,-18,-27],[-6,-15,-24]]")
    else:
        failed += 1
        print("  ❌ broadcasting sub drifted from the numpy reference")

    var mul_r = tx_ew_mul(a_bytes, a_dims, 2, DT_F32, b_bytes, b_dims, 1, DT_F32)
    var mul_expected = _vals6(10.0, 40.0, 90.0, 40.0, 100.0, 180.0)
    var mul_out = tx_buf_decode_flat(mul_r.bytes, 6, DT_F32)
    var mul_ok = mul_r.status == TX_OK
    if mul_ok:
        for i in range(6):
            if mul_out[i] != mul_expected[i]:
                mul_ok = False
    if mul_ok:
        passed += 1
        print("  ✅ (2,3)*(3,) matches numpy: [[10,40,90],[40,100,180]]")
    else:
        failed += 1
        print("  ❌ broadcasting mul drifted from the numpy reference")

    var div_r = tx_ew_div(a_bytes, a_dims, 2, DT_F32, b_bytes, b_dims, 1, DT_F32)
    var div_expected = _vals6(0.1, 0.1, 0.1, 0.4, 0.25, 0.2)
    var div_out = tx_buf_decode_flat(div_r.bytes, 6, DT_F32)
    var div_ok = div_r.status == TX_OK and div_r.n_non_finite == 0
    if div_ok:
        for i in range(6):
            # float32 precision: 0.1 is not exact, tolerate the storage-dtype's own epsilon.
            if _abs(div_out[i] - div_expected[i]) > 1e-6:
                div_ok = False
    if div_ok:
        passed += 1
        print("  ✅ (2,3)/(3,) matches numpy's float32 division within its own precision")
    else:
        failed += 1
        print("  ❌ broadcasting div drifted from the numpy reference")

    # ── dtype mismatch is refused, never implicitly promoted ────────────────────────
    var a_bytes_f64 = tx_buf_encode_flat(a_vals, 6, DT_F64)
    var mismatch = tx_ew_add(a_bytes_f64, a_dims, 2, DT_F64, b_bytes, b_dims, 1, DT_F32)
    if mismatch.status == TX_ERR_DTYPE_MISMATCH:
        passed += 1
        print("  ✅ f64 + f32 is refused as a dtype mismatch, never silently promoted")
    else:
        failed += 1
        print("  ❌ a cross-dtype op was not refused")

    # ── int4/nf4 have no self-contained value, so elementwise ops on them are refused ─
    var nf4_result = tx_ew_add(a_bytes, a_dims, 2, DT_NF4, a_bytes, a_dims, 2, DT_NF4)
    if nf4_result.status == TX_ERR_DTYPE_UNSUPPORTED_FOR_OP:
        passed += 1
        print("  ✅ elementwise add on nf4 is refused — no scale, no value")
    else:
        failed += 1
        print("  ❌ nf4 was accepted as an elementwise-addable dtype")

    # ── incompatible shapes are refused, matching tensorx.shape ──────────────────────
    var c_dims = _dims2(3, 2)  # (3,2) vs a's (2,3): not broadcastable
    var c_bytes = tx_buf_encode_flat(a_vals, 6, DT_F32)
    var incompat = tx_ew_add(a_bytes, a_dims, 2, DT_F32, c_bytes, c_dims, 2, DT_F32)
    if incompat.status == TX_ERR_BROADCAST_INCOMPATIBLE:
        passed += 1
        print("  ✅ (2,3) vs (3,2) elementwise add is refused as broadcast-incompatible")
    else:
        failed += 1
        print("  ❌ an incompatible shape pair was not refused")

    # ── division by zero is COUNTED, not silently dropped ───────────────────────────
    var zeros = List[Float64]()
    zeros.append(0.0)
    zeros.append(0.0)
    zeros.append(0.0)
    var zero_bytes = tx_buf_encode_flat(zeros, 3, DT_F32)
    var div_by_zero = tx_ew_div(a_bytes, a_dims, 2, DT_F32, zero_bytes, b_dims, 1, DT_F32)
    if div_by_zero.status == TX_OK and div_by_zero.n_non_finite == 6:
        passed += 1
        print("  ✅ dividing all 6 elements by zero reports n_non_finite=6, not a silent result")
    else:
        failed += 1
        print("  ❌ division by zero was not counted:", div_by_zero.n_non_finite)

    # ── explicit cast, cross-checked against torch's own bf16 rounding ──────────────
    var pi_vals = List[Float64]()
    pi_vals.append(3.14159265)
    var pi_bytes = tx_buf_encode_flat(pi_vals, 1, DT_F32)
    var cast_bytes = tx_ew_cast(pi_bytes, 1, DT_F32, DT_BF16)
    var cast_back = tx_buf_decode_flat(cast_bytes, 1, DT_BF16)
    if len(cast_back) == 1 and cast_back[0] == 3.140625:
        passed += 1
        print("  ✅ casting pi f32->bf16 gives 3.140625, matching torch's own bf16 rounding")
    else:
        failed += 1
        print("  ❌ tx_ew_cast drifted from the reference bf16 rounding")

    # int4/nf4 have no self-contained value to cast either direction.
    if len(tx_ew_cast(pi_bytes, 1, DT_F32, DT_NF4)) == 0 and len(tx_ew_cast(pi_bytes, 1, DT_NF4, DT_F32)) == 0:
        passed += 1
        print("  ✅ casting to or from nf4 is refused, not a fabricated code with no scale")
    else:
        failed += 1
        print("  ❌ tx_ew_cast accepted nf4 as a castable dtype")

    # A byte buffer too short for its claimed n must not be read past the end.
    var short = tx_buf_encode_flat(pi_vals, 1, DT_F32)
    if len(tx_ew_cast(short, 5, DT_F32, DT_F64)) == 0:
        passed += 1
        print("  ✅ casting n=5 from a 1-element f32 buffer is refused, not an uncatchable abort")
    else:
        failed += 1
        print("  ❌ tx_ew_cast read past the end of a too-short buffer")

    print()
    print("[tensorx.elementwise] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("tensorx.elementwise known-value suite failed")
