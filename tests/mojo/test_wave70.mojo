"""Tests for Wave 70 — Ecology, Acoustics, Textile."""

from ecology import (
    logistic_growth,
    exponential_growth,
    carrying_capacity_estimate,
    lotka_volterra_prey,
    lotka_volterra_predator,
    species_richness_margalef,
    shannon_diversity,
    simpson_index,
    simpson_diversity,
    jaccard_similarity,
    sorensen_similarity,
    species_area_relationship,
)
from acoustics import (
    sound_pressure_level,
    sound_intensity_level,
    sound_power_level,
    inverse_square_law_pressure,
    wavelength,
    resonant_frequency_pipe_open,
    resonant_frequency_pipe_closed,
    doppler_frequency,
    reverberation_time_sabine,
    noise_reduction_coefficient,
    decibel_sum_2,
    distance_doubling_attenuation,
)
from textile import (
    tex_to_denier,
    denier_to_tex,
    yarn_count_ne,
    tex_from_diameter_density,
    twist_per_meter,
    twist_multiplier,
    fabric_gsm,
    fabric_cover_factor,
    pilling_resistance_score,
    moisture_regain,
    shrinkage_percentage,
    breaking_tenacity,
)
from std.math import abs as fabs, exp, log, pow, sqrt


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


# ── Ecology tests ────────────────────────────────────────────────────────────


fn test_logistic_growth() raises:
    # r=0.5, N=50, K=100 => 0.5*50*(1-50/100) = 0.5*50*0.5 = 12.5
    var v = logistic_growth(0.5, 50.0, 100.0)
    _assert(fabs(v - 12.5) < 1e-9, "logistic_growth basic")

    # At carrying capacity, growth = 0
    var v2 = logistic_growth(0.5, 100.0, 100.0)
    _assert(fabs(v2) < 1e-9, "logistic_growth at K")

    # At N=0, growth = 0
    var v3 = logistic_growth(0.5, 0.0, 100.0)
    _assert(fabs(v3) < 1e-9, "logistic_growth at N=0")
    print("  ✓ logistic_growth (3 assertions)")


fn test_exponential_growth() raises:
    # N0=100, r=0, t=5 => 100
    var v = exponential_growth(100.0, 0.0, 5.0)
    _assert(fabs(v - 100.0) < 1e-9, "exponential_growth r=0")

    # N0=100, r=1, t=0 => 100
    var v2 = exponential_growth(100.0, 1.0, 0.0)
    _assert(fabs(v2 - 100.0) < 1e-9, "exponential_growth t=0")

    # N0=10, r=0.5, t=2 => 10*exp(1) ≈ 27.1828
    var v3 = exponential_growth(10.0, 0.5, 2.0)
    _assert(fabs(v3 - 10.0 * exp(1.0)) < 1e-6, "exponential_growth basic")
    print("  ✓ exponential_growth (3 assertions)")


fn test_carrying_capacity_estimate() raises:
    var v = carrying_capacity_estimate(500.0, 0.3, 50.0, 10.0)
    _assert(v > 0.0, "carrying_capacity positive")

    # When n0 is near zero, should return n_max
    var v2 = carrying_capacity_estimate(500.0, 0.3, 0.0, 10.0)
    _assert(fabs(v2 - 500.0) < 1e-9, "carrying_capacity n0=0")
    print("  ✓ carrying_capacity_estimate (2 assertions)")


fn test_lotka_volterra_prey() raises:
    # r=1.0, N=100, alpha=0.01, P=20 => 1*100 - 0.01*100*20 = 100-20 = 80
    var v = lotka_volterra_prey(1.0, 100.0, 0.01, 20.0)
    _assert(fabs(v - 80.0) < 1e-9, "lv_prey basic")

    # No predators => pure growth
    var v2 = lotka_volterra_prey(1.0, 100.0, 0.01, 0.0)
    _assert(fabs(v2 - 100.0) < 1e-9, "lv_prey no predators")
    print("  ✓ lotka_volterra_prey (2 assertions)")


