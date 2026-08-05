"""evolutionary_search — keyed, reproducible evolutionary search over the simulation parameters.

WHY THIS IS A KERNEL AND NOT A PYTHON LOOP

Two reasons, both load-bearing.

  * The compute boundary. Optimization is modelled computation, so a search heuristic that selects
    model parameters belongs in Mojo alongside the simulation and the metrics. Python may ferry a
    population and a fitness vector; it may not decide which candidates survive.
  * Reproducibility. `genetic.mutate_gaussian` draws from `random_float64()`, which is seeded from the
    process and cannot be replayed. A calibration result that cannot be reproduced is not evidence, and
    Invariant 1 requires counter-based keyed randomness for anything a claim rests on. Every draw here
    is addressed by (generation, individual, gene) so the entire search replays bit-exactly from
    `master_seed` alone -- and two runs on different core counts agree, because nothing depends on
    evaluation order.

The design is deliberately STATELESS: `ga_step` maps one scored generation to the next and holds no
corpus. That keeps the kernel small and lets the caller evaluate fitness however the experiment needs --
here, by simulating every race in the training fold with `outcome_distribution` and scoring with
`forecast_metrics`, so simulation, scoring and selection are all kernel-side while Python only moves
arrays.

Fitness is MAXIMISED. Genes are stored flat, individual-major: gene j of individual i is at
`pop[i * n_dim + j]`.
"""

from math import sqrt

from counter_rng import (
    rng_uniform,
    rng_normal,
    PROCESS_SEARCH,
)


fn ga_init(
    lo: List[Float64], hi: List[Float64], pop_size: Int, master_seed: Int
) -> List[Float64]:
    """Uniform initial population inside the bounds, flat and individual-major.

    Individual 0 is seeded at the MIDPOINT of every bound rather than at random. A search that can
    lose to its own starting point is hard to interpret, so the incumbent-like candidate is always
    present in generation 0 and elitism carries it forward until something beats it.
    """
    var n_dim = len(lo)
    # hi must cover every dimension and pop_size must be positive, or the bound reads and
    # the individual loop below abort the worker (uncatchable).
    if n_dim == 0 or len(hi) < n_dim or pop_size < 1:
        return List[Float64]()
    var pop = List[Float64]()
    for i in range(pop_size):
        for j in range(n_dim):
            var span = hi[j] - lo[j]
            if i == 0:
                pop.append(lo[j] + 0.5 * span)
            else:
                var u = rng_uniform(
                    UInt64(master_seed), 0, UInt64(i), 0, UInt64(j), PROCESS_SEARCH, 0
                )
                pop.append(lo[j] + u * span)
    return pop^


fn ga_step(
    pop: List[Float64], fitness: List[Float64], lo: List[Float64], hi: List[Float64],
    tournament: Int, cx_rate: Float64, mut_rate: Float64, mut_scale: Float64,
    elite: Int, master_seed: Int, generation: Int,
) -> List[Float64]:
    """One generation: elitism, then tournament selection, uniform crossover, Gaussian mutation.

    `mut_scale` is a FRACTION of each dimension's own range, not an absolute sigma. An absolute sigma
    is meaningless across a 12-dimensional parameter vector whose dimensions span 0.02 to 21 seconds --
    it would freeze the wide dimensions and destroy the narrow ones.
    """
    var n_dim = len(lo)
    var pop_size = len(fitness)
    var out = List[Float64]()
    # Shape contract: pop carries pop_size*n_dim genes and hi covers every dimension, or the
    # indexed reads below abort the worker (uncatchable).
    if n_dim == 0 or pop_size == 0 or len(hi) < n_dim or len(pop) < pop_size * n_dim:
        return out^

    # elitism: copy the top `elite` individuals by fitness, best first
    var taken = List[Bool]()
    for _ in range(pop_size):
        taken.append(False)
    var n_elite = elite
    if n_elite < 1:
        n_elite = 1
    if n_elite > pop_size:
        n_elite = pop_size
    for _ in range(n_elite):
        var best = -1
        for i in range(pop_size):
            if taken[i]:
                continue
            if best < 0 or fitness[i] > fitness[best]:
                best = i
        if best < 0:
            break
        taken[best] = True
        for j in range(n_dim):
            out.append(pop[best * n_dim + j])

    var made = n_elite
    while made < pop_size:
        var ia = _tournament(fitness, tournament, master_seed, generation, made, 0)
        var ib = _tournament(fitness, tournament, master_seed, generation, made, 1)
        for j in range(n_dim):
            var uc = rng_uniform(
                UInt64(master_seed), UInt64(generation), UInt64(made), 1, UInt64(j),
                PROCESS_SEARCH, 0
            )
            var v = pop[ia * n_dim + j]
            if uc < cx_rate:
                v = pop[ib * n_dim + j]
            var um = rng_uniform(
                UInt64(master_seed), UInt64(generation), UInt64(made), 2, UInt64(j),
                PROCESS_SEARCH, 0
            )
            if um < mut_rate:
                var z = rng_normal(
                    UInt64(master_seed), UInt64(generation), UInt64(made), 3, UInt64(j),
                    PROCESS_SEARCH, 0
                )
                v = v + z * mut_scale * (hi[j] - lo[j])
            if v < lo[j]:
                v = lo[j]
            if v > hi[j]:
                v = hi[j]
            out.append(v)
        made += 1
    return out^


