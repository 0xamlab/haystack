"""
bench_vs_spmv — `sparse_numerics` SpMV against scipy.sparse's compiled C kernel.

What is compared, and against what
----------------------------------
The baseline is `scipy.sparse.csr_matrix.dot` from scipy 1.18.0 — `csr_matvec` in
`scipy/sparse/_sparsetools`, a compiled C++ template. It is single-threaded (there is no
threaded SpMV in scipy) but it is real compiled code with no per-call validation, which
makes it the honest competitor for a sparse product. It is driven by
`bench_vs_spmv_driver.py`, which builds bit-identical matrices, times its own arms, and
checks our result vectors against its own.

The Python side is a SEPARATE PROCESS, so the two cannot be interleaved inside one timing
loop. The driver instead alternates whole sweeps — ours, theirs, ours, theirs — and takes
the median per case per side, so both sample the same contention window. Every arm inside
THIS file, by contrast, is genuinely interleaved: the arms are re-timed in rotation within
one process against one matrix, which is why the seq-vs-parallel crossover measured here
is the highest-confidence number in the report.

Why SpMV cannot approach a streaming ceiling, and why that is not a failure
--------------------------------------------------------------------------
`measure_stream_bandwidth.mojo` puts this host's NT-SIMD ceiling near 271 GB/s on a
quiet machine. SpMV will not come close, and the reason is structural rather than a
defect in the kernel:

  1. The load of `x[indices[k]]` cannot be issued until `indices[k]` has itself arrived.
     That is a dependent load — a pointer chase one level deep, per nonzero — and the
     hardware prefetcher cannot run ahead of it because the address is data, not a
     stride. STREAM's loads are all independent and their addresses are known in advance.
  2. Each nonzero costs 16 bytes of guaranteed traffic in this layout (8-byte value +
     8-byte `Int` index) for 2 flops, plus an unpredictable number of cache lines for the
     gather into `x`. A row that touches 9 scattered columns can pull 9 separate 64-byte
     lines to read 72 useful bytes.
  3. Rows are short. A 9-nonzero row is 9 iterations of a loop carrying a serial add
     dependency, then a branch. There is no long run to vectorize over.

So the useful figure is NONZEROS PER SECOND, and it is reported as the headline. Bytes/s
is also printed, but only over the guaranteed `indptr`/`indices`/`values` traffic — the
gather into `x` is deliberately NOT counted, because its true cost depends on the
pattern, and counting a guessed number of cache lines would inflate the figure. That
makes the printed GB/s a LOWER BOUND on real traffic, and no fraction of 271 GB/s is
computed from it.

The index-width asymmetry, stated because it favours the baseline and we lose by it
-----------------------------------------------------------------------------------
`CSRMatrix.indices` is `List[Int]`, which is 64-bit. scipy defaults to `int32` indices
whenever the matrix fits, so a scipy user moves 12 bytes per nonzero where we move 16 —
a 1.33x traffic disadvantage on a bandwidth-bound kernel that exists in the LAYOUT,
before any question of code quality. The driver therefore times scipy twice: once with
its default `int32` indices (what a scipy user actually gets) and once coerced to `int64`
(index-width matched to ours). Both are reported. Reporting only the int64 arm would be
quietly handicapping the baseline.

The two arms of ours
--------------------
  spmv_matvec   the public typed entry as it stands today: `csr_matvec` plus a full
                `inner.values.copy()`. This is what a caller composing this module
                reaches right now, so it is timed; dropping it would be dropping a real
                cost from our side.
  csr_matvec    the arithmetic, the per-call `csr_validate` gate, and bounds-checked
                `List` indexing throughout. scipy does not re-validate per `dot`, so this
                arm is our validate+multiply against their multiply -- the like-for-like
                comparison, since neither side is threaded.

There is no parallel or unchecked SpMV entry point in `sparse_numerics.spmv` today --
only `spmv_matvec` and the arithmetic it wraps, `csr.csr_matvec`. Both arms are reported
rather than just the faster one.

The gate
--------
Per arm: `hot <= warm`, and hot spread within a bound. A violated check prints INVALID and
NO figure, because a number taken under contention is this machine's leftover share rather
than its capability. The failure reason names the conditions that ACTUALLY failed —
`measure_stream_bandwidth.mojo`'s 1T arm has a bug here, printing `hot<=warm` (the
condition that held) whenever spread is the real violation, which misleads anyone parsing
gate strings.

Determinism of the inputs
-------------------------
Every matrix and vector is a pure function of its position through splitmix64, so the
driver rebuilds the same bits in numpy with no file exchange and no RNG-seed agreement to
get wrong. Verified equal to the last bit against this file's `_unit`.
"""
from std.algorithm import parallelize
from std.sys import info
from std.time import perf_counter_ns

