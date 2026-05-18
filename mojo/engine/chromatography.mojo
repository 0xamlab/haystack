"""
chromatography.mojo — Chemical separation science calculations. Zero Python imports.

Public API:
  retention_factor             — k = (tR - t0) / t0
  selectivity_factor           — α = k2 / k1
  plate_count                  — N = 16*(tR/w)²
  plate_height                 — H = L / N
  resolution                   — Rs = 2*(tR2-tR1)/(w1+w2)
  van_deemter_h                — H = A + B/u + C*u
  peak_capacity                — n_c = 1 + sqrt(N)/4 * ln(tR_last/tR_first)
  separation_number            — TZ from consecutive peaks
  retention_index_kovats       — I from reference n-alkane RTs
  mobile_phase_velocity        — u = L / t0
"""
from std.math import sqrt, log


fn retention_factor(retention_time: Float64, dead_time: Float64) -> Float64:
    """Capacity (retention) factor: k = (tR - t0) / t0.

    Args:
        retention_time: Analyte retention time tR (s or min).
        dead_time: Column dead time t0 (s or min).

    Returns:
        Retention factor k (dimensionless).
    """
    if dead_time <= 0.0:
        return 0.0
    return (retention_time - dead_time) / dead_time


fn selectivity_factor(k2: Float64, k1: Float64) -> Float64:
    """Selectivity factor: α = k2/k1 (k2 > k1).

    Args:
        k2: Retention factor of the more retained analyte.
        k1: Retention factor of the less retained analyte.

    Returns:
        Selectivity factor α (≥ 1).
    """
    if k1 <= 0.0:
        return 0.0
    return k2 / k1


fn plate_count(retention_time: Float64, peak_width: Float64) -> Float64:
    """Theoretical plate count: N = 16·(tR/w)².

    Args:
        retention_time: Retention time tR.
        peak_width: Peak width at base w.

    Returns:
        Number of theoretical plates N.
    """
    if peak_width <= 0.0:
        return 0.0
    var ratio = retention_time / peak_width
    return 16.0 * ratio * ratio


fn plate_height(column_length: Float64, n_plates: Float64) -> Float64:
    """Height equivalent to a theoretical plate: H = L/N.

    Args:
        column_length: Column length L (m or cm).
        n_plates: Theoretical plate count N.

    Returns:
        Plate height H (same units as L).
    """
    if n_plates <= 0.0:
        return 0.0
    return column_length / n_plates


fn resolution(
    tr2: Float64, tr1: Float64, w1: Float64, w2: Float64
) -> Float64:
    """Chromatographic resolution: Rs = 2·(tR2 - tR1)/(w1 + w2).

    Args:
        tr2: Retention time of second peak.
        tr1: Retention time of first peak.
        w1: Peak width at base of peak 1.
        w2: Peak width at base of peak 2.

    Returns:
        Resolution Rs (>1.5 = baseline separation).
    """
    var w_sum = w1 + w2
    if w_sum <= 0.0:
        return 0.0
    return 2.0 * (tr2 - tr1) / w_sum


fn van_deemter_h(
    a_term: Float64, b_term: Float64, c_term: Float64, velocity: Float64
) -> Float64:
    """Van Deemter equation: H = A + B/u + C·u.

    Args:
        a_term: Eddy diffusion term A.
        b_term: Longitudinal diffusion term B.
        c_term: Mass transfer term C.
        velocity: Mobile phase velocity u.

    Returns:
        Plate height H.
    """
    if velocity <= 0.0:
        return a_term
    return a_term + b_term / velocity + c_term * velocity


fn peak_capacity(
    n_plates: Float64, tr_last: Float64, tr_first: Float64
) -> Float64:
    """Peak capacity: n_c = 1 + (√N/4)·ln(tR_last/tR_first).

    Args:
        n_plates: Column theoretical plate count.
        tr_last: Retention time of last peak.
        tr_first: Retention time of first eluting analyte.

    Returns:
        Peak capacity (number of resolvable peaks).
    """
    if tr_first <= 0.0 or tr_last <= tr_first:
        return 1.0
    return 1.0 + sqrt(n_plates) / 4.0 * log(tr_last / tr_first)


fn separation_number(
    tr_n: Float64, tr_n1: Float64, w_n: Float64, w_n1: Float64
) -> Float64:
    """Separation number (Trennzahl): TZ = (tR2 - tR1)/(w1+w2)/2 - 1.

    Args:
        tr_n: Retention time of peak n.
        tr_n1: Retention time of peak n+1.
        w_n: Width at half-height of peak n.
        w_n1: Width at half-height of peak n+1.

    Returns:
        Separation (Trennzahl) number.
    """
    var w_sum = w_n + w_n1
    if w_sum <= 0.0:
        return 0.0
    return (tr_n1 - tr_n) / (w_sum / 2.0) - 1.0


fn retention_index_kovats(
    tr_x: Float64, tr_n: Float64, tr_n1: Float64, n: Float64
) -> Float64:
    """Kovats retention index for isothermal GC.

    I = 100 · (n + log(tR_x/tR_n) / log(tR_n+1/tR_n))

    Args:
        tr_x: Retention time of analyte x.
        tr_n: Retention time of n-alkane with n carbons.
        tr_n1: Retention time of n-alkane with n+1 carbons.
        n: Carbon number of lower reference alkane.

    Returns:
        Kovats retention index.
    """
    if tr_n <= 0.0 or tr_n1 <= tr_n or tr_x <= 0.0:
        return 0.0
    return 100.0 * (n + log(tr_x / tr_n) / log(tr_n1 / tr_n))


fn mobile_phase_velocity(column_length: Float64, dead_time: Float64) -> Float64:
    """Linear mobile phase velocity: u = L/t0.

    Args:
        column_length: Column length L (cm or m).
        dead_time: Dead time t0 (s or min, same time unit as L/velocity).

    Returns:
        Linear velocity (L-unit / time-unit).
    """
    if dead_time <= 0.0:
        return 0.0
    return column_length / dead_time
