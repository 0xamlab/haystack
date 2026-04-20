"""bench_mining.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mining import ore_grade, strip_ratio, recovery_rate, mill_throughput, bond_work_index_energy, cut_off_grade, dilution_factor, net_smelter_return, reserve_life, powder_factor, ventilation_quantity, subsidence_factor
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

    var _acc_ore_grade: Float64 = 0.0
    var _t0_ore_grade = perf_counter_ns()
    for _ in range(N):
        _acc_ore_grade += ore_grade(0.5, 0.5)
    var _t1_ore_grade = perf_counter_ns()
    var _ns_ore_grade = Float64(_t1_ore_grade - _t0_ore_grade) / Float64(N)
    print("MOJO_TIMING mining::ore_grade", _ns_ore_grade, _acc_ore_grade)
    var _acc_strip_ratio: Float64 = 0.0
    var _t0_strip_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_strip_ratio += strip_ratio(0.5, 0.5)
    var _t1_strip_ratio = perf_counter_ns()
    var _ns_strip_ratio = Float64(_t1_strip_ratio - _t0_strip_ratio) / Float64(N)
    print("MOJO_TIMING mining::strip_ratio", _ns_strip_ratio, _acc_strip_ratio)
    var _acc_recovery_rate: Float64 = 0.0
    var _t0_recovery_rate = perf_counter_ns()
    for _ in range(N):
        _acc_recovery_rate += recovery_rate(0.5, 0.5)
    var _t1_recovery_rate = perf_counter_ns()
    var _ns_recovery_rate = Float64(_t1_recovery_rate - _t0_recovery_rate) / Float64(N)
    print("MOJO_TIMING mining::recovery_rate", _ns_recovery_rate, _acc_recovery_rate)
    var _acc_mill_throughput: Float64 = 0.0
    var _t0_mill_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_mill_throughput += mill_throughput(0.5, 0.5)
    var _t1_mill_throughput = perf_counter_ns()
    var _ns_mill_throughput = Float64(_t1_mill_throughput - _t0_mill_throughput) / Float64(N)
    print("MOJO_TIMING mining::mill_throughput", _ns_mill_throughput, _acc_mill_throughput)
    var _acc_bond_work_index_energy: Float64 = 0.0
    var _t0_bond_work_index_energy = perf_counter_ns()
    for _ in range(N):
        _acc_bond_work_index_energy += bond_work_index_energy(0.5, 0.5, 0.5)
    var _t1_bond_work_index_energy = perf_counter_ns()
    var _ns_bond_work_index_energy = Float64(_t1_bond_work_index_energy - _t0_bond_work_index_energy) / Float64(N)
    print("MOJO_TIMING mining::bond_work_index_energy", _ns_bond_work_index_energy, _acc_bond_work_index_energy)
    var _acc_cut_off_grade: Float64 = 0.0
    var _t0_cut_off_grade = perf_counter_ns()
    for _ in range(N):
        _acc_cut_off_grade += cut_off_grade(0.5, 0.5, 0.5, 0.5)
    var _t1_cut_off_grade = perf_counter_ns()
    var _ns_cut_off_grade = Float64(_t1_cut_off_grade - _t0_cut_off_grade) / Float64(N)
    print("MOJO_TIMING mining::cut_off_grade", _ns_cut_off_grade, _acc_cut_off_grade)
    var _acc_dilution_factor: Float64 = 0.0
    var _t0_dilution_factor = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_factor += dilution_factor(0.5, 0.5)
    var _t1_dilution_factor = perf_counter_ns()
    var _ns_dilution_factor = Float64(_t1_dilution_factor - _t0_dilution_factor) / Float64(N)
    print("MOJO_TIMING mining::dilution_factor", _ns_dilution_factor, _acc_dilution_factor)
    var _acc_net_smelter_return: Float64 = 0.0
    var _t0_net_smelter_return = perf_counter_ns()
    for _ in range(N):
        _acc_net_smelter_return += net_smelter_return(0.5, 0.5, 0.5, 0.5)
    var _t1_net_smelter_return = perf_counter_ns()
    var _ns_net_smelter_return = Float64(_t1_net_smelter_return - _t0_net_smelter_return) / Float64(N)
    print("MOJO_TIMING mining::net_smelter_return", _ns_net_smelter_return, _acc_net_smelter_return)
    var _acc_reserve_life: Float64 = 0.0
    var _t0_reserve_life = perf_counter_ns()
    for _ in range(N):
        _acc_reserve_life += reserve_life(0.5, 0.5)
    var _t1_reserve_life = perf_counter_ns()
    var _ns_reserve_life = Float64(_t1_reserve_life - _t0_reserve_life) / Float64(N)
    print("MOJO_TIMING mining::reserve_life", _ns_reserve_life, _acc_reserve_life)
    var _acc_powder_factor: Float64 = 0.0
    var _t0_powder_factor = perf_counter_ns()
    for _ in range(N):
        _acc_powder_factor += powder_factor(0.5, 0.5)
    var _t1_powder_factor = perf_counter_ns()
    var _ns_powder_factor = Float64(_t1_powder_factor - _t0_powder_factor) / Float64(N)
    print("MOJO_TIMING mining::powder_factor", _ns_powder_factor, _acc_powder_factor)
    var _acc_ventilation_quantity: Float64 = 0.0
    var _t0_ventilation_quantity = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_quantity += ventilation_quantity(0.5, 0.5)
    var _t1_ventilation_quantity = perf_counter_ns()
    var _ns_ventilation_quantity = Float64(_t1_ventilation_quantity - _t0_ventilation_quantity) / Float64(N)
    print("MOJO_TIMING mining::ventilation_quantity", _ns_ventilation_quantity, _acc_ventilation_quantity)
    var _acc_subsidence_factor: Float64 = 0.0
    var _t0_subsidence_factor = perf_counter_ns()
    for _ in range(N):
        _acc_subsidence_factor += subsidence_factor(0.5, 0.5)
    var _t1_subsidence_factor = perf_counter_ns()
    var _ns_subsidence_factor = Float64(_t1_subsidence_factor - _t0_subsidence_factor) / Float64(N)
    print("MOJO_TIMING mining::subsidence_factor", _ns_subsidence_factor, _acc_subsidence_factor)
