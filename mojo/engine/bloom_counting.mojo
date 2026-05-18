"""
bloom_counting.mojo — Counting Bloom Filter. Zero Python imports.

Extends probabilistic structures with a counting variant that supports
deletion. Each bucket stores a counter instead of a single bit, allowing
both insert and remove operations.

Public API:
  struct CountingBloom
  cb_create           — Create counting Bloom filter
  cb_add              — Add item (increment counters)
  cb_remove           — Remove item (decrement counters, min 0)
  cb_contains         — Check membership (all counters > 0)
  cb_count_estimate   — Estimated count (min of counters)
  cb_hash             — Hash function
  cb_false_positive_rate — Theoretical FP rate
  cb_optimal_hashes   — Optimal number of hash functions
  cb_reset            — Reset all counters to 0
"""
from std.math import exp, log, abs as fabs


# ── CountingBloom struct ──────────────────────────────────────────────────────


struct CountingBloom(Copyable, Movable):
    """Counting Bloom filter with per-bucket counters."""

    var counters: List[Int]
    var size: Int
    var n_hashes: Int
    var hash_seeds: List[Int]

    fn __init__(out self, size: Int, n_hashes: Int, seeds: List[Int]):
        self.size = size
        self.n_hashes = n_hashes
        self.hash_seeds = seeds.copy()
        self.counters = List[Int]()
        for _ in range(size):
            self.counters.append(0)


# ── cb_create ─────────────────────────────────────────────────────────────────


fn cb_create(size: Int, n_hashes: Int) -> CountingBloom:
    """Create a counting Bloom filter with given size and number of hashes.

    Args:
        size: Number of counter buckets.
        n_hashes: Number of hash functions to use.

    Returns:
        A new CountingBloom instance with all counters at 0.
    """
    var seeds = List[Int]()
    for i in range(n_hashes):
        # Golden ratio based seeds for good distribution
        seeds.append(i * 2654435761 + 131)
    return CountingBloom(size, n_hashes, seeds^)


# ── cb_hash ───────────────────────────────────────────────────────────────────


fn cb_hash(item: Int, seed: Int, size: Int) -> Int:
    """Hash function mapping item+seed to a bucket index.

    Uses FNV-1a-inspired mixing for good distribution.

    Args:
        item: The integer item to hash.
        seed: The hash seed.
        size: Number of buckets (modulus).

    Returns:
        Bucket index in [0, size).
    """
    var h = seed ^ item
    h = h * 1099511628211
    h = h ^ (h >> 16)
    h = h * 2246822507
    h = h ^ (h >> 13)
    # Ensure positive
    if h < 0:
        h = -h
    return h % size


# ── cb_add ────────────────────────────────────────────────────────────────────


fn cb_add(mut bloom: CountingBloom, item: Int):
    """Add an item to the counting Bloom filter.

    Increments the counter at each hash position.

    Args:
        bloom: The counting Bloom filter (mutated).
        item: The integer item to add.
    """
    for i in range(bloom.n_hashes):
        var idx = cb_hash(item, bloom.hash_seeds[i], bloom.size)
        bloom.counters[idx] += 1


# ── cb_remove ─────────────────────────────────────────────────────────────────


fn cb_remove(mut bloom: CountingBloom, item: Int):
    """Remove an item from the counting Bloom filter.

    Decrements the counter at each hash position, with a minimum of 0.

    Args:
        bloom: The counting Bloom filter (mutated).
        item: The integer item to remove.
    """
    for i in range(bloom.n_hashes):
        var idx = cb_hash(item, bloom.hash_seeds[i], bloom.size)
        if bloom.counters[idx] > 0:
            bloom.counters[idx] -= 1


# ── cb_contains ───────────────────────────────────────────────────────────────


fn cb_contains(bloom: CountingBloom, item: Int) -> Bool:
    """Check if an item is possibly in the filter.

    Returns True only if all counters at the item's hash positions are > 0.

    Args:
        bloom: The counting Bloom filter.
        item: The integer item to check.

    Returns:
        True if possibly present, False if definitely absent.
    """
    for i in range(bloom.n_hashes):
        var idx = cb_hash(item, bloom.hash_seeds[i], bloom.size)
        if bloom.counters[idx] == 0:
            return False
    return True


# ── cb_count_estimate ─────────────────────────────────────────────────────────


fn cb_count_estimate(bloom: CountingBloom, item: Int) -> Int:
    """Estimated count of an item (minimum of counters at hash positions).

    Args:
        bloom: The counting Bloom filter.
        item: The integer item to estimate count for.

    Returns:
        Minimum counter value across all hash positions for this item.
    """
    var min_val = bloom.counters[cb_hash(item, bloom.hash_seeds[0], bloom.size)]
    for i in range(1, bloom.n_hashes):
        var idx = cb_hash(item, bloom.hash_seeds[i], bloom.size)
        if bloom.counters[idx] < min_val:
            min_val = bloom.counters[idx]
    return min_val


# ── cb_false_positive_rate ────────────────────────────────────────────────────


fn cb_false_positive_rate(size: Int, n_hashes: Int, n_items: Int) -> Float64:
    """Theoretical false positive rate: (1 - e^(-kn/m))^k.

    Args:
        size: Number of counter buckets (m).
        n_hashes: Number of hash functions (k).
        n_items: Number of items inserted (n).

    Returns:
        Theoretical false positive probability.
    """
    var m = Float64(size)
    var k = Float64(n_hashes)
    var n = Float64(n_items)
    if m <= 0.0 or k <= 0.0:
        return 1.0
    var inner = 1.0 - exp(-k * n / m)
    var result: Float64 = 1.0
    for _ in range(n_hashes):
        result *= inner
    return result


# ── cb_optimal_hashes ─────────────────────────────────────────────────────────


fn cb_optimal_hashes(size: Int, n_items: Int) -> Int:
    """Optimal number of hash functions: k = (m/n) * ln(2).

    Args:
        size: Number of counter buckets (m).
        n_items: Expected number of items (n).

    Returns:
        Optimal k (at least 1).
    """
    if n_items <= 0:
        return 1
    var k = (Float64(size) / Float64(n_items)) * 0.6931471805599453
    var ki = Int(k)
    if ki < 1:
        ki = 1
    return ki


# ── cb_reset ──────────────────────────────────────────────────────────────────


fn cb_reset(mut bloom: CountingBloom):
    """Reset all counters to 0.

    Args:
        bloom: The counting Bloom filter (mutated).
    """
    for i in range(bloom.size):
        bloom.counters[i] = 0
