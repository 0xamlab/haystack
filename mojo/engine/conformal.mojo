"""
conformal.mojo — Split conformal prediction intervals. Zero Python imports.

Replaces mapie / nonconformist (split-conformal regression): calibration
quantile via the ceil((1-alpha)(n+1)) rank rule, symmetric interval
construction, empirical coverage, and the locally-weighted (normalized)
variant with a per-sample scale.

Conventions (money-path conservative):
  - Nonconformity score is |residual| (signed residuals accepted).
  - When the rank exceeds n (alpha too small for the calibration size,
    n = 0, or non-finite alpha) the quantile is 1e308 — an effectively
    infinite half-width, i.e. "no finite guarantee possible".
  - NaN or infinite residuals and nonpositive / non-finite scales score as
    1e308 (maximally nonconforming rather than silently dropped), so q
    itself is always finite.

Public API:
  ConformalInterval             — one interval: lo, hi
  ConformalBand                 — per-sample interval lists: lo, hi
  conformal_quantile            — score quantile q via ceil((1-alpha)(n+1)) rule
  conformal_quantile_normalized — same rule on |residual| / scale
  conformal_interval            — pred ± q
  conformal_interval_normalized — pred ± q * scale
  conformal_band                — pred_i ± q for a list of predictions
  conformal_coverage            — fraction of y inside [lo, hi] (inclusive)
"""

from std.math import abs as fabs, isnan, isinf


# Effectively-infinite half-width sentinel (repo convention: finite 1e308
# instead of IEEE inf so downstream pred ± q arithmetic stays well-behaved).
alias _INF: Float64 = 1e308


# ── result structs ───────────────────────────────────────────────────────────


struct ConformalInterval(Copyable, Movable):
    """One conformal prediction interval [lo, hi]."""
    var lo: Float64
    var hi: Float64

    fn __init__(out self, lo: Float64, hi: Float64):
        self.lo = lo
        self.hi = hi


struct ConformalBand(Copyable, Movable):
    """Per-sample interval bounds: lo[i], hi[i] for each prediction i."""
    var lo: List[Float64]
    var hi: List[Float64]

    fn __init__(out self):
        self.lo = List[Float64]()
        self.hi = List[Float64]()


# ── sorting helpers (heapsort: O(n log n) worst case, no recursion) ──────────


