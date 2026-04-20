"""Tests for Wave 91 — Drones, Dentistry, Rubber."""

from drones import (
    thrust_to_weight_ratio,
    hover_power,
    flight_time_minutes,
    max_range,
    payload_capacity,
    disk_loading,
    propeller_tip_speed,
    advance_ratio,
    battery_energy_density,
    communication_range_los,
    gsd_from_altitude,
    endurance_factor,
)
from dentistry import (
    dmft_index,
    dmft_prevalence,
    plaque_index_score,
    gingival_index,
    attachment_loss,
    bone_loss_percentage,
    fluoride_concentration_ppm,
    anesthesia_dose_mg,
    max_anesthesia_dose,
    restoration_longevity_estimate,
    tooth_surface_area_estimate,
    treatment_cost_estimate,
)
from rubber import (
    shore_a_to_youngs_modulus,
    mooney_viscosity_index,
    tensile_set,
    compression_set,
    elongation_at_break,
    tear_strength,
    resilience_rebound,
    hardness_change_aging,
    swelling_percentage,
    crosslink_density_estimate,
    abrasion_loss_volume,
    heat_buildup,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _approx(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a - b) < eps
    return fabs(a - b) / fabs(b) < eps


# ── Drone tests ──────────────────────────────────────────────────────────────


fn test_drones() raises:
    # thrust_to_weight_ratio
    assert_true(_approx(thrust_to_weight_ratio(40.0, 20.0), 2.0), "twr basic")
    assert_true(_approx(thrust_to_weight_ratio(15.0, 15.0), 1.0), "twr=1")
    assert_true(_approx(thrust_to_weight_ratio(10.0, 0.0), 0.0), "twr div0")

    # hover_power: P = W^1.5 / sqrt(2*rho*A)
    # W=10, A=0.5, rho=1.225 => 10^1.5 / sqrt(2*1.225*0.5) = 31.6228/1.1068 ≈ 28.573
    var hp = hover_power(10.0, 0.5, 1.225)
    var expected_hp = 31.6227766 / sqrt(2.0 * 1.225 * 0.5)
    assert_true(_approx(hp, expected_hp, 1e-3), "hover_power")
    assert_true(_approx(hover_power(10.0, 0.0, 1.225), 0.0), "hover_power 0 area")

    # flight_time_minutes: t = (bat/power)*60
    assert_true(_approx(flight_time_minutes(100.0, 200.0), 30.0), "ft 30min")
    assert_true(_approx(flight_time_minutes(50.0, 100.0), 30.0), "ft 30min2")
    assert_true(_approx(flight_time_minutes(100.0, 0.0), 0.0), "ft div0")

    # max_range: R = speed * time/60
    assert_true(_approx(max_range(60.0, 30.0), 30.0), "range 30km")
    assert_true(_approx(max_range(120.0, 15.0), 30.0), "range 30km alt")

    # payload_capacity: PC = MTOW - empty - battery
    assert_true(_approx(payload_capacity(25.0, 12.0, 5.0), 8.0), "payload 8kg")
    assert_true(_approx(payload_capacity(10.0, 6.0, 3.0), 1.0), "payload 1kg")

    # disk_loading: DL = W/A
    assert_true(_approx(disk_loading(100.0, 2.0), 50.0), "dl 50")
    assert_true(_approx(disk_loading(100.0, 0.0), 0.0), "dl div0")

    # propeller_tip_speed: v = π*D*RPM/60
    # RPM=6000, D=0.3 => π*0.3*6000/60 = π*30 ≈ 94.2478
    var pts = propeller_tip_speed(6000.0, 0.3)
    assert_true(_approx(pts, 94.2477796, 1e-3), "tip_speed")

    # advance_ratio: J = V/(n*D), n=RPM/60
    # V=10, RPM=3000, D=0.5 => n=50, J=10/(50*0.5)=0.4
    assert_true(_approx(advance_ratio(10.0, 3000.0, 0.5), 0.4), "adv_ratio")
    assert_true(_approx(advance_ratio(10.0, 0.0, 0.5), 0.0), "adv_ratio div0")

    # battery_energy_density: ED = E/m
    assert_true(_approx(battery_energy_density(250.0, 1.0), 250.0), "bed 250")
    assert_true(_approx(battery_energy_density(500.0, 2.5), 200.0), "bed 200")
    assert_true(_approx(battery_energy_density(100.0, 0.0), 0.0), "bed div0")

    # communication_range_los: R = sqrt(2*Re*h + h²)
    # h=100, Re=6371000 => sqrt(2*6371000*100 + 10000) = sqrt(1274210000) ≈ 35696.8
    var cr = communication_range_los(100.0, 6371000.0)
    var expected_cr = sqrt(2.0 * 6371000.0 * 100.0 + 100.0 * 100.0)
    assert_true(_approx(cr, expected_cr, 1e-3), "comm_range")

    # gsd_from_altitude: GSD = (alt*sw)/(fl*iw)*1000
    # alt=100, sw=13.2, fl=8.8, iw=4000 => (100*13.2)/(8.8*4000)*1000 = 1320/35200*1000 = 37.5
    var gsd = gsd_from_altitude(8.8, 13.2, 4000.0, 100.0)
    assert_true(_approx(gsd, 37.5, 1e-3), "gsd")

    # endurance_factor: EF = (cap*volt*eff/power)*60
    # cap=5, volt=22.2, eff=0.8, power=200 => (5*22.2*0.8/200)*60 = 26.64
    assert_true(_approx(endurance_factor(5.0, 22.2, 0.8, 200.0), 26.64), "endurance")
    assert_true(_approx(endurance_factor(5.0, 22.2, 0.8, 0.0), 0.0), "endurance div0")

    print("  ✓ drones (26 assertions)")


# ── Dentistry tests ──────────────────────────────────────────────────────────


fn test_dentistry() raises:
    # dmft_index
    assert_equal(dmft_index(3, 2, 5), 10, "dmft 10")
    assert_equal(dmft_index(0, 0, 0), 0, "dmft 0")

    # dmft_prevalence
    assert_true(_approx(dmft_prevalence(80, 100), 80.0), "prev 80")
    assert_true(_approx(dmft_prevalence(0, 100), 0.0), "prev 0")
    assert_true(_approx(dmft_prevalence(5, 0), 0.0), "prev div0")

    # plaque_index_score
    assert_true(_approx(plaque_index_score(12.0, 6), 2.0), "pi 2.0")
    assert_true(_approx(plaque_index_score(7.5, 5), 1.5), "pi 1.5")

    # gingival_index
    assert_true(_approx(gingival_index(8.0, 4), 2.0), "gi 2.0")
    assert_true(_approx(gingival_index(3.0, 6), 0.5), "gi 0.5")

    # attachment_loss: CAL = PD + recession
    assert_true(_approx(attachment_loss(4.0, 2.0), 6.0), "cal 6")
    assert_true(_approx(attachment_loss(3.0, 0.0), 3.0), "cal 3")

    # bone_loss_percentage: BL = (orig-curr)/orig*100
    assert_true(_approx(bone_loss_percentage(20.0, 15.0), 25.0), "bl 25%")
    assert_true(_approx(bone_loss_percentage(10.0, 10.0), 0.0), "bl 0%")

    # fluoride_concentration_ppm
    assert_true(_approx(fluoride_concentration_ppm(1.0, 1.0), 1.0), "fl 1ppm")
    assert_true(_approx(fluoride_concentration_ppm(5.0, 2.0), 2.5), "fl 2.5ppm")

    # anesthesia_dose_mg: Dose = carpules * mg/ml * ml/carpule
    # 2 carpules * 20 mg/ml * 1.8 ml = 72 mg
    assert_true(_approx(anesthesia_dose_mg(2.0, 20.0, 1.8), 72.0), "anes 72")

    # max_anesthesia_dose: Max = weight * max_per_kg
    assert_true(_approx(max_anesthesia_dose(70.0, 7.0), 490.0), "maxanes 490")

    # restoration_longevity_estimate: Years = 10 * mat * (1/load)
    assert_true(_approx(restoration_longevity_estimate(1.5, 1.0), 15.0), "rest 15y")
    assert_true(_approx(restoration_longevity_estimate(1.0, 2.0), 5.0), "rest 5y")

    # tooth_surface_area_estimate: Total = n * avg
    assert_true(_approx(tooth_surface_area_estimate(28, 50.0), 1400.0), "tsa 1400")

    # treatment_cost_estimate: Cost = units * cost * factor
    assert_true(_approx(treatment_cost_estimate(3, 200.0, 1.5), 900.0), "cost 900")
    assert_true(_approx(treatment_cost_estimate(1, 500.0, 1.0), 500.0), "cost 500")

    print("  ✓ dentistry (24 assertions)")


# ── Rubber tests ─────────────────────────────────────────────────────────────


fn test_rubber() raises:
    # shore_a_to_youngs_modulus: E = 0.5 * exp(0.04 * shore_a)
    # shore_a=50 => 0.5*exp(2.0) ≈ 0.5*7.389056 = 3.694528
    var e50 = shore_a_to_youngs_modulus(50.0)
    assert_true(_approx(e50, 0.5 * exp(2.0), 1e-4), "shore 50")
    # shore_a=0 => 0.5*exp(0) = 0.5
    assert_true(_approx(shore_a_to_youngs_modulus(0.0), 0.5), "shore 0")

    # mooney_viscosity_index
    assert_true(_approx(mooney_viscosity_index(45.0, 100.0), 45.0), "mooney 45")

    # tensile_set: TS = (recov-orig)/(stretch-orig)*100
    # stretch=200, orig=100, recov=110 => (10/100)*100 = 10%
    assert_true(_approx(tensile_set(200.0, 100.0, 110.0), 10.0), "ts 10%")
    assert_true(_approx(tensile_set(100.0, 100.0, 100.0), 0.0), "ts div0")

    # compression_set: CS = (orig-recov)/(orig-comp)*100
    # orig=10, comp=5, recov=8 => (10-8)/(10-5)*100 = 40%
    assert_true(_approx(compression_set(10.0, 5.0, 8.0), 40.0), "cs 40%")
    assert_true(_approx(compression_set(10.0, 5.0, 10.0), 0.0), "cs 0%")

    # elongation_at_break: EB = (final-orig)/orig*100
    # final=500, orig=100 => 400%
    assert_true(_approx(elongation_at_break(500.0, 100.0), 400.0), "eb 400%")
    assert_true(_approx(elongation_at_break(200.0, 100.0), 100.0), "eb 100%")

    # tear_strength: TS = F/t
    assert_true(_approx(tear_strength(50.0, 2.0), 25.0), "tear 25")
    assert_true(_approx(tear_strength(100.0, 0.0), 0.0), "tear div0")

    # resilience_rebound: R = rebound/drop*100
    assert_true(_approx(resilience_rebound(100.0, 60.0), 60.0), "resil 60%")
    assert_true(_approx(resilience_rebound(100.0, 45.0), 45.0), "resil 45%")

    # hardness_change_aging: ΔH = aged - initial
    assert_true(_approx(hardness_change_aging(60.0, 65.0), 5.0), "hca +5")
    assert_true(_approx(hardness_change_aging(70.0, 68.0), -2.0), "hca -2")

    # swelling_percentage: S = (swollen-orig)/orig*100
    # swollen=130, orig=100 => 30%
    assert_true(_approx(swelling_percentage(130.0, 100.0), 30.0), "swell 30%")
    assert_true(_approx(swelling_percentage(100.0, 100.0), 0.0), "swell 0%")

    # crosslink_density_estimate: ν = E/(3*R*T)
    # E=1e6, T=300, R=8.314 => 1e6/(3*8.314*300) = 1e6/7482.6 ≈ 133.644
    var cd = crosslink_density_estimate(1e6, 300.0, 8.314)
    var expected_cd = 1e6 / (3.0 * 8.314 * 300.0)
    assert_true(_approx(cd, expected_cd, 1e-3), "crosslink")

    # abrasion_loss_volume: V = mass/density
    assert_true(_approx(abrasion_loss_volume(0.5, 1.25), 0.4), "abrasion 0.4")
    assert_true(_approx(abrasion_loss_volume(1.0, 0.0), 0.0), "abrasion div0")

    # heat_buildup: ΔT = hyst*freq*time/1000
    # hyst=0.5, freq=10, time=600 => 0.5*10*600/1000 = 3.0
    assert_true(_approx(heat_buildup(0.5, 10.0, 600.0), 3.0), "heatup 3.0")
    assert_true(_approx(heat_buildup(0.2, 5.0, 1000.0), 1.0), "heatup 1.0")

    print("  ✓ rubber (24 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 91 tests")
    test_drones()
    test_dentistry()
    test_rubber()
    print("All Wave 91 tests passed ✓  (74 assertions)")
