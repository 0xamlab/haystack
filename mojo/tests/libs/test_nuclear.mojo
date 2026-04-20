"""test_nuclear.mojo — auto-generated tests for nuclear library."""
from std.math import isnan, isinf
from nuclear import radioactive_decay, half_life_from_lambda, lambda_from_half_life, activity, decay_constant_from_activity, binding_energy_per_nucleon, mass_defect, q_value, neutron_multiplication, dose_rate_inverse_square, shielding_attenuation, critical_mass_estimate

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

    var _v_radioactive_decay = radioactive_decay(0.5, 0.5, 0.5)
    if is_finite(_v_radioactive_decay): passed += 1; print("  ✅ nuclear::radioactive_decay =", _v_radioactive_decay)
    else: failed += 1; print("  ❌ nuclear::radioactive_decay → non-finite:", _v_radioactive_decay)
    var _v_half_life_from_lambda = half_life_from_lambda(0.5)
    if is_finite(_v_half_life_from_lambda): passed += 1; print("  ✅ nuclear::half_life_from_lambda =", _v_half_life_from_lambda)
    else: failed += 1; print("  ❌ nuclear::half_life_from_lambda → non-finite:", _v_half_life_from_lambda)
    var _v_lambda_from_half_life = lambda_from_half_life(0.5)
    if is_finite(_v_lambda_from_half_life): passed += 1; print("  ✅ nuclear::lambda_from_half_life =", _v_lambda_from_half_life)
    else: failed += 1; print("  ❌ nuclear::lambda_from_half_life → non-finite:", _v_lambda_from_half_life)
    var _v_activity = activity(0.5, 0.5)
    if is_finite(_v_activity): passed += 1; print("  ✅ nuclear::activity =", _v_activity)
    else: failed += 1; print("  ❌ nuclear::activity → non-finite:", _v_activity)
    var _v_decay_constant_from_activity = decay_constant_from_activity(0.5, 0.5)
    if is_finite(_v_decay_constant_from_activity): passed += 1; print("  ✅ nuclear::decay_constant_from_activity =", _v_decay_constant_from_activity)
    else: failed += 1; print("  ❌ nuclear::decay_constant_from_activity → non-finite:", _v_decay_constant_from_activity)
    var _v_binding_energy_per_nucleon = binding_energy_per_nucleon(0.5, 0.5)
    if is_finite(_v_binding_energy_per_nucleon): passed += 1; print("  ✅ nuclear::binding_energy_per_nucleon =", _v_binding_energy_per_nucleon)
    else: failed += 1; print("  ❌ nuclear::binding_energy_per_nucleon → non-finite:", _v_binding_energy_per_nucleon)
    var _v_mass_defect = mass_defect(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_mass_defect): passed += 1; print("  ✅ nuclear::mass_defect =", _v_mass_defect)
    else: failed += 1; print("  ❌ nuclear::mass_defect → non-finite:", _v_mass_defect)
    var _v_q_value = q_value(0.5, 0.5, 0.5)
    if is_finite(_v_q_value): passed += 1; print("  ✅ nuclear::q_value =", _v_q_value)
    else: failed += 1; print("  ❌ nuclear::q_value → non-finite:", _v_q_value)
    var _v_neutron_multiplication = neutron_multiplication(0.5, 0.5)
    if is_finite(_v_neutron_multiplication): passed += 1; print("  ✅ nuclear::neutron_multiplication =", _v_neutron_multiplication)
    else: failed += 1; print("  ❌ nuclear::neutron_multiplication → non-finite:", _v_neutron_multiplication)
    var _v_dose_rate_inverse_square = dose_rate_inverse_square(0.5, 0.5, 0.5)
    if is_finite(_v_dose_rate_inverse_square): passed += 1; print("  ✅ nuclear::dose_rate_inverse_square =", _v_dose_rate_inverse_square)
    else: failed += 1; print("  ❌ nuclear::dose_rate_inverse_square → non-finite:", _v_dose_rate_inverse_square)
    var _v_shielding_attenuation = shielding_attenuation(0.5, 0.5, 0.5)
    if is_finite(_v_shielding_attenuation): passed += 1; print("  ✅ nuclear::shielding_attenuation =", _v_shielding_attenuation)
    else: failed += 1; print("  ❌ nuclear::shielding_attenuation → non-finite:", _v_shielding_attenuation)
    var _v_critical_mass_estimate = critical_mass_estimate(0.5, 0.5, 0.5)
    if is_finite(_v_critical_mass_estimate): passed += 1; print("  ✅ nuclear::critical_mass_estimate =", _v_critical_mass_estimate)
    else: failed += 1; print("  ❌ nuclear::critical_mass_estimate → non-finite:", _v_critical_mass_estimate)

    print("  [nuclear] Passed:", passed, "Failed:", failed)
