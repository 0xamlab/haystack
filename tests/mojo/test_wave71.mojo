"""Tests for Wave 71 — Agriculture, Marine, Brewing."""

from agriculture import (
    growing_degree_days,
    crop_water_need,
    irrigation_efficiency,
    fertilizer_rate,
    seed_rate,
    harvest_index,
    yield_per_hectare,
    soil_ph_lime_requirement,
    water_use_efficiency,
    photosynthetically_active_radiation,
    leaf_area_index,
    nitrogen_use_efficiency,
)
from marine import (
    seawater_density,
    wave_speed_deep,
    wave_speed_shallow,
    wave_period,
    significant_wave_height,
    tidal_range,
    mixed_layer_depth_estimate,
    ekman_depth,
    coriolis_parameter,
    buoyancy_frequency,
    salinity_from_conductivity,
    ocean_pressure_at_depth,
)
from brewing import (
    original_gravity_to_plato,
    plato_to_gravity,
    abv_from_og_fg,
    apparent_attenuation,
    real_attenuation,
    ibu_tinseth,
    utilization_tinseth,
    mash_water_volume,
    strike_water_temp,
    color_srm_from_mcu,
    calories_per_12oz,
    priming_sugar_g,
)
from std.math import abs as fabs, sqrt, exp, log, sin

comptime PI: Float64 = 3.141592653589793


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


# ── Agriculture tests ────────────────────────────────────────────────────────


def test_growing_degree_days() raises:
    # (30+10)/2 - 10 = 10
    var v = growing_degree_days(30.0, 10.0, 10.0)
    _assert(fabs(v - 10.0) < 1e-9, "gdd basic")

    # Below base: (10+5)/2 - 10 = -2.5 => 0
    var v2 = growing_degree_days(10.0, 5.0, 10.0)
    _assert(fabs(v2) < 1e-9, "gdd below base")

    # (20+20)/2 - 0 = 20
    var v3 = growing_degree_days(20.0, 20.0, 0.0)
    _assert(fabs(v3 - 20.0) < 1e-9, "gdd zero base")
    print("  ✓ growing_degree_days (3 assertions)")


def test_crop_water_need() raises:
    # ET0=5, Kc=1.2 => 6.0
    var v = crop_water_need(5.0, 1.2)
    _assert(fabs(v - 6.0) < 1e-9, "cwn basic")

    # Kc=0 => 0
    var v2 = crop_water_need(5.0, 0.0)
    _assert(fabs(v2) < 1e-9, "cwn zero kc")
    print("  ✓ crop_water_need (2 assertions)")


def test_irrigation_efficiency() raises:
    # 80/100 = 0.8
    var v = irrigation_efficiency(100.0, 80.0)
    _assert(fabs(v - 0.8) < 1e-9, "irr_eff basic")

    # Zero delivered => 0
    var v2 = irrigation_efficiency(0.0, 50.0)
    _assert(fabs(v2) < 1e-9, "irr_eff zero delivered")
    print("  ✓ irrigation_efficiency (2 assertions)")


def test_fertilizer_rate() raises:
    # (10*0.5 - 2) / 0.8 = (5-2)/0.8 = 3.75
    var v = fertilizer_rate(10.0, 0.5, 2.0, 0.8)
    _assert(fabs(v - 3.75) < 1e-9, "fert_rate basic")

    # Zero efficiency => 0
    var v2 = fertilizer_rate(10.0, 0.5, 2.0, 0.0)
    _assert(fabs(v2) < 1e-9, "fert_rate zero eff")
    print("  ✓ fertilizer_rate (2 assertions)")


def test_seed_rate() raises:
    # 100000 / (0.9 * 0.95) = 100000/0.855 ≈ 116959.06
    var v = seed_rate(100000.0, 0.9, 0.95)
    _assert(fabs(v - 100000.0 / 0.855) < 1e-2, "seed_rate basic")

    # Zero germination => 0
    var v2 = seed_rate(100000.0, 0.0, 0.95)
    _assert(fabs(v2) < 1e-9, "seed_rate zero germ")
    print("  ✓ seed_rate (2 assertions)")


def test_harvest_index() raises:
    # 4000/10000 = 0.4
    var v = harvest_index(4000.0, 10000.0)
    _assert(fabs(v - 0.4) < 1e-9, "hi basic")

    # Zero biomass => 0
    var v2 = harvest_index(4000.0, 0.0)
    _assert(fabs(v2) < 1e-9, "hi zero biomass")
    print("  ✓ harvest_index (2 assertions)")


