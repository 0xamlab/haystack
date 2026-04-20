"""Tests for Wave 83 — Battery, Fisheries, Museum."""

from battery import (
    state_of_charge,
    depth_of_discharge,
    coulombic_efficiency,
    energy_density,
    power_density,
    c_rate,
    discharge_time,
    peukert_capacity,
    cycle_life_degradation,
    internal_resistance_from_voltage,
    battery_pack_voltage,
    battery_pack_capacity,
)
from fisheries import (
    catch_per_unit_effort,
    maximum_sustainable_yield,
    biomass_at_msy,
    schaefer_surplus_production,
    fishing_mortality,
    total_mortality,
    exploitation_rate,
    survival_rate,
    von_bertalanffy_length,
    condition_factor,
    gonadosomatic_index,
    stock_recruitment_bevholt,
)
from museum import (
    lux_hours_annual,
    uv_exposure,
    relative_humidity_from_temps,
    moisture_content_equilibrium,
    time_weighted_preservation_index,
    light_damage_reciprocity,
    climate_stability_score,
    storage_density,
    collection_growth_rate,
    insurance_value_appreciation,
    visitor_density,
    conservation_priority_score,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, exp


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


fn rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Battery Technology Tests ─────────────────────────────────────────────────


fn test_battery() raises:
    # state_of_charge: 75/100 = 75%
    assert_true(approx_eq(state_of_charge(75.0, 100.0), 75.0), "soc 75/100")
    assert_true(approx_eq(state_of_charge(50.0, 200.0), 25.0), "soc 50/200")
    assert_true(approx_eq(state_of_charge(10.0, 0.0), 0.0), "soc zero max")

    # depth_of_discharge: DOD = 100 - SOC
    assert_true(approx_eq(depth_of_discharge(75.0), 25.0), "dod 75")
    assert_true(approx_eq(depth_of_discharge(100.0), 0.0), "dod 100")
    assert_true(approx_eq(depth_of_discharge(0.0), 100.0), "dod 0")

    # coulombic_efficiency: 95/100 = 95%
    assert_true(approx_eq(coulombic_efficiency(95.0, 100.0), 95.0), "ce 95/100")
    assert_true(approx_eq(coulombic_efficiency(48.0, 50.0), 96.0), "ce 48/50")
    assert_true(approx_eq(coulombic_efficiency(10.0, 0.0), 0.0), "ce zero chg")

    # energy_density: 500Wh / 2kg = 250 Wh/kg
    assert_true(approx_eq(energy_density(500.0, 2.0), 250.0), "ed 500/2")
    assert_true(approx_eq(energy_density(100.0, 0.0), 0.0), "ed zero mass")

    # power_density: 1000W / 5kg = 200 W/kg
    assert_true(approx_eq(power_density(1000.0, 5.0), 200.0), "pd 1000/5")
    assert_true(approx_eq(power_density(100.0, 0.0), 0.0), "pd zero mass")

    # c_rate: 10A / 5Ah = 2C
    assert_true(approx_eq(c_rate(10.0, 5.0), 2.0), "crate 10/5")
    assert_true(approx_eq(c_rate(5.0, 10.0), 0.5), "crate 5/10")

    # discharge_time: 10Ah / 2A = 5 hours
    assert_true(approx_eq(discharge_time(10.0, 2.0), 5.0), "dt 10/2")
    assert_true(approx_eq(discharge_time(10.0, 0.0), 0.0), "dt zero current")

    # peukert_capacity: k=1 means ratio^0 = 1, so C = rated
    assert_true(rel_eq(peukert_capacity(100.0, 20.0, 5.0, 1.0), 100.0), "peukert k=1")
    # k=1.2, rated=100Ah, rated_hours=20, actual_rate=10A
    # ratio = 20*10/100 = 2.0, C = 100 * 2^0.2
    assert_true(peukert_capacity(100.0, 20.0, 10.0, 1.2) > 100.0, "peukert k=1.2 > rated")

    # cycle_life_degradation: 100 * (1 - 0.001*500) = 100*0.5 = 50
    assert_true(approx_eq(cycle_life_degradation(100.0, 500.0, 0.001), 50.0), "cyc 500@0.001")
    assert_true(approx_eq(cycle_life_degradation(100.0, 0.0, 0.001), 100.0), "cyc 0 cycles")
    # full degradation caps at 0
    assert_true(approx_eq(cycle_life_degradation(100.0, 2000.0, 0.001), 0.0), "cyc overdeg")

    # internal_resistance: (4.2 - 3.9) / 1.0 = 0.3 Ohms
    assert_true(approx_eq(internal_resistance_from_voltage(4.2, 3.9, 1.0), 0.3), "ir 0.3")
    assert_true(approx_eq(internal_resistance_from_voltage(4.2, 3.9, 0.0), 0.0), "ir zero I")

    # battery_pack_voltage: 4 cells * 3.7V = 14.8V
    assert_true(approx_eq(battery_pack_voltage(4.0, 3.7), 14.8), "pack V 4s")

    # battery_pack_capacity: 3 parallel * 5Ah = 15Ah
    assert_true(approx_eq(battery_pack_capacity(3.0, 5.0), 15.0), "pack C 3p")

    print("  ✓ battery (26 assertions)")


# ── Fisheries Science Tests ──────────────────────────────────────────────────


fn test_fisheries() raises:
    # catch_per_unit_effort: 500/100 = 5.0
    assert_true(approx_eq(catch_per_unit_effort(500.0, 100.0), 5.0), "cpue 500/100")
    assert_true(approx_eq(catch_per_unit_effort(100.0, 0.0), 0.0), "cpue zero E")

    # maximum_sustainable_yield: 0.5 * 10000 / 4 = 1250
    assert_true(approx_eq(maximum_sustainable_yield(0.5, 10000.0), 1250.0), "msy")

    # biomass_at_msy: 10000/2 = 5000
    assert_true(approx_eq(biomass_at_msy(10000.0), 5000.0), "bmsy")

    # schaefer_surplus_production: 0.5 * 5000 * (1 - 5000/10000) = 0.5*5000*0.5 = 1250
    assert_true(approx_eq(schaefer_surplus_production(0.5, 5000.0, 10000.0), 1250.0), "sp")
    assert_true(approx_eq(schaefer_surplus_production(0.5, 5000.0, 0.0), 0.0), "sp zero K")

    # fishing_mortality: 200/1000 = 0.2
    assert_true(approx_eq(fishing_mortality(200.0, 1000.0), 0.2), "fmort")
    assert_true(approx_eq(fishing_mortality(200.0, 0.0), 0.0), "fmort zero B")

    # total_mortality: 0.2 + 0.3 = 0.5
    assert_true(approx_eq(total_mortality(0.2, 0.3), 0.5), "zmort")

    # exploitation_rate: 0.2 / 0.5 = 0.4
    assert_true(approx_eq(exploitation_rate(0.2, 0.5), 0.4), "exploit rate")
    assert_true(approx_eq(exploitation_rate(0.2, 0.0), 0.0), "exploit zero Z")

    # survival_rate: exp(-0.5) ≈ 0.6065
    assert_true(rel_eq(survival_rate(0.5), exp(-0.5)), "survival")
    assert_true(approx_eq(survival_rate(0.0), 1.0), "survival zero Z")

    # von_bertalanffy_length: Linf=100, k=0.3, t=5, t0=0
    # L = 100*(1 - exp(-0.3*5)) = 100*(1-exp(-1.5)) ≈ 100*0.7769 = 77.69
    var vb = von_bertalanffy_length(100.0, 0.3, 5.0, 0.0)
    assert_true(rel_eq(vb, 100.0 * (1.0 - exp(-1.5))), "vb length")
    # at t=t0, L=0
    assert_true(approx_eq(von_bertalanffy_length(100.0, 0.3, 0.0, 0.0), 0.0), "vb at t0")

    # condition_factor: K = 100 * 500 / 30^3 = 50000/27000 ≈ 1.8519
    assert_true(rel_eq(condition_factor(500.0, 30.0), 50000.0 / 27000.0), "cond factor")
    assert_true(approx_eq(condition_factor(500.0, 0.0), 0.0), "cond zero L")

    # gonadosomatic_index: 50/500 * 100 = 10%
    assert_true(approx_eq(gonadosomatic_index(50.0, 500.0), 10.0), "gsi")
    assert_true(approx_eq(gonadosomatic_index(50.0, 0.0), 0.0), "gsi zero body")

    # stock_recruitment_bevholt: R = 1000*200/(500+200) = 200000/700 ≈ 285.714
    assert_true(rel_eq(stock_recruitment_bevholt(1000.0, 500.0, 200.0), 200000.0 / 700.0), "bevholt")
    assert_true(approx_eq(stock_recruitment_bevholt(1000.0, 500.0, 0.0), 0.0), "bevholt zero S")

    print("  ✓ fisheries (24 assertions)")


# ── Museum Science Tests ─────────────────────────────────────────────────────


fn test_museum() raises:
    # lux_hours_annual: 50 lux * 8 hours * 365 days = 146000
    assert_true(approx_eq(lux_hours_annual(50.0, 8.0, 365.0), 146000.0), "lux hours")
    assert_true(approx_eq(lux_hours_annual(0.0, 8.0, 365.0), 0.0), "lux hours zero")

    # uv_exposure: 0.075 * 200 = 15.0 mW/m²
    assert_true(approx_eq(uv_exposure(0.075, 200.0), 15.0), "uv exposure")

    # relative_humidity_from_temps: 100 - 5*(25-22) = 100-15 = 85%
    assert_true(approx_eq(relative_humidity_from_temps(25.0, 22.0), 85.0), "rh from temps")
    assert_true(approx_eq(relative_humidity_from_temps(20.0, 20.0), 100.0), "rh equal temps")

    # moisture_content_equilibrium: 50*0.15 + 20*0.01 = 7.5+0.2 = 7.7%
    assert_true(approx_eq(moisture_content_equilibrium(50.0, 20.0), 7.7), "emc")

    # time_weighted_preservation_index at ref conditions (20°C, 50%RH) = ref
    assert_true(rel_eq(time_weighted_preservation_index(100.0, 20.0, 50.0), 100.0), "twpi ref")
    # higher temp → lower TWPI
    assert_true(time_weighted_preservation_index(100.0, 30.0, 50.0) < 100.0, "twpi high temp")
    # lower temp → higher TWPI
    assert_true(time_weighted_preservation_index(100.0, 10.0, 50.0) > 100.0, "twpi low temp")

    # light_damage_reciprocity: 200 * 8 = 1600
    assert_true(approx_eq(light_damage_reciprocity(200.0, 8.0), 1600.0), "light damage")

    # climate_stability_score: 100 - 2*2 - 5 = 100-4-5 = 91
    assert_true(approx_eq(climate_stability_score(2.0, 5.0), 91.0), "climate score")
    assert_true(approx_eq(climate_stability_score(0.0, 0.0), 100.0), "climate perfect")

    # storage_density: 5000 items / 200 m² = 25
    assert_true(approx_eq(storage_density(5000.0, 200.0), 25.0), "storage density")
    assert_true(approx_eq(storage_density(100.0, 0.0), 0.0), "storage zero area")

    # collection_growth_rate: (100-20)/10000 * 100 = 0.8%
    assert_true(approx_eq(collection_growth_rate(100.0, 20.0, 10000.0), 0.8), "growth rate")
    assert_true(approx_eq(collection_growth_rate(50.0, 50.0, 10000.0), 0.0), "growth neutral")

    # insurance_value_appreciation: 1000000 * (1.05)^10 ≈ 1628894.63
    var iv = insurance_value_appreciation(1000000.0, 0.05, 10.0)
    assert_true(rel_eq(iv, 1000000.0 * exp(10.0 * 0.04879016417), 0.01), "insurance val")
    # zero years = initial
    assert_true(approx_eq(insurance_value_appreciation(1000.0, 0.05, 0.0), 1000.0), "insurance 0yr")

    # visitor_density: 300/500 = 0.6
    assert_true(approx_eq(visitor_density(300.0, 500.0), 0.6), "visitor density")
    assert_true(approx_eq(visitor_density(300.0, 0.0), 0.0), "visitor zero area")

    # conservation_priority_score: 80*0.4 + 90*0.3 + 70*0.3 = 32+27+21 = 80
    assert_true(approx_eq(conservation_priority_score(80.0, 90.0, 70.0), 80.0), "cps")
    assert_true(approx_eq(conservation_priority_score(100.0, 100.0, 100.0), 100.0), "cps max")

    print("  ✓ museum (24 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 83 tests: Battery, Fisheries, Museum")
    test_battery()
    test_fisheries()
    test_museum()
    print("All Wave 83 tests passed! (74 assertions)")
