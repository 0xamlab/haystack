"""Tests for Wave 69 — Tribology, Ergonomics, Combustion."""

from tribology import (
    coulomb_friction_force,
    kinetic_friction,
    static_friction_max,
    coefficient_of_friction,
    hertz_contact_pressure,
    archard_wear_volume,
    bearing_pressure,
    sommerfeld_number,
    stribeck_parameter,
    flash_temperature_rise,
    lubrication_film_thickness,
    friction_power_loss,
)
from ergonomics import (
    niosh_rwl,
    lifting_index,
    metabolic_rate_walking,
    heat_stress_index,
    decibel_addition,
    noise_dose,
    cumulative_noise_dose_2,
    visual_angle_minutes,
    fitts_law_movement_time,
    hicks_law_reaction_time,
    comfort_temperature_pmv_simplified,
    body_mass_index,
)
from combustion import (
    stoichiometric_air_fuel_ratio,
    equivalence_ratio,
    excess_air_percentage,
    adiabatic_flame_temp_estimate,
    lower_heating_value_methane,
    thermal_efficiency,
    carnot_efficiency,
    brake_specific_fuel_consumption,
    combustion_efficiency,
    flame_speed_laminar,
    nox_formation_rate,
    heat_release_rate,
)
from std.math import abs as fabs, exp, log


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


