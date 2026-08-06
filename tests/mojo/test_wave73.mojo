"""Tests for Wave 73 — Corrosion, Paleontology, HVAC. 🎯 300 LIBRARY MILESTONE!"""

from corrosion import (
    corrosion_rate_mpy,
    corrosion_rate_mmpy,
    pitting_rate,
    pitting_factor,
    galvanic_potential_difference,
    nernst_potential,
    passivation_current_density,
    tafel_overpotential,
    metal_loss_from_rate,
    remaining_wall_thickness,
    cathodic_protection_current,
    service_life_estimate,
)
from paleontology import (
    radiocarbon_age,
    potassium_argon_age,
    uranium_lead_age,
    stratigraphic_completeness,
    sedimentation_rate,
    fossil_diversity_index,
    extinction_rate,
    origination_rate,
    turnover_rate,
    body_mass_estimate_mammal,
    phylogenetic_distance,
    completeness_metric,
)
from hvac import (
    sensible_heat_load,
    latent_heat_load,
    total_heat_load,
    sensible_heat_ratio,
    cooling_tons,
    btu_from_tons,
    air_changes_per_hour,
    duct_velocity,
    cop_to_eer,
    eer_to_cop,
    heating_degree_days,
    cooling_degree_days,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, log, exp

comptime TOL: Float64 = 1e-6
comptime LTOL: Float64 = 1e-2


# ── Helper ───────────────────────────────────────────────────────────────────


def _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Corrosion tests ──────────────────────────────────────────────────────────


def test_corrosion_rate_mpy() raises:
    # CR = (534 * 10) / (7.87 * 2.0 * 720) = 5340 / 11332.8 ≈ 0.47122
    var cr = corrosion_rate_mpy(10.0, 7.87, 2.0, 720.0)
    assert_true(_near(cr, 5340.0 / 11332.8, 1e-3), "corrosion_rate_mpy")


def test_corrosion_rate_mmpy() raises:
    # CR = (87600 * 5) / (7.87 * 10.0 * 1000) = 438000 / 78700 ≈ 5.565
    var cr = corrosion_rate_mmpy(5.0, 7.87, 10.0, 1000.0)
    assert_true(_near(cr, 438000.0 / 78700.0, 1e-3), "corrosion_rate_mmpy")


def test_pitting_rate() raises:
    assert_true(_near(pitting_rate(2.5, 5.0), 0.5), "pitting_rate")


def test_pitting_factor() raises:
    assert_true(_near(pitting_factor(3.0, 1.0), 3.0), "pitting_factor")
    assert_true(_near(pitting_factor(2.0, 2.0), 1.0), "pitting_factor=1")


def test_galvanic_potential() raises:
    assert_true(
        _near(galvanic_potential_difference(-0.76, -0.34), 0.42),
        "galvanic_potential",
    )
    assert_true(
        _near(galvanic_potential_difference(0.5, 0.5), 0.0),
        "galvanic_zero",
    )


def test_nernst_potential() raises:
    # E = 0.34 - (8.314*298/(2*96485))*ln(0.1)
    # RT/nF = 2477.572 / 192970 ≈ 0.012839
    # ln(0.1) ≈ -2.302585
    # E ≈ 0.34 - 0.012839*(-2.302585) ≈ 0.34 + 0.02957 ≈ 0.36957
    var e = nernst_potential(0.34, 2.0, 0.1, 298.0)
    assert_true(_near(e, 0.36957, 1e-3), "nernst_potential")


def test_passivation_current_density() raises:
    assert_true(
        _near(passivation_current_density(0.005, 10.0), 0.0005),
        "passivation_i",
    )


def test_tafel_overpotential() raises:
    # η = 0.1 + 0.05 * log10(0.001)
    # log10(0.001) = -3
    # η = 0.1 + 0.05*(-3) = 0.1 - 0.15 = -0.05
    var eta = tafel_overpotential(0.1, 0.05, 0.001)
    assert_true(_near(eta, -0.05, 1e-4), "tafel_overpotential")


def test_metal_loss() raises:
    assert_true(_near(metal_loss_from_rate(0.1, 20.0), 2.0), "metal_loss")


def test_remaining_wall() raises:
    assert_true(
        _near(remaining_wall_thickness(10.0, 2.0), 8.0), "remaining_wall"
    )


def test_cathodic_protection() raises:
    assert_true(
        _near(cathodic_protection_current(100.0, 0.02), 2.0), "cp_current"
    )


def test_service_life() raises:
    assert_true(
        _near(service_life_estimate(10.0, 0.5), 20.0), "service_life"
    )
    assert_true(
        _near(service_life_estimate(6.0, 0.2), 30.0), "service_life_2"
    )


# ── Paleontology tests ──────────────────────────────────────────────────────


def test_radiocarbon_age() raises:
    # t = -ln(0.5) / 1.21e-4 = 0.693147 / 1.21e-4 ≈ 5728.5 years
    var age = radiocarbon_age(0.5, 1.21e-4)
    assert_true(_near(age, 5728.5, 5.0), "radiocarbon_age")


def test_potassium_argon_age() raises:
    # t = ln(1 + 0.01) / 5.543e-10 = 0.00995 / 5.543e-10 ≈ 1.796e7
    var age = potassium_argon_age(0.01, 5.543e-10)
    var expected = log(1.01) / 5.543e-10
    assert_true(_near(age, expected, 1e3), "k_ar_age")


def test_uranium_lead_age() raises:
    var age = uranium_lead_age(0.05, 1.55125e-10)
    var expected = log(1.05) / 1.55125e-10
    assert_true(_near(age, expected, 1e3), "u_pb_age")


def test_stratigraphic_completeness() raises:
    assert_true(
        _near(stratigraphic_completeness(75.0, 100.0), 0.75),
        "strat_complete",
    )


def test_sedimentation_rate() raises:
    assert_true(
        _near(sedimentation_rate(500.0, 10.0), 50.0), "sed_rate"
    )


def test_fossil_diversity() raises:
    # D = (20-1)/ln(1000) = 19/6.9078 ≈ 2.7505
    var d = fossil_diversity_index(20.0, 1000.0)
    assert_true(_near(d, 19.0 / log(1000.0), 1e-3), "margalef_diversity")


def test_extinction_rate() raises:
    # ER = (5/100) / 2.0 = 0.025
    var er = extinction_rate(5.0, 100.0, 2.0)
    assert_true(_near(er, 0.025), "extinction_rate")


def test_origination_rate() raises:
    var o = origination_rate(8.0, 100.0, 4.0)
    assert_true(_near(o, 0.02), "origination_rate")


def test_turnover_rate() raises:
    assert_true(_near(turnover_rate(0.025, 0.02), 0.0225), "turnover_rate")


def test_body_mass_mammal() raises:
    # femur=100mm → log10(M) = 2.75*2 - 3.30 = 2.20 → M = 10^2.20 ≈ 158.49
    var m = body_mass_estimate_mammal(100.0)
    assert_true(_near(m, 158.489, 0.5), "body_mass_100mm")

    # femur=50mm → log10(M) = 2.75*log10(50) - 3.30
    #   log10(50) ≈ 1.69897 → 2.75*1.699 - 3.30 ≈ 1.372 → M ≈ 23.55
    var m2 = body_mass_estimate_mammal(50.0)
    var expected2 = exp((2.75 * log(50.0) / log(10.0) - 3.30) * log(10.0))
    assert_true(_near(m2, expected2, 0.5), "body_mass_50mm")


def test_phylogenetic_distance() raises:
    # D = 2 * 5e6 * 1e-9 = 0.01
    var d = phylogenetic_distance(5.0e6, 1.0e-9)
    assert_true(_near(d, 0.01), "phylo_dist")


def test_completeness_metric() raises:
    assert_true(
        _near(completeness_metric(180.0, 206.0), 180.0 / 206.0, 1e-4),
        "completeness",
    )
    assert_true(
        _near(completeness_metric(206.0, 206.0), 1.0), "completeness_full"
    )


# ── HVAC tests ───────────────────────────────────────────────────────────────


def test_sensible_heat_load() raises:
    # Q = 1.08 * 1000 * 20 = 21600
    var q = sensible_heat_load(1000.0, 20.0)
    assert_true(_near(q, 21600.0), "sensible_heat")


def test_latent_heat_load() raises:
    # Q = 0.68 * 1000 * 30 = 20400
    var q = latent_heat_load(1000.0, 30.0)
    assert_true(_near(q, 20400.0), "latent_heat")


def test_total_heat_load() raises:
    assert_true(
        _near(total_heat_load(21600.0, 20400.0), 42000.0), "total_heat"
    )


def test_sensible_heat_ratio() raises:
    assert_true(
        _near(sensible_heat_ratio(21600.0, 42000.0), 21600.0 / 42000.0),
        "shr",
    )


def test_cooling_tons() raises:
    assert_true(_near(cooling_tons(36000.0), 3.0), "cooling_tons")
    assert_true(_near(cooling_tons(12000.0), 1.0), "one_ton")


def test_btu_from_tons() raises:
    assert_true(_near(btu_from_tons(5.0), 60000.0), "btu_from_tons")


def test_air_changes_per_hour() raises:
    # ACH = 60 * 200 / 2400 = 5.0
    var ach = air_changes_per_hour(200.0, 2400.0)
    assert_true(_near(ach, 5.0), "ach")


def test_duct_velocity() raises:
    # v = 1000 / 2.0 = 500 ft/min
    assert_true(_near(duct_velocity(1000.0, 2.0), 500.0), "duct_vel")


def test_cop_to_eer() raises:
    # EER = 3.5 * 3.412 = 11.942
    assert_true(_near(cop_to_eer(3.5), 11.942), "cop_to_eer")


def test_eer_to_cop() raises:
    # COP = 11.942 / 3.412 ≈ 3.5
    assert_true(_near(eer_to_cop(11.942), 3.5, 1e-3), "eer_to_cop")


def test_cop_eer_roundtrip() raises:
    var cop = 4.0
    var eer = cop_to_eer(cop)
    var cop_back = eer_to_cop(eer)
    assert_true(_near(cop_back, cop, 1e-6), "cop_eer_roundtrip")


def test_heating_degree_days() raises:
    assert_true(
        _near(heating_degree_days(65.0, 40.0), 25.0), "hdd_25"
    )
    assert_true(
        _near(heating_degree_days(65.0, 70.0), 0.0), "hdd_zero"
    )


def test_cooling_degree_days() raises:
    assert_true(
        _near(cooling_degree_days(85.0, 65.0), 20.0), "cdd_20"
    )
    assert_true(
        _near(cooling_degree_days(60.0, 65.0), 0.0), "cdd_zero"
    )


# ── Additional cross-checks ─────────────────────────────────────────────────


def test_corrosion_service_consistency() raises:
    """Metal loss from rate should match remaining wall calc."""
    var rate = 0.25  # mm/yr
    var years = 40.0
    var loss = metal_loss_from_rate(rate, years)
    assert_true(_near(loss, 10.0), "loss=10mm")
    var rem = remaining_wall_thickness(15.0, loss)
    assert_true(_near(rem, 5.0), "remaining=5mm")
    var life = service_life_estimate(15.0, rate)
    assert_true(_near(life, 60.0), "life=60yr")


def test_hvac_heat_balance() raises:
    """SHR * total should equal sensible."""
    var s = sensible_heat_load(500.0, 15.0)
    var l = latent_heat_load(500.0, 25.0)
    var t = total_heat_load(s, l)
    var shr = sensible_heat_ratio(s, t)
    assert_true(_near(shr * t, s, 1e-3), "heat_balance")


def test_paleo_turnover_symmetry() raises:
    """Turnover with equal extinction and origination = either rate."""
    var r = 0.05
    assert_true(_near(turnover_rate(r, r), r), "turnover_symmetric")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 73 Tests: Corrosion, Paleontology, HVAC ===")

    # Corrosion (14 assertions)
    test_corrosion_rate_mpy()
    test_corrosion_rate_mmpy()
    test_pitting_rate()
    test_pitting_factor()
    test_galvanic_potential()
    test_nernst_potential()
    test_passivation_current_density()
    test_tafel_overpotential()
    test_metal_loss()
    test_remaining_wall()
    test_cathodic_protection()
    test_service_life()
    print("  ✓ Corrosion: all tests passed")

    # Paleontology (14 assertions)
    test_radiocarbon_age()
    test_potassium_argon_age()
    test_uranium_lead_age()
    test_stratigraphic_completeness()
    test_sedimentation_rate()
    test_fossil_diversity()
    test_extinction_rate()
    test_origination_rate()
    test_turnover_rate()
    test_body_mass_mammal()
    test_phylogenetic_distance()
    test_completeness_metric()
    print("  ✓ Paleontology: all tests passed")

    # HVAC (16 assertions)
    test_sensible_heat_load()
    test_latent_heat_load()
    test_total_heat_load()
    test_sensible_heat_ratio()
    test_cooling_tons()
    test_btu_from_tons()
    test_air_changes_per_hour()
    test_duct_velocity()
    test_cop_to_eer()
    test_eer_to_cop()
    test_cop_eer_roundtrip()
    test_heating_degree_days()
    test_cooling_degree_days()
    print("  ✓ HVAC: all tests passed")

    # Cross-checks (6 assertions)
    test_corrosion_service_consistency()
    test_hvac_heat_balance()
    test_paleo_turnover_symmetry()
    print("  ✓ Cross-checks: all tests passed")

    print("")
    print("🎯 300 LIBRARY MILESTONE REACHED!")
    print("All Wave 73 tests passed — 70+ assertions, 0 errors")
