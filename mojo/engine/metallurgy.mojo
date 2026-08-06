"""
metallurgy.mojo — Metallurgy equations. Zero Python imports.

Pure Mojo implementations of metallurgical formulas including
yield strength, flow stress, hardness conversion, hardenability,
phase transformation, tempering, and thermal/electrical conductivity.

Public API:
  hall_petch                          — σ_y = σ0 + k_y / sqrt(d)
  johnson_cook_flow_stress            — σ = A + B*ε^n
  hardness_to_tensile                 — σ_uts ≈ 3.45 * HB
  carbon_equivalent                   — CE weldability index
  jominy_distance_to_hardness         — H = h0 * exp(-decay*d)
  avrami_fraction                     — f = 1 - exp(-k*t^n)
  quench_severity                     — ideal_dia = h * diameter
  tempering_parameter                 — Hollomon-Jaffe P = T*(C + log10(t))
  density_of_alloy_rule_of_mixtures   — ρ = f1*d1 + f2*d2
  thermal_conductivity_wiedemann_franz — k = L*σ*T
  strain_hardening_exponent_from_points — n = ln(σ2/σ1)/ln(ε2/ε1)
  fatigue_life_basquin                — Nf = (σ_a / σ_f)^(1/b)
"""
from std.math import sqrt, exp, log, abs as fabs


# ── hall_petch ───────────────────────────────────────────────────────────────


def hall_petch(sigma0: Float64, ky: Float64, d: Float64) -> Float64:
    """Hall-Petch relation: σ_y = σ0 + k_y / sqrt(d).

    Args:
        sigma0: Friction stress (MPa).
        ky:     Strengthening coefficient (MPa·m^0.5).
        d:      Average grain diameter (m).

    Returns:
        Yield strength σ_y (MPa).
    """
    if d <= 0.0:
        return sigma0
    return sigma0 + ky / sqrt(d)


# ── johnson_cook_flow_stress ─────────────────────────────────────────────────


def johnson_cook_flow_stress(a: Float64, b: Float64, strain: Float64, n: Float64) -> Float64:
    """Johnson-Cook quasi-static flow stress: σ = A + B*ε^n.

    Args:
        a:      Yield stress constant A (MPa).
        b:      Hardening constant B (MPa).
        strain: Equivalent plastic strain ε.
        n:      Strain hardening exponent.

    Returns:
        Flow stress σ (MPa).
    """
    if strain <= 0.0:
        return a
    return a + b * exp(n * log(strain))


# ── hardness_to_tensile ──────────────────────────────────────────────────────


def hardness_to_tensile(hb: Float64) -> Float64:
    """Brinell hardness to ultimate tensile strength: σ_uts ≈ 3.45 * HB.

    Args:
        hb: Brinell hardness number.

    Returns:
        Approximate UTS (MPa).
    """
    return 3.45 * hb


# ── carbon_equivalent ────────────────────────────────────────────────────────


def carbon_equivalent(
    c: Float64, mn: Float64, si: Float64,
    ni: Float64, cr: Float64, mo: Float64, v: Float64,
) -> Float64:
    """Carbon equivalent (IIW simplified, Cu=0).

    CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15.

    Args:
        c:  Carbon wt%.
        mn: Manganese wt%.
        si: Silicon wt% (unused in IIW but kept for API).
        ni: Nickel wt%.
        cr: Chromium wt%.
        mo: Molybdenum wt%.
        v:  Vanadium wt%.

    Returns:
        Carbon equivalent value.
    """
    _ = si  # IIW formula doesn't include Si directly
    return c + mn / 6.0 + (cr + mo + v) / 5.0 + ni / 15.0


# ── jominy_distance_to_hardness ──────────────────────────────────────────────


def jominy_distance_to_hardness(
    h0: Float64, decay_rate: Float64, distance: Float64,
) -> Float64:
    """Jominy end-quench hardness decay: H = h0 * exp(-decay * d).

    Args:
        h0:         Initial hardness at quenched end (HRC).
        decay_rate: Decay constant (1/mm).
        distance:   Distance from quenched end (mm).

    Returns:
        Hardness at given distance (HRC).
    """
    return h0 * exp(-decay_rate * distance)


# ── avrami_fraction ──────────────────────────────────────────────────────────


