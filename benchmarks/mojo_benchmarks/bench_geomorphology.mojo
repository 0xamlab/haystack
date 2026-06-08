"""bench_geomorphology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geomorphology import stream_power, shear_stress_flow, shields_parameter, settling_velocity_stokes, erosion_rate_spl, hillslope_diffusion, drainage_density, relief_ratio, sinuosity, hack_law_length, ruggedness_number, hypsometric_integral
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

    var _acc_stream_power: Float64 = 0.0
    var _t0_stream_power = perf_counter_ns()
    for _ in range(N):
        _acc_stream_power += stream_power(0.5, 0.5, 0.5, 0.5)
    var _t1_stream_power = perf_counter_ns()
    var _ns_stream_power = Float64(_t1_stream_power - _t0_stream_power) / Float64(N)
    print("MOJO_TIMING geomorphology::stream_power", _ns_stream_power, _acc_stream_power)
    var _result_stream_power = stream_power(0.5, 0.5, 0.5, 0.5)
    var _summary_stream_power = _summary_float64(_result_stream_power)
    print("MOJO_RESULT geomorphology::stream_power", _summary_stream_power)
    var _acc_shear_stress_flow: Float64 = 0.0
    var _t0_shear_stress_flow = perf_counter_ns()
    for _ in range(N):
        _acc_shear_stress_flow += shear_stress_flow(0.5, 0.5, 0.5, 0.5)
    var _t1_shear_stress_flow = perf_counter_ns()
    var _ns_shear_stress_flow = Float64(_t1_shear_stress_flow - _t0_shear_stress_flow) / Float64(N)
    print("MOJO_TIMING geomorphology::shear_stress_flow", _ns_shear_stress_flow, _acc_shear_stress_flow)
    var _result_shear_stress_flow = shear_stress_flow(0.5, 0.5, 0.5, 0.5)
    var _summary_shear_stress_flow = _summary_float64(_result_shear_stress_flow)
    print("MOJO_RESULT geomorphology::shear_stress_flow", _summary_shear_stress_flow)
    var _acc_shields_parameter: Float64 = 0.0
    var _t0_shields_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_shields_parameter += shields_parameter(5.0, 2650.0, 1000.0, 9.81, 0.01)
    var _t1_shields_parameter = perf_counter_ns()
    var _ns_shields_parameter = Float64(_t1_shields_parameter - _t0_shields_parameter) / Float64(N)
    print("MOJO_TIMING geomorphology::shields_parameter", _ns_shields_parameter, _acc_shields_parameter)
    var _result_shields_parameter = shields_parameter(5.0, 2650.0, 1000.0, 9.81, 0.01)
    var _summary_shields_parameter = _summary_float64(_result_shields_parameter)
    print("MOJO_RESULT geomorphology::shields_parameter", _summary_shields_parameter)
    var _acc_settling_velocity_stokes: Float64 = 0.0
    var _t0_settling_velocity_stokes = perf_counter_ns()
    for _ in range(N):
        _acc_settling_velocity_stokes += settling_velocity_stokes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_settling_velocity_stokes = perf_counter_ns()
    var _ns_settling_velocity_stokes = Float64(_t1_settling_velocity_stokes - _t0_settling_velocity_stokes) / Float64(N)
    print("MOJO_TIMING geomorphology::settling_velocity_stokes", _ns_settling_velocity_stokes, _acc_settling_velocity_stokes)
    var _result_settling_velocity_stokes = settling_velocity_stokes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_settling_velocity_stokes = _summary_float64(_result_settling_velocity_stokes)
    print("MOJO_RESULT geomorphology::settling_velocity_stokes", _summary_settling_velocity_stokes)
    var _acc_erosion_rate_spl: Float64 = 0.0
    var _t0_erosion_rate_spl = perf_counter_ns()
    for _ in range(N):
        _acc_erosion_rate_spl += erosion_rate_spl(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_erosion_rate_spl = perf_counter_ns()
    var _ns_erosion_rate_spl = Float64(_t1_erosion_rate_spl - _t0_erosion_rate_spl) / Float64(N)
    print("MOJO_TIMING geomorphology::erosion_rate_spl", _ns_erosion_rate_spl, _acc_erosion_rate_spl)
    var _result_erosion_rate_spl = erosion_rate_spl(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_erosion_rate_spl = _summary_float64(_result_erosion_rate_spl)
    print("MOJO_RESULT geomorphology::erosion_rate_spl", _summary_erosion_rate_spl)
    var _acc_hillslope_diffusion: Float64 = 0.0
    var _t0_hillslope_diffusion = perf_counter_ns()
    for _ in range(N):
        _acc_hillslope_diffusion += hillslope_diffusion(0.5, 0.5)
    var _t1_hillslope_diffusion = perf_counter_ns()
    var _ns_hillslope_diffusion = Float64(_t1_hillslope_diffusion - _t0_hillslope_diffusion) / Float64(N)
    print("MOJO_TIMING geomorphology::hillslope_diffusion", _ns_hillslope_diffusion, _acc_hillslope_diffusion)
    var _result_hillslope_diffusion = hillslope_diffusion(0.5, 0.5)
    var _summary_hillslope_diffusion = _summary_float64(_result_hillslope_diffusion)
    print("MOJO_RESULT geomorphology::hillslope_diffusion", _summary_hillslope_diffusion)
    var _acc_drainage_density: Float64 = 0.0
    var _t0_drainage_density = perf_counter_ns()
    for _ in range(N):
        _acc_drainage_density += drainage_density(0.5, 0.5)
    var _t1_drainage_density = perf_counter_ns()
    var _ns_drainage_density = Float64(_t1_drainage_density - _t0_drainage_density) / Float64(N)
    print("MOJO_TIMING geomorphology::drainage_density", _ns_drainage_density, _acc_drainage_density)
    var _result_drainage_density = drainage_density(0.5, 0.5)
    var _summary_drainage_density = _summary_float64(_result_drainage_density)
    print("MOJO_RESULT geomorphology::drainage_density", _summary_drainage_density)
    var _acc_relief_ratio: Float64 = 0.0
    var _t0_relief_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_relief_ratio += relief_ratio(0.5, 0.5)
    var _t1_relief_ratio = perf_counter_ns()
    var _ns_relief_ratio = Float64(_t1_relief_ratio - _t0_relief_ratio) / Float64(N)
    print("MOJO_TIMING geomorphology::relief_ratio", _ns_relief_ratio, _acc_relief_ratio)
    var _result_relief_ratio = relief_ratio(0.5, 0.5)
    var _summary_relief_ratio = _summary_float64(_result_relief_ratio)
    print("MOJO_RESULT geomorphology::relief_ratio", _summary_relief_ratio)
    var _acc_sinuosity: Float64 = 0.0
    var _t0_sinuosity = perf_counter_ns()
    for _ in range(N):
        _acc_sinuosity += sinuosity(0.5, 0.5)
    var _t1_sinuosity = perf_counter_ns()
    var _ns_sinuosity = Float64(_t1_sinuosity - _t0_sinuosity) / Float64(N)
    print("MOJO_TIMING geomorphology::sinuosity", _ns_sinuosity, _acc_sinuosity)
    var _result_sinuosity = sinuosity(0.5, 0.5)
    var _summary_sinuosity = _summary_float64(_result_sinuosity)
    print("MOJO_RESULT geomorphology::sinuosity", _summary_sinuosity)
    var _acc_hack_law_length: Float64 = 0.0
    var _t0_hack_law_length = perf_counter_ns()
    for _ in range(N):
        _acc_hack_law_length += hack_law_length(0.5, 0.5, 0.5)
    var _t1_hack_law_length = perf_counter_ns()
    var _ns_hack_law_length = Float64(_t1_hack_law_length - _t0_hack_law_length) / Float64(N)
    print("MOJO_TIMING geomorphology::hack_law_length", _ns_hack_law_length, _acc_hack_law_length)
    var _result_hack_law_length = hack_law_length(0.5, 0.5, 0.5)
    var _summary_hack_law_length = _summary_float64(_result_hack_law_length)
    print("MOJO_RESULT geomorphology::hack_law_length", _summary_hack_law_length)
    var _acc_ruggedness_number: Float64 = 0.0
    var _t0_ruggedness_number = perf_counter_ns()
    for _ in range(N):
        _acc_ruggedness_number += ruggedness_number(0.5, 0.5)
    var _t1_ruggedness_number = perf_counter_ns()
    var _ns_ruggedness_number = Float64(_t1_ruggedness_number - _t0_ruggedness_number) / Float64(N)
    print("MOJO_TIMING geomorphology::ruggedness_number", _ns_ruggedness_number, _acc_ruggedness_number)
    var _result_ruggedness_number = ruggedness_number(0.5, 0.5)
    var _summary_ruggedness_number = _summary_float64(_result_ruggedness_number)
    print("MOJO_RESULT geomorphology::ruggedness_number", _summary_ruggedness_number)
    var _acc_hypsometric_integral: Float64 = 0.0
    var _t0_hypsometric_integral = perf_counter_ns()
    for _ in range(N):
        _acc_hypsometric_integral += hypsometric_integral(500.0, 100.0, 1000.0)
    var _t1_hypsometric_integral = perf_counter_ns()
    var _ns_hypsometric_integral = Float64(_t1_hypsometric_integral - _t0_hypsometric_integral) / Float64(N)
    print("MOJO_TIMING geomorphology::hypsometric_integral", _ns_hypsometric_integral, _acc_hypsometric_integral)
    var _result_hypsometric_integral = hypsometric_integral(500.0, 100.0, 1000.0)
    var _summary_hypsometric_integral = _summary_float64(_result_hypsometric_integral)
    print("MOJO_RESULT geomorphology::hypsometric_integral", _summary_hypsometric_integral)
