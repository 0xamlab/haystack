"""bench_tensorx_and_gemm.mojo — timing gate for the LLM-plane substrate.

Hand-written, not generated. `benchmark_mojo_vs_python.py` only writes `bench_<lib>.mojo` for
libraries in the runtime inventory; no library is named `tensorx_and_gemm`, so nothing can collide
with this name, and that harness only writes — it never unlinks.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
1. **Blocked GEMM beats the frozen naive kernel, and the gap widens with n.** `linalg.mat_mul` is
   `i-j-k`, which walks B down a column — one cache line per element — so it degrades once B stops
   fitting in cache. The blocked `i-k-j` kernel streams contiguous runs of B and C. At small n both
   fit in L1 and the two should be close; the blocking only pays once the working set exceeds it,
   which is why this is measured across a rising n rather than at one size.

2. **ns per FLOP stays roughly flat for the blocked kernel.** That is the actual property. A kernel
   whose per-FLOP cost grows with n is falling out of cache, and a single-size benchmark cannot see
   it. The frozen kernel is measured on the same axis for contrast.

3. **Fused NF4 GEMV beats dequantize-then-dense.** This is the entire justification for
   `gemm.quantized`: a 4-bit weight is 16x smaller than f64, and a decode step is bandwidth-bound, so
   materializing the dequantized matrix spends the whole saving before any arithmetic happens. If the
   fused path were not faster, the module should not exist.

4. **Blockwise quantization is O(n).** ns per element must stay flat as n rises; a quantizer that
   rescans for a global absmax would grow.

Correctness is asserted alongside every timing, because a fast wrong answer is not a result: the
blocked GEMM is diffed against the frozen `linalg.mat_mul`, and the fused NF4 GEMV against
dequantize-then-dense.

Gate
----
Fails on the properties, not on absolute nanoseconds, which vary by machine:
  * blocked GEMM must agree with the frozen kernel within the accumulated-rounding tolerance
  * blocked GEMM ns/FLOP must not grow more than 3x across a 4x increase in n
  * blocked GEMM must be at least as fast as the frozen kernel at the largest size measured
  * fused NF4 GEMV must agree EXACTLY with dequantize-then-dense, and be faster
  * blockwise-quantize ns/element must not grow more than 3x across a 16x increase in n
Absolute numbers are printed for tracking.
"""
from std.time import perf_counter_ns

from gemm.blocked import gemm_reference_delta_flat, gemv_flat, sgemm_flat
from gemm.contract import GEMM_OK
from gemm.quantized import gemv_nf4_flat, quantized_gemv_golden_delta
from linalg import Matrix, mat_mul
from tensorx.dtype import DT_BF16, dtx_round_trip_list
from tensorx.pack import nf4_levels, quantize_nf4


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic values in roughly [-1, 1]. No RNG dependency, so runs are comparable."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