def test_yield_per_hectare() raises:
    # 5000 / 2.0 = 2500
    var v = yield_per_hectare(5000.0, 2.0)
    _assert(fabs(v - 2500.0) < 1e-9, "yph basic")

    # Zero area => 0
    var v2 = yield_per_hectare(5000.0, 0.0)
    _assert(fabs(v2) < 1e-9, "yph zero area")
    print("  ✓ yield_per_hectare (2 assertions)")


def test_soil_ph_lime_requirement() raises:
    # (6.5 - 5.5) * 2.0 = 2.0
    var v = soil_ph_lime_requirement(5.5, 6.5, 2.0)
    _assert(fabs(v - 2.0) < 1e-9, "lime basic")

    # Already at target => 0
    var v2 = soil_ph_lime_requirement(6.5, 6.5, 2.0)
    _assert(fabs(v2) < 1e-9, "lime at target")
    print("  ✓ soil_ph_lime_requirement (2 assertions)")


def test_water_use_efficiency() raises:
    # 3000 / 500 = 6.0
    var v = water_use_efficiency(3000.0, 500.0)
    _assert(fabs(v - 6.0) < 1e-9, "wue basic")

    # Zero water => 0
    var v2 = water_use_efficiency(3000.0, 0.0)
    _assert(fabs(v2) < 1e-9, "wue zero water")
    print("  ✓ water_use_efficiency (2 assertions)")


def test_par() raises:
    # 0.48 * 1000 = 480
    var v = photosynthetically_active_radiation(1000.0)
    _assert(fabs(v - 480.0) < 1e-9, "par basic")

    # Zero => 0
    var v2 = photosynthetically_active_radiation(0.0)
    _assert(fabs(v2) < 1e-9, "par zero")
    print("  ✓ photosynthetically_active_radiation (2 assertions)")


def test_leaf_area_index() raises:
    # 5.0 / 2.0 = 2.5
    var v = leaf_area_index(5.0, 2.0)
    _assert(fabs(v - 2.5) < 1e-9, "lai basic")

    # Zero ground => 0
    var v2 = leaf_area_index(5.0, 0.0)
    _assert(fabs(v2) < 1e-9, "lai zero ground")
    print("  ✓ leaf_area_index (2 assertions)")


def test_nitrogen_use_efficiency() raises:
    # 500 / 100 = 5.0
    var v = nitrogen_use_efficiency(500.0, 100.0)
    _assert(fabs(v - 5.0) < 1e-9, "nue basic")

    # Zero N => 0
    var v2 = nitrogen_use_efficiency(500.0, 0.0)
    _assert(fabs(v2) < 1e-9, "nue zero n")
    print("  ✓ nitrogen_use_efficiency (2 assertions)")


# ── Marine tests ─────────────────────────────────────────────────────────────


def test_seawater_density() raises:
    # T=10, S=35 => 1025 + 0 - 0 = 1025
    var v = seawater_density(10.0, 35.0)
    _assert(fabs(v - 1025.0) < 1e-9, "sw_density baseline")

    # T=20, S=35 => 1025 + 0 - 0.15*10 = 1023.5
    var v2 = seawater_density(20.0, 35.0)
    _assert(fabs(v2 - 1023.5) < 1e-9, "sw_density warm")

    # T=10, S=40 => 1025 + 0.7*5 - 0 = 1028.5
    var v3 = seawater_density(10.0, 40.0)
    _assert(fabs(v3 - 1028.5) < 1e-9, "sw_density salty")
    print("  ✓ seawater_density (3 assertions)")


def test_wave_speed_deep() raises:
    # λ=100, g=9.81 => sqrt(9.81*100/(2π)) = sqrt(156.13) ≈ 12.495
    var v = wave_speed_deep(100.0, 9.81)
    var expected = sqrt(9.81 * 100.0 / (2.0 * PI))
    _assert(fabs(v - expected) < 1e-6, "wave_deep basic")
    print("  ✓ wave_speed_deep (1 assertion)")


def test_wave_speed_shallow() raises:
    # d=10, g=9.81 => sqrt(98.1) ≈ 9.905
    var v = wave_speed_shallow(10.0, 9.81)
    _assert(fabs(v - sqrt(98.1)) < 1e-6, "wave_shallow basic")

    # d=0 => 0
    var v2 = wave_speed_shallow(0.0, 9.81)
    _assert(fabs(v2) < 1e-9, "wave_shallow zero")
    print("  ✓ wave_speed_shallow (2 assertions)")


