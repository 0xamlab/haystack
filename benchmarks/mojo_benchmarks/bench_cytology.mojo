"""bench_cytology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cytology import cell_volume_sphere, nuclear_cytoplasmic_ratio, membrane_permeability, cell_doubling_time, mitotic_index, cell_viability, apoptosis_rate, phagocytic_index, cell_adhesion_strength, osmotic_fragility
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_cell_volume_sphere: Float64 = 0.0
    var _t0_cell_volume_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_cell_volume_sphere += cell_volume_sphere(0.5)
    var _t1_cell_volume_sphere = perf_counter_ns()
    var _ns_cell_volume_sphere = Float64(_t1_cell_volume_sphere - _t0_cell_volume_sphere) / Float64(N)
    print("MOJO_TIMING cytology::cell_volume_sphere", _ns_cell_volume_sphere, _acc_cell_volume_sphere)
    var _result_cell_volume_sphere = cell_volume_sphere(0.5)
    var _summary_cell_volume_sphere = _summary_float64(_result_cell_volume_sphere)
    print("MOJO_RESULT cytology::cell_volume_sphere", _summary_cell_volume_sphere)
    var _acc_nuclear_cytoplasmic_ratio: Float64 = 0.0
    var _t0_nuclear_cytoplasmic_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_nuclear_cytoplasmic_ratio += nuclear_cytoplasmic_ratio(0.5, 0.5)
    var _t1_nuclear_cytoplasmic_ratio = perf_counter_ns()
    var _ns_nuclear_cytoplasmic_ratio = Float64(_t1_nuclear_cytoplasmic_ratio - _t0_nuclear_cytoplasmic_ratio) / Float64(N)
    print("MOJO_TIMING cytology::nuclear_cytoplasmic_ratio", _ns_nuclear_cytoplasmic_ratio, _acc_nuclear_cytoplasmic_ratio)
    var _result_nuclear_cytoplasmic_ratio = nuclear_cytoplasmic_ratio(0.5, 0.5)
    var _summary_nuclear_cytoplasmic_ratio = _summary_float64(_result_nuclear_cytoplasmic_ratio)
    print("MOJO_RESULT cytology::nuclear_cytoplasmic_ratio", _summary_nuclear_cytoplasmic_ratio)
    var _acc_membrane_permeability: Float64 = 0.0
    var _t0_membrane_permeability = perf_counter_ns()
    for _ in range(N):
        _acc_membrane_permeability += membrane_permeability(0.5, 0.5, 0.5)
    var _t1_membrane_permeability = perf_counter_ns()
    var _ns_membrane_permeability = Float64(_t1_membrane_permeability - _t0_membrane_permeability) / Float64(N)
    print("MOJO_TIMING cytology::membrane_permeability", _ns_membrane_permeability, _acc_membrane_permeability)
    var _result_membrane_permeability = membrane_permeability(0.5, 0.5, 0.5)
    var _summary_membrane_permeability = _summary_float64(_result_membrane_permeability)
    print("MOJO_RESULT cytology::membrane_permeability", _summary_membrane_permeability)
    var _acc_cell_doubling_time: Float64 = 0.0
    var _t0_cell_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_cell_doubling_time += cell_doubling_time(0.5)
    var _t1_cell_doubling_time = perf_counter_ns()
    var _ns_cell_doubling_time = Float64(_t1_cell_doubling_time - _t0_cell_doubling_time) / Float64(N)
    print("MOJO_TIMING cytology::cell_doubling_time", _ns_cell_doubling_time, _acc_cell_doubling_time)
    var _result_cell_doubling_time = cell_doubling_time(0.5)
    var _summary_cell_doubling_time = _summary_float64(_result_cell_doubling_time)
    print("MOJO_RESULT cytology::cell_doubling_time", _summary_cell_doubling_time)
    var _acc_mitotic_index: Float64 = 0.0
    var _t0_mitotic_index = perf_counter_ns()
    for _ in range(N):
        _acc_mitotic_index += mitotic_index(0.5, 0.5)
    var _t1_mitotic_index = perf_counter_ns()
    var _ns_mitotic_index = Float64(_t1_mitotic_index - _t0_mitotic_index) / Float64(N)
    print("MOJO_TIMING cytology::mitotic_index", _ns_mitotic_index, _acc_mitotic_index)
    var _result_mitotic_index = mitotic_index(0.5, 0.5)
    var _summary_mitotic_index = _summary_float64(_result_mitotic_index)
    print("MOJO_RESULT cytology::mitotic_index", _summary_mitotic_index)
    var _acc_cell_viability: Float64 = 0.0
    var _t0_cell_viability = perf_counter_ns()
    for _ in range(N):
        _acc_cell_viability += cell_viability(0.5, 0.5)
    var _t1_cell_viability = perf_counter_ns()
    var _ns_cell_viability = Float64(_t1_cell_viability - _t0_cell_viability) / Float64(N)
    print("MOJO_TIMING cytology::cell_viability", _ns_cell_viability, _acc_cell_viability)
    var _result_cell_viability = cell_viability(0.5, 0.5)
    var _summary_cell_viability = _summary_float64(_result_cell_viability)
    print("MOJO_RESULT cytology::cell_viability", _summary_cell_viability)
    var _acc_apoptosis_rate: Float64 = 0.0
    var _t0_apoptosis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_apoptosis_rate += apoptosis_rate(0.5, 0.5, 0.5)
    var _t1_apoptosis_rate = perf_counter_ns()
    var _ns_apoptosis_rate = Float64(_t1_apoptosis_rate - _t0_apoptosis_rate) / Float64(N)
    print("MOJO_TIMING cytology::apoptosis_rate", _ns_apoptosis_rate, _acc_apoptosis_rate)
    var _result_apoptosis_rate = apoptosis_rate(0.5, 0.5, 0.5)
    var _summary_apoptosis_rate = _summary_float64(_result_apoptosis_rate)
    print("MOJO_RESULT cytology::apoptosis_rate", _summary_apoptosis_rate)
    var _acc_phagocytic_index: Float64 = 0.0
    var _t0_phagocytic_index = perf_counter_ns()
    for _ in range(N):
        _acc_phagocytic_index += phagocytic_index(0.5, 0.5)
    var _t1_phagocytic_index = perf_counter_ns()
    var _ns_phagocytic_index = Float64(_t1_phagocytic_index - _t0_phagocytic_index) / Float64(N)
    print("MOJO_TIMING cytology::phagocytic_index", _ns_phagocytic_index, _acc_phagocytic_index)
    var _result_phagocytic_index = phagocytic_index(0.5, 0.5)
    var _summary_phagocytic_index = _summary_float64(_result_phagocytic_index)
    print("MOJO_RESULT cytology::phagocytic_index", _summary_phagocytic_index)
    var _acc_cell_adhesion_strength: Float64 = 0.0
    var _t0_cell_adhesion_strength = perf_counter_ns()
    for _ in range(N):
        _acc_cell_adhesion_strength += cell_adhesion_strength(0.5, 0.5)
    var _t1_cell_adhesion_strength = perf_counter_ns()
    var _ns_cell_adhesion_strength = Float64(_t1_cell_adhesion_strength - _t0_cell_adhesion_strength) / Float64(N)
    print("MOJO_TIMING cytology::cell_adhesion_strength", _ns_cell_adhesion_strength, _acc_cell_adhesion_strength)
    var _result_cell_adhesion_strength = cell_adhesion_strength(0.5, 0.5)
    var _summary_cell_adhesion_strength = _summary_float64(_result_cell_adhesion_strength)
    print("MOJO_RESULT cytology::cell_adhesion_strength", _summary_cell_adhesion_strength)
    var _acc_osmotic_fragility: Float64 = 0.0
    var _t0_osmotic_fragility = perf_counter_ns()
    for _ in range(N):
        _acc_osmotic_fragility += osmotic_fragility(0.5, 0.5)
    var _t1_osmotic_fragility = perf_counter_ns()
    var _ns_osmotic_fragility = Float64(_t1_osmotic_fragility - _t0_osmotic_fragility) / Float64(N)
    print("MOJO_TIMING cytology::osmotic_fragility", _ns_osmotic_fragility, _acc_osmotic_fragility)
    var _result_osmotic_fragility = osmotic_fragility(0.5, 0.5)
    var _summary_osmotic_fragility = _summary_float64(_result_osmotic_fragility)
    print("MOJO_RESULT cytology::osmotic_fragility", _summary_osmotic_fragility)
