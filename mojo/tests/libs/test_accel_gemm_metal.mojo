"""test_accel_gemm_metal.mojo — the tiled GPU GEMM, and the two ways it is allowed to say no.

Hand-written. This suite runs on EVERY host and adapts, because the module has three legitimate
states and all three need testing:

| build flag | accelerator | expected |
|---|---|---|
| unset | either | `shader_toolchain_absent`, and the binary still built |
| set | absent | `no_accelerator_present` |
| set | present | a correct product |

The first row is the one that protects CI. `-D ALGENTA_GPU` is not set by default, so the assertions
below run in the default build too — and there they assert that the kernel is compiled out and says
so, which is precisely the property that lets a Linux runner with no shader compiler build this file.

Correctness is judged at FLOAT32 precision, deliberately
----------------------------------------------------------
The GPU kernel computes in Float32 and `gemm.blocked` computes in Float64. They do not compute the
same function. Judging their agreement by a Float64 tolerance would always fail and would say nothing
about whether the tiling is right — only that Float32 is Float32. The bound scales with `k`, because
a longer inner dimension accumulates more roundings, so a fixed bound would pass at k=16 and fail at
k=4096 on identical code.

The shapes are chosen to break tiling, not to flatter it
----------------------------------------------------------
Every size below is deliberately NOT a multiple of the threadgroup tile. A GEMM that only ever sees
tile-aligned shapes never exercises the partial tile at the edges, and the partial tile is where the
bounds guards and the zero-padding of the shared memory actually matter. A kernel that is wrong there
is right on every benchmark and wrong on every real model.
"""
from accel.contract import (
    ACCEL_BACKEND_METAL,
    ACCEL_ERR_EMPTY_DIM,
    ACCEL_ERR_NO_DEVICE,
    ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT,
    ACCEL_OK,
    accel_status_name,
)
from accel.gemm_metal import (
    ACCEL_GEMM_MAX_DIM,
    ACCEL_GPU_BUILD,
    BM,
    BN,
    gemm_metal_agreement,
    gemm_metal_available,
    gemm_metal_flat,
)
from gemm.blocked import sgemm_flat
from gemm.contract import GEMM_OK
from std.sys import has_accelerator


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

    var a = _pseudo(40 * 24, 1)
    var b = _pseudo(24 * 33, 5)

    # ── refusals that hold in EVERY build ─────────────────────────────────────
    if gemm_metal_flat(a, b, 0, 33, 24).status == ACCEL_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an empty dimension is refused")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    if gemm_metal_flat(a, b, ACCEL_GEMM_MAX_DIM + 1, 33, 24).status == ACCEL_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an edge past the ceiling is refused before any allocation")
    else:
        failed += 1
        print("  ❌ an oversized edge was accepted")

    # The A-Z call shape: 5-element lists, 5 for every Int -> needs 25 elements.
    var lf5 = _pseudo(5, 1)
    if gemm_metal_flat(lf5, lf5, 5, 5, 5).status != ACCEL_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    # ── the build-flag contract ───────────────────────────────────────────────
    @parameter
    if not ACCEL_GPU_BUILD:
        # THE DEFAULT BUILD. This branch is what runs on Linux CI, and it is a real assertion:
        # the module compiled, linked, and reports the absence honestly instead of crashing.
        var absent = gemm_metal_flat(a, b, 40, 33, 24)
        if absent.status == ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: reports", accel_status_name(absent.status))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", absent.status)

        if not gemm_metal_available():
            passed += 1
            print("  ✅ ...and gemm_metal_available() agrees")
        else:
            failed += 1
            print("  ❌ available() claims a GPU in a build that has no kernels")

        print("  [accel.gemm_metal] Passed:", passed, "Failed:", failed)
        return

    # ── from here: built WITH GPU kernels ─────────────────────────────────────
    if not has_accelerator():
        var no_dev = gemm_metal_flat(a, b, 40, 33, 24)
        if no_dev.status == ACCEL_ERR_NO_DEVICE:
            passed += 1
            print("  ✅ GPU build on a host with no accelerator reports", accel_status_name(no_dev.status))
        else:
            failed += 1
            print("  ❌ wrong status on a device-less host:", no_dev.status)
        print("  [accel.gemm_metal] Passed:", passed, "Failed:", failed)
        return

    if gemm_metal_available():
        passed += 1
        print("  ✅ GPU build on a GPU host reports available")
    else:
        failed += 1
        print("  ❌ available() is false on a GPU build with a device")

    # ── correctness on a tile-misaligned shape ────────────────────────────────
    # 40 x 33 from k=24. None of the three is a multiple of 16, so every edge has a partial tile.
    var m = 40
    var n = 33
    var k = 24
    var gpu = gemm_metal_flat(a, b, m, n, k)
    if gpu.status == ACCEL_OK and gpu.rows == m and gpu.cols == n:
        passed += 1
        print("  ✅ a 40x33 product from k=24 — every dimension a partial tile — computed")
    else:
        failed += 1
        print("  ❌ the misaligned shape failed:", accel_status_name(gpu.status))

    if gpu.backend_used == ACCEL_BACKEND_METAL:
        passed += 1
        print("  ✅ the result reports the backend that actually ran")
    else:
        failed += 1
        print("  ❌ the result did not report metal:", gpu.backend_used)

    var ag = gemm_metal_agreement(a, b, m, n, k)
    if ag.status == ACCEL_OK and ag.within_float32_precision:
        passed += 1
        print("  ✅ agrees with the Float64 CPU kernel to", ag.max_abs_delta,
              "within a Float32 bound of", ag.float32_bound)
    else:
        failed += 1
        print("  ❌ outside Float32 precision:", ag.max_abs_delta, "bound", ag.float32_bound)

    # The agreement check must be capable of failing. A Float64 bound is what a careless reader
    # would use; assert it would REJECT, so the loose bound above is a considered choice and not an
    # unfalsifiable one.
    if ag.max_abs_delta > 1.0e-12:
        passed += 1
        print("  ✅ ...and it would FAIL a Float64 bound — the precisions really differ")
    else:
        failed += 1
        print("  ❌ the two agree to Float64 precision, so the Float32 bound proves nothing")

    # ── a known value, not just agreement ─────────────────────────────────────
    # Identity times a matrix is that matrix. Catches a transposed index, which agreement against
    # another kernel would only catch if that kernel were right.
    var dim = 20
    var ident = List[Float64](capacity=dim * dim)
    for r in range(dim):
        for c in range(dim):
            ident.append(1.0 if r == c else 0.0)
    var mat = _pseudo(dim * dim, 9)
    var prod = gemm_metal_flat(ident, mat, dim, dim, dim)
    var worst_ident = 0.0
    if prod.status == ACCEL_OK:
        for i in range(dim * dim):
            var delta = _abs(prod.c[i] - mat[i])
            if delta > worst_ident:
                worst_ident = delta
    if prod.status == ACCEL_OK and worst_ident < 1.0e-6:
        passed += 1
        print("  ✅ identity @ M == M to", worst_ident, "— indices are not transposed")
    else:
        failed += 1
        print("  ❌ the identity product is wrong:", worst_ident)

    # ── a shape larger than one tile in every direction ───────────────────────
    # 100x70 from k=50 spans several threadgroups, so the shared-memory tile is reloaded many times
    # and the second barrier is load-bearing. A single-tile shape would never test it.
    var bm = 100
    var bn = 70
    var bk = 50
    var ba = _pseudo(bm * bk, 3)
    var bb = _pseudo(bk * bn, 7)
    var big = gemm_metal_agreement(ba, bb, bm, bn, bk)
    if big.status == ACCEL_OK and big.within_float32_precision:
        passed += 1
        print("  ✅ a multi-threadgroup 100x70 from k=50 agrees —", big.max_abs_delta)
    else:
        failed += 1
        print("  ❌ the multi-tile shape disagrees:", big.max_abs_delta)

    # ── a non-square, non-symmetric shape ─────────────────────────────────────
    # m != n != k, so a kernel that confused two of the three dimensions produces a wrong SHAPE or
    # wrong values rather than accidentally still working.
    var ra = _pseudo(17 * 65, 11)
    var rb = _pseudo(65 * 9, 13)
    var rect = gemm_metal_flat(ra, rb, 17, 9, 65)
    var cpu_rect = sgemm_flat(ra, rb, 17, 9, 65, 1.0, 0.0, False, False)
    var worst_rect = 0.0
    if rect.status == ACCEL_OK and cpu_rect.status == GEMM_OK:
        for i in range(17 * 9):
            var delta = _abs(rect.c[i] - cpu_rect.c[i])
            if delta > worst_rect:
                worst_rect = delta
    if rect.status == ACCEL_OK and rect.rows == 17 and rect.cols == 9 and worst_rect < 1.0e-4:
        passed += 1
        print("  ✅ a 17x9 from k=65 — all three dimensions distinct — matches to", worst_rect)
    else:
        failed += 1
        print("  ❌ the rectangular shape is wrong:", rect.rows, rect.cols, worst_rect)

    print("  [accel.gemm_metal] Passed:", passed, "Failed:", failed)
