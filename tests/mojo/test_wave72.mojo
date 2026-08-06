"""Tests for Wave 72 — Forensics, Transportation, Nuclear."""

from forensics import (
    time_of_death_newton,
    algor_mortis_rate,
    blood_alcohol_widmark,
    alcohol_elimination_rate,
    rigor_mortis_stage,
    ballistic_drop,
    bloodstain_impact_angle,
    dna_match_probability,
    fingerprint_minutiae_score,
    glass_refractive_index_match,
    decomposition_add,
    toxicology_lethal_dose,
)
from transportation import (
    level_of_service_density,
    highway_capacity,
    travel_time,
    delay_at_signal,
    headway,
    stopping_distance,
    fuel_consumption_rate,
    passenger_car_equivalent,
    intersection_capacity,
    queue_length_estimate,
    vehicle_operating_cost,
    crash_rate,
)
from nuclear import (
    radioactive_decay,
    half_life_from_lambda,
    lambda_from_half_life,
    activity,
    decay_constant_from_activity,
    binding_energy_per_nucleon,
    mass_defect,
    q_value,
    neutron_multiplication,
    dose_rate_inverse_square,
    shielding_attenuation,
    critical_mass_estimate,
)
from std.math import abs as fabs, exp, log, asin, pow

comptime PI: Float64 = 3.141592653589793
comptime LN2: Float64 = 0.6931471805599453


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


# ── Forensics tests ─────────────────────────────────────────────────────────


def test_time_of_death_newton() raises:
    # Body at 30°C, ambient 20°C, normal 37°C, k=0.1
    # t = -ln((30-20)/(37-20))/0.1 = -ln(10/17)/0.1
    var v = time_of_death_newton(30.0, 20.0, 37.0, 0.1)
    var expected = -log(10.0 / 17.0) / 0.1
    _assert(fabs(v - expected) < 0.01, "time_of_death_newton basic")

    # Body = ambient → ratio ≤ 0 → returns 0
    var v2 = time_of_death_newton(20.0, 20.0, 37.0, 0.1)
    _assert(v2 == 0.0, "time_of_death_newton body=ambient")

    # k=0 → returns 0
    var v3 = time_of_death_newton(30.0, 20.0, 37.0, 0.0)
    _assert(v3 == 0.0, "time_of_death_newton k=0")
    print("  ✓ time_of_death_newton")


def test_algor_mortis_rate() raises:
    # (35 - 20) / 10 = 1.5
    var v = algor_mortis_rate(35.0, 20.0)
    _assert(fabs(v - 1.5) < 0.001, "algor_mortis_rate basic")

    var v2 = algor_mortis_rate(20.0, 20.0)
    _assert(fabs(v2) < 0.001, "algor_mortis_rate equal temps")
    print("  ✓ algor_mortis_rate")


def test_blood_alcohol_widmark() raises:
    # BAC = 40 / (80 * 0.68) = 0.7353
    var v = blood_alcohol_widmark(40.0, 80.0, 0.68)
    _assert(fabs(v - 40.0 / (80.0 * 0.68)) < 0.001, "widmark basic")

    # Zero weight → 0
    var v2 = blood_alcohol_widmark(40.0, 0.0, 0.68)
    _assert(v2 == 0.0, "widmark zero weight")
    print("  ✓ blood_alcohol_widmark")


def test_alcohol_elimination_rate() raises:
    # 0.08 - 0.015*2 = 0.05
    var v = alcohol_elimination_rate(0.08, 2.0, 0.015)
    _assert(fabs(v - 0.05) < 0.001, "elimination basic")

    # Clamp to 0
    var v2 = alcohol_elimination_rate(0.02, 10.0, 0.015)
    _assert(v2 == 0.0, "elimination clamp zero")
    print("  ✓ alcohol_elimination_rate")


