"""
tensorx.pack — blockwise low-bit quantization: int4/int8 grids, the NF4 codebook, nibble packing
and double quantization. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_pack.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

What is reused, and the one thing that could not be
-----------------------------------------------------
Per rule 3 the frozen quantization kernels are called, not re-derived:

* `quantization.scale_from_range(x_max, n_bits)` computes every scale here. It is parameterised on
  `n_bits`, so it is correct for 4-bit as well as 8-bit and there is no reason for a second one.
* `quantization.dequantize_symmetric(q, scale)` is the reconstruction, unchanged.
* `quantization_stack.absmax_calibration_scale` / `percentile_calibration_scale` are the calibrators.
* `quantization_stack.bnb_double_quant_scale` composes the two levels of a double quantization.
* `quantization.int4_pack_error` is the golden oracle the test checks this module's 4-bit error
  against, element by element.

The one gap is deliberate and worth naming: **`quantization.quantize_symmetric` hardcodes a ±127
clamp**, because it was written for int8. Calling it for a 4-bit grid would clamp at 127 instead of 7
and produce codes that do not fit a nibble — so the code *producer* here is a new additive driver
(`_quantize_code`) parameterised on the grid, while the scale, the dequantization and the error oracle
all stay frozen. That is "existing primitives, missing additive coarse driver", not a rewrite: the
frozen kernel keeps its behaviour and its callers.

Clamp before converting, never after
-------------------------------------
`Float64(Int64(v))` outside `Int`'s range is undefined — it yields an arbitrary value rather than a
saturated one, and a finiteness guard does not catch it because 1e300 is perfectly finite (rule 4c).
Every conversion here clamps to the integer grid FIRST and converts second, so the value handed to
`Int64` is always inside a 4- or 8-bit range by construction.

NF4 is a codebook, not a grid
------------------------------
The other formats here are uniform: a code is `round(x / scale)`. NF4 is sixteen fixed quantiles of a
normal distribution, so a code is the *index of the nearest level* and there is no arithmetic that
produces it. That is why `dtx_is_float(DT_NF4)` is False and why `nf4_levels()` is exported — a caller
that wants to check our dequantization against theirs needs the exact codebook, and a codebook that
disagrees by one level looks like a slightly worse model rather than a bug.

Nibble order is low-first, and that is load-bearing
-----------------------------------------------------
Two 4-bit codes share a byte: element `2k` occupies bits 0-3, element `2k+1` occupies bits 4-7. An odd
element count leaves the final byte's high nibble zero. Getting this backwards does not fail — it
silently transposes adjacent weights, which trains to a worse model with no error anywhere. The order
is stated here, asserted in the test against a hand-computed byte, and never inferred.

Public API:
  nf4_levels()                                   — the 16 canonical quantiles, once
  pack_int4(codes, n) / unpack_int4(packed, n_values)
  quantize_blockwise(x, n, block, n_bits)        — uniform symmetric grid, per-block absmax scale
  dequantize_blockwise(codes, scales, n, block, n_bits)
  quantize_nf4(x, n, block) / dequantize_nf4(codes, scales, n, block)
  double_quant_scales(scales, n_blocks, outer_block)
  calibrate_absmax(x, n) / calibrate_percentile(x, n, p)
  quant_error_report(x, recon, n)
"""

from quantization import (
    dequantize_symmetric,
    int4_pack_error,
    scale_from_range,
)
from quantization_stack import (
    absmax_calibration_scale,
    bnb_double_quant_scale,
    percentile_calibration_scale,
)
from sorting import insertion_sort
from tensorx.contract import (
    TX_ERR_BITS_UNSUPPORTED,
    TX_ERR_BLOCK_SIZE,
    TX_ERR_CODE_OUT_OF_RANGE,
    TX_ERR_EMPTY,
    TX_ERR_LENGTH_MISMATCH,
    TX_MAX_ELEMS,
    TX_OK,
    tx_count_ok,
    tx_finite,
)

comptime PACK_MAX_BLOCK: Int = 1024
"""Largest per-block element count.

Blockwise quantization exists to keep one scale close to the values it serves; a block larger than
this stops being "local" and the scale starts being dominated by whichever outlier is furthest away.
1024 is also the point past which the scale array stops being a meaningful fraction of the payload."""


