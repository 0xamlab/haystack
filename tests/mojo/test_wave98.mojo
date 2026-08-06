"""Wave 98 tests -- geomorphology, watchmaking, pest_control (70+ assertions)."""

from std.testing import assert_true, assert_false, assert_equal
from std.math import abs, exp, sqrt

# -- geomorphology imports --
from geomorphology import (
    stream_power,
    shear_stress_flow,
    shields_parameter,
    settling_velocity_stokes,
    erosion_rate_spl,
    hillslope_diffusion,
    drainage_density,
    relief_ratio,
    sinuosity,
    hack_law_length,
    ruggedness_number,
    hypsometric_integral,
)

# -- watchmaking imports --
from watchmaking import (
    gear_ratio,
    gear_train_ratio,
    beats_per_hour,
    frequency_from_bph,
    mainspring_torque,
    power_reserve_hours,
    balance_wheel_period,
    escapement_error_spd,
    jewel_count_minimum,
    water_resistance_atm,
    case_diameter_mm,
    crown_winding_turns,
)

# -- pest_control imports --
from pest_control import (
    economic_threshold,
    economic_injury_level,
    pest_density,
    trap_catch_rate,
    spray_coverage,
    dilution_rate,
    residual_effectiveness,
    resistance_ratio,
    biocontrol_release_rate,
    fumigation_ct,
    bait_station_density,
    population_reduction,
)


