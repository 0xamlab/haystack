"""bench_radar.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from radar import radar_range_equation, doppler_frequency, doppler_velocity, range_from_time, pulse_repetition_interval, max_unambiguous_range, max_unambiguous_velocity, range_resolution, antenna_gain_from_area, radar_cross_section_sphere, noise_power, signal_to_clutter
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

    var _acc_radar_range_equation: Float64 = 0.0
    var _t0_radar_range_equation = perf_counter_ns()
    for _ in range(N):
        _acc_radar_range_equation += radar_range_equation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_radar_range_equation = perf_counter_ns()
    var _ns_radar_range_equation = Float64(_t1_radar_range_equation - _t0_radar_range_equation) / Float64(N)
    print("MOJO_TIMING radar::radar_range_equation", _ns_radar_range_equation, _acc_radar_range_equation)
    var _result_radar_range_equation = radar_range_equation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_radar_range_equation = _summary_float64(_result_radar_range_equation)
    print("MOJO_RESULT radar::radar_range_equation", _summary_radar_range_equation)
    var _acc_doppler_frequency: Float64 = 0.0
    var _t0_doppler_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_doppler_frequency += doppler_frequency(0.5, 0.5)
    var _t1_doppler_frequency = perf_counter_ns()
    var _ns_doppler_frequency = Float64(_t1_doppler_frequency - _t0_doppler_frequency) / Float64(N)
    print("MOJO_TIMING radar::doppler_frequency", _ns_doppler_frequency, _acc_doppler_frequency)
    var _result_doppler_frequency = doppler_frequency(0.5, 0.5)
    var _summary_doppler_frequency = _summary_float64(_result_doppler_frequency)
    print("MOJO_RESULT radar::doppler_frequency", _summary_doppler_frequency)
    var _acc_doppler_velocity: Float64 = 0.0
    var _t0_doppler_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_doppler_velocity += doppler_velocity(0.5, 0.5)
    var _t1_doppler_velocity = perf_counter_ns()
    var _ns_doppler_velocity = Float64(_t1_doppler_velocity - _t0_doppler_velocity) / Float64(N)
    print("MOJO_TIMING radar::doppler_velocity", _ns_doppler_velocity, _acc_doppler_velocity)
    var _result_doppler_velocity = doppler_velocity(0.5, 0.5)
    var _summary_doppler_velocity = _summary_float64(_result_doppler_velocity)
    print("MOJO_RESULT radar::doppler_velocity", _summary_doppler_velocity)
    var _acc_range_from_time: Float64 = 0.0
    var _t0_range_from_time = perf_counter_ns()
    for _ in range(N):
        _acc_range_from_time += range_from_time(0.5, 0.5)
    var _t1_range_from_time = perf_counter_ns()
    var _ns_range_from_time = Float64(_t1_range_from_time - _t0_range_from_time) / Float64(N)
    print("MOJO_TIMING radar::range_from_time", _ns_range_from_time, _acc_range_from_time)
    var _result_range_from_time = range_from_time(0.5, 0.5)
    var _summary_range_from_time = _summary_float64(_result_range_from_time)
    print("MOJO_RESULT radar::range_from_time", _summary_range_from_time)
    var _acc_pulse_repetition_interval: Float64 = 0.0
    var _t0_pulse_repetition_interval = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_repetition_interval += pulse_repetition_interval(0.5)
    var _t1_pulse_repetition_interval = perf_counter_ns()
    var _ns_pulse_repetition_interval = Float64(_t1_pulse_repetition_interval - _t0_pulse_repetition_interval) / Float64(N)
    print("MOJO_TIMING radar::pulse_repetition_interval", _ns_pulse_repetition_interval, _acc_pulse_repetition_interval)
    var _result_pulse_repetition_interval = pulse_repetition_interval(0.5)
    var _summary_pulse_repetition_interval = _summary_float64(_result_pulse_repetition_interval)
    print("MOJO_RESULT radar::pulse_repetition_interval", _summary_pulse_repetition_interval)
    var _acc_max_unambiguous_range: Float64 = 0.0
    var _t0_max_unambiguous_range = perf_counter_ns()
    for _ in range(N):
        _acc_max_unambiguous_range += max_unambiguous_range(0.5, 0.5)
    var _t1_max_unambiguous_range = perf_counter_ns()
    var _ns_max_unambiguous_range = Float64(_t1_max_unambiguous_range - _t0_max_unambiguous_range) / Float64(N)
    print("MOJO_TIMING radar::max_unambiguous_range", _ns_max_unambiguous_range, _acc_max_unambiguous_range)
    var _result_max_unambiguous_range = max_unambiguous_range(0.5, 0.5)
    var _summary_max_unambiguous_range = _summary_float64(_result_max_unambiguous_range)
    print("MOJO_RESULT radar::max_unambiguous_range", _summary_max_unambiguous_range)
    var _acc_max_unambiguous_velocity: Float64 = 0.0
    var _t0_max_unambiguous_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_max_unambiguous_velocity += max_unambiguous_velocity(0.5, 0.5)
    var _t1_max_unambiguous_velocity = perf_counter_ns()
    var _ns_max_unambiguous_velocity = Float64(_t1_max_unambiguous_velocity - _t0_max_unambiguous_velocity) / Float64(N)
    print("MOJO_TIMING radar::max_unambiguous_velocity", _ns_max_unambiguous_velocity, _acc_max_unambiguous_velocity)
    var _result_max_unambiguous_velocity = max_unambiguous_velocity(0.5, 0.5)
    var _summary_max_unambiguous_velocity = _summary_float64(_result_max_unambiguous_velocity)
    print("MOJO_RESULT radar::max_unambiguous_velocity", _summary_max_unambiguous_velocity)
    var _acc_range_resolution: Float64 = 0.0
    var _t0_range_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_range_resolution += range_resolution(0.5)
    var _t1_range_resolution = perf_counter_ns()
    var _ns_range_resolution = Float64(_t1_range_resolution - _t0_range_resolution) / Float64(N)
    print("MOJO_TIMING radar::range_resolution", _ns_range_resolution, _acc_range_resolution)
    var _result_range_resolution = range_resolution(0.5)
    var _summary_range_resolution = _summary_float64(_result_range_resolution)
    print("MOJO_RESULT radar::range_resolution", _summary_range_resolution)
    var _acc_antenna_gain_from_area: Float64 = 0.0
    var _t0_antenna_gain_from_area = perf_counter_ns()
    for _ in range(N):
        _acc_antenna_gain_from_area += antenna_gain_from_area(0.5, 0.5)
    var _t1_antenna_gain_from_area = perf_counter_ns()
    var _ns_antenna_gain_from_area = Float64(_t1_antenna_gain_from_area - _t0_antenna_gain_from_area) / Float64(N)
    print("MOJO_TIMING radar::antenna_gain_from_area", _ns_antenna_gain_from_area, _acc_antenna_gain_from_area)
    var _result_antenna_gain_from_area = antenna_gain_from_area(0.5, 0.5)
    var _summary_antenna_gain_from_area = _summary_float64(_result_antenna_gain_from_area)
    print("MOJO_RESULT radar::antenna_gain_from_area", _summary_antenna_gain_from_area)
    var _acc_radar_cross_section_sphere: Float64 = 0.0
    var _t0_radar_cross_section_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_radar_cross_section_sphere += radar_cross_section_sphere(0.5)
    var _t1_radar_cross_section_sphere = perf_counter_ns()
    var _ns_radar_cross_section_sphere = Float64(_t1_radar_cross_section_sphere - _t0_radar_cross_section_sphere) / Float64(N)
    print("MOJO_TIMING radar::radar_cross_section_sphere", _ns_radar_cross_section_sphere, _acc_radar_cross_section_sphere)
    var _result_radar_cross_section_sphere = radar_cross_section_sphere(0.5)
    var _summary_radar_cross_section_sphere = _summary_float64(_result_radar_cross_section_sphere)
    print("MOJO_RESULT radar::radar_cross_section_sphere", _summary_radar_cross_section_sphere)
    var _acc_noise_power: Float64 = 0.0
    var _t0_noise_power = perf_counter_ns()
    for _ in range(N):
        _acc_noise_power += noise_power(0.5, 0.5, 0.5)
    var _t1_noise_power = perf_counter_ns()
    var _ns_noise_power = Float64(_t1_noise_power - _t0_noise_power) / Float64(N)
    print("MOJO_TIMING radar::noise_power", _ns_noise_power, _acc_noise_power)
    var _result_noise_power = noise_power(0.5, 0.5, 0.5)
    var _summary_noise_power = _summary_float64(_result_noise_power)
    print("MOJO_RESULT radar::noise_power", _summary_noise_power)
    var _acc_signal_to_clutter: Float64 = 0.0
    var _t0_signal_to_clutter = perf_counter_ns()
    for _ in range(N):
        _acc_signal_to_clutter += signal_to_clutter(0.5, 0.5)
    var _t1_signal_to_clutter = perf_counter_ns()
    var _ns_signal_to_clutter = Float64(_t1_signal_to_clutter - _t0_signal_to_clutter) / Float64(N)
    print("MOJO_TIMING radar::signal_to_clutter", _ns_signal_to_clutter, _acc_signal_to_clutter)
    var _result_signal_to_clutter = signal_to_clutter(0.5, 0.5)
    var _summary_signal_to_clutter = _summary_float64(_result_signal_to_clutter)
    print("MOJO_RESULT radar::signal_to_clutter", _summary_signal_to_clutter)
