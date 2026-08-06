"""
mining.mojo — Mining Engineering Library. Zero Python imports.

Provides ore grade, economics, comminution, blasting, and ventilation calcs.

Public API:
  ore_grade              — Grade = metal/ore * 100
  strip_ratio            — SR = waste/ore
  recovery_rate          — R = recovered/feed * 100
  mill_throughput         — T = rate * hours
  bond_work_index_energy — E = 10*Wi*(1/√P80 - 1/√F80)
  cut_off_grade          — COG = (MC+PC)/(Price*Recovery)*100
  dilution_factor        — D = waste/(waste+ore)*100
  net_smelter_return     — NSR = Price*Grade/100*Recovery/100 - SC
  reserve_life           — Life = reserve/production
  powder_factor          — PF = explosive/rock
  ventilation_quantity   — Q = n * q
  subsidence_factor      — SF = h/depth
"""
from std.math import sqrt, abs as fabs


# ── ore_grade ────────────────────────────────────────────────────────────────


def ore_grade(metal_mass: Float64, ore_mass: Float64) -> Float64:
    """Ore grade: Grade = (metal/ore) * 100 (%).

    Args:
        metal_mass: Mass of contained metal (tonnes).
        ore_mass: Total ore mass (tonnes).

    Returns:
        Grade (%).
    """
    if fabs(ore_mass) < 1e-30:
        return 0.0
    return metal_mass / ore_mass * 100.0


# ── strip_ratio ──────────────────────────────────────────────────────────────


def strip_ratio(waste_volume: Float64, ore_volume: Float64) -> Float64:
    """Strip ratio: SR = waste / ore.

    Args:
        waste_volume: Volume (or mass) of waste.
        ore_volume: Volume (or mass) of ore.

    Returns:
        Strip ratio (dimensionless).
    """
    if fabs(ore_volume) < 1e-30:
        return 0.0
    return waste_volume / ore_volume


# ── recovery_rate ────────────────────────────────────────────────────────────


def recovery_rate(metal_recovered: Float64, metal_in_feed: Float64) -> Float64:
    """Recovery rate: R = (recovered/feed) * 100 (%).

    Args:
        metal_recovered: Metal recovered (tonnes).
        metal_in_feed: Metal in feed (tonnes).

    Returns:
        Recovery rate (%).
    """
    if fabs(metal_in_feed) < 1e-30:
        return 0.0
    return metal_recovered / metal_in_feed * 100.0


# ── mill_throughput ──────────────────────────────────────────────────────────


def mill_throughput(feed_rate: Float64, hours: Float64) -> Float64:
    """Mill throughput: T = rate * hours (tonnes).

    Args:
        feed_rate: Feed rate (tonnes/hour).
        hours: Operating hours.

    Returns:
        Total throughput (tonnes).
    """
    return feed_rate * hours


# ── bond_work_index_energy ───────────────────────────────────────────────────


def bond_work_index_energy(
    wi: Float64, p80: Float64, f80: Float64
) -> Float64:
    """Bond work index energy: E = 10 * Wi * (1/√P80 - 1/√F80) (kWh/t).

    Args:
        wi: Bond work index (kWh/t).
        p80: 80% passing size of product (μm).
        f80: 80% passing size of feed (μm).

    Returns:
        Specific energy (kWh/t).
    """
    if p80 <= 0.0 or f80 <= 0.0:
        return 0.0
    return 10.0 * wi * (1.0 / sqrt(p80) - 1.0 / sqrt(f80))


# ── cut_off_grade ────────────────────────────────────────────────────────────


def cut_off_grade(
    mining_cost: Float64,
    processing_cost: Float64,
    metal_price: Float64,
    recovery: Float64,
) -> Float64:
    """Cut-off grade: COG = (MC + PC) / (Price * Recovery) * 100 (%).

    Args:
        mining_cost: Mining cost ($/tonne ore).
        processing_cost: Processing cost ($/tonne ore).
        metal_price: Metal price ($/tonne metal).
        recovery: Recovery (0-1).

    Returns:
        Cut-off grade (%).
    """
    var denom = metal_price * recovery
    if fabs(denom) < 1e-30:
        return 0.0
    return (mining_cost + processing_cost) / denom * 100.0


# ── dilution_factor ──────────────────────────────────────────────────────────


def dilution_factor(
    tonnes_waste_in_ore: Float64, tonnes_ore: Float64
) -> Float64:
    """Dilution factor: D = waste / (waste + ore) * 100 (%).

    Args:
        tonnes_waste_in_ore: Tonnes of waste mixed in with ore.
        tonnes_ore: Tonnes of ore.

    Returns:
        Dilution (%).
    """
    var total = tonnes_waste_in_ore + tonnes_ore
    if fabs(total) < 1e-30:
        return 0.0
    return tonnes_waste_in_ore / total * 100.0


# ── net_smelter_return ───────────────────────────────────────────────────────


def net_smelter_return(
    metal_price: Float64,
    grade: Float64,
    recovery: Float64,
    smelting_cost: Float64,
) -> Float64:
    """Net smelter return: NSR = Price * Grade/100 * Recovery/100 - SC ($/t ore).

    Args:
        metal_price: Metal price ($/tonne metal).
        grade: Ore grade (%).
        recovery: Recovery (%).
        smelting_cost: Smelting/refining cost ($/tonne ore).

    Returns:
        NSR ($/tonne ore).
    """
    return metal_price * grade / 100.0 * recovery / 100.0 - smelting_cost


# ── reserve_life ─────────────────────────────────────────────────────────────


def reserve_life(
    tonnes_reserve: Float64, annual_production: Float64
) -> Float64:
    """Reserve life: Life = reserve / production (years).

    Args:
        tonnes_reserve: Total reserve (tonnes).
        annual_production: Annual production (tonnes/year).

    Returns:
        Reserve life (years).
    """
    if fabs(annual_production) < 1e-30:
        return 0.0
    return tonnes_reserve / annual_production


# ── powder_factor ────────────────────────────────────────────────────────────


def powder_factor(
    explosive_kg: Float64, rock_tonnes: Float64
) -> Float64:
    """Powder factor: PF = explosive / rock (kg/t).

    Args:
        explosive_kg: Explosives used (kg).
        rock_tonnes: Rock blasted (tonnes).

    Returns:
        Powder factor (kg/t).
    """
    if fabs(rock_tonnes) < 1e-30:
        return 0.0
    return explosive_kg / rock_tonnes


# ── ventilation_quantity ─────────────────────────────────────────────────────


def ventilation_quantity(
    workers: Float64, airflow_per_worker: Float64
) -> Float64:
    """Ventilation quantity: Q = n * q (m³/s).

    Args:
        workers: Number of workers.
        airflow_per_worker: Required airflow per worker (m³/s).

    Returns:
        Total ventilation quantity (m³/s).
    """
    return workers * airflow_per_worker


# ── subsidence_factor ────────────────────────────────────────────────────────


def subsidence_factor(
    extraction_height: Float64, depth: Float64
) -> Float64:
    """Subsidence factor: SF = extraction_height / depth.

    Args:
        extraction_height: Extraction height (m).
        depth: Depth of mining (m).

    Returns:
        Subsidence factor (dimensionless).
    """
    if fabs(depth) < 1e-30:
        return 0.0
    return extraction_height / depth
