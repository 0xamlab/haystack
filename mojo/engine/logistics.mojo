"""
logistics.mojo — Logistics and supply-chain operations metrics.

Public API:
  vehicle_utilization      — U = loaded/total * 100
  order_fill_rate          — FR = filled/total * 100
  perfect_order_rate       — POR = perfect/total * 100
  inventory_turns          — IT = COGS / AvgInv
  days_of_supply           — DOS = inv / demand
  warehouse_utilization    — WU = used/total * 100
  cost_per_unit_shipped    — CPU = cost / units
  on_time_delivery_rate    — OTD = ontime/total * 100
  dwell_time               — DT = departure - arrival (hours)
  cross_dock_throughput    — TPH = items / hours
  route_efficiency         — RE = optimal/actual * 100
  carbon_per_tonne_km      — C = CO2 / (tonnes * km)
"""


# ── vehicle_utilization ──────────────────────────────────────────────────────


fn vehicle_utilization(loaded_km: Float64, total_km: Float64) -> Float64:
    """Vehicle utilization %: loaded / total * 100."""
    return (loaded_km / total_km) * 100.0


# ── order_fill_rate ──────────────────────────────────────────────────────────


fn order_fill_rate(filled_orders: Float64, total_orders: Float64) -> Float64:
    """Order fill rate %: filled / total * 100."""
    return (filled_orders / total_orders) * 100.0


# ── perfect_order_rate ───────────────────────────────────────────────────────


fn perfect_order_rate(perfect: Float64, total: Float64) -> Float64:
    """Perfect order rate %: perfect / total * 100."""
    return (perfect / total) * 100.0


# ── inventory_turns ──────────────────────────────────────────────────────────


fn inventory_turns(cogs: Float64, avg_inventory: Float64) -> Float64:
    """Inventory turnover: COGS / average inventory."""
    return cogs / avg_inventory


# ── days_of_supply ───────────────────────────────────────────────────────────


fn days_of_supply(avg_inventory: Float64, daily_demand: Float64) -> Float64:
    """Days of supply: inventory / daily demand."""
    return avg_inventory / daily_demand


# ── warehouse_utilization ────────────────────────────────────────────────────


fn warehouse_utilization(used_space: Float64, total_space: Float64) -> Float64:
    """Warehouse utilization %: used / total * 100."""
    return (used_space / total_space) * 100.0


# ── cost_per_unit_shipped ────────────────────────────────────────────────────


fn cost_per_unit_shipped(total_cost: Float64, units_shipped: Float64) -> Float64:
    """Cost per unit shipped: total cost / units."""
    return total_cost / units_shipped


# ── on_time_delivery_rate ────────────────────────────────────────────────────


fn on_time_delivery_rate(on_time: Float64, total_deliveries: Float64) -> Float64:
    """On-time delivery rate %: on-time / total * 100."""
    return (on_time / total_deliveries) * 100.0


# ── dwell_time ───────────────────────────────────────────────────────────────


fn dwell_time(arrival_time: Float64, departure_time: Float64) -> Float64:
    """Dwell time in hours: departure - arrival."""
    return departure_time - arrival_time


# ── cross_dock_throughput ────────────────────────────────────────────────────


fn cross_dock_throughput(items_processed: Float64, hours: Float64) -> Float64:
    """Cross-dock throughput: items / hours."""
    return items_processed / hours


# ── route_efficiency ─────────────────────────────────────────────────────────


fn route_efficiency(actual_distance: Float64, optimal_distance: Float64) -> Float64:
    """Route efficiency %: optimal / actual * 100."""
    return (optimal_distance / actual_distance) * 100.0


# ── carbon_per_tonne_km ─────────────────────────────────────────────────────


fn carbon_per_tonne_km(
    total_co2_kg: Float64, tonnes: Float64, km: Float64
) -> Float64:
    """Carbon intensity: CO2 / (tonnes * km)."""
    return total_co2_kg / (tonnes * km)
