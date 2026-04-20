"""test_biomedical.mojo — auto-generated tests for biomedical library."""
from std.math import isnan, isinf
from biomedical import cardiac_output, mean_arterial_pressure, body_surface_area_dubois, glomerular_filtration_rate, oxygen_delivery, alveolar_gas_equation, bmi, drug_clearance, anion_gap, corrected_qt_bazett, fick_cardiac_output, pulse_pressure

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

    var _v_cardiac_output = cardiac_output(0.5, 0.5)
    if is_finite(_v_cardiac_output): passed += 1; print("  ✅ biomedical::cardiac_output =", _v_cardiac_output)
    else: failed += 1; print("  ❌ biomedical::cardiac_output → non-finite:", _v_cardiac_output)
    var _v_mean_arterial_pressure = mean_arterial_pressure(0.5, 0.5)
    if is_finite(_v_mean_arterial_pressure): passed += 1; print("  ✅ biomedical::mean_arterial_pressure =", _v_mean_arterial_pressure)
    else: failed += 1; print("  ❌ biomedical::mean_arterial_pressure → non-finite:", _v_mean_arterial_pressure)
    var _v_body_surface_area_dubois = body_surface_area_dubois(0.5, 0.5)
    if is_finite(_v_body_surface_area_dubois): passed += 1; print("  ✅ biomedical::body_surface_area_dubois =", _v_body_surface_area_dubois)
    else: failed += 1; print("  ❌ biomedical::body_surface_area_dubois → non-finite:", _v_body_surface_area_dubois)
    var _v_glomerular_filtration_rate = glomerular_filtration_rate(0.5, 0.5, 0.5, True)
    if is_finite(_v_glomerular_filtration_rate): passed += 1; print("  ✅ biomedical::glomerular_filtration_rate =", _v_glomerular_filtration_rate)
    else: failed += 1; print("  ❌ biomedical::glomerular_filtration_rate → non-finite:", _v_glomerular_filtration_rate)
    var _v_oxygen_delivery = oxygen_delivery(0.5, 0.5, 0.5)
    if is_finite(_v_oxygen_delivery): passed += 1; print("  ✅ biomedical::oxygen_delivery =", _v_oxygen_delivery)
    else: failed += 1; print("  ❌ biomedical::oxygen_delivery → non-finite:", _v_oxygen_delivery)
    var _v_alveolar_gas_equation = alveolar_gas_equation(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_alveolar_gas_equation): passed += 1; print("  ✅ biomedical::alveolar_gas_equation =", _v_alveolar_gas_equation)
    else: failed += 1; print("  ❌ biomedical::alveolar_gas_equation → non-finite:", _v_alveolar_gas_equation)
    var _v_bmi = bmi(0.5, 0.5)
    if is_finite(_v_bmi): passed += 1; print("  ✅ biomedical::bmi =", _v_bmi)
    else: failed += 1; print("  ❌ biomedical::bmi → non-finite:", _v_bmi)
    var _v_drug_clearance = drug_clearance(0.5, 0.5)
    if is_finite(_v_drug_clearance): passed += 1; print("  ✅ biomedical::drug_clearance =", _v_drug_clearance)
    else: failed += 1; print("  ❌ biomedical::drug_clearance → non-finite:", _v_drug_clearance)
    var _v_anion_gap = anion_gap(0.5, 0.5, 0.5)
    if is_finite(_v_anion_gap): passed += 1; print("  ✅ biomedical::anion_gap =", _v_anion_gap)
    else: failed += 1; print("  ❌ biomedical::anion_gap → non-finite:", _v_anion_gap)
    var _v_corrected_qt_bazett = corrected_qt_bazett(0.5, 0.5)
    if is_finite(_v_corrected_qt_bazett): passed += 1; print("  ✅ biomedical::corrected_qt_bazett =", _v_corrected_qt_bazett)
    else: failed += 1; print("  ❌ biomedical::corrected_qt_bazett → non-finite:", _v_corrected_qt_bazett)
    var _v_fick_cardiac_output = fick_cardiac_output(0.5, 0.5, 0.5)
    if is_finite(_v_fick_cardiac_output): passed += 1; print("  ✅ biomedical::fick_cardiac_output =", _v_fick_cardiac_output)
    else: failed += 1; print("  ❌ biomedical::fick_cardiac_output → non-finite:", _v_fick_cardiac_output)
    var _v_pulse_pressure = pulse_pressure(0.5, 0.5)
    if is_finite(_v_pulse_pressure): passed += 1; print("  ✅ biomedical::pulse_pressure =", _v_pulse_pressure)
    else: failed += 1; print("  ❌ biomedical::pulse_pressure → non-finite:", _v_pulse_pressure)

    print("  [biomedical] Passed:", passed, "Failed:", failed)
