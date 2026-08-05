"""measure_embeddings_simd_speedup.mojo — real before/after wall-clock for the
SIMD vectorization added to `embeddings.dot_product`, `cosine_similarity`, and
`euclidean_distance` in this same change.

Hand-written, not generated. Not a competitive benchmark against an external
reference (no other engine/library is involved) — a same-process, same-input,
same-hardware comparison of two Mojo implementations of the identical
mathematical function:

  BEFORE  `_scalar_pre_simd_*` below, copied VERBATIM (loop body, accumulator,
          `_min_len` truncation and all) from `embeddings.mojo` at the commit
          immediately before this session's SIMD change (`git show
          <pre-simd-commit>:mojo/engine/embeddings.mojo`). Renamed only to
          avoid colliding with the real names on import; not a single line
          of arithmetic changed.
  AFTER   `dot_product` / `cosine_similarity` / `euclidean_distance`, imported
          directly from the real `embeddings` module -- the actual production
          functions this benchmark's own repo ships, not a re-implementation.

Both arms run on the SAME pseudo-random input vectors, at THREE realistic
real-embedding-model output dimensions (384 -- e5-small/MiniLM-L12, 768 --
e5-base/BERT-base, 1536 -- OpenAI text-embedding-3-small), so the reported
multiple is the one that actually matters for the `/v1/embeddings/similarity`
API surface these kernels back.

Methodology, and why min-of-N rather than mean
-----------------------------------------------
Each arm is warmed once (first-touch page faults + branch predictor training
must not land in the timed region), then run for `REPS` calls per trial,
`TRIALS` trials, and the MINIMUM total across trials is reported as the hot
figure -- contention and scheduling noise can only make a trial slower than
the true steady-state cost, never faster, so the minimum is the closest
available estimate of the uncontended cost (same statistic
`measure_stream_bandwidth.mojo` uses for the same reason).

A checksum built from every call's return value is printed at the end so the
compiler cannot prove either loop's result is unused and eliminate it as dead
code -- the risk is real here because both arms are pure functions of inputs
that never change across the loop.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine \
    ../benchmarks/mojo_benchmarks/measure_embeddings_simd_speedup.mojo
"""
from std.math import sqrt
from std.time import perf_counter_ns

from embeddings import dot_product, cosine_similarity, euclidean_distance

# 384 = e5-small/MiniLM-L12 output width, 768 = e5-base/BERT-base, 1536 =
# OpenAI text-embedding-3-small -- three real embedding-model dimensions this
# module's own docstring and gitbook/llm/embeddings.md call out as the
# real-world case this API surface serves.
comptime DIMS_LEN: Int = 3


fn _dims() -> List[Int]:
    var out = List[Int]()
    out.append(384)
    out.append(768)
    out.append(1536)
    return out^


# REPS per trial x TRIALS per arm. Tuned so the fastest (SIMD, smallest dim)
# cell still runs long enough (single-digit ms) that perf_counter_ns's
# resolution is not itself a source of noise, while the slowest (scalar,
# largest dim) cell stays well under a second.
comptime REPS: Int = 200_000
comptime TRIALS: Int = 5


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic, non-integer values in roughly [-1, 1] -- reproducible
    across runs/machines, and explicitly NOT integer-valued so this is a
    realistic embedding-component distribution rather than the small
    integer inputs this module's golden tests happen to use (see the
    reassociation-ULP note in embeddings.mojo's own docstring)."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 2654435761 + seed * 40503) % 20000)) / 10000.0 - 1.0)
    return o^


# ── BEFORE: verbatim pre-SIMD scalar bodies, copied from embeddings.mojo at
# the commit immediately before this session's SIMD change. Renamed only to
# avoid colliding with the real (now-SIMD) names on import above. ──────────


fn _scalar_pre_simd_min_len(a: List[Float64], b: List[Float64]) -> Int:
    var n = len(a)
    if len(b) < n:
        n = len(b)
    return n


fn _scalar_pre_simd_dot_product(a: List[Float64], b: List[Float64]) -> Float64:
    var s: Float64 = 0.0
    var n = _scalar_pre_simd_min_len(a, b)
    for i in range(n):
        s += a[i] * b[i]
    return s


fn _scalar_pre_simd_cosine_similarity(a: List[Float64], b: List[Float64]) -> Float64:
    var dot: Float64 = 0.0
    var sq_a: Float64 = 0.0
    var sq_b: Float64 = 0.0
    var n = _scalar_pre_simd_min_len(a, b)
    for i in range(n):
        var av = a[i]
        var bv = b[i]
        dot += av * bv
        sq_a += av * av
        sq_b += bv * bv
    if sq_a <= 0.0 or sq_b <= 0.0:
        return 0.0
    return dot / (sqrt(sq_a) * sqrt(sq_b))