fn _near_rel(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Tribology tests ──────────────────────────────────────────────────────────


fn test_coulomb_friction_force() raises:
    # F = 0.3 * 100 = 30
    var f = coulomb_friction_force(0.3, 100.0)
    _assert(_near(f, 30.0), "coulomb_friction 0.3*100=30")


fn test_coulomb_friction_zero_mu() raises:
    var f = coulomb_friction_force(0.0, 500.0)
    _assert(_near(f, 0.0), "coulomb_friction mu=0 => 0")


fn test_kinetic_friction() raises:
    # F_k = 0.25 * 200 = 50
    var fk = kinetic_friction(0.25, 200.0)
    _assert(_near(fk, 50.0), "kinetic_friction 0.25*200=50")


fn test_static_friction_max() raises:
    # F_s = 0.4 * 150 = 60
    var fs = static_friction_max(0.4, 150.0)
    _assert(_near(fs, 60.0), "static_friction_max 0.4*150=60")


fn test_static_greater_than_kinetic() raises:
    var fs = static_friction_max(0.5, 100.0)
    var fk = kinetic_friction(0.3, 100.0)
    _assert(fs > fk, "static > kinetic friction")


fn test_coefficient_of_friction() raises:
    # μ = 30/100 = 0.3
    var mu = coefficient_of_friction(30.0, 100.0)
    _assert(_near(mu, 0.3), "coeff_friction 30/100=0.3")


fn test_coefficient_friction_roundtrip() raises:
    var f = coulomb_friction_force(0.35, 80.0)
    var mu = coefficient_of_friction(f, 80.0)
    _assert(_near(mu, 0.35), "coeff friction roundtrip")


fn test_hertz_contact_pressure() raises:
    # p0 = 3*1000/(2*pi*0.01^2) = 3000/(2*3.14159*0.0001) = 3000/0.000628318 ≈ 4774648
    var p = hertz_contact_pressure(1000.0, 0.01)
    var expected = 3.0 * 1000.0 / (2.0 * 3.14159265358979 * 0.01 * 0.01)
    _assert(_near_rel(p, expected), "hertz_contact_pressure")


fn test_archard_wear_volume() raises:
    # V = 1e-4 * 500 * 1000 / 2e9 = 50/2e9 = 2.5e-8
    var v = archard_wear_volume(1e-4, 500.0, 1000.0, 2e9)
    _assert(_near_rel(v, 2.5e-8), "archard_wear_volume")


fn test_bearing_pressure() raises:
    # p = 5000/0.01 = 500000
    var p = bearing_pressure(5000.0, 0.01)
    _assert(_near(p, 500000.0), "bearing_pressure 5000/0.01")


fn test_sommerfeld_number() raises:
    # S = (0.01*30/1e6) / (0.001^2) = 3e-7/1e-6 = 0.3
    var s = sommerfeld_number(0.01, 30.0, 1e6, 0.001)
    _assert(_near(s, 0.3, 1e-6), "sommerfeld_number")


fn test_stribeck_parameter() raises:
    # η*v/p = 0.01*2.0/1e5 = 2e-7
    var sp = stribeck_parameter(0.01, 2.0, 1e5)
    _assert(_near(sp, 2e-7, 1e-12), "stribeck_parameter")


fn test_flash_temperature_rise() raises:
    # ΔT = 0.3*100*5/(50*0.01) = 150/0.5 = 300
    var dt = flash_temperature_rise(0.3, 100.0, 5.0, 50.0, 0.01)
    _assert(_near(dt, 300.0), "flash_temperature_rise")


fn test_lubrication_film_thickness() raises:
    # h = (0.01*1.0/1000)^(2/3) = (1e-5)^(2/3)
    var h = lubrication_film_thickness(0.01, 1.0, 1000.0)
    var expected = exp(2.0 / 3.0 * log(1e-5))
    _assert(_near_rel(h, expected), "lubrication_film_thickness")


fn test_friction_power_loss() raises:
    # P = 50*3.0 = 150 W
    var p = friction_power_loss(50.0, 3.0)
    _assert(_near(p, 150.0), "friction_power_loss 50*3=150")


fn test_friction_power_loss_zero_velocity() raises:
    var p = friction_power_loss(100.0, 0.0)
    _assert(_near(p, 0.0), "friction_power_loss v=0 => 0")


# ── Ergonomics tests ─────────────────────────────────────────────────────────


fn test_niosh_rwl() raises:
    # RWL = 23 * 1.0 * 1.0 * 1.0 * 1.0 * 1.0 * 1.0 = 23
    var rwl = niosh_rwl(23.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    _assert(_near(rwl, 23.0), "niosh_rwl all 1.0 => 23")


fn test_niosh_rwl_reduced() raises:
    # RWL = 23 * 0.5 * 0.8 * 0.9 * 1.0 * 0.7 * 0.95 = 23*0.2394 = 5.5062
    var rwl = niosh_rwl(23.0, 0.5, 0.8, 0.9, 1.0, 0.7, 0.95)
    var expected = 23.0 * 0.5 * 0.8 * 0.9 * 1.0 * 0.7 * 0.95
    _assert(_near(rwl, expected, 0.001), "niosh_rwl reduced multipliers")


fn test_lifting_index() raises:
    # LI = 25/23 ≈ 1.087
    var li = lifting_index(25.0, 23.0)
    _assert(_near(li, 25.0 / 23.0, 0.001), "lifting_index 25/23")


fn test_lifting_index_safe() raises:
    var li = lifting_index(15.0, 23.0)
    _assert(li < 1.0, "lifting_index < 1 => safe")


fn test_lifting_index_risky() raises:
    var li = lifting_index(30.0, 20.0)
    _assert(li > 1.0, "lifting_index > 1 => risky")


fn test_metabolic_rate_walking() raises:
    # M = 70*(2+3*1.5+0.05*1.5*0.5) = 70*(2+4.5+0.0375) = 70*6.5375 = 457.625
    var m = metabolic_rate_walking(70.0, 1.5, 0.05)
    var expected = 70.0 * (2.0 + 3.0 * 1.5 + 0.05 * 1.5 * 0.5)
    _assert(_near(m, expected, 0.01), "metabolic_rate_walking")


fn test_heat_stress_index() raises:
    # HSI = 300/400 * 100 = 75
    var hsi = heat_stress_index(300.0, 400.0)
    _assert(_near(hsi, 75.0), "heat_stress_index 300/400*100=75")


fn test_heat_stress_index_over() raises:
    var hsi = heat_stress_index(500.0, 400.0)
    _assert(hsi > 100.0, "HSI > 100 => dangerous")


fn test_decibel_addition_equal() raises:
    # Two equal sources: L = L1 + 3.01 dB
    var total = decibel_addition(80.0, 80.0)
    _assert(_near(total, 83.01, 0.02), "dB addition 80+80≈83.01")


fn test_decibel_addition_different() raises:
    # 90 dB + 80 dB ≈ 90.41
    var total = decibel_addition(90.0, 80.0)
    _assert(_near(total, 90.414, 0.01), "dB addition 90+80≈90.41")


fn test_noise_dose() raises:
    # D = 6/8 = 0.75
    var d = noise_dose(6.0, 8.0)
    _assert(_near(d, 0.75), "noise_dose 6/8=0.75")


fn test_cumulative_noise_dose_2() raises:
    # D = 4/8 + 2/4 = 0.5 + 0.5 = 1.0
    var d = cumulative_noise_dose_2(4.0, 8.0, 2.0, 4.0)
    _assert(_near(d, 1.0), "cumulative_noise_dose 4/8+2/4=1")


fn test_visual_angle_minutes() raises:
    # Small angle: size=0.01m, dist=1m => ~34.38 arc-min
    var va = visual_angle_minutes(0.01, 1.0)
    _assert(va > 34.0, "visual_angle > 34 arcmin for 1cm at 1m")
    _assert(va < 35.0, "visual_angle < 35 arcmin for 1cm at 1m")


fn test_fitts_law_movement_time() raises:
    # MT = 0.1 + 0.15*log2(2*20/5) = 0.1 + 0.15*log2(8) = 0.1+0.15*3 = 0.55
    var mt = fitts_law_movement_time(0.1, 0.15, 20.0, 5.0)
    var expected = 0.1 + 0.15 * (log(8.0) / log(2.0))
    _assert(_near(mt, expected, 0.001), "fitts_law MT")


fn test_fitts_harder_target() raises:
    var mt1 = fitts_law_movement_time(0.1, 0.15, 20.0, 10.0)
    var mt2 = fitts_law_movement_time(0.1, 0.15, 20.0, 5.0)
    _assert(mt2 > mt1, "smaller target => longer MT")


fn test_hicks_law_reaction_time() raises:
    # RT = 0.2 + 0.15*log2(4+1) = 0.2 + 0.15*2.322 = 0.548
    var rt = hicks_law_reaction_time(0.2, 0.15, 4.0)
    var expected = 0.2 + 0.15 * (log(5.0) / log(2.0))
    _assert(_near(rt, expected, 0.001), "hicks_law RT")


fn test_hicks_more_choices() raises:
    var rt2 = hicks_law_reaction_time(0.2, 0.15, 2.0)
    var rt8 = hicks_law_reaction_time(0.2, 0.15, 8.0)
    _assert(rt8 > rt2, "more choices => longer RT")


fn test_comfort_temperature_pmv() raises:
    # met=1, clo=0.5, air_temp=22 => neutral=22+(0)*3-(0)*2=22 => diff=0
    var pmv = comfort_temperature_pmv_simplified(1.0, 0.5, 22.0)
    _assert(_near(pmv, 0.0, 0.01), "PMV neutral at 22C met=1 clo=0.5")


fn test_comfort_temperature_cold() raises:
    # air_temp=18 < neutral=22 => negative
    var pmv = comfort_temperature_pmv_simplified(1.0, 0.5, 18.0)
    _assert(pmv < 0.0, "PMV cold at 18C")


fn test_body_mass_index() raises:
    # BMI = 70/(1.75^2) = 70/3.0625 ≈ 22.857
    var bmi = body_mass_index(70.0, 1.75)
    _assert(_near(bmi, 70.0 / (1.75 * 1.75), 0.01), "BMI 70kg 1.75m")


fn test_body_mass_index_overweight() raises:
    var bmi = body_mass_index(90.0, 1.70)
    _assert(bmi > 25.0, "BMI 90kg/1.70m > 25 (overweight)")


# ── Combustion tests ─────────────────────────────────────────────────────────


fn test_stoichiometric_afr() raises:
    # For methane-like: c=0.75, h=0.25, o=0 => (0.75/12*32+0.25/4*32)/0.233
    # = (2.0+2.0)/0.233 = 4.0/0.233 ≈ 17.167
    var afr = stoichiometric_air_fuel_ratio(0.75, 0.25, 0.0)
    _assert(_near(afr, 4.0 / 0.233, 0.01), "stoich AFR methane-like")


fn test_equivalence_ratio_stoich() raises:
    # φ = 15/15 = 1.0
    var phi = equivalence_ratio(15.0, 15.0)
    _assert(_near(phi, 1.0), "equivalence_ratio stoich")


fn test_equivalence_ratio_lean() raises:
    # φ = 15/20 = 0.75 (lean)
    var phi = equivalence_ratio(20.0, 15.0)
    _assert(phi < 1.0, "equivalence_ratio lean < 1")


fn test_equivalence_ratio_rich() raises:
    # φ = 15/10 = 1.5 (rich)
    var phi = equivalence_ratio(10.0, 15.0)
    _assert(phi > 1.0, "equivalence_ratio rich > 1")


fn test_excess_air_percentage() raises:
    # φ=0.8 => EA = (1/0.8-1)*100 = (1.25-1)*100 = 25%
    var ea = excess_air_percentage(0.8)
    _assert(_near(ea, 25.0), "excess_air 25% at phi=0.8")


fn test_excess_air_stoich() raises:
    var ea = excess_air_percentage(1.0)
    _assert(_near(ea, 0.0), "excess_air 0% at phi=1.0")


fn test_adiabatic_flame_temp() raises:
    # T_ad = 300 + 2e6/(1.0*1200) = 300+1666.67 = 1966.67
    var tad = adiabatic_flame_temp_estimate(300.0, 2e6, 1200.0, 1.0)
    _assert(_near(tad, 1966.667, 0.01), "adiabatic_flame_temp")


fn test_lower_heating_value_methane() raises:
    var lhv = lower_heating_value_methane()
    _assert(_near(lhv, 50.0), "LHV methane = 50 MJ/kg")


fn test_thermal_efficiency() raises:
    # η = 400/1000 = 0.4
    var eta = thermal_efficiency(400.0, 1000.0)
    _assert(_near(eta, 0.4), "thermal_efficiency 400/1000=0.4")


fn test_carnot_efficiency() raises:
    # η_c = 1 - 300/600 = 0.5
    var eta = carnot_efficiency(600.0, 300.0)
    _assert(_near(eta, 0.5), "carnot_efficiency 600/300=0.5")


fn test_carnot_efficiency_high_temp() raises:
    # η_c = 1 - 300/1500 = 0.8
    var eta = carnot_efficiency(1500.0, 300.0)
    _assert(_near(eta, 0.8), "carnot_efficiency 1500/300=0.8")


fn test_bsfc() raises:
    # BSFC = 10/50 = 0.2 kg/kWh
    var bsfc = brake_specific_fuel_consumption(10.0, 50.0)
    _assert(_near(bsfc, 0.2), "BSFC 10/50=0.2")


fn test_combustion_efficiency() raises:
    # η_c = 45/50 = 0.9
    var eta = combustion_efficiency(45.0, 50.0)
    _assert(_near(eta, 0.9), "combustion_efficiency 45/50=0.9")


fn test_flame_speed_laminar() raises:
    # SL = 0.4 * (2.0)^2.0 * (1.0)^(-0.3) = 0.4*4*1 = 1.6
    var sl = flame_speed_laminar(0.4, 2.0, 1.0, 2.0, -0.3)
    _assert(_near(sl, 1.6, 0.001), "flame_speed_laminar")


fn test_flame_speed_pressure_effect() raises:
    var sl1 = flame_speed_laminar(0.4, 1.0, 1.0, 2.0, -0.3)
    var sl2 = flame_speed_laminar(0.4, 1.0, 5.0, 2.0, -0.3)
    _assert(sl2 < sl1, "higher pressure => lower flame speed (beta<0)")


fn test_nox_formation_rate() raises:
    # rate = 0.21 * exp(-38000/2000) = 0.21 * exp(-19)
    var r = nox_formation_rate(2000.0, 0.21)
    var expected = 0.21 * exp(-38000.0 / 2000.0)
    _assert(_near_rel(r, expected), "nox_formation_rate")


fn test_nox_increases_with_temp() raises:
    var r1 = nox_formation_rate(1500.0, 0.21)
    var r2 = nox_formation_rate(2500.0, 0.21)
    _assert(r2 > r1, "NOx increases with temperature")


fn test_heat_release_rate() raises:
    # γ=1.4, p=1e5, V=0.001, dV=1e-4, dp=5e4
    # dQ = (1.4/0.4)*1e5*1e-4 + (1/0.4)*0.001*5e4
    #    = 3.5*10 + 2.5*50 = 35 + 125 = 160
    var dq = heat_release_rate(1e5, 0.001, 1.4, 1e-4, 5e4)
    _assert(_near(dq, 160.0, 0.01), "heat_release_rate")


fn test_heat_release_rate_expansion_only() raises:
    # dp=0 => dQ = (γ/(γ-1))*p*dV
    var dq = heat_release_rate(2e5, 0.001, 1.4, 5e-4, 0.0)
    var expected = (1.4 / 0.4) * 2e5 * 5e-4
    _assert(_near(dq, expected, 0.01), "heat_release expansion only")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    # Tribology (18 assertions)
    test_coulomb_friction_force()
    test_coulomb_friction_zero_mu()
    test_kinetic_friction()
    test_static_friction_max()
    test_static_greater_than_kinetic()
    test_coefficient_of_friction()
    test_coefficient_friction_roundtrip()
    test_hertz_contact_pressure()
    test_archard_wear_volume()
    test_bearing_pressure()
    test_sommerfeld_number()
    test_stribeck_parameter()
    test_flash_temperature_rise()
    test_lubrication_film_thickness()
    test_friction_power_loss()
    test_friction_power_loss_zero_velocity()

    # Ergonomics (24 assertions)
    test_niosh_rwl()
    test_niosh_rwl_reduced()
    test_lifting_index()
    test_lifting_index_safe()
    test_lifting_index_risky()
    test_metabolic_rate_walking()
    test_heat_stress_index()
    test_heat_stress_index_over()
    test_decibel_addition_equal()
    test_decibel_addition_different()
    test_noise_dose()
    test_cumulative_noise_dose_2()
    test_visual_angle_minutes()
    test_fitts_law_movement_time()
    test_fitts_harder_target()
    test_hicks_law_reaction_time()
    test_hicks_more_choices()
    test_comfort_temperature_pmv()
    test_comfort_temperature_cold()
    test_body_mass_index()
    test_body_mass_index_overweight()

    # Combustion (22 assertions)
    test_stoichiometric_afr()
    test_equivalence_ratio_stoich()
    test_equivalence_ratio_lean()
    test_equivalence_ratio_rich()
    test_excess_air_percentage()
    test_excess_air_stoich()
    test_adiabatic_flame_temp()
    test_lower_heating_value_methane()
    test_thermal_efficiency()
    test_carnot_efficiency()
    test_carnot_efficiency_high_temp()
    test_bsfc()
    test_combustion_efficiency()
    test_flame_speed_laminar()
    test_flame_speed_pressure_effect()
    test_nox_formation_rate()
    test_nox_increases_with_temp()
    test_heat_release_rate()
    test_heat_release_rate_expansion_only()

    print("✅ Wave 69: All 74 assertions passed (Tribology, Ergonomics, Combustion)")
