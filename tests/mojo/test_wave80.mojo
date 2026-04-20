"""Tests for Wave 80 — Soil Science, Autonomous Vehicles, Insurance."""

from soil_science import (
    soil_texture_sand_silt_clay,
    bulk_density,
    particle_density_typical,
    total_porosity,
    volumetric_water_content,
    gravimetric_water_content,
    field_capacity_estimate,
    wilting_point_estimate,
    available_water,
    cation_exchange_capacity_estimate,
    soil_organic_carbon,
    infiltration_rate_horton,
)
from autonomous_vehicles import (
    safe_following_distance,
    time_to_collision,
    braking_distance,
    sensor_range_required,
    lane_change_distance,
    perception_latency_distance,
    comfort_deceleration,
    emergency_deceleration,
    headway_time,
    fuel_efficiency_at_speed,
    v2x_communication_range,
    localization_error_gps,
)
from insurance import (
    pure_premium,
    gross_premium,
    loss_ratio,
    expense_ratio,
    combined_ratio,
    expected_claim_frequency,
    expected_claim_severity,
    burning_cost,
    credibility_buhlmann,
    risk_load,
    aggregate_deductible_savings,
    retention_rate,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Soil Science Tests ───────────────────────────────────────────────────────


fn test_soil_science() raises:
    print("== Soil Science Tests ==")

    # soil_texture_sand_silt_clay — valid textures
    assert_true(soil_texture_sand_silt_clay(40.0, 40.0, 20.0), "texture 40/40/20")
    assert_true(soil_texture_sand_silt_clay(33.3, 33.3, 33.4), "texture thirds")
    assert_true(soil_texture_sand_silt_clay(100.0, 0.0, 0.0), "texture pure sand")
    # invalid texture — sum = 90
    assert_false(soil_texture_sand_silt_clay(30.0, 30.0, 30.0), "texture 30/30/30 invalid")
    # within tolerance — sum = 100.5
    assert_true(soil_texture_sand_silt_clay(50.0, 30.0, 20.5), "texture within tol")

    # bulk_density: 1500g / 1000cm³ = 1.5 g/cm³
    assert_true(approx_eq(bulk_density(1500.0, 1000.0), 1.5), "bulk density 1.5")
    assert_true(approx_eq(bulk_density(1300.0, 1000.0), 1.3), "bulk density 1.3")

    # particle_density_typical
    assert_true(approx_eq(particle_density_typical(), 2.65), "particle density 2.65")

    # total_porosity: n = 1 - 1.5/2.65
    var n_expected = 1.0 - 1.5 / 2.65
    assert_true(approx_eq(total_porosity(1.5, 2.65), n_expected), "porosity")
    # fully dense => porosity 0
    assert_true(approx_eq(total_porosity(2.65, 2.65), 0.0), "porosity zero")

    # volumetric_water_content: 300/1000 = 0.3
    assert_true(approx_eq(volumetric_water_content(300.0, 1000.0), 0.3), "VWC 0.3")
    assert_true(approx_eq(volumetric_water_content(0.0, 1000.0), 0.0), "VWC zero")

    # gravimetric_water_content: 200/800 = 0.25
    assert_true(approx_eq(gravimetric_water_content(200.0, 800.0), 0.25), "GWC 0.25")

    # field_capacity_estimate: clay=30% => 0.15 + 0.005*30 = 0.30
    assert_true(approx_eq(field_capacity_estimate(30.0), 0.30), "FC clay30")
    assert_true(approx_eq(field_capacity_estimate(0.0), 0.15), "FC clay0")

    # wilting_point_estimate: clay=30% => 0.04 + 0.003*30 = 0.13
    assert_true(approx_eq(wilting_point_estimate(30.0), 0.13), "WP clay30")
    assert_true(approx_eq(wilting_point_estimate(0.0), 0.04), "WP clay0")

    # available_water: (0.30-0.13)*100/100 = 0.17
    assert_true(approx_eq(available_water(0.30, 0.13, 100.0), 0.17), "AW 100cm")
    # depth 50cm => 0.085
    assert_true(approx_eq(available_water(0.30, 0.13, 50.0), 0.085), "AW 50cm")

    # cation_exchange_capacity_estimate: 0.5*30+2.0*5 = 15+10 = 25
    assert_true(approx_eq(cation_exchange_capacity_estimate(30.0, 5.0), 25.0), "CEC 30/5")
    assert_true(approx_eq(cation_exchange_capacity_estimate(0.0, 0.0), 0.0), "CEC zero")

    # soil_organic_carbon: 3.0/1.724 ≈ 1.7401
    assert_true(approx_eq(soil_organic_carbon(3.0), 3.0 / 1.724, 1e-4), "SOC 3%")
    assert_true(approx_eq(soil_organic_carbon(0.0), 0.0), "SOC zero")

    # infiltration_rate_horton: f0=100, fc=10, k=2, t=0 => 10+(100-10)*1=100
    assert_true(approx_eq(infiltration_rate_horton(100.0, 10.0, 2.0, 0.0), 100.0), "Horton t=0")
    # t→∞ (large t=100): fc + (f0-fc)*exp(-200) ≈ fc = 10
    assert_true(approx_eq(infiltration_rate_horton(100.0, 10.0, 2.0, 100.0), 10.0, 1e-3), "Horton t=inf")
    # t=1: 10 + 90*exp(-2) ≈ 10 + 90*0.13534 ≈ 22.18
    var h1_expected = 10.0 + 90.0 * exp(-2.0)
    assert_true(approx_eq(infiltration_rate_horton(100.0, 10.0, 2.0, 1.0), h1_expected, 1e-4), "Horton t=1")

    print("  ✓ All soil science tests passed")


# ── Autonomous Vehicles Tests ────────────────────────────────────────────────


fn test_autonomous_vehicles() raises:
    print("== Autonomous Vehicles Tests ==")

    # safe_following_distance: v=30, t=1.5, a=5 => 30*1.5 + 900/10 = 45+90=135
    assert_true(approx_eq(safe_following_distance(30.0, 1.5, 5.0), 135.0), "SFD 30mps")
    # v=0 => 0
    assert_true(approx_eq(safe_following_distance(0.0, 1.5, 5.0), 0.0), "SFD zero speed")

    # time_to_collision: d=50, v_rel=10 => 5.0s
    assert_true(approx_eq(time_to_collision(50.0, 10.0), 5.0), "TTC 5s")
    assert_true(approx_eq(time_to_collision(100.0, 25.0), 4.0), "TTC 4s")
    # v_rel<=0 => -1
    assert_true(approx_eq(time_to_collision(50.0, 0.0), -1.0), "TTC no approach")
    assert_true(approx_eq(time_to_collision(50.0, -5.0), -1.0), "TTC diverging")

    # braking_distance: v=30, μ=0.7, G=0 => 900/(2*9.81*0.7) = 900/13.734 ≈ 65.53
    var bd_exp = 900.0 / (2.0 * 9.81 * 0.7)
    assert_true(approx_eq(braking_distance(30.0, 0.7, 0.0), bd_exp, 1e-2), "BD flat")
    # with grade=0.05 => 900/(2*9.81*0.75) = 900/14.715 ≈ 61.16
    var bd_grade = 900.0 / (2.0 * 9.81 * 0.75)
    assert_true(approx_eq(braking_distance(30.0, 0.7, 0.05), bd_grade, 1e-2), "BD uphill")

    # sensor_range_required: same formula as safe_following_distance
    assert_true(approx_eq(sensor_range_required(30.0, 1.5, 5.0), 135.0), "SR 30mps")

    # lane_change_distance: v=20, a_lat=2.0, w=3.5 => 20*sqrt(2*3.5/2.0)=20*sqrt(3.5)
    var lcd_exp = 20.0 * sqrt(3.5)
    assert_true(approx_eq(lane_change_distance(20.0, 2.0, 3.5), lcd_exp, 1e-4), "LCD")

    # perception_latency_distance: v=30, latency=100ms => 30*0.1=3.0
    assert_true(approx_eq(perception_latency_distance(30.0, 100.0), 3.0), "PLD 100ms")
    assert_true(approx_eq(perception_latency_distance(30.0, 0.0), 0.0), "PLD 0ms")

    # comfort_deceleration
    assert_true(approx_eq(comfort_deceleration(), 3.0), "comfort decel")

    # emergency_deceleration
    assert_true(approx_eq(emergency_deceleration(), 8.0), "emergency decel")

    # headway_time: d=60, v=30 => 2.0s
    assert_true(approx_eq(headway_time(60.0, 30.0), 2.0), "THW 2s")
    assert_true(approx_eq(headway_time(30.0, 30.0), 1.0), "THW 1s")

    # fuel_efficiency_at_speed: base=15, speed=90, opt=90 => 15*(1-0)=15
    assert_true(approx_eq(fuel_efficiency_at_speed(15.0, 90.0, 90.0), 15.0), "FE optimal")
    # base=15, speed=100, opt=90 => 15*(1-0.01*100/90) = 15*(1-1/90*100/100)
    var fe_exp = 15.0 * (1.0 - 0.01 * 100.0 / 90.0)
    assert_true(approx_eq(fuel_efficiency_at_speed(15.0, 100.0, 90.0), fe_exp, 1e-4), "FE +10")

    # v2x_communication_range: (10/1e9)^(1/2)
    var v2x_exp = exp(log(10.0 / 1e9) / 2.0)
    assert_true(approx_eq(v2x_communication_range(10.0, 1e9, 2.0), v2x_exp, 1e-10), "V2X range")

    # localization_error_gps: hdop=1.2, uere=6.0 => 7.2
    assert_true(approx_eq(localization_error_gps(1.2, 6.0), 7.2), "GPS error 7.2")
    assert_true(approx_eq(localization_error_gps(2.0, 6.0), 12.0), "GPS error 12.0")

    print("  ✓ All autonomous vehicles tests passed")


# ── Insurance Tests ──────────────────────────────────────────────────────────


fn test_insurance() raises:
    print("== Insurance Tests ==")

    # pure_premium: 500000/1000 = 500
    assert_true(approx_eq(pure_premium(500000.0, 1000.0), 500.0), "PP 500")

    # gross_premium: 500/(1-0.25-0.05) = 500/0.70 ≈ 714.2857
    assert_true(approx_eq(gross_premium(500.0, 0.25, 0.05), 500.0 / 0.70, 1e-3), "GP")
    # no expense/profit: 500/1.0 = 500
    assert_true(approx_eq(gross_premium(500.0, 0.0, 0.0), 500.0), "GP no load")

    # loss_ratio: 700000/1000000 = 0.70
    assert_true(approx_eq(loss_ratio(700000.0, 1000000.0), 0.70), "LR 0.70")

    # expense_ratio: 250000/1000000 = 0.25
    assert_true(approx_eq(expense_ratio(250000.0, 1000000.0), 0.25), "ER 0.25")

    # combined_ratio: 0.70 + 0.25 = 0.95
    assert_true(approx_eq(combined_ratio(0.70, 0.25), 0.95), "CR 0.95")
    # over 1 = underwriting loss
    assert_true(approx_eq(combined_ratio(0.80, 0.25), 1.05), "CR 1.05")

    # expected_claim_frequency: 50/1000 = 0.05
    assert_true(approx_eq(expected_claim_frequency(50.0, 1000.0), 0.05), "freq 0.05")

    # expected_claim_severity: 500000/50 = 10000
    assert_true(approx_eq(expected_claim_severity(500000.0, 50.0), 10000.0), "severity 10k")

    # burning_cost: 500000/100000 = 5.0
    assert_true(approx_eq(burning_cost(500000.0, 100000.0), 5.0), "BC 5.0")

    # credibility_buhlmann: n=10, k=5 => 10/15 = 0.6667
    assert_true(approx_eq(credibility_buhlmann(10.0, 5.0), 10.0 / 15.0, 1e-4), "cred 10/5")
    # n=100, k=5 => 100/105 ≈ 0.9524
    assert_true(approx_eq(credibility_buhlmann(100.0, 5.0), 100.0 / 105.0, 1e-4), "cred 100/5")
    # n=0 => 0
    assert_true(approx_eq(credibility_buhlmann(0.0, 5.0), 0.0), "cred zero")

    # risk_load: variance=10000, λ=0.02 => 200
    assert_true(approx_eq(risk_load(10000.0, 0.02), 200.0), "RL 200")
    assert_true(approx_eq(risk_load(0.0, 0.02), 0.0), "RL zero var")

    # aggregate_deductible_savings: ded=500, freq=0.05, avg=800 => min(500,800)*0.05=25
    assert_true(approx_eq(aggregate_deductible_savings(500.0, 0.05, 800.0), 25.0), "ded savings capped")
    # ded=1000, freq=0.05, avg=800 => min(1000,800)*0.05=40
    assert_true(approx_eq(aggregate_deductible_savings(1000.0, 0.05, 800.0), 40.0), "ded savings full")
    # ded=800, freq=0.05, avg=800 => 800*0.05=40
    assert_true(approx_eq(aggregate_deductible_savings(800.0, 0.05, 800.0), 40.0), "ded savings equal")

    # retention_rate: 900/1000*100 = 90%
    assert_true(approx_eq(retention_rate(900.0, 1000.0), 90.0), "RR 90%")
    assert_true(approx_eq(retention_rate(1000.0, 1000.0), 100.0), "RR 100%")

    print("  ✓ All insurance tests passed")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    test_soil_science()
    test_autonomous_vehicles()
    test_insurance()
    print("Wave 80: All tests passed ✓")
