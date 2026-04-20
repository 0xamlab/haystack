"""Tests for Wave 85 — Crystallography, Pension, Plumbing."""

from crystallography import (
    bragg_angle,
    d_spacing_cubic,
    lattice_parameter_from_d,
    unit_cell_volume_cubic,
    unit_cell_volume_tetragonal,
    unit_cell_volume_orthorhombic,
    atomic_packing_factor_fcc,
    atomic_packing_factor_bcc,
    scherrer_crystallite_size,
    interplanar_angle_cubic,
    density_from_crystal,
    structure_factor_magnitude,
)
from pension import (
    replacement_ratio,
    defined_benefit_pension,
    defined_contribution_value,
    annuity_factor,
    pension_lump_sum_from_annuity,
    funding_ratio,
    contribution_rate_required,
    inflation_adjusted_pension,
    pension_gap,
    social_security_bend_points,
    years_to_full_vesting,
    withdrawal_rate,
)
from plumbing import (
    pipe_flow_velocity,
    reynolds_number,
    friction_factor_laminar,
    head_loss_darcy,
    head_loss_minor,
    total_dynamic_head,
    pump_power,
    water_demand_fixture_units,
    pipe_sizing_velocity_method,
    thermal_expansion_pipe,
    water_hammer_pressure,
    drainage_slope_minimum,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, asin, cos


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


fn rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Crystallography Tests ────────────────────────────────────────────────────


fn test_crystallography() raises:
    comptime PI: Float64 = 3.141592653589793
    comptime HALF_PI: Float64 = 1.5707963267948966

    # bragg_angle: n=1, λ=1.54Å, d=2.0Å → sin(θ)=0.385 → θ≈0.3948 rad
    var ba = bragg_angle(1.0, 1.54, 2.0)
    assert_true(rel_eq(ba, asin(1.54 / 4.0)), "bragg angle")
    assert_true(approx_eq(bragg_angle(1.0, 1.54, 0.0), 0.0), "bragg zero d")
    # invalid argument (>1)
    assert_true(approx_eq(bragg_angle(3.0, 1.54, 1.0), 0.0), "bragg invalid")

    # d_spacing_cubic: a=5.43, (1,1,1) → 5.43/sqrt(3) ≈ 3.1350
    var ds = d_spacing_cubic(5.43, 1.0, 1.0, 1.0)
    assert_true(rel_eq(ds, 5.43 / sqrt(3.0)), "d_spacing (111)")
    # (1,0,0) → 5.43/1 = 5.43
    assert_true(approx_eq(d_spacing_cubic(5.43, 1.0, 0.0, 0.0), 5.43), "d_spacing (100)")
    assert_true(approx_eq(d_spacing_cubic(5.43, 0.0, 0.0, 0.0), 0.0), "d_spacing (000)")

    # lattice_parameter_from_d: d=3.135, (1,1,1) → a=3.135*sqrt(3) ≈ 5.43
    var lp = lattice_parameter_from_d(3.135, 1.0, 1.0, 1.0)
    assert_true(rel_eq(lp, 3.135 * sqrt(3.0)), "lattice param")

    # unit_cell_volume_cubic: a=5.0 → 125.0
    assert_true(approx_eq(unit_cell_volume_cubic(5.0), 125.0), "ucv cubic")
    assert_true(approx_eq(unit_cell_volume_cubic(0.0), 0.0), "ucv cubic zero")

    # unit_cell_volume_tetragonal: a=3.0, c=5.0 → 9*5=45
    assert_true(approx_eq(unit_cell_volume_tetragonal(3.0, 5.0), 45.0), "ucv tetrag")

    # unit_cell_volume_orthorhombic: a=2, b=3, c=4 → 24
    assert_true(approx_eq(unit_cell_volume_orthorhombic(2.0, 3.0, 4.0), 24.0), "ucv ortho")

    # atomic_packing_factor_fcc ≈ 0.7405
    var apf_fcc = atomic_packing_factor_fcc()
    assert_true(rel_eq(apf_fcc, PI * sqrt(2.0) / 6.0), "apf fcc")
    assert_true(apf_fcc > 0.74 and apf_fcc < 0.75, "apf fcc range")

    # atomic_packing_factor_bcc ≈ 0.6802
    var apf_bcc = atomic_packing_factor_bcc()
    assert_true(rel_eq(apf_bcc, PI * sqrt(3.0) / 8.0), "apf bcc")
    assert_true(apf_bcc > 0.68 and apf_bcc < 0.69, "apf bcc range")

    # scherrer_crystallite_size: K=0.9, λ=1.54, β=0.01 rad, θ=0.3 rad
    var sc = scherrer_crystallite_size(0.9, 1.54, 0.01, 0.3)
    assert_true(rel_eq(sc, 0.9 * 1.54 / (0.01 * cos(0.3))), "scherrer")
    assert_true(approx_eq(scherrer_crystallite_size(0.9, 1.54, 0.0, 0.3), 0.0), "scherrer zero β")

    # interplanar_angle_cubic: (1,0,0) vs (0,1,0) → 90° = π/2
    var ia = interplanar_angle_cubic(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    assert_true(rel_eq(ia, HALF_PI), "interplanar 90°")
    # (1,0,0) vs (1,0,0) → 0°
    var ia2 = interplanar_angle_cubic(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    assert_true(approx_eq(ia2, 0.0), "interplanar 0°")

    # density_from_crystal: Z=4, M=58.44, Na=6.022e23, V=1.79e-22
    var rho = density_from_crystal(4.0, 58.44, 6.022e23, 1.79e-22)
    assert_true(rel_eq(rho, 4.0 * 58.44 / (6.022e23 * 1.79e-22)), "crystal density")
    assert_true(approx_eq(density_from_crystal(4.0, 58.44, 6.022e23, 0.0), 0.0), "crystal density zero V")

    # structure_factor_magnitude: (3,4) → 5
    assert_true(approx_eq(structure_factor_magnitude(3.0, 4.0), 5.0), "struct factor 3,4")
    assert_true(approx_eq(structure_factor_magnitude(0.0, 0.0), 0.0), "struct factor 0,0")
    assert_true(approx_eq(structure_factor_magnitude(5.0, 0.0), 5.0), "struct factor 5,0")

    print("  ✓ crystallography (28 assertions)")


# ── Pension Tests ────────────────────────────────────────────────────────────


fn test_pension() raises:
    # replacement_ratio: 30000/60000*100 = 50%
    assert_true(approx_eq(replacement_ratio(30000.0, 60000.0), 50.0), "rr 50%")
    assert_true(approx_eq(replacement_ratio(100.0, 0.0), 0.0), "rr zero salary")

    # defined_benefit_pension: 30*60000*(1/60) = 30000
    assert_true(approx_eq(defined_benefit_pension(30.0, 60000.0, 1.0 / 60.0), 30000.0), "db pension")

    # defined_contribution_value: C=5000, r=0.07, n=30
    # FV = 5000*((1.07^30-1)/0.07) ≈ 472304
    var dcv = defined_contribution_value(5000.0, 0.07, 30)
    assert_true(dcv > 470000.0 and dcv < 475000.0, "dc value range")
    # zero rate: 5000*30 = 150000
    assert_true(approx_eq(defined_contribution_value(5000.0, 0.0, 30), 150000.0), "dc zero rate")

    # annuity_factor: r=0.05, n=20 → (1-1.05^(-20))/0.05 ≈ 12.4622
    var af = annuity_factor(0.05, 20)
    assert_true(af > 12.4 and af < 12.6, "af range")
    # zero rate: just years
    assert_true(approx_eq(annuity_factor(0.0, 20), 20.0), "af zero rate")

    # pension_lump_sum_from_annuity: 30000 * 12.46 = 373800
    assert_true(approx_eq(pension_lump_sum_from_annuity(30000.0, 12.46), 373800.0), "lump sum")

    # funding_ratio: 800000/1000000 * 100 = 80%
    assert_true(approx_eq(funding_ratio(800000.0, 1000000.0), 80.0), "funding 80%")
    assert_true(approx_eq(funding_ratio(1000000.0, 1000000.0), 100.0), "funding 100%")
    assert_true(approx_eq(funding_ratio(100.0, 0.0), 0.0), "funding zero liab")

    # contribution_rate_required: target=500000, n=30, salary=60000, r=0.07
    var cr = contribution_rate_required(500000.0, 30, 60000.0, 0.07)
    assert_true(cr > 8.0 and cr < 10.0, "cr range")
    assert_true(approx_eq(contribution_rate_required(100.0, 10, 0.0, 0.07), 0.0), "cr zero salary")

    # inflation_adjusted_pension: 50000/(1.03)^20 ≈ 27684
    var iap = inflation_adjusted_pension(50000.0, 0.03, 20)
    assert_true(iap > 27000.0 and iap < 28000.0, "infl adj pension")

    # pension_gap: 50000-30000 = 20000
    assert_true(approx_eq(pension_gap(50000.0, 30000.0), 20000.0), "pension gap")
    assert_true(approx_eq(pension_gap(30000.0, 30000.0), 0.0), "pension gap zero")

    # social_security_bend_points: aime=3000, bp1=1024, bp2=6172
    # PIA = 0.9*1024 + 0.32*(3000-1024) + 0.15*0 = 921.6 + 632.32 = 1553.92
    var pia = social_security_bend_points(3000.0, 1024.0, 6172.0)
    assert_true(approx_eq(pia, 0.9 * 1024.0 + 0.32 * (3000.0 - 1024.0)), "ss bend pts")
    # aime below bp1
    assert_true(approx_eq(social_security_bend_points(500.0, 1024.0, 6172.0), 0.9 * 500.0), "ss low aime")

    # years_to_full_vesting: 3 years / 5 schedule = 60%
    assert_true(approx_eq(years_to_full_vesting(3.0, 5.0), 60.0), "vesting 60%")
    assert_true(approx_eq(years_to_full_vesting(7.0, 5.0), 100.0), "vesting capped")
    assert_true(approx_eq(years_to_full_vesting(5.0, 0.0), 100.0), "vesting zero sched")

    # withdrawal_rate: 40000/1000000*100 = 4%
    assert_true(approx_eq(withdrawal_rate(40000.0, 1000000.0), 4.0), "wr 4%")
    assert_true(approx_eq(withdrawal_rate(100.0, 0.0), 0.0), "wr zero portfolio")

    print("  ✓ pension (26 assertions)")


# ── Plumbing Tests ───────────────────────────────────────────────────────────


fn test_plumbing() raises:
    comptime PI: Float64 = 3.141592653589793

    # pipe_flow_velocity: Q=0.01 m³/s, d=0.1 m → v = 4*0.01/(π*0.01) ≈ 1.2732
    var pv = pipe_flow_velocity(0.01, 0.1)
    assert_true(rel_eq(pv, 4.0 * 0.01 / (PI * 0.01)), "pipe velocity")
    assert_true(approx_eq(pipe_flow_velocity(0.01, 0.0), 0.0), "pipe vel zero d")

    # reynolds_number: v=1.27, d=0.1, ν=1e-6 → Re=127000
    var re = reynolds_number(1.27, 0.1, 1e-6)
    assert_true(rel_eq(re, 127000.0), "reynolds")
    assert_true(approx_eq(reynolds_number(1.0, 0.1, 0.0), 0.0), "re zero visc")

    # friction_factor_laminar: Re=2000 → f=64/2000=0.032
    assert_true(approx_eq(friction_factor_laminar(2000.0), 0.032), "f laminar")
    assert_true(approx_eq(friction_factor_laminar(0.0), 0.0), "f zero re")

    # head_loss_darcy: f=0.032, L=100, d=0.1, v=1.0, g=9.81
    # hf = 0.032*100/0.1 * 1/(2*9.81) = 32 * 0.05097 ≈ 1.631
    var hd = head_loss_darcy(0.032, 100.0, 0.1, 1.0, 9.81)
    assert_true(rel_eq(hd, 0.032 * 100.0 / 0.1 * 1.0 / (2.0 * 9.81)), "darcy hl")
    assert_true(approx_eq(head_loss_darcy(0.032, 100.0, 0.0, 1.0, 9.81), 0.0), "darcy zero d")

    # head_loss_minor: K=5, v=2.0, g=9.81 → 5*4/(2*9.81) ≈ 1.019
    var hm = head_loss_minor(5.0, 2.0, 9.81)
    assert_true(rel_eq(hm, 5.0 * 4.0 / (2.0 * 9.81)), "minor hl")
    assert_true(approx_eq(head_loss_minor(5.0, 2.0, 0.0), 0.0), "minor zero g")

    # total_dynamic_head: 10+5+2 = 17
    assert_true(approx_eq(total_dynamic_head(10.0, 5.0, 2.0), 17.0), "tdh")

    # pump_power: ρ=1000, g=9.81, Q=0.01, H=20, η=0.75
    # P = 1000*9.81*0.01*20/0.75 = 2616
    var pp = pump_power(0.01, 20.0, 1000.0, 9.81, 0.75)
    assert_true(rel_eq(pp, 1000.0 * 9.81 * 0.01 * 20.0 / 0.75), "pump power")
    assert_true(approx_eq(pump_power(0.01, 20.0, 1000.0, 9.81, 0.0), 0.0), "pump zero eff")

    # water_demand_fixture_units: 20 fixtures * 3 FU = 60
    assert_true(approx_eq(water_demand_fixture_units(20.0, 3.0), 60.0), "fixture units")

    # pipe_sizing_velocity_method: Q=0.01, v_max=2.0
    # d = sqrt(4*0.01/(π*2.0)) = sqrt(0.006366) ≈ 0.07979
    var ps = pipe_sizing_velocity_method(0.01, 2.0)
    assert_true(rel_eq(ps, sqrt(4.0 * 0.01 / (PI * 2.0))), "pipe sizing")
    assert_true(approx_eq(pipe_sizing_velocity_method(0.01, 0.0), 0.0), "pipe size zero v")

    # thermal_expansion_pipe: α=1.2e-5, L=100, ΔT=50 → 0.06
    assert_true(approx_eq(thermal_expansion_pipe(1.2e-5, 100.0, 50.0), 0.06), "thermal exp")

    # water_hammer_pressure: ρ=1000, v=2.0, c=1400 → 2800000 Pa
    assert_true(approx_eq(water_hammer_pressure(1000.0, 2.0, 1400.0), 2800000.0), "water hammer")

    # drainage_slope_minimum: d>=3 → 0.25, d<3 → 0.125
    assert_true(approx_eq(drainage_slope_minimum(4.0), 0.25), "drain slope 4in")
    assert_true(approx_eq(drainage_slope_minimum(3.0), 0.25), "drain slope 3in")
    assert_true(approx_eq(drainage_slope_minimum(2.0), 0.125), "drain slope 2in")

    print("  ✓ plumbing (24 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 85 tests: Crystallography, Pension, Plumbing")
    test_crystallography()
    test_pension()
    test_plumbing()
    print("All Wave 85 tests passed! (78 assertions)")
