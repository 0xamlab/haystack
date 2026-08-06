"""bench_marine.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from marine import seawater_density, wave_speed_deep, wave_speed_shallow, wave_period, significant_wave_height, tidal_range, mixed_layer_depth_estimate, ekman_depth, coriolis_parameter, buoyancy_frequency, salinity_from_conductivity, ocean_pressure_at_depth
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

    var _acc_seawater_density: Float64 = 0.0
    var _t0_seawater_density = perf_counter_ns()
    for _ in range(N):
        _acc_seawater_density += seawater_density(0.5, 0.5)
    var _t1_seawater_density = perf_counter_ns()
    var _ns_seawater_density = Float64(_t1_seawater_density - _t0_seawater_density) / Float64(N)
    print("MOJO_TIMING marine::seawater_density", _ns_seawater_density, _acc_seawater_density)
    var _result_seawater_density = seawater_density(0.5, 0.5)
    var _summary_seawater_density = _summary_float64(_result_seawater_density)
    print("MOJO_RESULT marine::seawater_density", _summary_seawater_density)
    var _acc_wave_speed_deep: Float64 = 0.0
    var _t0_wave_speed_deep = perf_counter_ns()
    for _ in range(N):
        _acc_wave_speed_deep += wave_speed_deep(0.5, 0.5)
    var _t1_wave_speed_deep = perf_counter_ns()
    var _ns_wave_speed_deep = Float64(_t1_wave_speed_deep - _t0_wave_speed_deep) / Float64(N)
    print("MOJO_TIMING marine::wave_speed_deep", _ns_wave_speed_deep, _acc_wave_speed_deep)
    var _result_wave_speed_deep = wave_speed_deep(0.5, 0.5)
    var _summary_wave_speed_deep = _summary_float64(_result_wave_speed_deep)
    print("MOJO_RESULT marine::wave_speed_deep", _summary_wave_speed_deep)
    var _acc_wave_speed_shallow: Float64 = 0.0
    var _t0_wave_speed_shallow = perf_counter_ns()
    for _ in range(N):
        _acc_wave_speed_shallow += wave_speed_shallow(0.5, 0.5)
    var _t1_wave_speed_shallow = perf_counter_ns()
    var _ns_wave_speed_shallow = Float64(_t1_wave_speed_shallow - _t0_wave_speed_shallow) / Float64(N)
    print("MOJO_TIMING marine::wave_speed_shallow", _ns_wave_speed_shallow, _acc_wave_speed_shallow)
    var _result_wave_speed_shallow = wave_speed_shallow(0.5, 0.5)
    var _summary_wave_speed_shallow = _summary_float64(_result_wave_speed_shallow)
    print("MOJO_RESULT marine::wave_speed_shallow", _summary_wave_speed_shallow)
    var _acc_wave_period: Float64 = 0.0
    var _t0_wave_period = perf_counter_ns()
    for _ in range(N):
        _acc_wave_period += wave_period(0.5, 0.5)
    var _t1_wave_period = perf_counter_ns()
    var _ns_wave_period = Float64(_t1_wave_period - _t0_wave_period) / Float64(N)
    print("MOJO_TIMING marine::wave_period", _ns_wave_period, _acc_wave_period)
    var _result_wave_period = wave_period(0.5, 0.5)
    var _summary_wave_period = _summary_float64(_result_wave_period)
    print("MOJO_RESULT marine::wave_period", _summary_wave_period)
    var _acc_significant_wave_height: Float64 = 0.0
    var _t0_significant_wave_height = perf_counter_ns()
    for _ in range(N):
        _acc_significant_wave_height += significant_wave_height(0.5)
    var _t1_significant_wave_height = perf_counter_ns()
    var _ns_significant_wave_height = Float64(_t1_significant_wave_height - _t0_significant_wave_height) / Float64(N)
    print("MOJO_TIMING marine::significant_wave_height", _ns_significant_wave_height, _acc_significant_wave_height)
    var _result_significant_wave_height = significant_wave_height(0.5)
    var _summary_significant_wave_height = _summary_float64(_result_significant_wave_height)
    print("MOJO_RESULT marine::significant_wave_height", _summary_significant_wave_height)
    var _acc_tidal_range: Float64 = 0.0
    var _t0_tidal_range = perf_counter_ns()
    for _ in range(N):
        _acc_tidal_range += tidal_range(0.5, 0.5)
    var _t1_tidal_range = perf_counter_ns()
    var _ns_tidal_range = Float64(_t1_tidal_range - _t0_tidal_range) / Float64(N)
    print("MOJO_TIMING marine::tidal_range", _ns_tidal_range, _acc_tidal_range)
    var _result_tidal_range = tidal_range(0.5, 0.5)
    var _summary_tidal_range = _summary_float64(_result_tidal_range)
    print("MOJO_RESULT marine::tidal_range", _summary_tidal_range)
    var _acc_mixed_layer_depth_estimate: Float64 = 0.0
    var _t0_mixed_layer_depth_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_mixed_layer_depth_estimate += mixed_layer_depth_estimate(0.5, 0.5)
    var _t1_mixed_layer_depth_estimate = perf_counter_ns()
    var _ns_mixed_layer_depth_estimate = Float64(_t1_mixed_layer_depth_estimate - _t0_mixed_layer_depth_estimate) / Float64(N)
    print("MOJO_TIMING marine::mixed_layer_depth_estimate", _ns_mixed_layer_depth_estimate, _acc_mixed_layer_depth_estimate)
    var _result_mixed_layer_depth_estimate = mixed_layer_depth_estimate(0.5, 0.5)
    var _summary_mixed_layer_depth_estimate = _summary_float64(_result_mixed_layer_depth_estimate)
    print("MOJO_RESULT marine::mixed_layer_depth_estimate", _summary_mixed_layer_depth_estimate)
    var _acc_ekman_depth: Float64 = 0.0
    var _t0_ekman_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ekman_depth += ekman_depth(0.5, 0.5, 0.5)
    var _t1_ekman_depth = perf_counter_ns()
    var _ns_ekman_depth = Float64(_t1_ekman_depth - _t0_ekman_depth) / Float64(N)
    print("MOJO_TIMING marine::ekman_depth", _ns_ekman_depth, _acc_ekman_depth)
    var _result_ekman_depth = ekman_depth(0.5, 0.5, 0.5)
    var _summary_ekman_depth = _summary_float64(_result_ekman_depth)
    print("MOJO_RESULT marine::ekman_depth", _summary_ekman_depth)
    var _acc_coriolis_parameter: Float64 = 0.0
    var _t0_coriolis_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_coriolis_parameter += coriolis_parameter(0.5)
    var _t1_coriolis_parameter = perf_counter_ns()
    var _ns_coriolis_parameter = Float64(_t1_coriolis_parameter - _t0_coriolis_parameter) / Float64(N)
    print("MOJO_TIMING marine::coriolis_parameter", _ns_coriolis_parameter, _acc_coriolis_parameter)
    var _result_coriolis_parameter = coriolis_parameter(0.5)
    var _summary_coriolis_parameter = _summary_float64(_result_coriolis_parameter)
    print("MOJO_RESULT marine::coriolis_parameter", _summary_coriolis_parameter)
    var _acc_buoyancy_frequency: Float64 = 0.0
    var _t0_buoyancy_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_buoyancy_frequency += buoyancy_frequency(0.5, 0.5, 0.5)
    var _t1_buoyancy_frequency = perf_counter_ns()
    var _ns_buoyancy_frequency = Float64(_t1_buoyancy_frequency - _t0_buoyancy_frequency) / Float64(N)
    print("MOJO_TIMING marine::buoyancy_frequency", _ns_buoyancy_frequency, _acc_buoyancy_frequency)
    var _result_buoyancy_frequency = buoyancy_frequency(0.5, 0.5, 0.5)
    var _summary_buoyancy_frequency = _summary_float64(_result_buoyancy_frequency)
    print("MOJO_RESULT marine::buoyancy_frequency", _summary_buoyancy_frequency)
    var _acc_salinity_from_conductivity: Float64 = 0.0
    var _t0_salinity_from_conductivity = perf_counter_ns()
    for _ in range(N):
        _acc_salinity_from_conductivity += salinity_from_conductivity(0.5, 0.5)
    var _t1_salinity_from_conductivity = perf_counter_ns()
    var _ns_salinity_from_conductivity = Float64(_t1_salinity_from_conductivity - _t0_salinity_from_conductivity) / Float64(N)
    print("MOJO_TIMING marine::salinity_from_conductivity", _ns_salinity_from_conductivity, _acc_salinity_from_conductivity)
    var _result_salinity_from_conductivity = salinity_from_conductivity(0.5, 0.5)
    var _summary_salinity_from_conductivity = _summary_float64(_result_salinity_from_conductivity)
    print("MOJO_RESULT marine::salinity_from_conductivity", _summary_salinity_from_conductivity)
    var _acc_ocean_pressure_at_depth: Float64 = 0.0
    var _t0_ocean_pressure_at_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ocean_pressure_at_depth += ocean_pressure_at_depth(0.5, 0.5, 0.5)
    var _t1_ocean_pressure_at_depth = perf_counter_ns()
    var _ns_ocean_pressure_at_depth = Float64(_t1_ocean_pressure_at_depth - _t0_ocean_pressure_at_depth) / Float64(N)
    print("MOJO_TIMING marine::ocean_pressure_at_depth", _ns_ocean_pressure_at_depth, _acc_ocean_pressure_at_depth)
    var _result_ocean_pressure_at_depth = ocean_pressure_at_depth(0.5, 0.5, 0.5)
    var _summary_ocean_pressure_at_depth = _summary_float64(_result_ocean_pressure_at_depth)
    print("MOJO_RESULT marine::ocean_pressure_at_depth", _summary_ocean_pressure_at_depth)
