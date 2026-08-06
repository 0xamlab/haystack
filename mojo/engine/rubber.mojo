"""
rubber.mojo — Rubber / Elastomer Technology Library. Zero Python imports.

Provides hardness conversion, mechanical testing, aging, and crosslink metrics.

Public API:
  shore_a_to_youngs_modulus — E ≈ 0.5 * exp(0.04 * shore_a)
  mooney_viscosity_index    — Returns ML value as standardized index
  tensile_set               — TS = (recovered - original)/(stretched - original)*100
  compression_set           — CS = (original - recovered)/(original - compressed)*100
  elongation_at_break       — EB = (final - original)/original * 100
  tear_strength             — TS = F / t
  resilience_rebound        — R = rebound / drop * 100
  hardness_change_aging     — ΔH = aged - initial
  swelling_percentage       — S = (swollen - original)/original * 100
  crosslink_density_estimate— ν = E / (3*R*T)
  abrasion_loss_volume      — V = mass / density
  heat_buildup              — ΔT ≈ hysteresis * freq * time / 1000
"""
from std.math import exp, abs as fabs


# ── shore_a_to_youngs_modulus ────────────────────────────────────────────────


def shore_a_to_youngs_modulus(shore_a: Float64) -> Float64:
    """Approximate Young's modulus from Shore A hardness.

    Uses simplified relation: E ≈ 0.5 * exp(0.04 * shore_a) (MPa).

    Args:
        shore_a: Shore A hardness value (0-100).

    Returns:
        Approximate Young's modulus (MPa).
    """
    return 0.5 * exp(0.04 * shore_a)


# ── mooney_viscosity_index ───────────────────────────────────────────────────


def mooney_viscosity_index(
    ml_value: Float64, temperature: Float64
) -> Float64:
    """Mooney viscosity standardized index.

    Returns ML value annotated at temperature (simplified).

    Args:
        ml_value: Mooney viscosity (ML 1+4).
        temperature: Test temperature (°C).

    Returns:
        Mooney viscosity index (same as ml_value for standard reporting).
    """
    return ml_value


# ── tensile_set ──────────────────────────────────────────────────────────────


def tensile_set(
    stretched_length: Float64,
    original_length: Float64,
    recovered_length: Float64,
) -> Float64:
    """Tensile set: TS = (recovered - original)/(stretched - original) * 100.

    Args:
        stretched_length: Length at max stretch (mm).
        original_length: Original length (mm).
        recovered_length: Length after recovery (mm).

    Returns:
        Tensile set (%).
    """
    var denom = stretched_length - original_length
    if denom == 0.0:
        return 0.0
    return (recovered_length - original_length) / denom * 100.0


# ── compression_set ──────────────────────────────────────────────────────────


def compression_set(
    original_thickness: Float64,
    compressed_thickness: Float64,
    recovered_thickness: Float64,
) -> Float64:
    """Compression set: CS = (original - recovered)/(original - compressed) * 100.

    Args:
        original_thickness: Original thickness (mm).
        compressed_thickness: Compressed thickness (mm).
        recovered_thickness: Recovered thickness (mm).

    Returns:
        Compression set (%).
    """
    var denom = original_thickness - compressed_thickness
    if denom == 0.0:
        return 0.0
    return (original_thickness - recovered_thickness) / denom * 100.0


# ── elongation_at_break ──────────────────────────────────────────────────────


def elongation_at_break(
    final_length: Float64, original_length: Float64
) -> Float64:
    """Elongation at break: EB = (final - original) / original * 100.

    Args:
        final_length: Length at break (mm).
        original_length: Original length (mm).

    Returns:
        Elongation at break (%).
    """
    if original_length <= 0.0:
        return 0.0
    return (final_length - original_length) / original_length * 100.0


# ── tear_strength ────────────────────────────────────────────────────────────


def tear_strength(force: Float64, thickness: Float64) -> Float64:
    """Tear strength: TS = F / t.

    Args:
        force: Tearing force (N).
        thickness: Specimen thickness (mm).

    Returns:
        Tear strength (N/mm).
    """
    if thickness <= 0.0:
        return 0.0
    return force / thickness


# ── resilience_rebound ───────────────────────────────────────────────────────


def resilience_rebound(
    drop_height: Float64, rebound_height: Float64
) -> Float64:
    """Resilience: R = rebound / drop * 100.

    Args:
        drop_height: Height from which ball is dropped (mm).
        rebound_height: Height of rebound (mm).

    Returns:
        Resilience (%).
    """
    if drop_height <= 0.0:
        return 0.0
    return rebound_height / drop_height * 100.0


# ── hardness_change_aging ────────────────────────────────────────────────────


def hardness_change_aging(
    initial_hardness: Float64, aged_hardness: Float64
) -> Float64:
    """Hardness change after aging: ΔH = aged - initial.

    Args:
        initial_hardness: Shore A before aging.
        aged_hardness: Shore A after aging.

    Returns:
        Change in hardness (points).
    """
    return aged_hardness - initial_hardness


# ── swelling_percentage ──────────────────────────────────────────────────────


def swelling_percentage(
    swollen_volume: Float64, original_volume: Float64
) -> Float64:
    """Swelling %: S = (swollen - original) / original * 100.

    Args:
        swollen_volume: Volume after swelling (cm³).
        original_volume: Original volume (cm³).

    Returns:
        Swelling (%).
    """
    if original_volume <= 0.0:
        return 0.0
    return (swollen_volume - original_volume) / original_volume * 100.0


# ── crosslink_density_estimate ───────────────────────────────────────────────


def crosslink_density_estimate(
    modulus: Float64, temperature_k: Float64, r: Float64
) -> Float64:
    """Crosslink density: ν = E / (3 * R * T).

    Args:
        modulus: Elastic modulus (Pa).
        temperature_k: Temperature (K).
        r: Gas constant (8.314 J/(mol·K)).

    Returns:
        Crosslink density (mol/m³).
    """
    var denom = 3.0 * r * temperature_k
    if denom == 0.0:
        return 0.0
    return modulus / denom


# ── abrasion_loss_volume ─────────────────────────────────────────────────────


def abrasion_loss_volume(mass_loss: Float64, density: Float64) -> Float64:
    """Abrasion loss volume: V = mass / density.

    Args:
        mass_loss: Mass loss (g).
        density: Material density (g/cm³).

    Returns:
        Volume loss (mm³ equivalent via cm³ * 1000).
    """
    if density <= 0.0:
        return 0.0
    return mass_loss / density


# ── heat_buildup ─────────────────────────────────────────────────────────────


def heat_buildup(
    hysteresis_loss: Float64, frequency: Float64, time: Float64
) -> Float64:
    """Heat buildup (simplified): ΔT ≈ hysteresis * freq * time / 1000.

    Args:
        hysteresis_loss: Hysteresis loss per cycle (J).
        frequency: Cycling frequency (Hz).
        time: Duration (s).

    Returns:
        Approximate temperature rise (°C).
    """
    return hysteresis_loss * frequency * time / 1000.0