fn _scalar_pre_simd_euclidean_distance(a: List[Float64], b: List[Float64]) -> Float64:
    var s: Float64 = 0.0
    var n = _scalar_pre_simd_min_len(a, b)
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


fn _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def main() raises:
    print("=== embeddings SIMD vectorization: before/after wall-clock ===")
    print("REPS per trial =", REPS, " TRIALS =", TRIALS, " (hot = min total across trials)")
    print("")
    print("fn                    dim    before(ns/call)   after(ns/call)   speedup")

    var dims = _dims()
    var failures = 0
    var checksum: Float64 = 0.0

    for di in range(DIMS_LEN):
        var dim = dims[di]
        var a = _pseudo(dim, 1)
        var b = _pseudo(dim, 2)

        # ── dot_product ─────────────────────────────────────────────────────
        var _warm_before_dot = _scalar_pre_simd_dot_product(a, b)
        var _warm_after_dot = dot_product(a, b)
        checksum += _warm_before_dot + _warm_after_dot

        var before_dot_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += _scalar_pre_simd_dot_product(a, b)
            var ns = _ns_since(t0)
            if before_dot_hot == 0.0 or ns < before_dot_hot:
                before_dot_hot = ns

        var after_dot_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += dot_product(a, b)
            var ns = _ns_since(t0)
            if after_dot_hot == 0.0 or ns < after_dot_hot:
                after_dot_hot = ns

        var before_dot_per_call = before_dot_hot / Float64(REPS)
        var after_dot_per_call = after_dot_hot / Float64(REPS)
        var dot_speedup = before_dot_per_call / after_dot_per_call if after_dot_per_call > 0.0 else 0.0
        print("  dot_product         ", dim, "     ", before_dot_per_call, "     ", after_dot_per_call, "     ", dot_speedup, "x")
        if dot_speedup < 1.0:
            failures += 1

        # ── cosine_similarity ───────────────────────────────────────────────
        var _warm_before_cos = _scalar_pre_simd_cosine_similarity(a, b)
        var _warm_after_cos = cosine_similarity(a, b)
        checksum += _warm_before_cos + _warm_after_cos

        var before_cos_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += _scalar_pre_simd_cosine_similarity(a, b)
            var ns = _ns_since(t0)
            if before_cos_hot == 0.0 or ns < before_cos_hot:
                before_cos_hot = ns

        var after_cos_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += cosine_similarity(a, b)
            var ns = _ns_since(t0)
            if after_cos_hot == 0.0 or ns < after_cos_hot:
                after_cos_hot = ns

        var before_cos_per_call = before_cos_hot / Float64(REPS)
        var after_cos_per_call = after_cos_hot / Float64(REPS)
        var cos_speedup = before_cos_per_call / after_cos_per_call if after_cos_per_call > 0.0 else 0.0
        print("  cosine_similarity    ", dim, "     ", before_cos_per_call, "     ", after_cos_per_call, "     ", cos_speedup, "x")
        if cos_speedup < 1.0:
            failures += 1

        # ── euclidean_distance ──────────────────────────────────────────────
        var _warm_before_euc = _scalar_pre_simd_euclidean_distance(a, b)
        var _warm_after_euc = euclidean_distance(a, b)
        checksum += _warm_before_euc + _warm_after_euc

        var before_euc_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += _scalar_pre_simd_euclidean_distance(a, b)
            var ns = _ns_since(t0)
            if before_euc_hot == 0.0 or ns < before_euc_hot:
                before_euc_hot = ns

        var after_euc_hot = 0.0
        for _t in range(TRIALS):
            var t0 = perf_counter_ns()
            for _r in range(REPS):
                checksum += euclidean_distance(a, b)
            var ns = _ns_since(t0)
            if after_euc_hot == 0.0 or ns < after_euc_hot:
                after_euc_hot = ns

        var before_euc_per_call = before_euc_hot / Float64(REPS)
        var after_euc_per_call = after_euc_hot / Float64(REPS)
        var euc_speedup = before_euc_per_call / after_euc_per_call if after_euc_per_call > 0.0 else 0.0
        print("  euclidean_distance   ", dim, "     ", before_euc_per_call, "     ", after_euc_per_call, "     ", euc_speedup, "x")
        if euc_speedup < 1.0:
            failures += 1

        print("")

    if checksum != checksum:
        print("checksum is NaN, which is impossible here")

    print("(checksum, to keep every timed call live:", checksum, ")")

    if failures == 0:
        print("BENCH_GATE embeddings_simd_speedup PASS -- every vectorized fn is at least as fast, at all 3 real embedding dims")
    else:
        print("BENCH_GATE embeddings_simd_speedup FAIL", failures, "-- a vectorized fn was NOT faster than its pre-SIMD scalar body at some dimension")
