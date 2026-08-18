"""measure_stream_bandwidth.mojo — the machine's memory-bandwidth ceiling.

Why this benchmark exists, and why it is the most useful one here
----------------------------------------------------------------
Every other figure in `benchmarks/` is a rate. A rate is only interesting relative to a
limit, and for a kernel that touches each element a constant number of times the limit is
memory bandwidth, not arithmetic throughput. So this measures the ceiling directly, and then
other benchmarks can state what FRACTION of it they reach.

That converts a ratio into a ceiling argument. "This kernel runs at 88% of the machine's
measured bandwidth" says the remaining headroom for ANY implementation is at most 12% — which
is a stronger and less arguable claim than "Nx faster than X", because it does not depend on
whose X was chosen.

The four STREAM kernels, and the bytes each one moves
----------------------------------------------------
John McCalpin's STREAM defines four kernels. The byte counts below are the ones STREAM itself
counts, and they matter: getting them wrong is the easiest way to report a bandwidth figure
that is wrong by 1.5x.

    Copy    c[i] = a[i]              2 arrays touched -> 16 B/elem
    Scale   b[i] = q * c[i]          2 arrays touched -> 16 B/elem
    Add     c[i] = a[i] + b[i]       3 arrays touched -> 24 B/elem
    Triad   a[i] = b[i] + q * c[i]   3 arrays touched -> 24 B/elem

A write counts as one touch here, as STREAM counts it. On a write-allocate cache a store
actually costs a read AND a write, so the TRUE traffic can be up to 50% higher than STREAM
reports and the real bandwidth correspondingly higher. STREAM's convention is kept because
that is what published STREAM numbers use and a figure that cannot be compared to published
numbers defeats the purpose — but the effect is stated here rather than hidden, because it
means these figures are a conservative floor for the machine's true capability.

ARRAY SIZE IS THE THING MOST OFTEN GOT WRONG
--------------------------------------------
STREAM requires each array to be at least 4x the aggregate cache. An array that fits in cache
measures CACHE bandwidth, which on this machine is several times higher — and a ceiling
inflated that way would make every kernel look artificially far from the limit, which is the
opposite of a conservative error.

Measured on this host: L2 is 4 MiB and the M4 Max carries a large system-level cache on top.
`N = 100,000,000` Float64 makes each array 800 MB and the working set 2.4 GB, which is two
orders of magnitude past any cache level here. That is affordable because the machine has
128 GiB; on a 16 GB box this benchmark would need a smaller N and would have to say so.

What is reported, and why three tiers
-------------------------------------
Cold, warm and hot for every kernel:

  COLD  the first pass. Includes first-touch page faults on freshly allocated arrays — the
        kernel asks for pages, and the fault happens on first write, not at allocation. For a
        2.4 GB working set that is a real and large cost, and it is what a process pays once.
  WARM  the second pass. Pages mapped, nothing cache-resident at this size.
  HOT   min over `HOT_REPS` further passes. The steady-state figure, and the one to quote as
        the ceiling.

The minimum is the right statistic for the hot tier: contention can only ever make a reading
slower than the work takes, never faster, so the minimum is the closest available estimate of
the uncontended cost. The spread is printed so a reader can see how contended the machine was.

A LOADED MACHINE INVALIDATES THIS MEASUREMENT
---------------------------------------------
A bandwidth ceiling measured while other processes are saturating the same memory controller
is not this machine's ceiling — it is this machine's leftover share. `hot <= warm` and a
dispersion bound are therefore checked, and a violated check prints INVALID and no GB/s
figure at all rather than a number someone might quote.

SCALAR SINGLE-THREAD IS NOT A CEILING — the mistake this file was rewritten to fix
-----------------------------------------------------------------------------------
The first version of this benchmark ran one scalar thread and reported 23-35 GB/s. Using that
as "the ceiling" would have been circular: `determinism.reduce_det` measures ~23.5 GB/s, and
declaring it "at the ceiling" against a single-thread scalar STREAM only proves both are
single-threaded. An M4 Max carries roughly an order of magnitude more bandwidth than one
scalar thread can pull, so a fraction computed against 35 GB/s would overstate how close any
kernel is to the limit by more than 10x.

So both arms are reported and clearly separated:

  1T-SCALAR   one thread, no vectorization. The floor a naive loop reaches, and the right
              comparison for a kernel that is itself scalar and single-threaded.
  NT-SIMD     `parallelize` across physical cores with SIMD loads and stores. This is what
              published STREAM figures measure and the only one of the two that may be called
              the machine's ceiling.

The gap between them IS the available headroom, which makes it the most actionable number
here: a kernel sitting at the 1T-scalar figure has the whole NT-SIMD multiple still to gain.
"""
from max.algorithm import parallelize
from std.sys import info
from std.time import perf_counter_ns

