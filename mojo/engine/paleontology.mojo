"""
paleontology.mojo — Paleontology / Geochronology Library. Zero Python imports.

Provides radiometric dating (C-14, K-Ar, U-Pb), stratigraphic analysis,
fossil diversity indices, extinction/origination rates, body mass allometry,
phylogenetic distance, and skeletal completeness metrics.

Public API:
  radiocarbon_age              — C-14 age from isotope ratio
  potassium_argon_age          — K-Ar radiometric age
  uranium_lead_age             — U-Pb radiometric age
  stratigraphic_completeness   — Preserved / total time fraction
  sedimentation_rate           — Thickness / time (m/Myr)
  fossil_diversity_index       — Margalef diversity index
  extinction_rate              — Per-taxon extinction rate
  origination_rate             — Per-taxon origination rate
  turnover_rate                — Average of extinction + origination
  body_mass_estimate_mammal    — Allometric mass from femur length
  phylogenetic_distance        — Molecular divergence distance
  completeness_metric          — Skeletal completeness ratio
"""
from std.math import log


# ── Radiometric dating ───────────────────────────────────────────────────────


fn radiocarbon_age(ratio: Float64, lambda_c14: Float64) -> Float64:
    """Radiocarbon age: t = -ln(R) / λ  years.

    ratio = current/initial C-14 ratio (0 < R ≤ 1).
    lambda_c14 ≈ 1.21e-4 /yr (decay constant).
    """
    return -log(ratio) / lambda_c14


fn potassium_argon_age(
    ar40_k40_ratio: Float64, lambda_k: Float64
) -> Float64:
    """K-Ar age: t = ln(1 + R) / λ.

    ar40_k40_ratio = Ar-40 / K-40 measured ratio.
    lambda_k ≈ 5.543e-10 /yr.
    """
    return log(1.0 + ar40_k40_ratio) / lambda_k


fn uranium_lead_age(
    pb206_u238_ratio: Float64, lambda_u: Float64
) -> Float64:
    """U-Pb age: t = ln(1 + R) / λ.

    pb206_u238_ratio = Pb-206 / U-238 ratio.
    lambda_u ≈ 1.55125e-10 /yr.
    """
    return log(1.0 + pb206_u238_ratio) / lambda_u


# ── Stratigraphic analysis ───────────────────────────────────────────────────


fn stratigraphic_completeness(
    preserved_intervals: Float64, total_time: Float64
) -> Float64:
    """Stratigraphic completeness SC = preserved / total (0–1)."""
    return preserved_intervals / total_time


fn sedimentation_rate(
    thickness: Float64, time: Float64
) -> Float64:
    """Sedimentation rate SR = thickness / time  (m/Myr)."""
    return thickness / time


# ── Diversity & turnover ─────────────────────────────────────────────────────


fn fossil_diversity_index(
    n_species: Float64, n_specimens: Float64
) -> Float64:
    """Margalef diversity index: D = (S - 1) / ln(N).

    n_species = number of species (S), n_specimens = total specimens (N).
    """
    return (n_species - 1.0) / log(n_specimens)


fn extinction_rate(
    n_extinct: Float64,
    n_total: Float64,
    time_interval: Float64,
) -> Float64:
    """Per-taxon extinction rate: ER = (extinct / total) / Δt."""
    return (n_extinct / n_total) / time_interval


fn origination_rate(
    n_new: Float64,
    n_total: Float64,
    time_interval: Float64,
) -> Float64:
    """Per-taxon origination rate: OR = (new / total) / Δt."""
    return (n_new / n_total) / time_interval


fn turnover_rate(
    extinction_r: Float64, origination_r: Float64
) -> Float64:
    """Turnover rate TR = (ER + OR) / 2."""
    return (extinction_r + origination_r) / 2.0


# ── Allometry & phylogenetics ────────────────────────────────────────────────


fn body_mass_estimate_mammal(femur_length_mm: Float64) -> Float64:
    """Estimate mammalian body mass (g) from femur length (mm).

    log10(M) = 2.75 * log10(FL) - 3.30  (simplified allometry).
    Returns mass in grams.
    """
    var ln10 = log(10.0)
    var log10_fl = log(femur_length_mm) / ln10
    var log10_m = 2.75 * log10_fl - 3.30
    # M = 10^(log10_m) = exp(log10_m * ln(10))
    var m = _pow10(log10_m)
    return m


fn _pow10(x: Float64) -> Float64:
    """10^x via exp(x * ln(10))."""
    from std.math import exp
    return exp(x * log(10.0))


fn phylogenetic_distance(
    divergence_time: Float64, molecular_rate: Float64
) -> Float64:
    """Phylogenetic distance D = 2 * t * r.

    divergence_time in years, molecular_rate in substitutions/site/year.
    """
    return 2.0 * divergence_time * molecular_rate


fn completeness_metric(
    bones_found: Float64, bones_expected: Float64
) -> Float64:
    """Skeletal completeness C = bones_found / bones_expected  (0–1)."""
    return bones_found / bones_expected
