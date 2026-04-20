"""test_semiconductors.mojo — auto-generated tests for semiconductors library."""
from std.math import isnan, isinf
from semiconductors import intrinsic_carrier_concentration, drift_velocity, resistivity, conductivity, depletion_width, built_in_potential, thermal_voltage, diode_current, mosfet_saturation_current, junction_capacitance, diffusion_length, band_gap_temperature

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_intrinsic_carrier_concentration = intrinsic_carrier_concentration(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_intrinsic_carrier_concentration): passed += 1; print("  ✅ semiconductors::intrinsic_carrier_concentration =", _v_intrinsic_carrier_concentration)
    else: failed += 1; print("  ❌ semiconductors::intrinsic_carrier_concentration → non-finite:", _v_intrinsic_carrier_concentration)
    var _v_drift_velocity = drift_velocity(0.5, 0.5)
    if is_finite(_v_drift_velocity): passed += 1; print("  ✅ semiconductors::drift_velocity =", _v_drift_velocity)
    else: failed += 1; print("  ❌ semiconductors::drift_velocity → non-finite:", _v_drift_velocity)
    var _v_resistivity = resistivity(0.5, 0.5, 0.5)
    if is_finite(_v_resistivity): passed += 1; print("  ✅ semiconductors::resistivity =", _v_resistivity)
    else: failed += 1; print("  ❌ semiconductors::resistivity → non-finite:", _v_resistivity)
    var _v_conductivity = conductivity(0.5, 0.5, 0.5)
    if is_finite(_v_conductivity): passed += 1; print("  ✅ semiconductors::conductivity =", _v_conductivity)
    else: failed += 1; print("  ❌ semiconductors::conductivity → non-finite:", _v_conductivity)
    var _v_depletion_width = depletion_width(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_depletion_width): passed += 1; print("  ✅ semiconductors::depletion_width =", _v_depletion_width)
    else: failed += 1; print("  ❌ semiconductors::depletion_width → non-finite:", _v_depletion_width)
    var _v_built_in_potential = built_in_potential(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_built_in_potential): passed += 1; print("  ✅ semiconductors::built_in_potential =", _v_built_in_potential)
    else: failed += 1; print("  ❌ semiconductors::built_in_potential → non-finite:", _v_built_in_potential)
    var _v_thermal_voltage = thermal_voltage(0.5, 0.5, 0.5)
    if is_finite(_v_thermal_voltage): passed += 1; print("  ✅ semiconductors::thermal_voltage =", _v_thermal_voltage)
    else: failed += 1; print("  ❌ semiconductors::thermal_voltage → non-finite:", _v_thermal_voltage)
    var _v_diode_current = diode_current(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_diode_current): passed += 1; print("  ✅ semiconductors::diode_current =", _v_diode_current)
    else: failed += 1; print("  ❌ semiconductors::diode_current → non-finite:", _v_diode_current)
    var _v_mosfet_saturation_current = mosfet_saturation_current(0.5, 0.5, 0.5)
    if is_finite(_v_mosfet_saturation_current): passed += 1; print("  ✅ semiconductors::mosfet_saturation_current =", _v_mosfet_saturation_current)
    else: failed += 1; print("  ❌ semiconductors::mosfet_saturation_current → non-finite:", _v_mosfet_saturation_current)
    var _v_junction_capacitance = junction_capacitance(1e-12, 0.3, 0.7, 0.5)
    if is_finite(_v_junction_capacitance): passed += 1; print("  ✅ semiconductors::junction_capacitance =", _v_junction_capacitance)
    else: failed += 1; print("  ❌ semiconductors::junction_capacitance → non-finite:", _v_junction_capacitance)
    var _v_diffusion_length = diffusion_length(0.5, 0.5)
    if is_finite(_v_diffusion_length): passed += 1; print("  ✅ semiconductors::diffusion_length =", _v_diffusion_length)
    else: failed += 1; print("  ❌ semiconductors::diffusion_length → non-finite:", _v_diffusion_length)
    var _v_band_gap_temperature = band_gap_temperature(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_band_gap_temperature): passed += 1; print("  ✅ semiconductors::band_gap_temperature =", _v_band_gap_temperature)
    else: failed += 1; print("  ❌ semiconductors::band_gap_temperature → non-finite:", _v_band_gap_temperature)

    print("  [semiconductors] Passed:", passed, "Failed:", failed)
