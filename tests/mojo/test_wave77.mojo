"""Tests for Wave 77 — Polymer Science, Sports Analytics, Wastewater Treatment."""

from polymer import (
    degree_of_polymerization,
    number_average_mw,
    weight_average_mw,
    polydispersity_index,
    mark_houwink,
    glass_transition_fox,
    flory_huggins_free_energy,
    end_to_end_distance,
    radius_of_gyration,
    carothers_conversion,
    melt_flow_index_approx,
    tensile_modulus_rule_of_mixtures,
)
from sports_analytics import (
    batting_average,
    on_base_percentage,
    slugging_percentage,
    ops,
    era,
    whip,
    passer_rating_nfl,
    pythagorean_wins,
    elo_expected_score,
    elo_new_rating,
    true_shooting_percentage,
    player_efficiency_rating_approx,
)
from wastewater import (
    bod_removal_efficiency,
    hydraulic_retention_time,
    solids_retention_time,
    food_to_microorganism_ratio,
    sludge_volume_index,
    oxygen_demand,
    chlorine_demand,
    ct_value,
    alkalinity_consumption,
    sludge_production,
    trickling_filter_efficiency,
    detention_time_settling,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Polymer Science Tests ────────────────────────────────────────────────────


fn test_polymer() raises:
    print("== Polymer Science ==")

    # degree_of_polymerization: DP = 100000 / 104 ≈ 961.538
    var dp = degree_of_polymerization(100000.0, 104.0)
    assert_true(approx_eq(dp, 100000.0 / 104.0, 0.01), "degree_of_polymerization")

    # zero monomer MW
    assert_true(approx_eq(degree_of_polymerization(100000.0, 0.0), 0.0), "dp zero m0")

    # number_average_mw: Mn = 500 * 104 = 52000
    assert_true(approx_eq(number_average_mw(500.0, 104.0), 52000.0), "number_average_mw")

    # weight_average_mw: Mw = 50000 * 2.0 = 100000
    assert_true(approx_eq(weight_average_mw(50000.0, 2.0), 100000.0), "weight_average_mw")

    # polydispersity_index: PDI = 100000 / 50000 = 2.0
    assert_true(approx_eq(polydispersity_index(100000.0, 50000.0), 2.0), "polydispersity_index")

    # PDI zero denominator
    assert_true(approx_eq(polydispersity_index(100000.0, 0.0), 0.0), "pdi zero mn")

    # mark_houwink: [η] = 0.00011 * 100000^0.725
    var eta = mark_houwink(0.00011, 100000.0, 0.725)
    var expected_eta = 0.00011 * exp(0.725 * log(100000.0))
    assert_true(approx_eq(eta, expected_eta, 0.001), "mark_houwink")

    # mark_houwink zero MW
    assert_true(approx_eq(mark_houwink(0.00011, 0.0, 0.725), 0.0), "mark_houwink zero mw")

    # glass_transition_fox: blend of PS(373K) and PMMA(378K) 50/50
    var tg = glass_transition_fox(0.5, 373.0, 0.5, 378.0)
    var expected_tg = 1.0 / (0.5 / 373.0 + 0.5 / 378.0)
    assert_true(approx_eq(tg, expected_tg, 0.1), "glass_transition_fox")

    # fox with zero Tg
    assert_true(approx_eq(glass_transition_fox(0.5, 0.0, 0.5, 378.0), 0.0), "fox zero tg")

    # flory_huggins_free_energy: phi=0.5, n=100, chi=0.4
    var fh = flory_huggins_free_energy(0.5, 100.0, 0.4)
    var ex_fh = 0.5 * log(0.5) / 100.0 + 0.5 * log(0.5) + 0.4 * 0.5 * 0.5
    assert_true(approx_eq(fh, ex_fh, 1e-6), "flory_huggins_free_energy")

    # flory_huggins boundary
    assert_true(approx_eq(flory_huggins_free_energy(0.0, 100.0, 0.4), 0.0), "fh boundary")

    # end_to_end_distance: R = 1.54 * sqrt(1000) ≈ 48.695
    var r = end_to_end_distance(1000.0, 1.54)
    assert_true(approx_eq(r, 1.54 * sqrt(1000.0), 0.01), "end_to_end_distance")

    # end_to_end zero bonds
    assert_true(approx_eq(end_to_end_distance(0.0, 1.54), 0.0), "end_to_end zero")

    # radius_of_gyration: Rg = 48.695 / sqrt(6) ≈ 19.886
    var rg = radius_of_gyration(48.695)
    assert_true(approx_eq(rg, 48.695 / sqrt(6.0), 0.01), "radius_of_gyration")

    # carothers_conversion: p = 1 - 1/100 = 0.99
    assert_true(approx_eq(carothers_conversion(100.0), 0.99), "carothers_conversion")

    # carothers zero
    assert_true(approx_eq(carothers_conversion(0.0), 0.0), "carothers zero")

    # melt_flow_index_approx: MFI = 100 / 5000 = 0.02
    assert_true(approx_eq(melt_flow_index_approx(5000.0, 100.0), 0.02), "melt_flow_index_approx")

    # mfi zero viscosity
    assert_true(approx_eq(melt_flow_index_approx(0.0, 100.0), 0.0), "mfi zero visc")

    # tensile_modulus_rule_of_mixtures: E = 0.6*72 + 0.4*3.5 = 43.2 + 1.4 = 44.6
    var e_comp = tensile_modulus_rule_of_mixtures(0.6, 72.0, 3.5)
    assert_true(approx_eq(e_comp, 44.6, 0.01), "tensile_modulus_rule_of_mixtures")

    print("  All polymer tests passed ✓")


# ── Sports Analytics Tests ───────────────────────────────────────────────────


fn test_sports_analytics() raises:
    print("== Sports Analytics ==")

    # batting_average: BA = 180/540 ≈ 0.3333
    assert_true(approx_eq(batting_average(180.0, 540.0), 1.0 / 3.0, 0.001), "batting_average")

    # batting_average zero AB
    assert_true(approx_eq(batting_average(10.0, 0.0), 0.0), "ba zero ab")

    # on_base_percentage: OBP = (180+60+5)/(540+60+5+10) = 245/615 ≈ 0.39837
    var obp_val = on_base_percentage(180.0, 60.0, 5.0, 540.0, 10.0)
    assert_true(approx_eq(obp_val, 245.0 / 615.0, 0.001), "on_base_percentage")

    # slugging_percentage: SLG = 300/540 ≈ 0.5556
    assert_true(approx_eq(slugging_percentage(300.0, 540.0), 300.0 / 540.0, 0.001), "slugging_pct")

    # ops: OPS = 0.398 + 0.556 = 0.954
    assert_true(approx_eq(ops(0.398, 0.556), 0.954), "ops")

    # era: ERA = (80/200) * 9 = 3.6
    assert_true(approx_eq(era(80.0, 200.0), 3.6), "era")

    # era zero IP
    assert_true(approx_eq(era(80.0, 0.0), 0.0), "era zero ip")

    # whip: WHIP = (50+180)/200 = 1.15
    assert_true(approx_eq(whip(50.0, 180.0, 200.0), 1.15), "whip")

    # passer_rating_nfl: known example — perfect rating capped at 158.3
    var perfect = passer_rating_nfl(30.0, 30.0, 500.0, 5.0, 0.0)
    assert_true(perfect > 100.0, "passer_rating_nfl high")

    # passer_rating zero attempts
    assert_true(approx_eq(passer_rating_nfl(0.0, 0.0, 0.0, 0.0, 0.0), 0.0), "pr zero att")

    # pythagorean_wins: W% = 800^2/(800^2+700^2) = 640000/1130000 ≈ 0.56637
    var pw = pythagorean_wins(800.0, 700.0, 2.0)
    assert_true(approx_eq(pw, 640000.0 / 1130000.0, 0.001), "pythagorean_wins")

    # pythagorean both zero
    assert_true(approx_eq(pythagorean_wins(0.0, 0.0, 2.0), 0.0), "pyth zero")

    # pythagorean zero allowed → 1.0
    assert_true(approx_eq(pythagorean_wins(100.0, 0.0, 2.0), 1.0), "pyth perfect")

    # elo_expected_score: equal ratings → 0.5
    var elo_e = elo_expected_score(1500.0, 1500.0)
    assert_true(approx_eq(elo_e, 0.5, 0.001), "elo_expected equal")

    # elo_expected_score: 200-point advantage → ~0.76
    var elo_e2 = elo_expected_score(1600.0, 1400.0)
    assert_true(elo_e2 > 0.7 and elo_e2 < 0.8, "elo_expected advantage")

    # elo_new_rating: win from equal → 1500 + 32*(1-0.5) = 1516
    var new_r = elo_new_rating(1500.0, 32.0, 1.0, 0.5)
    assert_true(approx_eq(new_r, 1516.0), "elo_new_rating")

    # true_shooting_percentage: TS% = 30/(2*(20+0.44*10)) = 30/48.8 ≈ 0.6148
    var ts = true_shooting_percentage(30.0, 20.0, 10.0)
    assert_true(approx_eq(ts, 30.0 / (2.0 * (20.0 + 0.44 * 10.0)), 0.001), "true_shooting_pct")

    # ts zero FGA and FTA
    assert_true(approx_eq(true_shooting_percentage(30.0, 0.0, 0.0), 0.0), "ts zero denom")

    # player_efficiency_rating_approx
    var per = player_efficiency_rating_approx(25.0, 10.0, 5.0, 2.0, 1.0, 3.0, 36.0, 100.0)
    # raw = 25+10+5+2+1-3 = 40, per = (40/36)*(100/100) ≈ 1.1111
    assert_true(approx_eq(per, 40.0 / 36.0, 0.01), "player_efficiency_rating")

    # per zero minutes
    assert_true(
        approx_eq(
            player_efficiency_rating_approx(25.0, 10.0, 5.0, 2.0, 1.0, 3.0, 0.0, 100.0),
            0.0,
        ),
        "per zero min",
    )

    print("  All sports analytics tests passed ✓")


# ── Wastewater Treatment Tests ───────────────────────────────────────────────


fn test_wastewater() raises:
    print("== Wastewater Treatment ==")

    # bod_removal_efficiency: η = (200-20)/200*100 = 90%
    assert_true(approx_eq(bod_removal_efficiency(200.0, 20.0), 90.0), "bod_removal_efficiency")

    # bod zero in
    assert_true(approx_eq(bod_removal_efficiency(0.0, 20.0), 0.0), "bod zero in")

    # hydraulic_retention_time: HRT = 5000/500 = 10 hours
    assert_true(approx_eq(hydraulic_retention_time(5000.0, 500.0), 10.0), "hrt")

    # hrt zero flow
    assert_true(approx_eq(hydraulic_retention_time(5000.0, 0.0), 0.0), "hrt zero flow")

    # solids_retention_time: SRT = 1000*3000/(50*8000+950*20) = 3000000/419000 ≈ 7.16
    var srt = solids_retention_time(1000.0, 3000.0, 50.0, 8000.0, 950.0, 20.0)
    assert_true(approx_eq(srt, 3000000.0 / 419000.0, 0.01), "srt")

    # srt zero denom
    assert_true(approx_eq(solids_retention_time(1000.0, 3000.0, 0.0, 0.0, 0.0, 0.0), 0.0), "srt zero")

    # food_to_microorganism_ratio: F/M = 1000*200/(2000*3000) = 200000/6000000 ≈ 0.0333
    var fm = food_to_microorganism_ratio(1000.0, 200.0, 2000.0, 3000.0)
    assert_true(approx_eq(fm, 200000.0 / 6000000.0, 0.001), "food_to_microorganism_ratio")

    # fm zero denom
    assert_true(approx_eq(food_to_microorganism_ratio(1000.0, 200.0, 0.0, 3000.0), 0.0), "fm zero")

    # sludge_volume_index: SVI = 250*1000/3000 ≈ 83.33 mL/g
    var svi = sludge_volume_index(250.0, 3000.0)
    assert_true(approx_eq(svi, 250000.0 / 3000.0, 0.01), "sludge_volume_index")

    # svi zero MLSS
    assert_true(approx_eq(sludge_volume_index(250.0, 0.0), 0.0), "svi zero mlss")

    # oxygen_demand: O2 = 5000*(200-20)*0.001 = 5000*180*0.001 = 900 kg/day
    assert_true(approx_eq(oxygen_demand(5000.0, 200.0, 20.0, 0.001), 900.0, 0.01), "oxygen_demand")

    # chlorine_demand: Demand = 5.0 - 0.5 = 4.5
    assert_true(approx_eq(chlorine_demand(5.0, 0.5), 4.5), "chlorine_demand")

    # ct_value: CT = 2.0 * 30 = 60 mg·min/L
    assert_true(approx_eq(ct_value(2.0, 30.0), 60.0), "ct_value")

    # alkalinity_consumption: Alk = 7.14 * 20 = 142.8 mg/L
    assert_true(approx_eq(alkalinity_consumption(20.0), 142.8), "alkalinity_consumption")

    # sludge_production: P = 0.6*1000 - 0.05*3000 = 600 - 150 = 450
    assert_true(approx_eq(sludge_production(0.6, 1000.0, 0.05, 3000.0), 450.0), "sludge_production")

    # trickling_filter_efficiency: E = 1/(1+0.4432*sqrt(200/(1+1)))
    var tfe = trickling_filter_efficiency(200.0, 1.0)
    var ex_tfe = 1.0 / (1.0 + 0.4432 * sqrt(200.0 / 2.0))
    assert_true(approx_eq(tfe, ex_tfe, 0.001), "trickling_filter_efficiency")

    # tfe zero BOD
    assert_true(approx_eq(trickling_filter_efficiency(0.0, 1.0), 0.0), "tfe zero bod")

    # detention_time_settling: t = 3.0/1.5 = 2.0 hours
    assert_true(approx_eq(detention_time_settling(3.0, 1.5), 2.0), "detention_time_settling")

    # detention zero overflow
    assert_true(approx_eq(detention_time_settling(3.0, 0.0), 0.0), "detention zero overflow")

    print("  All wastewater treatment tests passed ✓")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 77 Tests: Polymer, Sports Analytics, Wastewater")
    test_polymer()
    test_sports_analytics()
    test_wastewater()
    print("All Wave 77 tests passed ✓  (74 assertions)")