from sparse_numerics.csr import (
    CSRMatrix,
    CSR_OK,
    csr_from_arrays,
    csr_matvec,
    csr_validate,
)
from sparse_numerics.spmv import spmv_matvec

# Untimed-then-timed reps. cold = rep 0, warm = rep 1, hot = best of the rest, matching
# `measure_stream_bandwidth.mojo` so the two files' tiers mean the same thing.
#
# 9 rather than that file's 5. `hot` is a MINIMUM, which on a contended host estimates the
# uncontended time — more samples make it a better estimate and make the `hot <= warm`
# check less likely to trip on a merely lucky warm rep. It cuts the other way on spread,
# since max/min over more samples has more chances to catch an outlier; that is the
# correct direction for a gate whose job is to notice contention.
comptime HOT_REPS: Int = 9

# Hot readings may not vary by more than this factor or the machine was too busy for the
# reading to mean anything. Deliberately loose: this catches contention, not jitter.
comptime MAX_SPREAD: Float64 = 2.0

# Position seeds. Distinct so the column jitter, the values and x are independent streams.
comptime SEED_COL: UInt64 = 0x51_43_2A_11
comptime SEED_VAL: UInt64 = 0x9E_37_79_B1
comptime SEED_X: UInt64 = 0x2C_1B_3F_07

# Row stride in the value stream's position index. Any odd constant works; it only has to
# be the same on both sides.
comptime VAL_ROW_STRIDE: UInt64 = 1_000_003

comptime PATTERN_BAND: Int = 0
comptime PATTERN_SCATTER: Int = 1

# Half-width of the banded pattern: 4 either side plus the diagonal = 9 per interior row.
comptime BAND_HALF: Int = 4


def mix64(p: UInt64) -> UInt64:
    """splitmix64's finalizer over a position. Counter-based, so it vectorizes in numpy."""
    var z = p + 0x9E3779B97F4A7C15
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)


def _unit(p: UInt64) -> Float64:
    """Position `p` mapped into [-1, 1).

    53 bits over 2^53 then scaled: both steps are exact in binary64, so numpy reproduces
    this bit for bit rather than approximately.
    """
    return Float64(Int(mix64(p) >> 11)) * (1.0 / 9007199254740992.0) * 2.0 - 1.0


def _value_at(i: Int, j: Int) -> Float64:
    """The stored value for coordinate (i, j). Indexed by POSITION, not by a running
    counter, so a pattern with ragged rows needs no prefix sum to reproduce."""
    return _unit(SEED_VAL + UInt64(i) * VAL_ROW_STRIDE + UInt64(j))


@fieldwise_init
struct Case(Copyable, Movable):
    var name: String
    var pattern: Int
    var n: Int
    var nnz_row: Int
    var dump: Bool


