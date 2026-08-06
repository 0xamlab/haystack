"""bench_reliability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from reliability import exponential_reliability, exponential_failure_rate, weibull_reliability, weibull_failure_rate, mtbf, availability, series_reliability, parallel_reliability, k_of_n_reliability, bathtub_rate, mission_reliability
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_exponential_reliability: Float64 = 0.0
    var _t0_exponential_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_reliability += exponential_reliability(0.5, 0.5)
    var _t1_exponential_reliability = perf_counter_ns()
    var _ns_exponential_reliability = Float64(_t1_exponential_reliability - _t0_exponential_reliability) / Float64(N)
    print("MOJO_TIMING reliability::exponential_reliability", _ns_exponential_reliability, _acc_exponential_reliability)
    var _result_exponential_reliability = exponential_reliability(0.5, 0.5)
    var _summary_exponential_reliability = _summary_float64(_result_exponential_reliability)
    print("MOJO_RESULT reliability::exponential_reliability", _summary_exponential_reliability)
    var _acc_exponential_failure_rate: Float64 = 0.0
    var _t0_exponential_failure_rate = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_failure_rate += exponential_failure_rate(0.5)
    var _t1_exponential_failure_rate = perf_counter_ns()
    var _ns_exponential_failure_rate = Float64(_t1_exponential_failure_rate - _t0_exponential_failure_rate) / Float64(N)
    print("MOJO_TIMING reliability::exponential_failure_rate", _ns_exponential_failure_rate, _acc_exponential_failure_rate)
    var _result_exponential_failure_rate = exponential_failure_rate(0.5)
    var _summary_exponential_failure_rate = _summary_float64(_result_exponential_failure_rate)
    print("MOJO_RESULT reliability::exponential_failure_rate", _summary_exponential_failure_rate)
    var _acc_weibull_reliability: Float64 = 0.0
    var _t0_weibull_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_reliability += weibull_reliability(0.5, 0.5, 0.5)
    var _t1_weibull_reliability = perf_counter_ns()
    var _ns_weibull_reliability = Float64(_t1_weibull_reliability - _t0_weibull_reliability) / Float64(N)
    print("MOJO_TIMING reliability::weibull_reliability", _ns_weibull_reliability, _acc_weibull_reliability)
    var _result_weibull_reliability = weibull_reliability(0.5, 0.5, 0.5)
    var _summary_weibull_reliability = _summary_float64(_result_weibull_reliability)
    print("MOJO_RESULT reliability::weibull_reliability", _summary_weibull_reliability)
    var _acc_weibull_failure_rate: Float64 = 0.0
    var _t0_weibull_failure_rate = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_failure_rate += weibull_failure_rate(0.5, 0.5, 0.5)
    var _t1_weibull_failure_rate = perf_counter_ns()
    var _ns_weibull_failure_rate = Float64(_t1_weibull_failure_rate - _t0_weibull_failure_rate) / Float64(N)
    print("MOJO_TIMING reliability::weibull_failure_rate", _ns_weibull_failure_rate, _acc_weibull_failure_rate)
    var _result_weibull_failure_rate = weibull_failure_rate(0.5, 0.5, 0.5)
    var _summary_weibull_failure_rate = _summary_float64(_result_weibull_failure_rate)
    print("MOJO_RESULT reliability::weibull_failure_rate", _summary_weibull_failure_rate)
    var _acc_mtbf: Float64 = 0.0
    var _t0_mtbf = perf_counter_ns()
    for _ in range(N):
        _acc_mtbf += mtbf(0.5)
    var _t1_mtbf = perf_counter_ns()
    var _ns_mtbf = Float64(_t1_mtbf - _t0_mtbf) / Float64(N)
    print("MOJO_TIMING reliability::mtbf", _ns_mtbf, _acc_mtbf)
    var _result_mtbf = mtbf(0.5)
    var _summary_mtbf = _summary_float64(_result_mtbf)
    print("MOJO_RESULT reliability::mtbf", _summary_mtbf)
    var _acc_availability: Float64 = 0.0
    var _t0_availability = perf_counter_ns()
    for _ in range(N):
        _acc_availability += availability(0.5, 0.5)
    var _t1_availability = perf_counter_ns()
    var _ns_availability = Float64(_t1_availability - _t0_availability) / Float64(N)
    print("MOJO_TIMING reliability::availability", _ns_availability, _acc_availability)
    var _result_availability = availability(0.5, 0.5)
    var _summary_availability = _summary_float64(_result_availability)
    print("MOJO_RESULT reliability::availability", _summary_availability)
    var _acc_series_reliability: Float64 = 0.0
    var _t0_series_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_series_reliability += series_reliability(_lf5)
    var _t1_series_reliability = perf_counter_ns()
    var _ns_series_reliability = Float64(_t1_series_reliability - _t0_series_reliability) / Float64(N)
    print("MOJO_TIMING reliability::series_reliability", _ns_series_reliability, _acc_series_reliability)
    var _result_series_reliability = series_reliability(_lf5)
    var _summary_series_reliability = _summary_float64(_result_series_reliability)
    print("MOJO_RESULT reliability::series_reliability", _summary_series_reliability)
    var _acc_parallel_reliability: Float64 = 0.0
    var _t0_parallel_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_reliability += parallel_reliability(_lf5)
    var _t1_parallel_reliability = perf_counter_ns()
    var _ns_parallel_reliability = Float64(_t1_parallel_reliability - _t0_parallel_reliability) / Float64(N)
    print("MOJO_TIMING reliability::parallel_reliability", _ns_parallel_reliability, _acc_parallel_reliability)
    var _result_parallel_reliability = parallel_reliability(_lf5)
    var _summary_parallel_reliability = _summary_float64(_result_parallel_reliability)
    print("MOJO_RESULT reliability::parallel_reliability", _summary_parallel_reliability)
    var _acc_k_of_n_reliability: Float64 = 0.0
    var _t0_k_of_n_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_k_of_n_reliability += k_of_n_reliability(5, 5, 0.5)
    var _t1_k_of_n_reliability = perf_counter_ns()
    var _ns_k_of_n_reliability = Float64(_t1_k_of_n_reliability - _t0_k_of_n_reliability) / Float64(N)
    print("MOJO_TIMING reliability::k_of_n_reliability", _ns_k_of_n_reliability, _acc_k_of_n_reliability)
    var _result_k_of_n_reliability = k_of_n_reliability(5, 5, 0.5)
    var _summary_k_of_n_reliability = _summary_float64(_result_k_of_n_reliability)
    print("MOJO_RESULT reliability::k_of_n_reliability", _summary_k_of_n_reliability)
    var _acc_bathtub_rate: Float64 = 0.0
    var _t0_bathtub_rate = perf_counter_ns()
    for _ in range(N):
        _acc_bathtub_rate += bathtub_rate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bathtub_rate = perf_counter_ns()
    var _ns_bathtub_rate = Float64(_t1_bathtub_rate - _t0_bathtub_rate) / Float64(N)
    print("MOJO_TIMING reliability::bathtub_rate", _ns_bathtub_rate, _acc_bathtub_rate)
    var _result_bathtub_rate = bathtub_rate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_bathtub_rate = _summary_float64(_result_bathtub_rate)
    print("MOJO_RESULT reliability::bathtub_rate", _summary_bathtub_rate)
    var _acc_mission_reliability: Float64 = 0.0
    var _t0_mission_reliability = perf_counter_ns()
    for _ in range(N):
        _acc_mission_reliability += mission_reliability(0.5, 0.5)
    var _t1_mission_reliability = perf_counter_ns()
    var _ns_mission_reliability = Float64(_t1_mission_reliability - _t0_mission_reliability) / Float64(N)
    print("MOJO_TIMING reliability::mission_reliability", _ns_mission_reliability, _acc_mission_reliability)
    var _result_mission_reliability = mission_reliability(0.5, 0.5)
    var _summary_mission_reliability = _summary_float64(_result_mission_reliability)
    print("MOJO_RESULT reliability::mission_reliability", _summary_mission_reliability)