fn _tournament(
    fitness: List[Float64], size: Int, master_seed: Int, generation: Int, slot: Int, which: Int
) -> Int:
    """Pick the fittest of `size` keyed-random contenders. Returns an individual index."""
    var pop_size = len(fitness)
    var best = -1
    var k = size
    if k < 1:
        k = 1
    for t in range(k):
        var u = rng_uniform(
            UInt64(master_seed), UInt64(generation), UInt64(slot), UInt64(4 + which),
            UInt64(t), PROCESS_SEARCH, 0
        )
        var i = Int(u * Float64(pop_size))
        if i >= pop_size:
            i = pop_size - 1
        if i < 0:
            i = 0
        if best < 0 or fitness[i] > fitness[best]:
            best = i
    return best


fn ga_best(pop: List[Float64], fitness: List[Float64], n_dim: Int) -> List[Float64]:
    """The fittest individual's genes, with its fitness appended as the final element."""
    var pop_size = len(fitness)
    var out = List[Float64]()
    # pop must carry pop_size*n_dim genes (and n_dim be positive), or the gene reads below
    # abort the worker (uncatchable).
    if n_dim <= 0 or pop_size == 0 or len(pop) < pop_size * n_dim:
        return out^
    var best = 0
    for i in range(pop_size):
        if fitness[i] > fitness[best]:
            best = i
    for j in range(n_dim):
        out.append(pop[best * n_dim + j])
    out.append(fitness[best])
    return out^


fn ga_diversity(pop: List[Float64], n_dim: Int) -> List[Float64]:
    """Per-dimension population standard deviation — the IDENTIFIABILITY diagnostic.

    A dimension whose spread stays near its initial width is one the objective cannot resolve: the
    search is indifferent to it, and reporting a fitted value for it would overstate what the data
    says. The plan requires this be logged per parameter rather than inferred from a single best
    vector.
    """
    var pop_size = len(pop) // n_dim
    var out = List[Float64]()
    if pop_size < 2:
        for _ in range(n_dim):
            out.append(0.0)
        return out^
    for j in range(n_dim):
        var m = 0.0
        for i in range(pop_size):
            m += pop[i * n_dim + j]
        m /= Float64(pop_size)
        var v = 0.0
        for i in range(pop_size):
            var d = pop[i * n_dim + j] - m
            v += d * d
        out.append(sqrt(v / Float64(pop_size - 1)))
    return out^


fn ga_saturation(pop: List[Float64], lo: List[Float64], hi: List[Float64]) -> List[Float64]:
    """Fraction of the population pinned within 1% of each bound: negative at `lo`, positive at `hi`.

    A saturated bound means the search wanted to leave the box, so the fitted value is an artifact of
    the box and not an estimate. Reported because it is the difference between "the data prefers 0.6"
    and "0.6 is as far as we let it go".
    """
    var n_dim = len(lo)
    # n_dim divides pop and hi covers every dimension, or the division/reads below abort
    # the worker (uncatchable).
    if n_dim == 0 or len(hi) < n_dim:
        return List[Float64]()
    var pop_size = len(pop) // n_dim
    var out = List[Float64]()
    for j in range(n_dim):
        var tol = 0.01 * (hi[j] - lo[j])
        var at_lo = 0
        var at_hi = 0
        for i in range(pop_size):
            var v = pop[i * n_dim + j]
            if v <= lo[j] + tol:
                at_lo += 1
            if v >= hi[j] - tol:
                at_hi += 1
        var frac = Float64(at_hi - at_lo) / Float64(pop_size)
        out.append(frac)
    return out^


# ── deterministic zero-argument probes ────────────────────────────────────────


fn search_version() -> String:
    """Contract identifier. Deterministic, zero-argument."""
    return String("evolutionary-search/v1")


fn search_selftest() -> Float64:
    """A one-dimensional search for the peak of -(x-3)^2 on [0,10] must converge near 3.

    Deterministic and zero-argument: the whole point of keyed randomness is that this returns the same
    number on every machine, core count and run.
    """
    var lo = List[Float64]()
    var hi = List[Float64]()
    lo.append(0.0)
    hi.append(10.0)
    var pop = ga_init(lo, hi, 24, 12345)
    for g in range(30):
        var fit = List[Float64]()
        for i in range(24):
            var d = pop[i] - 3.0
            fit.append(-d * d)
        pop = ga_step(pop, fit, lo, hi, 3, 0.5, 0.3, 0.15, 2, 12345, g)
    var fit2 = List[Float64]()
    for i in range(24):
        var d = pop[i] - 3.0
        fit2.append(-d * d)
    var b = ga_best(pop, fit2, 1)
    return b[0]
