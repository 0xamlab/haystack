"""Tests for Wave 79 — Food Science, Cryogenics, Urban Planning."""

from food_science import (
    water_activity,
    ph_from_h_concentration,
    shelf_life_q10,
    thermal_death_time,
    d_value_from_z,
    pasteurization_units,
    brix_to_sugar_g_per_l,
    caloric_density,
    moisture_content_wet_basis,
    moisture_content_dry_basis,
    freezing_point_depression,
    blanching_time_estimate,
)
from cryogenics import (
    ideal_gas_density,
    joule_thomson_cooling,
    carnot_cop_cooling,
    liquefaction_yield,
    boiloff_rate,
    thermal_contraction,
    heat_leak_through_wall,
    superconductor_critical_temp_estimate,
    residual_resistivity_ratio,
    cryocooler_input_power,
    vacuum_insulation_heat_flux,
    helium_lambda_point,
)
from urban_planning import (
    population_density,
    floor_area_ratio,
    lot_coverage,
    green_space_ratio,
    walk_score_distance_decay,
    vehicle_miles_traveled,
    parking_requirement,
    traffic_level_of_service,
    housing_affordability_ratio,
    jobs_housing_balance,
    infrastructure_cost_per_unit,
    impervious_surface_ratio,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Food Science Tests ───────────────────────────────────────────────────────


fn test_food_science() raises:
    print("== Food Science Tests ==")

    # water_activity
    assert_true(approx_eq(water_activity(0.95), 0.95), "water_activity 0.95")
    assert_true(approx_eq(water_activity(1.0), 1.0), "water_activity 1.0")
    assert_true(approx_eq(water_activity(0.0), 0.0), "water_activity 0.0")

    # ph_from_h_concentration: pH = -log10([H+])
    # [H+] = 1e-7 => pH = 7.0
    assert_true(approx_eq(ph_from_h_concentration(1e-7), 7.0, 1e-4), "pH 1e-7")
    # [H+] = 1e-3 => pH = 3.0
    assert_true(approx_eq(ph_from_h_concentration(1e-3), 3.0, 1e-4), "pH 1e-3")
    # [H+] = 1.0 => pH = 0.0
    assert_true(approx_eq(ph_from_h_concentration(1.0), 0.0, 1e-4), "pH 1.0")

    # shelf_life_q10: base=100, q10=2, ΔT=10 => 100/2^1 = 50
    assert_true(approx_eq(shelf_life_q10(100.0, 2.0, 10.0), 50.0, 1e-4), "shelf_life q10 ΔT10")
    # base=100, q10=2, ΔT=20 => 100/2^2 = 25
    assert_true(approx_eq(shelf_life_q10(100.0, 2.0, 20.0), 25.0, 1e-4), "shelf_life q10 ΔT20")
    # base=100, q10=2, ΔT=0 => 100/1 = 100
    assert_true(approx_eq(shelf_life_q10(100.0, 2.0, 0.0), 100.0, 1e-4), "shelf_life q10 ΔT0")

    # thermal_death_time: D=2.5, log_red=5 => 12.5
    assert_true(approx_eq(thermal_death_time(2.5, 5.0), 12.5), "thermal_death_time")
    assert_true(approx_eq(thermal_death_time(1.0, 12.0), 12.0), "thermal_death_time 12")

    # d_value_from_z: D_ref=1, z=10, temp=121, ref=121 => D=1
    assert_true(approx_eq(d_value_from_z(1.0, 10.0, 121.0, 121.0), 1.0, 1e-4), "d_value same temp")
    # D_ref=1, z=10, temp=131, ref=121 => D = 1 * 10^((121-131)/10) = 0.1
    assert_true(approx_eq(d_value_from_z(1.0, 10.0, 131.0, 121.0), 0.1, 1e-4), "d_value +10")

    # pasteurization_units: t=1, T=72, z=7, ref=60 => 1 * 10^(12/7)
    var pu_expected = exp(12.0 / 7.0 * log(10.0))
    assert_true(approx_eq(pasteurization_units(1.0, 72.0, 7.0, 60.0), pu_expected, 1e-3), "PU")
    # t=1, T=60, z=7, ref=60 => 1 * 10^0 = 1
    assert_true(approx_eq(pasteurization_units(1.0, 60.0, 7.0, 60.0), 1.0, 1e-4), "PU ref")

    # brix_to_sugar_g_per_l: 10 Brix => 100 g/L
    assert_true(approx_eq(brix_to_sugar_g_per_l(10.0), 100.0), "brix 10")
    assert_true(approx_eq(brix_to_sugar_g_per_l(0.0), 0.0), "brix 0")

    # caloric_density: 10P + 5F + 20C + 2A = 40+45+80+14 = 179
    assert_true(approx_eq(caloric_density(10.0, 5.0, 20.0, 2.0), 179.0), "caloric_density")
    assert_true(approx_eq(caloric_density(0.0, 0.0, 0.0, 0.0), 0.0), "caloric_density zero")

    # moisture_content_wet_basis: 20 water / 100 total = 20%
    assert_true(approx_eq(moisture_content_wet_basis(20.0, 100.0), 20.0), "MC wet")
    assert_true(approx_eq(moisture_content_wet_basis(50.0, 100.0), 50.0), "MC wet 50")

    # moisture_content_dry_basis: 20 water / 80 dry = 25%
    assert_true(approx_eq(moisture_content_dry_basis(20.0, 80.0), 25.0), "MC dry")

    # freezing_point_depression: Kf=1.86, m=0.5 => 0.93
    assert_true(approx_eq(freezing_point_depression(1.86, 0.5), 0.93), "FPD")
    assert_true(approx_eq(freezing_point_depression(1.86, 0.0), 0.0), "FPD zero")

    # blanching_time_estimate: thickness=10mm, D=0.25 => 100/(4*0.25)=100
    assert_true(approx_eq(blanching_time_estimate(10.0, 0.25), 100.0), "blanching")
    assert_true(approx_eq(blanching_time_estimate(5.0, 0.25), 25.0), "blanching 5mm")

    print("  ✓ All food science tests passed")


# ── Cryogenics Tests ─────────────────────────────────────────────────────────


fn test_cryogenics() raises:
    print("== Cryogenics Tests ==")

    # ideal_gas_density: P=101325, M=0.028, R=8.314, T=300 => 101325*0.028/(8.314*300)
    var rho = 101325.0 * 0.028 / (8.314 * 300.0)
    assert_true(approx_eq(ideal_gas_density(101325.0, 0.028, 8.314, 300.0), rho, 1e-3), "ideal_gas_density")

    # joule_thomson_cooling: mu=0.25, dP=-500 => -125
    assert_true(approx_eq(joule_thomson_cooling(0.25, -500.0), -125.0), "JT cooling")
    assert_true(approx_eq(joule_thomson_cooling(0.0, -500.0), 0.0), "JT zero mu")

    # carnot_cop_cooling: Tc=77, Th=300 => 77/(300-77) = 77/223
    var cop_expected = 77.0 / 223.0
    assert_true(approx_eq(carnot_cop_cooling(77.0, 300.0), cop_expected, 1e-6), "carnot COP")

    # liquefaction_yield: h1=500, h2=300, hf=100, hg=400 => (500-300)/400 = 0.5
    assert_true(approx_eq(liquefaction_yield(500.0, 300.0, 100.0, 400.0), 0.5), "liq yield")

    # boiloff_rate: Q=10, L=200, m=1000 => 10/(200*1000)*100 = 0.005
    assert_true(approx_eq(boiloff_rate(10.0, 200.0, 1000.0), 0.005, 1e-6), "BOR")

    # thermal_contraction: α=1.2e-5, ΔT=-200, L=1.0 => -0.0024
    assert_true(approx_eq(thermal_contraction(1.2e-5, -200.0, 1.0), -0.0024, 1e-8), "thermal contraction")

    # heat_leak_through_wall: k=0.04, A=10, Th=300, Tc=77, d=0.1 => 0.04*10*223/0.1 = 892
    assert_true(approx_eq(heat_leak_through_wall(0.04, 10.0, 300.0, 77.0, 0.1), 892.0, 1e-3), "heat leak")

    # superconductor_critical_temp_estimate: Tc0=9.2, H=0, Hc2=10 => 9.2*sqrt(1) = 9.2
    assert_true(approx_eq(superconductor_critical_temp_estimate(9.2, 0.0, 10.0), 9.2, 1e-6), "Tc no field")
    # Tc0=9.2, H=5, Hc2=10 => 9.2*sqrt(0.5)
    var tc_half = 9.2 * sqrt(0.5)
    assert_true(approx_eq(superconductor_critical_temp_estimate(9.2, 5.0, 10.0), tc_half, 1e-6), "Tc half field")

    # residual_resistivity_ratio: R300=100, Rlow=0.5 => 200
    assert_true(approx_eq(residual_resistivity_ratio(100.0, 0.5), 200.0), "RRR")

    # cryocooler_input_power: Q=50, COP=0.1 => 500
    assert_true(approx_eq(cryocooler_input_power(50.0, 0.1), 500.0), "cryocooler power")

    # vacuum_insulation_heat_flux: ε1=0.05, ε2=0.05, σ=5.67e-8, Th=300, Tc=77
    var th4 = 300.0 * 300.0 * 300.0 * 300.0
    var tc4 = 77.0 * 77.0 * 77.0 * 77.0
    var denom = 1.0 / 0.05 + 1.0 / 0.05 - 1.0  # 20+20-1=39
    var q_expected = 5.67e-8 * (th4 - tc4) / denom
    assert_true(approx_eq(vacuum_insulation_heat_flux(0.05, 0.05, 5.67e-8, 300.0, 77.0), q_expected, 1e-3), "vacuum heat flux")

    # helium_lambda_point
    assert_true(approx_eq(helium_lambda_point(), 2.17, 1e-6), "He lambda point")

    print("  ✓ All cryogenics tests passed")


# ── Urban Planning Tests ─────────────────────────────────────────────────────


fn test_urban_planning() raises:
    print("== Urban Planning Tests ==")

    # population_density: 50000 people / 25 sq km = 2000
    assert_true(approx_eq(population_density(50000.0, 25.0), 2000.0), "pop density")

    # floor_area_ratio: 10000 floor / 5000 plot = 2.0
    assert_true(approx_eq(floor_area_ratio(10000.0, 5000.0), 2.0), "FAR")

    # lot_coverage: 500 footprint / 1000 lot = 50%
    assert_true(approx_eq(lot_coverage(500.0, 1000.0), 50.0), "lot coverage")

    # green_space_ratio: 30 green / 100 total = 30%
    assert_true(approx_eq(green_space_ratio(30.0, 100.0), 30.0), "green space")

    # walk_score_distance_decay: 200m, max=400 => 0.5
    assert_true(approx_eq(walk_score_distance_decay(200.0, 400.0), 0.5), "walk score 200")
    # at max => 0.0
    assert_true(approx_eq(walk_score_distance_decay(400.0, 400.0), 0.0), "walk score max")
    # beyond max => 0.0
    assert_true(approx_eq(walk_score_distance_decay(600.0, 400.0), 0.0), "walk score beyond")
    # at origin => 1.0
    assert_true(approx_eq(walk_score_distance_decay(0.0, 400.0), 1.0), "walk score 0")

    # vehicle_miles_traveled: 1000 trips * 8.5 miles = 8500
    assert_true(approx_eq(vehicle_miles_traveled(1000.0, 8.5), 8500.0), "VMT")

    # parking_requirement: 200 units * 1.5 spaces = 300
    assert_true(approx_eq(parking_requirement(200.0, 1.5), 300.0), "parking")

    # traffic_level_of_service: 1500 vol / 2000 cap = 0.75
    assert_true(approx_eq(traffic_level_of_service(1500.0, 2000.0), 0.75), "LOS")

    # housing_affordability_ratio: 400000 / 80000 = 5.0
    assert_true(approx_eq(housing_affordability_ratio(400000.0, 80000.0), 5.0), "HAR")

    # jobs_housing_balance: 5000 / 4000 = 1.25
    assert_true(approx_eq(jobs_housing_balance(5000.0, 4000.0), 1.25), "JHB")

    # infrastructure_cost_per_unit: 1000000 / 500 = 2000
    assert_true(approx_eq(infrastructure_cost_per_unit(1000000.0, 500.0), 2000.0), "infra cost")

    # impervious_surface_ratio: 60 / 100 = 60%
    assert_true(approx_eq(impervious_surface_ratio(60.0, 100.0), 60.0), "ISR")

    print("  ✓ All urban planning tests passed")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    test_food_science()
    test_cryogenics()
    test_urban_planning()
    print("Wave 79: All tests passed ✓")
