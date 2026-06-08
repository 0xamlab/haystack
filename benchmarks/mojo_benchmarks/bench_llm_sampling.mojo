"""bench_llm_sampling.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from llm_sampling import temperature_scale, top_k_threshold, top_p_cumulative, greedy_token_id, beam_score_update, repetition_penalty_scale, length_penalty, pow_approx, min_p_threshold, typical_p_score, token_frequency_penalty
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

    var _acc_temperature_scale: Float64 = 0.0
    var _t0_temperature_scale = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_scale += temperature_scale(0.5, 0.5)
    var _t1_temperature_scale = perf_counter_ns()
    var _ns_temperature_scale = Float64(_t1_temperature_scale - _t0_temperature_scale) / Float64(N)
    print("MOJO_TIMING llm_sampling::temperature_scale", _ns_temperature_scale, _acc_temperature_scale)
    var _result_temperature_scale = temperature_scale(0.5, 0.5)
    var _summary_temperature_scale = _summary_float64(_result_temperature_scale)
    print("MOJO_RESULT llm_sampling::temperature_scale", _summary_temperature_scale)
    var _acc_top_k_threshold: Float64 = 0.0
    var _t0_top_k_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_top_k_threshold += top_k_threshold(0.5)
    var _t1_top_k_threshold = perf_counter_ns()
    var _ns_top_k_threshold = Float64(_t1_top_k_threshold - _t0_top_k_threshold) / Float64(N)
    print("MOJO_TIMING llm_sampling::top_k_threshold", _ns_top_k_threshold, _acc_top_k_threshold)
    var _result_top_k_threshold = top_k_threshold(0.5)
    var _summary_top_k_threshold = _summary_float64(_result_top_k_threshold)
    print("MOJO_RESULT llm_sampling::top_k_threshold", _summary_top_k_threshold)
    var _acc_top_p_cumulative: Float64 = 0.0
    var _t0_top_p_cumulative = perf_counter_ns()
    for _ in range(N):
        _acc_top_p_cumulative += top_p_cumulative(0.5, 0.5, 0.5)
    var _t1_top_p_cumulative = perf_counter_ns()
    var _ns_top_p_cumulative = Float64(_t1_top_p_cumulative - _t0_top_p_cumulative) / Float64(N)
    print("MOJO_TIMING llm_sampling::top_p_cumulative", _ns_top_p_cumulative, _acc_top_p_cumulative)
    var _result_top_p_cumulative = top_p_cumulative(0.5, 0.5, 0.5)
    var _summary_top_p_cumulative = _summary_float64(_result_top_p_cumulative)
    print("MOJO_RESULT llm_sampling::top_p_cumulative", _summary_top_p_cumulative)
    var _acc_greedy_token_id: Float64 = 0.0
    var _t0_greedy_token_id = perf_counter_ns()
    for _ in range(N):
        _acc_greedy_token_id += greedy_token_id(0.5, 0.5, 0.5)
    var _t1_greedy_token_id = perf_counter_ns()
    var _ns_greedy_token_id = Float64(_t1_greedy_token_id - _t0_greedy_token_id) / Float64(N)
    print("MOJO_TIMING llm_sampling::greedy_token_id", _ns_greedy_token_id, _acc_greedy_token_id)
    var _result_greedy_token_id = greedy_token_id(0.5, 0.5, 0.5)
    var _summary_greedy_token_id = _summary_float64(_result_greedy_token_id)
    print("MOJO_RESULT llm_sampling::greedy_token_id", _summary_greedy_token_id)
    var _acc_beam_score_update: Float64 = 0.0
    var _t0_beam_score_update = perf_counter_ns()
    for _ in range(N):
        _acc_beam_score_update += beam_score_update(0.5, 0.5)
    var _t1_beam_score_update = perf_counter_ns()
    var _ns_beam_score_update = Float64(_t1_beam_score_update - _t0_beam_score_update) / Float64(N)
    print("MOJO_TIMING llm_sampling::beam_score_update", _ns_beam_score_update, _acc_beam_score_update)
    var _result_beam_score_update = beam_score_update(0.5, 0.5)
    var _summary_beam_score_update = _summary_float64(_result_beam_score_update)
    print("MOJO_RESULT llm_sampling::beam_score_update", _summary_beam_score_update)
    var _acc_repetition_penalty_scale: Float64 = 0.0
    var _t0_repetition_penalty_scale = perf_counter_ns()
    for _ in range(N):
        _acc_repetition_penalty_scale += repetition_penalty_scale(0.5, 0.5, 0.5)
    var _t1_repetition_penalty_scale = perf_counter_ns()
    var _ns_repetition_penalty_scale = Float64(_t1_repetition_penalty_scale - _t0_repetition_penalty_scale) / Float64(N)
    print("MOJO_TIMING llm_sampling::repetition_penalty_scale", _ns_repetition_penalty_scale, _acc_repetition_penalty_scale)
    var _result_repetition_penalty_scale = repetition_penalty_scale(0.5, 0.5, 0.5)
    var _summary_repetition_penalty_scale = _summary_float64(_result_repetition_penalty_scale)
    print("MOJO_RESULT llm_sampling::repetition_penalty_scale", _summary_repetition_penalty_scale)
    var _acc_length_penalty: Float64 = 0.0
    var _t0_length_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_length_penalty += length_penalty(0.5, 0.5, 0.5)
    var _t1_length_penalty = perf_counter_ns()
    var _ns_length_penalty = Float64(_t1_length_penalty - _t0_length_penalty) / Float64(N)
    print("MOJO_TIMING llm_sampling::length_penalty", _ns_length_penalty, _acc_length_penalty)
    var _result_length_penalty = length_penalty(0.5, 0.5, 0.5)
    var _summary_length_penalty = _summary_float64(_result_length_penalty)
    print("MOJO_RESULT llm_sampling::length_penalty", _summary_length_penalty)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING llm_sampling::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _result_pow_approx = pow_approx(0.5, 0.5)
    var _summary_pow_approx = _summary_float64(_result_pow_approx)
    print("MOJO_RESULT llm_sampling::pow_approx", _summary_pow_approx)
    var _acc_min_p_threshold: Float64 = 0.0
    var _t0_min_p_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_min_p_threshold += min_p_threshold(0.5, 0.5)
    var _t1_min_p_threshold = perf_counter_ns()
    var _ns_min_p_threshold = Float64(_t1_min_p_threshold - _t0_min_p_threshold) / Float64(N)
    print("MOJO_TIMING llm_sampling::min_p_threshold", _ns_min_p_threshold, _acc_min_p_threshold)
    var _result_min_p_threshold = min_p_threshold(0.5, 0.5)
    var _summary_min_p_threshold = _summary_float64(_result_min_p_threshold)
    print("MOJO_RESULT llm_sampling::min_p_threshold", _summary_min_p_threshold)
    var _acc_typical_p_score: Float64 = 0.0
    var _t0_typical_p_score = perf_counter_ns()
    for _ in range(N):
        _acc_typical_p_score += typical_p_score(0.5, 0.5)
    var _t1_typical_p_score = perf_counter_ns()
    var _ns_typical_p_score = Float64(_t1_typical_p_score - _t0_typical_p_score) / Float64(N)
    print("MOJO_TIMING llm_sampling::typical_p_score", _ns_typical_p_score, _acc_typical_p_score)
    var _result_typical_p_score = typical_p_score(0.5, 0.5)
    var _summary_typical_p_score = _summary_float64(_result_typical_p_score)
    print("MOJO_RESULT llm_sampling::typical_p_score", _summary_typical_p_score)
    var _acc_token_frequency_penalty: Float64 = 0.0
    var _t0_token_frequency_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_token_frequency_penalty += token_frequency_penalty(0.5, 0.5, 0.5, 0.5)
    var _t1_token_frequency_penalty = perf_counter_ns()
    var _ns_token_frequency_penalty = Float64(_t1_token_frequency_penalty - _t0_token_frequency_penalty) / Float64(N)
    print("MOJO_TIMING llm_sampling::token_frequency_penalty", _ns_token_frequency_penalty, _acc_token_frequency_penalty)
    var _result_token_frequency_penalty = token_frequency_penalty(0.5, 0.5, 0.5, 0.5)
    var _summary_token_frequency_penalty = _summary_float64(_result_token_frequency_penalty)
    print("MOJO_RESULT llm_sampling::token_frequency_penalty", _summary_token_frequency_penalty)
