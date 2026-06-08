"""bench_ecohydrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ecohydrology import interception_loss, transpiration_priestley_taylor, root_water_uptake, streamflow_baseflow_index, wetland_retention_time, riparian_buffer_efficiency, ecohydrological_stress, flood_pulse_benefit, water_table_depth_et, catchment_runoff_ratio
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

    var _acc_interception_loss: Float64 = 0.0
    var _t0_interception_loss = perf_counter_ns()
    for _ in range(N):
        _acc_interception_loss += interception_loss(0.5, 0.5, 0.5)
    var _t1_interception_loss = perf_counter_ns()
    var _ns_interception_loss = Float64(_t1_interception_loss - _t0_interception_loss) / Float64(N)
    print("MOJO_TIMING ecohydrology::interception_loss", _ns_interception_loss, _acc_interception_loss)
    var _result_interception_loss = interception_loss(0.5, 0.5, 0.5)
    var _summary_interception_loss = _summary_float64(_result_interception_loss)
    print("MOJO_RESULT ecohydrology::interception_loss", _summary_interception_loss)
    var _acc_transpiration_priestley_taylor: Float64 = 0.0
    var _t0_transpiration_priestley_taylor = perf_counter_ns()
    for _ in range(N):
        _acc_transpiration_priestley_taylor += transpiration_priestley_taylor(0.5, 0.5, 0.5, 0.5)
    var _t1_transpiration_priestley_taylor = perf_counter_ns()
    var _ns_transpiration_priestley_taylor = Float64(_t1_transpiration_priestley_taylor - _t0_transpiration_priestley_taylor) / Float64(N)
    print("MOJO_TIMING ecohydrology::transpiration_priestley_taylor", _ns_transpiration_priestley_taylor, _acc_transpiration_priestley_taylor)
    var _result_transpiration_priestley_taylor = transpiration_priestley_taylor(0.5, 0.5, 0.5, 0.5)
    var _summary_transpiration_priestley_taylor = _summary_float64(_result_transpiration_priestley_taylor)
    print("MOJO_RESULT ecohydrology::transpiration_priestley_taylor", _summary_transpiration_priestley_taylor)
    var _acc_root_water_uptake: Float64 = 0.0
    var _t0_root_water_uptake = perf_counter_ns()
    for _ in range(N):
        _acc_root_water_uptake += root_water_uptake(0.5, 0.5, 0.5, 0.5)
    var _t1_root_water_uptake = perf_counter_ns()
    var _ns_root_water_uptake = Float64(_t1_root_water_uptake - _t0_root_water_uptake) / Float64(N)
    print("MOJO_TIMING ecohydrology::root_water_uptake", _ns_root_water_uptake, _acc_root_water_uptake)
    var _result_root_water_uptake = root_water_uptake(0.5, 0.5, 0.5, 0.5)
    var _summary_root_water_uptake = _summary_float64(_result_root_water_uptake)
    print("MOJO_RESULT ecohydrology::root_water_uptake", _summary_root_water_uptake)
    var _acc_streamflow_baseflow_index: Float64 = 0.0
    var _t0_streamflow_baseflow_index = perf_counter_ns()
    for _ in range(N):
        _acc_streamflow_baseflow_index += streamflow_baseflow_index(0.5, 0.5)
    var _t1_streamflow_baseflow_index = perf_counter_ns()
    var _ns_streamflow_baseflow_index = Float64(_t1_streamflow_baseflow_index - _t0_streamflow_baseflow_index) / Float64(N)
    print("MOJO_TIMING ecohydrology::streamflow_baseflow_index", _ns_streamflow_baseflow_index, _acc_streamflow_baseflow_index)
    var _result_streamflow_baseflow_index = streamflow_baseflow_index(0.5, 0.5)
    var _summary_streamflow_baseflow_index = _summary_float64(_result_streamflow_baseflow_index)
    print("MOJO_RESULT ecohydrology::streamflow_baseflow_index", _summary_streamflow_baseflow_index)
    var _acc_wetland_retention_time: Float64 = 0.0
    var _t0_wetland_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_wetland_retention_time += wetland_retention_time(0.5, 0.5)
    var _t1_wetland_retention_time = perf_counter_ns()
    var _ns_wetland_retention_time = Float64(_t1_wetland_retention_time - _t0_wetland_retention_time) / Float64(N)
    print("MOJO_TIMING ecohydrology::wetland_retention_time", _ns_wetland_retention_time, _acc_wetland_retention_time)
    var _result_wetland_retention_time = wetland_retention_time(0.5, 0.5)
    var _summary_wetland_retention_time = _summary_float64(_result_wetland_retention_time)
    print("MOJO_RESULT ecohydrology::wetland_retention_time", _summary_wetland_retention_time)
    var _acc_riparian_buffer_efficiency: Float64 = 0.0
    var _t0_riparian_buffer_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_riparian_buffer_efficiency += riparian_buffer_efficiency(0.5, 0.5, 0.5)
    var _t1_riparian_buffer_efficiency = perf_counter_ns()
    var _ns_riparian_buffer_efficiency = Float64(_t1_riparian_buffer_efficiency - _t0_riparian_buffer_efficiency) / Float64(N)
    print("MOJO_TIMING ecohydrology::riparian_buffer_efficiency", _ns_riparian_buffer_efficiency, _acc_riparian_buffer_efficiency)
    var _result_riparian_buffer_efficiency = riparian_buffer_efficiency(0.5, 0.5, 0.5)
    var _summary_riparian_buffer_efficiency = _summary_float64(_result_riparian_buffer_efficiency)
    print("MOJO_RESULT ecohydrology::riparian_buffer_efficiency", _summary_riparian_buffer_efficiency)
    var _acc_ecohydrological_stress: Float64 = 0.0
    var _t0_ecohydrological_stress = perf_counter_ns()
    for _ in range(N):
        _acc_ecohydrological_stress += ecohydrological_stress(0.5, 0.5, 0.5)
    var _t1_ecohydrological_stress = perf_counter_ns()
    var _ns_ecohydrological_stress = Float64(_t1_ecohydrological_stress - _t0_ecohydrological_stress) / Float64(N)
    print("MOJO_TIMING ecohydrology::ecohydrological_stress", _ns_ecohydrological_stress, _acc_ecohydrological_stress)
    var _result_ecohydrological_stress = ecohydrological_stress(0.5, 0.5, 0.5)
    var _summary_ecohydrological_stress = _summary_float64(_result_ecohydrological_stress)
    print("MOJO_RESULT ecohydrology::ecohydrological_stress", _summary_ecohydrological_stress)
    var _acc_flood_pulse_benefit: Float64 = 0.0
    var _t0_flood_pulse_benefit = perf_counter_ns()
    for _ in range(N):
        _acc_flood_pulse_benefit += flood_pulse_benefit(0.5, 0.5, 0.5)
    var _t1_flood_pulse_benefit = perf_counter_ns()
    var _ns_flood_pulse_benefit = Float64(_t1_flood_pulse_benefit - _t0_flood_pulse_benefit) / Float64(N)
    print("MOJO_TIMING ecohydrology::flood_pulse_benefit", _ns_flood_pulse_benefit, _acc_flood_pulse_benefit)
    var _result_flood_pulse_benefit = flood_pulse_benefit(0.5, 0.5, 0.5)
    var _summary_flood_pulse_benefit = _summary_float64(_result_flood_pulse_benefit)
    print("MOJO_RESULT ecohydrology::flood_pulse_benefit", _summary_flood_pulse_benefit)
    var _acc_water_table_depth_et: Float64 = 0.0
    var _t0_water_table_depth_et = perf_counter_ns()
    for _ in range(N):
        _acc_water_table_depth_et += water_table_depth_et(0.5, 0.5, 0.5)
    var _t1_water_table_depth_et = perf_counter_ns()
    var _ns_water_table_depth_et = Float64(_t1_water_table_depth_et - _t0_water_table_depth_et) / Float64(N)
    print("MOJO_TIMING ecohydrology::water_table_depth_et", _ns_water_table_depth_et, _acc_water_table_depth_et)
    var _result_water_table_depth_et = water_table_depth_et(0.5, 0.5, 0.5)
    var _summary_water_table_depth_et = _summary_float64(_result_water_table_depth_et)
    print("MOJO_RESULT ecohydrology::water_table_depth_et", _summary_water_table_depth_et)
    var _acc_catchment_runoff_ratio: Float64 = 0.0
    var _t0_catchment_runoff_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_catchment_runoff_ratio += catchment_runoff_ratio(0.5, 0.5)
    var _t1_catchment_runoff_ratio = perf_counter_ns()
    var _ns_catchment_runoff_ratio = Float64(_t1_catchment_runoff_ratio - _t0_catchment_runoff_ratio) / Float64(N)
    print("MOJO_TIMING ecohydrology::catchment_runoff_ratio", _ns_catchment_runoff_ratio, _acc_catchment_runoff_ratio)
    var _result_catchment_runoff_ratio = catchment_runoff_ratio(0.5, 0.5)
    var _summary_catchment_runoff_ratio = _summary_float64(_result_catchment_runoff_ratio)
    print("MOJO_RESULT ecohydrology::catchment_runoff_ratio", _summary_catchment_runoff_ratio)