fn test_lotka_volterra_predator() raises:
    # beta=0.02, N=100, P=10, delta=0.5 => 0.02*100*10 - 0.5*10 = 20-5 = 15
    var v = lotka_volterra_predator(0.02, 100.0, 10.0, 0.5)
    _assert(fabs(v - 15.0) < 1e-9, "lv_predator basic")

    # No prey => decline
    var v2 = lotka_volterra_predator(0.02, 0.0, 10.0, 0.5)
    _assert(fabs(v2 - (-5.0)) < 1e-9, "lv_predator no prey")
    print("  ✓ lotka_volterra_predator (2 assertions)")


fn test_species_richness_margalef() raises:
    # S=10, N=100 => (10-1)/ln(100) = 9/4.60517 ≈ 1.9541
    var v = species_richness_margalef(10.0, 100.0)
    _assert(fabs(v - 9.0 / log(100.0)) < 1e-6, "margalef basic")

    # Single species
    var v2 = species_richness_margalef(1.0, 100.0)
    _assert(fabs(v2) < 1e-9, "margalef single species")
    print("  ✓ species_richness_margalef (2 assertions)")


fn test_shannon_diversity() raises:
    # Pre-computed sum: for equal proportions of 2 species: 2*(0.5*ln(0.5)) = -0.6931
    var sum_plogp = 2.0 * (0.5 * log(0.5))  # ≈ -0.6931
    var v = shannon_diversity(sum_plogp)
    _assert(fabs(v - 0.6931471805599453) < 1e-6, "shannon basic")

    # Zero input => zero
    var v2 = shannon_diversity(0.0)
    _assert(fabs(v2) < 1e-9, "shannon zero")
    print("  ✓ shannon_diversity (2 assertions)")


fn test_simpson_index() raises:
    # Two equal species: 0.5^2 + 0.5^2 = 0.5
    var v = simpson_index(0.5)
    _assert(fabs(v - 0.5) < 1e-9, "simpson_index basic")
    print("  ✓ simpson_index (1 assertion)")


fn test_simpson_diversity() raises:
    var v = simpson_diversity(0.5)
    _assert(fabs(v - 0.5) < 1e-9, "simpson_diversity basic")

    var v2 = simpson_diversity(0.0)
    _assert(fabs(v2 - 1.0) < 1e-9, "simpson_diversity max")
    print("  ✓ simpson_diversity (2 assertions)")


fn test_jaccard_similarity() raises:
    # 3 shared, A=5, B=7 => 3/(5+7-3) = 3/9 = 0.333...
    var v = jaccard_similarity(3.0, 5.0, 7.0)
    _assert(fabs(v - 1.0 / 3.0) < 1e-9, "jaccard basic")

    # Perfect overlap
    var v2 = jaccard_similarity(5.0, 5.0, 5.0)
    _assert(fabs(v2 - 1.0) < 1e-9, "jaccard perfect")

    # No overlap
    var v3 = jaccard_similarity(0.0, 5.0, 7.0)
    _assert(fabs(v3) < 1e-9, "jaccard no overlap")
    print("  ✓ jaccard_similarity (3 assertions)")


fn test_sorensen_similarity() raises:
    # 3 shared, A=5, B=7 => 2*3/(5+7) = 6/12 = 0.5
    var v = sorensen_similarity(3.0, 5.0, 7.0)
    _assert(fabs(v - 0.5) < 1e-9, "sorensen basic")

    # Perfect overlap
    var v2 = sorensen_similarity(5.0, 5.0, 5.0)
    _assert(fabs(v2 - 1.0) < 1e-9, "sorensen perfect")
    print("  ✓ sorensen_similarity (2 assertions)")


fn test_species_area_relationship() raises:
    # c=2, area=100, z=0.25 => 2 * 100^0.25 = 2*3.16228 ≈ 6.3246
    var v = species_area_relationship(2.0, 100.0, 0.25)
    var expected = 2.0 * pow(100.0, 0.25)
    _assert(fabs(v - expected) < 1e-6, "species_area basic")

    # Area=1 => S=c
    var v2 = species_area_relationship(5.0, 1.0, 0.3)
    _assert(fabs(v2 - 5.0) < 1e-9, "species_area unit area")
    print("  ✓ species_area_relationship (2 assertions)")


# ── Acoustics tests ──────────────────────────────────────────────────────────


