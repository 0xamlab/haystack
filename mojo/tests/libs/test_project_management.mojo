"""test_project_management.mojo — auto-generated tests for project_management library."""
from std.math import isnan, isinf
from project_management import earned_value, schedule_variance, cost_variance, schedule_performance_index, cost_performance_index, estimate_at_completion, estimate_to_complete, variance_at_completion, to_complete_performance_index, critical_path_duration, float_time, pert_estimate

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

    var _v_earned_value = earned_value(0.5, 0.5)
    if is_finite(_v_earned_value): passed += 1; print("  ✅ project_management::earned_value =", _v_earned_value)
    else: failed += 1; print("  ❌ project_management::earned_value → non-finite:", _v_earned_value)
    var _v_schedule_variance = schedule_variance(0.5, 0.5)
    if is_finite(_v_schedule_variance): passed += 1; print("  ✅ project_management::schedule_variance =", _v_schedule_variance)
    else: failed += 1; print("  ❌ project_management::schedule_variance → non-finite:", _v_schedule_variance)
    var _v_cost_variance = cost_variance(0.5, 0.5)
    if is_finite(_v_cost_variance): passed += 1; print("  ✅ project_management::cost_variance =", _v_cost_variance)
    else: failed += 1; print("  ❌ project_management::cost_variance → non-finite:", _v_cost_variance)
    var _v_schedule_performance_index = schedule_performance_index(0.5, 0.5)
    if is_finite(_v_schedule_performance_index): passed += 1; print("  ✅ project_management::schedule_performance_index =", _v_schedule_performance_index)
    else: failed += 1; print("  ❌ project_management::schedule_performance_index → non-finite:", _v_schedule_performance_index)
    var _v_cost_performance_index = cost_performance_index(0.5, 0.5)
    if is_finite(_v_cost_performance_index): passed += 1; print("  ✅ project_management::cost_performance_index =", _v_cost_performance_index)
    else: failed += 1; print("  ❌ project_management::cost_performance_index → non-finite:", _v_cost_performance_index)
    var _v_estimate_at_completion = estimate_at_completion(0.5, 0.5)
    if is_finite(_v_estimate_at_completion): passed += 1; print("  ✅ project_management::estimate_at_completion =", _v_estimate_at_completion)
    else: failed += 1; print("  ❌ project_management::estimate_at_completion → non-finite:", _v_estimate_at_completion)
    var _v_estimate_to_complete = estimate_to_complete(0.5, 0.5)
    if is_finite(_v_estimate_to_complete): passed += 1; print("  ✅ project_management::estimate_to_complete =", _v_estimate_to_complete)
    else: failed += 1; print("  ❌ project_management::estimate_to_complete → non-finite:", _v_estimate_to_complete)
    var _v_variance_at_completion = variance_at_completion(0.5, 0.5)
    if is_finite(_v_variance_at_completion): passed += 1; print("  ✅ project_management::variance_at_completion =", _v_variance_at_completion)
    else: failed += 1; print("  ❌ project_management::variance_at_completion → non-finite:", _v_variance_at_completion)
    var _v_to_complete_performance_index = to_complete_performance_index(0.5, 0.5, 0.5)
    if is_finite(_v_to_complete_performance_index): passed += 1; print("  ✅ project_management::to_complete_performance_index =", _v_to_complete_performance_index)
    else: failed += 1; print("  ❌ project_management::to_complete_performance_index → non-finite:", _v_to_complete_performance_index)
    var _v_critical_path_duration = critical_path_duration(0.5)
    if is_finite(_v_critical_path_duration): passed += 1; print("  ✅ project_management::critical_path_duration =", _v_critical_path_duration)
    else: failed += 1; print("  ❌ project_management::critical_path_duration → non-finite:", _v_critical_path_duration)
    var _v_float_time = float_time(0.5, 0.5)
    if is_finite(_v_float_time): passed += 1; print("  ✅ project_management::float_time =", _v_float_time)
    else: failed += 1; print("  ❌ project_management::float_time → non-finite:", _v_float_time)
    var _v_pert_estimate = pert_estimate(0.5, 0.5, 0.5)
    if is_finite(_v_pert_estimate): passed += 1; print("  ✅ project_management::pert_estimate =", _v_pert_estimate)
    else: failed += 1; print("  ❌ project_management::pert_estimate → non-finite:", _v_pert_estimate)

    print("  [project_management] Passed:", passed, "Failed:", failed)
