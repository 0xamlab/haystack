"""bench_acoustics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from acoustics import sound_pressure_level, sound_intensity_level, sound_power_level, inverse_square_law_pressure, wavelength, resonant_frequency_pipe_open, resonant_frequency_pipe_closed, doppler_frequency, reverberation_time_sabine, noise_reduction_coefficient, decibel_sum_2, distance_doubling_attenuation
from std.time import perf_counter_ns

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
    var _acc_sound_intensity_level: Float64 = 0.0
    var _t0_sound_intensity_level = perf_counter_ns()
    for _ in range(N):
        _acc_sound_intensity_level += sound_intensity_level(0.5, 0.5)
    var _t1_sound_intensity_level = perf_counter_ns()
    var _ns_sound_intensity_level = Float64(_t1_sound_intensity_level - _t0_sound_intensity_level) / Float64(N)
    print("MOJO_TIMING acoustics::sound_intensity_level", _ns_sound_intensity_level, _acc_sound_intensity_level)
    var _acc_sound_power_level: Float64 = 0.0
    var _t0_sound_power_level = perf_counter_ns()
    for _ in range(N):
        _acc_sound_power_level += sound_power_level(0.5, 0.5)
    var _t1_sound_power_level = perf_counter_ns()
    var _ns_sound_power_level = Float64(_t1_sound_power_level - _t0_sound_power_level) / Float64(N)
    print("MOJO_TIMING acoustics::sound_power_level", _ns_sound_power_level, _acc_sound_power_level)
    var _acc_inverse_square_law_pressure: Float64 = 0.0
    var _t0_inverse_square_law_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_square_law_pressure += inverse_square_law_pressure(0.5, 0.5, 0.5)
    var _t1_inverse_square_law_pressure = perf_counter_ns()
    var _ns_inverse_square_law_pressure = Float64(_t1_inverse_square_law_pressure - _t0_inverse_square_law_pressure) / Float64(N)
    print("MOJO_TIMING acoustics::inverse_square_law_pressure", _ns_inverse_square_law_pressure, _acc_inverse_square_law_pressure)
    var _acc_wavelength: Float64 = 0.0
    var _t0_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength += wavelength(0.5, 0.5)
    var _t1_wavelength = perf_counter_ns()
    var _ns_wavelength = Float64(_t1_wavelength - _t0_wavelength) / Float64(N)
    print("MOJO_TIMING acoustics::wavelength", _ns_wavelength, _acc_wavelength)
    var _acc_resonant_frequency_pipe_open: Float64 = 0.0
    var _t0_resonant_frequency_pipe_open = perf_counter_ns()
    for _ in range(N):
        _acc_resonant_frequency_pipe_open += resonant_frequency_pipe_open(0.5, 0.5)
    var _t1_resonant_frequency_pipe_open = perf_counter_ns()
    var _ns_resonant_frequency_pipe_open = Float64(_t1_resonant_frequency_pipe_open - _t0_resonant_frequency_pipe_open) / Float64(N)
    print("MOJO_TIMING acoustics::resonant_frequency_pipe_open", _ns_resonant_frequency_pipe_open, _acc_resonant_frequency_pipe_open)
    var _acc_resonant_frequency_pipe_closed: Float64 = 0.0
    var _t0_resonant_frequency_pipe_closed = perf_counter_ns()
    for _ in range(N):
        _acc_resonant_frequency_pipe_closed += resonant_frequency_pipe_closed(0.5, 0.5)
    var _t1_resonant_frequency_pipe_closed = perf_counter_ns()
    var _ns_resonant_frequency_pipe_closed = Float64(_t1_resonant_frequency_pipe_closed - _t0_resonant_frequency_pipe_closed) / Float64(N)
    print("MOJO_TIMING acoustics::resonant_frequency_pipe_closed", _ns_resonant_frequency_pipe_closed, _acc_resonant_frequency_pipe_closed)
    var _acc_doppler_frequency: Float64 = 0.0
    var _t0_doppler_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_doppler_frequency += doppler_frequency(0.5, 0.5, 0.5, 0.5)
    var _t1_doppler_frequency = perf_counter_ns()
    var _ns_doppler_frequency = Float64(_t1_doppler_frequency - _t0_doppler_frequency) / Float64(N)
    print("MOJO_TIMING acoustics::doppler_frequency", _ns_doppler_frequency, _acc_doppler_frequency)
    var _acc_reverberation_time_sabine: Float64 = 0.0
    var _t0_reverberation_time_sabine = perf_counter_ns()
    for _ in range(N):
        _acc_reverberation_time_sabine += reverberation_time_sabine(0.5, 0.5)
    var _t1_reverberation_time_sabine = perf_counter_ns()
    var _ns_reverberation_time_sabine = Float64(_t1_reverberation_time_sabine - _t0_reverberation_time_sabine) / Float64(N)
    print("MOJO_TIMING acoustics::reverberation_time_sabine", _ns_reverberation_time_sabine, _acc_reverberation_time_sabine)
    var _acc_noise_reduction_coefficient: Float64 = 0.0
    var _t0_noise_reduction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_noise_reduction_coefficient += noise_reduction_coefficient(0.5, 0.5, 0.5, 0.5)
    var _t1_noise_reduction_coefficient = perf_counter_ns()
    var _ns_noise_reduction_coefficient = Float64(_t1_noise_reduction_coefficient - _t0_noise_reduction_coefficient) / Float64(N)
    print("MOJO_TIMING acoustics::noise_reduction_coefficient", _ns_noise_reduction_coefficient, _acc_noise_reduction_coefficient)
    var _acc_decibel_sum_2: Float64 = 0.0
    var _t0_decibel_sum_2 = perf_counter_ns()
    for _ in range(N):
        _acc_decibel_sum_2 += decibel_sum_2(0.5, 0.5)
    var _t1_decibel_sum_2 = perf_counter_ns()
    var _ns_decibel_sum_2 = Float64(_t1_decibel_sum_2 - _t0_decibel_sum_2) / Float64(N)
    print("MOJO_TIMING acoustics::decibel_sum_2", _ns_decibel_sum_2, _acc_decibel_sum_2)
    var _acc_distance_doubling_attenuation: Float64 = 0.0
    var _t0_distance_doubling_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_distance_doubling_attenuation += distance_doubling_attenuation()
    var _t1_distance_doubling_attenuation = perf_counter_ns()
    var _ns_distance_doubling_attenuation = Float64(_t1_distance_doubling_attenuation - _t0_distance_doubling_attenuation) / Float64(N)
    print("MOJO_TIMING acoustics::distance_doubling_attenuation", _ns_distance_doubling_attenuation, _acc_distance_doubling_attenuation)