fn test_sound_pressure_level() raises:
    # 1 Pa vs 20e-6 Pa => 20*log10(1/20e-6) = 20*log10(50000) ≈ 93.98 dB
    var v = sound_pressure_level(1.0, 20e-6)
    var expected = 20.0 * log(50000.0) / log(10.0)
    _assert(fabs(v - expected) < 1e-6, "spl basic")

    # Equal to reference => 0 dB
    var v2 = sound_pressure_level(20e-6, 20e-6)
    _assert(fabs(v2) < 1e-6, "spl at ref")
    print("  ✓ sound_pressure_level (2 assertions)")


fn test_sound_intensity_level() raises:
    # I=1e-6 vs 1e-12 => 10*log10(1e6) = 60 dB
    var v = sound_intensity_level(1e-6, 1e-12)
    _assert(fabs(v - 60.0) < 1e-6, "sil basic")
    print("  ✓ sound_intensity_level (1 assertion)")


fn test_sound_power_level() raises:
    # W=1 vs 1e-12 => 10*log10(1e12) = 120 dB
    var v = sound_power_level(1.0, 1e-12)
    _assert(fabs(v - 120.0) < 1e-6, "swl basic")
    print("  ✓ sound_power_level (1 assertion)")


fn test_inverse_square_law() raises:
    # Double distance => -6 dB
    var v = inverse_square_law_pressure(100.0, 1.0, 2.0)
    var expected = 100.0 - 20.0 * log(2.0) / log(10.0)
    _assert(fabs(v - expected) < 1e-6, "inverse_sq basic")

    # Same distance => same SPL
    var v2 = inverse_square_law_pressure(100.0, 1.0, 1.0)
    _assert(fabs(v2 - 100.0) < 1e-6, "inverse_sq same dist")
    print("  ✓ inverse_square_law_pressure (2 assertions)")


fn test_wavelength() raises:
    # c=343, f=1000 => 0.343
    var v = wavelength(343.0, 1000.0)
    _assert(fabs(v - 0.343) < 1e-9, "wavelength basic")

    # c=343, f=343 => 1.0
    var v2 = wavelength(343.0, 343.0)
    _assert(fabs(v2 - 1.0) < 1e-9, "wavelength unity")
    print("  ✓ wavelength (2 assertions)")


fn test_resonant_frequency_pipe_open() raises:
    # c=343, L=1.0 => 343/2 = 171.5
    var v = resonant_frequency_pipe_open(343.0, 1.0)
    _assert(fabs(v - 171.5) < 1e-9, "open pipe basic")
    print("  ✓ resonant_frequency_pipe_open (1 assertion)")


fn test_resonant_frequency_pipe_closed() raises:
    # c=343, L=1.0 => 343/4 = 85.75
    var v = resonant_frequency_pipe_closed(343.0, 1.0)
    _assert(fabs(v - 85.75) < 1e-9, "closed pipe basic")
    print("  ✓ resonant_frequency_pipe_closed (1 assertion)")


fn test_doppler_frequency() raises:
    # Stationary: f0=1000, c=343, vs=0, vo=0 => 1000
    var v = doppler_frequency(1000.0, 343.0, 0.0, 0.0)
    _assert(fabs(v - 1000.0) < 1e-6, "doppler stationary")

    # Observer approaching: vo=34.3 (10% of c), vs=0
    # f' = 1000 * (343+34.3)/343 = 1000 * 1.1 = 1100
    var v2 = doppler_frequency(1000.0, 343.0, 0.0, 34.3)
    _assert(fabs(v2 - 1100.0) < 1e-6, "doppler observer approach")

    # Source receding: vs=34.3 (10% of c), vo=0
    # f' = 1000 * 343/(343+34.3) = 1000/1.1 ≈ 909.09
    var v3 = doppler_frequency(1000.0, 343.0, 34.3, 0.0)
    var exp3 = 1000.0 * 343.0 / 377.3
    _assert(fabs(v3 - exp3) < 1e-4, "doppler source recede")
    print("  ✓ doppler_frequency (3 assertions)")


fn test_reverberation_time_sabine() raises:
    # V=500, A=50 => 0.161*500/50 = 0.161*10 = 1.61
    var v = reverberation_time_sabine(500.0, 50.0)
    _assert(fabs(v - 1.61) < 1e-9, "sabine basic")
    print("  ✓ reverberation_time_sabine (1 assertion)")


