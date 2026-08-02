"""test_tensorx_reduce.mojo — known-value tests for dtype-aware, wide-accumulating reductions.

Hand-written. The base statistics are cross-checked against Python's own `statistics` module, run
for real on `[1.0, 2.0, 3.0, 4.0]`:

    statistics.mean(data)     -> 2.5
    statistics.variance(data) -> 1.6666666666666667   (sample, n-1)
    statistics.stdev(data)    -> 1.2909944487358056

and the wide-vs-narrow accumulation divergence is cross-checked against real `torch.bfloat16`
arithmetic: summing 300 copies of `1.0` stored as bfloat16 gives `300.0` when the accumulator is kept
wide (Float64) and `256.0` when the accumulator itself is rounded back to bfloat16 after every
addition — bfloat16's 8-bit significand cannot represent `256.0 + 1.0` as anything but `256.0`.

The assertions target the failure this module exists to prevent: a reduction over low-precision
storage that quietly loses exactly the precision decoding to Float64 was supposed to preserve, and a
NaN inside the buffer producing a confident wrong number instead of a refusal.
"""
from tensorx.buffer import tx_buf_encode_flat
from tensorx.contract import (
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_ERR_LENGTH_MISMATCH,
    TX_ERR_NEGATIVE_COUNT,
    TX_ERR_NON_FINITE,
    TX_OK,
)
from tensorx.dtype import DT_BF16, DT_F32, DT_NF4
from tensorx.reduce import (
    tx_reduce_max,
    tx_reduce_mean,
    tx_reduce_min,
    tx_reduce_stddev,
    tx_reduce_sum,
    tx_reduce_sum_narrow_accum,
    tx_reduce_variance,
)


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var data = List[Float64]()
    data.append(1.0)
    data.append(2.0)
    data.append(3.0)
    data.append(4.0)
    var bytes32 = tx_buf_encode_flat(data, 4, DT_F32)

    # ── base statistics, cross-checked against Python's statistics module ───────────
    var s = tx_reduce_sum(bytes32, 4, DT_F32)
    if s.status == TX_OK and s.present and s.value == 10.0:
        passed += 1
        print("  ✅ sum([1,2,3,4]) = 10.0")
    else:
        failed += 1
        print("  ❌ tx_reduce_sum drifted:", s.value)

    var m = tx_reduce_mean(bytes32, 4, DT_F32)
    if m.status == TX_OK and m.present and m.value == 2.5:
        passed += 1
        print("  ✅ mean([1,2,3,4]) = 2.5")
    else:
        failed += 1
        print("  ❌ tx_reduce_mean drifted:", m.value)

    var mn = tx_reduce_min(bytes32, 4, DT_F32)
    var mx = tx_reduce_max(bytes32, 4, DT_F32)
    if mn.status == TX_OK and mn.value == 1.0 and mx.status == TX_OK and mx.value == 4.0:
        passed += 1
        print("  ✅ min([1,2,3,4])=1.0 and max([1,2,3,4])=4.0")
    else:
        failed += 1
        print("  ❌ tx_reduce_min/max drifted")

    var v = tx_reduce_variance(bytes32, 4, DT_F32)
    if v.status == TX_OK and v.present and _abs(v.value - 1.6666666666666667) < 1e-9:
        passed += 1
        print("  ✅ sample variance([1,2,3,4]) = 1.6666666666666667, matching statistics.variance")
    else:
        failed += 1
        print("  ❌ tx_reduce_variance drifted from statistics.variance:", v.value)

    var sd = tx_reduce_stddev(bytes32, 4, DT_F32)
    if sd.status == TX_OK and sd.present and _abs(sd.value - 1.2909944487358056) < 1e-9:
        passed += 1
        print("  ✅ sample stddev([1,2,3,4]) = 1.2909944487358056, matching statistics.stdev")
    else:
        failed += 1
        print("  ❌ tx_reduce_stddev drifted from statistics.stdev:", sd.value)

    # ── absent vs zero, per numeric.reduce's policy ──────────────────────────────────
    var empty_bytes = List[UInt8]()
    var sum0 = tx_reduce_sum(empty_bytes, 0, DT_F32)
    if sum0.status == TX_OK and sum0.present and sum0.value == 0.0:
        passed += 1
        print("  ✅ sum of zero elements is 0.0, present — a real answer")
    else:
        failed += 1
        print("  ❌ sum of zero elements was not reported as a present 0.0")

    var mean0 = tx_reduce_mean(empty_bytes, 0, DT_F32)
    var min0 = tx_reduce_min(empty_bytes, 0, DT_F32)
    var var0 = tx_reduce_variance(empty_bytes, 0, DT_F32)
    if (not mean0.present) and (not min0.present) and (not var0.present):
        passed += 1
        print("  ✅ mean/min/variance of zero elements are ABSENT, not zero")
    else:
        failed += 1
        print("  ❌ an absent reduction over zero elements reported present")

    # A single observation has no spread — variance and stddev are absent below n=2.
    var one_val = List[Float64]()
    one_val.append(5.0)
    var one_bytes = tx_buf_encode_flat(one_val, 1, DT_F32)
    var var1 = tx_reduce_variance(one_bytes, 1, DT_F32)
    if var1.status == TX_OK and not var1.present:
        passed += 1
        print("  ✅ variance of one element is absent, not 0.0")
    else:
        failed += 1
        print("  ❌ variance of one element was not reported as absent")

    # ── wide vs narrow accumulation, cross-checked against real torch.bfloat16 ──────
    var ones = List[Float64]()
    for _ in range(300):
        ones.append(1.0)
    var bf16_bytes = tx_buf_encode_flat(ones, 300, DT_BF16)

    var wide = tx_reduce_sum(bf16_bytes, 300, DT_BF16)
    var narrow = tx_reduce_sum_narrow_accum(bf16_bytes, 300, DT_BF16)
    if wide.status == TX_OK and wide.present and wide.value == 300.0 and narrow == 256.0:
        passed += 1
        print("  ✅ 300 bf16 ones: wide accumulation=300.0, narrow (same-width) saturates at 256.0")
        print("     (matches real torch.bfloat16 in-place accumulation, cross-checked before this")
        print("     module was written)")
    else:
        failed += 1
        print("  ❌ wide/narrow accumulation drifted from the torch reference:", wide.value, narrow)

    # ── failure modes: refused, not a confident wrong number ────────────────────────
    var nan_bytes = List[UInt8]()
    nan_bytes.append(0)
    nan_bytes.append(0)
    nan_bytes.append(192)
    nan_bytes.append(127)  # little-endian float32 NaN, cross-checked against struct.pack
    var nan_sum = tx_reduce_sum(nan_bytes, 1, DT_F32)
    var nan_mean = tx_reduce_mean(nan_bytes, 1, DT_F32)
    if nan_sum.status == TX_ERR_NON_FINITE and nan_mean.status == TX_ERR_NON_FINITE:
        passed += 1
        print("  ✅ a NaN inside the buffer is refused with TX_ERR_NON_FINITE, not summed silently")
    else:
        failed += 1
        print("  ❌ a NaN inside the buffer produced a status other than TX_ERR_NON_FINITE")

    if tx_reduce_sum(bytes32, -1, DT_F32).status == TX_ERR_NEGATIVE_COUNT:
        passed += 1
        print("  ✅ a negative n is refused as TX_ERR_NEGATIVE_COUNT")
    else:
        failed += 1
        print("  ❌ a negative n was not refused correctly")

    if tx_reduce_sum(bytes32, 99, DT_F32).status == TX_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ n=99 over a 4-element f32 buffer is refused, not an uncatchable abort")
    else:
        failed += 1
        print("  ❌ tx_reduce_sum read past the end of a too-short buffer")

    if tx_reduce_sum(bytes32, 4, DT_NF4).status == TX_ERR_DTYPE_UNSUPPORTED_FOR_OP:
        passed += 1
        print("  ✅ reducing nf4 'values' with no scale attached is refused")
    else:
        failed += 1
        print("  ❌ tx_reduce_sum accepted nf4 as a reducible dtype")

    if tx_reduce_sum_narrow_accum(bytes32, -1, DT_F32) == 0.0:
        passed += 1
        print("  ✅ the narrow-accumulation counterfactual also refuses a negative n cleanly")
    else:
        failed += 1
        print("  ❌ tx_reduce_sum_narrow_accum did not refuse a negative n")

    print()
    print("[tensorx.reduce] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("tensorx.reduce known-value suite failed")
