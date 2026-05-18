"""Semiconductor Physics Library — Wave 95."""

from std.math import sqrt, log, exp, abs


fn intrinsic_carrier_concentration(ni0: Float64, eg: Float64, k: Float64, t: Float64) -> Float64:
    """ni = ni0 * exp(-Eg/(2kT))."""
    return ni0 * exp(-eg / (2.0 * k * t))


fn drift_velocity(mobility: Float64, electric_field: Float64) -> Float64:
    """vd = μ*E."""
    return mobility * electric_field


fn resistivity(n: Float64, q: Float64, mobility: Float64) -> Float64:
    """ρ = 1/(n*q*μ)."""
    return 1.0 / (n * q * mobility)


fn conductivity(n: Float64, q: Float64, mobility: Float64) -> Float64:
    """σ = n*q*μ."""
    return n * q * mobility


fn depletion_width(epsilon: Float64, vbi: Float64, na: Float64, nd: Float64, q: Float64) -> Float64:
    """W = sqrt(2*ε*Vbi*(Na+Nd)/(q*Na*Nd))."""
    return sqrt(2.0 * epsilon * vbi * (na + nd) / (q * na * nd))


fn built_in_potential(vt: Float64, na: Float64, nd: Float64, ni: Float64) -> Float64:
    """Vbi = Vt * ln(Na*Nd/ni²)."""
    return vt * log(na * nd / (ni * ni))


fn thermal_voltage(k: Float64, t: Float64, q: Float64) -> Float64:
    """Vt = kT/q."""
    return k * t / q


fn diode_current(is_val: Float64, v: Float64, vt: Float64, n: Float64) -> Float64:
    """I = Is*(exp(V/(n*Vt))-1)."""
    return is_val * (exp(v / (n * vt)) - 1.0)


fn mosfet_saturation_current(kn: Float64, vgs: Float64, vth: Float64) -> Float64:
    """Id = 0.5*Kn*(Vgs-Vth)²."""
    var diff = vgs - vth
    return 0.5 * kn * diff * diff


fn junction_capacitance(cj0: Float64, v: Float64, vbi: Float64, m: Float64) -> Float64:
    """Cj = Cj0/(1-V/Vbi)^m."""
    var base = 1.0 - v / vbi
    # Compute base^m = exp(m*ln(base))
    return cj0 / exp(m * log(base))


fn diffusion_length(diffusivity: Float64, lifetime: Float64) -> Float64:
    """L = sqrt(D*τ)."""
    return sqrt(diffusivity * lifetime)


fn band_gap_temperature(eg0: Float64, alpha: Float64, beta: Float64, t: Float64) -> Float64:
    """Eg(T) = Eg0 - α*T²/(T+β)."""
    return eg0 - alpha * t * t / (t + beta)
