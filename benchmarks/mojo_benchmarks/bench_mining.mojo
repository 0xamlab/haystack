"""bench_mining.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mining import ore_grade, strip_ratio, recovery_rate, mill_throughput, bond_work_index_energy, cut_off_grade, dilution_factor, net_smelter_return, reserve_life, powder_factor, ventilation_quantity, subsidence_factor
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

    var _acc_ore_grade: Float64 = 0.0
    var _t0_ore_grade = perf_counter_ns()
    for _ in range(N):
        _acc_ore_grade += ore_grade(0.5, 0.5)
    var _t1_ore_grade = perf_counter_ns()
    var _ns_ore_grade = Float64(_t1_ore_grade - _t0_ore_grade) / Float64(N)
    print("MOJO_TIMING mining::ore_grade", _ns_ore_grade, _acc_ore_grade)
    var _result_ore_grade = ore_grade(0.5, 0.5)
    var _summary_ore_grade = _summary_float64(_result_ore_grade)
    print("MOJO_RESULT mining::ore_grade", _summary_ore_grade)
    var _acc_strip_ratio: Float64 = 0.0
    var _t0_strip_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_strip_ratio += strip_ratio(0.5, 0.5)
    var _t1_strip_ratio = perf_counter_ns()
    var _ns_strip_ratio = Float64(_t1_strip_ratio - _t0_strip_ratio) / Float64(N)
    print("MOJO_TIMING mining::strip_ratio", _ns_strip_ratio, _acc_strip_ratio)
    var _result_strip_ratio = strip_ratio(0.5, 0.5)
    var _summary_strip_ratio = _summary_float64(_result_strip_ratio)
    print("MOJO_RESULT mining::strip_ratio", _summary_strip_ratio)
    var _acc_recovery_rate: Float64 = 0.0
    var _t0_recovery_rate = perf_counter_ns()
    for _ in range(N):
        _acc_recovery_rate += recovery_rate(0.5, 0.5)
    var _t1_recovery_rate = perf_counter_ns()
    var _ns_recovery_rate = Float64(_t1_recovery_rate - _t0_recovery_rate) / Float64(N)
    print("MOJO_TIMING mining::recovery_rate", _ns_recovery_rate, _acc_recovery_rate)
    var _result_recovery_rate = recovery_rate(0.5, 0.5)
    var _summary_recovery_rate = _summary_float64(_result_recovery_rate)
    print("MOJO_RESULT mining::recovery_rate", _summary_recovery_rate)
    var _acc_mill_throughput: Float64 = 0.0
    var _t0_mill_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_mill_throughput += mill_throughput(0.5, 0.5)
    var _t1_mill_throughput = perf_counter_ns()
    var _ns_mill_throughput = Float64(_t1_mill_throughput - _t0_mill_throughput) / Float64(N)
    print("MOJO_TIMING mining::mill_throughput", _ns_mill_throughput, _acc_mill_throughput)
    var _result_mill_throughput = mill_throughput(0.5, 0.5)
    var _summary_mill_throughput = _summary_float64(_result_mill_throughput)
    print("MOJO_RESULT mining::mill_throughput", _summary_mill_throughput)
    var _acc_bond_work_index_energy: Float64 = 0.0
    var _t0_bond_work_index_energy = perf_counter_ns()
    for _ in range(N):
        _acc_bond_work_index_energy += bond_work_index_energy(0.5, 0.5, 0.5)
    var _t1_bond_work_index_energy = perf_counter_ns()
    var _ns_bond_work_index_energy = Float64(_t1_bond_work_index_energy - _t0_bond_work_index_energy) / Float64(N)
    print("MOJO_TIMING mining::bond_work_index_energy", _ns_bond_work_index_energy, _acc_bond_work_index_energy)
    var _result_bond_work_index_energy = bond_work_index_energy(0.5, 0.5, 0.5)
    var _summary_bond_work_index_energy = _summary_float64(_result_bond_work_index_energy)
    print("MOJO_RESULT mining::bond_work_index_energy", _summary_bond_work_index_energy)
    var _acc_cut_off_grade: Float64 = 0.0
    var _t0_cut_off_grade = perf_counter_ns()
    for _ in range(N):
        _acc_cut_off_grade += cut_off_grade(0.5, 0.5, 0.5, 0.5)
    var _t1_cut_off_grade = perf_counter_ns()
    var _ns_cut_off_grade = Float64(_t1_cut_off_grade - _t0_cut_off_grade) / Float64(N)
    print("MOJO_TIMING mining::cut_off_grade", _ns_cut_off_grade, _acc_cut_off_grade)
    var _result_cut_off_grade = cut_off_grade(0.5, 0.5, 0.5, 0.5)
    var _summary_cut_off_grade = _summary_float64(_result_cut_off_grade)
    print("MOJO_RESULT mining::cut_off_grade", _summary_cut_off_grade)
    var _acc_dilution_factor: Float64 = 0.0
    var _t0_dilution_factor = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_factor += dilution_factor(0.5, 0.5)
    var _t1_dilution_factor = perf_counter_ns()
    var _ns_dilution_factor = Float64(_t1_dilution_factor - _t0_dilution_factor) / Float64(N)
    print("MOJO_TIMING mining::dilution_factor", _ns_dilution_factor, _acc_dilution_factor)
    var _result_dilution_factor = dilution_factor(0.5, 0.5)
    var _summary_dilution_factor = _summary_float64(_result_dilution_factor)
    print("MOJO_RESULT mining::dilution_factor", _summary_dilution_factor)
    var _acc_net_smelter_return: Float64 = 0.0
    var _t0_net_smelter_return = perf_counter_ns()
    for _ in range(N):
        _acc_net_smelter_return += net_smelter_return(0.5, 0.5, 0.5, 0.5)
    var _t1_net_smelter_return = perf_counter_ns()
    var _ns_net_smelter_return = Float64(_t1_net_smelter_return - _t0_net_smelter_return) / Float64(N)
    print("MOJO_TIMING mining::net_smelter_return", _ns_net_smelter_return, _acc_net_smelter_return)
    var _result_net_smelter_return = net_smelter_return(0.5, 0.5, 0.5, 0.5)
    var _summary_net_smelter_return = _summary_float64(_result_net_smelter_return)
    print("MOJO_RESULT mining::net_smelter_return", _summary_net_smelter_return)
    var _acc_reserve_life: Float64 = 0.0
    var _t0_reserve_life = perf_counter_ns()
    for _ in range(N):
        _acc_reserve_life += reserve_life(0.5, 0.5)
    var _t1_reserve_life = perf_counter_ns()
    var _ns_reserve_life = Float64(_t1_reserve_life - _t0_reserve_life) / Float64(N)
    print("MOJO_TIMING mining::reserve_life", _ns_reserve_life, _acc_reserve_life)
    var _result_reserve_life = reserve_life(0.5, 0.5)
    var _summary_reserve_life = _summary_float64(_result_reserve_life)
    print("MOJO_RESULT mining::reserve_life", _summary_reserve_life)
    var _acc_powder_factor: Float64 = 0.0
    var _t0_powder_factor = perf_counter_ns()
    for _ in range(N):
        _acc_powder_factor += powder_factor(0.5, 0.5)
    var _t1_powder_factor = perf_counter_ns()
    var _ns_powder_factor = Float64(_t1_powder_factor - _t0_powder_factor) / Float64(N)
    print("MOJO_TIMING mining::powder_factor", _ns_powder_factor, _acc_powder_factor)
    var _result_powder_factor = powder_factor(0.5, 0.5)
    var _summary_powder_factor = _summary_float64(_result_powder_factor)
    print("MOJO_RESULT mining::powder_factor", _summary_powder_factor)
    var _acc_ventilation_quantity: Float64 = 0.0
    var _t0_ventilation_quantity = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_quantity += ventilation_quantity(0.5, 0.5)
    var _t1_ventilation_quantity = perf_counter_ns()
    var _ns_ventilation_quantity = Float64(_t1_ventilation_quantity - _t0_ventilation_quantity) / Float64(N)
    print("MOJO_TIMING mining::ventilation_quantity", _ns_ventilation_quantity, _acc_ventilation_quantity)
    var _result_ventilation_quantity = ventilation_quantity(0.5, 0.5)
    var _summary_ventilation_quantity = _summary_float64(_result_ventilation_quantity)
    print("MOJO_RESULT mining::ventilation_quantity", _summary_ventilation_quantity)
    var _acc_subsidence_factor: Float64 = 0.0
    var _t0_subsidence_factor = perf_counter_ns()
    for _ in range(N):
        _acc_subsidence_factor += subsidence_factor(0.5, 0.5)
    var _t1_subsidence_factor = perf_counter_ns()
    var _ns_subsidence_factor = Float64(_t1_subsidence_factor - _t0_subsidence_factor) / Float64(N)
    print("MOJO_TIMING mining::subsidence_factor", _ns_subsidence_factor, _acc_subsidence_factor)
    var _result_subsidence_factor = subsidence_factor(0.5, 0.5)
    var _summary_subsidence_factor = _summary_float64(_result_subsidence_factor)
    print("MOJO_RESULT mining::subsidence_factor", _summary_subsidence_factor)
