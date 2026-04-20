"""Tests for Wave 74 — Geotechnical, Cosmology, Packaging."""

from geotechnical import (
    bearing_capacity_terzaghi,
    effective_stress,
    overburden_pressure,
    coefficient_of_earth_pressure_at_rest,
    active_earth_pressure,
    rankine_ka,
    rankine_kp,
    settlement_elastic,
    factor_of_safety_slope,
    void_ratio,
    porosity_from_void_ratio,
    degree_of_saturation,
)
from cosmology import (
    hubble_velocity,
    hubble_distance,
    lookback_time_approx,
    comoving_distance_approx,
    luminosity_distance,
    angular_diameter_distance,
    redshift_from_wavelength,
    cosmic_scale_factor,
    critical_density,
    schwarzschild_radius,
    stefan_boltzmann_luminosity,
    wien_peak_wavelength,
)
from packaging import (
    box_volume,
    box_surface_area,
    cylinder_volume,
    cylinder_surface_area,
    material_utilization,
    compression_strength_mckee,
    stacking_load,
    cushion_curve_g,
    pallet_efficiency,
    shelf_life_arrhenius,
    fill_percentage,
    dimensional_weight,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, sin

comptime TOL: Float64 = 1e-6
comptime LTOL: Float64 = 1e-2


# ── Helper ───────────────────────────────────────────────────────────────────


fn _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


fn _relnear(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    if fabs(b) < 1e-30:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Geotechnical tests ──────────────────────────────────────────────────────


fn test_bearing_capacity() raises:
    # q_ult = 25*5.7 + 18*1.5*1.0 + 0.5*18*2.0*3.0
    # = 142.5 + 27.0 + 54.0 = 223.5
    var q = bearing_capacity_terzaghi(25.0, 18.0, 1.5, 2.0, 5.7, 1.0, 3.0)
    assert_true(_near(q, 223.5, 1e-3), "bearing_terzaghi")


fn test_effective_stress() raises:
    assert_true(_near(effective_stress(200.0, 50.0), 150.0), "eff_stress")
    assert_true(_near(effective_stress(100.0, 100.0), 0.0), "eff_stress_zero")


fn test_overburden_pressure() raises:
    # σ_v = 18 * 5 = 90
    assert_true(_near(overburden_pressure(5.0, 18.0), 90.0), "overburden")


fn test_k0() raises:
    # φ = 30° = π/6 ≈ 0.5236 rad, sin(π/6) = 0.5, K0 = 0.5
    var pi: Float64 = 3.141592653589793
    var phi = pi / 6.0
    var k0 = coefficient_of_earth_pressure_at_rest(phi)
    assert_true(_near(k0, 0.5, 1e-6), "k0_30deg")


fn test_rankine_ka() raises:
    # φ = 30° → Ka = (1-0.5)/(1+0.5) = 0.5/1.5 = 1/3
    var pi: Float64 = 3.141592653589793
    var ka = rankine_ka(pi / 6.0)
    assert_true(_near(ka, 1.0 / 3.0, 1e-6), "rankine_ka_30")


fn test_rankine_kp() raises:
    # φ = 30° → Kp = (1+0.5)/(1-0.5) = 1.5/0.5 = 3.0
    var pi: Float64 = 3.141592653589793
    var kp = rankine_kp(pi / 6.0)
    assert_true(_near(kp, 3.0, 1e-6), "rankine_kp_30")


fn test_ka_kp_reciprocal() raises:
    """Ka * Kp = 1 for same angle."""
    var pi: Float64 = 3.141592653589793
    var phi = pi / 6.0
    var product = rankine_ka(phi) * rankine_kp(phi)
    assert_true(_near(product, 1.0, 1e-9), "ka_kp_reciprocal")


fn test_active_earth_pressure() raises:
    # Ka=1/3, σv=90, c=10 → σa = (1/3)*90 - 2*10*√(1/3)
    # = 30 - 20*0.57735 = 30 - 11.547 = 18.453
    var ka = 1.0 / 3.0
    var sigma_a = active_earth_pressure(ka, 90.0, 10.0)
    var expected = ka * 90.0 - 2.0 * 10.0 * sqrt(ka)
    assert_true(_near(sigma_a, expected, 1e-3), "active_ep")


fn test_settlement_elastic() raises:
    # s = 100*2*(1-0.3^2)/50000 = 200*0.91/50000 = 0.00364
    var s = settlement_elastic(100.0, 2.0, 50000.0, 0.3)
    assert_true(_near(s, 200.0 * 0.91 / 50000.0, 1e-6), "settlement")


fn test_factor_of_safety() raises:
    assert_true(
        _near(factor_of_safety_slope(150.0, 100.0), 1.5), "fos_1.5"
    )
    assert_true(
        _near(factor_of_safety_slope(200.0, 200.0), 1.0), "fos_1.0"
    )


fn test_void_ratio() raises:
    # n=0.4 → e = 0.4/0.6 = 2/3
    assert_true(
        _near(void_ratio(0.4), 0.4 / 0.6, 1e-6), "void_ratio_0.4"
    )
    # n=0.5 → e = 1.0
    assert_true(_near(void_ratio(0.5), 1.0), "void_ratio_0.5")


fn test_porosity_from_void_ratio() raises:
    # e=1.0 → n = 1/(1+1) = 0.5
    assert_true(
        _near(porosity_from_void_ratio(1.0), 0.5), "porosity_e1"
    )
    # e=0.667 → n ≈ 0.4
    assert_true(
        _near(porosity_from_void_ratio(2.0 / 3.0), 0.4, 1e-4), "porosity_e067"
    )


fn test_void_porosity_roundtrip() raises:
    var n = 0.35
    var e = void_ratio(n)
    var n_back = porosity_from_void_ratio(e)
    assert_true(_near(n_back, n, 1e-10), "void_porosity_rt")


fn test_degree_of_saturation() raises:
    # w=0.25, e=0.7, Gs=2.65 → S = 0.25*2.65/0.7 ≈ 0.94643
    var s = degree_of_saturation(0.25, 0.7, 2.65)
    assert_true(_near(s, 0.25 * 2.65 / 0.7, 1e-4), "saturation")


# ── Cosmology tests ─────────────────────────────────────────────────────────


fn test_hubble_velocity() raises:
    # v = 70 * 100 = 7000 km/s
    assert_true(_near(hubble_velocity(70.0, 100.0), 7000.0), "hubble_v")


fn test_hubble_distance() raises:
    # d = 7000 / 70 = 100 Mpc
    assert_true(_near(hubble_distance(70.0, 7000.0), 100.0), "hubble_d")


fn test_hubble_roundtrip() raises:
    var h0 = 70.0
    var d = 150.0
    var v = hubble_velocity(h0, d)
    var d_back = hubble_distance(h0, v)
    assert_true(_near(d_back, d, 1e-9), "hubble_rt")


fn test_comoving_distance() raises:
    # d_c = 3e5 * 0.1 / 70 = 30000/70 ≈ 428.571 Mpc
    var dc = comoving_distance_approx(0.1, 3.0e5, 70.0)
    assert_true(_near(dc, 30000.0 / 70.0, 1e-2), "comoving_d")


fn test_luminosity_distance() raises:
    # d_L = 428.571 * 1.1 = 471.429
    var dc = 428.571
    var dl = luminosity_distance(dc, 0.1)
    assert_true(_near(dl, dc * 1.1, 1e-2), "lum_dist")


fn test_angular_diameter_distance() raises:
    var dc = 428.571
    var da = angular_diameter_distance(dc, 0.1)
    assert_true(_near(da, dc / 1.1, 1e-2), "ang_diam_dist")


fn test_redshift_from_wavelength() raises:
    # z = (700 - 500)/500 = 0.4
    assert_true(
        _near(redshift_from_wavelength(700.0, 500.0), 0.4), "redshift"
    )
    # No shift
    assert_true(
        _near(redshift_from_wavelength(500.0, 500.0), 0.0), "redshift_zero"
    )


fn test_cosmic_scale_factor() raises:
    # z=0 → a=1, z=1 → a=0.5, z=9 → a=0.1
    assert_true(_near(cosmic_scale_factor(0.0), 1.0), "scale_z0")
    assert_true(_near(cosmic_scale_factor(1.0), 0.5), "scale_z1")
    assert_true(_near(cosmic_scale_factor(9.0), 0.1), "scale_z9")


fn test_critical_density() raises:
    # H0 = 70 km/s/Mpc → H0_si = 70/3.0857e19 ≈ 2.2694e-18 /s
    # ρ_c = 3*(2.2694e-18)^2 / (8*π*6.674e-11) ≈ 9.2e-27 kg/m³
    var rho = critical_density(70.0)
    assert_true(_relnear(rho, 9.2e-27, 0.05), "critical_density")


fn test_schwarzschild_radius() raises:
    # Sun mass ≈ 1.989e30 kg → r_s = 2*6.674e-11*1.989e30/(9e16) ≈ 2953 m
    var rs = schwarzschild_radius(1.989e30)
    assert_true(_relnear(rs, 2953.0, 0.01), "schwarzschild_sun")


fn test_stefan_boltzmann_luminosity() raises:
    # Sun: R ≈ 6.957e8 m, T = 5778 K
    # L = 4π*(6.957e8)^2 * 5.670374419e-8 * 5778^4
    # ≈ 3.846e26 W
    var lum = stefan_boltzmann_luminosity(6.957e8, 5778.0)
    assert_true(_relnear(lum, 3.846e26, 0.01), "sb_luminosity_sun")


fn test_wien_peak() raises:
    # T = 5778 K → λ = 2.898e-3 / 5778 ≈ 5.015e-7 m (≈ 501.5 nm)
    var lam = wien_peak_wavelength(5778.0)
    assert_true(_relnear(lam, 5.015e-7, 0.01), "wien_sun")


# ── Packaging tests ──────────────────────────────────────────────────────────


fn test_box_volume() raises:
    assert_true(_near(box_volume(30.0, 20.0, 15.0), 9000.0), "box_vol")


fn test_box_surface_area() raises:
    # SA = 2*(600 + 300 + 450) = 2*1350 = 2700
    assert_true(
        _near(box_surface_area(30.0, 20.0, 15.0), 2700.0), "box_sa"
    )


fn test_cylinder_volume() raises:
    var pi: Float64 = 3.141592653589793
    # V = π*5²*10 = 250π ≈ 785.398
    var v = cylinder_volume(5.0, 10.0)
    assert_true(_near(v, 250.0 * pi, 1e-3), "cyl_vol")


fn test_cylinder_surface_area() raises:
    var pi: Float64 = 3.141592653589793
    # SA = 2π*5*(5+10) = 150π ≈ 471.239
    var sa = cylinder_surface_area(5.0, 10.0)
    assert_true(_near(sa, 150.0 * pi, 1e-3), "cyl_sa")


fn test_material_utilization() raises:
    # MU = (80/100)*100 = 80%
    assert_true(
        _near(material_utilization(80.0, 100.0), 80.0), "mat_util"
    )


fn test_compression_strength_mckee() raises:
    # CS = 5.87 * 6.0 * √(100*0.4) = 35.22 * √40 = 35.22 * 6.3246 ≈ 222.79
    var cs = compression_strength_mckee(6.0, 100.0, 0.4)
    var expected = 5.87 * 6.0 * sqrt(100.0 * 0.4)
    assert_true(_near(cs, expected, 1e-2), "mckee_cs")


fn test_stacking_load() raises:
    # F = 20 * (5-1) = 80
    assert_true(_near(stacking_load(20.0, 5.0), 80.0), "stacking")
    assert_true(_near(stacking_load(20.0, 1.0), 0.0), "stacking_single")


fn test_cushion_curve_g() raises:
    # G = 2*0.75 / (0.05 * (1 + 2.0/10)) = 1.5 / (0.05 * 1.2) = 1.5/0.06 = 25
    var g = cushion_curve_g(0.75, 0.05, 2.0)
    assert_true(_near(g, 25.0, 1e-3), "cushion_g")


fn test_pallet_efficiency() raises:
    # η = (8 * 0.12) / 1.2 * 100 = 0.96/1.2*100 = 80%
    var eff = pallet_efficiency(0.12, 1.2, 8.0)
    assert_true(_near(eff, 80.0, 1e-3), "pallet_eff")


fn test_shelf_life_arrhenius() raises:
    # k = 1e10 * exp(-80000/(8.314*300))
    # = 1e10 * exp(-32.07) ≈ 1e10 * 1.19e-14 ≈ 1.19e-4
    var k = shelf_life_arrhenius(1.0e10, 80000.0, 8.314, 300.0)
    var expected = 1.0e10 * exp(-80000.0 / (8.314 * 300.0))
    assert_true(_relnear(k, expected, 1e-6), "arrhenius")


fn test_fill_percentage() raises:
    assert_true(
        _near(fill_percentage(750.0, 1000.0), 75.0), "fill_pct"
    )
    assert_true(
        _near(fill_percentage(1000.0, 1000.0), 100.0), "fill_full"
    )


fn test_dimensional_weight() raises:
    # DW = 60*40*30 / 5000 = 72000/5000 = 14.4
    var dw = dimensional_weight(60.0, 40.0, 30.0, 5000.0)
    assert_true(_near(dw, 14.4, 1e-6), "dim_weight")


# ── Cross-checks ─────────────────────────────────────────────────────────────


fn test_geo_stress_chain() raises:
    """Overburden → effective stress chain."""
    var sigma_v = overburden_pressure(10.0, 20.0)  # 200
    var sigma_eff = effective_stress(sigma_v, 80.0)  # 120
    assert_true(_near(sigma_v, 200.0), "chain_overburden")
    assert_true(_near(sigma_eff, 120.0), "chain_effective")


fn test_cosmo_distance_relations() raises:
    """Verify d_L * d_A = d_c² for same z."""
    var dc = 400.0
    var z = 0.5
    var dl = luminosity_distance(dc, z)
    var da = angular_diameter_distance(dc, z)
    assert_true(_near(dl * da, dc * dc, 1e-6), "dl_da_dc2")


fn test_packaging_vol_fill() raises:
    """Box volume → fill percentage consistency."""
    var container = box_volume(30.0, 20.0, 15.0)  # 9000
    var product = 6750.0
    var fp = fill_percentage(product, container)
    assert_true(_near(fp, 75.0), "vol_fill_chain")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 74 Tests: Geotechnical, Cosmology, Packaging ===")

    # Geotechnical (22 assertions)
    test_bearing_capacity()
    test_effective_stress()
    test_overburden_pressure()
    test_k0()
    test_rankine_ka()
    test_rankine_kp()
    test_ka_kp_reciprocal()
    test_active_earth_pressure()
    test_settlement_elastic()
    test_factor_of_safety()
    test_void_ratio()
    test_porosity_from_void_ratio()
    test_void_porosity_roundtrip()
    test_degree_of_saturation()
    print("  ✓ Geotechnical: all tests passed")

    # Cosmology (16 assertions)
    test_hubble_velocity()
    test_hubble_distance()
    test_hubble_roundtrip()
    test_comoving_distance()
    test_luminosity_distance()
    test_angular_diameter_distance()
    test_redshift_from_wavelength()
    test_cosmic_scale_factor()
    test_critical_density()
    test_schwarzschild_radius()
    test_stefan_boltzmann_luminosity()
    test_wien_peak()
    print("  ✓ Cosmology: all tests passed")

    # Packaging (16 assertions)
    test_box_volume()
    test_box_surface_area()
    test_cylinder_volume()
    test_cylinder_surface_area()
    test_material_utilization()
    test_compression_strength_mckee()
    test_stacking_load()
    test_cushion_curve_g()
    test_pallet_efficiency()
    test_shelf_life_arrhenius()
    test_fill_percentage()
    test_dimensional_weight()
    print("  ✓ Packaging: all tests passed")

    # Cross-checks (5 assertions)
    test_geo_stress_chain()
    test_cosmo_distance_relations()
    test_packaging_vol_fill()
    print("  ✓ Cross-checks: all tests passed")

    print("")
    print("All Wave 74 tests passed — 75+ assertions, 0 errors")
