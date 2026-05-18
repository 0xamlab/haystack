"""
aquaculture.mojo — Aquaculture Library.

Provides stocking, feeding, water-quality, and production calculations for
fish/shrimp farming systems.

Public API:
  stocking_density            — SD = biomass / volume (kg/m³)
  feed_conversion_ratio       — FCR = feed / weight_gain
  specific_growth_rate        — SGR = (ln(Wf)-ln(Wi))/days * 100
  dissolved_oxygen_consumption— DO = biomass * rate (mg/hr)
  water_exchange_rate         — ER = flow / volume * 100 (%/hr)
  ammonia_production          — NH3 ≈ feed * protein/100 * 0.03
  carrying_capacity           — CC = DO_avail / DO_per_kg
  harvest_weight              — W = Wi * exp(SGR*days/100)
  survival_rate               — SR = final / initial * 100
  production_per_cycle        — P = Wavg * count * survival/100
  biofilter_capacity          — Cap = area * rate
  cost_per_kg_produced        — Cost = total / production
"""
from std.math import log, exp


# ── stocking_density ─────────────────────────────────────────────────────────


fn stocking_density(biomass_kg: Float64, volume_m3: Float64) -> Float64:
    """Stocking density: SD = biomass / volume (kg/m³).

    Args:
        biomass_kg: Total biomass in tank (kg).
        volume_m3: Tank volume (m³).

    Returns:
        Stocking density (kg/m³).
    """
    return biomass_kg / volume_m3


# ── feed_conversion_ratio ───────────────────────────────────────────────────


fn feed_conversion_ratio(feed_kg: Float64, weight_gain_kg: Float64) -> Float64:
    """Feed conversion ratio: FCR = feed / weight_gain.

    Args:
        feed_kg: Total feed consumed (kg).
        weight_gain_kg: Total weight gain (kg).

    Returns:
        FCR (dimensionless, lower is better).
    """
    return feed_kg / weight_gain_kg


# ── specific_growth_rate ─────────────────────────────────────────────────────


fn specific_growth_rate(w_final: Float64, w_initial: Float64, days: Float64) -> Float64:
    """Specific growth rate: SGR = (ln(Wf) - ln(Wi)) / days * 100 (%/day).

    Args:
        w_final: Final body weight (g or kg).
        w_initial: Initial body weight (same unit).
        days: Duration in days.

    Returns:
        SGR (%/day).
    """
    return (log(w_final) - log(w_initial)) / days * 100.0


# ── dissolved_oxygen_consumption ─────────────────────────────────────────────


fn dissolved_oxygen_consumption(biomass_kg: Float64, rate_per_kg: Float64) -> Float64:
    """Dissolved oxygen consumption: DO = biomass * rate (mg/hr).

    Args:
        biomass_kg: Total biomass (kg).
        rate_per_kg: Oxygen consumption rate per kg (mg O₂/kg/hr).

    Returns:
        Total DO consumption (mg/hr).
    """
    return biomass_kg * rate_per_kg


# ── water_exchange_rate ──────────────────────────────────────────────────────


fn water_exchange_rate(flow_rate: Float64, tank_volume: Float64) -> Float64:
    """Water exchange rate: ER = flow / volume * 100 (%/hr).

    Args:
        flow_rate: Inflow rate (m³/hr).
        tank_volume: Tank volume (m³).

    Returns:
        Exchange rate (%/hr).
    """
    return flow_rate / tank_volume * 100.0


# ── ammonia_production ───────────────────────────────────────────────────────


fn ammonia_production(feed_rate: Float64, protein_pct: Float64) -> Float64:
    """Ammonia production estimate: NH3 ≈ feed * protein/100 * 0.03.

    Args:
        feed_rate: Feed rate (kg/day).
        protein_pct: Feed protein content (%).

    Returns:
        Estimated ammonia production (kg/day).
    """
    return feed_rate * protein_pct / 100.0 * 0.03


# ── carrying_capacity ────────────────────────────────────────────────────────


fn carrying_capacity(do_available: Float64, do_per_kg: Float64) -> Float64:
    """Carrying capacity: CC = DO_available / DO_per_kg (kg).

    Args:
        do_available: Available dissolved oxygen supply (mg/hr).
        do_per_kg: Oxygen demand per kg biomass (mg/kg/hr).

    Returns:
        Maximum sustainable biomass (kg).
    """
    return do_available / do_per_kg


# ── harvest_weight ───────────────────────────────────────────────────────────


fn harvest_weight(initial_weight: Float64, sgr: Float64, days: Float64) -> Float64:
    """Projected harvest weight: W = Wi * exp(SGR * days / 100).

    Args:
        initial_weight: Starting weight (g or kg).
        sgr: Specific growth rate (%/day).
        days: Growth period (days).

    Returns:
        Projected final weight (same unit as initial).
    """
    return initial_weight * exp(sgr * days / 100.0)


# ── survival_rate ────────────────────────────────────────────────────────────


fn survival_rate(final_count: Float64, initial_count: Float64) -> Float64:
    """Survival rate: SR = final / initial * 100 (%).

    Args:
        final_count: Number of individuals at harvest.
        initial_count: Number of individuals at stocking.

    Returns:
        Survival rate (%).
    """
    return final_count / initial_count * 100.0


# ── production_per_cycle ─────────────────────────────────────────────────────


fn production_per_cycle(harvest_weight_avg: Float64, count: Float64, survival: Float64) -> Float64:
    """Production per cycle: P = Wavg * count * survival / 100 (kg).

    Args:
        harvest_weight_avg: Average harvest weight (kg).
        count: Number stocked.
        survival: Survival rate (%).

    Returns:
        Total production (kg).
    """
    return harvest_weight_avg * count * survival / 100.0


# ── biofilter_capacity ───────────────────────────────────────────────────────


fn biofilter_capacity(surface_area: Float64, nitrification_rate: Float64) -> Float64:
    """Biofilter capacity: Cap = surface_area * nitrification_rate.

    Args:
        surface_area: Media surface area (m²).
        nitrification_rate: Nitrification rate (g TAN/m²/day).

    Returns:
        Ammonia removal capacity (g TAN/day).
    """
    return surface_area * nitrification_rate


# ── cost_per_kg_produced ─────────────────────────────────────────────────────


fn cost_per_kg_produced(total_cost: Float64, production_kg: Float64) -> Float64:
    """Cost per kg produced: Cost = total / production.

    Args:
        total_cost: Total production cost ($).
        production_kg: Total production (kg).

    Returns:
        Unit cost ($/kg).
    """
    return total_cost / production_kg
