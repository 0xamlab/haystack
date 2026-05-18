"""
reservoir.mojo — Reservoir & streaming sampling. Zero Python imports.

Replaces custom reservoir/streaming sampling libraries with pure Mojo
implementations of Vitter's Algorithm R, Efraimidis-Spirakis weighted
sampling, bootstrap, systematic, and Fisher-Yates partial shuffle.

Public API:
  reservoir_sample          — Vitter's Algorithm R (uniform k from stream)
  weighted_reservoir_sample — Efraimidis-Spirakis (weighted reservoir)
  reservoir_sample_indices  — k random indices from [0, n) w/o replacement
  bootstrap_sample          — Bootstrap: n items with replacement
  systematic_sample         — Systematic sampling every n/k-th element
  sample_with_replacement   — Draw k items with replacement
  sample_without_replacement — Draw k items without replacement (Fisher-Yates)
"""
from std.math import log, floor
from std.random import random_float64


# ── reservoir_sample ─────────────────────────────────────────────────────────


fn reservoir_sample(stream: List[Float64], k: Int) -> List[Float64]:
    """Select k items uniformly at random from a stream (Vitter's Algorithm R).

    Args:
        stream: Input data stream.
        k:      Number of items to sample.

    Returns:
        List of k sampled Float64 values.
    """
    var n = len(stream)
    if k >= n:
        var copy = List[Float64]()
        for i in range(n):
            copy.append(stream[i])
        return copy^
    var reservoir = List[Float64]()
    for i in range(k):
        reservoir.append(stream[i])
    for i in range(k, n):
        var j = Int(random_float64() * Float64(i + 1))
        if j < 0:
            j = 0
        if j >= i + 1:
            j = i
        if j < k:
            reservoir[j] = stream[i]
    return reservoir^


# ── weighted_reservoir_sample ────────────────────────────────────────────────


fn weighted_reservoir_sample(
    stream: List[Float64], weights: List[Float64], k: Int
) -> List[Float64]:
    """Efraimidis-Spirakis weighted reservoir sampling.

    Uses key = random^(1/weight) for each item. Keeps the k items with
    the largest keys.

    Args:
        stream:  Input data values.
        weights: Corresponding positive weights.
        k:       Number of items to sample.

    Returns:
        List of k sampled Float64 values.
    """
    var n = len(stream)
    if k >= n:
        var copy = List[Float64]()
        for i in range(n):
            copy.append(stream[i])
        return copy^

    # Compute keys and initialize reservoir
    var reservoir = List[Float64]()
    var keys = List[Float64]()
    for i in range(k):
        var u = random_float64()
        if u < 1e-15:
            u = 1e-15
        var w = weights[i]
        if w < 1e-15:
            w = 1e-15
        var key = log(u) / w  # log(u^(1/w)) = log(u)/w — monotone transform
        reservoir.append(stream[i])
        keys.append(key)

    # Find current minimum key in reservoir
    var min_key = keys[0]
    var min_idx = 0
    for i in range(1, k):
        if keys[i] < min_key:
            min_key = keys[i]
            min_idx = i

    # Process remaining items
    for i in range(k, n):
        var u = random_float64()
        if u < 1e-15:
            u = 1e-15
        var w = weights[i]
        if w < 1e-15:
            w = 1e-15
        var key = log(u) / w
        if key > min_key:
            reservoir[min_idx] = stream[i]
            keys[min_idx] = key
            # Recompute minimum
            min_key = keys[0]
            min_idx = 0
            for j in range(1, k):
                if keys[j] < min_key:
                    min_key = keys[j]
                    min_idx = j

    return reservoir^


# ── reservoir_sample_indices ─────────────────────────────────────────────────


fn reservoir_sample_indices(n: Int, k: Int) -> List[Int]:
    """Return k random indices from [0, n) without replacement.

    Uses Fisher-Yates partial shuffle on a virtual array.

    Args:
        n: Upper bound (exclusive) of index range.
        k: Number of indices to sample.

    Returns:
        List of k unique Int indices in [0, n).
    """
    var actual_k = k
    if actual_k > n:
        actual_k = n
    # Build full index array
    var indices = List[Int]()
    for i in range(n):
        indices.append(i)
    # Fisher-Yates partial shuffle
    for i in range(actual_k):
        var remaining = n - i
        var j_offset = Int(random_float64() * Float64(remaining))
        if j_offset >= remaining:
            j_offset = remaining - 1
        if j_offset < 0:
            j_offset = 0
        var j = i + j_offset
        # Swap
        var tmp = indices[i]
        indices[i] = indices[j]
        indices[j] = tmp
    # Return first k
    var result = List[Int]()
    for i in range(actual_k):
        result.append(indices[i])
    return result^


# ── bootstrap_sample ─────────────────────────────────────────────────────────


fn bootstrap_sample(data: List[Float64]) -> List[Float64]:
    """Bootstrap: sample n items with replacement from data of size n.

    Args:
        data: Input data.

    Returns:
        List of len(data) sampled values (with replacement).
    """
    var n = len(data)
    var result = List[Float64]()
    for _ in range(n):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result^


# ── systematic_sample ────────────────────────────────────────────────────────


fn systematic_sample(data: List[Float64], k: Int) -> List[Float64]:
    """Systematic sampling: every n/k-th element with random start.

    Args:
        data: Input data.
        k:    Number of items to select.

    Returns:
        List of k sampled values.
    """
    var n = len(data)
    if k >= n:
        var copy = List[Float64]()
        for i in range(n):
            copy.append(data[i])
        return copy^
    var step = Float64(n) / Float64(k)
    var start = random_float64() * step
    var result = List[Float64]()
    for i in range(k):
        var idx = Int(start + Float64(i) * step)
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result^


# ── sample_with_replacement ──────────────────────────────────────────────────


fn sample_with_replacement(data: List[Float64], k: Int) -> List[Float64]:
    """Draw k items with replacement from data.

    Args:
        data: Input data.
        k:    Number of items to draw.

    Returns:
        List of k sampled values.
    """
    var n = len(data)
    var result = List[Float64]()
    for _ in range(k):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result^


# ── sample_without_replacement ───────────────────────────────────────────────


fn sample_without_replacement(data: List[Float64], k: Int) -> List[Float64]:
    """Draw k items without replacement (Fisher-Yates partial shuffle).

    Args:
        data: Input data.
        k:    Number of items to draw (must be <= len(data)).

    Returns:
        List of k unique sampled values.
    """
    var n = len(data)
    var actual_k = k
    if actual_k > n:
        actual_k = n
    # Copy data to shuffle
    var arr = List[Float64]()
    for i in range(n):
        arr.append(data[i])
    # Fisher-Yates partial shuffle
    for i in range(actual_k):
        var remaining = n - i
        var j_offset = Int(random_float64() * Float64(remaining))
        if j_offset >= remaining:
            j_offset = remaining - 1
        if j_offset < 0:
            j_offset = 0
        var j = i + j_offset
        var tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp
    var result = List[Float64]()
    for i in range(actual_k):
        result.append(arr[i])
    return result^
