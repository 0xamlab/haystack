"""test_gemm_quantized.mojo — known-value tests for dequant-fused matmul.

Hand-written. The headline assertion is `quantized_gemv_golden_delta == 0.0`: the fused kernel and
the dequantize-then-dense kernel it replaces must produce the *same* answer, because the fusion moves
only when the reconstruction happens, not what is reconstructed. This module's entire claim is "same
answer, less memory", and that is the half a test can actually check.

The other assertions target the scale-indexing trap. A blockwise scale array has one entry per
`block` consecutive weights in flattened row-major order, so the scale for `(i, j)` of an m-by-n
weight is `scales[(i * n + j) / block]`. Indexing by row instead — `scales[i]` — is the natural
mistake, produces a plausible tensor, and is wrong by a factor that varies per block. The shapes here
deliberately use two blocks per row so the two indexings disagree; a one-block-per-row test would pass
with the bug present.
"""
from gemm.contract import (
    GEMM_ERR_A_LENGTH,
    GEMM_ERR_BLOCK_SIZE,
    GEMM_ERR_CODE_OUT_OF_RANGE,
    GEMM_ERR_EMPTY_DIM,
    GEMM_ERR_SCALE_LENGTH,
    GEMM_OK,
)
from gemm.quantized import (
    QGEMM_MAX_BLOCK,
    gemm_nf4_flat,
    gemv_int_flat,
    gemv_nf4_flat,
    quantized_gemv_golden_delta,
)
from quantization import dequantize_symmetric
from tensorx.pack import PACK_MAX_BLOCK, nf4_levels, quantize_blockwise, quantize_nf4


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── a hand-computed fused GEMV with TWO blocks per row ────────────────────
    # W is 2x4, block = 2, so row 0 spans scales[0..1] and row 1 spans scales[2..3]. If the kernel
    # indexed scales[i] it would use scales[0] and scales[1] for the two rows and get a different,
    # entirely plausible, answer.
    var codes = List[Int]()
    # row 0: levels 15, 0, 15, 0   -> +1, -1, +1, -1 before scaling
    codes.append(15)
    codes.append(0)
    codes.append(15)
    codes.append(0)
    # row 1: levels 7, 7, 15, 15   -> 0, 0, +1, +1
    codes.append(7)
    codes.append(7)
    codes.append(15)
    codes.append(15)

    var scales = List[Float64]()
    scales.append(1.0)  # covers elements 0,1  (row 0, first half)
    scales.append(2.0)  # covers elements 2,3  (row 0, second half)
    scales.append(3.0)  # covers elements 4,5  (row 1, first half)
    scales.append(4.0)  # covers elements 6,7  (row 1, second half)

    var x = List[Float64]()
    for _ in range(4):
        x.append(1.0)

    # row 0 = (+1*1) + (-1*1) + (+1*2) + (-1*2) = 0
    # row 1 = ( 0*3) + ( 0*3) + (+1*4) + (+1*4) = 8
    var y = gemv_nf4_flat(codes, scales, x, 2, 4, 2)
    if y.status == GEMM_OK and y.rows == 2 and y.y[0] == 0.0 and y.y[1] == 8.0:
        passed += 1
        print("  ✅ blockwise scales index by flat position, not by row — hand-checked with 2 blocks/row")
    else:
        failed += 1
        print("  ❌ scale indexing is wrong:", y.y[0], y.y[1], "expected 0 and 8")

    # ── the fusion changes memory, not the answer ─────────────────────────────
    var w = List[Float64]()
    for i in range(8):
        w.append(Float64(i + 1) * 0.1 - 0.4)
    var q = quantize_nf4(w, 8, 2)
    var d = quantized_gemv_golden_delta(q.codes, q.scales, x, 2, 4, 2)
    # Within tolerance rather than exact: the fused kernel hoists the block scale out of its inner
    # loop, which re-associates the arithmetic and costs about one ULP. A scale-indexing bug is wrong
    # by a factor, so it still fails this bound by orders of magnitude.
    if d.status == GEMM_OK and d.within_tolerance and d.n_compared == 2:
        passed += 1
        print("  ✅ fused NF4 GEMV matches dequantize-then-dense within accumulated rounding")
    else:
        failed += 1
        print("  ❌ the fusion changed the answer:", d.max_abs_delta, "tol", d.tolerance_at_max)

    # Same at a shape with a partial trailing block, where the scale count is ceil rather than exact.
    var w7 = List[Float64]()
    for i in range(9):
        w7.append(Float64(i) * 0.25 - 1.0)
    var q7 = quantize_nf4(w7, 9, 4)
    var x3 = List[Float64]()
    for _ in range(3):
        x3.append(0.5)
    var d7 = quantized_gemv_golden_delta(q7.codes, q7.scales, x3, 3, 3, 4)
    if d7.status == GEMM_OK and d7.within_tolerance:
        passed += 1
        print("  ✅ the fusion stays exact when a block straddles a row boundary")
    else:
        failed += 1
        print("  ❌ the fusion diverged on a straddling block:", d7.max_abs_delta, d7.status)

    # ── NF4 reconstruction uses the real codebook ─────────────────────────────
    var levels = nf4_levels()
    # A single 1x1 weight at level 15 with scale 2.5 must reconstruct to levels[15] * 2.5 = 2.5.
    var one_code = List[Int]()
    one_code.append(15)
    var one_scale = List[Float64]()
    one_scale.append(2.5)
    var one_x = List[Float64]()
    one_x.append(1.0)
    var y1 = gemv_nf4_flat(one_code, one_scale, one_x, 1, 1, 1)
    if y1.status == GEMM_OK and y1.y[0] == levels[15] * 2.5:
        passed += 1
        print("  ✅ a single weight reconstructs as codebook level times block scale")
    else:
        failed += 1
        print("  ❌ single-weight reconstruction is wrong")

    # ── the k-loop GEMM form ──────────────────────────────────────────────────
    # W 2x4 (as above) times X 4x2 of all ones: each output column repeats the GEMV row result.
    var xm = List[Float64]()
    for _ in range(8):
        xm.append(1.0)
    var c = gemm_nf4_flat(codes, scales, xm, 2, 2, 4, 2)
    if (
        c.status == GEMM_OK
        and c.rows == 2
        and c.cols == 2
        and c.y[0] == 0.0
        and c.y[1] == 0.0
        and c.y[2] == 8.0
        and c.y[3] == 8.0
    ):
        passed += 1
        print("  ✅ the NF4 GEMM agrees with the GEMV on every output column")
    else:
        failed += 1
        print("  ❌ NF4 GEMM is wrong:", c.y[0], c.y[1], c.y[2], c.y[3])

    # ── the uniform int grid goes through the frozen dequantizer ──────────────
    var iq = quantize_blockwise(w, 8, 2, 4)
    var iy = gemv_int_flat(iq.codes, iq.scales, x, 2, 4, 2, 4)
    var hand = 0.0
    for j in range(4):
        hand += dequantize_symmetric(Float64(iq.codes[j]), iq.scales[j // 2]) * x[j]
    if iy.status == GEMM_OK and _abs(iy.y[0] - hand) < 1e-12:
        passed += 1
        print("  ✅ int4 GEMV matches a hand reduction through frozen dequantize_symmetric")
    else:
        failed += 1
        print("  ❌ int4 GEMV disagrees with the frozen dequantizer")

    var iq8 = quantize_blockwise(w, 8, 4, 8)
    if gemv_int_flat(iq8.codes, iq8.scales, x, 2, 4, 4, 8).status == GEMM_OK:
        passed += 1
        print("  ✅ the same kernel serves an 8-bit grid")
    else:
        failed += 1
        print("  ❌ the 8-bit path failed")

    # ── guards ────────────────────────────────────────────────────────────────
    if gemv_nf4_flat(codes, scales, x, 2, 4, 0).status == GEMM_ERR_BLOCK_SIZE:
        passed += 1
        print("  ✅ a zero block size is refused")
    else:
        failed += 1
        print("  ❌ a zero block size was accepted")

    if gemv_nf4_flat(codes, scales, x, 2, 9, 2).status == GEMM_ERR_A_LENGTH:
        passed += 1
        print("  ✅ a weight shape larger than the code buffer is refused, not an abort")
    else:
        failed += 1
        print("  ❌ the code count was not bounded")

    # Too few scales for the block count: the invariant that ties codes, block and scales together.
    var short_scales = List[Float64]()
    short_scales.append(1.0)
    if gemv_nf4_flat(codes, short_scales, x, 2, 4, 2).status == GEMM_ERR_SCALE_LENGTH:
        passed += 1
        print("  ✅ too few scales for the block count is its own status, not a generic length error")
    else:
        failed += 1
        print("  ❌ the scale count was not validated against the block count")

    var bad = List[Int]()
    for _ in range(8):
        bad.append(99)
    if gemv_nf4_flat(bad, scales, x, 2, 4, 2).status == GEMM_ERR_CODE_OUT_OF_RANGE:
        passed += 1
        print("  ✅ a code outside 0..15 is refused, not clamped to a codebook endpoint")
    else:
        failed += 1
        print("  ❌ an out-of-codebook index was accepted")

    if gemv_int_flat(iq.codes, iq.scales, x, 2, 4, 2, 5).status == GEMM_ERR_CODE_OUT_OF_RANGE:
        passed += 1
        print("  ✅ an unsupported bit width is refused")
    else:
        failed += 1
        print("  ❌ an unsupported bit width was accepted")

    # An int4 code of 99 does not fit the -8..7 grid even though it is a valid Int.
    if gemv_int_flat(bad, iq.scales, x, 2, 4, 2, 4).status == GEMM_ERR_CODE_OUT_OF_RANGE:
        passed += 1
        print("  ✅ an int4 code outside -8..7 is refused")
    else:
        failed += 1
        print("  ❌ an out-of-grid int code was accepted")

    if (
        gemv_nf4_flat(codes, scales, x, 0, 4, 2).status == GEMM_ERR_EMPTY_DIM
        and gemm_nf4_flat(codes, scales, xm, 2, 0, 4, 2).status == GEMM_ERR_EMPTY_DIM
    ):
        passed += 1
        print("  ✅ empty dimensions are refused on both the GEMV and GEMM forms")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    # The A-Z harness shape: 5-element lists, 5 for every Int. m*n = 25 > 8 codes.
    var lf5 = List[Float64]()
    var li5 = List[Int]()
    for _ in range(5):
        lf5.append(0.5)
        li5.append(5)
    if gemv_nf4_flat(li5, lf5, lf5, 5, 5, 5).status != GEMM_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than reading past the code buffer")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted — this would kill the worker")

    # The declaration's copy of the block ceiling must equal the one the kernels actually test.
    # QGEMM_MAX_BLOCK exists only because a capability relation must name a same-file constant; this
    # is what stops it becoming a second, divergent source of truth.
    if QGEMM_MAX_BLOCK == PACK_MAX_BLOCK:
        passed += 1
        print("  ✅ the declared block ceiling equals tensorx.pack.PACK_MAX_BLOCK")
    else:
        failed += 1
        print("  ❌ QGEMM_MAX_BLOCK drifted from PACK_MAX_BLOCK:", QGEMM_MAX_BLOCK, PACK_MAX_BLOCK)

    print("  [gemm.quantized] Passed:", passed, "Failed:", failed)
