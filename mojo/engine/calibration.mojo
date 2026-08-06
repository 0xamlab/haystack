"""
calibration.mojo — Probability/prediction calibration. Zero Python imports.

Replaces sklearn.isotonic (IsotonicRegression, PAVA), Platt scaling
(sklearn.calibration sigmoid method / LIBSVM sigmoid_train), and
sklearn.calibration.calibration_curve.

Public API:
  IsotonicFit        — thresholds + fitted values from PAV
  PlattParams        — sigmoid parameters (a, b) for p = 1/(1+exp(a*s+b))
  CalibrationCurve   — bin_centers, observed_freq, counts
  isotonic_fit       — Pool Adjacent Violators fit; ties in x averaged
  isotonic_transform — stepwise linear interpolation, clipped at extremes
  platt_fit          — Newton fit of Platt sigmoid with target smoothing
  platt_transform    — apply fitted sigmoid to scores
  calibration_curve  — reliability curve with equal-width bins on [0,1]
"""

from std.math import abs as fabs, exp, log


# ── result structs ───────────────────────────────────────────────────────────


struct IsotonicFit(Copyable, Movable):
    """Result of isotonic_fit: unique sorted x thresholds and the
    non-decreasing fitted values at those thresholds."""

    var thresholds: List[Float64]
    var values: List[Float64]

    def __init__(
        out self, thresholds: List[Float64], values: List[Float64]
    ):
        self.thresholds = thresholds.copy()
        self.values = values.copy()


struct PlattParams(Copyable, Movable):
    """Result of platt_fit: p = 1/(1+exp(a*s+b))."""

    var a: Float64
    var b: Float64

    def __init__(out self, a: Float64, b: Float64):
        self.a = a
        self.b = b


struct CalibrationCurve(Copyable, Movable):
    """Result of calibration_curve: per-bin center, observed label
    frequency (0.0 for empty bins) and sample count."""

    var bin_centers: List[Float64]
    var observed_freq: List[Float64]
    var counts: List[Int]

    def __init__(
        out self,
        bin_centers: List[Float64],
        observed_freq: List[Float64],
        counts: List[Int],
    ):
        self.bin_centers = bin_centers.copy()
        self.observed_freq = observed_freq.copy()
        self.counts = counts.copy()


# ── helpers ──────────────────────────────────────────────────────────────────


def _sort_pairs(mut xs: List[Float64], mut ys: List[Float64]):
    """Stable bottom-up merge sort of (xs, ys) pairs keyed on xs."""
    var n = len(xs)
    if n < 2:
        return
    var tmp_x = List[Float64](capacity=n)
    var tmp_y = List[Float64](capacity=n)
    for _ in range(n):
        tmp_x.append(0.0)
        tmp_y.append(0.0)
    var width = 1
    while width < n:
        var lo = 0
        while lo < n:
            var mid = lo + width
            if mid > n:
                mid = n
            var hi = lo + 2 * width
            if hi > n:
                hi = n
            var i = lo
            var j = mid
            var k = lo
            while i < mid and j < hi:
                if xs[i] <= xs[j]:
                    tmp_x[k] = xs[i]
                    tmp_y[k] = ys[i]
                    i += 1
                else:
                    tmp_x[k] = xs[j]
                    tmp_y[k] = ys[j]
                    j += 1
                k += 1
            while i < mid:
                tmp_x[k] = xs[i]
                tmp_y[k] = ys[i]
                i += 1
                k += 1
            while j < hi:
                tmp_x[k] = xs[j]
                tmp_y[k] = ys[j]
                j += 1
                k += 1
            for m in range(lo, hi):
                xs[m] = tmp_x[m]
                ys[m] = tmp_y[m]
            lo += 2 * width
        width *= 2


def _platt_nll(
    scores: List[Float64], targets: List[Float64], n: Int, a: Float64, b: Float64
) -> Float64:
    """Numerically stable NLL of the Platt sigmoid at (a, b)."""
    var f: Float64 = 0.0
    for i in range(n):
        var fapb = scores[i] * a + b
        if fapb >= 0.0:
            f += targets[i] * fapb + log(1.0 + exp(-fapb))
        else:
            f += (targets[i] - 1.0) * fapb + log(1.0 + exp(fapb))
    return f


def _sigmoid_neg(fapb: Float64) -> Float64:
    """Stable 1/(1+exp(fapb))."""
    if fapb >= 0.0:
        var e = exp(-fapb)
        return e / (1.0 + e)
    return 1.0 / (1.0 + exp(fapb))


