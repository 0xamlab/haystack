"""test_mlpk_gated_ffn.mojo — known-value tests for the fused, parallel-band gated FFN driver.

Hand-written. `mlpk.gated_ffn` exists to measure real memory traffic against
`F.silu(gate) * up`-style torch expressions (see its own module docstring), so its four gate kernels
must agree with the correctness-and-gradient reference this package already has,
`mlpk.activation.gated_ffn_fwd_flat` — same per-element formulas (`swiglu`, `gelu_new`,
`mlp_gelu_erf`), a different, band-parallel driver. `geglu_tanh_fast_gate` is the one exception,
by design: it rewrites `1 + tanh(y)` as `2 / (1 + exp(-2y))`, an identity rather than an
approximation, and the module docstring states the two roundings sit ~1.18e-13 apart.

This file also pins the count-relation hazard `mlp_pair_ok` exists to catch: a caller-supplied `n`
greater than either buffer's real length is exactly the shape of bug that fires an uncatchable
bounds assertion and aborts the whole worker elsewhere in this tree (see `sparse_numerics`). Every
gate kernel and `swiglu_ffn_block` must refuse it, not crash on it.
"""
from mlpk.activation import gated_ffn_fwd_flat
from mlpk.contract import (
    MLP_ACT_GEGLU_ERF,
    MLP_ACT_GEGLU_TANH,
    MLP_ACT_SWIGLU,
    MLP_BACKEND_CPU_SIMD,
    MLP_BACKEND_CPU_SIMD_PARALLEL,
    MLP_ERR_EMPTY_DIM,
    MLP_ERR_LENGTH_MISMATCH,
    MLP_OK,
    mlp_backend_name,
)
from mlpk.gated_ffn import (
    gate_bytes_moved,
    geglu_erf_gate,
    geglu_tanh_fast_gate,
    geglu_tanh_gate,
    swiglu_ffn_block,
    swiglu_gate,
)


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var n = 500
    var gate = _pseudo(n, 3)
    var up = _pseudo(n, 7)

    # ── every gate kernel agrees with the existing gradient-checked reference ──
    var oracle_swiglu = gated_ffn_fwd_flat(up, gate, 1, n, MLP_ACT_SWIGLU)
    var ours_swiglu = swiglu_gate(gate, up, n, 0)
    var d_swiglu = 0.0
    for i in range(n):
        var d = _abs(oracle_swiglu.y[i] - ours_swiglu.out[i])
        if d > d_swiglu:
            d_swiglu = d
    if ours_swiglu.status == MLP_OK and d_swiglu == 0.0:
        passed += 1
        print("  ✅ swiglu_gate is bit-identical to the gradient-checked reference")
    else:
        failed += 1
        print("  ❌ swiglu_gate diverged from the reference by", d_swiglu)

    # geglu_tanh_gate and geglu_erf_gate are NOT expected to be bit-identical to the reference:
    # both compute the same real-valued expression with a different left-to-right grouping
    # (`0.5 * g * (1 + f)` here vs `(0.5 * (1 + f)) * g` there), so a ~1 ULP gap is the same
    # benign association-order artifact `mlpk.contract`'s own docstring documents for
    # `gelu_fast` vs `gelu_new` (measured there at 2.6e-16). The tolerance below is two orders of
    # magnitude above that floor and eight below anything a real formula error would produce.
    comptime ROUNDING_TOL: Float64 = 1e-13

    var oracle_tanh = gated_ffn_fwd_flat(up, gate, 1, n, MLP_ACT_GEGLU_TANH)
    var ours_tanh = geglu_tanh_gate(gate, up, n, 0)
    var d_tanh = 0.0
    for i in range(n):
        var d = _abs(oracle_tanh.y[i] - ours_tanh.out[i])
        if d > d_tanh:
            d_tanh = d
    if ours_tanh.status == MLP_OK and d_tanh < ROUNDING_TOL:
        passed += 1
        print("  ✅ geglu_tanh_gate agrees with the gradient-checked reference, max delta", d_tanh)
    else:
        failed += 1
        print("  ❌ geglu_tanh_gate diverged from the reference by", d_tanh)

    var oracle_erf = gated_ffn_fwd_flat(up, gate, 1, n, MLP_ACT_GEGLU_ERF)
    var ours_erf = geglu_erf_gate(gate, up, n, 0)
    var d_erf = 0.0
    for i in range(n):
        var d = _abs(oracle_erf.y[i] - ours_erf.out[i])
        if d > d_erf:
            d_erf = d
    if ours_erf.status == MLP_OK and d_erf < ROUNDING_TOL:
        passed += 1
        print("  ✅ geglu_erf_gate agrees with the gradient-checked reference, max delta", d_erf)
    else:
        failed += 1
        print("  ❌ geglu_erf_gate diverged from the reference by", d_erf)

    # ── the "fast" tanh rewrite is an identity, not an approximation: same function, ──
    # different rounding, and the gap is the documented ~1.18e-13, not zero and not large.
    var ours_fast = geglu_tanh_fast_gate(gate, up, n, 0)
    var d_fast = 0.0
    for i in range(n):
        var d = _abs(ours_tanh.out[i] - ours_fast.out[i])
        if d > d_fast:
            d_fast = d
    if ours_fast.status == MLP_OK and d_fast > 0.0 and d_fast < 1e-11:
        passed += 1
        print("  ✅ geglu_tanh_fast_gate agrees with geglu_tanh_gate to rounding, max delta", d_fast)
    else:
        failed += 1
        print("  ❌ the fast tanh rewrite's agreement is wrong:", d_fast)

    # ── worker count must not change the answer: band split is a scheduling choice ──
    var big_n = 1 << 17
    var big_gate = _pseudo(big_n, 5)
    var big_up = _pseudo(big_n, 9)
    var serial = swiglu_gate(big_gate, big_up, big_n, 1)
    var parallel = swiglu_gate(big_gate, big_up, big_n, 0)
    var band_delta = 0.0
    for i in range(big_n):
        var d = _abs(serial.out[i] - parallel.out[i])
        if d > band_delta:
            band_delta = d
    if (
        serial.status == MLP_OK and parallel.status == MLP_OK
        and mlp_backend_name(serial.backend_used) == "cpu_simd"
        and mlp_backend_name(parallel.backend_used) == "cpu_simd_parallel"
        and band_delta == 0.0
    ):
        passed += 1
        print(
            "  ✅ serial (1 worker) and auto-parallel (", parallel.workers_used,
            "workers) are bit-identical",
        )
    else:
        failed += 1
        print("  ❌ worker count changed the answer by", band_delta, "or the backend tag is wrong")

    # ── bytes-moved is the stated 24 B/element (read gate, read up, write out) ────
    if _abs(gate_bytes_moved(n) - 24.0 * Float64(n)) < 1e-9:
        passed += 1
        print("  ✅ gate_bytes_moved matches the documented 24 B/element")
    else:
        failed += 1
        print("  ❌ gate_bytes_moved is wrong")

    # ── a full block composes three GEMMs around the gate correctly ──────────
    var tokens = 6
    var d_model = 5
    var d_ff = 8
    var x = _pseudo(tokens * d_model, 13)
    var wg = _pseudo(d_model * d_ff, 17)
    var wu = _pseudo(d_model * d_ff, 19)
    var wd = _pseudo(d_ff * d_model, 23)
    var blk = swiglu_ffn_block(x, wg, wu, wd, tokens, d_model, d_ff)
    if blk.status == MLP_OK and blk.rows == tokens and blk.cols == d_model and blk.flop_count > 0.0:
        passed += 1
        print("  ✅ swiglu_ffn_block runs the full 3-GEMM pipeline and reports", blk.flop_count, "flops")
    else:
        failed += 1
        print("  ❌ swiglu_ffn_block failed:", blk.status)

    # ── the count-relation guard: n greater than either real buffer length ───
    # is refused, not an uncatchable worker-crashing bounds assertion.
    var short = List[Float64]()
    short.append(1.0); short.append(2.0); short.append(3.0)
    if swiglu_gate(short, short, 100, 0).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ swiglu_gate refuses an n greater than the real buffer length")
    else:
        failed += 1
        print("  ❌ the count-relation guard did not catch an oversized n")

    if geglu_tanh_gate(short, short, 100, 0).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ geglu_tanh_gate refuses it too")
    else:
        failed += 1
        print("  ❌ geglu_tanh_gate accepted an oversized n")

    if swiglu_ffn_block(short, short, short, short, 10, 10, 10).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ swiglu_ffn_block refuses buffers shorter than its declared shape")
    else:
        failed += 1
        print("  ❌ swiglu_ffn_block accepted undersized buffers")

    if swiglu_gate(short, short, 0, 0).status == MLP_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ n=0 is refused as an empty dimension, not run as a no-op")
    else:
        failed += 1
        print("  ❌ n=0 was not refused as expected")

    # The generic A-Z probe: 5-element lists, 5 for every Int. n=5 equals the buffer
    # length here, so this must SUCCEED — proving the guard is exact, not merely strict.
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if swiglu_gate(lf5, lf5, 5, 5).status == MLP_OK:
        passed += 1
        print("  ✅ the A-Z call shape (n == buffer length) succeeds rather than being over-refused")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was wrongly refused")

    print("  [mlpk.gated_ffn] Passed:", passed, "Failed:", failed)