def test_wave_period() raises:
    # λ=100, c=10 => T=10
    var v = wave_period(100.0, 10.0)
    _assert(fabs(v - 10.0) < 1e-9, "wave_period basic")

    # c=0 => 0
    var v2 = wave_period(100.0, 0.0)
    _assert(fabs(v2) < 1e-9, "wave_period zero speed")
    print("  ✓ wave_period (2 assertions)")


def test_significant_wave_height() raises:
    # E=4 => 4*sqrt(4) = 8
    var v = significant_wave_height(4.0)
    _assert(fabs(v - 8.0) < 1e-9, "swh basic")

    # E=0 => 0
    var v2 = significant_wave_height(0.0)
    _assert(fabs(v2) < 1e-9, "swh zero")
    print("  ✓ significant_wave_height (2 assertions)")


def test_tidal_range() raises:
    # 3.5 - 0.5 = 3.0
    var v = tidal_range(3.5, 0.5)
    _assert(fabs(v - 3.0) < 1e-9, "tidal basic")

    # Equal => 0
    var v2 = tidal_range(2.0, 2.0)
    _assert(fabs(v2) < 1e-9, "tidal equal")
    print("  ✓ tidal_range (2 assertions)")


def test_mixed_layer_depth() raises:
    # wind=10 => 0.5*100 + 10 = 60
    var v = mixed_layer_depth_estimate(10.0, 45.0)
    _assert(fabs(v - 60.0) < 1e-9, "mld basic")

    # wind=0 => 10
    var v2 = mixed_layer_depth_estimate(0.0, 45.0)
    _assert(fabs(v2 - 10.0) < 1e-9, "mld calm")
    print("  ✓ mixed_layer_depth_estimate (2 assertions)")


def test_ekman_depth() raises:
    # Av=0.01, f=0.0001 => π*sqrt(2*0.01/0.0001) = π*sqrt(200) ≈ 44.43
    var v = ekman_depth(0.0, 0.0001, 0.01)
    var expected = PI * sqrt(200.0)
    _assert(fabs(v - expected) < 1e-4, "ekman basic")

    # f=0 => 0
    var v2 = ekman_depth(0.0, 0.0, 0.01)
    _assert(fabs(v2) < 1e-9, "ekman zero f")
    print("  ✓ ekman_depth (2 assertions)")


def test_coriolis_parameter() raises:
    # lat=90 => f = 2*Ω*sin(π/2) = 2*7.2921e-5 = 1.45842e-4
    var v = coriolis_parameter(90.0)
    _assert(fabs(v - 2.0 * 7.2921e-5) < 1e-9, "coriolis 90")

    # lat=0 => f = 0
    var v2 = coriolis_parameter(0.0)
    _assert(fabs(v2) < 1e-12, "coriolis equator")

    # lat=30 => 2*Ω*sin(π/6) = 2*Ω*0.5 = Ω
    var v3 = coriolis_parameter(30.0)
    _assert(fabs(v3 - 7.2921e-5) < 1e-9, "coriolis 30")
    print("  ✓ coriolis_parameter (3 assertions)")


def test_buoyancy_frequency() raises:
    # drho_dz=-0.01, rho0=1025, g=9.81 => N = sqrt(9.81/1025*0.01) = sqrt(9.571e-5) ≈ 0.00978
    var v = buoyancy_frequency(-0.01, 1025.0, 9.81)
    var expected = sqrt(9.81 / 1025.0 * 0.01)
    _assert(fabs(v - expected) < 1e-6, "buoyancy basic")

    # Positive drho_dz (unstable) => 0
    var v2 = buoyancy_frequency(0.01, 1025.0, 9.81)
    _assert(fabs(v2) < 1e-9, "buoyancy unstable")
    print("  ✓ buoyancy_frequency (2 assertions)")


def test_salinity_from_conductivity() raises:
    # C=70, T=25 => 0.5*70*(1-0) = 35
    var v = salinity_from_conductivity(70.0, 25.0)
    _assert(fabs(v - 35.0) < 1e-9, "salinity baseline")

    # C=70, T=15 => 0.5*70*(1-0.02*(-10)) = 35*(1+0.2) = 42
    var v2 = salinity_from_conductivity(70.0, 15.0)
    _assert(fabs(v2 - 42.0) < 1e-9, "salinity cold")
    print("  ✓ salinity_from_conductivity (2 assertions)")