# ── isotonic_fit ─────────────────────────────────────────────────────────────


def isotonic_fit(x: List[Float64], y: List[Float64]) -> IsotonicFit:
    """Isotonic regression via Pool Adjacent Violators.

    Sorts (x, y) by x, averages y over tied x values (weight = tie count),
    then pools adjacent violators to produce the non-decreasing stepwise
    fit. Returns unique sorted thresholds and fitted values at each.
    """
    var n = len(x)
    if len(y) < n:
        n = len(y)
    var thresholds = List[Float64]()
    var values = List[Float64]()
    if n == 0:
        return IsotonicFit(thresholds, values)

    var xs = List[Float64](capacity=n)
    var ys = List[Float64](capacity=n)
    for i in range(n):
        xs.append(x[i])
        ys.append(y[i])
    _sort_pairs(xs, ys)

    # Collapse ties in x: mean y, weight = count.
    var ux = List[Float64]()
    var uy = List[Float64]()
    var uw = List[Float64]()
    var i = 0
    while i < n:
        var j = i
        var s: Float64 = 0.0
        while j < n and xs[j] == xs[i]:
            s += ys[j]
            j += 1
        ux.append(xs[i])
        uy.append(s / Float64(j - i))
        uw.append(Float64(j - i))
        i = j

    # PAV over blocks (value, weight, span of unique-x points).
    var m = len(ux)
    var bval = List[Float64](capacity=m)
    var bw = List[Float64](capacity=m)
    var bcount = List[Int](capacity=m)
    for _ in range(m):
        bval.append(0.0)
        bw.append(0.0)
        bcount.append(0)
    var top = -1
    for k in range(m):
        top += 1
        bval[top] = uy[k]
        bw[top] = uw[k]
        bcount[top] = 1
        while top >= 1 and bval[top - 1] > bval[top]:
            var wsum = bw[top - 1] + bw[top]
            bval[top - 1] = (
                bval[top - 1] * bw[top - 1] + bval[top] * bw[top]
            ) / wsum
            bw[top - 1] = wsum
            bcount[top - 1] += bcount[top]
            top -= 1

    # Expand blocks back to per-threshold fitted values.
    for k in range(m):
        thresholds.append(ux[k])
    for b in range(top + 1):
        for _ in range(bcount[b]):
            values.append(bval[b])
    return IsotonicFit(thresholds, values)


# ── isotonic_transform ───────────────────────────────────────────────────────


def isotonic_transform(
    thresholds: List[Float64], values: List[Float64], x_new: List[Float64]
) -> List[Float64]:
    """Evaluate an isotonic fit at new points.

    Below the first threshold clamps to the first value, above the last
    clamps to the last value, and in between uses linear interpolation
    (matches sklearn IsotonicRegression with out_of_bounds='clip').
    Empty fit maps everything to 0.0.
    """
    var out = List[Float64](capacity=len(x_new))
    var m = len(thresholds)
    if len(values) < m:
        m = len(values)
    if m == 0:
        for _ in range(len(x_new)):
            out.append(0.0)
        return out^
    for i in range(len(x_new)):
        var xv = x_new[i]
        if xv <= thresholds[0]:
            out.append(values[0])
            continue
        if xv >= thresholds[m - 1]:
            out.append(values[m - 1])
            continue
        # Binary search: largest lo with thresholds[lo] <= xv.
        var lo = 0
        var hi = m - 1
        while hi - lo > 1:
            var mid = (lo + hi) // 2
            if thresholds[mid] <= xv:
                lo = mid
            else:
                hi = mid
        var x0 = thresholds[lo]
        var x1 = thresholds[hi]
        var dx = x1 - x0
        if dx <= 0.0:
            out.append(values[lo])
            continue
        var t = (xv - x0) / dx
        out.append(values[lo] + t * (values[hi] - values[lo]))
    return out^


# ── platt_fit ────────────────────────────────────────────────────────────────


