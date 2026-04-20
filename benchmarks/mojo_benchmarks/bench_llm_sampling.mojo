"""bench_llm_sampling.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from llm_sampling import temperature_scale, top_k_threshold, top_p_cumulative, greedy_token_id, beam_score_update, repetition_penalty_scale, length_penalty, pow_approx, min_p_threshold, typical_p_score, token_frequency_penalty
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

    var _acc_temperature_scale: Float64 = 0.0
    var _t0_temperature_scale = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_scale += temperature_scale(0.5, 0.5)
    var _t1_temperature_scale = perf_counter_ns()
    var _ns_temperature_scale = Float64(_t1_temperature_scale - _t0_temperature_scale) / Float64(N)
    print("MOJO_TIMING llm_sampling::temperature_scale", _ns_temperature_scale, _acc_temperature_scale)
    var _acc_top_k_threshold: Float64 = 0.0
    var _t0_top_k_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_top_k_threshold += top_k_threshold(0.5)
    var _t1_top_k_threshold = perf_counter_ns()
    var _ns_top_k_threshold = Float64(_t1_top_k_threshold - _t0_top_k_threshold) / Float64(N)
    print("MOJO_TIMING llm_sampling::top_k_threshold", _ns_top_k_threshold, _acc_top_k_threshold)
    var _acc_top_p_cumulative: Float64 = 0.0
    var _t0_top_p_cumulative = perf_counter_ns()
    for _ in range(N):
        _acc_top_p_cumulative += top_p_cumulative(0.5, 0.5, 0.5)
    var _t1_top_p_cumulative = perf_counter_ns()
    var _ns_top_p_cumulative = Float64(_t1_top_p_cumulative - _t0_top_p_cumulative) / Float64(N)
    print("MOJO_TIMING llm_sampling::top_p_cumulative", _ns_top_p_cumulative, _acc_top_p_cumulative)
    var _acc_greedy_token_id: Float64 = 0.0
    var _t0_greedy_token_id = perf_counter_ns()
    for _ in range(N):
        _acc_greedy_token_id += greedy_token_id(0.5, 0.5, 0.5)
    var _t1_greedy_token_id = perf_counter_ns()
    var _ns_greedy_token_id = Float64(_t1_greedy_token_id - _t0_greedy_token_id) / Float64(N)
    print("MOJO_TIMING llm_sampling::greedy_token_id", _ns_greedy_token_id, _acc_greedy_token_id)
    var _acc_beam_score_update: Float64 = 0.0
    var _t0_beam_score_update = perf_counter_ns()
    for _ in range(N):
        _acc_beam_score_update += beam_score_update(0.5, 0.5)
    var _t1_beam_score_update = perf_counter_ns()
    var _ns_beam_score_update = Float64(_t1_beam_score_update - _t0_beam_score_update) / Float64(N)
    print("MOJO_TIMING llm_sampling::beam_score_update", _ns_beam_score_update, _acc_beam_score_update)
    var _acc_repetition_penalty_scale: Float64 = 0.0
    var _t0_repetition_penalty_scale = perf_counter_ns()
    for _ in range(N):
        _acc_repetition_penalty_scale += repetition_penalty_scale(0.5, 0.5, 0.5)
    var _t1_repetition_penalty_scale = perf_counter_ns()
    var _ns_repetition_penalty_scale = Float64(_t1_repetition_penalty_scale - _t0_repetition_penalty_scale) / Float64(N)
    print("MOJO_TIMING llm_sampling::repetition_penalty_scale", _ns_repetition_penalty_scale, _acc_repetition_penalty_scale)
    var _acc_length_penalty: Float64 = 0.0
    var _t0_length_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_length_penalty += length_penalty(0.5, 0.5, 0.5)
    var _t1_length_penalty = perf_counter_ns()
    var _ns_length_penalty = Float64(_t1_length_penalty - _t0_length_penalty) / Float64(N)
    print("MOJO_TIMING llm_sampling::length_penalty", _ns_length_penalty, _acc_length_penalty)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING llm_sampling::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _acc_min_p_threshold: Float64 = 0.0
    var _t0_min_p_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_min_p_threshold += min_p_threshold(0.5, 0.5)
    var _t1_min_p_threshold = perf_counter_ns()
    var _ns_min_p_threshold = Float64(_t1_min_p_threshold - _t0_min_p_threshold) / Float64(N)
    print("MOJO_TIMING llm_sampling::min_p_threshold", _ns_min_p_threshold, _acc_min_p_threshold)
    var _acc_typical_p_score: Float64 = 0.0
    var _t0_typical_p_score = perf_counter_ns()
    for _ in range(N):
        _acc_typical_p_score += typical_p_score(0.5, 0.5)
    var _t1_typical_p_score = perf_counter_ns()
    var _ns_typical_p_score = Float64(_t1_typical_p_score - _t0_typical_p_score) / Float64(N)
    print("MOJO_TIMING llm_sampling::typical_p_score", _ns_typical_p_score, _acc_typical_p_score)
    var _acc_token_frequency_penalty: Float64 = 0.0
    var _t0_token_frequency_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_token_frequency_penalty += token_frequency_penalty(0.5, 0.5, 0.5, 0.5)
    var _t1_token_frequency_penalty = perf_counter_ns()
    var _ns_token_frequency_penalty = Float64(_t1_token_frequency_penalty - _t0_token_frequency_penalty) / Float64(N)
    print("MOJO_TIMING llm_sampling::token_frequency_penalty", _ns_token_frequency_penalty, _acc_token_frequency_penalty)