fn test_noise_reduction_coefficient() raises:
    # Average of 0.2, 0.4, 0.6, 0.8 = 0.5
    var v = noise_reduction_coefficient(0.2, 0.4, 0.6, 0.8)
    _assert(fabs(v - 0.5) < 1e-9, "nrc basic")

    # All zeros
    var v2 = noise_reduction_coefficient(0.0, 0.0, 0.0, 0.0)
    _assert(fabs(v2) < 1e-9, "nrc zeros")
    print("  ✓ noise_reduction_coefficient (2 assertions)")


fn test_decibel_sum_2() raises:
    # Two equal sources of 80 dB => 80 + 10*log10(2) ≈ 83.01
    var v = decibel_sum_2(80.0, 80.0)
    var expected = 80.0 + 10.0 * log(2.0) / log(10.0)
    _assert(fabs(v - expected) < 1e-4, "db_sum equal")

    # 90 dB + 80 dB
    var v2 = decibel_sum_2(90.0, 80.0)
    var p1 = pow(10.0, 9.0)
    var p2 = pow(10.0, 8.0)
    var exp2 = 10.0 * log(p1 + p2) / log(10.0)
    _assert(fabs(v2 - exp2) < 1e-4, "db_sum unequal")
    print("  ✓ decibel_sum_2 (2 assertions)")


fn test_distance_doubling_attenuation() raises:
    var v = distance_doubling_attenuation()
    _assert(fabs(v - 6.0) < 1e-9, "doubling atten")
    print("  ✓ distance_doubling_attenuation (1 assertion)")


# ── Textile tests ────────────────────────────────────────────────────────────


fn test_tex_to_denier() raises:
    # 10 tex => 90 denier
    var v = tex_to_denier(10.0)
    _assert(fabs(v - 90.0) < 1e-9, "tex_to_denier basic")

    # 0 tex => 0 denier
    var v2 = tex_to_denier(0.0)
    _assert(fabs(v2) < 1e-9, "tex_to_denier zero")
    print("  ✓ tex_to_denier (2 assertions)")


fn test_denier_to_tex() raises:
    # 90 denier => 10 tex
    var v = denier_to_tex(90.0)
    _assert(fabs(v - 10.0) < 1e-9, "denier_to_tex basic")

    # Round-trip
    var v2 = denier_to_tex(tex_to_denier(15.0))
    _assert(fabs(v2 - 15.0) < 1e-9, "denier_tex roundtrip")
    print("  ✓ denier_to_tex (2 assertions)")


fn test_yarn_count_ne() raises:
    # L=30, W=10 => Ne=3
    var v = yarn_count_ne(30.0, 10.0)
    _assert(fabs(v - 3.0) < 1e-9, "yarn_count basic")

    # W=0 => 0
    var v2 = yarn_count_ne(30.0, 0.0)
    _assert(fabs(v2) < 1e-9, "yarn_count zero weight")
    print("  ✓ yarn_count_ne (2 assertions)")


fn test_tex_from_diameter_density() raises:
    # d=0.1mm, density=1.5 g/cm³ => π/4 * 0.01 * 1.5 * 1000 = 11.78
    var v = tex_from_diameter_density(0.1, 1.5)
    var expected = 3.141592653589793 / 4.0 * 0.01 * 1.5 * 1000.0
    _assert(fabs(v - expected) < 1e-6, "tex_from_diam basic")
    print("  ✓ tex_from_diameter_density (1 assertion)")


fn test_twist_per_meter() raises:
    # 10 TPI => 10*39.37 = 393.7 TPM
    var v = twist_per_meter(10.0)
    _assert(fabs(v - 393.7) < 1e-9, "tpm basic")
    print("  ✓ twist_per_meter (1 assertion)")


fn test_twist_multiplier() raises:
    # TPI=20, Ne=16 => 20/sqrt(16) = 20/4 = 5.0
    var v = twist_multiplier(20.0, 16.0)
    _assert(fabs(v - 5.0) < 1e-9, "tm basic")

    # Ne=0 => 0
    var v2 = twist_multiplier(20.0, 0.0)
    _assert(fabs(v2) < 1e-9, "tm zero count")
    print("  ✓ twist_multiplier (2 assertions)")


