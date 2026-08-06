"""bench_scheduling_algo.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scheduling_algo import fcfs, sjf, priority_scheduling, round_robin, avg_wait_time, avg_turnaround, throughput, cpu_utilization, gantt_chart
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

    var _acc_fcfs: Float64 = 0.0
    var _t0_fcfs = perf_counter_ns()
    for _ in range(N):
        var _r_fcfs = fcfs([[0,3,1],[1,5,2],[2,2,3]])
        _acc_fcfs += Float64(len(_r_fcfs))
    var _t1_fcfs = perf_counter_ns()
    var _ns_fcfs = Float64(_t1_fcfs - _t0_fcfs) / Float64(N)
    print("MOJO_TIMING scheduling_algo::fcfs", _ns_fcfs, _acc_fcfs)
    var _result_fcfs = fcfs([[0,3,1],[1,5,2],[2,2,3]])
    var _summary_fcfs = _summary_list_list_int(_result_fcfs)
    print("MOJO_RESULT scheduling_algo::fcfs", _summary_fcfs)
    var _acc_sjf: Float64 = 0.0
    var _t0_sjf = perf_counter_ns()
    for _ in range(N):
        var _r_sjf = sjf([[0,3,1],[1,5,2],[2,2,3]])
        _acc_sjf += Float64(len(_r_sjf))
    var _t1_sjf = perf_counter_ns()
    var _ns_sjf = Float64(_t1_sjf - _t0_sjf) / Float64(N)
    print("MOJO_TIMING scheduling_algo::sjf", _ns_sjf, _acc_sjf)
    var _result_sjf = sjf([[0,3,1],[1,5,2],[2,2,3]])
    var _summary_sjf = _summary_list_list_int(_result_sjf)
    print("MOJO_RESULT scheduling_algo::sjf", _summary_sjf)
    var _acc_priority_scheduling: Float64 = 0.0
    var _t0_priority_scheduling = perf_counter_ns()
    for _ in range(N):
        var _r_priority_scheduling = priority_scheduling([[0,3,1],[1,5,2],[2,2,3]])
        _acc_priority_scheduling += Float64(len(_r_priority_scheduling))
    var _t1_priority_scheduling = perf_counter_ns()
    var _ns_priority_scheduling = Float64(_t1_priority_scheduling - _t0_priority_scheduling) / Float64(N)
    print("MOJO_TIMING scheduling_algo::priority_scheduling", _ns_priority_scheduling, _acc_priority_scheduling)
    var _result_priority_scheduling = priority_scheduling([[0,3,1],[1,5,2],[2,2,3]])
    var _summary_priority_scheduling = _summary_list_list_int(_result_priority_scheduling)
    print("MOJO_RESULT scheduling_algo::priority_scheduling", _summary_priority_scheduling)
    var _acc_round_robin: Float64 = 0.0
    var _t0_round_robin = perf_counter_ns()
    for _ in range(N):
        var _r_round_robin = round_robin([[0,3,1],[1,5,2],[2,2,3]], 2)
        _acc_round_robin += Float64(len(_r_round_robin))
    var _t1_round_robin = perf_counter_ns()
    var _ns_round_robin = Float64(_t1_round_robin - _t0_round_robin) / Float64(N)
    print("MOJO_TIMING scheduling_algo::round_robin", _ns_round_robin, _acc_round_robin)
    var _result_round_robin = round_robin([[0,3,1],[1,5,2],[2,2,3]], 2)
    var _summary_round_robin = _summary_list_list_int(_result_round_robin)
    print("MOJO_RESULT scheduling_algo::round_robin", _summary_round_robin)
    var _acc_avg_wait_time: Float64 = 0.0
    var _t0_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_avg_wait_time += avg_wait_time([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _t1_avg_wait_time = perf_counter_ns()
    var _ns_avg_wait_time = Float64(_t1_avg_wait_time - _t0_avg_wait_time) / Float64(N)
    print("MOJO_TIMING scheduling_algo::avg_wait_time", _ns_avg_wait_time, _acc_avg_wait_time)
    var _result_avg_wait_time = avg_wait_time([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _summary_avg_wait_time = _summary_float64(_result_avg_wait_time)
    print("MOJO_RESULT scheduling_algo::avg_wait_time", _summary_avg_wait_time)
    var _acc_avg_turnaround: Float64 = 0.0
    var _t0_avg_turnaround = perf_counter_ns()
    for _ in range(N):
        _acc_avg_turnaround += avg_turnaround([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _t1_avg_turnaround = perf_counter_ns()
    var _ns_avg_turnaround = Float64(_t1_avg_turnaround - _t0_avg_turnaround) / Float64(N)
    print("MOJO_TIMING scheduling_algo::avg_turnaround", _ns_avg_turnaround, _acc_avg_turnaround)
    var _result_avg_turnaround = avg_turnaround([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _summary_avg_turnaround = _summary_float64(_result_avg_turnaround)
    print("MOJO_RESULT scheduling_algo::avg_turnaround", _summary_avg_turnaround)
    var _acc_throughput: Float64 = 0.0
    var _t0_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_throughput += throughput([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _t1_throughput = perf_counter_ns()
    var _ns_throughput = Float64(_t1_throughput - _t0_throughput) / Float64(N)
    print("MOJO_TIMING scheduling_algo::throughput", _ns_throughput, _acc_throughput)
    var _result_throughput = throughput([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _summary_throughput = _summary_float64(_result_throughput)
    print("MOJO_RESULT scheduling_algo::throughput", _summary_throughput)
    var _acc_cpu_utilization: Float64 = 0.0
    var _t0_cpu_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_cpu_utilization += cpu_utilization([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _t1_cpu_utilization = perf_counter_ns()
    var _ns_cpu_utilization = Float64(_t1_cpu_utilization - _t0_cpu_utilization) / Float64(N)
    print("MOJO_TIMING scheduling_algo::cpu_utilization", _ns_cpu_utilization, _acc_cpu_utilization)
    var _result_cpu_utilization = cpu_utilization([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _summary_cpu_utilization = _summary_float64(_result_cpu_utilization)
    print("MOJO_RESULT scheduling_algo::cpu_utilization", _summary_cpu_utilization)
    var _acc_gantt_chart: Float64 = 0.0
    var _t0_gantt_chart = perf_counter_ns()
    for _ in range(N):
        var _r_gantt_chart = gantt_chart([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
        _acc_gantt_chart += Float64(len(_r_gantt_chart))
    var _t1_gantt_chart = perf_counter_ns()
    var _ns_gantt_chart = Float64(_t1_gantt_chart - _t0_gantt_chart) / Float64(N)
    print("MOJO_TIMING scheduling_algo::gantt_chart", _ns_gantt_chart, _acc_gantt_chart)
    var _result_gantt_chart = gantt_chart([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _summary_gantt_chart = _summary_list_int(_result_gantt_chart)
    print("MOJO_RESULT scheduling_algo::gantt_chart", _summary_gantt_chart)
