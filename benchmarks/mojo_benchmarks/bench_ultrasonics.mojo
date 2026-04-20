"""bench_ultrasonics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ultrasonics import acoustic_impedance, reflection_coefficient, attenuation_loss, doppler_frequency_shift, pulse_repetition_frequency, axial_resolution, lateral_resolution, acoustic_pressure_spl, ultrasound_power, thermal_index
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

    var _acc_acoustic_impedance: Float64 = 0.0
    var _t0_acoustic_impedance = perf_counter_ns()
    for _ in range(N):
        _acc_acoustic_impedance += acoustic_impedance(0.5, 0.5)
    var _t1_acoustic_impedance = perf_counter_ns()
    var _ns_acoustic_impedance = Float64(_t1_acoustic_impedance - _t0_acoustic_impedance) / Float64(N)
    print("MOJO_TIMING ultrasonics::acoustic_impedance", _ns_acoustic_impedance, _acc_acoustic_impedance)
    var _acc_reflection_coefficient: Float64 = 0.0
    var _t0_reflection_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_reflection_coefficient += reflection_coefficient(0.5, 0.5)
    var _t1_reflection_coefficient = perf_counter_ns()
    var _ns_reflection_coefficient = Float64(_t1_reflection_coefficient - _t0_reflection_coefficient) / Float64(N)
    print("MOJO_TIMING ultrasonics::reflection_coefficient", _ns_reflection_coefficient, _acc_reflection_coefficient)
    var _acc_attenuation_loss: Float64 = 0.0
    var _t0_attenuation_loss = perf_counter_ns()
    for _ in range(N):
        _acc_attenuation_loss += attenuation_loss(0.5, 0.5, 0.5)
    var _t1_attenuation_loss = perf_counter_ns()
    var _ns_attenuation_loss = Float64(_t1_attenuation_loss - _t0_attenuation_loss) / Float64(N)
    print("MOJO_TIMING ultrasonics::attenuation_loss", _ns_attenuation_loss, _acc_attenuation_loss)
    var _acc_doppler_frequency_shift: Float64 = 0.0
    var _t0_doppler_frequency_shift = perf_counter_ns()
    for _ in range(N):
        _acc_doppler_frequency_shift += doppler_frequency_shift(0.5, 0.5, 0.5, 0.5)
    var _t1_doppler_frequency_shift = perf_counter_ns()
    var _ns_doppler_frequency_shift = Float64(_t1_doppler_frequency_shift - _t0_doppler_frequency_shift) / Float64(N)
    print("MOJO_TIMING ultrasonics::doppler_frequency_shift", _ns_doppler_frequency_shift, _acc_doppler_frequency_shift)
    var _acc_pulse_repetition_frequency: Float64 = 0.0
    var _t0_pulse_repetition_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_repetition_frequency += pulse_repetition_frequency(0.5, 0.5)
    var _t1_pulse_repetition_frequency = perf_counter_ns()
    var _ns_pulse_repetition_frequency = Float64(_t1_pulse_repetition_frequency - _t0_pulse_repetition_frequency) / Float64(N)
    print("MOJO_TIMING ultrasonics::pulse_repetition_frequency", _ns_pulse_repetition_frequency, _acc_pulse_repetition_frequency)
    var _acc_axial_resolution: Float64 = 0.0
    var _t0_axial_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_axial_resolution += axial_resolution(0.5, 0.5)
    var _t1_axial_resolution = perf_counter_ns()
    var _ns_axial_resolution = Float64(_t1_axial_resolution - _t0_axial_resolution) / Float64(N)
    print("MOJO_TIMING ultrasonics::axial_resolution", _ns_axial_resolution, _acc_axial_resolution)
    var _acc_lateral_resolution: Float64 = 0.0
    var _t0_lateral_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_lateral_resolution += lateral_resolution(0.5, 0.5, 0.5)
    var _t1_lateral_resolution = perf_counter_ns()
    var _ns_lateral_resolution = Float64(_t1_lateral_resolution - _t0_lateral_resolution) / Float64(N)
    print("MOJO_TIMING ultrasonics::lateral_resolution", _ns_lateral_resolution, _acc_lateral_resolution)
    var _acc_acoustic_pressure_spl: Float64 = 0.0
    var _t0_acoustic_pressure_spl = perf_counter_ns()
    for _ in range(N):
        _acc_acoustic_pressure_spl += acoustic_pressure_spl(0.5)
    var _t1_acoustic_pressure_spl = perf_counter_ns()
    var _ns_acoustic_pressure_spl = Float64(_t1_acoustic_pressure_spl - _t0_acoustic_pressure_spl) / Float64(N)
    print("MOJO_TIMING ultrasonics::acoustic_pressure_spl", _ns_acoustic_pressure_spl, _acc_acoustic_pressure_spl)
    var _acc_ultrasound_power: Float64 = 0.0
    var _t0_ultrasound_power = perf_counter_ns()
    for _ in range(N):
        _acc_ultrasound_power += ultrasound_power(0.5, 0.5)
    var _t1_ultrasound_power = perf_counter_ns()
    var _ns_ultrasound_power = Float64(_t1_ultrasound_power - _t0_ultrasound_power) / Float64(N)
    print("MOJO_TIMING ultrasonics::ultrasound_power", _ns_ultrasound_power, _acc_ultrasound_power)
    var _acc_thermal_index: Float64 = 0.0
    var _t0_thermal_index = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_index += thermal_index(0.5, 0.5, 0.5)
    var _t1_thermal_index = perf_counter_ns()
    var _ns_thermal_index = Float64(_t1_thermal_index - _t0_thermal_index) / Float64(N)
    print("MOJO_TIMING ultrasonics::thermal_index", _ns_thermal_index, _acc_thermal_index)
