"""bench_generation_loop.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from generation_loop import temperature_logit_scale, top_k_accept, top_p_cumulative_accept, min_p_accept, repetition_penalty_logit, presence_penalty_logit, frequency_penalty_logit, eos_stop_score, eta_sampling_accept, typical_sampling_accept
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

    var _acc_temperature_logit_scale: Float64 = 0.0
    var _t0_temperature_logit_scale = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_logit_scale += temperature_logit_scale(0.5, 0.5)
    var _t1_temperature_logit_scale = perf_counter_ns()
    var _ns_temperature_logit_scale = Float64(_t1_temperature_logit_scale - _t0_temperature_logit_scale) / Float64(N)
    print("MOJO_TIMING generation_loop::temperature_logit_scale", _ns_temperature_logit_scale, _acc_temperature_logit_scale)
    var _acc_top_k_accept: Float64 = 0.0
    var _t0_top_k_accept = perf_counter_ns()
    for _ in range(N):
        _acc_top_k_accept += top_k_accept(0.5, 0.5)
    var _t1_top_k_accept = perf_counter_ns()
    var _ns_top_k_accept = Float64(_t1_top_k_accept - _t0_top_k_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::top_k_accept", _ns_top_k_accept, _acc_top_k_accept)
    var _acc_top_p_cumulative_accept: Float64 = 0.0
    var _t0_top_p_cumulative_accept = perf_counter_ns()
    for _ in range(N):
        _acc_top_p_cumulative_accept += top_p_cumulative_accept(0.5, 0.5, 0.5)
    var _t1_top_p_cumulative_accept = perf_counter_ns()
    var _ns_top_p_cumulative_accept = Float64(_t1_top_p_cumulative_accept - _t0_top_p_cumulative_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::top_p_cumulative_accept", _ns_top_p_cumulative_accept, _acc_top_p_cumulative_accept)
    var _acc_min_p_accept: Float64 = 0.0
    var _t0_min_p_accept = perf_counter_ns()
    for _ in range(N):
        _acc_min_p_accept += min_p_accept(0.5, 0.5, 0.5)
    var _t1_min_p_accept = perf_counter_ns()
    var _ns_min_p_accept = Float64(_t1_min_p_accept - _t0_min_p_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::min_p_accept", _ns_min_p_accept, _acc_min_p_accept)
    var _acc_repetition_penalty_logit: Float64 = 0.0
    var _t0_repetition_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_repetition_penalty_logit += repetition_penalty_logit(0.5, 0.5, 0.5)
    var _t1_repetition_penalty_logit = perf_counter_ns()
    var _ns_repetition_penalty_logit = Float64(_t1_repetition_penalty_logit - _t0_repetition_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::repetition_penalty_logit", _ns_repetition_penalty_logit, _acc_repetition_penalty_logit)
    var _acc_presence_penalty_logit: Float64 = 0.0
    var _t0_presence_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_presence_penalty_logit += presence_penalty_logit(0.5, 0.5, 0.5)
    var _t1_presence_penalty_logit = perf_counter_ns()
    var _ns_presence_penalty_logit = Float64(_t1_presence_penalty_logit - _t0_presence_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::presence_penalty_logit", _ns_presence_penalty_logit, _acc_presence_penalty_logit)
    var _acc_frequency_penalty_logit: Float64 = 0.0
    var _t0_frequency_penalty_logit = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_penalty_logit += frequency_penalty_logit(0.5, 0.5, 0.5)
    var _t1_frequency_penalty_logit = perf_counter_ns()
    var _ns_frequency_penalty_logit = Float64(_t1_frequency_penalty_logit - _t0_frequency_penalty_logit) / Float64(N)
    print("MOJO_TIMING generation_loop::frequency_penalty_logit", _ns_frequency_penalty_logit, _acc_frequency_penalty_logit)
    var _acc_eos_stop_score: Float64 = 0.0
    var _t0_eos_stop_score = perf_counter_ns()
    for _ in range(N):
        _acc_eos_stop_score += eos_stop_score(0.5, 0.5)
    var _t1_eos_stop_score = perf_counter_ns()
    var _ns_eos_stop_score = Float64(_t1_eos_stop_score - _t0_eos_stop_score) / Float64(N)
    print("MOJO_TIMING generation_loop::eos_stop_score", _ns_eos_stop_score, _acc_eos_stop_score)
    var _acc_eta_sampling_accept: Float64 = 0.0
    var _t0_eta_sampling_accept = perf_counter_ns()
    for _ in range(N):
        _acc_eta_sampling_accept += eta_sampling_accept(0.5, 0.5, 0.5)
    var _t1_eta_sampling_accept = perf_counter_ns()
    var _ns_eta_sampling_accept = Float64(_t1_eta_sampling_accept - _t0_eta_sampling_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::eta_sampling_accept", _ns_eta_sampling_accept, _acc_eta_sampling_accept)
    var _acc_typical_sampling_accept: Float64 = 0.0
    var _t0_typical_sampling_accept = perf_counter_ns()
    for _ in range(N):
        _acc_typical_sampling_accept += typical_sampling_accept(0.5, 0.5, 0.5)
    var _t1_typical_sampling_accept = perf_counter_ns()
    var _ns_typical_sampling_accept = Float64(_t1_typical_sampling_accept - _t0_typical_sampling_accept) / Float64(N)
    print("MOJO_TIMING generation_loop::typical_sampling_accept", _ns_typical_sampling_accept, _acc_typical_sampling_accept)
