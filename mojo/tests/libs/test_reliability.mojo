"""test_reliability.mojo — auto-generated tests for reliability library."""
from std.math import isnan, isinf
from reliability import exponential_reliability, exponential_failure_rate, weibull_reliability, weibull_failure_rate, mtbf, availability, series_reliability, parallel_reliability, k_of_n_reliability, bathtub_rate, mission_reliability

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

    var _v_exponential_reliability = exponential_reliability(0.5, 0.5)
    if is_finite(_v_exponential_reliability): passed += 1; print("  ✅ reliability::exponential_reliability =", _v_exponential_reliability)
    else: failed += 1; print("  ❌ reliability::exponential_reliability → non-finite:", _v_exponential_reliability)
    var _v_exponential_failure_rate = exponential_failure_rate(0.5)
    if is_finite(_v_exponential_failure_rate): passed += 1; print("  ✅ reliability::exponential_failure_rate =", _v_exponential_failure_rate)
    else: failed += 1; print("  ❌ reliability::exponential_failure_rate → non-finite:", _v_exponential_failure_rate)
    var _v_weibull_reliability = weibull_reliability(0.5, 0.5, 0.5)
    if is_finite(_v_weibull_reliability): passed += 1; print("  ✅ reliability::weibull_reliability =", _v_weibull_reliability)
    else: failed += 1; print("  ❌ reliability::weibull_reliability → non-finite:", _v_weibull_reliability)
    var _v_weibull_failure_rate = weibull_failure_rate(0.5, 0.5, 0.5)
    if is_finite(_v_weibull_failure_rate): passed += 1; print("  ✅ reliability::weibull_failure_rate =", _v_weibull_failure_rate)
    else: failed += 1; print("  ❌ reliability::weibull_failure_rate → non-finite:", _v_weibull_failure_rate)
    var _v_mtbf = mtbf(0.5)
    if is_finite(_v_mtbf): passed += 1; print("  ✅ reliability::mtbf =", _v_mtbf)
    else: failed += 1; print("  ❌ reliability::mtbf → non-finite:", _v_mtbf)
    var _v_availability = availability(0.5, 0.5)
    if is_finite(_v_availability): passed += 1; print("  ✅ reliability::availability =", _v_availability)
    else: failed += 1; print("  ❌ reliability::availability → non-finite:", _v_availability)
    var _v_series_reliability = series_reliability(_lf5)
    if is_finite(_v_series_reliability): passed += 1; print("  ✅ reliability::series_reliability =", _v_series_reliability)
    else: failed += 1; print("  ❌ reliability::series_reliability → non-finite:", _v_series_reliability)
    var _v_parallel_reliability = parallel_reliability(_lf5)
    if is_finite(_v_parallel_reliability): passed += 1; print("  ✅ reliability::parallel_reliability =", _v_parallel_reliability)
    else: failed += 1; print("  ❌ reliability::parallel_reliability → non-finite:", _v_parallel_reliability)
    var _v_k_of_n_reliability = k_of_n_reliability(5, 5, 0.5)
    if is_finite(_v_k_of_n_reliability): passed += 1; print("  ✅ reliability::k_of_n_reliability =", _v_k_of_n_reliability)
    else: failed += 1; print("  ❌ reliability::k_of_n_reliability → non-finite:", _v_k_of_n_reliability)
    var _v_bathtub_rate = bathtub_rate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_bathtub_rate): passed += 1; print("  ✅ reliability::bathtub_rate =", _v_bathtub_rate)
    else: failed += 1; print("  ❌ reliability::bathtub_rate → non-finite:", _v_bathtub_rate)
    var _v_mission_reliability = mission_reliability(0.5, 0.5)
    if is_finite(_v_mission_reliability): passed += 1; print("  ✅ reliability::mission_reliability =", _v_mission_reliability)
    else: failed += 1; print("  ❌ reliability::mission_reliability → non-finite:", _v_mission_reliability)

    print("  [reliability] Passed:", passed, "Failed:", failed)
