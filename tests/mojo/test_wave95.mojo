"""Tests for Wave 95: semiconductors, viticulture, hydraulics."""

from std.testing import assert_true, assert_false, assert_equal
from std.math import sqrt, log, exp, abs

from semiconductors import (
    intrinsic_carrier_concentration,
    drift_velocity,
    resistivity,
    conductivity,
    depletion_width,
    built_in_potential,
    thermal_voltage,
    diode_current,
    mosfet_saturation_current,
    junction_capacitance,
    diffusion_length,
    band_gap_temperature,
)
from viticulture import (
    brix_to_potential_alcohol,
    chaptalization_sugar,
    total_acidity_as_tartaric,
    ph_buffer_capacity,
    growing_degree_days_wine,
    winkler_index_daily,
    yield_tonnes_per_hectare,
    vine_density,
    pruning_weight_ratio,
    must_volume_from_grapes,
    sulfite_molecular_so2,
    fermentation_progress,
)
from hydraulics import (
    pascals_law_force,
    pascals_law_pressure,
    hydraulic_advantage,
    flow_rate_cylinder,
    cylinder_velocity,
    pump_displacement,
    hydraulic_power,
    system_pressure_loss,
    accumulator_volume,
    relief_valve_flow,
    oil_compressibility,
    cylinder_bore_from_force,
)


