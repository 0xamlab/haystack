"""bench_inference_security.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inference_security import prompt_injection_score, token_level_safety_score, tool_call_validation_score, data_leakage_risk_score, jailbreak_pattern_score, output_toxicity_estimate, pii_token_risk, sandboxed_exec_trust_score, rate_limit_violation_score, adversarial_input_score
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

    var _acc_prompt_injection_score: Float64 = 0.0
    var _t0_prompt_injection_score = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_injection_score += prompt_injection_score(0.5, 0.5, 0.5)
    var _t1_prompt_injection_score = perf_counter_ns()
    var _ns_prompt_injection_score = Float64(_t1_prompt_injection_score - _t0_prompt_injection_score) / Float64(N)
    print("MOJO_TIMING inference_security::prompt_injection_score", _ns_prompt_injection_score, _acc_prompt_injection_score)
    var _acc_token_level_safety_score: Float64 = 0.0
    var _t0_token_level_safety_score = perf_counter_ns()
    for _ in range(N):
        _acc_token_level_safety_score += token_level_safety_score(0.5, 0.5, 0.5)
    var _t1_token_level_safety_score = perf_counter_ns()
    var _ns_token_level_safety_score = Float64(_t1_token_level_safety_score - _t0_token_level_safety_score) / Float64(N)
    print("MOJO_TIMING inference_security::token_level_safety_score", _ns_token_level_safety_score, _acc_token_level_safety_score)
    var _acc_tool_call_validation_score: Float64 = 0.0
    var _t0_tool_call_validation_score = perf_counter_ns()
    for _ in range(N):
        _acc_tool_call_validation_score += tool_call_validation_score(0.5, 0.5, 0.5, 0.5)
    var _t1_tool_call_validation_score = perf_counter_ns()
    var _ns_tool_call_validation_score = Float64(_t1_tool_call_validation_score - _t0_tool_call_validation_score) / Float64(N)
    print("MOJO_TIMING inference_security::tool_call_validation_score", _ns_tool_call_validation_score, _acc_tool_call_validation_score)
    var _acc_data_leakage_risk_score: Float64 = 0.0
    var _t0_data_leakage_risk_score = perf_counter_ns()
    for _ in range(N):
        _acc_data_leakage_risk_score += data_leakage_risk_score(0.5, 0.5, 0.5)
    var _t1_data_leakage_risk_score = perf_counter_ns()
    var _ns_data_leakage_risk_score = Float64(_t1_data_leakage_risk_score - _t0_data_leakage_risk_score) / Float64(N)
    print("MOJO_TIMING inference_security::data_leakage_risk_score", _ns_data_leakage_risk_score, _acc_data_leakage_risk_score)
    var _acc_jailbreak_pattern_score: Float64 = 0.0
    var _t0_jailbreak_pattern_score = perf_counter_ns()
    for _ in range(N):
        _acc_jailbreak_pattern_score += jailbreak_pattern_score(0.5, 0.5, 0.5)
    var _t1_jailbreak_pattern_score = perf_counter_ns()
    var _ns_jailbreak_pattern_score = Float64(_t1_jailbreak_pattern_score - _t0_jailbreak_pattern_score) / Float64(N)
    print("MOJO_TIMING inference_security::jailbreak_pattern_score", _ns_jailbreak_pattern_score, _acc_jailbreak_pattern_score)
    var _acc_output_toxicity_estimate: Float64 = 0.0
    var _t0_output_toxicity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_output_toxicity_estimate += output_toxicity_estimate(0.5, 0.5, 0.5)
    var _t1_output_toxicity_estimate = perf_counter_ns()
    var _ns_output_toxicity_estimate = Float64(_t1_output_toxicity_estimate - _t0_output_toxicity_estimate) / Float64(N)
    print("MOJO_TIMING inference_security::output_toxicity_estimate", _ns_output_toxicity_estimate, _acc_output_toxicity_estimate)
    var _acc_pii_token_risk: Float64 = 0.0
    var _t0_pii_token_risk = perf_counter_ns()
    for _ in range(N):
        _acc_pii_token_risk += pii_token_risk(0.5, 0.5, 0.5)
    var _t1_pii_token_risk = perf_counter_ns()
    var _ns_pii_token_risk = Float64(_t1_pii_token_risk - _t0_pii_token_risk) / Float64(N)
    print("MOJO_TIMING inference_security::pii_token_risk", _ns_pii_token_risk, _acc_pii_token_risk)
    var _acc_sandboxed_exec_trust_score: Float64 = 0.0
    var _t0_sandboxed_exec_trust_score = perf_counter_ns()
    for _ in range(N):
        _acc_sandboxed_exec_trust_score += sandboxed_exec_trust_score(0.5, 0.5, 0.5, 0.5)
    var _t1_sandboxed_exec_trust_score = perf_counter_ns()
    var _ns_sandboxed_exec_trust_score = Float64(_t1_sandboxed_exec_trust_score - _t0_sandboxed_exec_trust_score) / Float64(N)
    print("MOJO_TIMING inference_security::sandboxed_exec_trust_score", _ns_sandboxed_exec_trust_score, _acc_sandboxed_exec_trust_score)
    var _acc_rate_limit_violation_score: Float64 = 0.0
    var _t0_rate_limit_violation_score = perf_counter_ns()
    for _ in range(N):
        _acc_rate_limit_violation_score += rate_limit_violation_score(0.5, 0.5, 0.5)
    var _t1_rate_limit_violation_score = perf_counter_ns()
    var _ns_rate_limit_violation_score = Float64(_t1_rate_limit_violation_score - _t0_rate_limit_violation_score) / Float64(N)
    print("MOJO_TIMING inference_security::rate_limit_violation_score", _ns_rate_limit_violation_score, _acc_rate_limit_violation_score)
    var _acc_adversarial_input_score: Float64 = 0.0
    var _t0_adversarial_input_score = perf_counter_ns()
    for _ in range(N):
        _acc_adversarial_input_score += adversarial_input_score(0.5, 0.5, 0.5)
    var _t1_adversarial_input_score = perf_counter_ns()
    var _ns_adversarial_input_score = Float64(_t1_adversarial_input_score - _t0_adversarial_input_score) / Float64(N)
    print("MOJO_TIMING inference_security::adversarial_input_score", _ns_adversarial_input_score, _acc_adversarial_input_score)
