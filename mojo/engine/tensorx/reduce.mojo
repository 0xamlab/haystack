"""
tensorx.reduce — sum/mean/min/max/var/std over a dtype-tagged buffer, accumulating wider than the
storage dtype. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, float32, bfloat16, float16, float8_e4m3fn, float8_e5m2, int8, uint8
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_reduce.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The reduction arithmetic is `numeric.reduce`, called — not reimplemented
------------------------------------------------------------------------------
Rule 3: `numeric.reduce` already carries the package's absent-vs-zero policy (sum of nothing is 0, a
mean/min/max/variance/stddev of nothing does NOT exist) and Welford's numerically-stable incremental
mean and variance. Reimplementing that here, even to add a dtype in front of it, would be exactly the
duplicated-guard hazard rule 3 warns about inside a package — except this hazard would be ACROSS
packages, which is worse, not better. So every public function below decodes its buffer to `Float64`
via `tensorx.buffer.tx_buf_decode_flat`, builds an `all_valid` mask (there are no nulls here, only a
dtype), calls the matching `numeric.reduce_*`, and re-wraps the `numeric.reduce.Reduction` it gets back
into a `TxReduction` declared IN THIS FILE — never returning `numeric.reduce.Reduction` itself from a
public driver here, which is the cross-file-struct-return case rule 2 asks new code to avoid.

"Accumulate in a wider type" is a fact about WHERE precision is preserved, not a new algorithm
--------------------------------------------------------------------------------------------------
`tx_buf_decode_flat` already recovers full `Float64` precision from bf16/fp8/int8 storage — that IS
the wide accumulator `tensorx.dtype.dtx_accum_dtype` calls for (f32 minimum, and `Float64` here is
wider still). The real content of this module is not a cleverer sum; it is refusing to throw that
width away by rounding the RUNNING ACCUMULATOR back down to the storage dtype at every step, the way
an in-place same-width accumulator register would. `tx_reduce_sum_narrow_accum` is that counterfactual,
exported for exactly the reason `tensorx.dtype.dtx_bf16_frozen_delta` exists: so the difference between
"accumulate wide" and "accumulate narrow" is a number a caller can see, not a claim taken on faith.

Measured, not asserted: summing 300 copies of `1.0` stored as `bfloat16`, `tx_reduce_sum` (decode once
to Float64, accumulate in Float64) reports exactly `300.0`. Re-rounding the running total to bfloat16
after every addition — what `tx_reduce_sum_narrow_accum` simulates — saturates at `256.0`, because
bfloat16's 8-bit significand cannot represent `256.0 + 1.0` as anything other than `256.0`. Cross-
checked against `torch.bfloat16` accumulation before this module was written; both agree exactly.

Public API:
  tx_reduce_sum / tx_reduce_mean / tx_reduce_min / tx_reduce_max / tx_reduce_variance / tx_reduce_stddev
      (data, n, dtype) -> TxReduction
  tx_reduce_sum_narrow_accum(data, n, dtype) -> Float64   — the same-width-accumulator counterfactual
"""

from numeric.reduce import all_valid, first_non_finite
from numeric.reduce import reduce_max as _n_reduce_max
from numeric.reduce import reduce_mean as _n_reduce_mean
from numeric.reduce import reduce_min as _n_reduce_min
from numeric.reduce import reduce_stddev as _n_reduce_stddev
from numeric.reduce import reduce_sum as _n_reduce_sum
from numeric.reduce import reduce_variance as _n_reduce_variance

from tensorx.buffer import tx_buf_decode_flat, tx_buf_element_width_bytes
from tensorx.contract import (
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_ERR_LENGTH_MISMATCH,
    TX_ERR_NEGATIVE_COUNT,
    TX_ERR_NON_FINITE,
    TX_MAX_ELEMS,
    TX_OK,
    tx_finite,
)
from tensorx.dtype import dtx_is_supported, dtx_is_sub_byte, dtx_round_trip

comptime _RED_SUM: Int = 0
comptime _RED_MEAN: Int = 1
comptime _RED_MIN: Int = 2
comptime _RED_MAX: Int = 3
comptime _RED_VAR: Int = 4
comptime _RED_STD: Int = 5


@fieldwise_init
struct TxReduction(Copyable, Movable):
    """A reduction outcome over a buffer. `present == False` means no answer exists — a mean,
    min, max, variance or stddev of zero live elements, per `numeric.reduce`'s own policy, carried
    here rather than re-decided."""

    var value: Float64
    var present: Bool
    var n: Int
    var status: Int


def _decode_checked(data: List[UInt8], n: Int, dtype: Int) -> List[Float64]:
    """The shared precondition check every public function below starts with: `n` in range, `dtype`
    self-contained, `data` long enough — THEN decode. Returning an empty list here always means one
    of those failed; the caller already knows which because it checked the same things itself before
    calling, so the status it reports is never inferred from this list's emptiness alone.
    """
    if n < 0 or n > TX_MAX_ELEMS:
        return List[Float64]()
    if dtx_is_sub_byte(dtype) or not dtx_is_supported(dtype):
        return List[Float64]()
    if tx_buf_element_width_bytes(dtype) == 0:
        return List[Float64]()
    var decoded = tx_buf_decode_flat(data, n, dtype)
    if len(decoded) != n:
        return List[Float64]()
    return decoded^


