"""
random_utils.mojo — Random sampling utilities. Zero Python imports.
Extends std.random for simulation needs (weighted choice, shuffle, bootstrap, etc.).

Public API:
  random_choice       — weighted random choice (returns index)
  random_shuffle      — Fisher-Yates in-place shuffle
  random_sample       — sample n items without replacement
  random_bootstrap    — sample n items with replacement
  random_uniform_int  — uniform integer in [low, high)
  random_permutation  — random permutation of 0..n-1
  stratified_sample   — stratified sampling from sorted data
"""
from std.random import random_float64


# ── Weighted random choice ────────────────────────────────────────────────────


fn random_choice(weights: List[Float64]) -> Int:
    """Return a random index weighted by the given probabilities.
    Weights need not sum to 1; they will be normalized."""
    var n = len(weights)
    if n == 0:
        return -1
    if n == 1:
        return 0

    # Compute total weight
    var total: Float64 = 0.0
    for i in range(n):
        total += weights[i]

    if total <= 0.0:
        return 0

    var u = random_float64() * total
    var cumulative: Float64 = 0.0
    for i in range(n):
        cumulative += weights[i]
        if u <= cumulative:
            return i
    return n - 1


# ── Fisher-Yates shuffle ─────────────────────────────────────────────────────


fn random_shuffle(mut data: List[Float64]):
    """Fisher-Yates in-place shuffle."""
    var n = len(data)
    if n <= 1:
        return
    for i in range(n - 1, 0, -1):
        var j = Int(random_float64() * Float64(i + 1))
        if j > i:
            j = i
        if j != i:
            var tmp = data[i]
            data[i] = data[j]
            data[j] = tmp


# ── Sample without replacement ────────────────────────────────────────────────


fn random_sample(data: List[Float64], n: Int) -> List[Float64]:
    """Sample n items from data without replacement (Fisher-Yates partial shuffle).
    If n >= len(data), returns a shuffled copy of all data."""
    var sz = len(data)
    var k = n
    if k > sz:
        k = sz

    # Copy data
    var pool = List[Float64]()
    for i in range(sz):
        pool.append(data[i])

    # Partial Fisher-Yates
    for i in range(k):
        var j = i + Int(random_float64() * Float64(sz - i))
        if j >= sz:
            j = sz - 1
        if j != i:
            var tmp = pool[i]
            pool[i] = pool[j]
            pool[j] = tmp

    # Take first k
    var result = List[Float64]()
    for i in range(k):
        result.append(pool[i])
    return result^


# ── Sample with replacement (bootstrap) ──────────────────────────────────────


fn random_bootstrap(data: List[Float64], n: Int) -> List[Float64]:
    """Sample n items from data with replacement (bootstrap sampling)."""
    var sz = len(data)
    var result = List[Float64]()
    if sz == 0:
        return result^
    for i in range(n):
        var idx = Int(random_float64() * Float64(sz))
        if idx >= sz:
            idx = sz - 1
        result.append(data[idx])
    return result^


# ── Uniform random integer ───────────────────────────────────────────────────


fn random_uniform_int(low: Int, high: Int) -> Int:
    """Return a random integer in [low, high). Returns low if low >= high."""
    if low >= high:
        return low
    var range_size = high - low
    var idx = Int(random_float64() * Float64(range_size))
    if idx >= range_size:
        idx = range_size - 1
    return low + idx


# ── Random permutation ───────────────────────────────────────────────────────


fn random_permutation(n: Int) -> List[Int]:
    """Return a random permutation of 0, 1, ..., n-1."""
    var perm = List[Int]()
    for i in range(n):
        perm.append(i)
    # Fisher-Yates
    for i in range(n - 1, 0, -1):
        var j = Int(random_float64() * Float64(i + 1))
        if j > i:
            j = i
        if j != i:
            var tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp
    return perm^


# ── Stratified sampling ──────────────────────────────────────────────────────


fn stratified_sample(data: List[Float64], n_strata: Int) -> List[Float64]:
    """Stratified sampling: divide data into n_strata equal strata,
    sample one random element from each stratum.
    Data should ideally be sorted for meaningful stratification."""
    var n = len(data)
    var result = List[Float64]()
    if n == 0 or n_strata <= 0:
        return result^

    var strata_count = n_strata
    if strata_count > n:
        strata_count = n

    var stratum_size = n // strata_count
    var remainder = n - stratum_size * strata_count

    var offset = 0
    for s in range(strata_count):
        # Distribute remainder across first strata
        var this_size = stratum_size
        if s < remainder:
            this_size += 1
        if this_size <= 0:
            continue
        var idx = offset + Int(random_float64() * Float64(this_size))
        if idx >= offset + this_size:
            idx = offset + this_size - 1
        result.append(data[idx])
        offset += this_size

    return result^