def _close(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    if b == 0.0:
        return abs(a) < eps
    return abs(a - b) / abs(b) < eps


def main() raises:
    print("== Wave 98 tests ==")
    var passed: Int = 0
    var failed: Int = 0

    # ─── geomorphology ──────────────────────────────────────────────────

    # stream_power: Ω = ρ*g*Q*S  => 1000*9.81*5.0*0.002 = 98.1
    var sp = stream_power(5.0, 0.002, 1000.0, 9.81)
    assert_true(_close(sp, 98.1), "stream_power basic")
    passed += 1

    # stream_power zero slope
    assert_true(_close(stream_power(10.0, 0.0, 1000.0, 9.81), 0.0), "stream_power zero slope")
    passed += 1

    # shear_stress_flow: τ = 1000*9.81*2.0*0.001 = 19.62
    var tau = shear_stress_flow(1000.0, 9.81, 2.0, 0.001)
    assert_true(_close(tau, 19.62), "shear_stress_flow basic")
    passed += 1

    # shear_stress_flow deeper => 1000*9.81*5.0*0.005 = 245.25
    assert_true(_close(shear_stress_flow(1000.0, 9.81, 5.0, 0.005), 245.25), "shear_stress deep")
    passed += 1

    # shields_parameter: θ = 10 / ((2650-1000)*9.81*0.001) = 10/(16.1865) ≈ 0.61779
    var sh = shields_parameter(10.0, 2650.0, 1000.0, 9.81, 0.001)
    assert_true(_close(sh, 10.0 / (1650.0 * 9.81 * 0.001)), "shields_parameter basic")
    passed += 1

    # settling_velocity_stokes: ws = (2650-1000)*9.81*(0.0001)^2/(18*0.001)
    #   = 1650*9.81*1e-8/0.018 = 0.00016185/0.018 ≈ 0.0089917
    var ws = settling_velocity_stokes(2650.0, 1000.0, 9.81, 0.0001, 0.001)
    var ws_exp = 1650.0 * 9.81 * 1e-8 / 0.018
    assert_true(_close(ws, ws_exp), "settling_velocity basic")
    passed += 1

    # settling_velocity larger grain
    var ws2 = settling_velocity_stokes(2650.0, 1000.0, 9.81, 0.0005, 0.001)
    var ws2_exp = 1650.0 * 9.81 * 0.0005 * 0.0005 / 0.018
    assert_true(_close(ws2, ws2_exp), "settling_velocity larger grain")
    passed += 1

    # erosion_rate_spl: E = 1e-5 * 1e6^0.5 * 0.01^1.0 = 1e-5*1000*0.01 = 1e-4
    var er = erosion_rate_spl(1e-5, 1e6, 0.01, 0.5, 1.0)
    assert_true(_close(er, 1e-4), "erosion_rate_spl basic")
    passed += 1

    # hillslope_diffusion: qs = 0.01 * (-0.05) = -0.0005
    var hd = hillslope_diffusion(0.01, -0.05)
    assert_true(_close(hd, -0.0005), "hillslope_diffusion basic")
    passed += 1

    # hillslope_diffusion positive curvature
    assert_true(_close(hillslope_diffusion(0.02, 0.1), 0.002), "hillslope_diffusion positive")
    passed += 1

    # drainage_density: Dd = 50.0/10.0 = 5.0
    assert_true(_close(drainage_density(50.0, 10.0), 5.0), "drainage_density basic")
    passed += 1

    # relief_ratio: Rr = 500/5000 = 0.1
    assert_true(_close(relief_ratio(500.0, 5000.0), 0.1), "relief_ratio basic")
    passed += 1

    # sinuosity: S = 1500/1000 = 1.5
    assert_true(_close(sinuosity(1500.0, 1000.0), 1.5), "sinuosity basic")
    passed += 1

    # sinuosity straight = 1.0
    assert_true(_close(sinuosity(100.0, 100.0), 1.0), "sinuosity straight")
    passed += 1

    # hack_law_length: L = 1.4 * 100^0.6
    #   100^0.6 = 10^1.2 ≈ 15.8489 => L ≈ 22.1885
    var hl = hack_law_length(1.4, 100.0, 0.6)
    var hl_exp = 1.4 * 15.848931924611134  # 100^0.6
    assert_true(_close(hl, hl_exp, 1e-4), "hack_law_length basic")
    passed += 1

    # ruggedness_number: Rn = 500 * 5.0 = 2500
    assert_true(_close(ruggedness_number(500.0, 5.0), 2500.0), "ruggedness_number basic")
    passed += 1

    # hypsometric_integral: HI = (600-200)/(1000-200) = 400/800 = 0.5
    assert_true(_close(hypsometric_integral(600.0, 200.0, 1000.0), 0.5), "hypsometric_integral basic")
    passed += 1

    # hypsometric_integral low
    assert_true(_close(hypsometric_integral(250.0, 200.0, 1000.0), 0.0625), "hypsometric low")
    passed += 1

    # ─── watchmaking ────────────────────────────────────────────────────

    # gear_ratio: 80/10 = 8.0
    assert_true(_close(gear_ratio(10.0, 80.0), 8.0), "gear_ratio basic")
    passed += 1

    # gear_ratio 1:1
    assert_true(_close(gear_ratio(20.0, 20.0), 1.0), "gear_ratio 1:1")
    passed += 1

    # gear_train_ratio passthrough
    assert_true(_close(gear_train_ratio(48.0), 48.0), "gear_train_ratio basic")
    passed += 1

    # beats_per_hour: 4 * 3600 * 2 = 28800
    assert_true(_close(beats_per_hour(4.0), 28800.0), "beats_per_hour 4Hz")
    passed += 1

    # beats_per_hour: 3 Hz => 21600
    assert_true(_close(beats_per_hour(3.0), 21600.0), "beats_per_hour 3Hz")
    passed += 1

    # frequency_from_bph: 28800/7200 = 4.0
    assert_true(_close(frequency_from_bph(28800.0), 4.0), "frequency_from_bph 28800")
    passed += 1

    # frequency_from_bph: 21600/7200 = 3.0
    assert_true(_close(frequency_from_bph(21600.0), 3.0), "frequency_from_bph 21600")
    passed += 1

    # mainspring_torque: 2.5 * 0.006 = 0.015
    assert_true(_close(mainspring_torque(2.5, 0.006), 0.015), "mainspring_torque basic")
    passed += 1

    # power_reserve_hours: 100/2.0 = 50
    assert_true(_close(power_reserve_hours(100.0, 2.0), 50.0), "power_reserve_hours basic")
    passed += 1

    # power_reserve_hours: 72/1.5 = 48
    assert_true(_close(power_reserve_hours(72.0, 1.5), 48.0), "power_reserve 48h")
    passed += 1

    # balance_wheel_period: T = 2π*sqrt(1e-7/1e-3) = 2π*sqrt(1e-4) = 2π*0.01 ≈ 0.06283
    comptime PI: Float64 = 3.141592653589793
    var bwp = balance_wheel_period(1e-7, 1e-3)
    var bwp_exp = 2.0 * PI * 0.01
    assert_true(_close(bwp, bwp_exp), "balance_wheel_period basic")
    passed += 1

    # escapement_error_spd: (28810-28800)/28800*86400 = 10/28800*86400 = 30.0
    var spd = escapement_error_spd(28810.0, 28800.0)
    assert_true(_close(spd, 30.0), "escapement_error_spd fast")
    passed += 1

    # escapement_error_spd slow: (28790-28800)/28800*86400 = -30.0
    assert_true(_close(escapement_error_spd(28790.0, 28800.0), -30.0), "escapement_error_spd slow")
    passed += 1

    # jewel_count_minimum: 5*2+1 = 11
    assert_equal(jewel_count_minimum(5), 11, "jewel_count_minimum 5 trains")
    passed += 1

    # jewel_count_minimum: 10*2+1 = 21
    assert_equal(jewel_count_minimum(10), 21, "jewel_count_minimum 10 trains")
    passed += 1

    # water_resistance_atm: 100/10+1 = 11.0
    assert_true(_close(water_resistance_atm(100.0), 11.0), "water_resistance 100m")
    passed += 1

    # water_resistance_atm: 200/10+1 = 21.0
    assert_true(_close(water_resistance_atm(200.0), 21.0), "water_resistance 200m")
    passed += 1

    # case_diameter_mm: 12 * 2.2558 = 27.0696
    assert_true(_close(case_diameter_mm(12.0), 27.0696), "case_diameter 12 ligne")
    passed += 1

    # case_diameter_mm: 11.5 * 2.2558 = 25.9417
    assert_true(_close(case_diameter_mm(11.5), 25.9417), "case_diameter 11.5 ligne")
    passed += 1

    # crown_winding_turns: 500 / (π * 10) = 500/31.4159 ≈ 15.9155
    var cwt = crown_winding_turns(500.0, 10.0)
    var cwt_exp = 500.0 / (PI * 10.0)
    assert_true(_close(cwt, cwt_exp), "crown_winding_turns basic")
    passed += 1

    # ─── pest_control ───────────────────────────────────────────────────

    # economic_threshold: 50/(5000*0.01) = 50/50 = 1.0
    assert_true(_close(economic_threshold(50.0, 5000.0, 0.01), 1.0), "economic_threshold basic")
    passed += 1

    # economic_threshold: 100/(10000*0.005) = 100/50 = 2.0
    assert_true(_close(economic_threshold(100.0, 10000.0, 0.005), 2.0), "economic_threshold alt")
    passed += 1

    # economic_injury_level: 1.0 * 1.5 = 1.5
    assert_true(_close(economic_injury_level(1.0, 1.5), 1.5), "economic_injury_level basic")
    passed += 1

    # pest_density: 120/4.0 = 30.0
    assert_true(_close(pest_density(120.0, 4.0), 30.0), "pest_density basic")
    passed += 1

    # pest_density: 50/2.5 = 20.0
    assert_true(_close(pest_density(50.0, 2.5), 20.0), "pest_density alt")
    passed += 1

    # trap_catch_rate: 150/(10*5) = 3.0
    assert_true(_close(trap_catch_rate(150.0, 10.0, 5.0), 3.0), "trap_catch_rate basic")
    passed += 1

    # trap_catch_rate: 36/(6*3) = 2.0
    assert_true(_close(trap_catch_rate(36.0, 6.0, 3.0), 2.0), "trap_catch_rate alt")
    passed += 1

    # spray_coverage: 200/10 = 20.0
    assert_true(_close(spray_coverage(200.0, 10.0), 20.0), "spray_coverage basic")
    passed += 1

    # dilution_rate: 50/(50+950) = 0.05
    assert_true(_close(dilution_rate(50.0, 950.0), 0.05), "dilution_rate basic")
    passed += 1

    # dilution_rate: 100/(100+900) = 0.1
    assert_true(_close(dilution_rate(100.0, 900.0), 0.1), "dilution_rate 10%")
    passed += 1

    # residual_effectiveness: 95 * exp(-0.693*7/14) = 95*exp(-0.3465) ≈ 95*0.70711 ≈ 67.175
    var re = residual_effectiveness(95.0, 14.0, 7.0)
    var re_exp = 95.0 * exp(-0.693 * 7.0 / 14.0)
    assert_true(_close(re, re_exp), "residual_effectiveness half")
    passed += 1

    # residual_effectiveness at t=0 => initial
    assert_true(_close(residual_effectiveness(90.0, 10.0, 0.0), 90.0), "residual_effectiveness t=0")
    passed += 1

    # residual_effectiveness one half-life => ~half
    var re2 = residual_effectiveness(100.0, 10.0, 10.0)
    var re2_exp = 100.0 * exp(-0.693)
    assert_true(_close(re2, re2_exp), "residual_effectiveness one HL")
    passed += 1

    # resistance_ratio: 50/5 = 10.0
    assert_true(_close(resistance_ratio(50.0, 5.0), 10.0), "resistance_ratio basic")
    passed += 1

    # resistance_ratio: 3.0/3.0 = 1.0 (susceptible)
    assert_true(_close(resistance_ratio(3.0, 3.0), 1.0), "resistance_ratio equal")
    passed += 1

    # biocontrol_release_rate: 20*5.0/10 = 10.0
    assert_true(_close(biocontrol_release_rate(20.0, 10.0, 5.0), 10.0), "biocontrol_release basic")
    passed += 1

    # biocontrol_release_rate: 50*2.0/5 = 20.0
    assert_true(_close(biocontrol_release_rate(50.0, 5.0, 2.0), 20.0), "biocontrol_release alt")
    passed += 1

    # fumigation_ct: 30*24 = 720
    assert_true(_close(fumigation_ct(30.0, 24.0), 720.0), "fumigation_ct basic")
    passed += 1

    # fumigation_ct: 15*48 = 720
    assert_true(_close(fumigation_ct(15.0, 48.0), 720.0), "fumigation_ct alt")
    passed += 1

    # bait_station_density: 25/5000*10000 = 50.0
    assert_true(_close(bait_station_density(25.0, 5000.0), 50.0), "bait_station_density basic")
    passed += 1

    # bait_station_density: 100/10000*10000 = 100.0
    assert_true(_close(bait_station_density(100.0, 10000.0), 100.0), "bait_station_density ha")
    passed += 1

    # population_reduction: (1000-300)/1000*100 = 70.0
    assert_true(_close(population_reduction(1000.0, 300.0), 70.0), "population_reduction 70%")
    passed += 1

    # population_reduction: (500-500)/500*100 = 0.0
    assert_true(_close(population_reduction(500.0, 500.0), 0.0), "population_reduction 0%")
    passed += 1

    # population_reduction: (200-0)/200*100 = 100.0
    assert_true(_close(population_reduction(200.0, 0.0), 100.0), "population_reduction 100%")
    passed += 1

    # ─── extra cross-checks ─────────────────────────────────────────────

    # frequency round-trip: bph -> freq -> bph
    var bph_val = beats_per_hour(4.0)
    var freq_back = frequency_from_bph(bph_val)
    assert_true(_close(freq_back, 4.0), "bph-freq round-trip")
    passed += 1

    # geomorphology: drainage_density and ruggedness compose
    var dd = drainage_density(100.0, 20.0)  # 5.0
    var rn = ruggedness_number(800.0, dd)    # 4000.0
    assert_true(_close(rn, 4000.0), "dd-rn composition")
    passed += 1

    # shields > 0 for typical values
    var sh2 = shields_parameter(5.0, 2650.0, 1000.0, 9.81, 0.002)
    assert_true(sh2 > 0.0, "shields positive")
    passed += 1

    # water_resistance_atm at 0 m => 1 ATM
    assert_true(_close(water_resistance_atm(0.0), 1.0), "water_resistance 0m = 1 ATM")
    passed += 1

    # erosion rate increases with steeper slope
    var e1 = erosion_rate_spl(1e-5, 1e6, 0.01, 0.5, 1.0)
    var e2 = erosion_rate_spl(1e-5, 1e6, 0.05, 0.5, 1.0)
    assert_true(e2 > e1, "erosion increases with slope")
    passed += 1

    # dilution rate < 1 always when water > 0
    assert_true(dilution_rate(10.0, 90.0) < 1.0, "dilution < 1")
    passed += 1

    # sinuosity >= 1 for valid channel
    assert_true(sinuosity(250.0, 200.0) >= 1.0, "sinuosity >= 1")
    passed += 1

    print("== Wave 98 complete: " + String(passed) + " passed, " + String(failed) + " failed ==")