def approx(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    if abs(b) < 1e-12:
        return abs(a - b) < tol
    return abs(a - b) / abs(b) < tol


def test_semiconductors() raises:
    print("Testing semiconductors...")

    # intrinsic_carrier_concentration: ni0*exp(-Eg/(2kT))
    # ni0=1e10, Eg=1.12eV, k=8.617e-5 eV/K, T=300K
    var k = 8.617e-5
    var t = 300.0
    var ni = intrinsic_carrier_concentration(1e10, 1.12, k, t)
    var expected_ni = 1e10 * exp(-1.12 / (2.0 * k * t))
    assert_true(approx(ni, expected_ni), "intrinsic_carrier_concentration")

    # drift_velocity
    var vd = drift_velocity(1500.0, 1000.0)
    assert_true(approx(vd, 1500000.0), "drift_velocity")

    # resistivity: 1/(n*q*μ)
    var rho = resistivity(1e16, 1.6e-19, 1400.0)
    var expected_rho = 1.0 / (1e16 * 1.6e-19 * 1400.0)
    assert_true(approx(rho, expected_rho), "resistivity")

    # conductivity: n*q*μ
    var sigma = conductivity(1e16, 1.6e-19, 1400.0)
    var expected_sigma = 1e16 * 1.6e-19 * 1400.0
    assert_true(approx(sigma, expected_sigma), "conductivity")

    # conductivity * resistivity ≈ 1
    assert_true(approx(sigma * rho, 1.0), "sigma*rho=1")

    # depletion_width
    var eps = 11.7 * 8.854e-12
    var vbi_val = 0.7
    var na = 1e17
    var nd = 1e15
    var q = 1.6e-19
    var w = depletion_width(eps, vbi_val, na, nd, q)
    var expected_w = sqrt(2.0 * eps * vbi_val * (na + nd) / (q * na * nd))
    assert_true(approx(w, expected_w), "depletion_width")

    # built_in_potential
    var vt = 0.02585
    var vbi2 = built_in_potential(vt, 1e17, 1e15, 1.5e10)
    var expected_vbi = vt * log(1e17 * 1e15 / (1.5e10 * 1.5e10))
    assert_true(approx(vbi2, expected_vbi), "built_in_potential")

    # thermal_voltage
    var vt2 = thermal_voltage(1.38e-23, 300.0, 1.6e-19)
    var expected_vt = 1.38e-23 * 300.0 / 1.6e-19
    assert_true(approx(vt2, expected_vt), "thermal_voltage")

    # diode_current
    var i_d = diode_current(1e-12, 0.6, 0.02585, 1.0)
    var expected_id = 1e-12 * (exp(0.6 / 0.02585) - 1.0)
    assert_true(approx(i_d, expected_id), "diode_current")

    # diode_current at V=0 should be 0
    var i_zero = diode_current(1e-12, 0.0, 0.02585, 1.0)
    assert_true(approx(i_zero, 0.0, 1e-20), "diode_current_zero_v")

    # mosfet_saturation_current
    var id_sat = mosfet_saturation_current(0.5e-3, 3.0, 1.0)
    var expected_idsat = 0.5 * 0.5e-3 * 4.0  # 0.5*Kn*(2)^2
    assert_true(approx(id_sat, expected_idsat), "mosfet_saturation")

    # junction_capacitance
    var cj = junction_capacitance(10e-12, -2.0, 0.7, 0.5)
    var base = 1.0 - (-2.0) / 0.7  # 1+2/0.7 = 3.857
    var expected_cj = 10e-12 / exp(0.5 * log(base))
    assert_true(approx(cj, expected_cj), "junction_capacitance")

    # diffusion_length
    var dl = diffusion_length(25.0, 1e-6)
    var expected_dl = sqrt(25.0 * 1e-6)
    assert_true(approx(dl, expected_dl), "diffusion_length")

    # band_gap_temperature: Eg(T) = Eg0 - α*T²/(T+β)
    # Silicon: Eg0=1.166, α=4.73e-4, β=636
    var eg = band_gap_temperature(1.166, 4.73e-4, 636.0, 300.0)
    var expected_eg = 1.166 - 4.73e-4 * 300.0 * 300.0 / (300.0 + 636.0)
    assert_true(approx(eg, expected_eg), "band_gap_temperature")

    # band_gap at T=0 should equal Eg0
    var eg0 = band_gap_temperature(1.166, 4.73e-4, 636.0, 0.0)
    assert_true(approx(eg0, 1.166), "band_gap_T0")

    print("  semiconductors: all passed ✓")


def test_viticulture() raises:
    print("Testing viticulture...")

    # brix_to_potential_alcohol
    var abv = brix_to_potential_alcohol(24.0)
    assert_true(approx(abv, 13.2), "brix_to_alcohol")

    var abv0 = brix_to_potential_alcohol(0.0)
    assert_true(approx(abv0, 0.0), "brix_to_alcohol_zero")

    # chaptalization_sugar
    var sugar = chaptalization_sugar(24.0, 20.0, 100.0)
    assert_true(approx(sugar, 4.0 * 100.0 * 1.7), "chaptalization")

    var sugar_zero = chaptalization_sugar(20.0, 20.0, 100.0)
    assert_true(approx(sugar_zero, 0.0), "chaptalization_zero")

    # total_acidity_as_tartaric
    var ta = total_acidity_as_tartaric(6.5)
    assert_true(approx(ta, 6.5), "total_acidity")

    # ph_buffer_capacity
    var bc = ph_buffer_capacity(6.0, 3.5)
    assert_true(approx(bc, 6.0 * 0.3 / 1.0), "ph_buffer_capacity")

    # growing_degree_days_wine
    var gdd = growing_degree_days_wine(30.0, 20.0, 10.0)
    assert_true(approx(gdd, 15.0), "gdd_wine")

    var gdd_cold = growing_degree_days_wine(8.0, 4.0, 10.0)
    assert_true(approx(gdd_cold, 0.0), "gdd_wine_cold")

    # winkler_index_daily
    var wi = winkler_index_daily(15.0)
    assert_true(approx(wi, 15.0), "winkler_daily")

    # yield_tonnes_per_hectare
    var y = yield_tonnes_per_hectare(8000.0, 1.0)
    assert_true(approx(y, 8.0), "yield_tonnes")

    var y2 = yield_tonnes_per_hectare(5000.0, 2.0)
    assert_true(approx(y2, 2.5), "yield_tonnes_2ha")

    # vine_density
    var d = vine_density(30.0, 100.0, 1.0)
    assert_true(approx(d, 3000.0), "vine_density")

    # pruning_weight_ratio (Ravaz index)
    var ravaz = pruning_weight_ratio(5.0, 1.0)
    assert_true(approx(ravaz, 5.0), "ravaz_index")

    # must_volume_from_grapes
    var vol = must_volume_from_grapes(1000.0, 0.75)
    assert_true(approx(vol, 750.0), "must_volume")

    # sulfite_molecular_so2
    var mol = sulfite_molecular_so2(30.0, 3.5)
    var power = exp((3.5 - 1.81) * log(10.0))
    var expected_mol = 30.0 / (1.0 + power)
    assert_true(approx(mol, expected_mol), "molecular_so2")

    # At very low pH, molecular SO2 should approach free SO2
    var mol_low = sulfite_molecular_so2(30.0, 1.81)
    # At pH=1.81: 10^0 = 1, so mol = 30/(1+1) = 15
    assert_true(approx(mol_low, 15.0), "molecular_so2_low_ph")

    # fermentation_progress
    var prog = fermentation_progress(24.0, 0.0)
    assert_true(approx(prog, 100.0), "fermentation_complete")

    var prog_half = fermentation_progress(24.0, 12.0)
    assert_true(approx(prog_half, 50.0), "fermentation_half")

    var prog_start = fermentation_progress(24.0, 24.0)
    assert_true(approx(prog_start, 0.0), "fermentation_start")

    print("  viticulture: all passed ✓")


def test_hydraulics() raises:
    print("Testing hydraulics...")

    # pascals_law_force
    var f = pascals_law_force(100000.0, 0.01)
    assert_true(approx(f, 1000.0), "pascals_force")

    # pascals_law_pressure
    var p = pascals_law_pressure(1000.0, 0.01)
    assert_true(approx(p, 100000.0), "pascals_pressure")

    # round trip: F->P->F
    var p2 = pascals_law_pressure(f, 0.01)
    assert_true(approx(p2, 100000.0), "pascals_roundtrip")

    # hydraulic_advantage
    var ma = hydraulic_advantage(0.1, 0.01)
    assert_true(approx(ma, 10.0), "hydraulic_advantage")

    # flow_rate_cylinder
    var q = flow_rate_cylinder(0.005, 2.0)
    assert_true(approx(q, 0.01), "flow_rate")

    # cylinder_velocity
    var v = cylinder_velocity(0.01, 0.005)
    assert_true(approx(v, 2.0), "cylinder_velocity")

    # round trip: Q = A*v, v = Q/A
    var v2 = cylinder_velocity(flow_rate_cylinder(0.005, 3.0), 0.005)
    assert_true(approx(v2, 3.0), "flow_vel_roundtrip")

    # pump_displacement
    var disp = pump_displacement(0.1, 1500.0)
    var expected_disp = 0.1 / 1500.0
    assert_true(approx(disp, expected_disp), "pump_displacement")

    # hydraulic_power
    var pw = hydraulic_power(20e6, 0.001)
    assert_true(approx(pw, 20000.0), "hydraulic_power")

    # system_pressure_loss
    var dp = system_pressure_loss(0.01, 5e8)
    assert_true(approx(dp, 0.01 * 0.01 * 5e8), "pressure_loss")

    # accumulator_volume
    var av = accumulator_volume(10.0, 100.0, 200.0)
    assert_true(approx(av, 10.0), "accumulator_volume")

    var av2 = accumulator_volume(5.0, 50.0, 150.0)
    assert_true(approx(av2, 5.0 * (150.0 / 50.0 - 1.0)), "accumulator_volume_2")

    # relief_valve_flow
    var rv = relief_valve_flow(150.0, 100.0, 0.5)
    assert_true(approx(rv, 25.0), "relief_valve_open")

    var rv_closed = relief_valve_flow(80.0, 100.0, 0.5)
    assert_true(approx(rv_closed, 0.0), "relief_valve_closed")

    var rv_crack = relief_valve_flow(100.0, 100.0, 0.5)
    assert_true(approx(rv_crack, 0.0), "relief_valve_at_crack")

    # oil_compressibility
    var dv = oil_compressibility(1.0, 10e6, 1.5e9)
    var expected_dv = 1.0 * 10e6 / 1.5e9
    assert_true(approx(dv, expected_dv), "oil_compressibility")

    # cylinder_bore_from_force
    var pi = 3.141592653589793
    var bore = cylinder_bore_from_force(10000.0, 20e6)
    var expected_bore = sqrt(4.0 * 10000.0 / (pi * 20e6))
    assert_true(approx(bore, expected_bore), "cylinder_bore")

    # Verify bore produces correct force: F = P * π*d²/4
    var area_check = pi * bore * bore / 4.0
    var force_check = 20e6 * area_check
    assert_true(approx(force_check, 10000.0), "bore_force_roundtrip")

    print("  hydraulics: all passed ✓")


def main() raises:
    print("=== Wave 95 Tests ===")
    test_semiconductors()
    test_viticulture()
    test_hydraulics()
    print("=== All Wave 95 tests passed! ===")
