"""Tests for Wave 94 — Greenhouse, Numismatics, Pneumatics."""

from greenhouse import (
    heat_loss_conduction,
    ventilation_rate,
    solar_gain,
    heating_requirement,
    co2_enrichment_rate,
    light_supplementation_hours,
    irrigation_volume,
    growing_area_utilization,
    energy_cost_heating,
    yield_per_sq_meter,
    temperature_setpoint_night,
    shade_factor,
)
from numismatics import (
    melt_value,
    premium_over_melt,
    grade_numeric_to_scale,
    population_scarcity,
    annual_return,
    insurance_value,
    mintage_per_capita,
    survival_rate_estimate,
    price_trend,
    auction_fee,
    total_cost_acquisition,
    bullion_content_troy_oz,
)
from pneumatics import (
    ideal_gas_volume,
    flow_rate_orifice,
    compressor_power,
    pressure_drop_pipe,
    air_consumption,
    cylinder_force,
    bore_area,
    piston_speed,
    receiver_volume,
    free_air_delivery,
    specific_power,
    dew_point_pressure,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, log


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx(a: Float64, b: Float64, eps: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < eps


def approx_rel(a: Float64, b: Float64, rel: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < 1e-12
    return fabs((a - b) / b) < rel


# ── Greenhouse tests ─────────────────────────────────────────────────────────


def test_greenhouse() raises:
    # heat_loss_conduction: U=5, A=100, ΔT=20 => 10000 W
    assert_true(approx(heat_loss_conduction(5.0, 100.0, 20.0), 10000.0), "hlc basic")
    # U=2.5, A=50, ΔT=15 => 1875
    assert_true(approx(heat_loss_conduction(2.5, 50.0, 15.0), 1875.0), "hlc 1875")

    # ventilation_rate: V=1000, ACH=10 => 1000*10/3600 ≈ 2.7778
    assert_true(approx_rel(ventilation_rate(1000.0, 10.0), 2.77778), "vent basic")
    # V=3600, ACH=1 => 1.0
    assert_true(approx(ventilation_rate(3600.0, 1.0), 1.0), "vent 1.0")

    # solar_gain: τ=0.7, A=200, G=500 => 70000
    assert_true(approx(solar_gain(0.7, 200.0, 500.0), 70000.0), "sg 70k")
    # τ=0.9, A=100, G=300 => 27000
    assert_true(approx(solar_gain(0.9, 100.0, 300.0), 27000.0), "sg 27k")

    # heating_requirement: loss=10000, gain=3000 => 7000
    assert_true(approx(heating_requirement(10000.0, 3000.0), 7000.0), "hr 7k")
    # loss=3000, gain=5000 => 0
    assert_true(approx(heating_requirement(3000.0, 5000.0), 0.0), "hr zero")

    # co2_enrichment_rate: (1000-400)*500/1e6 + 0.5 = 0.3+0.5 = 0.8
    assert_true(approx(co2_enrichment_rate(1000.0, 400.0, 500.0, 0.5), 0.8), "co2 0.8")
    # (1200-400)*1000/1e6 + 1.0 = 0.8+1.0 = 1.8
    assert_true(approx(co2_enrichment_rate(1200.0, 400.0, 1000.0, 1.0), 1.8), "co2 1.8")

    # light_supplementation_hours: (20-10)*1e6/(400*3600) = 10e6/1440000 ≈ 6.9444
    assert_true(approx_rel(light_supplementation_hours(20.0, 10.0, 400.0), 6.94444), "lsh 6.94")
    # no deficit => 0
    assert_true(approx(light_supplementation_hours(15.0, 15.0, 400.0), 0.0), "lsh zero")

    # irrigation_volume: 5*100/0.9 ≈ 555.556
    assert_true(approx_rel(irrigation_volume(5.0, 100.0, 0.9), 555.5556), "irr 555")
    # 3*50/0.8 = 187.5
    assert_true(approx(irrigation_volume(3.0, 50.0, 0.8), 187.5), "irr 187.5")

    # growing_area_utilization: 800/1000*100 = 80
    assert_true(approx(growing_area_utilization(800.0, 1000.0), 80.0), "gau 80")
    # 450/500*100 = 90
    assert_true(approx(growing_area_utilization(450.0, 500.0), 90.0), "gau 90")

    # energy_cost_heating: 500*0.12 = 60
    assert_true(approx(energy_cost_heating(500.0, 0.12), 60.0), "ech 60")
    # 1000*0.15 = 150
    assert_true(approx(energy_cost_heating(1000.0, 0.15), 150.0), "ech 150")

    # yield_per_sq_meter: 500/200 = 2.5
    assert_true(approx(yield_per_sq_meter(500.0, 200.0), 2.5), "ypsm 2.5")
    # 100/50 = 2.0
    assert_true(approx(yield_per_sq_meter(100.0, 50.0), 2.0), "ypsm 2.0")

    # temperature_setpoint_night: 24-6 = 18
    assert_true(approx(temperature_setpoint_night(24.0, 6.0), 18.0), "tsn 18")
    # 22-4 = 18
    assert_true(approx(temperature_setpoint_night(22.0, 4.0), 18.0), "tsn 18b")

    # shade_factor: 30% => 0.7
    assert_true(approx(shade_factor(30.0), 0.7), "sf 0.7")
    # 0% => 1.0
    assert_true(approx(shade_factor(0.0), 1.0), "sf 1.0")
    # 100% => 0.0
    assert_true(approx(shade_factor(100.0), 0.0), "sf 0.0")

    print("  ✓ greenhouse (25 assertions)")


# ── Numismatics tests ────────────────────────────────────────────────────────


def test_numismatics() raises:
    # melt_value: 1oz * $2000 = 2000
    assert_true(approx(melt_value(1.0, 2000.0), 2000.0), "mv 2k")
    # 0.5oz * $1800 = 900
    assert_true(approx(melt_value(0.5, 1800.0), 900.0), "mv 900")

    # premium_over_melt: (3000-2000)/2000*100 = 50%
    assert_true(approx(premium_over_melt(3000.0, 2000.0), 50.0), "pom 50")
    # same => 0%
    assert_true(approx(premium_over_melt(2000.0, 2000.0), 0.0), "pom 0")

    # grade_numeric_to_scale: 65 => 65
    assert_true(approx(grade_numeric_to_scale(65.0), 65.0), "gns 65")
    # -5 clamped => 0
    assert_true(approx(grade_numeric_to_scale(-5.0), 0.0), "gns clamp lo")
    # 80 clamped => 70
    assert_true(approx(grade_numeric_to_scale(80.0), 70.0), "gns clamp hi")

    # population_scarcity: 500/1000000*100 = 0.05
    assert_true(approx(population_scarcity(500.0, 1000000.0), 0.05), "ps 0.05")
    # 100/50000*100 = 0.2
    assert_true(approx(population_scarcity(100.0, 50000.0), 0.2), "ps 0.2")

    # annual_return: ((200/100)^(1/10)-1)*100 ≈ 7.177%
    assert_true(approx_rel(annual_return(100.0, 200.0, 10.0), 7.17735, 1e-3), "ar 7.18")
    # ((1000/500)^(1/5)-1)*100 ≈ 14.87%
    assert_true(approx_rel(annual_return(500.0, 1000.0, 5.0), 14.8698, 1e-3), "ar 14.87")

    # insurance_value: 5000*1.2 = 6000
    assert_true(approx(insurance_value(5000.0, 1.2), 6000.0), "iv 6k")
    # 10000*1.1 = 11000
    assert_true(approx(insurance_value(10000.0, 1.1), 11000.0), "iv 11k")

    # mintage_per_capita: 5e6/50e6 = 0.1
    assert_true(approx(mintage_per_capita(5000000.0, 50000000.0), 0.1), "mpc 0.1")
    # 1e6/300e6 ≈ 0.003333
    assert_true(approx_rel(mintage_per_capita(1000000.0, 300000000.0), 0.0033333333, 1e-3), "mpc 0.0033")

    # survival_rate_estimate: 1000/100000*100 = 1.0%
    assert_true(approx(survival_rate_estimate(1000.0, 100000.0), 1.0), "sre 1.0")
    # 500/10000*100 = 5.0%
    assert_true(approx(survival_rate_estimate(500.0, 10000.0), 5.0), "sre 5.0")

    # price_trend: (150-100)/100*100 = 50%
    assert_true(approx(price_trend(100.0, 150.0), 50.0), "pt +50")
    # (180-200)/200*100 = -10%
    assert_true(approx(price_trend(200.0, 180.0), -10.0), "pt -10")

    # auction_fee: 10000*20/100 = 2000
    assert_true(approx(auction_fee(10000.0, 20.0), 2000.0), "af 2k")
    # 5000*15/100 = 750
    assert_true(approx(auction_fee(5000.0, 15.0), 750.0), "af 750")

    # total_cost_acquisition: 10000*1.2*1.08 = 12960
    assert_true(approx(total_cost_acquisition(10000.0, 20.0, 8.0), 12960.0), "tca 12960")
    # 5000*1.15*1.05 = 6037.5
    assert_true(approx(total_cost_acquisition(5000.0, 15.0, 5.0), 6037.5), "tca 6037")

    # bullion_content_troy_oz: 31.1035*1.0/31.1035 = 1.0
    assert_true(approx(bullion_content_troy_oz(31.1035, 1.0), 1.0), "bct 1.0")
    # 8.0*0.9/31.1035 ≈ 0.23151
    assert_true(approx_rel(bullion_content_troy_oz(8.0, 0.9), 0.23151, 1e-3), "bct 0.23")

    print("  ✓ numismatics (25 assertions)")


# ── Pneumatics tests ─────────────────────────────────────────────────────────


def test_pneumatics() raises:
    # ideal_gas_volume: 200*10/400 = 5.0
    assert_true(approx(ideal_gas_volume(200.0, 10.0, 400.0), 5.0), "igv 5")
    # 100*5/50 = 10
    assert_true(approx(ideal_gas_volume(100.0, 5.0, 50.0), 10.0), "igv 10")

    # flow_rate_orifice: 0.6*0.001*sqrt(2*100000/1.2) = 0.0006*sqrt(166666.67)
    # sqrt(166666.67) ≈ 408.248 => 0.0006*408.248 ≈ 0.24495
    var fro = flow_rate_orifice(0.6, 0.001, 100000.0, 1.2)
    assert_true(approx_rel(fro, 0.24495, 1e-3), "fro basic")

    # compressor_power: 1.0*100000*ln(2)/1.0 = 69314.718
    var cp1 = compressor_power(1.0, 100000.0, 200000.0, 1.0)
    assert_true(approx_rel(cp1, 69314.718, 1e-3), "cp ln2")
    # 0.5*100000*ln(3)/0.8 ≈ 68663.3
    var cp2 = compressor_power(0.5, 100000.0, 300000.0, 0.8)
    var expected_cp2 = 0.5 * 100000.0 * log(3.0) / 0.8
    assert_true(approx_rel(cp2, expected_cp2, 1e-6), "cp ln3")

    # pressure_drop_pipe: 0.02*100/0.05 * 1.2*20^2/2 = 40*240 = 9600
    assert_true(approx(pressure_drop_pipe(0.02, 100.0, 0.05, 1.2, 20.0), 9600.0), "pdp 9600")

    # air_consumption: π/4*0.01*0.5*2*1.0*1.0 = π*0.0025 ≈ 0.007854
    var ac = air_consumption(0.1, 0.5, 101.325, 1.0)
    assert_true(approx_rel(ac, 0.007854, 1e-3), "ac basic")

    # cylinder_force: 0.01*500000 = 5000
    assert_true(approx(cylinder_force(0.01, 500000.0), 5000.0), "cf 5k")
    # 0.005*600000 = 3000
    assert_true(approx(cylinder_force(0.005, 600000.0), 3000.0), "cf 3k")

    # bore_area: π/4*0.01 ≈ 0.007854
    assert_true(approx_rel(bore_area(0.1), 0.007854, 1e-3), "ba 0.1")
    # π/4*0.0025 ≈ 0.001963
    assert_true(approx_rel(bore_area(0.05), 0.001963, 1e-3), "ba 0.05")

    # piston_speed: 2*0.3*60/60 = 0.6
    assert_true(approx(piston_speed(0.3, 60.0), 0.6), "ps 0.6")
    # 2*0.5*30/60 = 0.5
    assert_true(approx(piston_speed(0.5, 30.0), 0.5), "ps 0.5")

    # receiver_volume: 10*5/(800-700) = 50/100 = 0.5
    assert_true(approx(receiver_volume(10.0, 5.0, 800.0, 700.0), 0.5), "rv 0.5")
    # 2*3/(900-800) = 6/100 = 0.06
    assert_true(approx(receiver_volume(2.0, 3.0, 900.0, 800.0), 0.06), "rv 0.06")

    # free_air_delivery: 10*700/100 = 70.0
    assert_true(approx(free_air_delivery(10.0, 700.0, 100.0), 70.0), "fad 70")
    # 5*800/101.325 ≈ 39.477
    assert_true(approx_rel(free_air_delivery(5.0, 800.0, 101.325), 39.477, 1e-3), "fad 39.5")

    # specific_power: 15/3 = 5.0
    assert_true(approx(specific_power(15.0, 3.0), 5.0), "sp 5")
    # 22/4 = 5.5
    assert_true(approx(specific_power(22.0, 4.0), 5.5), "sp 5.5")

    # dew_point_pressure: ratio=1.0 => dp + 10*ln(1) = dp + 0 = 10
    assert_true(approx(dew_point_pressure(10.0, 1.0), 10.0), "dpp 10")
    # ratio=e^2 ≈ 7.389056 => 5 + 10*2 = 25
    assert_true(approx_rel(dew_point_pressure(5.0, 7.389056), 25.0, 1e-3), "dpp 25")

    print("  ✓ pneumatics (22 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 94 tests — Greenhouse, Numismatics, Pneumatics")
    test_greenhouse()
    test_numismatics()
    test_pneumatics()
    print("All Wave 94 tests passed ✓  (72 assertions)")
