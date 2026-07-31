"""forecast_metrics — forecast scoring for the backtest.

Every number the accuracy claim rests on is computed here. Python selects rows and prints.

Design notes that matter for honest reporting:

  * Brier alone is misleading for RARE events. An overtake base rate near 3% makes a constant
    base-rate predictor score about p(1-p) = 0.031, so a "good-looking" 0.0275 is only ~10% skill.
    brier_skill_score against an explicit baseline is therefore the primary number, and raw Brier is
    reported beside it rather than instead of it.
  * The Murphy decomposition (BS = reliability - resolution + uncertainty) separates the two failure
    modes a single score conflates: miscalibration and lack of discrimination. A forecaster can improve
    Brier by becoming better calibrated while losing resolution, and that trade should be visible.
  * ECE and the reliability diagram share ONE binning function, so a published diagram and a published
    ECE can never disagree about which bin a forecast fell in.
  * Spearman is computed with proper tie handling (average ranks). Finishing positions tie whenever
    cars are classified equal, and integer-rank shortcuts silently bias rho.
"""

from math import log, sqrt


struct MurphyTerms(Copyable, Movable):
    """BS = reliability - resolution + uncertainty. Lower reliability is better; higher resolution is."""

    var brier: Float64
    var reliability: Float64
    var resolution: Float64
    var uncertainty: Float64
    var n: Int
    var base_rate: Float64

    fn __init__(
        out self, brier: Float64, reliability: Float64, resolution: Float64,
        uncertainty: Float64, n: Int, base_rate: Float64,
    ):
        self.brier = brier
        self.reliability = reliability
        self.resolution = resolution
        self.uncertainty = uncertainty
        self.n = n
        self.base_rate = base_rate


struct ReliabilityBins(Copyable, Movable):
    """Per-bin forecast mean, observed frequency and count. Empty bins carry count 0."""

    var bin_center: List[Float64]
    var forecast_mean: List[Float64]
    var observed_freq: List[Float64]
    var count: List[Float64]

    fn __init__(
        out self, var bin_center: List[Float64], var forecast_mean: List[Float64],
        var observed_freq: List[Float64], var count: List[Float64],
    ):
        self.bin_center = bin_center^
        self.forecast_mean = forecast_mean^
        self.observed_freq = observed_freq^
        self.count = count^


fn brier_score(probs: List[Float64], outcomes: List[Float64]) -> Float64:
    """Mean squared error of probabilistic forecasts against 0/1 outcomes."""
    var n = len(probs)
    if len(outcomes) < n:
        n = len(outcomes)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        var d = probs[i] - outcomes[i]
        s += d * d
    return s / Float64(n)


fn base_rate(outcomes: List[Float64]) -> Float64:
    """Observed event frequency — the climatological baseline."""
    var n = len(outcomes)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        s += outcomes[i]
    return s / Float64(n)


fn brier_skill_score(probs: List[Float64], outcomes: List[Float64], baseline: Float64) -> Float64:
    """Skill against a constant-probability baseline. 0 means no better than the baseline.

    This is the primary accuracy number, not raw Brier. For a rare event a constant base-rate
    forecast already scores well, so raw Brier flatters any model.
    """
    # Effective n must match brier_score's, or an EMPTY probability vector yields bs = 0 and a skill
    # score of 1.0 -- a metric reporting perfection for no data. That silently turned an
    # argument-order mistake in a caller into a flawless calibration result.
    var n = len(probs)
    if len(outcomes) < n:
        n = len(outcomes)
    if n == 0:
        return 0.0
    var bs = brier_score(probs, outcomes)
    var baseline_bs = 0.0
    for i in range(n):
        var d = baseline - outcomes[i]
        baseline_bs += d * d
    baseline_bs /= Float64(n)
    if baseline_bs <= 0.0:
        return 0.0
    return 1.0 - bs / baseline_bs


fn log_loss(probs: List[Float64], outcomes: List[Float64], eps: Float64) -> Float64:
    """Mean negative log likelihood, clipped by eps so a confident miss is finite but heavy."""
    var n = len(probs)
    if len(outcomes) < n:
        n = len(outcomes)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        var p = probs[i]
        if p < eps:
            p = eps
        if p > 1.0 - eps:
            p = 1.0 - eps
        if outcomes[i] > 0.5:
            s -= log(p)
        else:
            s -= log(1.0 - p)
    return s / Float64(n)


