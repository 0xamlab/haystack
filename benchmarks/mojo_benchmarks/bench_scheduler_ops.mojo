"""bench_scheduler_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scheduler_ops import priority_fair_score, weighted_fair_queue_credit, backpressure_load_factor, token_bucket_tokens, rate_limiter_wait_time, work_stealing_threshold, request_timeout_score, pipeline_stage_utilization, latency_sla_headroom, exponential_backoff_delay
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

    var _acc_priority_fair_score: Float64 = 0.0
    var _t0_priority_fair_score = perf_counter_ns()
    for _ in range(N):
        _acc_priority_fair_score += priority_fair_score(0.5, 0.5, 0.5)
    var _t1_priority_fair_score = perf_counter_ns()
    var _ns_priority_fair_score = Float64(_t1_priority_fair_score - _t0_priority_fair_score) / Float64(N)
    print("MOJO_TIMING scheduler_ops::priority_fair_score", _ns_priority_fair_score, _acc_priority_fair_score)
    var _acc_weighted_fair_queue_credit: Float64 = 0.0
    var _t0_weighted_fair_queue_credit = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_fair_queue_credit += weighted_fair_queue_credit(0.5, 0.5, 0.5)
    var _t1_weighted_fair_queue_credit = perf_counter_ns()
    var _ns_weighted_fair_queue_credit = Float64(_t1_weighted_fair_queue_credit - _t0_weighted_fair_queue_credit) / Float64(N)
    print("MOJO_TIMING scheduler_ops::weighted_fair_queue_credit", _ns_weighted_fair_queue_credit, _acc_weighted_fair_queue_credit)
    var _acc_backpressure_load_factor: Float64 = 0.0
    var _t0_backpressure_load_factor = perf_counter_ns()
    for _ in range(N):
        _acc_backpressure_load_factor += backpressure_load_factor(0.5, 0.5)
    var _t1_backpressure_load_factor = perf_counter_ns()
    var _ns_backpressure_load_factor = Float64(_t1_backpressure_load_factor - _t0_backpressure_load_factor) / Float64(N)
    print("MOJO_TIMING scheduler_ops::backpressure_load_factor", _ns_backpressure_load_factor, _acc_backpressure_load_factor)
    var _acc_token_bucket_tokens: Float64 = 0.0
    var _t0_token_bucket_tokens = perf_counter_ns()
    for _ in range(N):
        _acc_token_bucket_tokens += token_bucket_tokens(0.5, 0.5, 0.5, 0.5)
    var _t1_token_bucket_tokens = perf_counter_ns()
    var _ns_token_bucket_tokens = Float64(_t1_token_bucket_tokens - _t0_token_bucket_tokens) / Float64(N)
    print("MOJO_TIMING scheduler_ops::token_bucket_tokens", _ns_token_bucket_tokens, _acc_token_bucket_tokens)
    var _acc_rate_limiter_wait_time: Float64 = 0.0
    var _t0_rate_limiter_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_rate_limiter_wait_time += rate_limiter_wait_time(0.5, 0.5, 0.5)
    var _t1_rate_limiter_wait_time = perf_counter_ns()
    var _ns_rate_limiter_wait_time = Float64(_t1_rate_limiter_wait_time - _t0_rate_limiter_wait_time) / Float64(N)
    print("MOJO_TIMING scheduler_ops::rate_limiter_wait_time", _ns_rate_limiter_wait_time, _acc_rate_limiter_wait_time)
    var _acc_work_stealing_threshold: Float64 = 0.0
    var _t0_work_stealing_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_work_stealing_threshold += work_stealing_threshold(0.5, 0.5, 0.5)
    var _t1_work_stealing_threshold = perf_counter_ns()
    var _ns_work_stealing_threshold = Float64(_t1_work_stealing_threshold - _t0_work_stealing_threshold) / Float64(N)
    print("MOJO_TIMING scheduler_ops::work_stealing_threshold", _ns_work_stealing_threshold, _acc_work_stealing_threshold)
    var _acc_request_timeout_score: Float64 = 0.0
    var _t0_request_timeout_score = perf_counter_ns()
    for _ in range(N):
        _acc_request_timeout_score += request_timeout_score(0.5, 0.5, 0.5)
    var _t1_request_timeout_score = perf_counter_ns()
    var _ns_request_timeout_score = Float64(_t1_request_timeout_score - _t0_request_timeout_score) / Float64(N)
    print("MOJO_TIMING scheduler_ops::request_timeout_score", _ns_request_timeout_score, _acc_request_timeout_score)
    var _acc_pipeline_stage_utilization: Float64 = 0.0
    var _t0_pipeline_stage_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_stage_utilization += pipeline_stage_utilization(0.5, 0.5)
    var _t1_pipeline_stage_utilization = perf_counter_ns()
    var _ns_pipeline_stage_utilization = Float64(_t1_pipeline_stage_utilization - _t0_pipeline_stage_utilization) / Float64(N)
    print("MOJO_TIMING scheduler_ops::pipeline_stage_utilization", _ns_pipeline_stage_utilization, _acc_pipeline_stage_utilization)
    var _acc_latency_sla_headroom: Float64 = 0.0
    var _t0_latency_sla_headroom = perf_counter_ns()
    for _ in range(N):
        _acc_latency_sla_headroom += latency_sla_headroom(0.5, 0.5, 0.5, 0.5)
    var _t1_latency_sla_headroom = perf_counter_ns()
    var _ns_latency_sla_headroom = Float64(_t1_latency_sla_headroom - _t0_latency_sla_headroom) / Float64(N)
    print("MOJO_TIMING scheduler_ops::latency_sla_headroom", _ns_latency_sla_headroom, _acc_latency_sla_headroom)
    var _acc_exponential_backoff_delay: Float64 = 0.0
    var _t0_exponential_backoff_delay = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_backoff_delay += exponential_backoff_delay(0.5, 0.5, 0.5, 0.5)
    var _t1_exponential_backoff_delay = perf_counter_ns()
    var _ns_exponential_backoff_delay = Float64(_t1_exponential_backoff_delay - _t0_exponential_backoff_delay) / Float64(N)
    print("MOJO_TIMING scheduler_ops::exponential_backoff_delay", _ns_exponential_backoff_delay, _acc_exponential_backoff_delay)
