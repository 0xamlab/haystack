"""bench_etiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from etiology import relative_risk, odds_ratio, attributable_risk, population_attributable_risk, number_needed_to_treat, sensitivity_test, specificity_test, positive_predictive_value, negative_predictive_value, likelihood_ratio_positive
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_relative_risk: Float64 = 0.0
    var _t0_relative_risk = perf_counter_ns()
    for _ in range(N):
        _acc_relative_risk += relative_risk(0.5, 0.5)
    var _t1_relative_risk = perf_counter_ns()
    var _ns_relative_risk = Float64(_t1_relative_risk - _t0_relative_risk) / Float64(N)
    print("MOJO_TIMING etiology::relative_risk", _ns_relative_risk, _acc_relative_risk)
    var _result_relative_risk = relative_risk(0.5, 0.5)
    var _summary_relative_risk = _summary_float64(_result_relative_risk)
    print("MOJO_RESULT etiology::relative_risk", _summary_relative_risk)
    var _acc_odds_ratio: Float64 = 0.0
    var _t0_odds_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_odds_ratio += odds_ratio(0.5, 0.5, 0.5, 0.5)
    var _t1_odds_ratio = perf_counter_ns()
    var _ns_odds_ratio = Float64(_t1_odds_ratio - _t0_odds_ratio) / Float64(N)
    print("MOJO_TIMING etiology::odds_ratio", _ns_odds_ratio, _acc_odds_ratio)
    var _result_odds_ratio = odds_ratio(0.5, 0.5, 0.5, 0.5)
    var _summary_odds_ratio = _summary_float64(_result_odds_ratio)
    print("MOJO_RESULT etiology::odds_ratio", _summary_odds_ratio)
    var _acc_attributable_risk: Float64 = 0.0
    var _t0_attributable_risk = perf_counter_ns()
    for _ in range(N):
        _acc_attributable_risk += attributable_risk(0.5, 0.5)
    var _t1_attributable_risk = perf_counter_ns()
    var _ns_attributable_risk = Float64(_t1_attributable_risk - _t0_attributable_risk) / Float64(N)
    print("MOJO_TIMING etiology::attributable_risk", _ns_attributable_risk, _acc_attributable_risk)
    var _result_attributable_risk = attributable_risk(0.5, 0.5)
    var _summary_attributable_risk = _summary_float64(_result_attributable_risk)
    print("MOJO_RESULT etiology::attributable_risk", _summary_attributable_risk)
    var _acc_population_attributable_risk: Float64 = 0.0
    var _t0_population_attributable_risk = perf_counter_ns()
    for _ in range(N):
        _acc_population_attributable_risk += population_attributable_risk(0.5, 0.5)
    var _t1_population_attributable_risk = perf_counter_ns()
    var _ns_population_attributable_risk = Float64(_t1_population_attributable_risk - _t0_population_attributable_risk) / Float64(N)
    print("MOJO_TIMING etiology::population_attributable_risk", _ns_population_attributable_risk, _acc_population_attributable_risk)
    var _result_population_attributable_risk = population_attributable_risk(0.5, 0.5)
    var _summary_population_attributable_risk = _summary_float64(_result_population_attributable_risk)
    print("MOJO_RESULT etiology::population_attributable_risk", _summary_population_attributable_risk)
    var _acc_number_needed_to_treat: Float64 = 0.0
    var _t0_number_needed_to_treat = perf_counter_ns()
    for _ in range(N):
        _acc_number_needed_to_treat += number_needed_to_treat(0.5, 0.5)
    var _t1_number_needed_to_treat = perf_counter_ns()
    var _ns_number_needed_to_treat = Float64(_t1_number_needed_to_treat - _t0_number_needed_to_treat) / Float64(N)
    print("MOJO_TIMING etiology::number_needed_to_treat", _ns_number_needed_to_treat, _acc_number_needed_to_treat)
    var _result_number_needed_to_treat = number_needed_to_treat(0.5, 0.5)
    var _summary_number_needed_to_treat = _summary_float64(_result_number_needed_to_treat)
    print("MOJO_RESULT etiology::number_needed_to_treat", _summary_number_needed_to_treat)
    var _acc_sensitivity_test: Float64 = 0.0
    var _t0_sensitivity_test = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_test += sensitivity_test(0.5, 0.5)
    var _t1_sensitivity_test = perf_counter_ns()
    var _ns_sensitivity_test = Float64(_t1_sensitivity_test - _t0_sensitivity_test) / Float64(N)
    print("MOJO_TIMING etiology::sensitivity_test", _ns_sensitivity_test, _acc_sensitivity_test)
    var _result_sensitivity_test = sensitivity_test(0.5, 0.5)
    var _summary_sensitivity_test = _summary_float64(_result_sensitivity_test)
    print("MOJO_RESULT etiology::sensitivity_test", _summary_sensitivity_test)
    var _acc_specificity_test: Float64 = 0.0
    var _t0_specificity_test = perf_counter_ns()
    for _ in range(N):
        _acc_specificity_test += specificity_test(0.5, 0.5)
    var _t1_specificity_test = perf_counter_ns()
    var _ns_specificity_test = Float64(_t1_specificity_test - _t0_specificity_test) / Float64(N)
    print("MOJO_TIMING etiology::specificity_test", _ns_specificity_test, _acc_specificity_test)
    var _result_specificity_test = specificity_test(0.5, 0.5)
    var _summary_specificity_test = _summary_float64(_result_specificity_test)
    print("MOJO_RESULT etiology::specificity_test", _summary_specificity_test)
    var _acc_positive_predictive_value: Float64 = 0.0
    var _t0_positive_predictive_value = perf_counter_ns()
    for _ in range(N):
        _acc_positive_predictive_value += positive_predictive_value(0.5, 0.5, 0.5)
    var _t1_positive_predictive_value = perf_counter_ns()
    var _ns_positive_predictive_value = Float64(_t1_positive_predictive_value - _t0_positive_predictive_value) / Float64(N)
    print("MOJO_TIMING etiology::positive_predictive_value", _ns_positive_predictive_value, _acc_positive_predictive_value)
    var _result_positive_predictive_value = positive_predictive_value(0.5, 0.5, 0.5)
    var _summary_positive_predictive_value = _summary_float64(_result_positive_predictive_value)
    print("MOJO_RESULT etiology::positive_predictive_value", _summary_positive_predictive_value)
    var _acc_negative_predictive_value: Float64 = 0.0
    var _t0_negative_predictive_value = perf_counter_ns()
    for _ in range(N):
        _acc_negative_predictive_value += negative_predictive_value(0.5, 0.5, 0.5)
    var _t1_negative_predictive_value = perf_counter_ns()
    var _ns_negative_predictive_value = Float64(_t1_negative_predictive_value - _t0_negative_predictive_value) / Float64(N)
    print("MOJO_TIMING etiology::negative_predictive_value", _ns_negative_predictive_value, _acc_negative_predictive_value)
    var _result_negative_predictive_value = negative_predictive_value(0.5, 0.5, 0.5)
    var _summary_negative_predictive_value = _summary_float64(_result_negative_predictive_value)
    print("MOJO_RESULT etiology::negative_predictive_value", _summary_negative_predictive_value)
    var _acc_likelihood_ratio_positive: Float64 = 0.0
    var _t0_likelihood_ratio_positive = perf_counter_ns()
    for _ in range(N):
        _acc_likelihood_ratio_positive += likelihood_ratio_positive(0.5, 0.5)
    var _t1_likelihood_ratio_positive = perf_counter_ns()
    var _ns_likelihood_ratio_positive = Float64(_t1_likelihood_ratio_positive - _t0_likelihood_ratio_positive) / Float64(N)
    print("MOJO_TIMING etiology::likelihood_ratio_positive", _ns_likelihood_ratio_positive, _acc_likelihood_ratio_positive)
    var _result_likelihood_ratio_positive = likelihood_ratio_positive(0.5, 0.5)
    var _summary_likelihood_ratio_positive = _summary_float64(_result_likelihood_ratio_positive)
    print("MOJO_RESULT etiology::likelihood_ratio_positive", _summary_likelihood_ratio_positive)