def test_rigor_mortis_stage() raises:
    _assert(rigor_mortis_stage(0.5) == 0, "rigor stage 0")
    _assert(rigor_mortis_stage(1.9) == 0, "rigor stage 0 edge")
    _assert(rigor_mortis_stage(3.0) == 1, "rigor stage 1")
    _assert(rigor_mortis_stage(8.0) == 2, "rigor stage 2")
    _assert(rigor_mortis_stage(24.0) == 3, "rigor stage 3")
    _assert(rigor_mortis_stage(48.0) == 4, "rigor stage 4")
    print("  ✓ rigor_mortis_stage")


def test_ballistic_drop() raises:
    # drop = 0.5 * 9.81 * (100/800)² = 0.5*9.81*0.015625 = 0.07664
    var v = ballistic_drop(800.0, 100.0, 9.81)
    var expected = 0.5 * 9.81 * (100.0 / 800.0) * (100.0 / 800.0)
    _assert(fabs(v - expected) < 0.001, "ballistic_drop basic")

    # Zero velocity → 0
    var v2 = ballistic_drop(0.0, 100.0, 9.81)
    _assert(v2 == 0.0, "ballistic_drop zero vel")
    print("  ✓ ballistic_drop")


def test_bloodstain_impact_angle() raises:
    # sin(θ) = 0.5 → θ = π/6 ≈ 0.5236
    var v = bloodstain_impact_angle(5.0, 10.0)
    _assert(fabs(v - asin(0.5)) < 0.001, "bloodstain angle 30°")

    # width = length → sin(θ)=1 → θ=π/2
    var v2 = bloodstain_impact_angle(10.0, 10.0)
    _assert(fabs(v2 - asin(1.0)) < 0.001, "bloodstain angle 90°")

    # Zero length → 0
    var v3 = bloodstain_impact_angle(5.0, 0.0)
    _assert(v3 == 0.0, "bloodstain zero length")
    print("  ✓ bloodstain_impact_angle")


def test_dna_match_probability() raises:
    # P = 2 * 0.1 * 0.2 = 0.04
    var v = dna_match_probability(0.1, 0.2)
    _assert(fabs(v - 0.04) < 0.0001, "dna match basic")

    var v2 = dna_match_probability(0.5, 0.5)
    _assert(fabs(v2 - 0.5) < 0.0001, "dna match equal freq")
    print("  ✓ dna_match_probability")


def test_fingerprint_minutiae_score() raises:
    var v = fingerprint_minutiae_score(12.0, 16.0)
    _assert(fabs(v - 0.75) < 0.001, "minutiae score 75%")

    var v2 = fingerprint_minutiae_score(5.0, 0.0)
    _assert(v2 == 0.0, "minutiae zero total")
    print("  ✓ fingerprint_minutiae_score")


def test_glass_refractive_index_match() raises:
    _assert(glass_refractive_index_match(1.518, 1.519, 0.005), "glass match close")
    _assert(not glass_refractive_index_match(1.518, 1.530, 0.005), "glass no match")
    print("  ✓ glass_refractive_index_match")


def test_decomposition_add() raises:
    # ADD = 100 + max(0,25)*48/24 = 100 + 50 = 150
    var v = decomposition_add(100.0, 25.0, 48.0)
    _assert(fabs(v - 150.0) < 0.01, "decomposition add positive")

    # Negative temp → no contribution
    var v2 = decomposition_add(100.0, -5.0, 48.0)
    _assert(fabs(v2 - 100.0) < 0.01, "decomposition add negative temp")
    print("  ✓ decomposition_add")


def test_toxicology_lethal_dose() raises:
    # LD50=50 mg/kg, 70kg → 3500 mg
    var v = toxicology_lethal_dose(50.0, 70.0)
    _assert(fabs(v - 3500.0) < 0.01, "lethal dose basic")
    print("  ✓ toxicology_lethal_dose")


# ── Transportation tests ─────────────────────────────────────────────────────


def test_level_of_service_density() raises:
    # 1800 veh/hr / 100 km/hr = 18 veh/km
    var v = level_of_service_density(1800.0, 100.0)
    _assert(fabs(v - 18.0) < 0.01, "LOS density basic")

    var v2 = level_of_service_density(1800.0, 0.0)
    _assert(v2 == 0.0, "LOS density zero speed")
    print("  ✓ level_of_service_density")