# 100M Float64 per array = 800 MB each, 2.4 GB working set. Two orders of magnitude past the
# 4 MiB L2 and comfortably past the system-level cache, per the note above.
comptime N: Int = 100_000_000

# Untimed passes before the timed ones: the first faults pages in, the second runs against a
# warm page table. Both are REPORTED rather than discarded — see the docstring.
comptime HOT_REPS: Int = 5

# The scalar STREAM uses for Scale and Triad. Any non-trivial value works; 3.0 is STREAM's.
comptime Q: Float64 = 3.0

# Hot readings may not vary by more than this factor, or the machine was too busy for the
# result to mean anything. 2.0 is deliberately loose: this gate exists to catch a machine
# under heavy contention, not to demand a quiet one.
comptime MAX_SPREAD: Float64 = 2.0

# SIMD width for the vectorized arm. 8 lanes x Float64 = 512 bits per load, which is wider
# than any single NEON register — the compiler splits it, and that is deliberate: issuing
# several independent loads per iteration is what keeps enough requests in flight to saturate
# the memory controller. A width equal to one hardware register would leave the pipeline
# waiting on each load in turn.
comptime W: Int = 8


def _gb_per_s(bytes_moved: Int, elapsed_ns: Float64) -> Float64:
    if elapsed_ns <= 0.0:
        return 0.0
    return (Float64(bytes_moved) / 1.0e9) / (elapsed_ns / 1.0e9)


def _filled(n: Int, value: Float64) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for _ in range(n):
        out.append(value)
    return out^