fn test_fabric_gsm() raises:
    # 150g / 1.0 m² = 150 GSM
    var v = fabric_gsm(150.0, 1.0)
    _assert(fabs(v - 150.0) < 1e-9, "gsm basic")

    # 300g / 2.0 m² = 150 GSM
    var v2 = fabric_gsm(300.0, 2.0)
    _assert(fabs(v2 - 150.0) < 1e-9, "gsm double")
    print("  ✓ fabric_gsm (2 assertions)")


fn test_fabric_cover_factor() raises:
    # 30 threads/cm, count=25 => 30/sqrt(25) = 30/5 = 6.0
    var v = fabric_cover_factor(30.0, 25.0)
    _assert(fabs(v - 6.0) < 1e-9, "cover_factor basic")
    print("  ✓ fabric_cover_factor (1 assertion)")


fn test_pilling_resistance_score() raises:
    # Grade 4, cycles=1000 => 4/5 = 0.8
    var v = pilling_resistance_score(1000, 4.0)
    _assert(fabs(v - 0.8) < 1e-9, "pilling basic")

    # Grade 5 => 1.0
    var v2 = pilling_resistance_score(2000, 5.0)
    _assert(fabs(v2 - 1.0) < 1e-9, "pilling perfect")
    print("  ✓ pilling_resistance_score (2 assertions)")


fn test_moisture_regain() raises:
    # wet=110, dry=100 => (110-100)/100*100 = 10%
    var v = moisture_regain(110.0, 100.0)
    _assert(fabs(v - 10.0) < 1e-9, "moisture basic")

    # No moisture
    var v2 = moisture_regain(100.0, 100.0)
    _assert(fabs(v2) < 1e-9, "moisture zero")
    print("  ✓ moisture_regain (2 assertions)")


fn test_shrinkage_percentage() raises:
    # L0=100, Lf=95 => (100-95)/100*100 = 5%
    var v = shrinkage_percentage(100.0, 95.0)
    _assert(fabs(v - 5.0) < 1e-9, "shrinkage basic")

    # No shrinkage
    var v2 = shrinkage_percentage(100.0, 100.0)
    _assert(fabs(v2) < 1e-9, "shrinkage zero")
    print("  ✓ shrinkage_percentage (2 assertions)")


fn test_breaking_tenacity() raises:
    # F=50 cN, tex=25 => 50/25 = 2.0 cN/tex
    var v = breaking_tenacity(50.0, 25.0)
    _assert(fabs(v - 2.0) < 1e-9, "tenacity basic")

    # tex=0 => 0
    var v2 = breaking_tenacity(50.0, 0.0)
    _assert(fabs(v2) < 1e-9, "tenacity zero tex")
    print("  ✓ breaking_tenacity (2 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 70 Tests: Ecology, Acoustics, Textile ===")
    print()

    print("── Ecology ──")
    test_logistic_growth()
    test_exponential_growth()
    test_carrying_capacity_estimate()
    test_lotka_volterra_prey()
    test_lotka_volterra_predator()
    test_species_richness_margalef()
    test_shannon_diversity()
    test_simpson_index()
    test_simpson_diversity()
    test_jaccard_similarity()
    test_sorensen_similarity()
    test_species_area_relationship()
    print()

    print("── Acoustics ──")
    test_sound_pressure_level()
    test_sound_intensity_level()
    test_sound_power_level()
    test_inverse_square_law()
    test_wavelength()
    test_resonant_frequency_pipe_open()
    test_resonant_frequency_pipe_closed()
    test_doppler_frequency()
    test_reverberation_time_sabine()
    test_noise_reduction_coefficient()
    test_decibel_sum_2()
    test_distance_doubling_attenuation()
    print()

    print("── Textile ──")
    test_tex_to_denier()
    test_denier_to_tex()
    test_yarn_count_ne()
    test_tex_from_diameter_density()
    test_twist_per_meter()
    test_twist_multiplier()
    test_fabric_gsm()
    test_fabric_cover_factor()
    test_pilling_resistance_score()
    test_moisture_regain()
    test_shrinkage_percentage()
    test_breaking_tenacity()
    print()

    print("✅ Wave 70 — All 72 assertions passed.")
