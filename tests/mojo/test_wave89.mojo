"""Tests for Wave 89 — Structural Engineering, Entomology, Perfumery.
🎯 350 LIBRARY MILESTONE!
"""

from structural import (
    bending_stress,
    shear_stress_beam,
    moment_of_inertia_rect,
    section_modulus_rect,
    deflection_cantilever_point,
    deflection_simply_supported_center,
    euler_buckling_load,
    slenderness_ratio,
    axial_stress,
    combined_stress_von_mises,
    safety_factor,
    natural_frequency_cantilever,
)
from entomology import (
    degree_days,
    accumulated_degree_days,
    population_growth_intrinsic,
    net_reproductive_rate,
    generation_time,
    doubling_time_population,
    species_diversity_simpson,
    trap_catch_index,
    infestation_rate,
    biocontrol_efficacy,
    larval_mortality_rate,
    metabolic_rate_insect,
)
from perfumery import (
    concentration_parfum,
    dilution_ratio,
    evaporation_rate_relative,
    top_note_duration,
    middle_note_duration,
    base_note_duration,
    triangle_accord_balance,
    tenacity_hours,
    sillage_distance,
    cost_per_ml,
    fragrance_strength_scale,
    ingredient_proportion,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, log, exp


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < eps


def approx_rel(a: Float64, b: Float64, eps: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < eps
    return fabs((a - b) / b) < eps


# ── Structural Engineering Tests ─────────────────────────────────────────────


def test_structural() raises:
    print("Testing structural engineering...")

    # 1. bending_stress: σ = M/S
    assert_true(approx(bending_stress(1000.0, 50.0), 20.0), "bending_stress basic")
    # 2
    assert_true(approx(bending_stress(5000.0, 100.0), 50.0), "bending_stress 2")

    # 3. shear_stress_beam: τ = V/A
    assert_true(approx(shear_stress_beam(500.0, 25.0), 20.0), "shear_stress basic")
    # 4
    assert_true(approx(shear_stress_beam(1200.0, 40.0), 30.0), "shear_stress 2")

    # 5. moment_of_inertia_rect: I = bh³/12
    # 6*12³/12 = 6*1728/12 = 864
    assert_true(approx(moment_of_inertia_rect(6.0, 12.0), 864.0), "MoI rect")
    # 6. 10*10³/12 = 833.333...
    assert_true(approx_rel(moment_of_inertia_rect(10.0, 10.0), 833.3333333), "MoI rect sq")

    # 7. section_modulus_rect: S = bh²/6
    assert_true(approx(section_modulus_rect(6.0, 12.0), 144.0), "section mod rect")
    # 8
    assert_true(approx_rel(section_modulus_rect(10.0, 10.0), 166.6666667), "section mod sq")

    # 9. deflection_cantilever_point: δ = PL³/(3EI)
    # 100*27/(3*9000) = 2700/27000 = 0.1
    assert_true(approx(deflection_cantilever_point(100.0, 3.0, 9000.0), 0.1), "cantilever defl")

    # 10. deflection_simply_supported_center: δ = PL³/(48EI)
    # 480*8/(48*1000) = 3840/48000 = 0.08
    assert_true(approx(deflection_simply_supported_center(480.0, 2.0, 1000.0), 0.08), "SS defl")

    # 11. euler_buckling_load: Pcr = π²EI/(kL)²
    # π²*1000/(1*1)² = 9869.604...
    var pcr = euler_buckling_load(1000.0, 1.0, 1.0)
    assert_true(approx_rel(pcr, 9869.6044), "euler buckling k=1")
    # 12. k=2, L=1: π²*1000/4 = 2467.40...
    var pcr2 = euler_buckling_load(1000.0, 1.0, 2.0)
    assert_true(approx_rel(pcr2, 2467.4011), "euler buckling k=2")

    # 13. slenderness_ratio: λ = L/r
    assert_true(approx(slenderness_ratio(3000.0, 30.0), 100.0), "slenderness")

    # 14. axial_stress: σ = P/A
    assert_true(approx(axial_stress(5000.0, 100.0), 50.0), "axial stress")
    # 15
    assert_true(approx(axial_stress(10000.0, 200.0), 50.0), "axial stress 2")

    # 16. combined_stress_von_mises — pure uniaxial
    assert_true(approx(combined_stress_von_mises(100.0, 0.0, 0.0), 100.0), "von mises uniaxial")
    # 17. pure shear: sqrt(3*50²) = sqrt(7500) ≈ 86.6025
    assert_true(approx_rel(combined_stress_von_mises(0.0, 0.0, 50.0), 86.6025), "von mises shear")
    # 18. biaxial: sqrt(100²-100*50+50²+3*30²) = sqrt(10200) ≈ 100.995
    assert_true(approx_rel(combined_stress_von_mises(100.0, 50.0, 30.0), 100.995), "von mises biaxial")

    # 19. safety_factor: FS = σ_u/σ_w
    assert_true(approx(safety_factor(500.0, 100.0), 5.0), "safety factor")
    # 20
    assert_true(approx(safety_factor(1000.0, 250.0), 4.0), "safety factor 2")

    # 21. natural_frequency_cantilever
    # f = (3.515625/6.28318..) * sqrt(EI/(m*L⁴))
    var beta1_sq: Float64 = 3.515625
    var two_pi: Float64 = 6.283185307179586
    var f1 = natural_frequency_cantilever(1.0, 1.0, 1.0)
    var expected_f1 = (beta1_sq / two_pi) * sqrt(1.0 / 1.0)
    assert_true(approx_rel(f1, expected_f1), "nat freq cantilever")
    # 22. EI=10000, m=5, L=2
    var f2 = natural_frequency_cantilever(10000.0, 5.0, 2.0)
    var expected_f2 = (beta1_sq / two_pi) * sqrt(10000.0 / (5.0 * 16.0))
    assert_true(approx_rel(f2, expected_f2), "nat freq cantilever 2")

    print("  ✅ structural: 22 assertions passed")


# ── Entomology Tests ─────────────────────────────────────────────────────────


def test_entomology() raises:
    print("Testing entomology...")

    # 23. degree_days: normal case
    assert_true(approx(degree_days(30.0, 20.0, 10.0), 15.0), "degree days normal")
    # 24. below base → 0
    assert_true(approx(degree_days(20.0, 10.0, 20.0), 0.0), "degree days below base")
    # 25. edge
    assert_true(approx(degree_days(15.0, 5.0, 15.0), 0.0), "degree days edge neg")

    # 26. accumulated_degree_days
    assert_true(approx(accumulated_degree_days(15.0, 10.0), 150.0), "ADD basic")
    # 27
    assert_true(approx(accumulated_degree_days(8.5, 20.0), 170.0), "ADD 2")

    # 28. population_growth_intrinsic: N = N0*exp(r*t)
    # N0=100, r=0.1, t=10 => 100*e^1 ≈ 271.828
    assert_true(approx_rel(population_growth_intrinsic(100.0, 0.1, 10.0), 271.8282), "pop growth")
    # 29. r=0, no growth
    assert_true(approx(population_growth_intrinsic(50.0, 0.0, 10.0), 50.0), "pop growth zero r")

    # 30. net_reproductive_rate: R0 = fecundity * survival
    assert_true(approx(net_reproductive_rate(200.0, 0.5), 100.0), "net repro rate")
    # 31
    assert_true(approx(net_reproductive_rate(500.0, 0.8), 400.0), "net repro rate 2")

    # 32. generation_time: T = ln(R0)/r
    # ln(100)/0.1 = 46.0517...
    assert_true(approx_rel(generation_time(100.0, 0.1), 46.0517), "gen time")

    # 33. doubling_time_population: DT = ln(2)/r
    # ln(2)/0.5 = 1.38629...
    assert_true(approx_rel(doubling_time_population(0.5), 1.38629), "doubling time")
    # 34. ln(2)/1.0 = 0.69315
    assert_true(approx_rel(doubling_time_population(1.0), 0.69315), "doubling time 2")

    # 35. species_diversity_simpson: D = 1 - Σ(pi²)
    assert_true(approx(species_diversity_simpson(0.3), 0.7), "simpson div")
    # 36
    assert_true(approx(species_diversity_simpson(0.0), 1.0), "simpson div max")
    # 37
    assert_true(approx(species_diversity_simpson(1.0), 0.0), "simpson div min")

    # 38. trap_catch_index: caught/(traps*days)
    assert_true(approx(trap_catch_index(100.0, 5.0, 4.0), 5.0), "trap catch")
    # 39
    assert_true(approx(trap_catch_index(60.0, 10.0, 3.0), 2.0), "trap catch 2")

    # 40. infestation_rate: infested/total * 100
    assert_true(approx(infestation_rate(20.0, 200.0), 10.0), "infestation rate")
    # 41
    assert_true(approx(infestation_rate(50.0, 100.0), 50.0), "infestation rate 2")

    # 42. biocontrol_efficacy: (control-treated)/control * 100
    assert_true(approx(biocontrol_efficacy(30.0, 100.0), 70.0), "biocontrol eff")
    # 43
    assert_true(approx(biocontrol_efficacy(10.0, 50.0), 80.0), "biocontrol eff 2")

    # 44. larval_mortality_rate: (init-surv)/init * 100
    assert_true(approx(larval_mortality_rate(1000.0, 600.0), 40.0), "larval mort")
    # 45
    assert_true(approx(larval_mortality_rate(500.0, 250.0), 50.0), "larval mort 2")

    # 46. metabolic_rate_insect: 0.01 * mass^0.75 * exp(0.07*T)
    var mr = metabolic_rate_insect(100.0, 25.0)
    var expected_mr = 0.01 * exp(0.75 * log(100.0)) * exp(0.07 * 25.0)
    assert_true(approx_rel(mr, expected_mr), "metabolic rate insect")
    # 47. different mass/temp
    var mr2 = metabolic_rate_insect(50.0, 20.0)
    var expected_mr2 = 0.01 * exp(0.75 * log(50.0)) * exp(0.07 * 20.0)
    assert_true(approx_rel(mr2, expected_mr2), "metabolic rate insect 2")

    print("  ✅ entomology: 25 assertions passed")


# ── Perfumery Tests ──────────────────────────────────────────────────────────


def test_perfumery() raises:
    print("Testing perfumery...")

    # 48. concentration_parfum: oil/total * 100
    assert_true(approx(concentration_parfum(15.0, 100.0), 15.0), "concentration parfum")
    # 49
    assert_true(approx(concentration_parfum(25.0, 100.0), 25.0), "concentration parfum 2")

    # 50. dilution_ratio: conc/(conc+diluent)
    assert_true(approx(dilution_ratio(10.0, 90.0), 0.1), "dilution ratio")
    # 51
    assert_true(approx(dilution_ratio(50.0, 50.0), 0.5), "dilution ratio half")

    # 52. evaporation_rate_relative
    assert_true(approx(evaporation_rate_relative(2.0, 1.0), 2.0), "evap rate rel")
    # 53
    assert_true(approx(evaporation_rate_relative(3.0, 2.0), 1.5), "evap rate rel 2")

    # 54. top_note_duration = 30 min
    assert_true(approx(top_note_duration(), 30.0), "top note dur")
    # 55. middle_note_duration = 240 min
    assert_true(approx(middle_note_duration(), 240.0), "mid note dur")
    # 56. base_note_duration = 1440 min
    assert_true(approx(base_note_duration(), 1440.0), "base note dur")

    # 57. triangle_accord_balance — balanced (all > 15%)
    assert_true(approx(triangle_accord_balance(30.0, 40.0, 30.0), 30.0), "accord balanced")
    # 58. unbalanced (one ≤ 15%)
    assert_true(approx(triangle_accord_balance(10.0, 40.0, 50.0), 0.0), "accord unbalanced")
    # 59. edge: exactly 15 is ≤ 15 → unbalanced
    assert_true(approx(triangle_accord_balance(15.0, 40.0, 45.0), 0.0), "accord edge 15")
    # 60. all equal > 15
    assert_true(approx_rel(triangle_accord_balance(33.3, 33.3, 33.4), 33.3), "accord equal")

    # 61. tenacity_hours: hours*(1 - final/initial)
    # 8*(1-2/10) = 8*0.8 = 6.4
    assert_true(approx(tenacity_hours(10.0, 2.0, 8.0), 6.4), "tenacity hours")
    # 62
    assert_true(approx(tenacity_hours(10.0, 5.0, 12.0), 6.0), "tenacity hours 2")

    # 63. sillage_distance: conc * volatility
    assert_true(approx(sillage_distance(20.0, 1.5), 30.0), "sillage dist")
    # 64
    assert_true(approx(sillage_distance(10.0, 3.0), 30.0), "sillage dist 2")

    # 65. cost_per_ml: cost/volume
    assert_true(approx(cost_per_ml(120.0, 50.0), 2.4), "cost per ml")
    # 66
    assert_true(approx(cost_per_ml(200.0, 100.0), 2.0), "cost per ml 2")

    # 67. fragrance_strength_scale
    assert_equal(fragrance_strength_scale(0.0), 0, "strength 0")
    # 68
    assert_equal(fragrance_strength_scale(3.0), 1, "strength cologne")
    # 69
    assert_equal(fragrance_strength_scale(10.0), 2, "strength EDT")
    # 70
    assert_equal(fragrance_strength_scale(18.0), 3, "strength EDP")
    # 71
    assert_equal(fragrance_strength_scale(25.0), 4, "strength parfum")
    # 72. boundary: 5.0 → EDT (2)
    assert_equal(fragrance_strength_scale(5.0), 2, "strength boundary 5")
    # 73. boundary: 15.0 → EDP (3)
    assert_equal(fragrance_strength_scale(15.0), 3, "strength boundary 15")
    # 74. boundary: 20.0 → EDP (3)
    assert_equal(fragrance_strength_scale(20.0), 3, "strength boundary 20")

    # 75. ingredient_proportion: ingredient/total * 100
    assert_true(approx(ingredient_proportion(5.0, 100.0), 5.0), "ingredient prop")
    # 76
    assert_true(approx(ingredient_proportion(25.0, 200.0), 12.5), "ingredient prop 2")

    print("  ✅ perfumery: 29 assertions passed")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=" * 60)
    print("Wave 89 Tests — Structural, Entomology, Perfumery")
    print("=" * 60)

    test_structural()
    test_entomology()
    test_perfumery()

    print("=" * 60)
    print("🎯 350 LIBRARY MILESTONE REACHED!")
    print("All 76 assertions passed ✅")
    print("=" * 60)