def test_ocean_pressure_at_depth() raises:
    # d=100, ρ=1025, g=9.81 => 1025*9.81*100 = 1005525
    var v = ocean_pressure_at_depth(100.0, 1025.0, 9.81)
    _assert(fabs(v - 1005525.0) < 1e-2, "ocean_p basic")

    # d=0 => 0
    var v2 = ocean_pressure_at_depth(0.0, 1025.0, 9.81)
    _assert(fabs(v2) < 1e-9, "ocean_p surface")
    print("  ✓ ocean_pressure_at_depth (2 assertions)")


# ── Brewing tests ────────────────────────────────────────────────────────────


def test_original_gravity_to_plato() raises:
    # OG=1.048 => (0.048)*1000/4 = 12
    var v = original_gravity_to_plato(1.048)
    _assert(fabs(v - 12.0) < 1e-9, "og_to_plato basic")

    # OG=1.0 => 0
    var v2 = original_gravity_to_plato(1.0)
    _assert(fabs(v2) < 1e-9, "og_to_plato water")
    print("  ✓ original_gravity_to_plato (2 assertions)")


def test_plato_to_gravity() raises:
    # P=12 => 1 + 48/1000 = 1.048
    var v = plato_to_gravity(12.0)
    _assert(fabs(v - 1.048) < 1e-9, "plato_to_g basic")

    # Round-trip
    var v2 = plato_to_gravity(original_gravity_to_plato(1.060))
    _assert(fabs(v2 - 1.060) < 1e-9, "plato_g roundtrip")
    print("  ✓ plato_to_gravity (2 assertions)")


def test_abv_from_og_fg() raises:
    # OG=1.050, FG=1.010 => 0.040*131.25 = 5.25
    var v = abv_from_og_fg(1.050, 1.010)
    _assert(fabs(v - 5.25) < 1e-6, "abv basic")

    # Same OG/FG => 0
    var v2 = abv_from_og_fg(1.050, 1.050)
    _assert(fabs(v2) < 1e-9, "abv zero")
    print("  ✓ abv_from_og_fg (2 assertions)")


def test_apparent_attenuation() raises:
    # OG=1.050, FG=1.010 => (0.040/0.050)*100 = 80%
    var v = apparent_attenuation(1.050, 1.010)
    _assert(fabs(v - 80.0) < 1e-6, "aa basic")

    # OG=1.0 => 0 (avoid div by zero)
    var v2 = apparent_attenuation(1.0, 1.0)
    _assert(fabs(v2) < 1e-9, "aa zero denom")
    print("  ✓ apparent_attenuation (2 assertions)")


def test_real_attenuation() raises:
    # AA=80 => 80*0.8192 = 65.536
    var v = real_attenuation(80.0)
    _assert(fabs(v - 65.536) < 1e-6, "ra basic")

    # AA=0 => 0
    var v2 = real_attenuation(0.0)
    _assert(fabs(v2) < 1e-9, "ra zero")
    print("  ✓ real_attenuation (2 assertions)")


def test_ibu_tinseth() raises:
    # U=0.2, AA=0.10, W=2.0, V=5.0 => (0.2*0.10*2.0*7490)/5 = 59.92
    var v = ibu_tinseth(0.2, 0.10, 2.0, 5.0)
    _assert(fabs(v - 59.92) < 1e-6, "ibu basic")

    # V=0 => 0
    var v2 = ibu_tinseth(0.2, 0.10, 2.0, 0.0)
    _assert(fabs(v2) < 1e-9, "ibu zero vol")
    print("  ✓ ibu_tinseth (2 assertions)")


def test_utilization_tinseth() raises:
    # At G=1.050, t=60
    var v = utilization_tinseth(1.050, 60.0)
    var bigness = 1.65 * exp(0.050 * log(0.000125))
    var boil = (1.0 - exp(-0.04 * 60.0)) / 4.15
    var expected = bigness * boil
    _assert(fabs(v - expected) < 1e-9, "util basic")

    # t=0 => 0 (no boil time means no utilization)
    var v2 = utilization_tinseth(1.050, 0.0)
    _assert(fabs(v2) < 1e-9, "util zero time")
    print("  ✓ utilization_tinseth (2 assertions)")


