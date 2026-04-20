"""bench_survival.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from survival import kaplan_meier, nelson_aalen, log_rank_statistic, hazard_rate, life_table
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

    var _acc_kaplan_meier: Float64 = 0.0
    var _t0_kaplan_meier = perf_counter_ns()
    for _ in range(N):
        var _r_kaplan_meier = kaplan_meier(_lf5, _lb5)
        _acc_kaplan_meier += Float64(len(_r_kaplan_meier))
    var _t1_kaplan_meier = perf_counter_ns()
    var _ns_kaplan_meier = Float64(_t1_kaplan_meier - _t0_kaplan_meier) / Float64(N)
    print("MOJO_TIMING survival::kaplan_meier", _ns_kaplan_meier, _acc_kaplan_meier)
    var _acc_nelson_aalen: Float64 = 0.0
    var _t0_nelson_aalen = perf_counter_ns()
    for _ in range(N):
        var _r_nelson_aalen = nelson_aalen(_lf5, _lb5)
        _acc_nelson_aalen += Float64(len(_r_nelson_aalen))
    var _t1_nelson_aalen = perf_counter_ns()
    var _ns_nelson_aalen = Float64(_t1_nelson_aalen - _t0_nelson_aalen) / Float64(N)
    print("MOJO_TIMING survival::nelson_aalen", _ns_nelson_aalen, _acc_nelson_aalen)
    var _acc_log_rank_statistic: Float64 = 0.0
    var _t0_log_rank_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_log_rank_statistic += log_rank_statistic(_lf5, _lb5, _lf5, _lb5)
    var _t1_log_rank_statistic = perf_counter_ns()
    var _ns_log_rank_statistic = Float64(_t1_log_rank_statistic - _t0_log_rank_statistic) / Float64(N)
    print("MOJO_TIMING survival::log_rank_statistic", _ns_log_rank_statistic, _acc_log_rank_statistic)
    var _acc_hazard_rate: Float64 = 0.0
    var _t0_hazard_rate = perf_counter_ns()
    for _ in range(N):
        var _r_hazard_rate = hazard_rate(_lf5, _lb5, 0.5)
        _acc_hazard_rate += Float64(len(_r_hazard_rate))
    var _t1_hazard_rate = perf_counter_ns()
    var _ns_hazard_rate = Float64(_t1_hazard_rate - _t0_hazard_rate) / Float64(N)
    print("MOJO_TIMING survival::hazard_rate", _ns_hazard_rate, _acc_hazard_rate)
    var _acc_life_table: Float64 = 0.0
    var _t0_life_table = perf_counter_ns()
    for _ in range(N):
        var _r_life_table = life_table(_lf5, _lb5, _lf5)
        _acc_life_table += Float64(len(_r_life_table))
    var _t1_life_table = perf_counter_ns()
    var _ns_life_table = Float64(_t1_life_table - _t0_life_table) / Float64(N)
    print("MOJO_TIMING survival::life_table", _ns_life_table, _acc_life_table)
