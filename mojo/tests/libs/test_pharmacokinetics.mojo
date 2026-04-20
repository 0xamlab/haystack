"""test_pharmacokinetics.mojo — auto-generated tests for pharmacokinetics library."""
from std.math import isnan, isinf
from pharmacokinetics import one_compartment_oral, one_compartment_iv, half_life, elimination_rate, clearance, bioavailability, loading_dose, maintenance_dose, steady_state_concentration, time_to_peak, accumulation_factor, drug_auc_trapezoidal

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

    var _v_one_compartment_oral = one_compartment_oral(100.0, 0.8, 0.2, 10.0, 2.0)
    if is_finite(_v_one_compartment_oral): passed += 1; print("  ✅ pharmacokinetics::one_compartment_oral =", _v_one_compartment_oral)
    else: failed += 1; print("  ❌ pharmacokinetics::one_compartment_oral → non-finite:", _v_one_compartment_oral)
    var _v_one_compartment_iv = one_compartment_iv(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_one_compartment_iv): passed += 1; print("  ✅ pharmacokinetics::one_compartment_iv =", _v_one_compartment_iv)
    else: failed += 1; print("  ❌ pharmacokinetics::one_compartment_iv → non-finite:", _v_one_compartment_iv)
    var _v_half_life = half_life(0.5)
    if is_finite(_v_half_life): passed += 1; print("  ✅ pharmacokinetics::half_life =", _v_half_life)
    else: failed += 1; print("  ❌ pharmacokinetics::half_life → non-finite:", _v_half_life)
    var _v_elimination_rate = elimination_rate(0.5)
    if is_finite(_v_elimination_rate): passed += 1; print("  ✅ pharmacokinetics::elimination_rate =", _v_elimination_rate)
    else: failed += 1; print("  ❌ pharmacokinetics::elimination_rate → non-finite:", _v_elimination_rate)
    var _v_clearance = clearance(0.5, 0.5)
    if is_finite(_v_clearance): passed += 1; print("  ✅ pharmacokinetics::clearance =", _v_clearance)
    else: failed += 1; print("  ❌ pharmacokinetics::clearance → non-finite:", _v_clearance)
    var _v_bioavailability = bioavailability(0.5, 0.5)
    if is_finite(_v_bioavailability): passed += 1; print("  ✅ pharmacokinetics::bioavailability =", _v_bioavailability)
    else: failed += 1; print("  ❌ pharmacokinetics::bioavailability → non-finite:", _v_bioavailability)
    var _v_loading_dose = loading_dose(0.5, 0.5)
    if is_finite(_v_loading_dose): passed += 1; print("  ✅ pharmacokinetics::loading_dose =", _v_loading_dose)
    else: failed += 1; print("  ❌ pharmacokinetics::loading_dose → non-finite:", _v_loading_dose)
    var _v_maintenance_dose = maintenance_dose(0.5, 0.5, 0.5)
    if is_finite(_v_maintenance_dose): passed += 1; print("  ✅ pharmacokinetics::maintenance_dose =", _v_maintenance_dose)
    else: failed += 1; print("  ❌ pharmacokinetics::maintenance_dose → non-finite:", _v_maintenance_dose)
    var _v_steady_state_concentration = steady_state_concentration(0.5, 0.5, 0.5)
    if is_finite(_v_steady_state_concentration): passed += 1; print("  ✅ pharmacokinetics::steady_state_concentration =", _v_steady_state_concentration)
    else: failed += 1; print("  ❌ pharmacokinetics::steady_state_concentration → non-finite:", _v_steady_state_concentration)
    var _v_time_to_peak = time_to_peak(0.8, 0.2)
    if is_finite(_v_time_to_peak): passed += 1; print("  ✅ pharmacokinetics::time_to_peak =", _v_time_to_peak)
    else: failed += 1; print("  ❌ pharmacokinetics::time_to_peak → non-finite:", _v_time_to_peak)
    var _v_accumulation_factor = accumulation_factor(0.5, 0.5)
    if is_finite(_v_accumulation_factor): passed += 1; print("  ✅ pharmacokinetics::accumulation_factor =", _v_accumulation_factor)
    else: failed += 1; print("  ❌ pharmacokinetics::accumulation_factor → non-finite:", _v_accumulation_factor)
    var _v_drug_auc_trapezoidal = drug_auc_trapezoidal(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_drug_auc_trapezoidal): passed += 1; print("  ✅ pharmacokinetics::drug_auc_trapezoidal =", _v_drug_auc_trapezoidal)
    else: failed += 1; print("  ❌ pharmacokinetics::drug_auc_trapezoidal → non-finite:", _v_drug_auc_trapezoidal)

    print("  [pharmacokinetics] Passed:", passed, "Failed:", failed)
