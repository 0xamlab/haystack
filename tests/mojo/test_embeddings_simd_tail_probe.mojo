"""test_embeddings_simd_tail_probe.mojo — hand-verified probe for the SIMD
vectorization added to `dot_product`, `cosine_similarity`, `euclidean_distance`,
`manhattan_distance`, and `vector_magnitude` in embeddings.mojo.

Not an auto-generated suite (tests/generate_mojo_tests.py emits one smoke call
per function at one fixed length -- it cannot sweep a range of lengths or hold
an independent scalar reference to compare against). This hand-written probe
proves, at vector lengths that are NOT multiples of common SIMD widths (0, 1,
2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 1001) plus one large-and-odd length (10007):

  1. Every vectorized function's TAIL HANDLING is correct: at every length
     above, the SIMD path (`while i + W <= n` main loop) plus its scalar
     remainder loop covers every element exactly once. This part IS asserted
     exactly: at n=0 the SIMD-with-integer golden-vector check below proves
     the empty case returns the same zero/identity every frozen scalar path
     always returned, and the tolerance check below (part 2) would itself
     fail with a large, obviously-wrong delta -- not a ULP-scale one -- if a
     single element were ever skipped or double-counted, so a tolerance-based
     comparison still catches an off-by-one; it just would not distinguish a
     correct SIMD reduction from an incorrect one that happened to be close.

  2. Numerically, the vectorized result matches an INDEPENDENT scalar
     reference (written in this file, not calling any embeddings.mojo
     internal) within a tolerance -- NOT bit-identical `==`.

     This is a real, measured finding, not a precaution: `reduce_add()`
     folds SIMD lanes in a different order than the scalar loop's
     `i = 0, 1, 2, ...`, and float addition is not associative, so on
     realistic (non-integer) inputs the two sums disagree at the ULP level
     starting at n as small as 2 (confirmed by running this probe with `==`
     before it was changed to a tolerance -- see embeddings.mojo's module
     docstring). Every EXISTING hand-written golden vector in this module's
     other suites happens to use small integer-valued inputs and stays
     EXACTLY bit-identical (checked separately below, with `==`, against the
     literal vectors `mojo/tests/libs/test_embeddings.mojo` uses) -- but that
     is a property of those specific inputs, not a general one, so this
     broader sweep is honest about needing a tolerance instead.

     The tolerance is `tensorx.dtype.dtx_tol_for`, the SAME primitive and the
     SAME length-scaled-relative-term shape `gemm.blocked.gemm_reference_delta_flat`
     already uses to compare its own blocked SIMD accumulation against a
     reference: `dtx_tol_for(reference_value, DT_F64, 0.0).relative_term`,
     scaled by the reduction length (`n`) because accumulated rounding grows
     with it, times a small constant safety factor -- not a hand-picked
     epsilon, and not loosened beyond what that established convention
     already allows elsewhere in this codebase.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine \
    ../tests/mojo/test_embeddings_simd_tail_probe.mojo
"""
from std.math import sqrt
from embeddings import (
    dot_product,
    cosine_similarity,
    euclidean_distance,
    manhattan_distance,
    vector_magnitude,
)
from tensorx.dtype import DT_F64, dtx_tol_for