fn reliability_bins(
    probs: List[Float64], outcomes: List[Float64], n_bins: Int
) -> ReliabilityBins:
    """Equal-width binning shared by ECE and the reliability diagram, so the two cannot disagree."""
    var centers = List[Float64]()
    var fmean = List[Float64]()
    var ofreq = List[Float64]()
    var cnt = List[Float64]()
    var nb = n_bins
    if nb < 1:
        nb = 1
    for b in range(nb):
        centers.append((Float64(b) + 0.5) / Float64(nb))
        fmean.append(0.0)
        ofreq.append(0.0)
        cnt.append(0.0)

    var n = len(probs)
    if len(outcomes) < n:
        n = len(outcomes)
    for i in range(n):
        var p = probs[i]
        if p < 0.0:
            p = 0.0
        if p > 1.0:
            p = 1.0
        var b = Int(p * Float64(nb))
        if b >= nb:
            b = nb - 1
        cnt[b] = cnt[b] + 1.0
        fmean[b] = fmean[b] + p
        ofreq[b] = ofreq[b] + outcomes[i]
    for b in range(nb):
        if cnt[b] > 0.0:
            fmean[b] = fmean[b] / cnt[b]
            ofreq[b] = ofreq[b] / cnt[b]
    return ReliabilityBins(centers^, fmean^, ofreq^, cnt^)


fn expected_calibration_error(
    probs: List[Float64], outcomes: List[Float64], n_bins: Int
) -> Float64:
    """Bin-weighted mean |forecast - observed|, over the same bins as the diagram."""
    var rb = reliability_bins(probs, outcomes, n_bins)
    var total = 0.0
    for b in range(len(rb.count)):
        total += rb.count[b]
    if total <= 0.0:
        return 0.0
    var e = 0.0
    for b in range(len(rb.count)):
        if rb.count[b] > 0.0:
            var d = rb.forecast_mean[b] - rb.observed_freq[b]
            if d < 0.0:
                d = -d
            e += rb.count[b] * d
    return e / total


fn murphy_decomposition(
    probs: List[Float64], outcomes: List[Float64], n_bins: Int
) -> MurphyTerms:
    """BS = REL - RES + UNC over binned forecasts.

    Reported because a single Brier hides which of the two failure modes moved: a model can look better
    by becoming calibrated while losing discrimination, and that should be visible rather than netted.
    """
    var n = len(probs)
    if len(outcomes) < n:
        n = len(outcomes)
    var br = base_rate(outcomes)
    var unc = br * (1.0 - br)
    if n == 0:
        return MurphyTerms(0.0, 0.0, 0.0, 0.0, 0, 0.0)

    var rb = reliability_bins(probs, outcomes, n_bins)
    var rel = 0.0
    var res = 0.0
    for b in range(len(rb.count)):
        var k = rb.count[b]
        if k <= 0.0:
            continue
        var d1 = rb.forecast_mean[b] - rb.observed_freq[b]
        rel += k * d1 * d1
        var d2 = rb.observed_freq[b] - br
        res += k * d2 * d2
    rel /= Float64(n)
    res /= Float64(n)
    return MurphyTerms(brier_score(probs, outcomes), rel, res, unc, n, br)


fn _avg_ranks(x: List[Float64]) -> List[Float64]:
    """Average ranks with tie handling. Integer ranks bias Spearman when values tie."""
    var n = len(x)
    var idx = List[Int]()
    for i in range(n):
        idx.append(i)
    # insertion sort on value (n is small: field size, or races per season)
    for i in range(1, n):
        var j = i
        while j > 0 and x[idx[j - 1]] > x[idx[j]]:
            var tmp = idx[j - 1]
            idx[j - 1] = idx[j]
            idx[j] = tmp
            j -= 1
    var ranks = List[Float64]()
    for _ in range(n):
        ranks.append(0.0)
    var i = 0
    while i < n:
        var j = i
        while j + 1 < n and x[idx[j + 1]] == x[idx[i]]:
            j += 1
        var avg = (Float64(i) + Float64(j)) * 0.5 + 1.0
        for k in range(i, j + 1):
            ranks[idx[k]] = avg
        i = j + 1
    return ranks^


fn spearman_rho(a: List[Float64], b: List[Float64]) -> Float64:
    """Rank correlation with proper tie handling — Pearson on average ranks."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    if n < 2:
        return 0.0
    var ra = _avg_ranks(a)
    var rb = _avg_ranks(b)
    var ma = 0.0
    var mb = 0.0
    for i in range(n):
        ma += ra[i]
        mb += rb[i]
    ma /= Float64(n)
    mb /= Float64(n)
    var num = 0.0
    var va = 0.0
    var vb = 0.0
    for i in range(n):
        var da = ra[i] - ma
        var db = rb[i] - mb
        num += da * db
        va += da * da
        vb += db * db
    if va <= 0.0 or vb <= 0.0:
        return 0.0
    return num / sqrt(va * vb)


# ── deterministic zero-argument probes ────────────────────────────────────────


fn metrics_version() -> String:
    """Contract identifier. Deterministic, zero-argument."""
    return String("forecast-metrics/v1")


fn metrics_selftest() -> Float64:
    """A perfectly calibrated 2-bin forecast must have zero reliability. Deterministic, zero-argument."""
    var p = List[Float64]()
    var o = List[Float64]()
    for i in range(100):
        if i < 50:
            p.append(0.2)
            o.append(1.0 if i < 10 else 0.0)
        else:
            p.append(0.8)
            o.append(1.0 if i < 90 else 0.0)
    var m = murphy_decomposition(p, o, 10)
    return m.reliability
