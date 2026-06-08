"""bench_fermentation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fermentation import ethanol_yield, alcohol_by_volume, carbon_dioxide_produced, yeast_growth_rate, substrate_consumption, volumetric_productivity, fermentation_efficiency, dissolved_oxygen_kla, ph_buffer_capacity, heat_generation_rate
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

    var _acc_ethanol_yield: Float64 = 0.0
    var _t0_ethanol_yield = perf_counter_ns()
    for _ in range(N):
        _acc_ethanol_yield += ethanol_yield(0.5)
    var _t1_ethanol_yield = perf_counter_ns()
    var _ns_ethanol_yield = Float64(_t1_ethanol_yield - _t0_ethanol_yield) / Float64(N)
    print("MOJO_TIMING fermentation::ethanol_yield", _ns_ethanol_yield, _acc_ethanol_yield)
    var _result_ethanol_yield = ethanol_yield(0.5)
    var _summary_ethanol_yield = _summary_float64(_result_ethanol_yield)
    print("MOJO_RESULT fermentation::ethanol_yield", _summary_ethanol_yield)
    var _acc_alcohol_by_volume: Float64 = 0.0
    var _t0_alcohol_by_volume = perf_counter_ns()
    for _ in range(N):
        _acc_alcohol_by_volume += alcohol_by_volume(0.5, 0.5)
    var _t1_alcohol_by_volume = perf_counter_ns()
    var _ns_alcohol_by_volume = Float64(_t1_alcohol_by_volume - _t0_alcohol_by_volume) / Float64(N)
    print("MOJO_TIMING fermentation::alcohol_by_volume", _ns_alcohol_by_volume, _acc_alcohol_by_volume)
    var _result_alcohol_by_volume = alcohol_by_volume(0.5, 0.5)
    var _summary_alcohol_by_volume = _summary_float64(_result_alcohol_by_volume)
    print("MOJO_RESULT fermentation::alcohol_by_volume", _summary_alcohol_by_volume)
    var _acc_carbon_dioxide_produced: Float64 = 0.0
    var _t0_carbon_dioxide_produced = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_dioxide_produced += carbon_dioxide_produced(0.5)
    var _t1_carbon_dioxide_produced = perf_counter_ns()
    var _ns_carbon_dioxide_produced = Float64(_t1_carbon_dioxide_produced - _t0_carbon_dioxide_produced) / Float64(N)
    print("MOJO_TIMING fermentation::carbon_dioxide_produced", _ns_carbon_dioxide_produced, _acc_carbon_dioxide_produced)
    var _result_carbon_dioxide_produced = carbon_dioxide_produced(0.5)
    var _summary_carbon_dioxide_produced = _summary_float64(_result_carbon_dioxide_produced)
    print("MOJO_RESULT fermentation::carbon_dioxide_produced", _summary_carbon_dioxide_produced)
    var _acc_yeast_growth_rate: Float64 = 0.0
    var _t0_yeast_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_yeast_growth_rate += yeast_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_yeast_growth_rate = perf_counter_ns()
    var _ns_yeast_growth_rate = Float64(_t1_yeast_growth_rate - _t0_yeast_growth_rate) / Float64(N)
    print("MOJO_TIMING fermentation::yeast_growth_rate", _ns_yeast_growth_rate, _acc_yeast_growth_rate)
    var _result_yeast_growth_rate = yeast_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_yeast_growth_rate = _summary_float64(_result_yeast_growth_rate)
    print("MOJO_RESULT fermentation::yeast_growth_rate", _summary_yeast_growth_rate)
    var _acc_substrate_consumption: Float64 = 0.0
    var _t0_substrate_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_substrate_consumption += substrate_consumption(0.5, 0.5, 0.5)
    var _t1_substrate_consumption = perf_counter_ns()
    var _ns_substrate_consumption = Float64(_t1_substrate_consumption - _t0_substrate_consumption) / Float64(N)
    print("MOJO_TIMING fermentation::substrate_consumption", _ns_substrate_consumption, _acc_substrate_consumption)
    var _result_substrate_consumption = substrate_consumption(0.5, 0.5, 0.5)
    var _summary_substrate_consumption = _summary_float64(_result_substrate_consumption)
    print("MOJO_RESULT fermentation::substrate_consumption", _summary_substrate_consumption)
    var _acc_volumetric_productivity: Float64 = 0.0
    var _t0_volumetric_productivity = perf_counter_ns()
    for _ in range(N):
        _acc_volumetric_productivity += volumetric_productivity(0.5, 0.5)
    var _t1_volumetric_productivity = perf_counter_ns()
    var _ns_volumetric_productivity = Float64(_t1_volumetric_productivity - _t0_volumetric_productivity) / Float64(N)
    print("MOJO_TIMING fermentation::volumetric_productivity", _ns_volumetric_productivity, _acc_volumetric_productivity)
    var _result_volumetric_productivity = volumetric_productivity(0.5, 0.5)
    var _summary_volumetric_productivity = _summary_float64(_result_volumetric_productivity)
    print("MOJO_RESULT fermentation::volumetric_productivity", _summary_volumetric_productivity)
    var _acc_fermentation_efficiency: Float64 = 0.0
    var _t0_fermentation_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_fermentation_efficiency += fermentation_efficiency(0.5, 0.5)
    var _t1_fermentation_efficiency = perf_counter_ns()
    var _ns_fermentation_efficiency = Float64(_t1_fermentation_efficiency - _t0_fermentation_efficiency) / Float64(N)
    print("MOJO_TIMING fermentation::fermentation_efficiency", _ns_fermentation_efficiency, _acc_fermentation_efficiency)
    var _result_fermentation_efficiency = fermentation_efficiency(0.5, 0.5)
    var _summary_fermentation_efficiency = _summary_float64(_result_fermentation_efficiency)
    print("MOJO_RESULT fermentation::fermentation_efficiency", _summary_fermentation_efficiency)
    var _acc_dissolved_oxygen_kla: Float64 = 0.0
    var _t0_dissolved_oxygen_kla = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_kla += dissolved_oxygen_kla(0.5, 0.5, 0.5)
    var _t1_dissolved_oxygen_kla = perf_counter_ns()
    var _ns_dissolved_oxygen_kla = Float64(_t1_dissolved_oxygen_kla - _t0_dissolved_oxygen_kla) / Float64(N)
    print("MOJO_TIMING fermentation::dissolved_oxygen_kla", _ns_dissolved_oxygen_kla, _acc_dissolved_oxygen_kla)
    var _result_dissolved_oxygen_kla = dissolved_oxygen_kla(0.5, 0.5, 0.5)
    var _summary_dissolved_oxygen_kla = _summary_float64(_result_dissolved_oxygen_kla)
    print("MOJO_RESULT fermentation::dissolved_oxygen_kla", _summary_dissolved_oxygen_kla)
    var _acc_ph_buffer_capacity: Float64 = 0.0
    var _t0_ph_buffer_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_ph_buffer_capacity += ph_buffer_capacity(0.5, 0.5, 0.5)
    var _t1_ph_buffer_capacity = perf_counter_ns()
    var _ns_ph_buffer_capacity = Float64(_t1_ph_buffer_capacity - _t0_ph_buffer_capacity) / Float64(N)
    print("MOJO_TIMING fermentation::ph_buffer_capacity", _ns_ph_buffer_capacity, _acc_ph_buffer_capacity)
    var _result_ph_buffer_capacity = ph_buffer_capacity(0.5, 0.5, 0.5)
    var _summary_ph_buffer_capacity = _summary_float64(_result_ph_buffer_capacity)
    print("MOJO_RESULT fermentation::ph_buffer_capacity", _summary_ph_buffer_capacity)
    var _acc_heat_generation_rate: Float64 = 0.0
    var _t0_heat_generation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_generation_rate += heat_generation_rate(0.5, 0.5)
    var _t1_heat_generation_rate = perf_counter_ns()
    var _ns_heat_generation_rate = Float64(_t1_heat_generation_rate - _t0_heat_generation_rate) / Float64(N)
    print("MOJO_TIMING fermentation::heat_generation_rate", _ns_heat_generation_rate, _acc_heat_generation_rate)
    var _result_heat_generation_rate = heat_generation_rate(0.5, 0.5)
    var _summary_heat_generation_rate = _summary_float64(_result_heat_generation_rate)
    print("MOJO_RESULT fermentation::heat_generation_rate", _summary_heat_generation_rate)
