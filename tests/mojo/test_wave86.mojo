"""Tests for Wave 86 — Paper Science, Radar, Veterinary."""

from paper_science import (
    basis_weight,
    caliper_to_density,
    bulk,
    tearing_resistance_index,
    tensile_index,
    burst_index,
    freeness_csf,
    kappa_number_to_lignin,
    pulp_yield,
    moisture_content_paper,
    stiffness_index,
    recycled_fiber_content,
)
from radar import (
    radar_range_equation,
    doppler_frequency,
    doppler_velocity,
    range_from_time,
    pulse_repetition_interval,
    max_unambiguous_range,
    max_unambiguous_velocity,
    range_resolution,
    antenna_gain_from_area,
    radar_cross_section_sphere,
    noise_power,
    signal_to_clutter,
)
from veterinary import (
    dose_mg,
    fluid_rate_ml_hr,
    fluid_deficit,
    maintenance_fluid_dog,
    caloric_requirement_dog,
    body_condition_score_ideal,
    anesthesia_mac,
    gestation_period_days,
    heart_rate_normal_range_low,
    heart_rate_normal_range_high,
    packed_cell_volume_normal,
    blood_volume_estimate,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


def rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Paper Science Tests ─────────────────────────────────────────────────────


def test_paper_science() raises:
    # basis_weight: 80g over 1 m² = 80 GSM
    assert_true(approx_eq(basis_weight(80.0, 1.0), 80.0))
    # 160g over 2 m² = 80 GSM
    assert_true(approx_eq(basis_weight(160.0, 2.0), 80.0))

    # caliper_to_density: 80 GSM, 0.1mm caliper → 80/(0.1*1000) = 0.8 g/cm³
    assert_true(approx_eq(caliper_to_density(80.0, 0.1), 0.8))
    # 100 GSM, 0.125mm → 100/125 = 0.8
    assert_true(approx_eq(caliper_to_density(100.0, 0.125), 0.8))

    # bulk: 0.1mm, 80 GSM → 0.1*1000/80 = 1.25 cm³/g
    assert_true(approx_eq(bulk(0.1, 80.0), 1.25))

    # tearing_resistance_index: 800 mN, 80 GSM → 10
    assert_true(approx_eq(tearing_resistance_index(800.0, 80.0), 10.0))

    # tensile_index: 5 kN/m, 80 GSM → 5*1000/80 = 62.5 N·m/g
    assert_true(approx_eq(tensile_index(5.0, 80.0), 62.5))

    # burst_index: 240 kPa, 80 GSM → 3.0 kPa·m²/g
    assert_true(approx_eq(burst_index(240.0, 80.0), 3.0))

    # freeness_csf: pass-through
    assert_true(approx_eq(freeness_csf(450.0), 450.0))
    assert_true(approx_eq(freeness_csf(200.0), 200.0))

    # kappa_number_to_lignin: kappa 30 → 4.5%
    assert_true(approx_eq(kappa_number_to_lignin(30.0), 4.5))
    # kappa 20 → 3.0%
    assert_true(approx_eq(kappa_number_to_lignin(20.0), 3.0))

    # pulp_yield: 450kg from 1000kg → 45%
    assert_true(approx_eq(pulp_yield(450.0, 1000.0), 45.0))

    # moisture_content_paper: wet=110, dry=100 → 9.0909%
    assert_true(rel_eq(moisture_content_paper(110.0, 100.0), 9.0909))

    # stiffness_index: stiffness=512000, BW=80 → 512000/512000 = 1.0
    assert_true(approx_eq(stiffness_index(512000.0, 80.0), 1.0))

    # recycled_fiber_content: 30 of 100 → 30%
    assert_true(approx_eq(recycled_fiber_content(30.0, 100.0), 30.0))
    # 75 of 150 → 50%
    assert_true(approx_eq(recycled_fiber_content(75.0, 150.0), 50.0))

    print("  ✓ paper_science: all tests passed")


# ── Radar Tests ──────────────────────────────────────────────────────────────


def test_radar() raises:
    # doppler_frequency: 300 m/s, λ=0.03m → 2*300/0.03 = 20000 Hz
    assert_true(approx_eq(doppler_frequency(300.0, 0.03), 20000.0))

    # doppler_velocity: fd=20000, λ=0.03 → 20000*0.03/2 = 300
    assert_true(approx_eq(doppler_velocity(20000.0, 0.03), 300.0))

    # range_from_time: t=1e-5, c=3e8 → 3e8*1e-5/2 = 1500 m
    assert_true(approx_eq(range_from_time(1e-5, 3e8), 1500.0))

    # pulse_repetition_interval: PRF=1000 → PRI=0.001
    assert_true(approx_eq(pulse_repetition_interval(1000.0), 0.001))

    # max_unambiguous_range: PRF=1000, c=3e8 → 150000 m
    assert_true(approx_eq(max_unambiguous_range(1000.0, 3e8), 150000.0))

    # max_unambiguous_velocity: PRF=1000, λ=0.03 → 1000*0.03/4 = 7.5
    assert_true(approx_eq(max_unambiguous_velocity(1000.0, 0.03), 7.5))

    # range_resolution: B=1e6 → 3e8/(2*1e6) = 150 m
    assert_true(approx_eq(range_resolution(1e6), 150.0))
    # B=10e6 → 15 m
    assert_true(approx_eq(range_resolution(10e6), 15.0))

    # antenna_gain_from_area: Ae=1.0 m², λ=0.1 m
    # G = 4*π*1.0/(0.01) = 4*3.14159.../0.01 ≈ 1256.637
    var g = antenna_gain_from_area(1.0, 0.1)
    assert_true(rel_eq(g, 1256.637))

    # radar_cross_section_sphere: r=1 → π*1 ≈ 3.14159
    assert_true(rel_eq(radar_cross_section_sphere(1.0), 3.14159))
    # r=2 → π*4 ≈ 12.5664
    assert_true(rel_eq(radar_cross_section_sphere(2.0), 12.5664))

    # noise_power: B=1e6, F=4, T=290 → 1.38e-23*290*1e6*4 = 1.6008e-14
    var np = noise_power(1e6, 4.0, 290.0)
    assert_true(rel_eq(np, 1.6008e-14))

    # signal_to_clutter: S=100, C=10 → 10.0
    assert_true(approx_eq(signal_to_clutter(100.0, 10.0), 10.0))

    # radar_range_equation: simple values
    # pt=1000, gt=30, gr=30, λ=0.03, σ=1, Fn=4, B=1e6, SNR=10
    # = 1000*30*30*0.0009*1 / (10*4*1e6)
    # = 810 / 40000000 = 2.025e-5
    var rre = radar_range_equation(1000.0, 30.0, 30.0, 0.03, 1.0, 4.0, 1e6, 10.0)
    assert_true(rel_eq(rre, 2.025e-5))

    # max_unambiguous_range with higher PRF
    assert_true(approx_eq(max_unambiguous_range(5000.0, 3e8), 30000.0))

    # doppler roundtrip consistency: v→fd→v
    var v_orig = 150.0
    var lam = 0.05
    var fd = doppler_frequency(v_orig, lam)
    var v_back = doppler_velocity(fd, lam)
    assert_true(approx_eq(v_back, v_orig))

    print("  ✓ radar: all tests passed")


# ── Veterinary Tests ─────────────────────────────────────────────────────────


def test_veterinary() raises:
    # dose_mg: 25kg dog, 10 mg/kg → 250 mg
    assert_true(approx_eq(dose_mg(25.0, 10.0), 250.0))
    # 4kg cat, 5 mg/kg → 20 mg
    assert_true(approx_eq(dose_mg(4.0, 5.0), 20.0))

    # fluid_rate_ml_hr: 480 mL over 8 hrs → 60 mL/hr
    assert_true(approx_eq(fluid_rate_ml_hr(480.0, 8.0), 60.0))

    # fluid_deficit: 10kg, 8% → 10*8/100*1000 = 800 mL
    assert_true(approx_eq(fluid_deficit(10.0, 8.0), 800.0))
    # 5kg, 5% → 250 mL
    assert_true(approx_eq(fluid_deficit(5.0, 5.0), 250.0))

    # maintenance_fluid_dog: 20kg → 1200 mL/day
    assert_true(approx_eq(maintenance_fluid_dog(20.0), 1200.0))

    # caloric_requirement_dog: 10kg → 70 * 10^0.75
    # 10^0.75 = 5.6234... → RER ≈ 393.64
    var rer = caloric_requirement_dog(10.0)
    assert_true(rel_eq(rer, 393.64, 0.01))

    # caloric_requirement_dog: 5kg → 70 * 5^0.75
    # 5^0.75 ≈ 3.3437 → RER ≈ 234.06
    var rer5 = caloric_requirement_dog(5.0)
    assert_true(rel_eq(rer5, 234.06, 0.01))

    # body_condition_score_ideal: dog=5, cat=5
    assert_true(approx_eq(body_condition_score_ideal(0), 5.0))
    assert_true(approx_eq(body_condition_score_ideal(1), 5.0))

    # anesthesia_mac
    assert_true(approx_eq(anesthesia_mac(0, 0), 1.3))  # Dog, iso
    assert_true(approx_eq(anesthesia_mac(1, 0), 1.6))  # Cat, iso
    assert_true(approx_eq(anesthesia_mac(0, 1), 2.4))  # Dog, sevo
    assert_true(approx_eq(anesthesia_mac(1, 1), 3.1))  # Cat, sevo

    # gestation_period_days
    assert_true(approx_eq(gestation_period_days(0), 63.0))   # Dog
    assert_true(approx_eq(gestation_period_days(1), 65.0))   # Cat
    assert_true(approx_eq(gestation_period_days(2), 340.0))  # Horse
    assert_true(approx_eq(gestation_period_days(3), 283.0))  # Cow

    # heart_rate_normal_range_low
    assert_true(approx_eq(heart_rate_normal_range_low(0), 60.0))
    assert_true(approx_eq(heart_rate_normal_range_low(1), 120.0))
    assert_true(approx_eq(heart_rate_normal_range_low(2), 28.0))

    # heart_rate_normal_range_high
    assert_true(approx_eq(heart_rate_normal_range_high(0), 140.0))
    assert_true(approx_eq(heart_rate_normal_range_high(1), 220.0))
    assert_true(approx_eq(heart_rate_normal_range_high(2), 44.0))

    # packed_cell_volume_normal
    assert_true(approx_eq(packed_cell_volume_normal(0), 46.0))
    assert_true(approx_eq(packed_cell_volume_normal(1), 37.5))

    # blood_volume_estimate: 25kg dog → 2250 mL
    assert_true(approx_eq(blood_volume_estimate(25.0, 0), 2250.0))
    # 4kg cat → 240 mL
    assert_true(approx_eq(blood_volume_estimate(4.0, 1), 240.0))

    print("  ✓ veterinary: all tests passed")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 86 tests:")
    test_paper_science()
    test_radar()
    test_veterinary()
    print("All Wave 86 tests passed ✓")
