"""bench_generation_loop.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from generation_loop import temperature_logit_scale, top_k_accept, top_p_cumulative_accept, min_p_accept, repetition_penalty_logit, presence_penalty_logit, frequency_penalty_logit, eos_stop_score, eta_sampling_accept, typical_sampling_accept
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

    var _acc_temperature_logit_scale: Float64 = 0.0
    var _t0_temperature_logit_scale = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_logit_scale += temperature_logit_scale(0.5, 0.5)
    var _t1_temperature_logit_scale = perf_counter_ns()
    var _ns_temperature_logit_scale = Float64(_t1_temperature_logit_scale - _t0_temperature_logit_scale) / Float64(N)
    print("MOJO_TIMING generation_loop::temperature_logit_scale", _ns_temperature_logit_scale, _acc_temperature_logit_scale)
    var _result_temperature_logit_scale = temperature_logit_scale(0.5, 0.5)
    var _summary_temperature_logit_scale = _summary_float64(_result_temperature_logit_scale)
    print("MOJO_RESULT generation_loop::temperature_logit_scale", _summary_temperature_logit_scale)
    var _acc_top_k_accept: Float64 = 0.0
    var _t0_top_k_accept = perf_counter_ns()
    for _ in range(N):
        _acc_top_k_accept += top_k_accept(0.5, 0.5)
    var _t1_top_k_accept = perf_counter_ns()
    var _ns_top_k_accept = Float64(_t1_top_k_accept - _t0_top_k_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::top_k_accept", _ns_top_k_accept, _acc_top_k_accept)
    var _result_top_k_accept = top_k_accept(0.5, 0.5)
    var _summary_top_k_accept = _summary_float64(_result_top_k_accept)
    print("MOJO_RESULT generation_loop::top_k_accept", _summary_top_k_accept)
    var _acc_top_p_cumulative_accept: Float64 = 0.0
    var _t0_top_p_cumulative_accept = perf_counter_ns()
    for _ in range(N):
        _acc_top_p_cumulative_accept += top_p_cumulative_accept(0.5, 0.5, 0.5)
    var _t1_top_p_cumulative_accept = perf_counter_ns()
    var _ns_top_p_cumulative_accept = Float64(_t1_top_p_cumulative_accept - _t0_top_p_cumulative_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::top_p_cumulative_accept", _ns_top_p_cumulative_accept, _acc_top_p_cumulative_accept)
    var _result_top_p_cumulative_accept = top_p_cumulative_accept(0.5, 0.5, 0.5)
    var _summary_top_p_cumulative_accept = _summary_float64(_result_top_p_cumulative_accept)
    print("MOJO_RESULT generation_loop::top_p_cumulative_accept", _summary_top_p_cumulative_accept)
    var _acc_min_p_accept: Float64 = 0.0
    var _t0_min_p_accept = perf_counter_ns()
    for _ in range(N):
        _acc_min_p_accept += min_p_accept(0.5, 0.5, 0.5)
    var _t1_min_p_accept = perf_counter_ns()
    var _ns_min_p_accept = Float64(_t1_min_p_accept - _t0_min_p_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::min_p_accept", _ns_min_p_accept, _acc_min_p_accept)
    var _result_min_p_accept = min_p_accept(0.5, 0.5, 0.5)
    var _summary_min_p_accept = _summary_float64(_result_min_p_accept)
    print("MOJO_RESULT generation_loop::min_p_accept", _summary_min_p_accept)
    var _acc_repetition_penalty_logit: Float64 = 0.0
    var _t0_repetition_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_repetition_penalty_logit += repetition_penalty_logit(0.5, 0.5, 0.5)
    var _t1_repetition_penalty_logit = perf_counter_ns()
    var _ns_repetition_penalty_logit = Float64(_t1_repetition_penalty_logit - _t0_repetition_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::repetition_penalty_logit", _ns_repetition_penalty_logit, _acc_repetition_penalty_logit)
    var _result_repetition_penalty_logit = repetition_penalty_logit(0.5, 0.5, 0.5)
    var _summary_repetition_penalty_logit = _summary_float64(_result_repetition_penalty_logit)
    print("MOJO_RESULT generation_loop::repetition_penalty_logit", _summary_repetition_penalty_logit)
    var _acc_presence_penalty_logit: Float64 = 0.0
    var _t0_presence_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_presence_penalty_logit += presence_penalty_logit(0.5, 0.5, 0.5)
    var _t1_presence_penalty_logit = perf_counter_ns()
    var _ns_presence_penalty_logit = Float64(_t1_presence_penalty_logit - _t0_presence_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::presence_penalty_logit", _ns_presence_penalty_logit, _acc_presence_penalty_logit)
    var _result_presence_penalty_logit = presence_penalty_logit(0.5, 0.5, 0.5)
    var _summary_presence_penalty_logit = _summary_float64(_result_presence_penalty_logit)
    print("MOJO_RESULT generation_loop::presence_penalty_logit", _summary_presence_penalty_logit)
    var _acc_frequency_penalty_logit: Float64 = 0.0
    var _t0_frequency_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_penalty_logit += frequency_penalty_logit(0.5, 0.5, 0.5)
    var _t1_frequency_penalty_logit = perf_counter_ns()
    var _ns_frequency_penalty_logit = Float64(_t1_frequency_penalty_logit - _t0_frequency_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::frequency_penalty_logit", _ns_frequency_penalty_logit, _acc_frequency_penalty_logit)
    var _result_frequency_penalty_logit = frequency_penalty_logit(0.5, 0.5, 0.5)
    var _summary_frequency_penalty_logit = _summary_float64(_result_frequency_penalty_logit)
    print("MOJO_RESULT generation_loop::frequency_penalty_logit", _summary_frequency_penalty_logit)
    var _acc_eos_stop_score: Float64 = 0.0
    var _t0_eos_stop_score = perf_counter_ns()
    for _ in range(N):
        _acc_eos_stop_score += eos_stop_score(0.5, 0.5)
    var _t1_eos_stop_score = perf_counter_ns()
    var _ns_eos_stop_score = Float64(_t1_eos_stop_score - _t0_eos_stop_score) / Float64(N)
    print("MOJO_TIMING generation_loop::eos_stop_score", _ns_eos_stop_score, _acc_eos_stop_score)
    var _result_eos_stop_score = eos_stop_score(0.5, 0.5)
    var _summary_eos_stop_score = _summary_float64(_result_eos_stop_score)
    print("MOJO_RESULT generation_loop::eos_stop_score", _summary_eos_stop_score)
    var _acc_eta_sampling_accept: Float64 = 0.0
    var _t0_eta_sampling_accept = perf_counter_ns()
    for _ in range(N):
        _acc_eta_sampling_accept += eta_sampling_accept(0.5, 0.5, 0.5)
    var _t1_eta_sampling_accept = perf_counter_ns()
    var _ns_eta_sampling_accept = Float64(_t1_eta_sampling_accept - _t0_eta_sampling_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::eta_sampling_accept", _ns_eta_sampling_accept, _acc_eta_sampling_accept)
    var _result_eta_sampling_accept = eta_sampling_accept(0.5, 0.5, 0.5)
    var _summary_eta_sampling_accept = _summary_float64(_result_eta_sampling_accept)
    print("MOJO_RESULT generation_loop::eta_sampling_accept", _summary_eta_sampling_accept)
    var _acc_typical_sampling_accept: Float64 = 0.0
    var _t0_typical_sampling_accept = perf_counter_ns()
    for _ in range(N):
        _acc_typical_sampling_accept += typical_sampling_accept(0.5, 0.5, 0.5)
    var _t1_typical_sampling_accept = perf_counter_ns()
    var _ns_typical_sampling_accept = Float64(_t1_typical_sampling_accept - _t0_typical_sampling_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::typical_sampling_accept", _ns_typical_sampling_accept, _acc_typical_sampling_accept)
    var _result_typical_sampling_accept = typical_sampling_accept(0.5, 0.5, 0.5)
    var _summary_typical_sampling_accept = _summary_float64(_result_typical_sampling_accept)
    print("MOJO_RESULT generation_loop::typical_sampling_accept", _summary_typical_sampling_accept)
