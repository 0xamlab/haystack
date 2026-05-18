"""
metrics_agg.mojo — Metrics aggregation primitives. Zero Python imports.

Replaces prometheus_client basics with pure Mojo implementations of
counters, histograms, percentiles, rate, throughput, and latency stats.

Public API:
  struct MetricsCounter   — named counter with value
  counter_create          — create counter at 0
  counter_inc             — increment counter
  counter_value           — get current value
  struct Histogram        — named histogram with buckets
  histogram_create        — create with bucket boundaries
  histogram_observe       — record observation
  histogram_bucket_counts — count per bucket
  histogram_mean          — mean of observations
  histogram_percentile    — exact percentile from stored values
  rate                    — rate of change
  gauge_set               — set gauge, return new value
  compute_throughput      — count / duration
  latency_stats           — [min, max, mean, p50, p95, p99]
"""


# ── MetricsCounter ───────────────────────────────────────────────────────────


struct MetricsCounter(Copyable, Movable):
    """A named counter that can only increase."""

    var name: String
    var value: Float64

    fn __init__(out self, name: String, value: Float64):
        self.name = name
        self.value = value


fn counter_create(name: String) -> MetricsCounter:
    """Create a counter starting at 0."""
    return MetricsCounter(name, 0.0)


fn counter_inc(mut c: MetricsCounter, amount: Float64 = 1.0):
    """Increment counter by amount (default 1.0)."""
    c.value += amount


fn counter_value(c: MetricsCounter) -> Float64:
    """Get current counter value."""
    return c.value


# ── Histogram ────────────────────────────────────────────────────────────────


struct Histogram(Copyable, Movable):
    """A named histogram with bucket boundaries and stored observations."""

    var name: String
    var values: List[Float64]
    var bucket_boundaries: List[Float64]

    fn __init__(out self, name: String, values: List[Float64], bucket_boundaries: List[Float64]):
        self.name = name
        self.values = values.copy()
        self.bucket_boundaries = bucket_boundaries.copy()


fn histogram_create(name: String, boundaries: List[Float64]) -> Histogram:
    """Create a histogram with the given bucket boundaries."""
    return Histogram(name, List[Float64](), boundaries)


fn histogram_observe(mut h: Histogram, value: Float64):
    """Record an observation."""
    h.values.append(value)


fn histogram_bucket_counts(h: Histogram) -> List[Int]:
    """Count observations in each bucket (plus +Inf bucket).

    Returns a list of length len(boundaries) + 1.
    Bucket i counts values <= boundaries[i] (and > boundaries[i-1]).
    Last bucket counts values > last boundary (+Inf).
    """
    var nb = len(h.bucket_boundaries)
    var counts = List[Int]()
    for _ in range(nb + 1):
        counts.append(0)
    var nv = len(h.values)
    for i in range(nv):
        var v = h.values[i]
        var placed = False
        for b in range(nb):
            if v <= h.bucket_boundaries[b]:
                counts[b] += 1
                placed = True
                break
        if not placed:
            counts[nb] += 1
    return counts^


fn histogram_mean(h: Histogram) -> Float64:
    """Mean of all observations."""
    var n = len(h.values)
    if n == 0:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        total += h.values[i]
    return total / Float64(n)


fn _sort_floats(mut arr: List[Float64]):
    """Insertion sort for float list."""
    var n = len(arr)
    for i in range(1, n):
        var key = arr[i]
        var j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key


fn histogram_percentile(h: Histogram, p: Float64) -> Float64:
    """Exact percentile from stored values. p in [0, 100]."""
    var n = len(h.values)
    if n == 0:
        return 0.0
    var sorted_vals = List[Float64]()
    for i in range(n):
        sorted_vals.append(h.values[i])
    _sort_floats(sorted_vals)
    var rank = p / 100.0 * Float64(n)
    var idx = Int(rank)
    if idx < 1:
        idx = 1
    if idx > n:
        idx = n
    return sorted_vals[idx - 1]


# ── rate ─────────────────────────────────────────────────────────────────────


fn rate(values: List[Float64], interval: Float64) -> Float64:
    """Rate of change: (last - first) / ((n-1) * interval)."""
    var n = len(values)
    if n < 2 or interval == 0.0:
        return 0.0
    return (values[n - 1] - values[0]) / (Float64(n - 1) * interval)


# ── gauge_set ────────────────────────────────────────────────────────────────


fn gauge_set(mut value: Float64, new_value: Float64) -> Float64:
    """Set gauge and return new value."""
    value = new_value
    return value


# ── compute_throughput ───────────────────────────────────────────────────────


fn compute_throughput(count: Int, duration_seconds: Float64) -> Float64:
    """Throughput = count / duration."""
    if duration_seconds == 0.0:
        return 0.0
    return Float64(count) / duration_seconds


# ── _percentile_from_sorted ──────────────────────────────────────────────────


fn _percentile_from_sorted(sorted_v: List[Float64], nn: Int, pval: Float64) -> Float64:
    """Nearest-rank percentile from a pre-sorted list."""
    var rank = pval / 100.0 * Float64(nn)
    var idx = Int(rank)
    if idx < 1:
        idx = 1
    if idx > nn:
        idx = nn
    return sorted_v[idx - 1]


# ── latency_stats ────────────────────────────────────────────────────────────


fn latency_stats(latencies: List[Float64]) -> List[Float64]:
    """Returns [min, max, mean, p50, p95, p99] from latency data."""
    var result = List[Float64]()
    var n = len(latencies)
    if n == 0:
        for _ in range(6):
            result.append(0.0)
        return result^

    var sorted_vals = List[Float64]()
    for i in range(n):
        sorted_vals.append(latencies[i])
    _sort_floats(sorted_vals)

    var min_val = sorted_vals[0]
    var max_val = sorted_vals[n - 1]
    var total: Float64 = 0.0
    for i in range(n):
        total += sorted_vals[i]
    var mean_val = total / Float64(n)

    var p50 = _percentile_from_sorted(sorted_vals, n, 50.0)
    var p95 = _percentile_from_sorted(sorted_vals, n, 95.0)
    var p99 = _percentile_from_sorted(sorted_vals, n, 99.0)

    result.append(min_val)
    result.append(max_val)
    result.append(mean_val)
    result.append(p50)
    result.append(p95)
    result.append(p99)
    return result^
