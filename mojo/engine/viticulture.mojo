"""Viticulture (Grape Growing & Wine) Library — Wave 95."""

from std.math import sqrt, log, exp, abs


fn brix_to_potential_alcohol(brix: Float64) -> Float64:
    """ABV ≈ brix * 0.55."""
    return brix * 0.55


fn chaptalization_sugar(target_brix: Float64, current_brix: Float64, volume_l: Float64) -> Float64:
    """Sugar_g = (target - current) * volume * 1.7."""
    return (target_brix - current_brix) * volume_l * 1.7


fn total_acidity_as_tartaric(ta_g_per_l: Float64) -> Float64:
    """Returns value in g/L tartaric equivalent."""
    return ta_g_per_l


fn ph_buffer_capacity(ta: Float64, ph: Float64) -> Float64:
    """BC ≈ ta * 0.3 / (pH - 2.5) simplified."""
    return ta * 0.3 / (ph - 2.5)


fn growing_degree_days_wine(t_max: Float64, t_min: Float64, t_base: Float64) -> Float64:
    """GDD = max(0, (Tmax+Tmin)/2 - Tbase)."""
    var avg = (t_max + t_min) / 2.0 - t_base
    if avg < 0.0:
        return 0.0
    return avg


fn winkler_index_daily(gdd: Float64) -> Float64:
    """Returns daily GDD contribution (sum April-October)."""
    return gdd


fn yield_tonnes_per_hectare(kg_total: Float64, area_ha: Float64) -> Float64:
    """Y = kg / (1000 * ha)."""
    return kg_total / (1000.0 * area_ha)


fn vine_density(vines_per_row: Float64, rows: Float64, area_ha: Float64) -> Float64:
    """D = vines * rows / area (vines/ha)."""
    return vines_per_row * rows / area_ha


fn pruning_weight_ratio(crop_weight: Float64, pruning_weight: Float64) -> Float64:
    """Ravaz index = crop_weight / pruning_weight."""
    return crop_weight / pruning_weight


fn must_volume_from_grapes(grape_kg: Float64, extraction_rate: Float64) -> Float64:
    """V = kg * rate (L, typical 0.7-0.8)."""
    return grape_kg * extraction_rate


fn sulfite_molecular_so2(free_so2: Float64, ph: Float64) -> Float64:
    """Molecular = free / (1 + 10^(pH - 1.81))."""
    var power = exp((ph - 1.81) * log(10.0))
    return free_so2 / (1.0 + power)


fn fermentation_progress(initial_brix: Float64, current_brix: Float64) -> Float64:
    """Progress = (initial - current) / initial * 100."""
    return (initial_brix - current_brix) / initial_brix * 100.0
