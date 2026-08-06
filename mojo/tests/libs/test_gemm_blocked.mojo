"""test_gemm_blocked.mojo — known-value tests for the blocked SIMD GEMM and GEMV.

Hand-written. Three jobs.

**One: a hand-computed product.** A 2x3 by 3x2 multiply whose answer can be checked on paper, so a
loop-order or indexing error fails immediately rather than after a plausible-looking benchmark.

**Two: agreement with the frozen oracle at sizes that cross a tile boundary.** The blocking factors
are 64/256/128, so a 2x2 test exercises none of them — every interesting bug in a blocked kernel lives
at the seams. Shapes larger than one tile in each dimension are checked against `linalg.mat_mul` via
`gemm_reference_delta_flat`, which is also the self-consistency assertion rule 4b asks for.

**Three: the backend tag tells the truth.** `kernel_variant` is a product requirement, not a
diagnostic: "no silent fallback" is unverifiable if a result cannot say what executed. A transposed
operand takes the scalar path and must report it.
"""
from gemm.blocked import (
    W,
    gemm_reference_delta_flat,
    gemm_tile_plan,
    gemv_flat,
    sgemm_flat,
)
from gemm.contract import (
    GEMM_BACKEND_CPU_SIMD,
    GEMM_BACKEND_SCALAR,
    GEMM_ERR_A_LENGTH,
    GEMM_ERR_EMPTY_DIM,
    GEMM_ERR_NON_FINITE_SCALAR,
    GEMM_OK,
)
from linalg import Matrix, mat_mul


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _ramp(n: Int, start: Float64, step: Float64) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(start + Float64(i) * step)
    return o^


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic spread of values in roughly [-1, 1], no RNG dependency."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the hand-computed product ─────────────────────────────────────────────
    # A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
    # C = [[1*7+2*9+3*11, 1*8+2*10+3*12], [4*7+5*9+6*11, 4*8+5*10+6*12]]
    #   = [[58, 64], [139, 154]]
    var a = _ramp(6, 1.0, 1.0)
    var b = _ramp(6, 7.0, 1.0)
    var r = sgemm_flat(a, b, 2, 2, 3, 1.0, 0.0, False, False)
    if (
        r.status == GEMM_OK
        and r.rows == 2
        and r.cols == 2
        and r.c[0] == 58.0
        and r.c[1] == 64.0
        and r.c[2] == 139.0
        and r.c[3] == 154.0
    ):
        passed += 1
        print("  ✅ the hand-computed 2x3 by 3x2 product is exact")
    else:
        failed += 1
        print("  ❌ the hand-computed product is wrong:", r.c[0], r.c[1], r.c[2], r.c[3])

    if r.backend_used == GEMM_BACKEND_CPU_SIMD and r.flop_count == 24.0:
        passed += 1
        print("  ✅ the non-transposed path reports cpu_simd and its real FLOP count")
    else:
        failed += 1
        print("  ❌ backend or flop_count is wrong:", r.backend_used, r.flop_count)

    # alpha scales the product; beta has no prior C to scale, so it must not appear in the answer.
    var r2 = sgemm_flat(a, b, 2, 2, 3, 2.0, 0.0, False, False)
    if r2.c[0] == 116.0 and r2.c[3] == 308.0:
        passed += 1
        print("  ✅ alpha scales the product exactly")
    else:
        failed += 1
        print("  ❌ alpha was not applied correctly:", r2.c[0], r2.c[3])

    # ── transposition is correct AND honestly tagged ──────────────────────────
    # A^T read as 3x2 from the same buffer: A_T = [[1,4],[2,5],[3,6]] means op(A) is 3x2, so with
    # m=3, k=2 and B as 2x2 the product is checkable by hand.
    var b22 = _ramp(4, 1.0, 1.0)  # [[1,2],[3,4]]
    var rt = sgemm_flat(a, b22, 3, 2, 2, 1.0, 0.0, True, False)
    # op(A)[0] = [1,4]; row0 = [1*1+4*3, 1*2+4*4] = [13, 18]
    if rt.status == GEMM_OK and rt.c[0] == 13.0 and rt.c[1] == 18.0:
        passed += 1
        print("  ✅ trans_a reads the buffer column-major and produces the right product")
    else:
        failed += 1
        print("  ❌ trans_a is wrong:", rt.c[0], rt.c[1])

    if rt.backend_used == GEMM_BACKEND_SCALAR:
        passed += 1
        print("  ✅ the transposed path reports cpu_scalar — no silent fallback to a false tag")
    else:
        failed += 1
        print("  ❌ a scalar kernel reported a SIMD backend")

    # ── the frozen oracle, across tile seams ──────────────────────────────────
    # Blocking is 64/256/128. Shapes below exercise a partial tile in every dimension, which is where
    # a blocked kernel's off-by-one lives; a 2x2 case would pass with the tiling entirely broken.
    var seam_ok = True
    var worst_seen = 0.0
    var shapes_m = List[Int]()
    var shapes_n = List[Int]()
    var shapes_k = List[Int]()
    # (m, n, k) triples: degenerate, sub-tile, then one crossing each blocking factor, then all.
    for v in [1, 7, 65, 3, 3, 70]:
        shapes_m.append(v)
    for v in [1, 5, 3, 257, 3, 70]:
        shapes_n.append(v)
    for v in [1, 3, 2, 2, 129, 70]:
        shapes_k.append(v)

    for s in range(len(shapes_m)):
        var m = shapes_m[s]
        var n = shapes_n[s]
        var k = shapes_k[s]
        var av = _pseudo(m * k, 11 + s)
        var bv = _pseudo(k * n, 977 + s)
        var d = gemm_reference_delta_flat(av, bv, m, n, k)
        if d.status != GEMM_OK or not d.within_tolerance or d.n_compared != m * n:
            seam_ok = False
        if d.max_abs_delta > worst_seen:
            worst_seen = d.max_abs_delta
    if seam_ok:
        passed += 1
        print("  ✅ blocked GEMM matches frozen linalg.mat_mul across 6 shapes incl. all tile seams")
    else:
        failed += 1
        print("  ❌ the blocked kernel diverged from the frozen oracle at a tile seam")

    # A non-associative reordering means the delta is small but need not be zero. Asserting bitwise
    # equality would either be false or force the frozen accumulation order, which is the slow one.
    if worst_seen < 1e-9:
        passed += 1
        print("  ✅ the accumulation-order delta stays tiny (worst seen:", worst_seen, ")")
    else:
        failed += 1
        print("  ❌ the accumulation-order delta is larger than expected:", worst_seen)

    # The frozen oracle is reachable and unchanged.
    var ma = Matrix(2, 3)
    for i in range(6):
        ma.data[i] = a[i]
    var mb = Matrix(3, 2)
    for i in range(6):
        mb.data[i] = b[i]
    var oracle = mat_mul(ma, mb)
    if oracle.data[0] == 58.0 and oracle.data[3] == 154.0:
        passed += 1
        print("  ✅ the frozen linalg.mat_mul is reachable and behaves as before")
    else:
        failed += 1
        print("  ❌ the frozen mat_mul changed")

    # ── GEMV ──────────────────────────────────────────────────────────────────
    var ones3 = List[Float64]()
    for _ in range(3):
        ones3.append(1.0)
    var y = gemv_flat(a, ones3, 2, 3, False)
    # Row sums of [[1,2,3],[4,5,6]] are 6 and 15.
    if y.status == GEMM_OK and y.rows == 2 and y.c[0] == 6.0 and y.c[1] == 15.0:
        passed += 1
        print("  ✅ GEMV row sums are exact")
    else:
        failed += 1
        print("  ❌ GEMV is wrong")

    var ones2 = List[Float64]()
    for _ in range(2):
        ones2.append(1.0)
    var yt = gemv_flat(a, ones2, 2, 3, True)
    # A^T @ [1,1] sums down columns: [1+4, 2+5, 3+6] = [5, 7, 9].
    if yt.rows == 3 and yt.c[0] == 5.0 and yt.c[1] == 7.0 and yt.c[2] == 9.0:
        passed += 1
        print("  ✅ transposed GEMV sums down columns and returns n rows, not m")
    else:
        failed += 1
        print("  ❌ transposed GEMV is wrong")

    # A GEMV whose vector is shorter than the reduction would read past the end.
    if gemv_flat(a, ones2, 2, 3, False).status == GEMM_ERR_A_LENGTH:
        passed += 1
        print("  ✅ a vector shorter than the reduction is refused, not an out-of-bounds read")
    else:
        failed += 1
        print("  ❌ GEMV did not bound its vector length")

    # ── the guards the A-Z harness cannot reach ───────────────────────────────
    # This is the harness's literal call shape: five-element lists, 5 for every Int. A[24] on a
    # 6-element buffer is the uncatchable abort.
    var lf5 = _ramp(5, 0.5, 0.0)
    if sgemm_flat(lf5, lf5, 5, 5, 5, 0.5, 0.5, False, False).status == GEMM_ERR_A_LENGTH:
        passed += 1
        print("  ✅ the A-Z call shape (5-element lists, m=n=k=5) is refused, not an abort")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was not refused — this would kill the worker")

    var nan_v = 0.0 / 0.0
    if sgemm_flat(a, b, 2, 2, 3, nan_v, 0.0, False, False).status == GEMM_ERR_NON_FINITE_SCALAR:
        passed += 1
        print("  ✅ a NaN alpha is refused before it can poison every output element")
    else:
        failed += 1
        print("  ❌ a NaN alpha was accepted")

    if sgemm_flat(a, b, 1 << 20, 1 << 20, 1 << 20, 1.0, 0.0, False, False).status != GEMM_OK:
        passed += 1
        print("  ✅ a shape that would run for years is refused rather than hanging")
    else:
        failed += 1
        print("  ❌ the work budget did not stop a 2^60-operation call")

    # ── tile planning ─────────────────────────────────────────────────────────
    var tp = gemm_tile_plan(512, 512, 512, 262144)
    if tp.status == GEMM_OK and tp.tile_m > 0 and tp.tile_n > 0 and tp.tile_k > 0:
        passed += 1
        print("  ✅ tile planning returns positive factors from the frozen smem model")
    else:
        failed += 1
        print("  ❌ tile planning failed")

    # Arithmetic intensity should rise with size — a bigger GEMM reuses each loaded byte more.
    var small = gemm_tile_plan(16, 16, 16, 262144)
    var big = gemm_tile_plan(1024, 1024, 1024, 262144)
    if big.arithmetic_intensity > small.arithmetic_intensity:
        passed += 1
        print("  ✅ arithmetic intensity grows with problem size, as the roofline model requires")
    else:
        failed += 1
        print("  ❌ arithmetic intensity did not grow with size")

    if gemm_tile_plan(0, 16, 16, 262144).status == GEMM_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ tile planning refuses an empty dimension")
    else:
        failed += 1
        print("  ❌ tile planning accepted an empty dimension")

    if W >= 1:
        passed += 1
        print("  ✅ SIMD width for Float64 on this target is", W)
    else:
        failed += 1
        print("  ❌ SIMD width is not positive")

    print("  [gemm.blocked] Passed:", passed, "Failed:", failed)
