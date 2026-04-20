"""bench_engines_join_detector.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from engines.join_detector import run_join_detect
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

    var _acc_run_join_detect: Float64 = 0.0
    var _t0_run_join_detect = perf_counter_ns()
    for _ in range(N):
        _ = run_join_detect("test")
    var _t1_run_join_detect = perf_counter_ns()
    var _ns_run_join_detect = Float64(_t1_run_join_detect - _t0_run_join_detect) / Float64(N)
    print("MOJO_TIMING engines_join_detector::run_join_detect", _ns_run_join_detect, _acc_run_join_detect)
