"""bench_behavioral_economics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from behavioral_economics import prospect_theory_value, probability_weighting, hyperbolic_discount, quasi_hyperbolic_discount, anchoring_adjusted_estimate, endowment_effect_wta_wtp_ratio, loss_aversion_coefficient, mental_accounting_total, status_quo_bias, sunk_cost_ratio, fairness_ultimatum_threshold, nudge_effectiveness
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_prospect_theory_value: Float64 = 0.0
    var _t0_prospect_theory_value = perf_counter_ns()
    for _ in range(N):
        _acc_prospect_theory_value += prospect_theory_value(0.5, 0.5, 0.5)
    var _t1_prospect_theory_value = perf_counter_ns()
    var _ns_prospect_theory_value = Float64(_t1_prospect_theory_value - _t0_prospect_theory_value) / Float64(N)
    print("MOJO_TIMING behavioral_economics::prospect_theory_value", _ns_prospect_theory_value, _acc_prospect_theory_value)
    var _result_prospect_theory_value = prospect_theory_value(0.5, 0.5, 0.5)
    var _summary_prospect_theory_value = _summary_float64(_result_prospect_theory_value)
    print("MOJO_RESULT behavioral_economics::prospect_theory_value", _summary_prospect_theory_value)
    var _acc_probability_weighting: Float64 = 0.0
    var _t0_probability_weighting = perf_counter_ns()
    for _ in range(N):
        _acc_probability_weighting += probability_weighting(0.5, 0.5)
    var _t1_probability_weighting = perf_counter_ns()
    var _ns_probability_weighting = Float64(_t1_probability_weighting - _t0_probability_weighting) / Float64(N)
    print("MOJO_TIMING behavioral_economics::probability_weighting", _ns_probability_weighting, _acc_probability_weighting)
    var _result_probability_weighting = probability_weighting(0.5, 0.5)
    var _summary_probability_weighting = _summary_float64(_result_probability_weighting)
    print("MOJO_RESULT behavioral_economics::probability_weighting", _summary_probability_weighting)
    var _acc_hyperbolic_discount: Float64 = 0.0
    var _t0_hyperbolic_discount = perf_counter_ns()
    for _ in range(N):
        _acc_hyperbolic_discount += hyperbolic_discount(0.5, 0.5, 0.5)
    var _t1_hyperbolic_discount = perf_counter_ns()
    var _ns_hyperbolic_discount = Float64(_t1_hyperbolic_discount - _t0_hyperbolic_discount) / Float64(N)
    print("MOJO_TIMING behavioral_economics::hyperbolic_discount", _ns_hyperbolic_discount, _acc_hyperbolic_discount)
    var _result_hyperbolic_discount = hyperbolic_discount(0.5, 0.5, 0.5)
    var _summary_hyperbolic_discount = _summary_float64(_result_hyperbolic_discount)
    print("MOJO_RESULT behavioral_economics::hyperbolic_discount", _summary_hyperbolic_discount)
    var _acc_quasi_hyperbolic_discount: Float64 = 0.0
    var _t0_quasi_hyperbolic_discount = perf_counter_ns()
    for _ in range(N):
        _acc_quasi_hyperbolic_discount += quasi_hyperbolic_discount(0.5, 0.5, 0.5, 0.5)
    var _t1_quasi_hyperbolic_discount = perf_counter_ns()
    var _ns_quasi_hyperbolic_discount = Float64(_t1_quasi_hyperbolic_discount - _t0_quasi_hyperbolic_discount) / Float64(N)
    print("MOJO_TIMING behavioral_economics::quasi_hyperbolic_discount", _ns_quasi_hyperbolic_discount, _acc_quasi_hyperbolic_discount)
    var _result_quasi_hyperbolic_discount = quasi_hyperbolic_discount(0.5, 0.5, 0.5, 0.5)
    var _summary_quasi_hyperbolic_discount = _summary_float64(_result_quasi_hyperbolic_discount)
    print("MOJO_RESULT behavioral_economics::quasi_hyperbolic_discount", _summary_quasi_hyperbolic_discount)
    var _acc_anchoring_adjusted_estimate: Float64 = 0.0
    var _t0_anchoring_adjusted_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_anchoring_adjusted_estimate += anchoring_adjusted_estimate(0.5, 0.5, 0.5)
    var _t1_anchoring_adjusted_estimate = perf_counter_ns()
    var _ns_anchoring_adjusted_estimate = Float64(_t1_anchoring_adjusted_estimate - _t0_anchoring_adjusted_estimate) / Float64(N)
    print("MOJO_TIMING behavioral_economics::anchoring_adjusted_estimate", _ns_anchoring_adjusted_estimate, _acc_anchoring_adjusted_estimate)
    var _result_anchoring_adjusted_estimate = anchoring_adjusted_estimate(0.5, 0.5, 0.5)
    var _summary_anchoring_adjusted_estimate = _summary_float64(_result_anchoring_adjusted_estimate)
    print("MOJO_RESULT behavioral_economics::anchoring_adjusted_estimate", _summary_anchoring_adjusted_estimate)
    var _acc_endowment_effect_wta_wtp_ratio: Float64 = 0.0
    var _t0_endowment_effect_wta_wtp_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_endowment_effect_wta_wtp_ratio += endowment_effect_wta_wtp_ratio(0.5, 0.5)
    var _t1_endowment_effect_wta_wtp_ratio = perf_counter_ns()
    var _ns_endowment_effect_wta_wtp_ratio = Float64(_t1_endowment_effect_wta_wtp_ratio - _t0_endowment_effect_wta_wtp_ratio) / Float64(N)
    print("MOJO_TIMING behavioral_economics::endowment_effect_wta_wtp_ratio", _ns_endowment_effect_wta_wtp_ratio, _acc_endowment_effect_wta_wtp_ratio)
    var _result_endowment_effect_wta_wtp_ratio = endowment_effect_wta_wtp_ratio(0.5, 0.5)
    var _summary_endowment_effect_wta_wtp_ratio = _summary_float64(_result_endowment_effect_wta_wtp_ratio)
    print("MOJO_RESULT behavioral_economics::endowment_effect_wta_wtp_ratio", _summary_endowment_effect_wta_wtp_ratio)
    var _acc_loss_aversion_coefficient: Float64 = 0.0
    var _t0_loss_aversion_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_loss_aversion_coefficient += loss_aversion_coefficient(0.5, 0.5)
    var _t1_loss_aversion_coefficient = perf_counter_ns()
    var _ns_loss_aversion_coefficient = Float64(_t1_loss_aversion_coefficient - _t0_loss_aversion_coefficient) / Float64(N)
    print("MOJO_TIMING behavioral_economics::loss_aversion_coefficient", _ns_loss_aversion_coefficient, _acc_loss_aversion_coefficient)
    var _result_loss_aversion_coefficient = loss_aversion_coefficient(0.5, 0.5)
    var _summary_loss_aversion_coefficient = _summary_float64(_result_loss_aversion_coefficient)
    print("MOJO_RESULT behavioral_economics::loss_aversion_coefficient", _summary_loss_aversion_coefficient)
    var _acc_mental_accounting_total: Float64 = 0.0
    var _t0_mental_accounting_total = perf_counter_ns()
    for _ in range(N):
        _acc_mental_accounting_total += mental_accounting_total(0.5, 0.5)
    var _t1_mental_accounting_total = perf_counter_ns()
    var _ns_mental_accounting_total = Float64(_t1_mental_accounting_total - _t0_mental_accounting_total) / Float64(N)
    print("MOJO_TIMING behavioral_economics::mental_accounting_total", _ns_mental_accounting_total, _acc_mental_accounting_total)
    var _result_mental_accounting_total = mental_accounting_total(0.5, 0.5)
    var _summary_mental_accounting_total = _summary_float64(_result_mental_accounting_total)
    print("MOJO_RESULT behavioral_economics::mental_accounting_total", _summary_mental_accounting_total)
    var _acc_status_quo_bias: Float64 = 0.0
    var _t0_status_quo_bias = perf_counter_ns()
    for _ in range(N):
        _acc_status_quo_bias += status_quo_bias(0.5, 0.5)
    var _t1_status_quo_bias = perf_counter_ns()
    var _ns_status_quo_bias = Float64(_t1_status_quo_bias - _t0_status_quo_bias) / Float64(N)
    print("MOJO_TIMING behavioral_economics::status_quo_bias", _ns_status_quo_bias, _acc_status_quo_bias)
    var _result_status_quo_bias = status_quo_bias(0.5, 0.5)
    var _summary_status_quo_bias = _summary_float64(_result_status_quo_bias)
    print("MOJO_RESULT behavioral_economics::status_quo_bias", _summary_status_quo_bias)
    var _acc_sunk_cost_ratio: Float64 = 0.0
    var _t0_sunk_cost_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sunk_cost_ratio += sunk_cost_ratio(0.5, 0.5)
    var _t1_sunk_cost_ratio = perf_counter_ns()
    var _ns_sunk_cost_ratio = Float64(_t1_sunk_cost_ratio - _t0_sunk_cost_ratio) / Float64(N)
    print("MOJO_TIMING behavioral_economics::sunk_cost_ratio", _ns_sunk_cost_ratio, _acc_sunk_cost_ratio)
    var _result_sunk_cost_ratio = sunk_cost_ratio(0.5, 0.5)
    var _summary_sunk_cost_ratio = _summary_float64(_result_sunk_cost_ratio)
    print("MOJO_RESULT behavioral_economics::sunk_cost_ratio", _summary_sunk_cost_ratio)
    var _acc_fairness_ultimatum_threshold: Float64 = 0.0
    var _t0_fairness_ultimatum_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_fairness_ultimatum_threshold += fairness_ultimatum_threshold(0.5, 0.5)
    var _t1_fairness_ultimatum_threshold = perf_counter_ns()
    var _ns_fairness_ultimatum_threshold = Float64(_t1_fairness_ultimatum_threshold - _t0_fairness_ultimatum_threshold) / Float64(N)
    print("MOJO_TIMING behavioral_economics::fairness_ultimatum_threshold", _ns_fairness_ultimatum_threshold, _acc_fairness_ultimatum_threshold)
    var _result_fairness_ultimatum_threshold = fairness_ultimatum_threshold(0.5, 0.5)
    var _summary_fairness_ultimatum_threshold = _summary_float64(_result_fairness_ultimatum_threshold)
    print("MOJO_RESULT behavioral_economics::fairness_ultimatum_threshold", _summary_fairness_ultimatum_threshold)
    var _acc_nudge_effectiveness: Float64 = 0.0
    var _t0_nudge_effectiveness = perf_counter_ns()
    for _ in range(N):
        _acc_nudge_effectiveness += nudge_effectiveness(0.5, 0.5)
    var _t1_nudge_effectiveness = perf_counter_ns()
    var _ns_nudge_effectiveness = Float64(_t1_nudge_effectiveness - _t0_nudge_effectiveness) / Float64(N)
    print("MOJO_TIMING behavioral_economics::nudge_effectiveness", _ns_nudge_effectiveness, _acc_nudge_effectiveness)
    var _result_nudge_effectiveness = nudge_effectiveness(0.5, 0.5)
    var _summary_nudge_effectiveness = _summary_float64(_result_nudge_effectiveness)
    print("MOJO_RESULT behavioral_economics::nudge_effectiveness", _summary_nudge_effectiveness)
