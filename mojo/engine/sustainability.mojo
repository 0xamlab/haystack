"""
sustainability.mojo — Sustainability / ESG Metrics Library. Zero Python imports.

Provides functions for computing environmental, social, and governance (ESG)
metrics including carbon footprint, energy/water intensity, waste diversion,
GHG scopes, carbon offsets, circular economy, and composite ESG scores.

Public API:
  carbon_footprint_transport   — CO2 = dist * factor (kgCO2)
  energy_intensity             — EI = energy/revenue (kWh/$)
  water_intensity              — WI = water/units
  waste_diversion_rate         — WDR = recycled/total * 100
  renewable_energy_fraction    — REF = renewable/total * 100
  ghg_scope1                   — Returns direct (Scope 1 = direct)
  ghg_scope2                   — Scope2 = kWh * factor
  ghg_scope3_estimate          — Scope3 ≈ revenue * factor
  carbon_offset_cost           — Cost = tonnes * price
  circular_economy_index       — CEI = reused/total * 100
  social_return_on_investment  — SROI = value/investment
  esg_composite_score          — ESG = (E*we+S*ws+G*wg)/(we+ws+wg)
"""


# ── public API ───────────────────────────────────────────────────────────────


def carbon_footprint_transport(distance_km: Float64, emission_factor: Float64) -> Float64:
    """CO2 emissions from transport in kgCO2 = distance_km * emission_factor."""
    return distance_km * emission_factor


def energy_intensity(energy_kwh: Float64, revenue: Float64) -> Float64:
    """Energy intensity = energy (kWh) / revenue ($)."""
    if revenue == 0.0:
        return 0.0
    return energy_kwh / revenue


def water_intensity(water_m3: Float64, production_units: Float64) -> Float64:
    """Water intensity = water (m³) / production units."""
    if production_units == 0.0:
        return 0.0
    return water_m3 / production_units


def waste_diversion_rate(recycled: Float64, total_waste: Float64) -> Float64:
    """Waste diversion rate (%) = recycled / total_waste * 100."""
    if total_waste == 0.0:
        return 0.0
    return recycled / total_waste * 100.0


def renewable_energy_fraction(renewable: Float64, total_energy: Float64) -> Float64:
    """Renewable energy fraction (%) = renewable / total_energy * 100."""
    if total_energy == 0.0:
        return 0.0
    return renewable / total_energy * 100.0


def ghg_scope1(direct_emissions: Float64) -> Float64:
    """GHG Scope 1 = direct emissions (pass-through)."""
    return direct_emissions


def ghg_scope2(purchased_energy_kwh: Float64, grid_factor: Float64) -> Float64:
    """GHG Scope 2 = purchased_energy_kwh * grid_factor (kgCO2/kWh)."""
    return purchased_energy_kwh * grid_factor


def ghg_scope3_estimate(revenue: Float64, intensity_factor: Float64) -> Float64:
    """GHG Scope 3 estimate ≈ revenue * intensity_factor."""
    return revenue * intensity_factor


def carbon_offset_cost(tonnes_co2: Float64, price_per_tonne: Float64) -> Float64:
    """Carbon offset cost = tonnes_co2 * price_per_tonne."""
    return tonnes_co2 * price_per_tonne


def circular_economy_index(reused_material: Float64, total_material: Float64) -> Float64:
    """Circular economy index (%) = reused_material / total_material * 100."""
    if total_material == 0.0:
        return 0.0
    return reused_material / total_material * 100.0


def social_return_on_investment(social_value: Float64, investment: Float64) -> Float64:
    """SROI = social_value / investment."""
    if investment == 0.0:
        return 0.0
    return social_value / investment


def esg_composite_score(
    e_score: Float64,
    s_score: Float64,
    g_score: Float64,
    e_weight: Float64,
    s_weight: Float64,
    g_weight: Float64,
) -> Float64:
    """Weighted ESG composite = (E*we + S*ws + G*wg) / (we + ws + wg)."""
    var total_w = e_weight + s_weight + g_weight
    if total_w == 0.0:
        return 0.0
    return (e_score * e_weight + s_score * s_weight + g_score * g_weight) / total_w
