"""
interval.mojo — Interval arithmetic. Zero Python imports.

Replaces portion/pyinterval with pure Mojo implementations of closed
interval creation, arithmetic operations (+, -, *, /), containment,
overlap detection, intersection, union hull, and metric queries.

Public API:
  Interval               — Struct with lo, hi, empty fields
  interval               — Create [lo, hi] interval
  empty_interval         — Create empty interval
  interval_add           — [a.lo+b.lo, a.hi+b.hi]
  interval_sub           — [a.lo-b.hi, a.hi-b.lo]
  interval_mul           — min/max of endpoint products
  interval_div           — a * [1/b.hi, 1/b.lo]
  interval_contains      — Check x ∈ [lo, hi]
  interval_overlaps      — Check if intervals overlap
  interval_intersection  — Intersection of two intervals
  interval_union_hull    — Smallest interval containing both
  interval_width         — hi - lo
  interval_midpoint      — (lo + hi) / 2
  interval_radius        — (hi - lo) / 2
"""


# ── Interval Struct ──────────────────────────────────────────────────────────


struct Interval(Copyable, Movable):
    """Closed interval [lo, hi] or empty."""

    var lo: Float64
    var hi: Float64
    var empty: Bool

    fn __init__(out self, lo: Float64, hi: Float64, empty: Bool):
        self.lo = lo
        self.hi = hi
        self.empty = empty


# ── interval ─────────────────────────────────────────────────────────────────


fn interval(lo: Float64, hi: Float64) -> Interval:
    """Create interval [lo, hi]. If lo > hi, returns empty interval.

    Args:
        lo: Lower bound.
        hi: Upper bound.

    Returns:
        Interval [lo, hi], or empty if lo > hi.
    """
    if lo > hi:
        return Interval(0.0, 0.0, True)
    return Interval(lo, hi, False)


# ── empty_interval ───────────────────────────────────────────────────────────


fn empty_interval() -> Interval:
    """Create an empty interval.

    Returns:
        An Interval with empty=True.
    """
    return Interval(0.0, 0.0, True)


# ── interval_add ─────────────────────────────────────────────────────────────


fn interval_add(a: Interval, b: Interval) -> Interval:
    """Add two intervals: [a.lo+b.lo, a.hi+b.hi].

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        Sum interval, or empty if either input is empty.
    """
    if a.empty or b.empty:
        return empty_interval()
    return Interval(a.lo + b.lo, a.hi + b.hi, False)


# ── interval_sub ─────────────────────────────────────────────────────────────


fn interval_sub(a: Interval, b: Interval) -> Interval:
    """Subtract intervals: [a.lo-b.hi, a.hi-b.lo].

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        Difference interval, or empty if either input is empty.
    """
    if a.empty or b.empty:
        return empty_interval()
    return Interval(a.lo - b.hi, a.hi - b.lo, False)


# ── interval_mul ─────────────────────────────────────────────────────────────


fn _min4(a: Float64, b: Float64, c: Float64, d: Float64) -> Float64:
    """Return minimum of four Float64 values."""
    var m = a
    if b < m:
        m = b
    if c < m:
        m = c
    if d < m:
        m = d
    return m


fn _max4(a: Float64, b: Float64, c: Float64, d: Float64) -> Float64:
    """Return maximum of four Float64 values."""
    var m = a
    if b > m:
        m = b
    if c > m:
        m = c
    if d > m:
        m = d
    return m


fn interval_mul(a: Interval, b: Interval) -> Interval:
    """Multiply intervals: [min(products), max(products)] of all endpoints.

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        Product interval, or empty if either input is empty.
    """
    if a.empty or b.empty:
        return empty_interval()
    var p1 = a.lo * b.lo
    var p2 = a.lo * b.hi
    var p3 = a.hi * b.lo
    var p4 = a.hi * b.hi
    return Interval(_min4(p1, p2, p3, p4), _max4(p1, p2, p3, p4), False)


# ── interval_div ─────────────────────────────────────────────────────────────


fn interval_div(a: Interval, b: Interval) raises -> Interval:
    """Divide intervals: a * [1/b.hi, 1/b.lo].

    Raises if b contains 0.

    Args:
        a: Numerator interval.
        b: Denominator interval.

    Returns:
        Quotient interval.

    Raises:
        Error if b contains zero.
    """
    if a.empty or b.empty:
        return empty_interval()
    if b.lo <= 0.0 and b.hi >= 0.0:
        raise Error("interval_div: divisor interval contains zero")
    var inv = Interval(1.0 / b.hi, 1.0 / b.lo, False)
    return interval_mul(a, inv)


# ── interval_contains ────────────────────────────────────────────────────────


fn interval_contains(iv: Interval, x: Float64) -> Bool:
    """Check if x ∈ [lo, hi].

    Args:
        iv: The interval.
        x:  The value to test.

    Returns:
        True if iv is non-empty and lo <= x <= hi.
    """
    if iv.empty:
        return False
    return x >= iv.lo and x <= iv.hi


# ── interval_overlaps ────────────────────────────────────────────────────────


fn interval_overlaps(a: Interval, b: Interval) -> Bool:
    """Check if two intervals overlap.

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        True if the intervals share at least one point.
    """
    if a.empty or b.empty:
        return False
    return a.lo <= b.hi and b.lo <= a.hi


# ── interval_intersection ────────────────────────────────────────────────────


fn interval_intersection(a: Interval, b: Interval) -> Interval:
    """Intersection of two intervals (may be empty).

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        The intersection, or empty if they don't overlap.
    """
    if a.empty or b.empty:
        return empty_interval()
    var lo = a.lo
    if b.lo > lo:
        lo = b.lo
    var hi = a.hi
    if b.hi < hi:
        hi = b.hi
    if lo > hi:
        return empty_interval()
    return Interval(lo, hi, False)


# ── interval_union_hull ──────────────────────────────────────────────────────


fn interval_union_hull(a: Interval, b: Interval) -> Interval:
    """Smallest interval containing both (convex hull).

    Args:
        a: First interval.
        b: Second interval.

    Returns:
        Hull interval [min(lo), max(hi)], or the non-empty one if one is empty.
    """
    if a.empty and b.empty:
        return empty_interval()
    if a.empty:
        return Interval(b.lo, b.hi, b.empty)
    if b.empty:
        return Interval(a.lo, a.hi, a.empty)
    var lo = a.lo
    if b.lo < lo:
        lo = b.lo
    var hi = a.hi
    if b.hi > hi:
        hi = b.hi
    return Interval(lo, hi, False)


# ── interval_width ───────────────────────────────────────────────────────────


fn interval_width(iv: Interval) -> Float64:
    """Width of interval: hi - lo (0 for empty).

    Args:
        iv: The interval.

    Returns:
        Width as Float64.
    """
    if iv.empty:
        return 0.0
    return iv.hi - iv.lo


# ── interval_midpoint ────────────────────────────────────────────────────────


fn interval_midpoint(iv: Interval) -> Float64:
    """Midpoint of interval: (lo + hi) / 2.

    Args:
        iv: The interval.

    Returns:
        Midpoint as Float64 (0 for empty).
    """
    if iv.empty:
        return 0.0
    return (iv.lo + iv.hi) / 2.0


# ── interval_radius ──────────────────────────────────────────────────────────


fn interval_radius(iv: Interval) -> Float64:
    """Radius of interval: (hi - lo) / 2.

    Args:
        iv: The interval.

    Returns:
        Radius as Float64 (0 for empty).
    """
    if iv.empty:
        return 0.0
    return (iv.hi - iv.lo) / 2.0
