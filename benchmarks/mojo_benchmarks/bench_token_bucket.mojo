"""bench_token_bucket.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from token_bucket import tb_create, lb_create, sw_create
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

    var _acc_tb_create: Float64 = 0.0
    var _t0_tb_create = perf_counter_ns()
    for _ in range(N):
        var _r_tb_create = tb_create(0.5, 0.5)
        _acc_tb_create += Float64(_r_tb_create.capacity)
    var _t1_tb_create = perf_counter_ns()
    var _ns_tb_create = Float64(_t1_tb_create - _t0_tb_create) / Float64(N)
    print("MOJO_TIMING token_bucket::tb_create", _ns_tb_create, _acc_tb_create)
    var _acc_lb_create: Float64 = 0.0
    var _t0_lb_create = perf_counter_ns()
    for _ in range(N):
        var _r_lb_create = lb_create(0.5, 0.5)
        _acc_lb_create += Float64(_r_lb_create.capacity)
    var _t1_lb_create = perf_counter_ns()
    var _ns_lb_create = Float64(_t1_lb_create - _t0_lb_create) / Float64(N)
    print("MOJO_TIMING token_bucket::lb_create", _ns_lb_create, _acc_lb_create)
    var _acc_sw_create: Float64 = 0.0
    var _t0_sw_create = perf_counter_ns()
    for _ in range(N):
        var _r_sw_create = sw_create(0.5, 5)
        _acc_sw_create += Float64(_r_sw_create.window_size)
    var _t1_sw_create = perf_counter_ns()
    var _ns_sw_create = Float64(_t1_sw_create - _t0_sw_create) / Float64(N)
    print("MOJO_TIMING token_bucket::sw_create", _ns_sw_create, _acc_sw_create)
