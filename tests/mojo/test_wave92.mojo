"""Tests for Wave 92 — Laundry, Volcanology, Biomechanics."""

from laundry import (
    water_usage_liters,
    detergent_dose_ml,
    wash_temperature_energy,
    spin_g_force,
    moisture_retention,
    drying_time_estimate,
    energy_per_cycle,
    cost_per_wash,
    fabric_wear_cycles,
    stain_removal_efficiency,
    color_fastness_delta_e,
    water_hardness_compensation,
)
from volcanology import (
    vei_energy_estimate,
    lava_flow_velocity,
    eruption_column_height,
    tephra_fallout_thickness,
    magma_viscosity_estimate,
    effusion_rate,
    lahar_velocity,
    volcanic_gas_emission_rate,
    recurrence_interval,
    alert_level,
    pyroclastic_flow_runout,
    caldera_collapse_volume,
)
from biomechanics import (
    joint_torque,
    angular_velocity,
    angular_acceleration,
    moment_of_inertia_limb,
    ground_reaction_force_ratio,
    stride_length,
    cadence_from_velocity,
    metabolic_cost_walking,
    joint_power,
    elastic_energy_tendon,
    center_of_mass_two_segments,
    muscle_force_hill,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, pow


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < eps


fn approx_rel(a: Float64, b: Float64, rel: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < 1e-12
    return fabs((a - b) / b) < rel


# ── Laundry tests ────────────────────────────────────────────────────────────


fn test_laundry() raises:
    # water_usage_liters: 5 kg * 10 L/kg = 50 L
    assert_true(approx(water_usage_liters(5.0, 10.0), 50.0), "water_usage 5*10")
    assert_true(approx(water_usage_liters(3.0, 12.0), 36.0), "water_usage 3*12")

    # detergent_dose_ml: base=20, load=5, soil=1.5 => 150
    assert_true(approx(detergent_dose_ml(5.0, 1.5, 20.0), 150.0), "detergent normal")
    assert_true(approx(detergent_dose_ml(3.0, 2.0, 15.0), 90.0), "detergent heavy")

    # wash_temperature_energy: 50L * 40K * 4.186 / 3600 ≈ 2.3256
    var e = wash_temperature_energy(50.0, 40.0, 4.186)
    assert_true(approx(e, 50.0 * 40.0 * 4.186 / 3600.0), "wash energy")

    # spin_g_force: 1200 RPM, 0.25m radius
    var g = spin_g_force(1200.0, 0.25)
    assert_true(g > 400.0, "spin g-force > 400")
    assert_true(g < 410.0, "spin g-force < 410")

    # moisture_retention: (3.0 - 2.0) / 2.0 * 100 = 50%
    assert_true(approx(moisture_retention(3.0, 2.0), 50.0), "moisture retention")

    # drying_time_estimate: 60% / 2.0 = 30 min
    assert_true(approx(drying_time_estimate(60.0, 2.0), 30.0), "drying time")

    # energy_per_cycle: 2.0 kW * 45 min / 60 = 1.5 kWh
    assert_true(approx(energy_per_cycle(2.0, 45.0), 1.5), "energy per cycle")

    # cost_per_wash: 1.5*0.15 + 50*0.005 = 0.225 + 0.25 = 0.475
    assert_true(approx(cost_per_wash(1.5, 50.0, 0.15, 0.005), 0.475), "cost per wash")

    # fabric_wear_cycles: (100-20)/0.5 = 160
    assert_true(approx(fabric_wear_cycles(100.0, 0.5, 20.0), 160.0), "fabric wear")

    # stain_removal_efficiency: (100-15)/100*100 = 85%
    assert_true(approx(stain_removal_efficiency(100.0, 15.0), 85.0), "stain removal")

    # color_fastness_delta_e: sqrt(1+4+9) = sqrt(14)
    var de = color_fastness_delta_e(50.0, 20.0, 30.0, 49.0, 18.0, 27.0)
    assert_true(approx(de, sqrt(14.0)), "delta E")

    # water_hardness_compensation: 30 * (1 + 200*0.5/1000) = 30*1.1 = 33
    assert_true(approx(water_hardness_compensation(30.0, 200.0, 0.5), 33.0), "hardness comp")

    print("  ✓ laundry (14 assertions)")


# ── Volcanology tests ────────────────────────────────────────────────────────


fn test_volcanology() raises:
    # vei_energy_estimate: VEI 5 => 10^12
    assert_true(approx(vei_energy_estimate(5.0), 1e12), "VEI 5 energy")
    assert_true(approx(vei_energy_estimate(0.0), 1e7), "VEI 0 energy")

    # lava_flow_velocity: positive for positive slope
    var v = lava_flow_velocity(10.0, 1000.0, 2.0, 2600.0, 9.81)
    assert_true(v > 0.0, "lava flow positive")

    # eruption_column_height: 0.25 * (1e8)^0.25 = 0.25 * 100 = 25 km
    var h = eruption_column_height(1e8, 9.81)
    assert_true(approx(h, 0.25 * pow(1e8, 0.25)), "column height")

    # tephra_fallout_thickness: 1e6 / 1e7 = 0.1 m
    assert_true(approx(tephra_fallout_thickness(1e6, 1e7), 0.1), "tephra thickness")

    # magma_viscosity_estimate: sio2=60 => 10^2 = 100
    assert_true(approx(magma_viscosity_estimate(60.0), 100.0), "magma visc 60")
    assert_true(approx(magma_viscosity_estimate(40.0), 1.0), "magma visc 40")

    # effusion_rate: 1000 m³ / 100 s = 10 m³/s
    assert_true(approx(effusion_rate(1000.0, 100.0), 10.0), "effusion rate")

    # lahar_velocity: sqrt(9.81 * 3.0 * 0.1)
    var lv = lahar_velocity(0.1, 3.0)
    assert_true(approx(lv, sqrt(9.81 * 3.0 * 0.1)), "lahar velocity")

    # volcanic_gas_emission_rate: 0.05 * 1000 = 50
    assert_true(approx(volcanic_gas_emission_rate(0.05, 1000.0), 50.0), "gas emission")

    # recurrence_interval: 10000 / 20 = 500
    assert_true(approx(recurrence_interval(20.0, 10000.0), 500.0), "recurrence")

    # alert_level: max(2, 3, 1) = 3
    assert_true(approx(alert_level(2.0, 3.0, 1.0), 3.0), "alert level max")
    assert_true(approx(alert_level(4.0, 1.0, 2.0), 4.0), "alert level first")
    assert_true(approx(alert_level(1.0, 0.0, 3.0), 3.0), "alert level third")

    # pyroclastic_flow_runout: 30 * 0.5 * 10 = 150 km
    assert_true(approx(pyroclastic_flow_runout(30.0, 0.5), 150.0), "pyro runout")

    # caldera_collapse_volume: π * (10/2)² * 2 = π*25*2 ≈ 157.08
    var cv = caldera_collapse_volume(10.0, 2.0)
    assert_true(approx_rel(cv, 157.07963267948966), "caldera volume")

    print("  ✓ volcanology (18 assertions)")


# ── Biomechanics tests ───────────────────────────────────────────────────────


fn test_biomechanics() raises:
    # joint_torque: 100 N * 0.3 m = 30 N·m
    assert_true(approx(joint_torque(100.0, 0.3), 30.0), "joint torque")

    # angular_velocity: π rad / 2 s = π/2
    assert_true(approx(angular_velocity(3.14159265, 2.0), 1.57079632), "ang vel")

    # angular_acceleration: 10.0 / 2.0 = 5.0
    assert_true(approx(angular_acceleration(10.0, 2.0), 5.0), "ang accel")

    # moment_of_inertia_limb: 4.0 * 0.5² / 3 = 4*0.25/3 ≈ 0.3333
    assert_true(approx(moment_of_inertia_limb(4.0, 0.5), 4.0 * 0.25 / 3.0), "MOI limb")

    # ground_reaction_force_ratio: 1200 / 800 = 1.5
    assert_true(approx(ground_reaction_force_ratio(1200.0, 800.0), 1.5), "GRF ratio")

    # stride_length: v=1.5 m/s, cadence=120 steps/min => 1.5*60/(120/2) = 90/60 = 1.5
    assert_true(approx(stride_length(1.5, 120.0), 1.5), "stride length")

    # cadence_from_velocity: v=1.5, SL=1.5 => (1.5/1.5)*2*60 = 120
    assert_true(approx(cadence_from_velocity(1.5, 1.5), 120.0), "cadence from v")

    # metabolic_cost_walking: 70kg, 1.4 m/s => 2.5*70 + 3.0*70*1.96 = 175+411.6 = 586.6
    var mc = metabolic_cost_walking(70.0, 1.4)
    assert_true(approx(mc, 2.5 * 70.0 + 3.0 * 70.0 * 1.96), "metabolic cost")

    # joint_power: 50 N·m * 3.0 rad/s = 150 W
    assert_true(approx(joint_power(50.0, 3.0), 150.0), "joint power")

    # elastic_energy_tendon: 0.5 * 2000 * 0.01² = 0.5*2000*0.0001 = 0.1
    assert_true(approx(elastic_energy_tendon(2000.0, 0.01), 0.1), "tendon energy")

    # center_of_mass_two_segments: (5*0.2 + 3*0.6)/(5+3) = (1.0+1.8)/8 = 0.35
    assert_true(approx(center_of_mass_two_segments(5.0, 0.2, 3.0, 0.6), 0.35), "CoM 2seg")

    # muscle_force_hill: fmax=1000, v=0.1, vmax=1.0, a=0.25
    # F = 1000*(1.0-0.1)/(1.0+0.1/0.25) = 1000*0.9/(1.0+0.4) = 900/1.4 ≈ 642.857
    var mf = muscle_force_hill(1000.0, 0.1, 1.0, 0.25)
    assert_true(approx_rel(mf, 900.0 / 1.4), "hill muscle force")

    # Additional edge cases
    # Zero velocity in Hill model => F = Fmax*(vmax)/(vmax) = Fmax
    assert_true(approx(muscle_force_hill(500.0, 0.0, 1.0, 0.25), 500.0), "hill v=0")

    # stride_length with different cadence
    assert_true(approx(stride_length(2.0, 160.0), 2.0 * 60.0 / 80.0), "stride alt")

    # energy_per_cycle with zero time
    assert_true(approx(energy_per_cycle(2.0, 0.0), 0.0), "zero cycle energy")

    # moisture_retention high ratio
    assert_true(approx(moisture_retention(5.0, 2.0), 150.0), "high moisture")

    # water_usage zero load
    assert_true(approx(water_usage_liters(0.0, 10.0), 0.0), "zero load water")

    # vei 8 = 10^15
    assert_true(approx(vei_energy_estimate(8.0), 1e15), "VEI 8 energy")

    # GRF ratio < 1 for light impact
    assert_true(approx(ground_reaction_force_ratio(500.0, 800.0), 0.625), "GRF low")

    # joint_torque zero force
    assert_true(approx(joint_torque(0.0, 0.5), 0.0), "zero force torque")

    # stain removal 100%
    assert_true(approx(stain_removal_efficiency(50.0, 0.0), 100.0), "perfect stain removal")

    # recurrence_interval single event
    assert_true(approx(recurrence_interval(1.0, 500.0), 500.0), "single event recurrence")

    print("  ✓ biomechanics + extras (23 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 92 tests — Laundry, Volcanology, Biomechanics")
    test_laundry()
    test_volcanology()
    test_biomechanics()
    print("All Wave 92 tests passed ✓  (55 assertions)")