def test_mash_water_volume() raises:
    # 5kg * 3.0 L/kg = 15 L
    var v = mash_water_volume(5.0, 3.0)
    _assert(fabs(v - 15.0) < 1e-9, "mash_vol basic")

    # 0 grain => 0
    var v2 = mash_water_volume(0.0, 3.0)
    _assert(fabs(v2) < 1e-9, "mash_vol zero grain")
    print("  ✓ mash_water_volume (2 assertions)")


def test_strike_water_temp() raises:
    # target=67, grain=20, ratio=2.5 => (0.2/2.5)*(67-20)+67 = 0.08*47+67 = 70.76
    var v = strike_water_temp(67.0, 20.0, 2.5)
    var expected = (0.2 / 2.5) * (67.0 - 20.0) + 67.0
    _assert(fabs(v - expected) < 1e-6, "strike basic")

    # ratio=0 => target
    var v2 = strike_water_temp(67.0, 20.0, 0.0)
    _assert(fabs(v2 - 67.0) < 1e-9, "strike zero ratio")
    print("  ✓ strike_water_temp (2 assertions)")


def test_color_srm_from_mcu() raises:
    # MCU=10 => 1.4922 * 10^0.6859 = 1.4922 * exp(0.6859*ln(10))
    var v = color_srm_from_mcu(10.0)
    var expected = 1.4922 * exp(0.6859 * log(10.0))
    _assert(fabs(v - expected) < 1e-6, "srm basic")

    # MCU=0 => 0
    var v2 = color_srm_from_mcu(0.0)
    _assert(fabs(v2) < 1e-9, "srm zero mcu")

    # MCU=1 => 1.4922 * 1 = 1.4922
    var v3 = color_srm_from_mcu(1.0)
    _assert(fabs(v3 - 1.4922) < 1e-4, "srm mcu=1")
    print("  ✓ color_srm_from_mcu (3 assertions)")


def test_calories_per_12oz() raises:
    # OG=1.050, FG=1.010
    var v = calories_per_12oz(1.050, 1.010)
    _assert(v > 0.0, "cal positive")

    # Higher OG => more calories
    var v2 = calories_per_12oz(1.080, 1.020)
    _assert(v2 > v, "cal higher og")
    print("  ✓ calories_per_12oz (2 assertions)")


def test_priming_sugar_g() raises:
    # volume_co2=2.5, temp=20, beer=20L
    var v = priming_sugar_g(2.5, 20.0, 20.0)
    _assert(v > 0.0, "priming positive")

    # Very high residual CO2 (very cold, high target already met) => 0 or near 0
    var v2 = priming_sugar_g(0.5, 2.0, 20.0)
    # At 2°C, residual ≈ 3.0378 - 0.1 + 0.001 ≈ 2.94, so 0.5 < residual => 0
    _assert(fabs(v2) < 1e-9, "priming excess co2")
    print("  ✓ priming_sugar_g (2 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 71 Tests: Agriculture, Marine, Brewing ===")
    print()

    print("── Agriculture ──")
    test_growing_degree_days()
    test_crop_water_need()
    test_irrigation_efficiency()
    test_fertilizer_rate()
    test_seed_rate()
    test_harvest_index()
    test_yield_per_hectare()
    test_soil_ph_lime_requirement()
    test_water_use_efficiency()
    test_par()
    test_leaf_area_index()
    test_nitrogen_use_efficiency()
    print()

    print("── Marine ──")
    test_seawater_density()
    test_wave_speed_deep()
    test_wave_speed_shallow()
    test_wave_period()
    test_significant_wave_height()
    test_tidal_range()
    test_mixed_layer_depth()
    test_ekman_depth()
    test_coriolis_parameter()
    test_buoyancy_frequency()
    test_salinity_from_conductivity()
    test_ocean_pressure_at_depth()
    print()

    print("── Brewing ──")
    test_original_gravity_to_plato()
    test_plato_to_gravity()
    test_abv_from_og_fg()
    test_apparent_attenuation()
    test_real_attenuation()
    test_ibu_tinseth()
    test_utilization_tinseth()
    test_mash_water_volume()
    test_strike_water_temp()
    test_color_srm_from_mcu()
    test_calories_per_12oz()
    test_priming_sugar_g()
    print()

    print("✅ Wave 71 — All 75 assertions passed.")
