"""bench_etiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from etiology import relative_risk, odds_ratio, attributable_risk, population_attributable_risk, number_needed_to_treat, sensitivity_test, specificity_test, positive_predictive_value, negative_predictive_value, likelihood_ratio_positive
from std.time import perf_counter_ns

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
    var _acc_odds_ratio: Float64 = 0.0
    var _t0_odds_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_odds_ratio += odds_ratio(0.5, 0.5, 0.5, 0.5)
    var _t1_odds_ratio = perf_counter_ns()
    var _ns_odds_ratio = Float64(_t1_odds_ratio - _t0_odds_ratio) / Float64(N)
    print("MOJO_TIMING etiology::odds_ratio", _ns_odds_ratio, _acc_odds_ratio)
    var _acc_attributable_risk: Float64 = 0.0
    var _t0_attributable_risk = perf_counter_ns()
    for _ in range(N):
        _acc_attributable_risk += attributable_risk(0.5, 0.5)
    var _t1_attributable_risk = perf_counter_ns()
    var _ns_attributable_risk = Float64(_t1_attributable_risk - _t0_attributable_risk) / Float64(N)
    print("MOJO_TIMING etiology::attributable_risk", _ns_attributable_risk, _acc_attributable_risk)
    var _acc_population_attributable_risk: Float64 = 0.0
    var _t0_population_attributable_risk = perf_counter_ns()
    for _ in range(N):
        _acc_population_attributable_risk += population_attributable_risk(0.5, 0.5)
    var _t1_population_attributable_risk = perf_counter_ns()
    var _ns_population_attributable_risk = Float64(_t1_population_attributable_risk - _t0_population_attributable_risk) / Float64(N)
    print("MOJO_TIMING etiology::population_attributable_risk", _ns_population_attributable_risk, _acc_population_attributable_risk)
    var _acc_number_needed_to_treat: Float64 = 0.0
    var _t0_number_needed_to_treat = perf_counter_ns()
    for _ in range(N):
        _acc_number_needed_to_treat += number_needed_to_treat(0.5, 0.5)
    var _t1_number_needed_to_treat = perf_counter_ns()
    var _ns_number_needed_to_treat = Float64(_t1_number_needed_to_treat - _t0_number_needed_to_treat) / Float64(N)
    print("MOJO_TIMING etiology::number_needed_to_treat", _ns_number_needed_to_treat, _acc_number_needed_to_treat)
    var _acc_sensitivity_test: Float64 = 0.0
    var _t0_sensitivity_test = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_test += sensitivity_test(0.5, 0.5)
    var _t1_sensitivity_test = perf_counter_ns()
    var _ns_sensitivity_test = Float64(_t1_sensitivity_test - _t0_sensitivity_test) / Float64(N)
    print("MOJO_TIMING etiology::sensitivity_test", _ns_sensitivity_test, _acc_sensitivity_test)
    var _acc_specificity_test: Float64 = 0.0
    var _t0_specificity_test = perf_counter_ns()
    for _ in range(N):
        _acc_specificity_test += specificity_test(0.5, 0.5)
    var _t1_specificity_test = perf_counter_ns()
    var _ns_specificity_test = Float64(_t1_specificity_test - _t0_specificity_test) / Float64(N)
    print("MOJO_TIMING etiology::specificity_test", _ns_specificity_test, _acc_specificity_test)
    var _acc_positive_predictive_value: Float64 = 0.0
    var _t0_positive_predictive_value = perf_counter_ns()
    for _ in range(N):
        _acc_positive_predictive_value += positive_predictive_value(0.5, 0.5, 0.5)
    var _t1_positive_predictive_value = perf_counter_ns()
    var _ns_positive_predictive_value = Float64(_t1_positive_predictive_value - _t0_positive_predictive_value) / Float64(N)
    print("MOJO_TIMING etiology::positive_predictive_value", _ns_positive_predictive_value, _acc_positive_predictive_value)
    var _acc_negative_predictive_value: Float64 = 0.0
    var _t0_negative_predictive_value = perf_counter_ns()
    for _ in range(N):
        _acc_negative_predictive_value += negative_predictive_value(0.5, 0.5, 0.5)
    var _t1_negative_predictive_value = perf_counter_ns()
    var _ns_negative_predictive_value = Float64(_t1_negative_predictive_value - _t0_negative_predictive_value) / Float64(N)
    print("MOJO_TIMING etiology::negative_predictive_value", _ns_negative_predictive_value, _acc_negative_predictive_value)
    var _acc_likelihood_ratio_positive: Float64 = 0.0
    var _t0_likelihood_ratio_positive = perf_counter_ns()
    for _ in range(N):
        _acc_likelihood_ratio_positive += likelihood_ratio_positive(0.5, 0.5)
    var _t1_likelihood_ratio_positive = perf_counter_ns()
    var _ns_likelihood_ratio_positive = Float64(_t1_likelihood_ratio_positive - _t0_likelihood_ratio_positive) / Float64(N)
    print("MOJO_TIMING etiology::likelihood_ratio_positive", _ns_likelihood_ratio_positive, _acc_likelihood_ratio_positive)
