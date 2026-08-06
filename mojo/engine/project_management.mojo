"""Project Management Library — Earned Value Management, PERT, critical path."""

from std.math import sqrt, log, exp, abs


def earned_value(bac: Float64, pct_complete: Float64) -> Float64:
    """EV = BAC * pct_complete / 100."""
    return bac * pct_complete / 100.0


def schedule_variance(ev: Float64, pv: Float64) -> Float64:
    """SV = EV - PV."""
    return ev - pv


def cost_variance(ev: Float64, ac: Float64) -> Float64:
    """CV = EV - AC."""
    return ev - ac


def schedule_performance_index(ev: Float64, pv: Float64) -> Float64:
    """SPI = EV / PV."""
    if pv == 0.0:
        return 0.0
    return ev / pv


def cost_performance_index(ev: Float64, ac: Float64) -> Float64:
    """CPI = EV / AC."""
    if ac == 0.0:
        return 0.0
    return ev / ac


def estimate_at_completion(bac: Float64, cpi: Float64) -> Float64:
    """EAC = BAC / CPI."""
    if cpi == 0.0:
        return 0.0
    return bac / cpi


def estimate_to_complete(eac: Float64, ac: Float64) -> Float64:
    """ETC = EAC - AC."""
    return eac - ac


def variance_at_completion(bac: Float64, eac: Float64) -> Float64:
    """VAC = BAC - EAC."""
    return bac - eac


def to_complete_performance_index(
    bac: Float64, ev: Float64, ac: Float64
) -> Float64:
    """TCPI = (BAC - EV) / (BAC - AC)."""
    var denom = bac - ac
    if denom == 0.0:
        return 0.0
    return (bac - ev) / denom


def critical_path_duration(task_durations_sum: Float64) -> Float64:
    """CP = sum (pass pre-computed sum)."""
    return task_durations_sum


def float_time(late_finish: Float64, early_finish: Float64) -> Float64:
    """Float = LF - EF."""
    return late_finish - early_finish


def pert_estimate(
    optimistic: Float64, most_likely: Float64, pessimistic: Float64
) -> Float64:
    """E = (O + 4M + P) / 6."""
    return (optimistic + 4.0 * most_likely + pessimistic) / 6.0
