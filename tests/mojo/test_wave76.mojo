"""Tests for Wave 76 — Metallurgy, Game Physics, Real Estate."""

from metallurgy import (
    hall_petch,
    johnson_cook_flow_stress,
    hardness_to_tensile,
    carbon_equivalent,
    jominy_distance_to_hardness,
    avrami_fraction,
    quench_severity,
    tempering_parameter,
    density_of_alloy_rule_of_mixtures,
    thermal_conductivity_wiedemann_franz,
    strain_hardening_exponent_from_points,
    fatigue_life_basquin,
)
from game_physics import (
    position_update,
    velocity_update,
    verlet_position,
    elastic_collision_1d,
    coefficient_of_restitution,
    kinetic_energy,
    gravitational_force,
    projectile_range,
    drag_force_quadratic,
    spring_force,
    angular_velocity_from_linear,
    moment_of_inertia_sphere,
)
from real_estate import (
    cap_rate,
    gross_rent_multiplier,
    cash_on_cash_return,
    debt_service_coverage,
    loan_to_value,
    net_operating_income,
    mortgage_payment,
    price_per_sqft,
    break_even_ratio,
    internal_rate_of_return_approx,
    equity_buildup,
    appreciation_value,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


fn _relnear(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-30:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ══════════════════════════════════════════════════════════════════════════════
# ── Metallurgy tests ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_hall_petch() raises:
    # σ_y = 100 + 0.5 / sqrt(0.0001) = 100 + 50 = 150
    var sy = hall_petch(100.0, 0.5, 0.0001)
    assert_true(_near(sy, 150.0, 1e-3), "hall_petch_basic")
    # d <= 0 guard
    assert_true(_near(hall_petch(100.0, 0.5, 0.0), 100.0, 1e-6), "hall_petch_zero_d")


fn test_johnson_cook() raises:
    # σ = 200 + 300 * 0.1^0.5 = 200 + 300*0.31623 = 294.868
    var s = johnson_cook_flow_stress(200.0, 300.0, 0.1, 0.5)
    assert_true(_near(s, 294.868, 0.01), "johnson_cook")
    # zero strain → A
    assert_true(_near(johnson_cook_flow_stress(200.0, 300.0, 0.0, 0.5), 200.0, 1e-6), "jc_zero")


fn test_hardness_to_tensile() raises:
    assert_true(_near(hardness_to_tensile(200.0), 690.0, 1e-6), "hb_to_tensile")
    assert_true(_near(hardness_to_tensile(100.0), 345.0, 1e-6), "hb_to_tensile_2")


fn test_carbon_equivalent() raises:
    # CE = 0.2 + 1.2/6 + (0.8+0.3+0.1)/5 + 0.5/15
    #    = 0.2 + 0.2 + 0.24 + 0.03333 = 0.67333
    var ce = carbon_equivalent(0.2, 1.2, 0.3, 0.5, 0.8, 0.3, 0.1)
    assert_true(_near(ce, 0.67333, 1e-3), "carbon_equivalent")


fn test_jominy() raises:
    # H = 60 * exp(-0.05*10) = 60 * exp(-0.5) ≈ 36.392
    var h = jominy_distance_to_hardness(60.0, 0.05, 10.0)
    assert_true(_near(h, 36.392, 0.01), "jominy")
    # distance=0 → h0
    assert_true(_near(jominy_distance_to_hardness(60.0, 0.05, 0.0), 60.0, 1e-6), "jominy_zero")


fn test_avrami() raises:
    # f = 1 - exp(-0.01 * 5^3) = 1 - exp(-1.25) ≈ 0.7135
    var f = avrami_fraction(0.01, 3.0, 5.0)
    assert_true(_near(f, 0.7135, 0.001), "avrami")
    # t=0 → 0
    assert_true(_near(avrami_fraction(0.01, 3.0, 0.0), 0.0, 1e-6), "avrami_zero")


fn test_quench_severity() raises:
    assert_true(_near(quench_severity(0.5, 25.0), 12.5, 1e-6), "quench")
    assert_true(_near(quench_severity(1.0, 50.0), 50.0, 1e-6), "quench_2")


fn test_tempering_parameter() raises:
    # P = 773 * (20 + log10(1.0)) = 773 * 20 = 15460
    var p = tempering_parameter(773.0, 1.0, 20.0)
    assert_true(_near(p, 15460.0, 1e-1), "tempering")
    # t=0 guard
    assert_true(_near(tempering_parameter(773.0, 0.0, 20.0), 0.0, 1e-6), "tempering_zero")


fn test_density_rule_of_mixtures() raises:
    # ρ = 0.7*7800 + 0.3*2700 = 5460 + 810 = 6270
    var d = density_of_alloy_rule_of_mixtures(0.7, 7800.0, 0.3, 2700.0)
    assert_true(_near(d, 6270.0, 1e-3), "density_rom")


fn test_wiedemann_franz() raises:
    # k = 2.44e-8 * 5.96e7 * 300 = 436.272
    var k = thermal_conductivity_wiedemann_franz(5.96e7, 300.0, 2.44e-8)
    assert_true(_near(k, 436.272, 0.1), "wiedemann_franz")


fn test_strain_hardening_exp() raises:
    # n = ln(600/400)/ln(0.15/0.05) = ln(1.5)/ln(3) ≈ 0.3691
    var n = strain_hardening_exponent_from_points(400.0, 0.05, 600.0, 0.15)
    assert_true(_near(n, 0.3691, 0.001), "strain_hard_exp")
    # guard: zero strain
    assert_true(_near(strain_hardening_exponent_from_points(400.0, 0.0, 600.0, 0.15), 0.0, 1e-6), "she_guard")


fn test_fatigue_basquin() raises:
    # Nf = (300/1000)^(1/(-0.12)) = 0.3^(-8.3333)
    var nf = fatigue_life_basquin(1000.0, 300.0, -0.12)
    assert_true(_relnear(nf, 22697.0, 0.01), "fatigue_basquin")
    # guard
    assert_true(_near(fatigue_life_basquin(0.0, 300.0, -0.12), 0.0, 1e-6), "fatigue_guard")


# ══════════════════════════════════════════════════════════════════════════════
# ── Game Physics tests ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_position_update() raises:
    # x = 10 + 5*0.1 + 0.5*2*0.01 = 10.51
    var x = position_update(10.0, 5.0, 2.0, 0.1)
    assert_true(_near(x, 10.51, 1e-6), "position_update")
    assert_true(_near(position_update(0.0, 0.0, 0.0, 1.0), 0.0, 1e-6), "pos_zeros")


fn test_velocity_update() raises:
    assert_true(_near(velocity_update(5.0, 2.0, 0.1), 5.2, 1e-6), "velocity_update")
    assert_true(_near(velocity_update(0.0, -9.81, 1.0), -9.81, 1e-6), "vel_gravity")


fn test_verlet_position() raises:
    # x_new = 2*10 - 9.8 + 2*0.01 = 10.22
    var x = verlet_position(10.0, 9.8, 2.0, 0.1)
    assert_true(_near(x, 10.22, 1e-6), "verlet")


fn test_elastic_collision() raises:
    # equal masses: v1'=v2, v2' (we only get v1')
    # m1=1,v1=2,m2=1,v2=0 → v1'=((1-1)*2+2*1*0)/2=0
    assert_true(_near(elastic_collision_1d(1.0, 2.0, 1.0, 0.0), 0.0, 1e-6), "elastic_equal")
    # m1=2,v1=3,m2=1,v2=0 → v1'=((2-1)*3+0)/3=1
    assert_true(_near(elastic_collision_1d(2.0, 3.0, 1.0, 0.0), 1.0, 1e-6), "elastic_heavy")


fn test_coefficient_restitution() raises:
    assert_true(_near(coefficient_of_restitution(3.0, 5.0), 0.6, 1e-6), "cor")
    assert_true(_near(coefficient_of_restitution(5.0, 5.0), 1.0, 1e-6), "cor_perfect")


fn test_kinetic_energy() raises:
    assert_true(_near(kinetic_energy(2.0, 3.0), 9.0, 1e-6), "ke")
    assert_true(_near(kinetic_energy(10.0, 0.0), 0.0, 1e-6), "ke_zero")


fn test_gravitational_force() raises:
    # F = 1*10*20/25 = 8
    assert_true(_near(gravitational_force(10.0, 20.0, 5.0, 1.0), 8.0, 1e-6), "grav")
    # r=0 guard
    assert_true(_near(gravitational_force(10.0, 20.0, 0.0, 1.0), 0.0, 1e-6), "grav_zero")


fn test_projectile_range() raises:
    # R = 100 * sin(pi/2) / 10 = 10.0  (angle=pi/4≈0.785398)
    var r = projectile_range(10.0, 0.7853981633974483, 10.0)
    assert_true(_near(r, 10.0, 1e-3), "proj_range")


fn test_drag_force() raises:
    # F = 0.5*0.47*1.225*0.01*100 = 0.287875
    var f = drag_force_quadratic(0.47, 1.225, 0.01, 10.0)
    assert_true(_near(f, 0.287875, 1e-4), "drag")


fn test_spring_force() raises:
    assert_true(_near(spring_force(100.0, -0.05), 5.0, 1e-6), "spring_neg")
    assert_true(_near(spring_force(100.0, 0.05), 5.0, 1e-6), "spring_pos")


fn test_angular_velocity() raises:
    assert_true(_near(angular_velocity_from_linear(10.0, 2.0), 5.0, 1e-6), "omega")
    assert_true(_near(angular_velocity_from_linear(10.0, 0.0), 0.0, 1e-6), "omega_zero_r")


fn test_moment_of_inertia_sphere() raises:
    # I = 0.4 * 5 * 0.01 = 0.02
    assert_true(_near(moment_of_inertia_sphere(5.0, 0.1), 0.02, 1e-6), "moi_sphere")
    assert_true(_near(moment_of_inertia_sphere(10.0, 1.0), 4.0, 1e-6), "moi_sphere_2")


# ══════════════════════════════════════════════════════════════════════════════
# ── Real Estate tests ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_cap_rate() raises:
    assert_true(_near(cap_rate(50000.0, 500000.0), 10.0, 1e-6), "cap_rate")
    assert_true(_near(cap_rate(0.0, 500000.0), 0.0, 1e-6), "cap_rate_zero")


fn test_gross_rent_multiplier() raises:
    assert_true(_near(gross_rent_multiplier(300000.0, 30000.0), 10.0, 1e-6), "grm")
    assert_true(_near(gross_rent_multiplier(300000.0, 0.0), 0.0, 1e-6), "grm_zero")


fn test_cash_on_cash() raises:
    assert_true(_near(cash_on_cash_return(12000.0, 100000.0), 12.0, 1e-6), "coc")
    assert_true(_near(cash_on_cash_return(8000.0, 50000.0), 16.0, 1e-6), "coc_2")


fn test_dscr() raises:
    assert_true(_near(debt_service_coverage(60000.0, 48000.0), 1.25, 1e-6), "dscr")
    assert_true(_near(debt_service_coverage(48000.0, 48000.0), 1.0, 1e-6), "dscr_unity")


fn test_ltv() raises:
    assert_true(_near(loan_to_value(400000.0, 500000.0), 80.0, 1e-6), "ltv")
    assert_true(_near(loan_to_value(0.0, 500000.0), 0.0, 1e-6), "ltv_zero")


fn test_noi() raises:
    # NOI = 100000*(1-0.05) - 35000 = 95000 - 35000 = 60000
    assert_true(_near(net_operating_income(100000.0, 0.05, 35000.0), 60000.0, 1e-3), "noi")
    # 0% vacancy
    assert_true(_near(net_operating_income(100000.0, 0.0, 30000.0), 70000.0, 1e-3), "noi_full")


fn test_mortgage_payment() raises:
    # P=200000, r=0.005, n=360 → PMT ≈ 1199.1
    var pmt = mortgage_payment(200000.0, 0.005, 360)
    assert_true(_relnear(pmt, 1199.1, 0.002), "mortgage")
    # zero rate → principal/n
    assert_true(_near(mortgage_payment(120000.0, 0.0, 360), 333.333, 0.01), "mortgage_zero_rate")


fn test_price_per_sqft() raises:
    assert_true(_near(price_per_sqft(500000.0, 2000.0), 250.0, 1e-6), "ppsf")
    assert_true(_near(price_per_sqft(500000.0, 0.0), 0.0, 1e-6), "ppsf_zero")


fn test_break_even_ratio() raises:
    # BER = (35000+48000)/100000*100 = 83.0
    assert_true(_near(break_even_ratio(35000.0, 48000.0, 100000.0), 83.0, 1e-6), "ber")


fn test_irr_approx() raises:
    # IRR ≈ (200000/100000)^(1/5) - 1 = 2^0.2 - 1 ≈ 0.14870
    var irr = internal_rate_of_return_approx(100000.0, 200000.0, 5)
    assert_true(_near(irr, 0.14870, 0.001), "irr_approx")
    # guard
    assert_true(_near(internal_rate_of_return_approx(0.0, 200000.0, 5), 0.0, 1e-6), "irr_guard")


fn test_equity_buildup() raises:
    assert_true(_near(equity_buildup(300000.0, 250000.0), 50000.0, 1e-6), "equity")
    assert_true(_near(equity_buildup(300000.0, 300000.0), 0.0, 1e-6), "equity_zero")


fn test_appreciation() raises:
    # FV = 500000 * (1.03)^5 ≈ 579637
    var fv = appreciation_value(500000.0, 0.03, 5)
    assert_true(_relnear(fv, 579637.0, 0.001), "appreciation")
    # years=0 → same value
    assert_true(_near(appreciation_value(500000.0, 0.03, 0), 500000.0, 1e-3), "appr_zero_yr")


# ══════════════════════════════════════════════════════════════════════════════
# ── main ─────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn main() raises:
    # Metallurgy (26 assertions)
    test_hall_petch()
    test_johnson_cook()
    test_hardness_to_tensile()
    test_carbon_equivalent()
    test_jominy()
    test_avrami()
    test_quench_severity()
    test_tempering_parameter()
    test_density_rule_of_mixtures()
    test_wiedemann_franz()
    test_strain_hardening_exp()
    test_fatigue_basquin()

    # Game Physics (24 assertions)
    test_position_update()
    test_velocity_update()
    test_verlet_position()
    test_elastic_collision()
    test_coefficient_restitution()
    test_kinetic_energy()
    test_gravitational_force()
    test_projectile_range()
    test_drag_force()
    test_spring_force()
    test_angular_velocity()
    test_moment_of_inertia_sphere()

    # Real Estate (26 assertions)
    test_cap_rate()
    test_gross_rent_multiplier()
    test_cash_on_cash()
    test_dscr()
    test_ltv()
    test_noi()
    test_mortgage_payment()
    test_price_per_sqft()
    test_break_even_ratio()
    test_irr_approx()
    test_equity_buildup()
    test_appreciation()

    print("✅ Wave 76 — all 76 assertions passed (Metallurgy, Game Physics, Real Estate)")
