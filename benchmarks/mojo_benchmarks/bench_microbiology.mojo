"""bench_microbiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from microbiology import exponential_growth, doubling_time, monod_growth_rate, bacterial_generation_time, colony_forming_units, minimum_inhibitory_conc, biofilm_formation_index, inactivation_first_order, d_value, z_value
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

    var _acc_exponential_growth: Float64 = 0.0
    var _t0_exponential_growth = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_growth += exponential_growth(0.5, 0.5, 0.5)
    var _t1_exponential_growth = perf_counter_ns()
    var _ns_exponential_growth = Float64(_t1_exponential_growth - _t0_exponential_growth) / Float64(N)
    print("MOJO_TIMING microbiology::exponential_growth", _ns_exponential_growth, _acc_exponential_growth)
    var _result_exponential_growth = exponential_growth(0.5, 0.5, 0.5)
    var _summary_exponential_growth = _summary_float64(_result_exponential_growth)
    print("MOJO_RESULT microbiology::exponential_growth", _summary_exponential_growth)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING microbiology::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _result_doubling_time = doubling_time(0.5)
    var _summary_doubling_time = _summary_float64(_result_doubling_time)
    print("MOJO_RESULT microbiology::doubling_time", _summary_doubling_time)
    var _acc_monod_growth_rate: Float64 = 0.0
    var _t0_monod_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_monod_growth_rate += monod_growth_rate(0.5, 0.5, 0.5)
    var _t1_monod_growth_rate = perf_counter_ns()
    var _ns_monod_growth_rate = Float64(_t1_monod_growth_rate - _t0_monod_growth_rate) / Float64(N)
    print("MOJO_TIMING microbiology::monod_growth_rate", _ns_monod_growth_rate, _acc_monod_growth_rate)
    var _result_monod_growth_rate = monod_growth_rate(0.5, 0.5, 0.5)
    var _summary_monod_growth_rate = _summary_float64(_result_monod_growth_rate)
    print("MOJO_RESULT microbiology::monod_growth_rate", _summary_monod_growth_rate)
    var _acc_bacterial_generation_time: Float64 = 0.0
    var _t0_bacterial_generation_time = perf_counter_ns()
    for _ in range(N):
        _acc_bacterial_generation_time += bacterial_generation_time(0.5, 0.5, 0.5)
    var _t1_bacterial_generation_time = perf_counter_ns()
    var _ns_bacterial_generation_time = Float64(_t1_bacterial_generation_time - _t0_bacterial_generation_time) / Float64(N)
    print("MOJO_TIMING microbiology::bacterial_generation_time", _ns_bacterial_generation_time, _acc_bacterial_generation_time)
    var _result_bacterial_generation_time = bacterial_generation_time(0.5, 0.5, 0.5)
    var _summary_bacterial_generation_time = _summary_float64(_result_bacterial_generation_time)
    print("MOJO_RESULT microbiology::bacterial_generation_time", _summary_bacterial_generation_time)
    var _acc_colony_forming_units: Float64 = 0.0
    var _t0_colony_forming_units = perf_counter_ns()
    for _ in range(N):
        _acc_colony_forming_units += colony_forming_units(0.5, 0.5, 0.5)
    var _t1_colony_forming_units = perf_counter_ns()
    var _ns_colony_forming_units = Float64(_t1_colony_forming_units - _t0_colony_forming_units) / Float64(N)
    print("MOJO_TIMING microbiology::colony_forming_units", _ns_colony_forming_units, _acc_colony_forming_units)
    var _result_colony_forming_units = colony_forming_units(0.5, 0.5, 0.5)
    var _summary_colony_forming_units = _summary_float64(_result_colony_forming_units)
    print("MOJO_RESULT microbiology::colony_forming_units", _summary_colony_forming_units)
    var _acc_minimum_inhibitory_conc: Float64 = 0.0
    var _t0_minimum_inhibitory_conc = perf_counter_ns()
    for _ in range(N):
        _acc_minimum_inhibitory_conc += minimum_inhibitory_conc(0.5, 0.5)
    var _t1_minimum_inhibitory_conc = perf_counter_ns()
    var _ns_minimum_inhibitory_conc = Float64(_t1_minimum_inhibitory_conc - _t0_minimum_inhibitory_conc) / Float64(N)
    print("MOJO_TIMING microbiology::minimum_inhibitory_conc", _ns_minimum_inhibitory_conc, _acc_minimum_inhibitory_conc)
    var _result_minimum_inhibitory_conc = minimum_inhibitory_conc(0.5, 0.5)
    var _summary_minimum_inhibitory_conc = _summary_float64(_result_minimum_inhibitory_conc)
    print("MOJO_RESULT microbiology::minimum_inhibitory_conc", _summary_minimum_inhibitory_conc)
    var _acc_biofilm_formation_index: Float64 = 0.0
    var _t0_biofilm_formation_index = perf_counter_ns()
    for _ in range(N):
        _acc_biofilm_formation_index += biofilm_formation_index(0.5, 0.5)
    var _t1_biofilm_formation_index = perf_counter_ns()
    var _ns_biofilm_formation_index = Float64(_t1_biofilm_formation_index - _t0_biofilm_formation_index) / Float64(N)
    print("MOJO_TIMING microbiology::biofilm_formation_index", _ns_biofilm_formation_index, _acc_biofilm_formation_index)
    var _result_biofilm_formation_index = biofilm_formation_index(0.5, 0.5)
    var _summary_biofilm_formation_index = _summary_float64(_result_biofilm_formation_index)
    print("MOJO_RESULT microbiology::biofilm_formation_index", _summary_biofilm_formation_index)
    var _acc_inactivation_first_order: Float64 = 0.0
    var _t0_inactivation_first_order = perf_counter_ns()
    for _ in range(N):
        _acc_inactivation_first_order += inactivation_first_order(0.5, 0.5, 0.5)
    var _t1_inactivation_first_order = perf_counter_ns()
    var _ns_inactivation_first_order = Float64(_t1_inactivation_first_order - _t0_inactivation_first_order) / Float64(N)
    print("MOJO_TIMING microbiology::inactivation_first_order", _ns_inactivation_first_order, _acc_inactivation_first_order)
    var _result_inactivation_first_order = inactivation_first_order(0.5, 0.5, 0.5)
    var _summary_inactivation_first_order = _summary_float64(_result_inactivation_first_order)
    print("MOJO_RESULT microbiology::inactivation_first_order", _summary_inactivation_first_order)
    var _acc_d_value: Float64 = 0.0
    var _t0_d_value = perf_counter_ns()
    for _ in range(N):
        _acc_d_value += d_value(0.5)
    var _t1_d_value = perf_counter_ns()
    var _ns_d_value = Float64(_t1_d_value - _t0_d_value) / Float64(N)
    print("MOJO_TIMING microbiology::d_value", _ns_d_value, _acc_d_value)
    var _result_d_value = d_value(0.5)
    var _summary_d_value = _summary_float64(_result_d_value)
    print("MOJO_RESULT microbiology::d_value", _summary_d_value)
    var _acc_z_value: Float64 = 0.0
    var _t0_z_value = perf_counter_ns()
    for _ in range(N):
        _acc_z_value += z_value(0.5, 0.5, 0.5, 0.5)
    var _t1_z_value = perf_counter_ns()
    var _ns_z_value = Float64(_t1_z_value - _t0_z_value) / Float64(N)
    print("MOJO_TIMING microbiology::z_value", _ns_z_value, _acc_z_value)
    var _result_z_value = z_value(0.5, 0.5, 0.5, 0.5)
    var _summary_z_value = _summary_float64(_result_z_value)
    print("MOJO_RESULT microbiology::z_value", _summary_z_value)