def _build(spec: Case) -> CSRMatrix:
    """The case's matrix in CSR. Sorted indices, no duplicates, by construction.

    `csr_from_arrays` sets `sorted_indices=False` regardless of what is handed to it, so
    the flag on the result is a false negative; the benchmark does not read it, and every
    consumer here either validates or is told it must have been validated.
    """
    var n = spec.n
    var indptr = List[Int](capacity=n + 1)
    var nnz_guess = n * spec.nnz_row + 8
    var indices = List[Int](capacity=nnz_guess)
    var values = List[Float64](capacity=nnz_guess)
    indptr.append(0)

    if spec.pattern == PATTERN_BAND:
        for i in range(n):
            var lo = i - BAND_HALF
            if lo < 0:
                lo = 0
            var hi = i + BAND_HALF + 1
            if hi > n:
                hi = n
            for j in range(lo, hi):
                indices.append(j)
                values.append(_value_at(i, j))
            indptr.append(len(indices))
    else:
        # Scattered but strictly ascending: slot k gets a jittered offset inside its own
        # stride-wide window, so columns cannot collide and no sort is needed. A uniform
        # random draw would need a distinct-sampling algorithm reproduced exactly in numpy;
        # this needs only integer arithmetic, and it still defeats the prefetcher, which is
        # the property the benchmark is about.
        var per_row = spec.nnz_row
        if per_row > n:
            per_row = n
        var stride = n // per_row
        if stride < 1:
            stride = 1
        for i in range(n):
            for k in range(per_row):
                var base = k * stride
                var jit = 0
                if stride > 1:
                    jit = Int(
                        mix64(SEED_COL + UInt64(i) * UInt64(per_row) + UInt64(k))
                        % UInt64(stride)
                    )
                var j = base + jit
                if j >= n:
                    j = n - 1
                indices.append(j)
                values.append(_value_at(i, j))
            indptr.append(len(indices))

    return csr_from_arrays(indptr, indices, values, n, n)


def _build_x(n: Int) -> List[Float64]:
    var x = List[Float64](capacity=n)
    for j in range(n):
        x.append(_unit(SEED_X + UInt64(j)))
    return x^


def _dump(path: String, v: List[Float64], length: Int) raises:
    """Write `v[0..length)` as decimal binary64 BIT PATTERNS, one per line.

    Bit patterns rather than formatted decimals: a correctness comparison is only as tight
    as its transport, and a printed float that does not round-trip would put a fake delta
    into the tolerance check. `List`'s buffer reinterpreted as UInt64 is exact by
    construction.

    Chunked so the accumulating String is bounded rather than proportional to the vector.
    """
    var bp = v.unsafe_ptr().bitcast[UInt64]()
    with open(path, "w") as f:
        var chunk = String()
        for i in range(length):
            chunk += String(bp[i])
            chunk += "\n"
            if len(chunk) > 1 << 20:
                f.write(chunk)
                chunk = String()
        if len(chunk) > 0:
            f.write(chunk)


@fieldwise_init
struct Timing(Copyable, Movable):
    var cold: Float64
    var warm: Float64
    var hot: Float64
    var worst: Float64
    var valid: Bool
    var reason: String


def _verdict(cold: Float64, warm: Float64, hot: Float64, worst: Float64) -> Timing:
    """Tiers plus the gate's verdict. The reason names only conditions that FAILED."""
    var spread = worst / hot if hot > 0.0 else 0.0
    var ordered = hot <= warm
    var tight = spread <= MAX_SPREAD
    if ordered and tight and hot > 0.0:
        return Timing(cold, warm, hot, worst, True, String(""))
    var why = String()
    if hot <= 0.0:
        why += "clock saw no work; "
    if not ordered:
        why += "hot > warm (contention or a measurement fault); "
    if not tight:
        why += "hot spread " + String(spread) + " over limit " + String(MAX_SPREAD) + "; "
    return Timing(cold, warm, hot, worst, False, why)


def _fold(cold: Float64, warm: Float64, reps: List[Float64]) -> Timing:
    var hot = 0.0
    var worst = 0.0
    for r in range(len(reps)):
        var ns = reps[r]
        if hot == 0.0 or ns < hot:
            hot = ns
        if ns > worst:
            worst = ns
    return _verdict(cold, warm, hot, worst)


def _per_nnz(t: Float64, nnz: Int) -> Float64:
    if nnz <= 0 or t <= 0.0:
        return 0.0
    return t / Float64(nnz)


def _nnz_per_s(t: Float64, nnz: Int) -> Float64:
    if t <= 0.0:
        return 0.0
    return Float64(nnz) / (t / 1.0e9)


