"""bench_acoustics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from acoustics import sound_pressure_level, sound_intensity_level, sound_power_level, inverse_square_law_pressure, wavelength, resonant_frequency_pipe_open, resonant_frequency_pipe_closed, doppler_frequency, reverberation_time_sabine, noise_reduction_coefficient, decibel_sum_2, distance_doubling_attenuation
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

    var _acc_sound_pressure_level: Float64 = 0.0
    var _t0_sound_pressure_level = perf_counter_ns()
    for _ in range(N):
        _acc_sound_pressure_level += sound_pressure_level(0.5, 0.5)
    var _t1_sound_pressure_level = perf_counter_ns()
    var _ns_sound_pressure_level = Float64(_t1_sound_pressure_level - _t0_sound_pressure_level) / Float64(N)
    print("MOJO_TIMING acoustics::sound_pressure_level", _ns_sound_pressure_level, _acc_sound_pressure_level)
    var _result_sound_pressure_level = sound_pressure_level(0.5, 0.5)
    var _summary_sound_pressure_level = _summary_float64(_result_sound_pressure_level)
    print("MOJO_RESULT acoustics::sound_pressure_level", _summary_sound_pressure_level)
    var _acc_sound_intensity_level: Float64 = 0.0
    var _t0_sound_intensity_level = perf_counter_ns()
    for _ in range(N):
        _acc_sound_intensity_level += sound_intensity_level(0.5, 0.5)
    var _t1_sound_intensity_level = perf_counter_ns()
    var _ns_sound_intensity_level = Float64(_t1_sound_intensity_level - _t0_sound_intensity_level) / Float64(N)
    print("MOJO_TIMING acoustics::sound_intensity_level", _ns_sound_intensity_level, _acc_sound_intensity_level)
    var _result_sound_intensity_level = sound_intensity_level(0.5, 0.5)
    var _summary_sound_intensity_level = _summary_float64(_result_sound_intensity_level)
    print("MOJO_RESULT acoustics::sound_intensity_level", _summary_sound_intensity_level)
    var _acc_sound_power_level: Float64 = 0.0
    var _t0_sound_power_level = perf_counter_ns()
    for _ in range(N):
        _acc_sound_power_level += sound_power_level(0.5, 0.5)
    var _t1_sound_power_level = perf_counter_ns()
    var _ns_sound_power_level = Float64(_t1_sound_power_level - _t0_sound_power_level) / Float64(N)
    print("MOJO_TIMING acoustics::sound_power_level", _ns_sound_power_level, _acc_sound_power_level)
    var _result_sound_power_level = sound_power_level(0.5, 0.5)
    var _summary_sound_power_level = _summary_float64(_result_sound_power_level)
    print("MOJO_RESULT acoustics::sound_power_level", _summary_sound_power_level)
    var _acc_inverse_square_law_pressure: Float64 = 0.0
    var _t0_inverse_square_law_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_square_law_pressure += inverse_square_law_pressure(0.5, 0.5, 0.5)
    var _t1_inverse_square_law_pressure = perf_counter_ns()
    var _ns_inverse_square_law_pressure = Float64(_t1_inverse_square_law_pressure - _t0_inverse_square_law_pressure) / Float64(N)
    print("MOJO_TIMING acoustics::inverse_square_law_pressure", _ns_inverse_square_law_pressure, _acc_inverse_square_law_pressure)
    var _result_inverse_square_law_pressure = inverse_square_law_pressure(0.5, 0.5, 0.5)
    var _summary_inverse_square_law_pressure = _summary_float64(_result_inverse_square_law_pressure)
    print("MOJO_RESULT acoustics::inverse_square_law_pressure", _summary_inverse_square_law_pressure)
    var _acc_wavelength: Float64 = 0.0
    var _t0_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength += wavelength(0.5, 0.5)
    var _t1_wavelength = perf_counter_ns()
    var _ns_wavelength = Float64(_t1_wavelength - _t0_wavelength) / Float64(N)
    print("MOJO_TIMING acoustics::wavelength", _ns_wavelength, _acc_wavelength)
    var _result_wavelength = wavelength(0.5, 0.5)
    var _summary_wavelength = _summary_float64(_result_wavelength)
    print("MOJO_RESULT acoustics::wavelength", _summary_wavelength)
    var _acc_resonant_frequency_pipe_open: Float64 = 0.0
    var _t0_resonant_frequency_pipe_open = perf_counter_ns()
    for _ in range(N):
        _acc_resonant_frequency_pipe_open += resonant_frequency_pipe_open(0.5, 0.5)
    var _t1_resonant_frequency_pipe_open = perf_counter_ns()
    var _ns_resonant_frequency_pipe_open = Float64(_t1_resonant_frequency_pipe_open - _t0_resonant_frequency_pipe_open) / Float64(N)
    print("MOJO_TIMING acoustics::resonant_frequency_pipe_open", _ns_resonant_frequency_pipe_open, _acc_resonant_frequency_pipe_open)
    var _result_resonant_frequency_pipe_open = resonant_frequency_pipe_open(0.5, 0.5)
    var _summary_resonant_frequency_pipe_open = _summary_float64(_result_resonant_frequency_pipe_open)
    print("MOJO_RESULT acoustics::resonant_frequency_pipe_open", _summary_resonant_frequency_pipe_open)
    var _acc_resonant_frequency_pipe_closed: Float64 = 0.0
    var _t0_resonant_frequency_pipe_closed = perf_counter_ns()
    for _ in range(N):
        _acc_resonant_frequency_pipe_closed += resonant_frequency_pipe_closed(0.5, 0.5)
    var _t1_resonant_frequency_pipe_closed = perf_counter_ns()
    var _ns_resonant_frequency_pipe_closed = Float64(_t1_resonant_frequency_pipe_closed - _t0_resonant_frequency_pipe_closed) / Float64(N)
    print("MOJO_TIMING acoustics::resonant_frequency_pipe_closed", _ns_resonant_frequency_pipe_closed, _acc_resonant_frequency_pipe_closed)
    var _result_resonant_frequency_pipe_closed = resonant_frequency_pipe_closed(0.5, 0.5)
    var _summary_resonant_frequency_pipe_closed = _summary_float64(_result_resonant_frequency_pipe_closed)
    print("MOJO_RESULT acoustics::resonant_frequency_pipe_closed", _summary_resonant_frequency_pipe_closed)
    var _acc_doppler_frequency: Float64 = 0.0
    var _t0_doppler_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_doppler_frequency += doppler_frequency(0.5, 0.5, 0.5, 0.5)
    var _t1_doppler_frequency = perf_counter_ns()
    var _ns_doppler_frequency = Float64(_t1_doppler_frequency - _t0_doppler_frequency) / Float64(N)
    print("MOJO_TIMING acoustics::doppler_frequency", _ns_doppler_frequency, _acc_doppler_frequency)
    var _result_doppler_frequency = doppler_frequency(0.5, 0.5, 0.5, 0.5)
    var _summary_doppler_frequency = _summary_float64(_result_doppler_frequency)
    print("MOJO_RESULT acoustics::doppler_frequency", _summary_doppler_frequency)
    var _acc_reverberation_time_sabine: Float64 = 0.0
    var _t0_reverberation_time_sabine = perf_counter_ns()
    for _ in range(N):
        _acc_reverberation_time_sabine += reverberation_time_sabine(0.5, 0.5)
    var _t1_reverberation_time_sabine = perf_counter_ns()
    var _ns_reverberation_time_sabine = Float64(_t1_reverberation_time_sabine - _t0_reverberation_time_sabine) / Float64(N)
    print("MOJO_TIMING acoustics::reverberation_time_sabine", _ns_reverberation_time_sabine, _acc_reverberation_time_sabine)
    var _result_reverberation_time_sabine = reverberation_time_sabine(0.5, 0.5)
    var _summary_reverberation_time_sabine = _summary_float64(_result_reverberation_time_sabine)
    print("MOJO_RESULT acoustics::reverberation_time_sabine", _summary_reverberation_time_sabine)
    var _acc_noise_reduction_coefficient: Float64 = 0.0
    var _t0_noise_reduction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_noise_reduction_coefficient += noise_reduction_coefficient(0.5, 0.5, 0.5, 0.5)
    var _t1_noise_reduction_coefficient = perf_counter_ns()
    var _ns_noise_reduction_coefficient = Float64(_t1_noise_reduction_coefficient - _t0_noise_reduction_coefficient) / Float64(N)
    print("MOJO_TIMING acoustics::noise_reduction_coefficient", _ns_noise_reduction_coefficient, _acc_noise_reduction_coefficient)
    var _result_noise_reduction_coefficient = noise_reduction_coefficient(0.5, 0.5, 0.5, 0.5)
    var _summary_noise_reduction_coefficient = _summary_float64(_result_noise_reduction_coefficient)
    print("MOJO_RESULT acoustics::noise_reduction_coefficient", _summary_noise_reduction_coefficient)
    var _acc_decibel_sum_2: Float64 = 0.0
    var _t0_decibel_sum_2 = perf_counter_ns()
    for _ in range(N):
        _acc_decibel_sum_2 += decibel_sum_2(0.5, 0.5)
    var _t1_decibel_sum_2 = perf_counter_ns()
    var _ns_decibel_sum_2 = Float64(_t1_decibel_sum_2 - _t0_decibel_sum_2) / Float64(N)
    print("MOJO_TIMING acoustics::decibel_sum_2", _ns_decibel_sum_2, _acc_decibel_sum_2)
    var _result_decibel_sum_2 = decibel_sum_2(0.5, 0.5)
    var _summary_decibel_sum_2 = _summary_float64(_result_decibel_sum_2)
    print("MOJO_RESULT acoustics::decibel_sum_2", _summary_decibel_sum_2)
    var _acc_distance_doubling_attenuation: Float64 = 0.0
    var _t0_distance_doubling_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_distance_doubling_attenuation += distance_doubling_attenuation()
    var _t1_distance_doubling_attenuation = perf_counter_ns()
    var _ns_distance_doubling_attenuation = Float64(_t1_distance_doubling_attenuation - _t0_distance_doubling_attenuation) / Float64(N)
    print("MOJO_TIMING acoustics::distance_doubling_attenuation", _ns_distance_doubling_attenuation, _acc_distance_doubling_attenuation)
    var _result_distance_doubling_attenuation = distance_doubling_attenuation()
    var _summary_distance_doubling_attenuation = _summary_float64(_result_distance_doubling_attenuation)
    print("MOJO_RESULT acoustics::distance_doubling_attenuation", _summary_distance_doubling_attenuation)