def _precondition_status(data: List[UInt8], n: Int, dtype: Int) -> Int:
    """Why `_decode_checked` would fail, named — so a public function can report a real status
    instead of guessing from an empty list."""
    if n < 0:
        return TX_ERR_NEGATIVE_COUNT
    if n > TX_MAX_ELEMS:
        return TX_ERR_LENGTH_MISMATCH
    if dtx_is_sub_byte(dtype) or not dtx_is_supported(dtype):
        return TX_ERR_DTYPE_UNSUPPORTED_FOR_OP
    if tx_buf_element_width_bytes(dtype) == 0:
        return TX_ERR_DTYPE_UNSUPPORTED_FOR_OP
    var need_ok = n * tx_buf_element_width_bytes(dtype) <= len(data)
    if not need_ok:
        return TX_ERR_LENGTH_MISMATCH
    return TX_OK


def _reduce_dispatch(op: Int, data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Shared implementation for every public reduction: check preconditions, decode wide (to
    Float64), reject on any non-finite live value, then call the matching frozen-in-spirit
    `numeric.reduce_*` and re-wrap its result in a same-file `TxReduction`.
    """
    var pre = _precondition_status(data, n, dtype)
    if pre != TX_OK:
        return TxReduction(0.0, False, 0, pre)
    var values = _decode_checked(data, n, dtype)
    if len(values) != n:
        return TxReduction(0.0, False, 0, TX_ERR_LENGTH_MISMATCH)
    var mask = all_valid(n)
    var bad = first_non_finite(values, mask)
    if bad >= 0:
        return TxReduction(0.0, False, n, TX_ERR_NON_FINITE)

    if op == _RED_SUM:
        var r = _n_reduce_sum(values, mask)
        return TxReduction(r.value, r.present, r.n, TX_OK)
    if op == _RED_MEAN:
        var r2 = _n_reduce_mean(values, mask)
        return TxReduction(r2.value, r2.present, r2.n, TX_OK)
    if op == _RED_MIN:
        var r3 = _n_reduce_min(values, mask)
        return TxReduction(r3.value, r3.present, r3.n, TX_OK)
    if op == _RED_MAX:
        var r4 = _n_reduce_max(values, mask)
        return TxReduction(r4.value, r4.present, r4.n, TX_OK)
    if op == _RED_VAR:
        var r5 = _n_reduce_variance(values, mask)
        return TxReduction(r5.value, r5.present, r5.n, TX_OK)
    # _RED_STD
    var r6 = _n_reduce_stddev(values, mask)
    return TxReduction(r6.value, r6.present, r6.n, TX_OK)


def tx_reduce_sum(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Sum of `n` elements of `dtype`, decoded to `Float64` and accumulated there — never re-rounded
    to `dtype` between additions. Sum of zero elements is `0.0`, present — a real answer, per
    `numeric.reduce`'s policy.

    @capability tx_reduce_sum
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_SUM, data, n, dtype)


def tx_reduce_mean(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Mean of `n` elements of `dtype`. Absent (not `0.0`) for zero elements — a mean of nothing
    does not exist.

    @capability tx_reduce_mean
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_MEAN, data, n, dtype)


def tx_reduce_min(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Minimum of `n` elements of `dtype`. Absent for zero elements.

    @capability tx_reduce_min
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_MIN, data, n, dtype)


def tx_reduce_max(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Maximum of `n` elements of `dtype`. Absent for zero elements.

    @capability tx_reduce_max
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_MAX, data, n, dtype)


def tx_reduce_variance(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Sample variance (n-1) of `n` elements of `dtype`, via Welford. Absent below two elements — one
    observation has no spread to report.

    @capability tx_reduce_variance
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_VAR, data, n, dtype)


def tx_reduce_stddev(data: List[UInt8], n: Int, dtype: Int) -> TxReduction:
    """Sample standard deviation of `n` elements of `dtype`. Absent below two elements.

    @capability tx_reduce_stddev
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    return _reduce_dispatch(_RED_STD, data, n, dtype)


def tx_reduce_sum_narrow_accum(data: List[UInt8], n: Int, dtype: Int) -> Float64:
    """The counterfactual `tx_reduce_sum` deliberately does NOT compute: what the sum would be if the
    running accumulator itself were rounded back to `dtype` after every addition, the way an in-place
    same-width accumulator register works.

    Exists so the value of wide accumulation is a measured difference, not a claim: summing 300
    copies of `1.0` stored as `bfloat16` gives `300.0` from `tx_reduce_sum` and `256.0` from this
    function, because bfloat16's significand cannot represent `256.0 + 1.0` as anything but `256.0`.
    `0.0` on any precondition failure, matching `tx_reduce_sum`'s own failure value for a non-present
    result (callers wanting the DISTINCTION between "zero" and "invalid" use `tx_reduce_sum`, which
    reports it; this function is a single number for direct comparison against that one).

    @capability tx_reduce_sum_narrow_accum
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    if _precondition_status(data, n, dtype) != TX_OK:
        return 0.0
    var values = _decode_checked(data, n, dtype)
    if len(values) != n:
        return 0.0
    var acc = 0.0
    for i in range(n):
        if not tx_finite(values[i]):
            return 0.0
        acc = dtx_round_trip(acc + values[i], dtype)
    return acc