def test_highway_capacity() raises:
    # 4 lanes * 2000 = 8000
    var v = highway_capacity(4.0, 2000.0)
    _assert(fabs(v - 8000.0) < 0.01, "highway capacity basic")
    print("  ✓ highway_capacity")


def test_travel_time() raises:
    # 120km / 60km/hr = 2hr
    var v = travel_time(120.0, 60.0)
    _assert(fabs(v - 2.0) < 0.001, "travel time basic")

    var v2 = travel_time(120.0, 0.0)
    _assert(v2 == 0.0, "travel time zero speed")
    print("  ✓ travel_time")


def test_delay_at_signal() raises:
    # C=90, g/C=0.4, λ=0.3, μ=0.5 → x=0.6
    # d = 0.5*90*(1-0.4)²/(1-0.6*0.4) = 0.5*90*0.36/(1-0.24) = 16.2/0.76 ≈ 21.316
    var v = delay_at_signal(90.0, 0.4, 0.3, 0.5)
    var expected = 0.5 * 90.0 * 0.36 / 0.76
    _assert(fabs(v - expected) < 0.1, "delay_at_signal basic")
    print("  ✓ delay_at_signal")


def test_headway() raises:
    # h = 2.5 + 30/(2*3.0) = 2.5 + 5 = 7.5
    var v = headway(30.0, 2.5, 3.0)
    _assert(fabs(v - 7.5) < 0.01, "headway basic")

    # Zero decel → just reaction time
    var v2 = headway(30.0, 2.5, 0.0)
    _assert(fabs(v2 - 2.5) < 0.01, "headway zero decel")
    print("  ✓ headway")


def test_stopping_distance() raises:
    # v=20 m/s, t=2.5s, f=0.35, G=0.0
    # d = 20*2.5 + 20²/(2*9.81*0.35) = 50 + 400/6.867 = 50 + 58.25 ≈ 108.25
    var v = stopping_distance(20.0, 2.5, 0.35, 0.0)
    var expected = 20.0 * 2.5 + 400.0 / (2.0 * 9.81 * 0.35)
    _assert(fabs(v - expected) < 0.5, "stopping distance basic")
    print("  ✓ stopping_distance")


def test_fuel_consumption_rate() raises:
    # base=8, speed=100, optimal=80 → 8*(1+0.01*400) = 8*5 = 40
    var v = fuel_consumption_rate(8.0, 100.0, 80.0)
    _assert(fabs(v - 40.0) < 0.01, "fuel consumption basic")

    # At optimal speed → base rate
    var v2 = fuel_consumption_rate(8.0, 80.0, 80.0)
    _assert(fabs(v2 - 8.0) < 0.01, "fuel consumption at optimal")
    print("  ✓ fuel_consumption_rate")


def test_passenger_car_equivalent() raises:
    # 10% trucks, terrain=2.5 → 1 + 0.1*1.5 = 1.15
    var v = passenger_car_equivalent(0.10, 2.5)
    _assert(fabs(v - 1.15) < 0.001, "PCE basic")

    # No trucks → 1.0
    var v2 = passenger_car_equivalent(0.0, 2.5)
    _assert(fabs(v2 - 1.0) < 0.001, "PCE no trucks")
    print("  ✓ passenger_car_equivalent")


def test_intersection_capacity() raises:
    # s=1800, g/C=0.5 → 900
    var v = intersection_capacity(1800.0, 0.5)
    _assert(fabs(v - 900.0) < 0.01, "intersection cap basic")
    print("  ✓ intersection_capacity")


def test_queue_length_estimate() raises:
    # λ=500, μ=400, T=0.5 → (500-400)*0.5 = 50
    var v = queue_length_estimate(500.0, 400.0, 0.5)
    _assert(fabs(v - 50.0) < 0.01, "queue length oversaturated")

    # μ > λ → 0
    var v2 = queue_length_estimate(300.0, 400.0, 0.5)
    _assert(v2 == 0.0, "queue length undersaturated")
    print("  ✓ queue_length_estimate")