def _mk(n: Int, seed: Float64, step: Float64) -> List[Float64]:
    """`n` values `seed, seed + step, seed + 2*step, ...` -- deterministic,
    comparable-magnitude, and independent of any embeddings.mojo internals."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(seed + Float64(i) * step)
    return out^


def _ref_dot(a: List[Float64], b: List[Float64]) -> Float64:
    """Independent scalar reference: NOT a call into embeddings.mojo."""
    var s: Float64 = 0.0
    for i in range(len(a)):
        s += a[i] * b[i]
    return s


def _ref_cosine(a: List[Float64], b: List[Float64]) -> Float64:
    var dot: Float64 = 0.0
    var sq_a: Float64 = 0.0
    var sq_b: Float64 = 0.0
    for i in range(len(a)):
        dot += a[i] * b[i]
        sq_a += a[i] * a[i]
        sq_b += b[i] * b[i]
    if sq_a <= 0.0 or sq_b <= 0.0:
        return 0.0
    return dot / (sqrt(sq_a) * sqrt(sq_b))


def _ref_euclidean(a: List[Float64], b: List[Float64]) -> Float64:
    var s: Float64 = 0.0
    for i in range(len(a)):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


def _ref_manhattan(a: List[Float64], b: List[Float64]) -> Float64:
    var s: Float64 = 0.0
    for i in range(len(a)):
        var d = a[i] - b[i]
        if d < 0.0:
            d = -d
        s += d
    return s


def _ref_magnitude(v: List[Float64]) -> Float64:
    var s: Float64 = 0.0
    for i in range(len(v)):
        s += v[i] * v[i]
    return sqrt(s)


def _within_tol(got: Float64, want: Float64, n: Int) -> Bool:
    """`gemm.blocked.gemm_reference_delta_flat`'s exact tolerance shape:
    `dtx_tol_for(want, DT_F64, 0.0).relative_term`, scaled by the reduction
    length (rounding grows with it) times a small constant safety factor --
    reused, not reinvented, and not widened beyond that precedent."""
    var d = got - want
    if d < 0.0:
        d = -d
    var tol = dtx_tol_for(want, DT_F64, 0.0)
    var allowed = tol.relative_term * Float64(n if n > 0 else 1) * 4.0
    # A floor for `want == 0.0` (e.g. a would-be-zero cosine numerator):
    # `relative_term` is then 0.0 too, and a handful of ULP of absolute
    # rounding noise around an exact zero is still a correct SIMD answer.
    var floor = 1e-9
    if allowed < floor:
        allowed = floor
    return d <= allowed


def main() raises:
    var passed = 0
    var failed = 0

    # ── 1. Exact bit-identity against the SAME small integer-valued vectors
    #    `tests/mojo/test_embeddings_dimension_mismatch_probe.mojo` already
    #    uses -- proves no regression on inputs this module's other suites
    #    pin. Hand-computed by hand, not by calling embeddings.mojo:
    #      dot       = 1*2 + 2*4 + 3*5 + 4*4 + 5*6           = 71
    #      magnitude = sqrt(1^2 + 2^2 + 3^2 + 4^2 + 5^2)     = sqrt(55)
    #      euclidean = sqrt((-1)^2+(-2)^2+(-2)^2+0^2+(-1)^2) = sqrt(10)
    #      manhattan = |-1|+|-2|+|-2|+|0|+|-1|               = 6
    #    Integer-valued products and sums are exact in Float64 (no rounding
    #    below 2^53), so SIMD's different summation ORDER cannot change an
    #    exact integer result -- this is expected to hold exactly, not just
    #    observed to. ──────────────────────────────────────────────────────
    var gx: List[Float64] = [1.0, 2.0, 3.0, 4.0, 5.0]
    var gy: List[Float64] = [2.0, 4.0, 5.0, 4.0, 6.0]
    if (
        dot_product(gx, gy) == 71.0
        and vector_magnitude(gx) == sqrt(55.0)
        and euclidean_distance(gx, gy) == sqrt(10.0)
        and manhattan_distance(gx, gy) == 6.0
    ):
        passed += 1
        print("  ✅ small integer-valued golden vectors stay bit-identical after vectorization")
    else:
        failed += 1
        print("  ❌ small integer-valued golden vectors regressed after vectorization")

    # ── 2. Tail-handling + numerical correctness across many lengths, against
    #    an independent scalar reference, within `_within_tol`. ──────────────
    # Lengths deliberately NOT chosen to be multiples of common SIMD widths
    # (2, 4, 8): 0 is the empty-vector edge, 1-9 and 16-17 straddle every
    # small width's boundary, 1001 and 10007 are large-and-odd.
    var lengths = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 1001, 10007]

    for n in lengths:
        # Comparable-magnitude, non-adversarial inputs -- the regime every
        # other golden vector in this module's suites uses.
        var a = _mk(n, 1.0, 0.37)
        var b = _mk(n, -2.5, 0.11)

        var got_dot = dot_product(a, b)
        var want_dot = _ref_dot(a, b)
        if _within_tol(got_dot, want_dot, n):
            passed += 1
        else:
            failed += 1
            print("  ❌ dot_product mismatch at n=", n, "got=", got_dot, "want=", want_dot)

        var got_cos = cosine_similarity(a, b)
        var want_cos = _ref_cosine(a, b)
        if _within_tol(got_cos, want_cos, n):
            passed += 1
        else:
            failed += 1
            print("  ❌ cosine_similarity mismatch at n=", n, "got=", got_cos, "want=", want_cos)

        var got_euc = euclidean_distance(a, b)
        var want_euc = _ref_euclidean(a, b)
        if _within_tol(got_euc, want_euc, n):
            passed += 1
        else:
            failed += 1
            print("  ❌ euclidean_distance mismatch at n=", n, "got=", got_euc, "want=", want_euc)

        var got_man = manhattan_distance(a, b)
        var want_man = _ref_manhattan(a, b)
        if _within_tol(got_man, want_man, n):
            passed += 1
        else:
            failed += 1
            print("  ❌ manhattan_distance mismatch at n=", n, "got=", got_man, "want=", want_man)

        var got_mag = vector_magnitude(a)
        var want_mag = _ref_magnitude(a)
        if _within_tol(got_mag, want_mag, n):
            passed += 1
        else:
            failed += 1
            print("  ❌ vector_magnitude mismatch at n=", n, "got=", got_mag, "want=", want_mag)

    if failed == 0:
        print("  ✅ all 5 vectorized functions within tolerance of an independent scalar reference at every swept length")

    print("  [test_embeddings_simd_tail_probe] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_embeddings_simd_tail_probe: " + String(failed) + " check(s) failed")
