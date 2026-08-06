"""
atmospheric_chemistry.mojo — Atmospheric gas and photochemistry calculations. Zero Python imports.

Public API:
  ozone_column_dobson          — Dobson units from column density
  photolysis_rate              — j from cross-section and quantum yield
  hydroxyl_steady_state        — [OH]ss from production and loss
  aerosol_optical_depth        — AOD from extinction and path
  mixing_ratio_to_conc         — mol/m³ from ppm and conditions
  residence_time               — tau = column / source_rate
  smog_formation_index         — NOx·VOC interaction index
  acid_rain_ph                 — pH from SO2 and NOx deposition
  greenhouse_forcing           — simplified CO2 radiative forcing
  lifetime_from_oh             — tau = 1/(k_OH * [OH])
"""
from std.math import log, exp, sqrt


def _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


def ozone_column_dobson(
    column_density_mol_m2: Float64
) -> Float64:
    """Convert ozone column to Dobson units.

    1 DU = 2.687e20 molecules/m²

    Args:
        column_density_mol_m2: Column density (mol/m²).

    Returns:
        Ozone column (Dobson units).
    """
    var avogadro = 6.022e23
    var molecules_per_m2 = column_density_mol_m2 * avogadro
    return molecules_per_m2 / 2.687e20


def photolysis_rate(
    actinic_flux: Float64, cross_section: Float64, quantum_yield: Float64
) -> Float64:
    """Photolysis rate coefficient: j = F·σ·Φ.

    Args:
        actinic_flux: Actinic flux F (photons/cm²/s/nm, integrated over bandwidth).
        cross_section: Absorption cross-section σ (cm²/molecule).
        quantum_yield: Quantum yield Φ (molecules/photon, 0–1).

    Returns:
        Photolysis rate j (s⁻¹).
    """
    return actinic_flux * cross_section * quantum_yield


def hydroxyl_steady_state(
    oh_production: Float64, loss_rate_constant: Float64, substrate_conc: Float64
) -> Float64:
    """Steady-state OH concentration.

    [OH]ss = P(OH) / (k_loss · [X])

    Args:
        oh_production: OH production rate (molecules/cm³/s).
        loss_rate_constant: OH loss rate constant (cm³/molecule/s).
        substrate_conc: Reacting species concentration (molecules/cm³).

    Returns:
        [OH]ss (molecules/cm³).
    """
    var denom = loss_rate_constant * substrate_conc
    if denom <= 0.0:
        return 0.0
    return oh_production / denom


def aerosol_optical_depth(
    extinction_coefficient: Float64, path_length: Float64
) -> Float64:
    """Aerosol optical depth: AOD = β_ext · L.

    Args:
        extinction_coefficient: Extinction coefficient β (km⁻¹).
        path_length: Vertical or slant path length (km).

    Returns:
        Aerosol optical depth (dimensionless).
    """
    return extinction_coefficient * path_length


def mixing_ratio_to_conc(
    mixing_ratio_ppm: Float64, temperature_k: Float64, pressure_pa: Float64
) -> Float64:
    """Convert volume mixing ratio to number concentration.

    n = χ · P / (k_B · T)

    Args:
        mixing_ratio_ppm: Volume mixing ratio (ppm = 10⁻⁶).
        temperature_k: Temperature (K).
        pressure_pa: Pressure (Pa).

    Returns:
        Number concentration (molecules/m³).
    """
    var chi = mixing_ratio_ppm * 1e-6
    var kB = 1.380649e-23
    if temperature_k <= 0.0:
        return 0.0
    return chi * pressure_pa / (kB * temperature_k)


def residence_time(column_amount: Float64, source_rate: Float64) -> Float64:
    """Atmospheric residence time: τ = column / source rate.

    Args:
        column_amount: Total atmospheric burden (kg or Tg).
        source_rate: Source rate (kg/yr or Tg/yr).

    Returns:
        Residence time (years).
    """
    if source_rate <= 0.0:
        return 0.0
    return column_amount / source_rate


def smog_formation_index(
    nox_ppb: Float64, voc_ppb: Float64
) -> Float64:
    """Simple smog formation potential index.

    SFI = NOx × VOC (indicator, not mechanistic)

    Args:
        nox_ppb: NOx concentration (ppb).
        voc_ppb: Volatile organic compound concentration (ppb).

    Returns:
        Smog formation index (ppb²).
    """
    return nox_ppb * voc_ppb


def acid_rain_ph(
    so2_deposition: Float64, nox_deposition: Float64
) -> Float64:
    """Approximate pH of precipitation from acid deposition.

    pH ≈ 5.6 - log10((SO2 + NOx) / 100)  simplified

    Args:
        so2_deposition: SO2 wet deposition (mg/L as SO4²⁻ equivalents).
        nox_deposition: NOx wet deposition (mg/L as NO3⁻ equivalents).

    Returns:
        Approximate precipitation pH.
    """
    var total = so2_deposition + nox_deposition
    if total <= 0.0:
        return 5.6  # clean rain
    return 5.6 - _log10(1.0 + total / 100.0)


def greenhouse_forcing(co2_ppm: Float64, co2_ref_ppm: Float64) -> Float64:
    """Simplified CO2 radiative forcing: ΔF = 5.35·ln(C/C0).

    Args:
        co2_ppm: Current CO2 concentration (ppm).
        co2_ref_ppm: Pre-industrial reference (typically 280 ppm).

    Returns:
        Radiative forcing ΔF (W/m²).
    """
    if co2_ref_ppm <= 0.0 or co2_ppm <= 0.0:
        return 0.0
    return 5.35 * log(co2_ppm / co2_ref_ppm)


def lifetime_from_oh(
    rate_constant_oh: Float64, oh_concentration: Float64
) -> Float64:
    """Atmospheric lifetime from OH reaction: τ = 1/(k_OH·[OH]).

    Args:
        rate_constant_oh: OH rate constant k_OH (cm³/molecule/s).
        oh_concentration: Annual mean [OH] (molecules/cm³, ~1e6).

    Returns:
        Atmospheric lifetime (s).
    """
    var loss_rate = rate_constant_oh * oh_concentration
    if loss_rate <= 0.0:
        return 0.0
    return 1.0 / loss_rate
