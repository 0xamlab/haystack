"""bench_water_chemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from water_chemistry import ph_from_hydrogen_ion, hydrogen_ion_from_ph, water_hardness, alkalinity_as_caco3, langelier_saturation_index, turbidity_ntu_to_sdd, chlorine_demand, dissolved_oxygen_deficit, conductivity_tds, bod_removal
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

    var _acc_ph_from_hydrogen_ion: Float64 = 0.0
    var _t0_ph_from_hydrogen_ion = perf_counter_ns()
    for _ in range(N):
        _acc_ph_from_hydrogen_ion += ph_from_hydrogen_ion(0.5)
    var _t1_ph_from_hydrogen_ion = perf_counter_ns()
    var _ns_ph_from_hydrogen_ion = Float64(_t1_ph_from_hydrogen_ion - _t0_ph_from_hydrogen_ion) / Float64(N)
    print("MOJO_TIMING water_chemistry::ph_from_hydrogen_ion", _ns_ph_from_hydrogen_ion, _acc_ph_from_hydrogen_ion)
    var _result_ph_from_hydrogen_ion = ph_from_hydrogen_ion(0.5)
    var _summary_ph_from_hydrogen_ion = _summary_float64(_result_ph_from_hydrogen_ion)
    print("MOJO_RESULT water_chemistry::ph_from_hydrogen_ion", _summary_ph_from_hydrogen_ion)
    var _acc_hydrogen_ion_from_ph: Float64 = 0.0
    var _t0_hydrogen_ion_from_ph = perf_counter_ns()
    for _ in range(N):
        _acc_hydrogen_ion_from_ph += hydrogen_ion_from_ph(0.5)
    var _t1_hydrogen_ion_from_ph = perf_counter_ns()
    var _ns_hydrogen_ion_from_ph = Float64(_t1_hydrogen_ion_from_ph - _t0_hydrogen_ion_from_ph) / Float64(N)
    print("MOJO_TIMING water_chemistry::hydrogen_ion_from_ph", _ns_hydrogen_ion_from_ph, _acc_hydrogen_ion_from_ph)
    var _result_hydrogen_ion_from_ph = hydrogen_ion_from_ph(0.5)
    var _summary_hydrogen_ion_from_ph = _summary_float64(_result_hydrogen_ion_from_ph)
    print("MOJO_RESULT water_chemistry::hydrogen_ion_from_ph", _summary_hydrogen_ion_from_ph)
    var _acc_water_hardness: Float64 = 0.0
    var _t0_water_hardness = perf_counter_ns()
    for _ in range(N):
        _acc_water_hardness += water_hardness(0.5, 0.5)
    var _t1_water_hardness = perf_counter_ns()
    var _ns_water_hardness = Float64(_t1_water_hardness - _t0_water_hardness) / Float64(N)
    print("MOJO_TIMING water_chemistry::water_hardness", _ns_water_hardness, _acc_water_hardness)
    var _result_water_hardness = water_hardness(0.5, 0.5)
    var _summary_water_hardness = _summary_float64(_result_water_hardness)
    print("MOJO_RESULT water_chemistry::water_hardness", _summary_water_hardness)
    var _acc_alkalinity_as_caco3: Float64 = 0.0
    var _t0_alkalinity_as_caco3 = perf_counter_ns()
    for _ in range(N):
        _acc_alkalinity_as_caco3 += alkalinity_as_caco3(0.5, 0.5, 0.5)
    var _t1_alkalinity_as_caco3 = perf_counter_ns()
    var _ns_alkalinity_as_caco3 = Float64(_t1_alkalinity_as_caco3 - _t0_alkalinity_as_caco3) / Float64(N)
    print("MOJO_TIMING water_chemistry::alkalinity_as_caco3", _ns_alkalinity_as_caco3, _acc_alkalinity_as_caco3)
    var _result_alkalinity_as_caco3 = alkalinity_as_caco3(0.5, 0.5, 0.5)
    var _summary_alkalinity_as_caco3 = _summary_float64(_result_alkalinity_as_caco3)
    print("MOJO_RESULT water_chemistry::alkalinity_as_caco3", _summary_alkalinity_as_caco3)
    var _acc_langelier_saturation_index: Float64 = 0.0
    var _t0_langelier_saturation_index = perf_counter_ns()
    for _ in range(N):
        _acc_langelier_saturation_index += langelier_saturation_index(0.5, 0.5)
    var _t1_langelier_saturation_index = perf_counter_ns()
    var _ns_langelier_saturation_index = Float64(_t1_langelier_saturation_index - _t0_langelier_saturation_index) / Float64(N)
    print("MOJO_TIMING water_chemistry::langelier_saturation_index", _ns_langelier_saturation_index, _acc_langelier_saturation_index)
    var _result_langelier_saturation_index = langelier_saturation_index(0.5, 0.5)
    var _summary_langelier_saturation_index = _summary_float64(_result_langelier_saturation_index)
    print("MOJO_RESULT water_chemistry::langelier_saturation_index", _summary_langelier_saturation_index)
    var _acc_turbidity_ntu_to_sdd: Float64 = 0.0
    var _t0_turbidity_ntu_to_sdd = perf_counter_ns()
    for _ in range(N):
        _acc_turbidity_ntu_to_sdd += turbidity_ntu_to_sdd(0.5)
    var _t1_turbidity_ntu_to_sdd = perf_counter_ns()
    var _ns_turbidity_ntu_to_sdd = Float64(_t1_turbidity_ntu_to_sdd - _t0_turbidity_ntu_to_sdd) / Float64(N)
    print("MOJO_TIMING water_chemistry::turbidity_ntu_to_sdd", _ns_turbidity_ntu_to_sdd, _acc_turbidity_ntu_to_sdd)
    var _result_turbidity_ntu_to_sdd = turbidity_ntu_to_sdd(0.5)
    var _summary_turbidity_ntu_to_sdd = _summary_float64(_result_turbidity_ntu_to_sdd)
    print("MOJO_RESULT water_chemistry::turbidity_ntu_to_sdd", _summary_turbidity_ntu_to_sdd)
    var _acc_chlorine_demand: Float64 = 0.0
    var _t0_chlorine_demand = perf_counter_ns()
    for _ in range(N):
        _acc_chlorine_demand += chlorine_demand(0.5, 0.5)
    var _t1_chlorine_demand = perf_counter_ns()
    var _ns_chlorine_demand = Float64(_t1_chlorine_demand - _t0_chlorine_demand) / Float64(N)
    print("MOJO_TIMING water_chemistry::chlorine_demand", _ns_chlorine_demand, _acc_chlorine_demand)
    var _result_chlorine_demand = chlorine_demand(0.5, 0.5)
    var _summary_chlorine_demand = _summary_float64(_result_chlorine_demand)
    print("MOJO_RESULT water_chemistry::chlorine_demand", _summary_chlorine_demand)
    var _acc_dissolved_oxygen_deficit: Float64 = 0.0
    var _t0_dissolved_oxygen_deficit = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_deficit += dissolved_oxygen_deficit(0.5, 0.5)
    var _t1_dissolved_oxygen_deficit = perf_counter_ns()
    var _ns_dissolved_oxygen_deficit = Float64(_t1_dissolved_oxygen_deficit - _t0_dissolved_oxygen_deficit) / Float64(N)
    print("MOJO_TIMING water_chemistry::dissolved_oxygen_deficit", _ns_dissolved_oxygen_deficit, _acc_dissolved_oxygen_deficit)
    var _result_dissolved_oxygen_deficit = dissolved_oxygen_deficit(0.5, 0.5)
    var _summary_dissolved_oxygen_deficit = _summary_float64(_result_dissolved_oxygen_deficit)
    print("MOJO_RESULT water_chemistry::dissolved_oxygen_deficit", _summary_dissolved_oxygen_deficit)
    var _acc_conductivity_tds: Float64 = 0.0
    var _t0_conductivity_tds = perf_counter_ns()
    for _ in range(N):
        _acc_conductivity_tds += conductivity_tds(0.5, 0.5)
    var _t1_conductivity_tds = perf_counter_ns()
    var _ns_conductivity_tds = Float64(_t1_conductivity_tds - _t0_conductivity_tds) / Float64(N)
    print("MOJO_TIMING water_chemistry::conductivity_tds", _ns_conductivity_tds, _acc_conductivity_tds)
    var _result_conductivity_tds = conductivity_tds(0.5, 0.5)
    var _summary_conductivity_tds = _summary_float64(_result_conductivity_tds)
    print("MOJO_RESULT water_chemistry::conductivity_tds", _summary_conductivity_tds)
    var _acc_bod_removal: Float64 = 0.0
    var _t0_bod_removal = perf_counter_ns()
    for _ in range(N):
        _acc_bod_removal += bod_removal(0.5, 0.5)
    var _t1_bod_removal = perf_counter_ns()
    var _ns_bod_removal = Float64(_t1_bod_removal - _t0_bod_removal) / Float64(N)
    print("MOJO_TIMING water_chemistry::bod_removal", _ns_bod_removal, _acc_bod_removal)
    var _result_bod_removal = bod_removal(0.5, 0.5)
    var _summary_bod_removal = _summary_float64(_result_bod_removal)
    print("MOJO_RESULT water_chemistry::bod_removal", _summary_bod_removal)