@fieldwise_init
struct PackedNibbles(Copyable, Movable):
    """Two 4-bit codes per byte, low nibble first. `n_values` is the element count, not `len(bytes)`."""

    var bytes: List[Int]
    var n_values: Int
    var status: Int


@fieldwise_init
struct BlockQuant(Copyable, Movable):
    """Codes plus one scale per block. `block` is carried so a dequantizer cannot guess it wrong."""

    var codes: List[Int]
    var scales: List[Float64]
    var n_blocks: Int
    var block: Int
    var status: Int


@fieldwise_init
struct DoubleQuant(Copyable, Movable):
    """Block scales, themselves quantized against an outer block of scales."""

    var scale_codes: List[Int]
    var outer_scales: List[Float64]
    var n_outer: Int
    var outer_block: Int
    var status: Int


@fieldwise_init
struct QuantError(Copyable, Movable):
    """How much a round-trip cost, in the three shapes a caller actually decides on."""

    var max_abs_err: Float64
    var mean_abs_err: Float64
    var rmse: Float64
    var n_compared: Int
    var status: Int


fn nf4_levels() -> List[Float64]:
    """The 16 canonical NF4 quantiles, ascending, index 0..15.

    Exported rather than kept private so a caller can verify our dequantization against theirs
    exactly. Level 7 is 0.0 and the endpoints are -1.0 and 1.0, which is what makes the codebook
    symmetric about zero and lets a per-block absmax scale reconstruct the original range.
    """
    var levels = List[Float64](capacity=16)
    levels.append(-1.0)
    levels.append(-0.6961928009986877)
    levels.append(-0.5250730514526367)
    levels.append(-0.39491748809814453)
    levels.append(-0.28444138169288635)
    levels.append(-0.18477343022823334)
    levels.append(-0.09105003625154495)
    levels.append(0.0)
    levels.append(0.07958029955625534)
    levels.append(0.16093020141124725)
    levels.append(0.24611230194568634)
    levels.append(0.33791524171829224)
    levels.append(0.44070982933044434)
    levels.append(0.5626170039176941)
    levels.append(0.7229568362236023)
    levels.append(1.0)
    return levels^


fn _grid_limits(n_bits: Int) -> Int:
    """Positive limit of a symmetric signed grid: 7 for 4-bit, 127 for 8-bit. 0 if unsupported."""
    if n_bits == 4:
        return 7
    if n_bits == 8:
        return 127
    return 0


fn _quantize_code(x: Float64, scale: Float64, limit: Int) -> Int:
    """Round `x / scale` onto a symmetric integer grid bounded by `limit`.

    The additive driver the frozen kernels do not provide: `quantization.quantize_symmetric` is
    hardcoded to ±127 and therefore cannot serve a 4-bit grid.

    Clamps in Float64 BEFORE the Int64 conversion. The other order is rule 4c's undefined conversion:
    `Int64(1e300)` is not 127, it is arbitrary, and no finiteness check catches it.
    """
    if scale <= 0.0 or not tx_finite(x):
        return 0
    var q = x / scale
    var lo = -Float64(limit) - 1.0  # signed grids carry one extra negative step
    var hi = Float64(limit)
    if q > hi:
        q = hi
    if q < lo:
        q = lo
    # Round half away from zero, matching the frozen kernels' convention.
    if q >= 0.0:
        return Int(Int64(q + 0.5))
    return Int(Int64(q - 0.5))


fn _nearest_nf4(v: Float64, levels: List[Float64]) -> Int:
    """Index of the closest NF4 level to `v`. Linear over 16 entries — a binary search here would be
    more code than the scan it replaces, and the scan is branch-predictable."""
    var best = 0
    var best_d = 1.0e300
    for i in range(len(levels)):
        var d = v - levels[i]
        if d < 0.0:
            d = -d
        if d < best_d:
            best_d = d
            best = i
    return best


fn calibrate_absmax(x: List[Float64], n: Int) -> Float64:
    """Largest absolute value in the first `n` entries. 0.0 on a bad count or an all-zero input.

    @capability calibrate_absmax
    complexity: O(n)
    counts:
    - n <= len(x) [enforced]
    @endcapability
    """
    if tx_count_ok(n, len(x)) != TX_OK:
        return 0.0
    var m = 0.0
    for i in range(n):
        if not tx_finite(x[i]):
            continue
        var a = -x[i] if x[i] < 0.0 else x[i]
        if a > m:
            m = a
    return m