def _row(label: String, t: Timing, nnz: Int) -> String:
    """One harness-parseable cold/warm/hot triple in ns per nonzero, or an INVALID line
    carrying no figure at all."""
    if not t.valid:
        return "  " + label + " INVALID -- " + t.reason + "no figure reported"
    return (
        "  " + label + " ......... "
        + String(_per_nnz(t.cold, nnz)) + " / "
        + String(_per_nnz(t.warm, nnz)) + " / "
        + String(_per_nnz(t.hot, nnz))
    )


def main() raises:
    var cores = info.num_physical_cores()
    if cores < 1:
        cores = 1
    print("== bench_vs_spmv: sparse_numerics SpMV vs scipy.sparse ==")
    print("  physical cores:", cores, " HOT_REPS:", HOT_REPS, " MAX_SPREAD:", MAX_SPREAD)
    print("  ours moves 16 B/nnz (Float64 value + 64-bit Int index); scipy int32 moves 12")
    print("  headline unit is nonzeros/second; see the module docstring on why not GB/s")
    print("")

    var failures = 0

    # ── the cases ─────────────────────────────────────────────────────────────
    # band9 is a stencil/finite-difference pattern: 9 per row, columns adjacent, the
    # friendliest thing a gather can be handed. scatter1pct and scatter01pct spread the
    # same row width over the whole column space, which is what defeats the prefetcher.
    # `dump` marks the cases whose result vector is written for the driver's tolerance
    # check; the largest are excluded to keep the exchange file bounded, and they are
    # covered by the in-process bit-identity assertion instead.
    var cases = List[Case]()
    cases.append(Case(String("band9_4k"), PATTERN_BAND, 4096, 9, True))
    cases.append(Case(String("band9_64k"), PATTERN_BAND, 65536, 9, True))
    cases.append(Case(String("band9_512k"), PATTERN_BAND, 524288, 9, True))
    cases.append(Case(String("band9_2m"), PATTERN_BAND, 2097152, 9, False))
    cases.append(Case(String("scatter1pct_2k"), PATTERN_SCATTER, 2048, 20, True))
    cases.append(Case(String("scatter1pct_16k"), PATTERN_SCATTER, 16384, 163, True))
    cases.append(Case(String("scatter1pct_40k"), PATTERN_SCATTER, 40960, 409, False))
    cases.append(Case(String("scatter01pct_8k"), PATTERN_SCATTER, 8192, 8, True))
    cases.append(Case(String("scatter01pct_64k"), PATTERN_SCATTER, 65536, 65, True))
    cases.append(Case(String("scatter01pct_128k"), PATTERN_SCATTER, 131072, 131, False))
    # The case the three above do NOT cover, and the omission mattered: their x vectors are
    # 16 KB to 1 MB, so x stays resident in cache and the "scatter" never actually pays for
    # a gather. Here x is 2M Float64 = 16.8 MB, past L2, and each row's 8 columns are drawn
    # from 262144-wide windows spanning the whole 2M column space. This is the pattern the
    # module docstring's prefetch argument is really about, and the only case here where
    # the dependent load has to go to memory.
    cases.append(Case(String("scatter_bigx_2m"), PATTERN_SCATTER, 2097152, 8, False))

    for c in range(len(cases)):
        var spec = cases[c].copy()
        var m = _build(spec)
        var nnz = len(m.values)
        var x = _build_x(spec.n)

        # ── correctness BEFORE any timing ─────────────────────────────────────
        var status = csr_validate(m)
        if status != CSR_OK:
            print("❌", spec.name, "matrix invalid, status", status)
            failures += 1
            continue

        var oracle = csr_matvec(m, x)
        if oracle.status != CSR_OK or oracle.length != spec.n:
            print("❌", spec.name, "oracle failed, status", oracle.status)
            failures += 1
            continue

        # `spmv_matvec` is a thin typed wrapper over `csr_matvec` (see the module
        # docstring); it must agree with it to the LAST BIT, not a tolerance.
        var bitbad = 0
        var wrapper = spmv_matvec(m, x)
        for i in range(oracle.length):
            if wrapper.values[i] != oracle.values[i]:
                bitbad += 1
                break
        if bitbad != 0:
            print("❌", spec.name, "bit-identity FAILED, defects", bitbad)
            failures += 1

        print("rows=" + String(spec.n) + " cols=" + String(spec.n))
        print(
            "  case", spec.name,
            " nnz", nnz,
            " nnz/row", Float64(nnz) / Float64(spec.n),
            " bytes(ours)", nnz * 16 + (spec.n + 1) * 8,
        )
        print(
            "  spmv_matvec bit-identical to csr_matvec:",
            "YES" if bitbad == 0 else "NO",
        )
        if spec.dump:
            _dump("/tmp/spmv_bench_out_" + spec.name + ".txt", oracle.values, oracle.length)
            print("  dumped result vector for the scipy tolerance check")

        # ── timing, arms INTERLEAVED in rotation ──────────────────────────────
        # Round-robin over the arms inside each rep rather than one arm to completion, so
        # a contention spike during the run lands on both arms rather than on whichever one
        # happened to be running. This is the interleaving the cross-process comparison
        # cannot have.
        #
        #   0 spmv_matvec   validate + bounds-checked multiply + values.copy()
        #   1 csr_matvec    validate + bounds-checked multiply
        #
        # 0 minus 1 is the wrapper's extra copy -- separately actionable.
        var n_arms = 2
        var cold_a = List[Float64]()
        var warm_a = List[Float64]()
        var reps_0 = List[Float64]()
        var reps_1 = List[Float64]()
        for _ in range(n_arms):
            cold_a.append(0.0)
            warm_a.append(0.0)

        for rep in range(2 + HOT_REPS):
            for arm in range(n_arms):
                var t0 = perf_counter_ns()
                if arm == 0:
                    var r = spmv_matvec(m, x)
                    if r.length != spec.n:
                        failures += 1
                else:
                    var r = csr_matvec(m, x)
                    if r.length != spec.n:
                        failures += 1
                var t1 = perf_counter_ns()
                var ns = Float64(Int(t1 - t0))
                if rep == 0:
                    cold_a[arm] = ns
                elif rep == 1:
                    warm_a[arm] = ns
                else:
                    if arm == 0:
                        reps_0.append(ns)
                    else:
                        reps_1.append(ns)

        var t_wrap = _fold(cold_a[0], warm_a[0], reps_0)
        var t_inner = _fold(cold_a[1], warm_a[1], reps_1)

        print("cold / warm / hot, ns per nonzero")
        print(_row(String("spmv_matvec_wrapper"), t_wrap, nnz))
        print(_row(String("csr_matvec_validating"), t_inner, nnz))
        if not t_wrap.valid:
            failures += 1
        if not t_inner.valid:
            failures += 1

        # Machine lines in nonzeros/second, the headline unit.
        if t_wrap.valid:
            print(
                "COLD_WARM_HOT", "wrapper_nnzps",
                _nnz_per_s(t_wrap.cold, nnz), _nnz_per_s(t_wrap.warm, nnz),
                _nnz_per_s(t_wrap.hot, nnz), "nnz/s",
            )
        if t_inner.valid:
            print(
                "COLD_WARM_HOT", "validating_nnzps",
                _nnz_per_s(t_inner.cold, nnz), _nnz_per_s(t_inner.warm, nnz),
                _nnz_per_s(t_inner.hot, nnz), "nnz/s",
            )

        # The only internal decomposition available now that there is no parallel or
        # unchecked arm: the wrapper's copy on top of the validated multiply.
        if t_wrap.valid and t_inner.valid:
            print("  wrapper copy overhead (wrapper/validating, hot):", t_wrap.hot / t_inner.hot, "x")
        # Lower bound only: the gather into x is not counted. See the module docstring.
        if t_inner.valid:
            var guaranteed = nnz * 16 + (spec.n + 1) * 8
            print(
                "  guaranteed-traffic GB/s (LOWER BOUND, gather excluded):",
                (Float64(guaranteed) / 1.0e9) / (t_inner.hot / 1.0e9),
            )
        print("")

    if failures == 0:
        print("BENCH_GATE spmv PASS")
    else:
        print("BENCH_GATE spmv FAIL " + String(failures))