def test_vehicle_operating_cost() raises:
    # $3.50/gal * 100mi / 25mpg = $14
    var v = vehicle_operating_cost(3.50, 100.0, 25.0)
    _assert(fabs(v - 14.0) < 0.01, "VOC basic")

    var v2 = vehicle_operating_cost(3.50, 100.0, 0.0)
    _assert(v2 == 0.0, "VOC zero efficiency")
    print("  ✓ vehicle_operating_cost")


def test_crash_rate() raises:
    # 25 crashes / 10 MVMT = 2.5
    var v = crash_rate(25.0, 10.0)
    _assert(fabs(v - 2.5) < 0.01, "crash rate basic")

    var v2 = crash_rate(25.0, 0.0)
    _assert(v2 == 0.0, "crash rate zero VMT")
    print("  ✓ crash_rate")


# ── Nuclear tests ────────────────────────────────────────────────────────────


def test_radioactive_decay() raises:
    # N(t) = 1000 * exp(-0.1*5) = 1000 * exp(-0.5)
    var v = radioactive_decay(1000.0, 0.1, 5.0)
    var expected = 1000.0 * exp(-0.5)
    _assert(fabs(v - expected) < 0.01, "decay basic")

    # t=0 → N0
    var v2 = radioactive_decay(1000.0, 0.1, 0.0)
    _assert(fabs(v2 - 1000.0) < 0.01, "decay t=0")
    print("  ✓ radioactive_decay")


def test_half_life_from_lambda() raises:
    # t½ = ln(2)/0.1 ≈ 6.931
    var v = half_life_from_lambda(0.1)
    _assert(fabs(v - LN2 / 0.1) < 0.001, "half_life basic")

    var v2 = half_life_from_lambda(0.0)
    _assert(v2 == 0.0, "half_life zero lambda")
    print("  ✓ half_life_from_lambda")


def test_lambda_from_half_life() raises:
    # λ = ln(2)/10 ≈ 0.0693
    var v = lambda_from_half_life(10.0)
    _assert(fabs(v - LN2 / 10.0) < 0.0001, "lambda basic")

    var v2 = lambda_from_half_life(0.0)
    _assert(v2 == 0.0, "lambda zero half_life")
    print("  ✓ lambda_from_half_life")


def test_activity() raises:
    # A = 0.05 * 1e6 = 50000
    var v = activity(0.05, 1e6)
    _assert(fabs(v - 50000.0) < 0.01, "activity basic")
    print("  ✓ activity")


def test_decay_constant_from_activity() raises:
    # λ = 50000 / 1e6 = 0.05
    var v = decay_constant_from_activity(50000.0, 1e6)
    _assert(fabs(v - 0.05) < 0.0001, "decay const from activity")

    var v2 = decay_constant_from_activity(50000.0, 0.0)
    _assert(v2 == 0.0, "decay const zero N")
    print("  ✓ decay_constant_from_activity")


def test_binding_energy_per_nucleon() raises:
    # Fe-56: total BE ≈ 492 MeV, A=56 → ~8.786 MeV/nucleon
    var v = binding_energy_per_nucleon(492.0, 56.0)
    _assert(fabs(v - 492.0 / 56.0) < 0.001, "BE per nucleon Fe56")

    var v2 = binding_energy_per_nucleon(492.0, 0.0)
    _assert(v2 == 0.0, "BE per nucleon zero A")
    print("  ✓ binding_energy_per_nucleon")


def test_mass_defect() raises:
    # He-4: Z=2, N=2, mp=1.00728, mn=1.00866, M=4.00260
    # Δm = 2*1.00728 + 2*1.00866 - 4.00260 = 4.03188 - 4.00260 = 0.02928
    var v = mass_defect(2.0, 2.0, 4.00260, 1.00728, 1.00866)
    _assert(fabs(v - 0.02928) < 0.0001, "mass defect He4")
    print("  ✓ mass_defect")


