"""bench_queue_ds.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from queue_ds import pq_create, cb_create, CircularBuffer, PriorityQueue
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

    var _keeper_pq_create = List[PriorityQueue]()
    _keeper_pq_create.append(pq_create())
    var _acc_pq_create: Float64 = 0.0
    var _t0_pq_create = perf_counter_ns()
    for _ in range(N):
        _keeper_pq_create[0] = pq_create()
        _acc_pq_create += Float64(len(_keeper_pq_create))
    var _t1_pq_create = perf_counter_ns()
    var _ns_pq_create = Float64(_t1_pq_create - _t0_pq_create) / Float64(N)
    print("MOJO_TIMING queue_ds::pq_create", _ns_pq_create, _acc_pq_create)
    var _keeper_cb_create = List[CircularBuffer]()
    _keeper_cb_create.append(cb_create(5))
    var _acc_cb_create: Float64 = 0.0
    var _t0_cb_create = perf_counter_ns()
    for _ in range(N):
        _keeper_cb_create[0] = cb_create(5)
        _acc_cb_create += Float64(len(_keeper_cb_create))
    var _t1_cb_create = perf_counter_ns()
    var _ns_cb_create = Float64(_t1_cb_create - _t0_cb_create) / Float64(N)
    print("MOJO_TIMING queue_ds::cb_create", _ns_cb_create, _acc_cb_create)