fn _sift_down(mut a: List[Float64], start: Int, end: Int):
    """Restore the max-heap property for the subtree rooted at start (heap
    occupies a[0:end])."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child >= end:
            return
        if child + 1 < end and a[child + 1] > a[child]:
            child += 1
        if a[root] >= a[child]:
            return
        var tmp = a[root]
        a[root] = a[child]
        a[child] = tmp
        root = child


fn _sort_floats(mut a: List[Float64]):
    """In-place ascending heapsort. Deterministic; sub-ms for n <= 10k."""
    var n = len(a)
    if n < 2:
        return
    var i = n // 2 - 1
    while i >= 0:
        _sift_down(a, i, n)
        i -= 1
    var end = n - 1
    while end > 0:
        var tmp = a[0]
        a[0] = a[end]
        a[end] = tmp
        _sift_down(a, 0, end)
        end -= 1


# ── rank rule ────────────────────────────────────────────────────────────────


fn _conformal_rank(n: Int, alpha: Float64) -> Int:
    """1-based rank k = ceil((1 - alpha) * (n + 1)), clamped to k >= 1.

    Equivalent to the (1-alpha)(1+1/n) empirical quantile of n calibration
    scores. Returns n + 1 (caller maps to the infinite sentinel) when alpha
    is NaN or infinite, or so small that no finite calibration quantile
    achieves the requested coverage. A -1e-9 nudge before the ceil absorbs
    float fuzz so exact-integer products (e.g. 0.9 * 10) never round up a
    rank. The t > n early-out also keeps t within Int range: Int(t) on a
    huge float is undefined (fptosi poison), which could otherwise collapse
    the rank to 1 for absurdly negative alpha.
    """
    if isnan(alpha) or isinf(alpha):
        return n + 1
    var t = (1.0 - alpha) * Float64(n + 1) - 1e-9
    if t <= 0.0:
        return 1
    if t > Float64(n):
        return n + 1
    var k = Int(t)
    if Float64(k) < t:
        k += 1
    if k < 1:
        k = 1
    return k


fn _quantile_of_scores(var scores: List[Float64], alpha: Float64) -> Float64:
    """Sort scores ascending and take the ceil((1-alpha)(n+1))-th smallest."""
    var n = len(scores)
    if n <= 0:
        return _INF
    var k = _conformal_rank(n, alpha)
    if k > n:
        return _INF
    _sort_floats(scores)
    return scores[k - 1]


# ── conformal_quantile ───────────────────────────────────────────────────────


fn conformal_quantile(
    residuals_calibration: List[Float64], alpha: Float64
) -> Float64:
    """Split-conformal quantile q from calibration residuals.

    Scores are |residual|; q is the k-th smallest score with
    k = ceil((1-alpha)(n+1)) — the standard split-conformal rule giving
    P(y in pred ± q) >= 1 - alpha under exchangeability. Returns 1e308
    (effectively infinite) when the calibration set is empty or k > n
    (alpha < 1/(n+1)). NaN or infinite residuals score as 1e308
    (conservative, and q stays finite per the module convention).
    """
    var n = len(residuals_calibration)
    if n <= 0:
        return _INF
    var scores = List[Float64](capacity=n)
    for i in range(n):
        var s = fabs(residuals_calibration[i])
        if isnan(s) or isinf(s):
            s = _INF
        scores.append(s)
    return _quantile_of_scores(scores^, alpha)


# ── conformal_quantile_normalized ────────────────────────────────────────────


fn conformal_quantile_normalized(
    residuals_calibration: List[Float64],
    scales: List[Float64],
    alpha: Float64,
) -> Float64:
    """Normalized (locally-weighted) split-conformal quantile.

    Scores are |residual_i| / scale_i with the same ceil((1-alpha)(n+1))
    rank rule; pair with conformal_interval_normalized (pred ± q * scale).
    Returns 1e308 when inputs are empty, lengths mismatch, or k > n.
    A nonpositive / non-finite scale or NaN residual makes that sample's
    score 1e308 (maximally nonconforming — conservative, not dropped).
    """
    var n = len(residuals_calibration)
    if n <= 0 or len(scales) != n:
        return _INF
    var scores = List[Float64](capacity=n)
    for i in range(n):
        var sc = scales[i]
        var score: Float64
        if isnan(sc) or isinf(sc) or sc <= 0.0:
            score = _INF
        else:
            score = fabs(residuals_calibration[i]) / sc
            if isnan(score) or isinf(score):
                # NaN/inf residual, or a denormal scale overflowing the
                # division to inf: clamp to the finite sentinel.
                score = _INF
        scores.append(score)
    return _quantile_of_scores(scores^, alpha)


# ── conformal_interval / conformal_interval_normalized ───────────────────────


fn conformal_interval(pred: Float64, q: Float64) -> ConformalInterval:
    """Symmetric conformal interval [pred - q, pred + q].

    A negative or NaN q is treated as 0 (degenerate point interval) so a
    malformed half-width can never invert the bounds.
    """
    var hw = q
    if not (hw > 0.0):
        hw = 0.0
    return ConformalInterval(pred - hw, pred + hw)


fn conformal_interval_normalized(
    pred: Float64, q: Float64, scale: Float64
) -> ConformalInterval:
    """Normalized conformal interval [pred - q*scale, pred + q*scale].

    scale is this sample's difficulty estimate (same units as the
    calibration scales). A negative or NaN half-width collapses to 0.
    """
    var hw = q * scale
    if not (hw > 0.0):
        hw = 0.0
    return ConformalInterval(pred - hw, pred + hw)


# ── conformal_band ───────────────────────────────────────────────────────────


fn conformal_band(preds: List[Float64], q: Float64) -> ConformalBand:
    """Intervals pred_i ± q for every prediction (feeds conformal_coverage)."""
    var out = ConformalBand()
    for i in range(len(preds)):
        var iv = conformal_interval(preds[i], q)
        out.lo.append(iv.lo)
        out.hi.append(iv.hi)
    return out^


# ── conformal_coverage ───────────────────────────────────────────────────────


fn conformal_coverage(
    y: List[Float64], lo: List[Float64], hi: List[Float64]
) -> Float64:
    """Fraction of samples with lo[i] <= y[i] <= hi[i] (bounds inclusive).

    Returns 0.0 for empty or length-mismatched inputs (fail-safe: malformed
    data never reports coverage). NaN y never counts as covered.
    """
    var n = len(y)
    if n <= 0 or len(lo) != n or len(hi) != n:
        return 0.0
    var covered = 0
    for i in range(n):
        if y[i] >= lo[i] and y[i] <= hi[i]:
            covered += 1
    return Float64(covered) / Float64(n)