def test_q_value() raises:
    # Q = (m_r - m_p) * 931.5
    # If m_r=236.05, m_p=235.86 → Q = 0.19*931.5 = 176.985
    var v = q_value(236.05, 235.86, 931.5)
    _assert(fabs(v - 0.19 * 931.5) < 0.1, "q value basic")
    print("  ✓ q_value")


def test_neutron_multiplication() raises:
    # k=1.05, gen=10 → 1.05^10 ≈ 1.6289
    var v = neutron_multiplication(1.05, 10.0)
    var expected = pow(1.05, 10.0)
    _assert(fabs(v - expected) < 0.01, "neutron mult supercritical")

    # k=1.0 → always 1
    var v2 = neutron_multiplication(1.0, 100.0)
    _assert(fabs(v2 - 1.0) < 0.001, "neutron mult critical")
    print("  ✓ neutron_multiplication")


def test_dose_rate_inverse_square() raises:
    # D = 100 * (2/4)² = 100 * 0.25 = 25
    var v = dose_rate_inverse_square(100.0, 2.0, 4.0)
    _assert(fabs(v - 25.0) < 0.01, "dose inv sq double dist")

    # Halve distance → 4x dose
    var v2 = dose_rate_inverse_square(100.0, 2.0, 1.0)
    _assert(fabs(v2 - 400.0) < 0.01, "dose inv sq half dist")

    var v3 = dose_rate_inverse_square(100.0, 2.0, 0.0)
    _assert(v3 == 0.0, "dose inv sq zero dist")
    print("  ✓ dose_rate_inverse_square")


def test_shielding_attenuation() raises:
    # I = 1000 * exp(-0.2*5) = 1000 * exp(-1) ≈ 367.88
    var v = shielding_attenuation(1000.0, 0.2, 5.0)
    var expected = 1000.0 * exp(-1.0)
    _assert(fabs(v - expected) < 0.1, "shielding basic")

    # Zero thickness → I0
    var v2 = shielding_attenuation(1000.0, 0.2, 0.0)
    _assert(fabs(v2 - 1000.0) < 0.01, "shielding zero thickness")
    print("  ✓ shielding_attenuation")


def test_critical_mass_estimate() raises:
    # Proportionality: 19000 * 1.235 * 2.5 = 58662.5
    var v = critical_mass_estimate(19000.0, 1.235, 2.5)
    _assert(fabs(v - 19000.0 * 1.235 * 2.5) < 0.1, "critical mass prop")
    print("  ✓ critical_mass_estimate")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 72 Tests: Forensics, Transportation, Nuclear ===")

    print("\n-- Forensics --")
    test_time_of_death_newton()
    test_algor_mortis_rate()
    test_blood_alcohol_widmark()
    test_alcohol_elimination_rate()
    test_rigor_mortis_stage()
    test_ballistic_drop()
    test_bloodstain_impact_angle()
    test_dna_match_probability()
    test_fingerprint_minutiae_score()
    test_glass_refractive_index_match()
    test_decomposition_add()
    test_toxicology_lethal_dose()

    print("\n-- Transportation --")
    test_level_of_service_density()
    test_highway_capacity()
    test_travel_time()
    test_delay_at_signal()
    test_headway()
    test_stopping_distance()
    test_fuel_consumption_rate()
    test_passenger_car_equivalent()
    test_intersection_capacity()
    test_queue_length_estimate()
    test_vehicle_operating_cost()
    test_crash_rate()

    print("\n-- Nuclear --")
    test_radioactive_decay()
    test_half_life_from_lambda()
    test_lambda_from_half_life()
    test_activity()
    test_decay_constant_from_activity()
    test_binding_energy_per_nucleon()
    test_mass_defect()
    test_q_value()
    test_neutron_multiplication()
    test_dose_rate_inverse_square()
    test_shielding_attenuation()
    test_critical_mass_estimate()

    print("\n✅ All Wave 72 tests passed!")
