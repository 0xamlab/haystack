"""bench_behavioral_economics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from behavioral_economics import prospect_theory_value, probability_weighting, hyperbolic_discount, quasi_hyperbolic_discount, anchoring_adjusted_estimate, endowment_effect_wta_wtp_ratio, loss_aversion_coefficient, mental_accounting_total, status_quo_bias, sunk_cost_ratio, fairness_ultimatum_threshold, nudge_effectiveness
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

    var _acc_prospect_theory_value: Float64 = 0.0
    var _t0_prospect_theory_value = perf_counter_ns()
    for _ in range(N):
        _acc_prospect_theory_value += prospect_theory_value(0.5, 0.5, 0.5)
    var _t1_prospect_theory_value = perf_counter_ns()
    var _ns_prospect_theory_value = Float64(_t1_prospect_theory_value - _t0_prospect_theory_value) / Float64(N)
    print("MOJO_TIMING behavioral_economics::prospect_theory_value", _ns_prospect_theory_value, _acc_prospect_theory_value)
    var _acc_probability_weighting: Float64 = 0.0
    var _t0_probability_weighting = perf_counter_ns()
    for _ in range(N):
        _acc_probability_weighting += probability_weighting(0.5, 0.5)
    var _t1_probability_weighting = perf_counter_ns()
    var _ns_probability_weighting = Float64(_t1_probability_weighting - _t0_probability_weighting) / Float64(N)
    print("MOJO_TIMING behavioral_economics::probability_weighting", _ns_probability_weighting, _acc_probability_weighting)
    var _acc_hyperbolic_discount: Float64 = 0.0
    var _t0_hyperbolic_discount = perf_counter_ns()
    for _ in range(N):
        _acc_hyperbolic_discount += hyperbolic_discount(0.5, 0.5, 0.5)
    var _t1_hyperbolic_discount = perf_counter_ns()
    var _ns_hyperbolic_discount = Float64(_t1_hyperbolic_discount - _t0_hyperbolic_discount) / Float64(N)
    print("MOJO_TIMING behavioral_economics::hyperbolic_discount", _ns_hyperbolic_discount, _acc_hyperbolic_discount)
    var _acc_quasi_hyperbolic_discount: Float64 = 0.0
    var _t0_quasi_hyperbolic_discount = perf_counter_ns()
    for _ in range(N):
        _acc_quasi_hyperbolic_discount += quasi_hyperbolic_discount(0.5, 0.5, 0.5, 0.5)
    var _t1_quasi_hyperbolic_discount = perf_counter_ns()
    var _ns_quasi_hyperbolic_discount = Float64(_t1_quasi_hyperbolic_discount - _t0_quasi_hyperbolic_discount) / Float64(N)
    print("MOJO_TIMING behavioral_economics::quasi_hyperbolic_discount", _ns_quasi_hyperbolic_discount, _acc_quasi_hyperbolic_discount)
    var _acc_anchoring_adjusted_estimate: Float64 = 0.0
    var _t0_anchoring_adjusted_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_anchoring_adjusted_estimate += anchoring_adjusted_estimate(0.5, 0.5, 0.5)
    var _t1_anchoring_adjusted_estimate = perf_counter_ns()
    var _ns_anchoring_adjusted_estimate = Float64(_t1_anchoring_adjusted_estimate - _t0_anchoring_adjusted_estimate) / Float64(N)
    print("MOJO_TIMING behavioral_economics::anchoring_adjusted_estimate", _ns_anchoring_adjusted_estimate, _acc_anchoring_adjusted_estimate)
    var _acc_endowment_effect_wta_wtp_ratio: Float64 = 0.0
    var _t0_endowment_effect_wta_wtp_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_endowment_effect_wta_wtp_ratio += endowment_effect_wta_wtp_ratio(0.5, 0.5)
    var _t1_endowment_effect_wta_wtp_ratio = perf_counter_ns()
    var _ns_endowment_effect_wta_wtp_ratio = Float64(_t1_endowment_effect_wta_wtp_ratio - _t0_endowment_effect_wta_wtp_ratio) / Float64(N)
    print("MOJO_TIMING behavioral_economics::endowment_effect_wta_wtp_ratio", _ns_endowment_effect_wta_wtp_ratio, _acc_endowment_effect_wta_wtp_ratio)
    var _acc_loss_aversion_coefficient: Float64 = 0.0
    var _t0_loss_aversion_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_loss_aversion_coefficient += loss_aversion_coefficient(0.5, 0.5)
    var _t1_loss_aversion_coefficient = perf_counter_ns()
    var _ns_loss_aversion_coefficient = Float64(_t1_loss_aversion_coefficient - _t0_loss_aversion_coefficient) / Float64(N)
    print("MOJO_TIMING behavioral_economics::loss_aversion_coefficient", _ns_loss_aversion_coefficient, _acc_loss_aversion_coefficient)
    var _acc_mental_accounting_total: Float64 = 0.0
    var _t0_mental_accounting_total = perf_counter_ns()
    for _ in range(N):
        _acc_mental_accounting_total += mental_accounting_total(0.5, 0.5)
    var _t1_mental_accounting_total = perf_counter_ns()
    var _ns_mental_accounting_total = Float64(_t1_mental_accounting_total - _t0_mental_accounting_total) / Float64(N)
    print("MOJO_TIMING behavioral_economics::mental_accounting_total", _ns_mental_accounting_total, _acc_mental_accounting_total)
    var _acc_status_quo_bias: Float64 = 0.0
    var _t0_status_quo_bias = perf_counter_ns()
    for _ in range(N):
        _acc_status_quo_bias += status_quo_bias(0.5, 0.5)
    var _t1_status_quo_bias = perf_counter_ns()
    var _ns_status_quo_bias = Float64(_t1_status_quo_bias - _t0_status_quo_bias) / Float64(N)
    print("MOJO_TIMING behavioral_economics::status_quo_bias", _ns_status_quo_bias, _acc_status_quo_bias)
    var _acc_sunk_cost_ratio: Float64 = 0.0
    var _t0_sunk_cost_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sunk_cost_ratio += sunk_cost_ratio(0.5, 0.5)
    var _t1_sunk_cost_ratio = perf_counter_ns()
    var _ns_sunk_cost_ratio = Float64(_t1_sunk_cost_ratio - _t0_sunk_cost_ratio) / Float64(N)
    print("MOJO_TIMING behavioral_economics::sunk_cost_ratio", _ns_sunk_cost_ratio, _acc_sunk_cost_ratio)
    var _acc_fairness_ultimatum_threshold: Float64 = 0.0
    var _t0_fairness_ultimatum_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_fairness_ultimatum_threshold += fairness_ultimatum_threshold(0.5, 0.5)
    var _t1_fairness_ultimatum_threshold = perf_counter_ns()
    var _ns_fairness_ultimatum_threshold = Float64(_t1_fairness_ultimatum_threshold - _t0_fairness_ultimatum_threshold) / Float64(N)
    print("MOJO_TIMING behavioral_economics::fairness_ultimatum_threshold", _ns_fairness_ultimatum_threshold, _acc_fairness_ultimatum_threshold)
    var _acc_nudge_effectiveness: Float64 = 0.0
    var _t0_nudge_effectiveness = perf_counter_ns()
    for _ in range(N):
        _acc_nudge_effectiveness += nudge_effectiveness(0.5, 0.5)
    var _t1_nudge_effectiveness = perf_counter_ns()
    var _ns_nudge_effectiveness = Float64(_t1_nudge_effectiveness - _t0_nudge_effectiveness) / Float64(N)
    print("MOJO_TIMING behavioral_economics::nudge_effectiveness", _ns_nudge_effectiveness, _acc_nudge_effectiveness)