def avrami_fraction(k: Float64, n: Float64, t: Float64) -> Float64:
    """Avrami (JMAK) phase transformation: f = 1 - exp(-k * t^n).

    Args:
        k: Rate constant.
        n: Avrami exponent.
        t: Time.

    Returns:
        Transformed fraction (0..1).
    """
    if t <= 0.0:
        return 0.0
    return 1.0 - exp(-k * exp(n * log(t)))


# ── quench_severity ──────────────────────────────────────────────────────────


def quench_severity(h: Float64, diameter: Float64) -> Float64:
    """Grossmann ideal diameter: ideal_dia = H * diameter.

    Args:
        h:        Grossmann quench severity factor.
        diameter: Bar diameter (mm).

    Returns:
        Ideal critical diameter (mm).
    """
    return h * diameter


# ── tempering_parameter ──────────────────────────────────────────────────────


def tempering_parameter(
    temperature_k: Float64, time_hours: Float64, c: Float64,
) -> Float64:
    """Hollomon-Jaffe tempering parameter: P = T * (C + log10(t)).

    log10(t) = ln(t) / ln(10).

    Args:
        temperature_k: Tempering temperature (K).
        time_hours:    Tempering time (hours).
        c:             Material constant (typically ~20).

    Returns:
        Tempering parameter P.
    """
    if time_hours <= 0.0:
        return 0.0
    var log10_t = log(time_hours) / log(10.0)
    return temperature_k * (c + log10_t)


# ── density_of_alloy_rule_of_mixtures ────────────────────────────────────────


def density_of_alloy_rule_of_mixtures(
    f1: Float64, d1: Float64, f2: Float64, d2: Float64,
) -> Float64:
    """Rule of mixtures for alloy density: ρ = f1*d1 + f2*d2.

    Args:
        f1: Volume fraction of phase 1.
        d1: Density of phase 1 (kg/m³).
        f2: Volume fraction of phase 2.
        d2: Density of phase 2 (kg/m³).

    Returns:
        Alloy density (kg/m³).
    """
    return f1 * d1 + f2 * d2


# ── thermal_conductivity_wiedemann_franz ─────────────────────────────────────


def thermal_conductivity_wiedemann_franz(
    electrical_cond: Float64, temperature: Float64, lorenz: Float64,
) -> Float64:
    """Wiedemann-Franz law: k = L * σ * T.

    Args:
        electrical_cond: Electrical conductivity σ (S/m).
        temperature:     Temperature T (K).
        lorenz:          Lorenz number L (W·Ω/K²).

    Returns:
        Thermal conductivity k (W/(m·K)).
    """
    return lorenz * electrical_cond * temperature


# ── strain_hardening_exponent_from_points ────────────────────────────────────


def strain_hardening_exponent_from_points(
    stress1: Float64, strain1: Float64,
    stress2: Float64, strain2: Float64,
) -> Float64:
    """Strain hardening exponent from two stress-strain points.

    n = ln(σ2/σ1) / ln(ε2/ε1).

    Args:
        stress1: First true stress.
        strain1: First true strain.
        stress2: Second true stress.
        strain2: Second true strain.

    Returns:
        Strain hardening exponent n.
    """
    if stress1 <= 0.0 or stress2 <= 0.0 or strain1 <= 0.0 or strain2 <= 0.0:
        return 0.0
    var denom = log(strain2 / strain1)
    if fabs(denom) < 1e-30:
        return 0.0
    return log(stress2 / stress1) / denom


# ── fatigue_life_basquin ─────────────────────────────────────────────────────


def fatigue_life_basquin(
    sigma_f: Float64, sigma_a: Float64, b: Float64,
) -> Float64:
    """Basquin fatigue life: Nf = (σ_a / σ_f)^(1/b).

    Args:
        sigma_f: Fatigue strength coefficient (MPa).
        sigma_a: Stress amplitude (MPa).
        b:       Basquin exponent (negative).

    Returns:
        Number of cycles to failure Nf.
    """
    if fabs(sigma_f) < 1e-30 or fabs(b) < 1e-30:
        return 0.0
    var ratio = sigma_a / sigma_f
    if ratio <= 0.0:
        return 0.0
    return exp((1.0 / b) * log(ratio))
