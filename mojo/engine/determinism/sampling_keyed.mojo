"""
determinism.sampling_keyed — reproducible sampling. Zero Python.

`random_utils` takes no seed at all: `random_choice`, `random_shuffle`,
`random_sample` and friends draw from process-global state, so the same call twice
gives different answers and a run cannot be replayed. Thirty-two modules under
`mojo/engine` use unseeded randomness that way.

Those modules are frozen and unchanged. This is a parallel set of keyed entry
points, so new surfaces can sample reproducibly without touching them.

Why new functions rather than a seed parameter
----------------------------------------------
Adding a defaulted `seed` to `random_choice` would change its arity, and arity is
load-bearing here: the dispatch generator emits an exact-count check, the inventory
records `has_default`, and both feed the shipped contract, the generated tests and
the docs catalog. One added parameter therefore ripples through five artifacts and
the pinned function count. Additive functions cost nothing by comparison.

Addressed, not sequential
-------------------------
Each draw names its coordinates rather than advancing a stream, so
`choice_keyed(weights, seed, stream, 7)` is the same value whatever happened before
it. That is what makes a shuffle reproducible in isolation and makes common random
numbers valid across alternatives that consume different numbers of draws.
"""
from determinism.counter_rng import rng_uniform


fn choice_keyed(
    weights: List[Float64],
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> Int:
    """Index sampled proportional to `weights`. Reproducible for fixed coordinates.

    Returns -1 for an empty list or non-positive total, rather than 0: index 0 would
    be indistinguishable from a legitimate draw of the first element.
    """
    var total: Float64 = 0.0
    for i in range(len(weights)):
        if weights[i] > 0.0:
            total += weights[i]
    if len(weights) == 0 or total <= 0.0:
        return -1

    var target = rng_uniform(master_seed, 0, 0, 0, 0, stream, draw_index) * total
    var cumulative: Float64 = 0.0
    for i in range(len(weights)):
        if weights[i] <= 0.0:
            continue
        cumulative += weights[i]
        if target < cumulative:
            return i
    # Only reachable through floating-point accumulation at the very top of the
    # range; the last positive weight is the correct answer there.
    for i in range(len(weights) - 1, -1, -1):
        if weights[i] > 0.0:
            return i
    return -1


fn permutation_keyed(
    n: Int,
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> List[Int]:
    """A permutation of 0..n-1 via Fisher-Yates over keyed draws.

    Draw i consumes coordinate `draw_index + i`, so the whole permutation is a pure
    function of its coordinates and reproduces exactly.
    """
    var out = List[Int]()
    for i in range(n):
        out.append(i)
    if n <= 1:
        return out^
    # Downward Fisher-Yates: each position picks from the unshuffled prefix.
    for i in range(n - 1, 0, -1):
        var u = rng_uniform(master_seed, 0, 0, 0, 0, stream, draw_index + UInt64(n - 1 - i))
        var j = Int(u * Float64(i + 1))
        if j > i:
            j = i
        var swap = out[i]
        out[i] = out[j]
        out[j] = swap
    return out^


fn shuffle_keyed(
    values: List[Float64],
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> List[Float64]:
    """`values` reordered by a keyed permutation. Returns a copy; input untouched."""
    var order = permutation_keyed(len(values), master_seed, stream, draw_index)
    var out = List[Float64]()
    for i in range(len(order)):
        out.append(values[order[i]])
    return out^


fn sample_without_replacement_keyed(
    values: List[Float64],
    k: Int,
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> List[Float64]:
    """First `k` of a keyed permutation — sampling without replacement.

    `k` above the population returns the whole population rather than padding or
    erroring: the request "give me k distinct items" is satisfied by all of them.
    """
    var order = permutation_keyed(len(values), master_seed, stream, draw_index)
    var take = k if k < len(order) else len(order)
    var out = List[Float64]()
    for i in range(take):
        out.append(values[order[i]])
    return out^


fn bootstrap_keyed(
    values: List[Float64],
    n_draws: Int,
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> List[Float64]:
    """Resample WITH replacement — the bootstrap.

    Distinct from `sample_without_replacement_keyed`: a bootstrap replicate must be
    able to repeat an observation, which is the entire mechanism behind its variance
    estimate.
    """
    var out = List[Float64]()
    if len(values) == 0:
        return out^
    for i in range(n_draws):
        var u = rng_uniform(master_seed, 0, 0, 0, 0, stream, draw_index + UInt64(i))
        var index = Int(u * Float64(len(values)))
        if index >= len(values):
            index = len(values) - 1
        out.append(values[index])
    return out^


fn uniform_int_keyed(
    low: Int,
    high: Int,
    master_seed: UInt64,
    stream: UInt64,
    draw_index: UInt64,
) -> Int:
    """Uniform integer in [low, high]. Inclusive at both ends."""
    if high <= low:
        return low
    var span = high - low + 1
    var u = rng_uniform(master_seed, 0, 0, 0, 0, stream, draw_index)
    var offset = Int(u * Float64(span))
    if offset >= span:
        offset = span - 1
    return low + offset
