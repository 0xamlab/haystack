"""
radiometry.mojo — Electromagnetic radiation measurement calculations. Zero Python imports.

Public API:
  planck_spectral_radiance     — B_ν from Planck's law
  stefan_boltzmann_radiance    — total emittance M = ε·σ·T⁴
  photon_energy                — E = h·c/λ
  photon_flux                  — N = P/(h·ν)
  solid_angle_cone             — Ω = 2π·(1-cos(θ))
  lambertian_irradiance        — E = L·cos(θ)·π
  radiant_exitance_blackbody   — M = σ·T⁴
  luminous_efficacy            — lm/W from luminous flux
  absorptance_from_reflectance — A = 1 - R - T
  noise_equivalent_power       — NEP = noise_voltage / responsivity
"""
from std.math import exp, cos, log, sqrt, pow


fn planck_spectral_radiance(wavelength_um: Float64, temperature: Float64) -> Float64:
    """Spectral radiance from Planck's blackbody law.

    B_λ = (2hc²/λ⁵) / (exp(hc/λkT) - 1)  → simplified form.

    Args:
        wavelength_um: Wavelength (μm).
        temperature: Temperature (K).

    Returns:
        Spectral radiance (W/sr/m²/μm, simplified scale).
    """
    if wavelength_um <= 0.0 or temperature <= 0.0:
        return 0.0
    var c1 = 3.7418e8   # 2hc² in W·μm⁴/m²
    var c2 = 14388.0    # hc/k in μm·K
    var exponent = c2 / (wavelength_um * temperature)
    if exponent > 700.0:
        return 0.0
    var denom = exp(exponent) - 1.0
    if denom <= 0.0:
        return 0.0
    return c1 / (pow(wavelength_um, 5.0) * denom)


fn stefan_boltzmann_radiance(emissivity: Float64, temperature: Float64) -> Float64:
    """Total emittance from Stefan-Boltzmann law: M = ε·σ·T⁴.

    Args:
        emissivity: Surface emissivity (0–1).
        temperature: Surface temperature (K).

    Returns:
        Total emittance (W/m²).
    """
    if temperature < 0.0:
        return 0.0
    var sigma = 5.6704e-8  # W/(m²·K⁴)
    return emissivity * sigma * pow(temperature, 4.0)


fn photon_energy(wavelength_nm: Float64) -> Float64:
    """Photon energy: E = hc/λ.

    Args:
        wavelength_nm: Wavelength (nm).

    Returns:
        Photon energy (eV).
    """
    if wavelength_nm <= 0.0:
        return 0.0
    var h = 6.626e-34   # J·s
    var c = 2.998e8     # m/s
    var lambda_m = wavelength_nm * 1e-9
    var e_joules = h * c / lambda_m
    return e_joules / 1.602e-19  # to eV


fn photon_flux(power_w: Float64, wavelength_nm: Float64) -> Float64:
    """Photon flux: N = P/E_photon.

    Args:
        power_w: Optical power (W).
        wavelength_nm: Wavelength (nm).

    Returns:
        Photon flux (photons/s).
    """
    if wavelength_nm <= 0.0:
        return 0.0
    var h = 6.626e-34
    var c = 2.998e8
    var lambda_m = wavelength_nm * 1e-9
    var e_photon = h * c / lambda_m
    if e_photon <= 0.0:
        return 0.0
    return power_w / e_photon


fn solid_angle_cone(half_angle_rad: Float64) -> Float64:
    """Solid angle of a cone: Ω = 2π·(1 - cos(θ)).

    Args:
        half_angle_rad: Half-angle of the cone (rad).

    Returns:
        Solid angle (sr).
    """
    var pi = 3.141592653589793
    return 2.0 * pi * (1.0 - cos(half_angle_rad))


fn lambertian_irradiance(radiance: Float64, angle_rad: Float64) -> Float64:
    """Irradiance on a surface from a Lambertian source.

    E = L·cos(θ)·π  (if integrating over hemisphere)

    Args:
        radiance: Source radiance (W/sr/m²).
        angle_rad: Angle of incidence (rad).

    Returns:
        Irradiance (W/m²).
    """
    var pi = 3.141592653589793
    return radiance * cos(angle_rad) * pi


fn radiant_exitance_blackbody(temperature: Float64) -> Float64:
    """Total radiant exitance of a blackbody: M = σ·T⁴.

    Args:
        temperature: Temperature (K).

    Returns:
        Exitance (W/m²).
    """
    var sigma = 5.6704e-8
    return sigma * pow(temperature, 4.0)


fn luminous_efficacy(luminous_flux_lm: Float64, power_w: Float64) -> Float64:
    """Luminous efficacy of a light source.

    η = Φ_v / P  (lm/W)

    Args:
        luminous_flux_lm: Luminous flux (lm).
        power_w: Electrical power consumed (W).

    Returns:
        Luminous efficacy (lm/W).
    """
    if power_w <= 0.0:
        return 0.0
    return luminous_flux_lm / power_w


fn absorptance_from_reflectance(
    reflectance: Float64, transmittance: Float64
) -> Float64:
    """Absorptance from energy balance: A = 1 - R - T.

    Args:
        reflectance: Reflectance (0–1).
        transmittance: Transmittance (0–1).

    Returns:
        Absorptance (0–1).
    """
    var a = 1.0 - reflectance - transmittance
    if a < 0.0:
        return 0.0
    return a


fn noise_equivalent_power(
    noise_voltage_vrms: Float64, responsivity_v_per_w: Float64
) -> Float64:
    """Noise equivalent power of a detector.

    NEP = V_noise / R  (W/√Hz)

    Args:
        noise_voltage_vrms: RMS noise voltage (V/√Hz).
        responsivity_v_per_w: Detector responsivity (V/W).

    Returns:
        NEP (W/√Hz).
    """
    if responsivity_v_per_w <= 0.0:
        return 0.0
    return noise_voltage_vrms / responsivity_v_per_w
