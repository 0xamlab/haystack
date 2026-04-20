"""Tests for Wave 90 — Hydroponics, Concrete, Lottery."""

from hydroponics import (
    ec_from_tds,
    tds_from_ec,
    nutrient_concentration,
    ph_adjustment_acid,
    light_daily_integral,
    vpd,
    water_consumption_rate,
    nutrient_uptake_rate,
    grow_light_efficiency,
    reservoir_dilution,
    yield_per_area,
    crop_cycle_roi,
)
from concrete import (
    water_cement_ratio,
    compressive_strength_abrams,
    cement_content,
    aggregate_volume,
    slump_estimate,
    maturity_nurse_saul,
    modulus_of_elasticity,
    splitting_tensile_strength,
    drying_shrinkage_estimate,
    carbonation_depth,
    rebar_development_length,
    concrete_density_estimate,
)
from lottery import (
    combinations,
    permutations,
    lottery_odds,
    expected_value,
    expected_value_net,
    house_edge,
    probability_at_least_one_win,
    annuity_vs_lump_sum,
    tax_after_winnings,
    odds_to_probability,
    probability_to_odds,
    jackpot_ev_threshold,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, log, exp


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < eps


fn approx_rel(a: Float64, b: Float64, eps: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < eps
    return fabs((a - b) / b) < eps


# ── Hydroponics Tests ────────────────────────────────────────────────────────


fn test_hydroponics() raises:
    print("Testing hydroponics...")

    # 1. ec_from_tds: 500ppm * 0.5 / 1000 = 0.25 mS/cm
    assert_true(approx(ec_from_tds(500.0, 0.5), 0.25), "ec_from_tds basic")
    # 2. 1000ppm * 0.7 / 1000 = 0.7
    assert_true(approx(ec_from_tds(1000.0, 0.7), 0.7), "ec_from_tds 2")

    # 3. tds_from_ec: 1.0 / 0.5 * 1000 = 2000 ppm
    assert_true(approx(tds_from_ec(1.0, 0.5), 2000.0), "tds_from_ec basic")
    # 4. 2.0 / 0.7 * 1000 ≈ 2857.14
    assert_true(approx_rel(tds_from_ec(2.0, 0.7), 2857.1429), "tds_from_ec 2")

    # 5. nutrient_concentration: 10ml / 5L = 2 ppm
    assert_true(approx(nutrient_concentration(10.0, 5.0), 2.0), "nutrient conc")
    # 6. 25ml / 10L = 2.5 ppm
    assert_true(approx(nutrient_concentration(25.0, 10.0), 2.5), "nutrient conc 2")

    # 7. ph_adjustment_acid: (7.0-5.5)*10 = 15 ml
    assert_true(approx(ph_adjustment_acid(7.0, 5.5, 10.0), 15.0), "ph adj acid")
    # 8. target >= current → 0
    assert_true(approx(ph_adjustment_acid(5.5, 6.0, 10.0), 0.0), "ph adj no need")

    # 9. light_daily_integral: 400*16*3600/1e6 = 23.04
    assert_true(approx(light_daily_integral(400.0, 16.0), 23.04), "DLI basic")
    # 10. 200*12*3600/1e6 = 8.64
    assert_true(approx(light_daily_integral(200.0, 12.0), 8.64), "DLI 2")

    # 11. vpd: (1-0.6)*0.6108*exp(17.27*25/(25+237.3)) at 25°C, 60% RH
    var svp25 = 0.6108 * exp(17.27 * 25.0 / (25.0 + 237.3))
    var expected_vpd = 0.4 * svp25
    assert_true(approx_rel(vpd(25.0, 60.0), expected_vpd), "vpd 25C 60RH")
    # 12. 30°C, 80% RH
    var svp30 = 0.6108 * exp(17.27 * 30.0 / (30.0 + 237.3))
    assert_true(approx_rel(vpd(30.0, 80.0), 0.2 * svp30), "vpd 30C 80RH")

    # 13. water_consumption_rate: 5.0 * 10.0 = 50 L/day
    assert_true(approx(water_consumption_rate(5.0, 10.0), 50.0), "water cons rate")

    # 14. nutrient_uptake_rate: (800-600)*50/24 = 416.667
    assert_true(approx_rel(nutrient_uptake_rate(800.0, 600.0, 50.0, 24.0), 416.6667), "nutrient uptake")
    # 15. (1000-900)*20/10 = 200
    assert_true(approx(nutrient_uptake_rate(1000.0, 900.0, 20.0, 10.0), 200.0), "nutrient uptake 2")

    # 16. grow_light_efficiency: 600/300 = 2.0 µmol/J
    assert_true(approx(grow_light_efficiency(600.0, 300.0), 2.0), "light eff")
    # 17. 400/200 = 2.0
    assert_true(approx(grow_light_efficiency(400.0, 200.0), 2.0), "light eff 2")

    # 18. reservoir_dilution: 100*(2.0/1.0-1) = 100 L
    assert_true(approx(reservoir_dilution(2.0, 1.0, 100.0), 100.0), "reservoir dilute")
    # 19. target >= current → 0
    assert_true(approx(reservoir_dilution(1.0, 2.0, 100.0), 0.0), "reservoir no dilute")

    # 20. yield_per_area: 50/10 = 5.0 kg/m²
    assert_true(approx(yield_per_area(50.0, 10.0), 5.0), "yield per area")
    # 21. 120/30 = 4.0
    assert_true(approx(yield_per_area(120.0, 30.0), 4.0), "yield per area 2")

    # 22. crop_cycle_roi: (5000-2000)/2000*100 = 150%
    assert_true(approx(crop_cycle_roi(5000.0, 2000.0), 150.0), "crop ROI")
    # 23. (1000-1000)/1000*100 = 0%
    assert_true(approx(crop_cycle_roi(1000.0, 1000.0), 0.0), "crop ROI break even")
    # 24. (800-1000)/1000*100 = -20%
    assert_true(approx(crop_cycle_roi(800.0, 1000.0), -20.0), "crop ROI loss")

    print("  ✅ hydroponics: 24 assertions passed")


# ── Concrete Tests ───────────────────────────────────────────────────────────


fn test_concrete() raises:
    print("Testing concrete...")

    # 25. water_cement_ratio: 180/400 = 0.45
    assert_true(approx(water_cement_ratio(180.0, 400.0), 0.45), "wc ratio")
    # 26. 200/500 = 0.4
    assert_true(approx(water_cement_ratio(200.0, 500.0), 0.4), "wc ratio 2")

    # 27. compressive_strength_abrams: 100*exp(-3*0.5) = 100*exp(-1.5) ≈ 22.313
    assert_true(approx_rel(compressive_strength_abrams(100.0, 3.0, 0.5), 100.0 * exp(-1.5)), "abrams")
    # 28. 80*exp(-2*0.45)
    assert_true(approx_rel(compressive_strength_abrams(80.0, 2.0, 0.45), 80.0 * exp(-0.9)), "abrams 2")

    # 29. cement_content: 180/0.45 = 400
    assert_true(approx(cement_content(180.0, 0.45), 400.0), "cement content")
    # 30. 200/0.4 = 500
    assert_true(approx(cement_content(200.0, 0.4), 500.0), "cement content 2")

    # 31. aggregate_volume: 1.0 - 0.1 - 0.18 - 2*1.0/100 = 1.0-0.1-0.18-0.02 = 0.7
    assert_true(approx(aggregate_volume(1.0, 0.1, 0.18, 2.0), 0.7), "agg volume")

    # 32. slump_estimate: 300*(0.5-0.3) = 60 mm
    assert_true(approx(slump_estimate(0.5), 60.0), "slump 0.5")
    # 33. 300*(0.3-0.3) = 0 mm
    assert_true(approx(slump_estimate(0.3), 0.0), "slump 0.3")
    # 34. 300*(0.2-0.3) < 0 → clamped to 0
    assert_true(approx(slump_estimate(0.2), 0.0), "slump below range")

    # 35. maturity_nurse_saul: (20-(-10))*48 = 30*48 = 1440
    assert_true(approx(maturity_nurse_saul(48.0, 20.0, -10.0), 1440.0), "maturity NS")
    # 36. (25-0)*24 = 600
    assert_true(approx(maturity_nurse_saul(24.0, 25.0, 0.0), 600.0), "maturity NS 2")

    # 37. modulus_of_elasticity: 4700*sqrt(30) ≈ 25742.96
    assert_true(approx_rel(modulus_of_elasticity(30.0), 4700.0 * sqrt(30.0)), "E modulus")
    # 38. 4700*sqrt(40) ≈ 29725.41
    assert_true(approx_rel(modulus_of_elasticity(40.0), 4700.0 * sqrt(40.0)), "E modulus 2")

    # 39. splitting_tensile_strength: 0.56*sqrt(30) ≈ 3.0666
    assert_true(approx_rel(splitting_tensile_strength(30.0), 0.56 * sqrt(30.0)), "split tensile")
    # 40. 0.56*sqrt(50) ≈ 3.9598
    assert_true(approx_rel(splitting_tensile_strength(50.0), 0.56 * sqrt(50.0)), "split tensile 2")

    # 41. drying_shrinkage_estimate: (0.5-0.2)*0.001*(1-70/100) = 0.3*0.001*0.3 = 0.00009
    assert_true(approx(drying_shrinkage_estimate(0.5, 70.0), 0.00009), "shrinkage")
    # 42. (0.6-0.2)*0.001*(1-60/100) = 0.4*0.001*0.4 = 0.00016
    assert_true(approx(drying_shrinkage_estimate(0.6, 60.0), 0.00016), "shrinkage 2")

    # 43. carbonation_depth: 5*sqrt(25) = 5*5 = 25 mm
    assert_true(approx(carbonation_depth(5.0, 25.0), 25.0), "carbonation depth")
    # 44. 3*sqrt(16) = 12 mm
    assert_true(approx(carbonation_depth(3.0, 16.0), 12.0), "carbonation depth 2")

    # 45. rebar_development_length: 20*420/(4*0.56*sqrt(30))
    var expected_ld = 20.0 * 420.0 / (4.0 * 0.56 * sqrt(30.0))
    assert_true(approx_rel(rebar_development_length(20.0, 420.0, 30.0), expected_ld), "rebar dev len")

    # 46. concrete_density_estimate: (400+180+1800)*(1-2/100) = 2380*0.98 = 2332.4
    assert_true(approx(concrete_density_estimate(400.0, 180.0, 1800.0, 2.0), 2332.4), "concrete density")
    # 47. (350+160+1850)*(1-1.5/100) = 2360*0.985 = 2324.6
    assert_true(approx(concrete_density_estimate(350.0, 160.0, 1850.0, 1.5), 2324.6), "concrete density 2")

    print("  ✅ concrete: 23 assertions passed")


# ── Lottery Tests ────────────────────────────────────────────────────────────


fn test_lottery() raises:
    print("Testing lottery...")

    # 48. combinations: C(6,2) = 15
    assert_true(approx(combinations(6, 2), 15.0), "C(6,2)")
    # 49. C(49,6) = 13983816
    assert_true(approx(combinations(49, 6), 13983816.0), "C(49,6)")
    # 50. C(10,0) = 1
    assert_true(approx(combinations(10, 0), 1.0), "C(10,0)")
    # 51. C(10,10) = 1
    assert_true(approx(combinations(10, 10), 1.0), "C(10,10)")

    # 52. permutations: P(5,3) = 60
    assert_true(approx(permutations(5, 3), 60.0), "P(5,3)")
    # 53. P(10,2) = 90
    assert_true(approx(permutations(10, 2), 90.0), "P(10,2)")
    # 54. P(5,0) = 1
    assert_true(approx(permutations(5, 0), 1.0), "P(5,0)")

    # 55. lottery_odds: C(49,6)*1 = 13983816
    assert_true(approx(lottery_odds(49, 6, 1), 13983816.0), "lottery odds 6/49")
    # 56. C(69,5)*26 = with bonus
    var c69_5 = combinations(69, 5)
    assert_true(approx(lottery_odds(69, 5, 26), c69_5 * 26.0), "lottery odds powerball")

    # 57. expected_value: 1000000 * (1/13983816) ≈ 0.07151
    var ev1 = expected_value(1000000.0, 1.0 / 13983816.0)
    assert_true(approx_rel(ev1, 1000000.0 / 13983816.0), "EV jackpot")

    # 58. expected_value_net: 0.5 - 2.0 = -1.5
    assert_true(approx(expected_value_net(0.5, 2.0), -1.5), "EV net")
    # 59. 3.0 - 2.0 = 1.0
    assert_true(approx(expected_value_net(3.0, 2.0), 1.0), "EV net positive")

    # 60. house_edge: (2-0.5)/2*100 = 75%
    assert_true(approx(house_edge(0.5, 2.0), 75.0), "house edge")
    # 61. (1-0.95)/1*100 = 5%
    assert_true(approx(house_edge(0.95, 1.0), 5.0), "house edge 5pct")

    # 62. probability_at_least_one_win: 1-(1-0.01)^10
    var p10 = probability_at_least_one_win(0.01, 10)
    var expected_p10 = 1.0 - exp(10.0 * log(0.99))
    assert_true(approx_rel(p10, expected_p10), "prob at least one")
    # 63. n=1 → just p
    assert_true(approx(probability_at_least_one_win(0.5, 1), 0.5), "prob at least one n=1")

    # 64. annuity_vs_lump_sum: 50000*(1-(1.05)^(-20))/0.05
    var pv = annuity_vs_lump_sum(50000.0, 20.0, 0.05)
    var expected_pv = 50000.0 * (1.0 - exp(-20.0 * log(1.05))) / 0.05
    assert_true(approx_rel(pv, expected_pv), "annuity PV")
    # 65. rate=0 → payment*years
    assert_true(approx(annuity_vs_lump_sum(50000.0, 20.0, 0.0), 1000000.0), "annuity PV r=0")

    # 66. tax_after_winnings: 1000000*(1-0.24-0.05) = 710000
    assert_true(approx(tax_after_winnings(1000000.0, 0.24, 0.05), 710000.0), "tax after win")
    # 67. 500000*(1-0.37-0.10) = 265000
    assert_true(approx(tax_after_winnings(500000.0, 0.37, 0.10), 265000.0), "tax after win 2")

    # 68. odds_to_probability: 1/(9+1) = 0.1
    assert_true(approx(odds_to_probability(9.0), 0.1), "odds to prob")
    # 69. 1/(1+1) = 0.5
    assert_true(approx(odds_to_probability(1.0), 0.5), "odds to prob even")

    # 70. probability_to_odds: (1-0.1)/0.1 = 9
    assert_true(approx(probability_to_odds(0.1), 9.0), "prob to odds")
    # 71. (1-0.5)/0.5 = 1
    assert_true(approx(probability_to_odds(0.5), 1.0), "prob to odds even")

    # 72. jackpot_ev_threshold: 13983816 * 2 = 27967632
    assert_true(approx(jackpot_ev_threshold(13983816.0, 2.0), 27967632.0), "jackpot threshold")
    # 73. 292201338 * 2 = 584402676
    assert_true(approx(jackpot_ev_threshold(292201338.0, 2.0), 584402676.0), "jackpot threshold PB")

    print("  ✅ lottery: 26 assertions passed")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=" * 60)
    print("Wave 90 Tests — Hydroponics, Concrete, Lottery")
    print("=" * 60)

    test_hydroponics()
    test_concrete()
    test_lottery()

    print("=" * 60)
    print("All 73 assertions passed ✅")
    print("=" * 60)
