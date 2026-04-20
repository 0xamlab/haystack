"""bench_reliability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from reliability import exponential_reliability, exponential_failure_rate, weibull_reliability, weibull_failure_rate, mtbf, availability, series_reliability, parallel_reliability, k_of_n_reliability, bathtub_rate, mission_reliability
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

    var _acc_exponential_reliability: Float64 = 0.0
    var _t0_exponential_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_reliability += exponential_reliability(0.5, 0.5)
    var _t1_exponential_reliability = perf_counter_ns()
    var _ns_exponential_reliability = Float64(_t1_exponential_reliability - _t0_exponential_reliability) / Float64(N)
    print("MOJO_TIMING reliability::exponential_reliability", _ns_exponential_reliability, _acc_exponential_reliability)
    var _acc_exponential_failure_rate: Float64 = 0.0
    var _t0_exponential_failure_rate = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_failure_rate += exponential_failure_rate(0.5)
    var _t1_exponential_failure_rate = perf_counter_ns()
    var _ns_exponential_failure_rate = Float64(_t1_exponential_failure_rate - _t0_exponential_failure_rate) / Float64(N)
    print("MOJO_TIMING reliability::exponential_failure_rate", _ns_exponential_failure_rate, _acc_exponential_failure_rate)
    var _acc_weibull_reliability: Float64 = 0.0
    var _t0_weibull_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_reliability += weibull_reliability(0.5, 0.5, 0.5)
    var _t1_weibull_reliability = perf_counter_ns()
    var _ns_weibull_reliability = Float64(_t1_weibull_reliability - _t0_weibull_reliability) / Float64(N)
    print("MOJO_TIMING reliability::weibull_reliability", _ns_weibull_reliability, _acc_weibull_reliability)
    var _acc_weibull_failure_rate: Float64 = 0.0
    var _t0_weibull_failure_rate = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_failure_rate += weibull_failure_rate(0.5, 0.5, 0.5)
    var _t1_weibull_failure_rate = perf_counter_ns()
    var _ns_weibull_failure_rate = Float64(_t1_weibull_failure_rate - _t0_weibull_failure_rate) / Float64(N)
    print("MOJO_TIMING reliability::weibull_failure_rate", _ns_weibull_failure_rate, _acc_weibull_failure_rate)
    var _acc_mtbf: Float64 = 0.0
    var _t0_mtbf = perf_counter_ns()
    for _ in range(N):
        _acc_mtbf += mtbf(0.5)
    var _t1_mtbf = perf_counter_ns()
    var _ns_mtbf = Float64(_t1_mtbf - _t0_mtbf) / Float64(N)
    print("MOJO_TIMING reliability::mtbf", _ns_mtbf, _acc_mtbf)
    var _acc_availability: Float64 = 0.0
    var _t0_availability = perf_counter_ns()
    for _ in range(N):
        _acc_availability += availability(0.5, 0.5)
    var _t1_availability = perf_counter_ns()
    var _ns_availability = Float64(_t1_availability - _t0_availability) / Float64(N)
    print("MOJO_TIMING reliability::availability", _ns_availability, _acc_availability)
    var _acc_series_reliability: Float64 = 0.0
    var _t0_series_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_series_reliability += series_reliability(_lf5)
    var _t1_series_reliability = perf_counter_ns()
    var _ns_series_reliability = Float64(_t1_series_reliability - _t0_series_reliability) / Float64(N)
    print("MOJO_TIMING reliability::series_reliability", _ns_series_reliability, _acc_series_reliability)
    var _acc_parallel_reliability: Float64 = 0.0
    var _t0_parallel_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_reliability += parallel_reliability(_lf5)
    var _t1_parallel_reliability = perf_counter_ns()
    var _ns_parallel_reliability = Float64(_t1_parallel_reliability - _t0_parallel_reliability) / Float64(N)
    print("MOJO_TIMING reliability::parallel_reliability", _ns_parallel_reliability, _acc_parallel_reliability)
    var _acc_k_of_n_reliability: Float64 = 0.0
    var _t0_k_of_n_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_k_of_n_reliability += k_of_n_reliability(5, 5, 0.5)
    var _t1_k_of_n_reliability = perf_counter_ns()
    var _ns_k_of_n_reliability = Float64(_t1_k_of_n_reliability - _t0_k_of_n_reliability) / Float64(N)
    print("MOJO_TIMING reliability::k_of_n_reliability", _ns_k_of_n_reliability, _acc_k_of_n_reliability)
    var _acc_bathtub_rate: Float64 = 0.0
    var _t0_bathtub_rate = perf_counter_ns()
    for _ in range(N):
        _acc_bathtub_rate += bathtub_rate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bathtub_rate = perf_counter_ns()
    var _ns_bathtub_rate = Float64(_t1_bathtub_rate - _t0_bathtub_rate) / Float64(N)
    print("MOJO_TIMING reliability::bathtub_rate", _ns_bathtub_rate, _acc_bathtub_rate)
    var _acc_mission_reliability: Float64 = 0.0
    var _t0_mission_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_mission_reliability += mission_reliability(0.5, 0.5)
    var _t1_mission_reliability = perf_counter_ns()
    var _ns_mission_reliability = Float64(_t1_mission_reliability - _t0_mission_reliability) / Float64(N)
    print("MOJO_TIMING reliability::mission_reliability", _ns_mission_reliability, _acc_mission_reliability)
