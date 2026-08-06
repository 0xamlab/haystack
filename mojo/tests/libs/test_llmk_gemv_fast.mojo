"""test_llmk_gemv_fast.mojo — known-value tests for the parallel transposed GEMV.

Hand-written, same idiom as `test_gemm_blocked.mojo`'s own GEMV section. Three jobs.

**One: the hand-computable case, below the fan-out threshold.** Small enough that
`gemv_transposed_parallel_flat` delegates straight to the frozen `gemv_flat` (rule 3) — this proves
the delegation path returns the exact same answer the frozen kernel does, not a second, drifted
implementation of the same arithmetic.

**Two: agreement with `gemv_flat` at a shape that actually triggers the parallel column-band path.**
`cells = m * n` has to clear `PARALLEL_MIN_CELLS` (1<<16) for the `parallelize` fan-out to run at all,
so the small hand-computed case above cannot exercise it. Both kernels accumulate over the SAME input
index `i`, in the SAME order, for a given output column `j` — the scalar branch does it for every `j`
in one thread, this kernel does it for a disjoint column BAND per thread — so the two are expected to
agree exactly, not just within a tolerance (the self-consistency assertion rule 4b asks for, at a
shape neither implementation is allowed to fake).

**Three: shape refusals.** A caller's wrong `m`/`n` claim against the real buffer lengths must be
refused, not read past the end (rule 1) — the same hazard `gemv_flat` itself guards against, checked
here under this package's own status vocabulary (rule 4e).
"""
from gemm.blocked import gemv_flat
from gemm.contract import GEMM_OK
from llmk.contract import LLMK_ERR_EMPTY_DIM, LLMK_ERR_GEMV_A_LENGTH, LLMK_ERR_GEMV_X_LENGTH, LLMK_OK
from llmk.gemv_fast import gemv_transposed_parallel_flat


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── small, hand-computable, below the fan-out threshold (delegates to gemv_flat) ───────────
    var a_small = List[Float64]()
    a_small.append(1.0)
    a_small.append(2.0)
    a_small.append(3.0)
    a_small.append(4.0)
    a_small.append(5.0)
    a_small.append(6.0)
    var ones2 = List[Float64]()
    ones2.append(1.0)
    ones2.append(1.0)
    var r_small = gemv_transposed_parallel_flat(a_small, ones2, 2, 3)
    # A^T @ [1,1] over [[1,2,3],[4,5,6]] sums down columns: [1+4, 2+5, 3+6] = [5, 7, 9].
    if (
        r_small.status == LLMK_OK
        and r_small.n == 3
        and r_small.y[0] == 5.0
        and r_small.y[1] == 7.0
        and r_small.y[2] == 9.0
    ):
        passed += 1
        print("  ✅ below the fan-out threshold: matches the frozen gemv_flat's hand-computed answer")
    else:
        failed += 1
        print("  ❌ small transposed GEMV is wrong")

    var non_uniform = List[Float64]()
    non_uniform.append(2.0)
    non_uniform.append(-3.0)
    var r_weighted = gemv_transposed_parallel_flat(a_small, non_uniform, 2, 3)
    var ref_weighted = gemv_flat(a_small, non_uniform, 2, 3, True)
    var weighted_ok = r_weighted.status == LLMK_OK and ref_weighted.status == GEMM_OK
    for j in range(3):
        if _abs(r_weighted.y[j] - ref_weighted.c[j]) > 1e-12:
            weighted_ok = False
    if weighted_ok:
        passed += 1
        print("  ✅ a non-uniform (and negative) weight vector agrees with gemv_flat exactly")
    else:
        failed += 1
        print("  ❌ the weighted small case disagreed with the frozen oracle")

    # ── large enough to clear PARALLEL_MIN_CELLS and actually run the column-band parallel path ──
    var m = 300
    var n = 300
    var a_big = List[Float64](capacity=m * n)
    for i in range(m):
        for j in range(n):
            a_big.append(Float64((i * 7 + j * 13) % 97) - 48.0)
    var x_big = List[Float64](capacity=m)
    for i in range(m):
        # Includes exact zeros on purpose, to exercise the `if xi == 0.0: continue` skip both kernels
        # take -- a real decode step's post-RoPE / post-SDPA vectors routinely contain them.
        x_big.append(Float64((i * 3) % 11) - 5.0)

    var big_parallel = gemv_transposed_parallel_flat(a_big, x_big, m, n)
    var big_reference = gemv_flat(a_big, x_big, m, n, True)
    var big_ok = (
        big_parallel.status == LLMK_OK
        and big_reference.status == GEMM_OK
        and big_parallel.n == n
        and big_reference.rows == n
    )
    var worst = 0.0
    for j in range(n):
        var d = _abs(big_parallel.y[j] - big_reference.c[j])
        if d > worst:
            worst = d
        if d > 1e-9:
            big_ok = False
    if big_ok:
        passed += 1
        print("  ✅ at a 300x300 (90000-cell, above the 65536-cell fan-out threshold) shape, the")
        print("     parallel column-band path agrees with the frozen gemv_flat scalar path,")
        print("     worst abs delta:", worst)
    else:
        failed += 1
        print("  ❌ the parallel path disagreed with gemv_flat at a shape that should trigger it,")
        print("     worst abs delta:", worst)

    # ── the exact decode-projection SHAPE (in_features x out_features) is what matters, not just size:
    #    a rectangular (not square) case, closer to a real Q/K/V/gate/up/down projection ───────────
    var m2 = 128
    var n2 = 1536
    var a_rect = List[Float64](capacity=m2 * n2)
    for i in range(m2):
        for j in range(n2):
            a_rect.append(Float64((i * 11 + j * 5) % 61) - 30.0)
    var x_rect = List[Float64](capacity=m2)
    for i in range(m2):
        x_rect.append(Float64((i * 17) % 23) - 11.0)
    var rect_parallel = gemv_transposed_parallel_flat(a_rect, x_rect, m2, n2)
    var rect_reference = gemv_flat(a_rect, x_rect, m2, n2, True)
    var rect_ok = rect_parallel.status == LLMK_OK and rect_reference.status == GEMM_OK
    for j in range(n2):
        if _abs(rect_parallel.y[j] - rect_reference.c[j]) > 1e-9:
            rect_ok = False
    if rect_ok:
        passed += 1
        print("  ✅ a rectangular 128x1536 decode-projection-shaped case agrees with gemv_flat")
    else:
        failed += 1
        print("  ❌ the rectangular decode-projection-shaped case disagreed with gemv_flat")

    # ── refusals: a caller's wrong shape claim must be refused, not read past the real buffer ────
    if gemv_transposed_parallel_flat(a_small, ones2, 2, 4).status == LLMK_ERR_GEMV_A_LENGTH:
        passed += 1
        print("  ✅ a wrong (m, n) claim against the real `a` length is refused")
    else:
        failed += 1
        print("  ❌ a mismatched a-length was accepted -- this WOULD read past the real buffer")

    var short_x = List[Float64]()
    short_x.append(1.0)
    if gemv_transposed_parallel_flat(a_small, short_x, 2, 3).status == LLMK_ERR_GEMV_X_LENGTH:
        passed += 1
        print("  ✅ a wrong `x` length claim is refused")
    else:
        failed += 1
        print("  ❌ a mismatched x-length was accepted -- this WOULD read past the real buffer")

    if gemv_transposed_parallel_flat(List[Float64](), List[Float64](), 0, 0).status == LLMK_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ a zero-sized shape is refused rather than returning a fabricated empty result")
    else:
        failed += 1
        print("  ❌ a zero-sized shape was not refused")

    print("  [llmk.gemv_fast] Passed:", passed, "Failed:", failed)
