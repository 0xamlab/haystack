"""
pedology.mojo — Soil formation and classification science calculations. Zero Python imports.

Public API:
  soil_development_index        — weathering and pedogenesis index
  clay_illuviation_ratio        — Bt/E horizon clay ratio
  rubification_index            — redness from hue/chroma
  organic_horizon_depth         — O horizon estimate from litter
  base_saturation_percent       — exchangeable cations fraction
  solum_thickness_estimate      — from climate and age
  profile_development_index     — PDI from horizon properties
  biological_weathering_index   — lichen/root contribution
  translocation_coefficient     — element mobility in profile
  soil_age_from_pedogenesis     — inverse weathering estimate
"""
from std.math import log, exp, sqrt, pow


def soil_development_index(
    clay_content: Float64, base_saturation: Float64, organic_matter: Float64
) -> Float64:
    """Composite soil development index.

    SDI = (clay × BS × OM)^(1/3)

    Args:
        clay_content: Clay fraction (% by mass, 0–100).
        base_saturation: Base saturation (%, 0–100).
        organic_matter: Organic matter content (%, 0–20).

    Returns:
        SDI (geometric mean; higher = more developed soil).
    """
    var product = clay_content * base_saturation * organic_matter
    if product <= 0.0:
        return 0.0
    return pow(product, 1.0 / 3.0)


def clay_illuviation_ratio(
    bt_clay_pct: Float64, eluvial_clay_pct: Float64
) -> Float64:
    """Clay illuviation ratio Bt/E horizon.

    ratio = clay_Bt / clay_E

    Args:
        bt_clay_pct: Clay in Bt (argillic) horizon (%).
        eluvial_clay_pct: Clay in E (eluvial) horizon (%).

    Returns:
        Illuviation ratio (>1.2 = significant clay accumulation).
    """
    if eluvial_clay_pct <= 0.0:
        return 0.0
    return bt_clay_pct / eluvial_clay_pct


def rubification_index(
    munsell_hue_number: Float64, chroma: Float64, value: Float64
) -> Float64:
    """Redness rating from Munsell colour components.

    RR = (hue_num × chroma) / value  (Torrent et al.)

    Args:
        munsell_hue_number: Numerical hue code (2.5R=2.5, 5R=5, 10R=10, 2.5YR=12.5...).
        chroma: Munsell chroma.
        value: Munsell value.

    Returns:
        Redness rating (higher = redder = more oxidised iron).
    """
    if value <= 0.0:
        return 0.0
    return (10.0 - munsell_hue_number) * chroma / value


def organic_horizon_depth(
    litter_input_g_m2_yr: Float64, decomposition_rate: Float64
) -> Float64:
    """O-horizon depth from steady-state litter balance.

    depth ≈ (input / k) / bulk_density (assume BD = 100 g/m²/cm)

    Args:
        litter_input_g_m2_yr: Annual litter production (g/m²/yr).
        decomposition_rate: First-order k (yr⁻¹).

    Returns:
        Steady-state O-horizon depth (cm).
    """
    if decomposition_rate <= 0.0:
        return 0.0
    var mass = litter_input_g_m2_yr / decomposition_rate
    return mass / 100.0  # assume 100 g/m² per cm


def base_saturation_percent(
    sum_bases_cmol_kg: Float64, cec_cmol_kg: Float64
) -> Float64:
    """Base saturation as % of CEC.

    BS% = (Ca + Mg + K + Na) / CEC × 100

    Args:
        sum_bases_cmol_kg: Sum of exchangeable bases (cmol+/kg).
        cec_cmol_kg: Cation exchange capacity (cmol+/kg).

    Returns:
        Base saturation (%; <35% = Ultisol, >50% = Mollisol criterion).
    """
    if cec_cmol_kg <= 0.0:
        return 0.0
    return sum_bases_cmol_kg / cec_cmol_kg * 100.0


def solum_thickness_estimate(
    precipitation_mm_yr: Float64, temperature_c: Float64, age_kyr: Float64
) -> Float64:
    """Approximate solum thickness from Jenny (1941) climate-age model.

    T = a × (P/T) × log(age+1)

    Args:
        precipitation_mm_yr: Mean annual precipitation (mm/yr).
        temperature_c: Mean annual temperature (°C, must be >0).
        age_kyr: Soil age (ka).

    Returns:
        Estimated solum thickness (cm).
    """
    if temperature_c <= 0.0:
        return 0.0
    return 0.8 * (precipitation_mm_yr / temperature_c) * log(age_kyr + 1.0)


def profile_development_index(
    clay_increase: Float64, structure_grade: Float64,
    horizon_thickness_cm: Float64
) -> Float64:
    """Profile Development Index (Birkeland type).

    PDI = clay_increase × structure_grade × thickness

    Args:
        clay_increase: Clay% in Bt minus parent material (%).
        structure_grade: Soil structure grade (0–4: massive to strong).
        horizon_thickness_cm: Horizon thickness (cm).

    Returns:
        PDI (higher = more developed profile).
    """
    return clay_increase * structure_grade * horizon_thickness_cm


def biological_weathering_index(
    root_density_km_m3: Float64, lichen_cover_pct: Float64
) -> Float64:
    """Biological contribution to chemical weathering.

    BWI = root_density × lichen_cover / 100

    Args:
        root_density_km_m3: Fine root length density (km/m³).
        lichen_cover_pct: Lichen surface cover (%).

    Returns:
        Biological weathering index.
    """
    return root_density_km_m3 * lichen_cover_pct / 100.0


def translocation_coefficient(
    element_subsoil: Float64, element_topsoil: Float64
) -> Float64:
    """Element translocation coefficient (leaching vs. accumulation).

    Tc = subsoil_conc / topsoil_conc

    Args:
        element_subsoil: Element concentration in subsoil (mg/kg).
        element_topsoil: Element concentration in topsoil (mg/kg).

    Returns:
        Tc (<1 = depleted in subsoil, >1 = accumulated, e.g. Fe in spodosols).
    """
    if element_topsoil <= 0.0:
        return 0.0
    return element_subsoil / element_topsoil


def soil_age_from_pedogenesis(
    observed_pdi: Float64, pdi_rate: Float64
) -> Float64:
    """Estimate soil age from profile development index and accumulation rate.

    age = PDI / PDI_rate

    Args:
        observed_pdi: Measured profile development index.
        pdi_rate: PDI accumulation rate (PDI units per ky).

    Returns:
        Estimated soil age (ky).
    """
    if pdi_rate <= 0.0:
        return 0.0
    return observed_pdi / pdi_rate
