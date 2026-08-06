"""Semiconductor Physics Library — Wave 95."""

from std.math import sqrt, log, exp, abs


def intrinsic_carrier_concentration(ni0: Float64, eg: Float64, k: Float64, t: Float64) -> Float64:
    """ni = ni0 * exp(-Eg/(2kT))."""
    return ni0 * exp(-eg / (2.0 * k * t))


def drift_velocity(mobility: Float64, electric_field: Float64) -> Float64:
    """vd = μ*E."""
    return mobility * electric_field


def resistivity(n: Float64, q: Float64, mobility: Float64) -> Float64:
    """ρ = 1/(n*q*μ)."""
    return 1.0 / (n * q * mobility)


def conductivity(n: Float64, q: Float64, mobility: Float64) -> Float64:
    """σ = n*q*μ."""
    return n * q * mobility


def depletion_width(epsilon: Float64, vbi: Float64, na: Float64, nd: Float64, q: Float64) -> Float64:
    """W = sqrt(2*ε*Vbi*(Na+Nd)/(q*Na*Nd))."""
    return sqrt(2.0 * epsilon * vbi * (na + nd) / (q * na * nd))


def built_in_potential(vt: Float64, na: Float64, nd: Float64, ni: Float64) -> Float64:
    """Vbi = Vt * ln(Na*Nd/ni²)."""
    return vt * log(na * nd / (ni * ni))


def thermal_voltage(k: Float64, t: Float64, q: Float64) -> Float64:
    """Vt = kT/q."""
    return k * t / q


def diode_current(is_val: Float64, v: Float64, vt: Float64, n: Float64) -> Float64:
    """I = Is*(exp(V/(n*Vt))-1)."""
    return is_val * (exp(v / (n * vt)) - 1.0)


def mosfet_saturation_current(kn: Float64, vgs: Float64, vth: Float64) -> Float64:
    """Id = 0.5*Kn*(Vgs-Vth)²."""
    var diff = vgs - vth
    return 0.5 * kn * diff * diff


def junction_capacitance(cj0: Float64, v: Float64, vbi: Float64, m: Float64) -> Float64:
    """Cj = Cj0/(1-V/Vbi)^m."""
    # Zero vbi divides, base <= 0 makes log(base) -inf/NaN, and exp underflow
    # would zero the denominator; inf/nan cannot cross the result wire.
    if vbi == 0.0:
        return 0.0
    var base = 1.0 - v / vbi
    if base <= 0.0:
        return 0.0
    # Compute base^m = exp(m*ln(base))
    var denom = exp(m * log(base))
    if denom == 0.0:
        return 0.0
    return cj0 / denom


def diffusion_length(diffusivity: Float64, lifetime: Float64) -> Float64:
    """L = sqrt(D*τ)."""
    return sqrt(diffusivity * lifetime)


def band_gap_temperature(eg0: Float64, alpha: Float64, beta: Float64, t: Float64) -> Float64:
    """Eg(T) = Eg0 - α*T²/(T+β)."""
    return eg0 - alpha * t * t / (t + beta)
