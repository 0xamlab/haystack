"""
survival.mojo — Survival Analysis. Zero Python imports.

Replaces lifelines with pure Mojo implementations of Kaplan-Meier estimator,
Nelson-Aalen cumulative hazard, log-rank test, hazard rate estimation,
restricted mean survival time, and life tables.

Public API:
  SurvivalPoint       — Struct: time, survival, at_risk, events
  kaplan_meier        — Kaplan-Meier estimator
  nelson_aalen        — Nelson-Aalen cumulative hazard
  median_survival     — Time where S(t) first drops below 0.5
  log_rank_statistic  — Log-rank test statistic comparing two groups
  hazard_rate         — Kernel-smoothed hazard rate estimate
  restricted_mean     — Restricted mean survival time (area under KM)
  life_table          — Life table by intervals
  survival_at_time    — Look up S(t) from KM curve
"""

from std.math import exp, abs as fabs, sqrt


# ── SurvivalPoint ────────────────────────────────────────────────────────────


struct SurvivalPoint(Copyable, Movable):
    """A point on a survival curve."""
    var time: Float64
    var survival: Float64
    var at_risk: Int
    var events: Int

    def __init__(out self, time: Float64, survival: Float64, at_risk: Int, events: Int):
        self.time = time
        self.survival = survival
        self.at_risk = at_risk
        self.events = events


# ── helpers ──────────────────────────────────────────────────────────────────


def _sort_indices(times: List[Float64]) -> List[Int]:
    """Return indices that sort times in ascending order."""
    var n = len(times)
    var idx = List[Int]()
    for i in range(n):
        idx.append(i)
    # Insertion sort
    for i in range(1, n):
        var key = idx[i]
        var key_val = times[key]
        var j = i - 1
        while j >= 0 and times[idx[j]] > key_val:
            idx[j + 1] = idx[j]
            j -= 1
        idx[j + 1] = key
    return idx^


# ── kaplan_meier ─────────────────────────────────────────────────────────────


def kaplan_meier(times: List[Float64], events: List[Bool]) -> List[SurvivalPoint]:
    """Kaplan-Meier estimator. S(t) = Π(1 - d_i/n_i).
    Returns survival curve starting at (0, 1.0)."""
    if len(events) != len(times):
        return List[SurvivalPoint]()
    var n = len(times)
    var result = List[SurvivalPoint]()
    result.append(SurvivalPoint(0.0, 1.0, n, 0))
    if n == 0:
        return result^

    var idx = _sort_indices(times)
    var surv: Float64 = 1.0
    var at_risk = n
    var i = 0

    while i < n:
        var t = times[idx[i]]
        var d = 0
        var c = 0
        # Count events and censored at this time
        while i < n and times[idx[i]] == t:
            if events[idx[i]]:
                d += 1
            else:
                c += 1
            i += 1
        if d > 0:
            surv *= (1.0 - Float64(d) / Float64(at_risk))
            result.append(SurvivalPoint(t, surv, at_risk, d))
        at_risk -= (d + c)
    return result^


# ── nelson_aalen ─────────────────────────────────────────────────────────────


def nelson_aalen(times: List[Float64], events: List[Bool]) -> List[List[Float64]]:
    """Nelson-Aalen cumulative hazard: H(t) = Σ(d_i/n_i).
    Returns [[time, H(t)], ...]."""
    if len(events) != len(times):
        return List[List[Float64]]()
    var n = len(times)
    var result = List[List[Float64]]()
    var row0 = List[Float64]()
    row0.append(0.0); row0.append(0.0)
    result.append(row0^)
    if n == 0:
        return result^

    var idx = _sort_indices(times)
    var cum_h: Float64 = 0.0
    var at_risk = n
    var i = 0

    while i < n:
        var t = times[idx[i]]
        var d = 0
        var c = 0
        while i < n and times[idx[i]] == t:
            if events[idx[i]]:
                d += 1
            else:
                c += 1
            i += 1
        if d > 0:
            cum_h += Float64(d) / Float64(at_risk)
            var row = List[Float64]()
            row.append(t); row.append(cum_h)
            result.append(row^)
        at_risk -= (d + c)
    return result^


# ── median_survival ──────────────────────────────────────────────────────────


def median_survival(km_curve: List[SurvivalPoint]) -> Float64:
    """Time where S(t) first drops below 0.5. Returns -1 if never."""
    for i in range(len(km_curve)):
        if km_curve[i].survival < 0.5:
            return km_curve[i].time
    return -1.0


# ── log_rank_statistic ───────────────────────────────────────────────────────