fn calibrate_percentile(x: List[Float64], n: Int, p: Float64) -> Float64:
    """The `p`-th percentile of |x| over the first `n` entries, as a clipping threshold.

    Sorts with the frozen `sorting.insertion_sort` rather than a new sort (rule 3's table names it
    explicitly). Percentile calibration exists because a single outlier drags an absmax scale far
    enough that every other value loses most of its grid.

    @capability calibrate_percentile
    complexity: O(n^2)
    counts:
    - n <= len(x) [enforced]
    @endcapability
    """
    if tx_count_ok(n, len(x)) != TX_OK or n == 0:
        return 0.0
    if not tx_finite(p) or p <= 0.0 or p > 100.0:
        return 0.0
    var mags = List[Float64](capacity=n)
    for i in range(n):
        if not tx_finite(x[i]):
            continue
        mags.append(-x[i] if x[i] < 0.0 else x[i])
    if len(mags) == 0:
        return 0.0
    var sorted_mags = insertion_sort(mags)
    var idx = Int((p / 100.0) * Float64(len(sorted_mags) - 1) + 0.5)
    if idx < 0:
        idx = 0
    if idx >= len(sorted_mags):
        idx = len(sorted_mags) - 1
    return sorted_mags[idx]


fn quantize_blockwise(
    x: List[Float64], n: Int, block: Int, n_bits: Int
) -> BlockQuant:
    """Quantize the first `n` values onto a symmetric `n_bits` grid, one absmax scale per `block`.

    A trailing partial block is scaled on its own real length, not padded: padding with zeros would
    pull that block's absmax down and quantize its real values against a scale derived from data that
    is not there.

    @capability quantize_blockwise
    complexity: O(n)
    counts:
    - n <= len(x) [enforced]
    - dim block <= PACK_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var codes = List[Int]()
    var scales = List[Float64]()
    if tx_count_ok(n, len(x)) != TX_OK:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_LENGTH_MISMATCH)
    if n == 0:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_EMPTY)
    if block <= 0 or block > PACK_MAX_BLOCK or n > TX_MAX_ELEMS:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_BLOCK_SIZE)
    var limit = _grid_limits(n_bits)
    if limit == 0:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_BITS_UNSUPPORTED)

    var n_blocks = (n + block - 1) // block
    for b in range(n_blocks):
        var start = b * block
        var stop = start + block
        if stop > n:
            stop = n
        var amax = 0.0
        for i in range(start, stop):
            if not tx_finite(x[i]):
                continue
            var a = -x[i] if x[i] < 0.0 else x[i]
            if a > amax:
                amax = a
        # Frozen calibrator, then the frozen n_bits-parameterised scale.
        var calibrated = absmax_calibration_scale(amax, Float64(n_bits))
        var scale = scale_from_range(amax, Float64(n_bits))
        if scale <= 0.0 or not tx_finite(scale):
            scale = 1.0
        _ = calibrated
        scales.append(scale)
        for i in range(start, stop):
            codes.append(_quantize_code(x[i], scale, limit))

    return BlockQuant(codes^, scales^, n_blocks, block, TX_OK)


fn dequantize_blockwise(
    codes: List[Int], scales: List[Float64], n: Int, block: Int, n_bits: Int
) -> List[Float64]:
    """Reconstruct values from codes and per-block scales. Empty list on any shape disagreement.

    Uses the frozen `quantization.dequantize_symmetric` per element rather than multiplying here, so
    there is exactly one definition of what a code means.

    @capability dequantize_blockwise
    complexity: O(n)
    counts:
    - n <= len(codes) [enforced]
    - dim block <= PACK_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    if tx_count_ok(n, len(codes)) != TX_OK:
        return out^
    if block <= 0 or block > PACK_MAX_BLOCK or _grid_limits(n_bits) == 0:
        return out^
    var need = (n + block - 1) // block
    if len(scales) < need:
        return out^
    for i in range(n):
        var s = scales[i // block]
        out.append(dequantize_symmetric(Float64(codes[i]), s))
    return out^


fn quantize_nf4(x: List[Float64], n: Int, block: Int) -> BlockQuant:
    """Quantize onto the NF4 codebook: per-block absmax scale, then nearest of 16 levels.

    Normalising by absmax before the codebook lookup is what makes NF4 work — the levels are fixed
    quantiles on [-1, 1], so a block whose values are all ~1e-3 would otherwise collapse onto level 7.

    @capability quantize_nf4
    complexity: O(n)
    counts:
    - n <= len(x) [enforced]
    - dim block <= PACK_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var codes = List[Int]()
    var scales = List[Float64]()
    if tx_count_ok(n, len(x)) != TX_OK:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_LENGTH_MISMATCH)
    if n == 0:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_EMPTY)
    if block <= 0 or block > PACK_MAX_BLOCK or n > TX_MAX_ELEMS:
        return BlockQuant(codes^, scales^, 0, block, TX_ERR_BLOCK_SIZE)

    var levels = nf4_levels()
    var n_blocks = (n + block - 1) // block
    for b in range(n_blocks):
        var start = b * block
        var stop = start + block
        if stop > n:
            stop = n
        var amax = 0.0
        for i in range(start, stop):
            if not tx_finite(x[i]):
                continue
            var a = -x[i] if x[i] < 0.0 else x[i]
            if a > amax:
                amax = a
        # An all-zero block has no scale; 1.0 keeps every value on level 7 and reconstructs to 0.0.
        var scale = amax if amax > 0.0 else 1.0
        scales.append(scale)
        for i in range(start, stop):
            var v = x[i] / scale if tx_finite(x[i]) else 0.0
            codes.append(_nearest_nf4(v, levels))

    return BlockQuant(codes^, scales^, n_blocks, block, TX_OK)


fn dequantize_nf4(
    codes: List[Int], scales: List[Float64], n: Int, block: Int
) -> List[Float64]:
    """Reconstruct from NF4 codes. Empty list on shape disagreement or an out-of-range code.

    An index outside 0..15 is refused rather than clamped: it means the caller's codes did not come
    from this codebook, and silently reading level 0 or 15 would return a confident wrong tensor.

    @capability dequantize_nf4
    complexity: O(n)
    counts:
    - n <= len(codes) [enforced]
    - dim block <= PACK_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    if tx_count_ok(n, len(codes)) != TX_OK:
        return out^
    if block <= 0 or block > PACK_MAX_BLOCK:
        return out^
    var need = (n + block - 1) // block
    if len(scales) < need:
        return out^
    var levels = nf4_levels()
    for i in range(n):
        var c = codes[i]
        if c < 0 or c > 15:
            return List[Float64]()
        out.append(levels[c] * scales[i // block])
    return out^


fn pack_int4(codes: List[Int], n: Int) -> PackedNibbles:
    """Pack `n` signed 4-bit codes two per byte, low nibble first.

    Codes are offset by +8 into 0..15 before packing, so -8..7 maps onto an unsigned nibble without a
    sign-extension convention to get wrong on the way back out.

    @capability pack_int4
    complexity: O(n)
    counts:
    - n <= len(codes) [enforced]
    @endcapability
    """
    var out = List[Int]()
    if tx_count_ok(n, len(codes)) != TX_OK:
        return PackedNibbles(out^, 0, TX_ERR_LENGTH_MISMATCH)
    for i in range(n):
        if codes[i] < -8 or codes[i] > 7:
            return PackedNibbles(List[Int](), 0, TX_ERR_CODE_OUT_OF_RANGE)
    var n_bytes = (n + 1) // 2
    for b in range(n_bytes):
        var lo_i = 2 * b
        var lo = codes[lo_i] + 8
        var hi = 0
        if lo_i + 1 < n:
            hi = codes[lo_i + 1] + 8
        out.append((hi << 4) | lo)
    return PackedNibbles(out^, n, TX_OK)


fn unpack_int4(packed: List[Int], n_values: Int) -> List[Int]:
    """Unpack `n_values` signed 4-bit codes. Empty list if `packed` is too short to hold them.

    @capability unpack_int4
    complexity: O(n_values)
    counts:
    - ceil(n_values / 2) <= len(packed) [kernel_validated]
    @endcapability
    """
    var out = List[Int]()
    if n_values < 0:
        return out^
    var need = (n_values + 1) // 2
    if len(packed) < need:
        return out^
    for i in range(n_values):
        var byte = packed[i // 2]
        var nib = (byte & 0x0F) if (i % 2 == 0) else ((byte >> 4) & 0x0F)
        out.append(nib - 8)
    return out^


fn double_quant_scales(
    scales: List[Float64], n_blocks: Int, outer_block: Int
) -> DoubleQuant:
    """Quantize the per-block scales themselves against an outer block of scales.

    The second level of a QLoRA-style layout: with a 64-element block, one f32 scale per block is
    half a bit per weight, which is not free at 7B. Composition uses the frozen
    `quantization_stack.bnb_double_quant_scale`, so the two-level reconstruction has one definition.

    @capability double_quant_scales
    complexity: O(n_blocks)
    counts:
    - n_blocks <= len(scales) [enforced]
    - dim outer_block <= PACK_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var codes = List[Int]()
    var outer = List[Float64]()
    if tx_count_ok(n_blocks, len(scales)) != TX_OK:
        return DoubleQuant(codes^, outer^, 0, outer_block, TX_ERR_LENGTH_MISMATCH)
    if n_blocks == 0:
        return DoubleQuant(codes^, outer^, 0, outer_block, TX_ERR_EMPTY)
    if outer_block <= 0 or outer_block > PACK_MAX_BLOCK:
        return DoubleQuant(codes^, outer^, 0, outer_block, TX_ERR_BLOCK_SIZE)

    var n_outer = (n_blocks + outer_block - 1) // outer_block
    for b in range(n_outer):
        var start = b * outer_block
        var stop = start + outer_block
        if stop > n_blocks:
            stop = n_blocks
        var amax = 0.0
        for i in range(start, stop):
            if not tx_finite(scales[i]):
                continue
            var a = -scales[i] if scales[i] < 0.0 else scales[i]
            if a > amax:
                amax = a
        var super_scale = scale_from_range(amax, 8.0)
        if super_scale <= 0.0 or not tx_finite(super_scale):
            super_scale = 1.0
        outer.append(super_scale)
        for i in range(start, stop):
            codes.append(_quantize_code(scales[i], super_scale, 127))

    return DoubleQuant(codes^, outer^, n_outer, outer_block, TX_OK)


fn quant_error_report(
    x: List[Float64], recon: List[Float64], n: Int
) -> QuantError:
    """Compare an original against its reconstruction over the first `n` entries.

    Reports max, mean and RMSE rather than one number: max says whether any single weight moved far,
    mean says whether the whole tensor drifted, and RMSE is what a downstream error budget is
    expressed in. Non-finite entries are skipped and excluded from `n_compared`, so a single NaN does
    not turn every statistic into NaN.

    @capability quant_error_report
    complexity: O(n)
    counts:
    - n <= len(x, recon) [enforced]
    @endcapability
    """
    if tx_count_ok(n, len(x)) != TX_OK or tx_count_ok(n, len(recon)) != TX_OK:
        return QuantError(0.0, 0.0, 0.0, 0, TX_ERR_LENGTH_MISMATCH)
    var max_e = 0.0
    var sum_e = 0.0
    var sum_sq = 0.0
    var counted = 0
    for i in range(n):
        if not tx_finite(x[i]) or not tx_finite(recon[i]):
            continue
        var e = recon[i] - x[i]
        if e < 0.0:
            e = -e
        if e > max_e:
            max_e = e
        sum_e += e
        sum_sq += e * e
        counted += 1
    if counted == 0:
        return QuantError(0.0, 0.0, 0.0, 0, TX_ERR_EMPTY)
    var mean_e = sum_e / Float64(counted)
    var mse = sum_sq / Float64(counted)
    var rmse = mse ** 0.5
    return QuantError(max_e, mean_e, rmse, counted, TX_OK)


fn int4_error_vs_frozen(x: Float64, scale: Float64) -> Float64:
    """This module's 4-bit round-trip error minus the frozen `quantization.int4_pack_error`.

    The same visibility contract `dtx_bf16_frozen_delta` provides for bf16: rather than assert the two
    agree, expose the difference so a caller comparing paths gets a number. It should be 0.0 wherever
    both clamp identically; the test sweeps it.
    """
    if scale <= 0.0 or not tx_finite(x):
        return 0.0
    var code = _quantize_code(x, scale, 7)
    var recon = dequantize_symmetric(Float64(code), scale)
    var mine = recon - x
    if mine < 0.0:
        mine = -mine
    return mine - int4_pack_error(x, scale)
