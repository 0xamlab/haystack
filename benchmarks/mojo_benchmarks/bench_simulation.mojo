"""bench_simulation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from simulation import create_sim, mm1_simulate, SimState
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

    var _keeper_create_sim = List[SimState]()
    _keeper_create_sim.append(create_sim())
    var _acc_create_sim: Float64 = 0.0
    var _t0_create_sim = perf_counter_ns()
    for _ in range(N):
        _keeper_create_sim[0] = create_sim()
        _acc_create_sim += Float64(len(_keeper_create_sim))
    var _t1_create_sim = perf_counter_ns()
    var _ns_create_sim = Float64(_t1_create_sim - _t0_create_sim) / Float64(N)
    print("MOJO_TIMING simulation::create_sim", _ns_create_sim, _acc_create_sim)
    var _acc_mm1_simulate: Float64 = 0.0
    var _t0_mm1_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_mm1_simulate = mm1_simulate(0.5, 0.5, 5)
        _acc_mm1_simulate += Float64(len(_r_mm1_simulate))
    var _t1_mm1_simulate = perf_counter_ns()
    var _ns_mm1_simulate = Float64(_t1_mm1_simulate - _t0_mm1_simulate) / Float64(N)
    print("MOJO_TIMING simulation::mm1_simulate", _ns_mm1_simulate, _acc_mm1_simulate)