def log_rank_statistic(
    times1: List[Float64], events1: List[Bool],
    times2: List[Float64], events2: List[Bool],
) -> Float64:
    """Log-rank test statistic comparing two survival curves.
    Returns chi-squared statistic with 1 df."""
    if len(events1) != len(times1) or len(events2) != len(times2):
        return 0.0
    # Collect all unique event times
    var all_times = List[Float64]()
    for i in range(len(times1)):
        if events1[i]:
            var t = times1[i]
            var found = False
            for j in range(len(all_times)):
                if all_times[j] == t:
                    found = True
                    break
            if not found:
                all_times.append(t)
    for i in range(len(times2)):
        if events2[i]:
            var t = times2[i]
            var found = False
            for j in range(len(all_times)):
                if all_times[j] == t:
                    found = True
                    break
            if not found:
                all_times.append(t)

    # Sort all_times
    for i in range(1, len(all_times)):
        var key = all_times[i]
        var j = i - 1
        while j >= 0 and all_times[j] > key:
            all_times[j + 1] = all_times[j]
            j -= 1
        all_times[j + 1] = key

    var obs_minus_exp: Float64 = 0.0
    var variance: Float64 = 0.0

    for ti in range(len(all_times)):
        var t = all_times[ti]
        # Count at risk and events in each group at time t
        var n1 = 0
        var d1 = 0
        for j in range(len(times1)):
            if times1[j] >= t:
                n1 += 1
            if times1[j] == t and events1[j]:
                d1 += 1
        var n2 = 0
        var d2 = 0
        for j in range(len(times2)):
            if times2[j] >= t:
                n2 += 1
            if times2[j] == t and events2[j]:
                d2 += 1

        var n_total = n1 + n2
        var d_total = d1 + d2
        if n_total == 0:
            continue
        var e1 = Float64(n1) * Float64(d_total) / Float64(n_total)
        obs_minus_exp += Float64(d1) - e1

        if n_total > 1:
            var num = Float64(n1) * Float64(n2) * Float64(d_total) * Float64(n_total - d_total)
            var den = Float64(n_total) * Float64(n_total) * Float64(n_total - 1)
            variance += num / den

    if variance <= 0.0:
        return 0.0
    return (obs_minus_exp * obs_minus_exp) / variance


# ── hazard_rate ──────────────────────────────────────────────────────────────


def hazard_rate(
    times: List[Float64], events: List[Bool], bandwidth: Float64,
) -> List[List[Float64]]:
    """Kernel-smoothed hazard rate estimate using Epanechnikov kernel.
    Returns [[time, h(t)], ...]."""
    if len(events) != len(times):
        return List[List[Float64]]()
    var n = len(times)
    var idx = _sort_indices(times)
    # Get unique event times
    var utimes = List[Float64]()
    for i in range(n):
        if events[idx[i]]:
            var t = times[idx[i]]
            var found = False
            for j in range(len(utimes)):
                if utimes[j] == t:
                    found = True
                    break
            if not found:
                utimes.append(t)

    var result = List[List[Float64]]()
    for ti in range(len(utimes)):
        var t = utimes[ti]
        var num: Float64 = 0.0
        var den: Float64 = 0.0
        for j in range(n):
            var u = (t - times[j]) / bandwidth
            if fabs(u) <= 1.0:
                var k = 0.75 * (1.0 - u * u)
                if events[j]:
                    num += k
                den += k
        var h: Float64 = 0.0
        if den > 0.0:
            h = num / (den * bandwidth)
        var row = List[Float64]()
        row.append(t); row.append(h)
        result.append(row^)
    return result^


# ── restricted_mean ──────────────────────────────────────────────────────────


def restricted_mean(km_curve: List[SurvivalPoint], tau: Float64) -> Float64:
    """Restricted mean survival time: area under KM curve up to tau.
    Uses trapezoidal integration."""
    var area: Float64 = 0.0
    var n = len(km_curve)
    for i in range(1, n):
        var t0 = km_curve[i - 1].time
        var t1 = km_curve[i].time
        if t0 >= tau:
            break
        if t1 > tau:
            t1 = tau
        var s0 = km_curve[i - 1].survival
        area += s0 * (t1 - t0)  # Step function: use previous survival
    # Add remaining area from last step to tau
    if n > 0:
        var last_t = km_curve[n - 1].time
        var last_s = km_curve[n - 1].survival
        if last_t < tau:
            area += last_s * (tau - last_t)
    return area


# ── life_table ───────────────────────────────────────────────────────────────


def life_table(
    times: List[Float64], events: List[Bool], intervals: List[Float64],
) -> List[List[Float64]]:
    """Life table: for each interval, [start, n_risk, n_event, survival].
    intervals defines the start of each interval. Last interval goes to +inf."""
    if len(events) != len(times):
        return List[List[Float64]]()
    var n_int = len(intervals)
    var result = List[List[Float64]]()
    var surv: Float64 = 1.0
    var n_total = len(times)

    for k in range(n_int):
        var lo = intervals[k]
        var hi: Float64 = 1e30
        if k + 1 < n_int:
            hi = intervals[k + 1]

        var n_risk = 0
        var n_event = 0
        for j in range(n_total):
            if times[j] >= lo:
                n_risk += 1
        for j in range(n_total):
            if times[j] >= lo and times[j] < hi and events[j]:
                n_event += 1

        if n_risk > 0 and n_event > 0:
            surv *= (1.0 - Float64(n_event) / Float64(n_risk))

        var row = List[Float64]()
        row.append(lo)
        row.append(Float64(n_risk))
        row.append(Float64(n_event))
        row.append(surv)
        result.append(row^)
    return result^


# ── survival_at_time ─────────────────────────────────────────────────────────


def survival_at_time(km_curve: List[SurvivalPoint], t: Float64) -> Float64:
    """Look up S(t) from KM curve. Step function: returns S at largest time <= t."""
    var s: Float64 = 1.0
    for i in range(len(km_curve)):
        if km_curve[i].time <= t:
            s = km_curve[i].survival
        else:
            break
    return s