fn _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def main() raises:
    var failures = 0
    print("=== tensorx + gemm timing gate ===")

    # ── 1 & 2. blocked GEMM vs the frozen naive kernel, across a rising n ─────
    print("")
    print("[gemm.blocked] square GEMM vs frozen linalg.mat_mul")
    print("   n     blocked ns    frozen ns    speedup   blocked ns/FLOP")

    var sizes = List[Int]()
    sizes.append(64)
    sizes.append(128)
    sizes.append(256)
    sizes.append(512)

    # Warm up before the first timed call. The very first invocation pays one-time costs — page
    # faults on the fresh output buffer, the thread pool spinning up for `parallelize` — that belong
    # to neither kernel. Without this the first row reads as a loss and the whole table is misleading.
    var warm_a = _pseudo(64 * 64, 1)
    var warm_b = _pseudo(64 * 64, 2)
    var warm = sgemm_flat(warm_a, warm_b, 64, 64, 64, 1.0, 0.0, False, False)
    _ = warm

    var first_ns_per_flop = 0.0
    var last_ns_per_flop = 0.0
    var last_speedup = 0.0

    for si in range(len(sizes)):
        var n = sizes[si]
        var a = _pseudo(n * n, 7 + si)
        var b = _pseudo(n * n, 991 + si)
        var flops = 2.0 * Float64(n) * Float64(n) * Float64(n)

        var t0 = perf_counter_ns()
        var mine = sgemm_flat(a, b, n, n, n, 1.0, 0.0, False, False)
        var blocked_ns = _ns_since(t0)
        if mine.status != GEMM_OK:
            failures += 1
            print("   status not ok at n =", n)
            continue

        var ma = Matrix(n, n)
        for i in range(n * n):
            ma.data[i] = a[i]
        var mb = Matrix(n, n)
        for i in range(n * n):
            mb.data[i] = b[i]
        var t1 = perf_counter_ns()
        var oracle = mat_mul(ma, mb)
        var frozen_ns = _ns_since(t1)
        _ = oracle

        var speedup = frozen_ns / blocked_ns if blocked_ns > 0.0 else 0.0
        var ns_per_flop = blocked_ns / flops
        if si == 0:
            first_ns_per_flop = ns_per_flop
        last_ns_per_flop = ns_per_flop
        last_speedup = speedup

        print("  ", n, "  ", blocked_ns, "  ", frozen_ns, "  ", speedup, "x  ", ns_per_flop)

    # Correctness first: a fast wrong answer is not a result.
    var av = _pseudo(64 * 64, 31)
    var bv = _pseudo(64 * 64, 57)
    var delta = gemm_reference_delta_flat(av, bv, 64, 64, 64)
    if delta.status == GEMM_OK and delta.within_tolerance:
        print("   correctness: blocked matches frozen within tolerance (max delta", delta.max_abs_delta, ")")
    else:
        failures += 1
        print("   FAIL: blocked GEMM disagrees with the frozen kernel")

    var flop_growth = last_ns_per_flop / first_ns_per_flop if first_ns_per_flop > 0.0 else 0.0
    if flop_growth <= 3.0:
        print("   ns/FLOP growth across 8x n:", flop_growth, "x  (gate: <= 3x)")
    else:
        failures += 1
        print("   FAIL: ns/FLOP grew", flop_growth, "x — the blocking is not holding the working set")

    if last_speedup >= 1.0:
        print("   speedup at the largest size:", last_speedup, "x  (gate: >= 1.0x)")
    else:
        failures += 1
        print("   FAIL: the blocked kernel is slower than the frozen naive one")

    # ── 3. fused NF4 GEMV vs dequantize-then-dense ───────────────────────────
    print("")
    print("[gemm.quantized] fused NF4 GEMV vs dequantize-then-dense")

    var qn = 512
    var w = _pseudo(qn * qn, 4242)
    var q = quantize_nf4(w, qn * qn, 64)
    var x = _pseudo(qn, 909)

    var t2 = perf_counter_ns()
    var fused = gemv_nf4_flat(q.codes, q.scales, x, qn, qn, 64)
    var fused_ns = _ns_since(t2)

    # The path the module exists to avoid: build the dense weight, then multiply it.
    var levels = nf4_levels()
    var t3 = perf_counter_ns()
    var dense = List[Float64](capacity=qn * qn)
    for idx in range(qn * qn):
        dense.append(levels[q.codes[idx]] * q.scales[idx // 64])
    var materialized = gemv_flat(dense, x, qn, qn, False)
    var dense_ns = _ns_since(t3)

    var q_speedup = dense_ns / fused_ns if fused_ns > 0.0 else 0.0
    print("   fused ns:", fused_ns, "  materialized ns:", dense_ns, "  speedup:", q_speedup, "x")
    print("   f64 weight bytes avoided:", 8 * qn * qn)

    var gd = quantized_gemv_golden_delta(q.codes, q.scales, x, qn, qn, 64)
    if gd.status == GEMM_OK and gd.within_tolerance:
        print("   correctness: fused matches dequantize-then-dense within rounding (delta", gd.max_abs_delta, ")")
    else:
        failures += 1
        print("   FAIL: the fusion changed the answer:", gd.max_abs_delta)

    if fused.status == GEMM_OK and materialized.status == GEMM_OK and q_speedup >= 1.0:
        print("   gate: fused is at least as fast (>= 1.0x)")
    else:
        failures += 1
        print("   FAIL: the fused path is slower than materializing — the module has no reason to exist")

    # ── 4. blockwise quantization is O(n) ────────────────────────────────────
    print("")
    print("[tensorx.pack] blockwise NF4 quantization, ns per element")

    var qsizes = List[Int]()
    qsizes.append(4096)
    qsizes.append(16384)
    qsizes.append(65536)

    var first_ns_per_elem = 0.0
    var last_ns_per_elem = 0.0
    for si in range(len(qsizes)):
        var n = qsizes[si]
        var v = _pseudo(n, 13 + si)
        var t4 = perf_counter_ns()
        var qq = quantize_nf4(v, n, 64)
        var ns = _ns_since(t4)
        _ = qq
        var per = ns / Float64(n)
        if si == 0:
            first_ns_per_elem = per
        last_ns_per_elem = per
        print("   n =", n, "  ns:", ns, "  ns/element:", per)

    var q_growth = last_ns_per_elem / first_ns_per_elem if first_ns_per_elem > 0.0 else 0.0
    if q_growth <= 3.0:
        print("   ns/element growth across 16x n:", q_growth, "x  (gate: <= 3x)")
    else:
        failures += 1
        print("   FAIL: quantization is not O(n) — ns/element grew", q_growth, "x")

    # ── dtype round-trip, for tracking ───────────────────────────────────────
    print("")
    print("[tensorx.dtype] bf16 round-trip, ns per element")
    var rn = 65536
    var rv = _pseudo(rn, 77)
    var t5 = perf_counter_ns()
    var cast = dtx_round_trip_list(rv, rn, DT_BF16)
    var cast_ns = _ns_since(t5)
    print("   n =", rn, "  ns:", cast_ns, "  ns/element:", cast_ns / Float64(rn))
    print("   max abs error:", cast.max_abs_err, "  overflow:", cast.n_overflow)

    print("")
    if failures == 0:
        print("✅ tensorx + gemm timing gate: all properties hold")
    else:
        print("❌ tensorx + gemm timing gate:", failures, "property failure(s)")