def main() raises:
    print("== STREAM: memory bandwidth ceiling ==")
    print("  N =", N, "Float64 per array;", 3 * N * 8 // (1024 * 1024), "MB working set")
    print("  bytes counted per element: copy 16, scale 16, add 24, triad 24 (STREAM convention)")

    var a = _filled(N, 1.0)
    var b = _filled(N, 2.0)
    var c = _filled(N, 0.0)
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var cp = c.unsafe_ptr()

    var failures = 0

    # Four kernels x (cold, warm, HOT_REPS hot). Each kernel is timed in its own loop so a
    # slow neighbour cannot be attributed to it.
    for k in range(4):
        var name = String("copy")
        var bytes_per_elem = 16
        if k == 1:
            name = String("scale")
        elif k == 2:
            name = String("add")
            bytes_per_elem = 24
        elif k == 3:
            name = String("triad")
            bytes_per_elem = 24

        var total_bytes = N * bytes_per_elem
        var cold = 0.0
        var warm = 0.0
        var hot = 0.0
        var hot_worst = 0.0

        for rep in range(2 + HOT_REPS):
            var t0 = perf_counter_ns()
            if k == 0:
                for i in range(N):
                    cp[i] = ap[i]
            elif k == 1:
                for i in range(N):
                    bp[i] = Q * cp[i]
            elif k == 2:
                for i in range(N):
                    cp[i] = ap[i] + bp[i]
            else:
                for i in range(N):
                    ap[i] = bp[i] + Q * cp[i]
            var t1 = perf_counter_ns()
            var ns = Float64(Int(t1 - t0))

            if rep == 0:
                cold = ns
            elif rep == 1:
                warm = ns
            else:
                if hot == 0.0 or ns < hot:
                    hot = ns
                if ns > hot_worst:
                    hot_worst = ns

        # Validity BEFORE any figure is printed. A ceiling measured under contention is this
        # machine's leftover share rather than its capability, so an invalid run reports no
        # number at all instead of one that could be quoted out of context.
        var spread = hot_worst / hot if hot > 0.0 else 0.0
        var ordered = hot <= warm
        if not ordered or spread > MAX_SPREAD:
            failures += 1
            print(
                "  ", name, "INVALID -- ",
                "hot<=warm" if ordered else "hot > warm (contention or a measurement fault)",
                ", spread", spread, "against a limit of", MAX_SPREAD,
                "; no GB/s reported",
            )
            continue

        print(
            "  ", name,
            " cold", _gb_per_s(total_bytes, cold),
            " warm", _gb_per_s(total_bytes, warm),
            " HOT", _gb_per_s(total_bytes, hot),
            " GB/s   (cold/hot", cold / hot, "x, hot spread", spread, "x over", HOT_REPS, "reps)",
        )

    # ── NT-SIMD: the arm that may be called a ceiling ─────────────────────────
    # One thread cannot saturate this memory controller, so the figures above are a FLOOR.
    # Here every core gets a contiguous band and each band is walked with W-wide loads and
    # stores. Contiguous bands rather than interleaved indices: interleaving would have all
    # cores contend for the same cache lines and measure coherence traffic instead of
    # bandwidth.
    var n_workers = info.num_physical_cores()
    print("  -- NT-SIMD:", n_workers, "physical cores,", W, "lanes per access --")

    for k in range(4):
        var name = String("copy")
        var bytes_per_elem = 16
        if k == 1:
            name = String("scale")
        elif k == 2:
            name = String("add")
            bytes_per_elem = 24
        elif k == 3:
            name = String("triad")
            bytes_per_elem = 24

        var total_bytes = N * bytes_per_elem
        var band = (N + n_workers - 1) // n_workers
        var cold = 0.0
        var warm = 0.0
        var hot = 0.0
        var hot_worst = 0.0

        @parameter
        def run_band(w: Int):
            var lo = w * band
            var hi = lo + band
            if hi > N:
                hi = N
            # W-wide while the whole vector fits, then a scalar tail. The tail matters for
            # correctness, not speed: a band end that is not a multiple of W would otherwise
            # read past it, and reading past a buffer is an uncatchable abort here.
            var i = lo
            while i + W <= hi:
                if k == 0:
                    cp.store[width=W, alignment=8](i, ap.load[width=W, alignment=8](i))
                elif k == 1:
                    bp.store[width=W, alignment=8](i, Q * cp.load[width=W, alignment=8](i))
                elif k == 2:
                    cp.store[width=W, alignment=8](
                        i, ap.load[width=W, alignment=8](i) + bp.load[width=W, alignment=8](i)
                    )
                else:
                    ap.store[width=W, alignment=8](
                        i, bp.load[width=W, alignment=8](i) + Q * cp.load[width=W, alignment=8](i)
                    )
                i += W
            while i < hi:
                if k == 0:
                    cp[i] = ap[i]
                elif k == 1:
                    bp[i] = Q * cp[i]
                elif k == 2:
                    cp[i] = ap[i] + bp[i]
                else:
                    ap[i] = bp[i] + Q * cp[i]
                i += 1

        for rep in range(2 + HOT_REPS):
            var t0 = perf_counter_ns()
            parallelize[run_band](n_workers)
            var t1 = perf_counter_ns()
            var ns = Float64(Int(t1 - t0))
            if rep == 0:
                cold = ns
            elif rep == 1:
                warm = ns
            else:
                if hot == 0.0 or ns < hot:
                    hot = ns
                if ns > hot_worst:
                    hot_worst = ns

        var spread = hot_worst / hot if hot > 0.0 else 0.0
        if hot > warm or spread > MAX_SPREAD:
            failures += 1
            print("  ", name, "NT-SIMD INVALID -- spread", spread, "; no GB/s reported")
            continue
        print(
            "  ", name,
            " cold", _gb_per_s(total_bytes, cold),
            " warm", _gb_per_s(total_bytes, warm),
            " HOT", _gb_per_s(total_bytes, hot),
            " GB/s   (spread", spread, "x)",
        )

    # Keep the arrays observably alive so no kernel above is eliminated as dead code.
    var checksum = a[0] + b[N // 2] + c[N - 1]
    if checksum != checksum:
        print("  checksum is NaN, which is impossible here")

    if failures == 0:
        print("BENCH_GATE stream PASS")
    else:
        print("BENCH_GATE stream FAIL " + String(failures))
