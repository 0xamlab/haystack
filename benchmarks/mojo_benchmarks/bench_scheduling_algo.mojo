"""bench_scheduling_algo.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scheduling_algo import fcfs, sjf, priority_scheduling, round_robin, avg_wait_time, avg_turnaround, throughput, cpu_utilization, gantt_chart
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

    var _acc_fcfs: Float64 = 0.0
    var _t0_fcfs = perf_counter_ns()
    for _ in range(N):
        var _r_fcfs = fcfs([[0,3,1],[1,5,2],[2,2,3]])
        _acc_fcfs += Float64(len(_r_fcfs))
    var _t1_fcfs = perf_counter_ns()
    var _ns_fcfs = Float64(_t1_fcfs - _t0_fcfs) / Float64(N)
    print("MOJO_TIMING scheduling_algo::fcfs", _ns_fcfs, _acc_fcfs)
    var _acc_sjf: Float64 = 0.0
    var _t0_sjf = perf_counter_ns()
    for _ in range(N):
        var _r_sjf = sjf([[0,3,1],[1,5,2],[2,2,3]])
        _acc_sjf += Float64(len(_r_sjf))
    var _t1_sjf = perf_counter_ns()
    var _ns_sjf = Float64(_t1_sjf - _t0_sjf) / Float64(N)
    print("MOJO_TIMING scheduling_algo::sjf", _ns_sjf, _acc_sjf)
    var _acc_priority_scheduling: Float64 = 0.0
    var _t0_priority_scheduling = perf_counter_ns()
    for _ in range(N):
        var _r_priority_scheduling = priority_scheduling([[0,3,1],[1,5,2],[2,2,3]])
        _acc_priority_scheduling += Float64(len(_r_priority_scheduling))
    var _t1_priority_scheduling = perf_counter_ns()
    var _ns_priority_scheduling = Float64(_t1_priority_scheduling - _t0_priority_scheduling) / Float64(N)
    print("MOJO_TIMING scheduling_algo::priority_scheduling", _ns_priority_scheduling, _acc_priority_scheduling)
    var _acc_round_robin: Float64 = 0.0
    var _t0_round_robin = perf_counter_ns()
    for _ in range(N):
        var _r_round_robin = round_robin([[0,3,1],[1,5,2],[2,2,3]], 2)
        _acc_round_robin += Float64(len(_r_round_robin))
    var _t1_round_robin = perf_counter_ns()
    var _ns_round_robin = Float64(_t1_round_robin - _t0_round_robin) / Float64(N)
    print("MOJO_TIMING scheduling_algo::round_robin", _ns_round_robin, _acc_round_robin)
    var _acc_avg_wait_time: Float64 = 0.0
    var _t0_avg_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_avg_wait_time += avg_wait_time([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _t1_avg_wait_time = perf_counter_ns()
    var _ns_avg_wait_time = Float64(_t1_avg_wait_time - _t0_avg_wait_time) / Float64(N)
    print("MOJO_TIMING scheduling_algo::avg_wait_time", _ns_avg_wait_time, _acc_avg_wait_time)
    var _acc_avg_turnaround: Float64 = 0.0
    var _t0_avg_turnaround = perf_counter_ns()
    for _ in range(N):
        _acc_avg_turnaround += avg_turnaround([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
    var _t1_avg_turnaround = perf_counter_ns()
    var _ns_avg_turnaround = Float64(_t1_avg_turnaround - _t0_avg_turnaround) / Float64(N)
    print("MOJO_TIMING scheduling_algo::avg_turnaround", _ns_avg_turnaround, _acc_avg_turnaround)
    var _acc_throughput: Float64 = 0.0
    var _t0_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_throughput += throughput([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _t1_throughput = perf_counter_ns()
    var _ns_throughput = Float64(_t1_throughput - _t0_throughput) / Float64(N)
    print("MOJO_TIMING scheduling_algo::throughput", _ns_throughput, _acc_throughput)
    var _acc_cpu_utilization: Float64 = 0.0
    var _t0_cpu_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_cpu_utilization += cpu_utilization([[0,0,3,1],[1,3,8,2],[2,8,10,1]], 10)
    var _t1_cpu_utilization = perf_counter_ns()
    var _ns_cpu_utilization = Float64(_t1_cpu_utilization - _t0_cpu_utilization) / Float64(N)
    print("MOJO_TIMING scheduling_algo::cpu_utilization", _ns_cpu_utilization, _acc_cpu_utilization)
    var _acc_gantt_chart: Float64 = 0.0
    var _t0_gantt_chart = perf_counter_ns()
    for _ in range(N):
        var _r_gantt_chart = gantt_chart([[0,0,3,1],[1,3,8,2],[2,8,10,1]])
        _acc_gantt_chart += Float64(len(_r_gantt_chart))
    var _t1_gantt_chart = perf_counter_ns()
    var _ns_gantt_chart = Float64(_t1_gantt_chart - _t0_gantt_chart) / Float64(N)
    print("MOJO_TIMING scheduling_algo::gantt_chart", _ns_gantt_chart, _acc_gantt_chart)