def platt_fit(
    scores: List[Float64], labels: List[Float64], max_iter: Int = 100
) -> PlattParams:
    """Fit Platt sigmoid p = 1/(1+exp(a*s+b)) by Newton descent on the NLL.

    Uses Platt's smoothed targets t+ = (N+ +1)/(N+ +2), t- = 1/(N- +2)
    and the Lin–Weng–Keerthi Newton iteration with backtracking line
    search. Deterministic. labels > 0.5 count as positive.
    """
    var n = len(scores)
    if len(labels) < n:
        n = len(labels)
    if n == 0:
        return PlattParams(0.0, 0.0)

    var n_pos: Float64 = 0.0
    var n_neg: Float64 = 0.0
    for i in range(n):
        if labels[i] > 0.5:
            n_pos += 1.0
        else:
            n_neg += 1.0
    var hi_t = (n_pos + 1.0) / (n_pos + 2.0)
    var lo_t = 1.0 / (n_neg + 2.0)
    var targets = List[Float64](capacity=n)
    for i in range(n):
        if labels[i] > 0.5:
            targets.append(hi_t)
        else:
            targets.append(lo_t)

    var a: Float64 = 0.0
    var b: Float64 = log((n_neg + 1.0) / (n_pos + 1.0))
    var sigma: Float64 = 1e-12  # Hessian ridge for numerical safety
    var eps: Float64 = 1e-5
    var min_step: Float64 = 1e-10
    var fval = _platt_nll(scores, targets, n, a, b)

    for _ in range(max_iter):
        # Gradient and Hessian of the NLL.
        var h11 = sigma
        var h22 = sigma
        var h21: Float64 = 0.0
        var g1: Float64 = 0.0
        var g2: Float64 = 0.0
        for i in range(n):
            var fapb = scores[i] * a + b
            var p = _sigmoid_neg(fapb)
            var q = 1.0 - p
            var d2 = p * q
            h11 += scores[i] * scores[i] * d2
            h22 += d2
            h21 += scores[i] * d2
            var d1 = targets[i] - p
            g1 += scores[i] * d1
            g2 += d1
        if fabs(g1) < eps and fabs(g2) < eps:
            break
        var det = h11 * h22 - h21 * h21
        var da = -(h22 * g1 - h21 * g2) / det
        var db = -(-h21 * g1 + h11 * g2) / det
        var gd = g1 * da + g2 * db

        # Backtracking line search (Armijo).
        var stepsize: Float64 = 1.0
        while stepsize >= min_step:
            var new_a = a + stepsize * da
            var new_b = b + stepsize * db
            var new_f = _platt_nll(scores, targets, n, new_a, new_b)
            if new_f < fval + 0.0001 * stepsize * gd:
                a = new_a
                b = new_b
                fval = new_f
                break
            stepsize /= 2.0
        if stepsize < min_step:
            break
    return PlattParams(a, b)


# ── platt_transform ──────────────────────────────────────────────────────────


def platt_transform(
    a: Float64, b: Float64, scores: List[Float64]
) -> List[Float64]:
    """Apply the fitted Platt sigmoid: p_i = 1/(1+exp(a*s_i+b))."""
    var out = List[Float64](capacity=len(scores))
    for i in range(len(scores)):
        out.append(_sigmoid_neg(scores[i] * a + b))
    return out^


# ── calibration_curve ────────────────────────────────────────────────────────


def calibration_curve(
    probs: List[Float64], labels: List[Float64], n_bins: Int
) -> CalibrationCurve:
    """Reliability curve: equal-width bins on [0,1].

    Bin i covers [i/n_bins, (i+1)/n_bins) with the last bin closed at 1.0;
    probs are clamped into [0,1]. observed_freq is the mean label per bin
    (0.0 for empty bins); counts is the per-bin sample count.
    """
    var centers = List[Float64]()
    var freq = List[Float64]()
    var counts = List[Int]()
    if n_bins <= 0:
        return CalibrationCurve(centers, freq, counts)
    var sums = List[Float64](capacity=n_bins)
    for bin_i in range(n_bins):
        centers.append((Float64(bin_i) + 0.5) / Float64(n_bins))
        freq.append(0.0)
        counts.append(0)
        sums.append(0.0)
    var n = len(probs)
    if len(labels) < n:
        n = len(labels)
    for i in range(n):
        var p = probs[i]
        if p < 0.0:
            p = 0.0
        if p > 1.0:
            p = 1.0
        var idx = Int(p * Float64(n_bins))
        if idx >= n_bins:
            idx = n_bins - 1
        counts[idx] += 1
        sums[idx] += labels[i]
    for bin_i in range(n_bins):
        if counts[bin_i] > 0:
            freq[bin_i] = sums[bin_i] / Float64(counts[bin_i])
    return CalibrationCurve(centers, freq, counts)
