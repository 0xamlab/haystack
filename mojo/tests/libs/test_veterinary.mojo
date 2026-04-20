"""test_veterinary.mojo — auto-generated tests for veterinary library."""
from std.math import isnan, isinf
from veterinary import dose_mg, fluid_rate_ml_hr, fluid_deficit, maintenance_fluid_dog, caloric_requirement_dog, body_condition_score_ideal, anesthesia_mac, gestation_period_days, heart_rate_normal_range_low, heart_rate_normal_range_high, packed_cell_volume_normal, blood_volume_estimate

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

    var _v_dose_mg = dose_mg(0.5, 0.5)
    if is_finite(_v_dose_mg): passed += 1; print("  ✅ veterinary::dose_mg =", _v_dose_mg)
    else: failed += 1; print("  ❌ veterinary::dose_mg → non-finite:", _v_dose_mg)
    var _v_fluid_rate_ml_hr = fluid_rate_ml_hr(0.5, 0.5)
    if is_finite(_v_fluid_rate_ml_hr): passed += 1; print("  ✅ veterinary::fluid_rate_ml_hr =", _v_fluid_rate_ml_hr)
    else: failed += 1; print("  ❌ veterinary::fluid_rate_ml_hr → non-finite:", _v_fluid_rate_ml_hr)
    var _v_fluid_deficit = fluid_deficit(0.5, 0.5)
    if is_finite(_v_fluid_deficit): passed += 1; print("  ✅ veterinary::fluid_deficit =", _v_fluid_deficit)
    else: failed += 1; print("  ❌ veterinary::fluid_deficit → non-finite:", _v_fluid_deficit)
    var _v_maintenance_fluid_dog = maintenance_fluid_dog(0.5)
    if is_finite(_v_maintenance_fluid_dog): passed += 1; print("  ✅ veterinary::maintenance_fluid_dog =", _v_maintenance_fluid_dog)
    else: failed += 1; print("  ❌ veterinary::maintenance_fluid_dog → non-finite:", _v_maintenance_fluid_dog)
    var _v_caloric_requirement_dog = caloric_requirement_dog(0.5)
    if is_finite(_v_caloric_requirement_dog): passed += 1; print("  ✅ veterinary::caloric_requirement_dog =", _v_caloric_requirement_dog)
    else: failed += 1; print("  ❌ veterinary::caloric_requirement_dog → non-finite:", _v_caloric_requirement_dog)
    var _v_body_condition_score_ideal = body_condition_score_ideal(5)
    if is_finite(_v_body_condition_score_ideal): passed += 1; print("  ✅ veterinary::body_condition_score_ideal =", _v_body_condition_score_ideal)
    else: failed += 1; print("  ❌ veterinary::body_condition_score_ideal → non-finite:", _v_body_condition_score_ideal)
    var _v_anesthesia_mac = anesthesia_mac(5, 5)
    if is_finite(_v_anesthesia_mac): passed += 1; print("  ✅ veterinary::anesthesia_mac =", _v_anesthesia_mac)
    else: failed += 1; print("  ❌ veterinary::anesthesia_mac → non-finite:", _v_anesthesia_mac)
    var _v_gestation_period_days = gestation_period_days(5)
    if is_finite(_v_gestation_period_days): passed += 1; print("  ✅ veterinary::gestation_period_days =", _v_gestation_period_days)
    else: failed += 1; print("  ❌ veterinary::gestation_period_days → non-finite:", _v_gestation_period_days)
    var _v_heart_rate_normal_range_low = heart_rate_normal_range_low(5)
    if is_finite(_v_heart_rate_normal_range_low): passed += 1; print("  ✅ veterinary::heart_rate_normal_range_low =", _v_heart_rate_normal_range_low)
    else: failed += 1; print("  ❌ veterinary::heart_rate_normal_range_low → non-finite:", _v_heart_rate_normal_range_low)
    var _v_heart_rate_normal_range_high = heart_rate_normal_range_high(5)
    if is_finite(_v_heart_rate_normal_range_high): passed += 1; print("  ✅ veterinary::heart_rate_normal_range_high =", _v_heart_rate_normal_range_high)
    else: failed += 1; print("  ❌ veterinary::heart_rate_normal_range_high → non-finite:", _v_heart_rate_normal_range_high)
    var _v_packed_cell_volume_normal = packed_cell_volume_normal(5)
    if is_finite(_v_packed_cell_volume_normal): passed += 1; print("  ✅ veterinary::packed_cell_volume_normal =", _v_packed_cell_volume_normal)
    else: failed += 1; print("  ❌ veterinary::packed_cell_volume_normal → non-finite:", _v_packed_cell_volume_normal)
    var _v_blood_volume_estimate = blood_volume_estimate(0.5, 5)
    if is_finite(_v_blood_volume_estimate): passed += 1; print("  ✅ veterinary::blood_volume_estimate =", _v_blood_volume_estimate)
    else: failed += 1; print("  ❌ veterinary::blood_volume_estimate → non-finite:", _v_blood_volume_estimate)

    print("  [veterinary] Passed:", passed, "Failed:", failed)
